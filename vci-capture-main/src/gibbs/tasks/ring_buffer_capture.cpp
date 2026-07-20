#include <omp.h>
#include <fstream>
#include <iostream>
#include <queue>
#include <sstream>
#include <thread>
#include "../buffer.h"
#include "image.h"
#include "processing/bayer.h"
#include "processing/codec.h"
#include "processing/color_kernels.h"
#include "processing/color_superkernel.h"
#include "processing/mono_kernels.h"
#include "processing/mono_superkernel.h"
#include "processing/packing.h"
#include "processing/util.h"
#include "util.h"

#include "tasks/ring_buffer_capture.h"

#include <interceptor/logging.h>

#include <c10/cuda/CUDAGuard.h>
#include <cuda_runtime.h>

RingBuffer::RingBuffer(std::vector<std::shared_ptr<Camera>> cameras,
                       std::vector<std::vector<torch::Tensor>> calibration_data, std::vector<int> rotations,
                       std::shared_ptr<vci::gibbs::Matting> matting_network, std::vector<GibbsImage> background_images,
                       float threshold)
    : cameras_(cameras),
      calibration_data_(calibration_data),
      rotations_(rotations),
      matting_network_(matting_network),
      background_images_(background_images),
      is_running_(false),
      buffer_queue_(32),
      matting_queue_(12),
      jpg_encoding_queue_(8),
      mask_encoding_queue_(8) {
  if (cameras.size() != background_images_.size()) {
    vci::interceptor::logger()->error("Need as many cameras as background images.");
  }
  threshold_ = threshold;
}

RingBuffer::~RingBuffer() {
  Stop();
  while (!event_pool_.empty()) {
    auto& event = event_pool_.front();
    cudaEventDestroy(event);
    event_pool_.pop();
  }
}

void RingBuffer::Run() {
  std::lock_guard<std::mutex> lock(control_mutex_);
  pybind11::gil_scoped_release release;  // Release the GIL
  if (is_running_) {
    return;
  }
  counter_ = 0;
  jpg_counters_.resize(cameras_.size());
  mask_counters_.resize(cameras_.size());
  for (int i = 0; i < cameras_.size(); ++i) {
    jpg_counters_[i] = 0;
    mask_counters_[i] = 0;
  }
  stop_ = false;

#ifdef RING_BUFFER_LATENCY_TEST_ENABLE
  durations_ms_jpg_.reserve(latency_num_samples_);
  durations_ms_mask_.reserve(latency_num_samples_);
  durations_ms_jpg_.clear();
  durations_ms_mask_.clear();
#endif

  for (int i = 0; i < 50; ++i) {  //<-- ring buffer depth here
    masks_.push_back(std::vector<EncodedImage>(cameras_.size()));
    images_.push_back(std::vector<EncodedImage>(cameras_.size()));
  }
  for (int i = 0; i < cameras_.size(); ++i) {
    threads_.emplace_back(&RingBuffer::capture_thread, this, i);
  }
  for (int i = 0; i < 4; ++i) {
    threads_.emplace_back(&RingBuffer::image_processing_thread, this);
  }
  for (int i = 0; i < 4; ++i) {
    threads_.emplace_back(&RingBuffer::jpg_encoding_thread, this);
  }
  for (int i = 0; i < 4; ++i) {
    threads_.emplace_back(&RingBuffer::matting_thread, this);
  }
  for (int i = 0; i < 4; ++i) {
    threads_.emplace_back(&RingBuffer::mask_encoding_thread, this);
  }
  is_running_ = true;
}

bool RingBuffer::IsRunning() {
  return is_running_;
}

void RingBuffer::SetThreshold(float threshold) {
  threshold_ = threshold;
}

void RingBuffer::Stop() {
  std::lock_guard<std::mutex> lock(control_mutex_);
  pybind11::gil_scoped_release release;
  stop_ = true;
  vci::interceptor::logger()->debug("RingBuffer::Stop(), joining threads...");
  for (int i = 0; i < threads_.size(); ++i) {
    threads_[i].join();
  }
  threads_.clear();
  masks_.clear();
  images_.clear();
  vci::interceptor::logger()->debug("RingBuffer threads joined, clearing queues...");
  // Empty queues
  while (true) {
    std::vector<BufferQueueEntry> buffers = buffer_queue_.try_pop();
    if (buffers.empty()) {
      break;
    }
    buffers[0].entry->Unlock();
  }
  while (true) {
    std::vector<MattingQueueEntry> buffers = matting_queue_.try_pop();
    if (buffers.empty()) {
      break;
    }
    return_event_to_pool(buffers[0].event);
    buffers[0].image.release();
  }
  while (true) {
    auto buffers = jpg_encoding_queue_.try_pop();
    if (buffers.empty()) {
      break;
    }
    return_event_to_pool(buffers[0].event);
    buffers[0].image.release();
  }
  while (true) {
    auto buffers = mask_encoding_queue_.try_pop();
    if (buffers.empty()) {
      break;
    }
    return_event_to_pool(buffers[0].event);
    buffers[0].mask.release();
  }

  vci::interceptor::logger()->debug("RingBuffer::Stop() is done");

  is_running_ = false;
}

int RingBuffer::LastFrame() {
  return counter_ - 1;
}

std::vector<EncodedImage> RingBuffer::GetMasks(int frame_idx) {
  vci::interceptor::logger()->debug("GetMasks: counter {}; frame_idx {}; size masks {}; size entry {}.", counter_,
                                    frame_idx, masks_.size(), masks_[frame_idx % images_.size()].size());
  CheckIndex(frame_idx, static_cast<int>(masks_.size()));
  return masks_[frame_idx % masks_.size()];
}

std::vector<EncodedImage> RingBuffer::GetImages(int frame_idx) {
  vci::interceptor::logger()->debug("GetImages: counter {}; frame_idx {}; size images {}; size entry {}.", counter_,
                                    frame_idx, images_.size(), images_[frame_idx % images_.size()].size());
  CheckIndex(frame_idx, static_cast<int>(images_.size()));
  return images_[frame_idx % images_.size()];
}

void RingBuffer::CheckIndex(int frame_idx, int stack_size) {
  if (counter_ <= 0) {
    throw std::out_of_range("RingBuffer is empty.");
  }
  // Check for "Future" index
  // The user is asking for a frame we haven't reached yet.
  if (frame_idx >= counter_) {
    throw std::out_of_range("Frame index " + std::to_string(frame_idx) +
                            " is in the future. Current counter: " + std::to_string(counter_));
  }
  // Check for "Stale" index (The Ring Buffer Wrap-around)
  // If frame_idx is older than the oldest element we keep.
  if (frame_idx < (counter_ - stack_size)) {
    throw std::out_of_range("Frame index " + std::to_string(frame_idx) +
                            " has been overwritten. Oldest available: " + std::to_string(counter_ - stack_size));
  }
}

void RingBuffer::capture_thread(int idx) {
  vci::interceptor::logger()->debug("capture_thread: {}", idx);
#ifdef RING_BUFFER_LOG_CAMERA_FPS
  auto orientation_time = std::chrono::high_resolution_clock::now();
  auto one_second = std::chrono::seconds(1);
  int fps_counter = 0;
#endif
  // Frame counting
  int raw_frame_number = -1;
  int first_frame_number = -1;  // Offset that is subtracted from frame_number
  while (!stop_) {
    if (!cameras_[idx]->IsRunning()) {
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
      continue;
    }
    // Capture next frame
    BufferEntry* entry = nullptr;
    try {
      entry = cameras_[idx]->CaptureNext(1000);
    } catch (BufferTimeout e) {
      continue;
    } catch (TransportInterrupted e) {
      vci::interceptor::logger()->warn("TransportInterrupted! Camera {}", idx);
      continue;
    }
    // Check and count frames
    if (entry == nullptr) {
      vci::interceptor::logger()->warn("Camera {} captured EMPTY frame after frame {}.", idx, raw_frame_number);
    } else {
#ifdef RING_BUFFER_LOG_CAMERA_FPS
      fps_counter++;
#endif
      if (first_frame_number == -1) {
        first_frame_number = entry->Info()->frame_number;
        raw_frame_number = first_frame_number - 1;
      }
      while (++raw_frame_number < entry->Info()->frame_number) {
        vci::interceptor::logger()->warn("Camera {} dropped frame {}.", idx, raw_frame_number);
      }
      vci::interceptor::logger()->debug("Camera {} captured frame {}.", idx, raw_frame_number);
      // Push to queue
      BufferQueueEntry queue_entry{
          .camera_idx = idx,
          .frame_idx = raw_frame_number - first_frame_number,
          .entry = entry,
#ifdef RING_BUFFER_LATENCY_TEST_ENABLE
          .capture_time = std::chrono::steady_clock::now(),
#endif
      };
      if (!buffer_queue_.push(queue_entry)) {
        vci::interceptor::logger()->warn("Buffer Queue Size Limit Reached ({})! Dropping frame {} of camera {}",
                                         buffer_queue_.capacity(), raw_frame_number, idx);
        queue_entry.entry->Unlock();
      }
    }
#ifdef RING_BUFFER_LOG_CAMERA_FPS
    if (std::chrono::high_resolution_clock::now() >= orientation_time + one_second) {
      vci::interceptor::logger()->info("Camera {} fps: {}", idx, fps_counter);
      fps_counter = 0;
      orientation_time = orientation_time + one_second;
    }
#endif
  }
}

void RingBuffer::image_processing_thread() {
  auto at_stream = at::cuda::getStreamFromPool(false, 0);
  cudaStream_t stream = at_stream.stream();
  at::cuda::CUDAStreamGuard stream_guard(at_stream);
  torch::NoGradGuard no_grad;
  while (!stop_) {
    // Wait if empty
    std::vector<BufferQueueEntry> buffers = buffer_queue_.try_pop();
    if (buffers.empty()) {
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
      continue;
    }
    // Do processing
    BufferQueueEntry buffer = buffers[0];
    vci::interceptor::logger()->debug("processing of frame {} {}", buffer.frame_idx, buffer.camera_idx);
    torch::Tensor buffer_content = vci::gibbs::BufferEntryToDeviceAsync(buffer.entry, torch::Device(torch::kCUDA, 0));
    std::vector<torch::Tensor> c = calibration_data_[buffer.camera_idx];
    int rotate = rotations_[buffer.camera_idx];

    GibbsImage image;
    if (cameras_[buffer.camera_idx]->Info().camera_type == ImageType::Color) {  // is color
      image = vci::gibbs::CombinedKernel_Color(buffer_content, buffer.entry->Info(), c[0], c[1], c[2] / 2,
                                               c[3]);  // ~ 2.84554 ms - 3.37933 ms
    } else {
      image = vci::gibbs::CombinedKernel_Mono(buffer_content, buffer.entry->Info(), c[2], c[3]);  // ~ 3.1 - 3.5 ms
      // outputs 1 Channel image [H, W]

      int stride = 2;  // pick every 2nd pixel

      auto H = image.size(0);
      auto W = image.size(1);

      // Allocate the downsampled tensor
      torch::Tensor mono_small =
          torch::empty({H / stride, W / stride}, torch::TensorOptions().dtype(image.dtype()).device(image.device()));

      // Copy every 2nd pixel manually (cheap CUDA kernel)
      mono_small = image.pixels.index({torch::indexing::Slice(0, H, stride), torch::indexing::Slice(0, W, stride)})
                       .clone();  // clone allocates a new contiguous tensor

      //-> expand without memory copy to [3, H, W]
      image.pixels = mono_small.unsqueeze(0).expand({3, mono_small.size(0), mono_small.size(1)});
    }
    if (rotate != 0) {
      image.pixels = torch::rot90(image.pixels, rotate, {(1), (2)});
    }

    vci::interceptor::logger()->debug("done processing of frame {} {}", buffer.frame_idx, buffer.camera_idx);

    // Add to queues
    {
      // Matting
      cudaEvent_t event = RingBuffer::get_event_from_pool();
      cuda_error_check(cudaEventRecord(event, stream));
      MattingQueueEntry matting_queue_entry{
          .camera_idx = buffer.camera_idx,
          .frame_idx = buffer.frame_idx,
          .image = image,
          .event = event,
#ifdef RING_BUFFER_LATENCY_TEST_ENABLE
          .capture_time = buffer.capture_time,
#endif
      };
      if (!matting_queue_.push(matting_queue_entry)) {
        vci::interceptor::logger()->warn("Matting Queue Size Limit Reached ({})! Dropping frame {} of camera {}",
                                         matting_queue_.capacity(), buffer.frame_idx, buffer.camera_idx);
        // Clean up
        return_event_to_pool(event);
        buffer.entry->Unlock();  // Wait until after event, so we know it is no longer needed
        continue;                // No need to store jpg
      }
    }
    {
      // Jpg
      cudaEvent_t event = RingBuffer::get_event_from_pool();
      cuda_error_check(cudaEventRecord(event, stream));
      JpgEncodingQueueEntry jpg_encoding_queue_entry{
          .entry = buffer.entry,
          .camera_idx = buffer.camera_idx,
          .frame_idx = buffer.frame_idx,
          .image = image,
          .event = event,
#ifdef RING_BUFFER_LATENCY_TEST_ENABLE
          .capture_time = buffer.capture_time,
#endif
      };
      if (!jpg_encoding_queue_.push(jpg_encoding_queue_entry)) {
        vci::interceptor::logger()->warn("JPG Encoding Queue Size Limit Reached ({})! Dropping frame {} of camera {}",
                                         jpg_encoding_queue_.capacity(), buffer.frame_idx, buffer.camera_idx);
        // Clean up
        return_event_to_pool(event);
        buffer.entry->Unlock();  // Wait until after event, so we now it is no longer needed
      }
    }
  }
}

void RingBuffer::matting_thread() {
  // Wait to get four frames together in matting_pool
  // Sync with their events
  // Run Matting batched in own stream
  // Add to mask_encoding_pool
  auto at_stream = at::cuda::getStreamFromPool(false, 0);
  cudaStream_t stream = at_stream.stream();
  at::cuda::CUDAStreamGuard stream_guard(at_stream);
  torch::NoGradGuard no_grad;
  while (!stop_) {
    // Wait if empty
    std::vector<MattingQueueEntry> buffers = matting_queue_.try_pop(1);
    if (buffers.empty()) {
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
      continue;
    }
    MattingQueueEntry buffer = buffers[0];
    cuda_error_check(cudaStreamWaitEvent(stream, buffer.event, 0));
    vci::interceptor::logger()->debug("Perform matting of frame {} {}", buffer.frame_idx, buffer.camera_idx);
    GibbsImage mask = matting_network_->infer(buffer.image, background_images_[buffer.camera_idx]);
    vci::interceptor::logger()->debug("matting done of frame {} {}", buffer.frame_idx, buffer.camera_idx);
    // Add to queue
    cudaEvent_t event = RingBuffer::get_event_from_pool();
    cuda_error_check(cudaEventRecord(event, stream));
    MaskEncodingQueueEntry mask_encoding_queue_entry{
        .camera_idx = buffer.camera_idx,
        .frame_idx = buffer.frame_idx,
        .mask = mask,
        .event = event,
#ifdef RING_BUFFER_LATENCY_TEST_ENABLE
        .capture_time = buffer.capture_time,
#endif
    };
    if (!mask_encoding_queue_.push(mask_encoding_queue_entry)) {
      vci::interceptor::logger()->warn("Mask Encoding Queue Size Limit Reached ({})! Dropping frame {} of camera {}",
                                       mask_encoding_queue_.capacity(), buffer.frame_idx, buffer.camera_idx);
      // Clean up
      return_event_to_pool(mask_encoding_queue_entry.event);
    }
    return_event_to_pool(buffer.event);
  }
}

void RingBuffer::jpg_encoding_thread() {
  // Wait for a image in jpg_encoding_queue_
  // Run encoding in own stream
  // Copy to cpu async and wait for completion
  // Mark image as available
  auto at_stream = at::cuda::getStreamFromPool(false, 0);
  cudaStream_t stream = at_stream.stream();
  at::cuda::CUDAStreamGuard stream_guard(at_stream);
  torch::NoGradGuard no_grad;
  while (!stop_) {
    // Wait if empty
    std::vector<JpgEncodingQueueEntry> buffers = jpg_encoding_queue_.try_pop();
    if (buffers.empty()) {
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
      continue;
    }
    // Do processing
    JpgEncodingQueueEntry buffer = buffers[0];
    cuda_error_check(cudaStreamWaitEvent(stream, buffer.event, 0));
    vci::interceptor::logger()->debug("encode jpg of frame {} {}", buffer.frame_idx, buffer.camera_idx);
    auto jpg_image = vci::gibbs::encode_jpg(vci::gibbs::ConvertToUInt8(buffer.image), 95)
                         .to(torch::Device(torch::kCPU), true);  // ~ 0.823296 ms
    buffer.image.release();                                      // free memory of the now no longer needed GibbsImage.
    at_stream.synchronize();
    vci::interceptor::logger()->debug("encode jpg done of frame {} {}", buffer.frame_idx, buffer.camera_idx);
    {
      std::lock_guard<std::recursive_mutex> lock(ring_buffer_mutex_);
      // Repeat missed frames
      if (jpg_counters_[buffer.camera_idx] > 0) {
        while (jpg_counters_[buffer.camera_idx] < buffer.frame_idx) {
          images_[jpg_counters_[buffer.camera_idx] % images_.size()][buffer.camera_idx] =
              images_[(jpg_counters_[buffer.camera_idx] - 1) % images_.size()][buffer.camera_idx];
          jpg_counters_[buffer.camera_idx]++;
        }
      }
      // Insert new frame (maybe also fill previous if it was empty)
      while (jpg_counters_[buffer.camera_idx] <= buffer.frame_idx) {
        images_[jpg_counters_[buffer.camera_idx] % images_.size()][buffer.camera_idx] = jpg_image;
        jpg_counters_[buffer.camera_idx]++;
      }
      // Update global counter
      update_counter();
    }
    // Clean Up
    return_event_to_pool(buffer.event);
    buffer.entry->Unlock();  // Wait until after event, so we now it is no longer needed
#ifdef RING_BUFFER_LATENCY_TEST_ENABLE
    {
      auto end = std::chrono::steady_clock::now();
      auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - buffer.capture_time);
      std::lock_guard<std::mutex> lock(duration_mutex_);
      durations_ms_jpg_.push_back(duration.count());
      if (durations_ms_jpg_.size() == latency_num_samples_) {
        float sum = std::accumulate(durations_ms_jpg_.begin(), durations_ms_jpg_.end(), 0.0f);
        float mean = sum / durations_ms_jpg_.size();
        float sq_sum =
            std::inner_product(durations_ms_jpg_.begin(), durations_ms_jpg_.end(), durations_ms_jpg_.begin(), 0.0f);
        float variance = (sq_sum / durations_ms_jpg_.size()) - (mean * mean);
        float stddev = std::sqrt(variance);
        vci::interceptor::logger()->info("Image to jpg latency: {} ms (std: {}, n: {})", mean, stddev,
                                         latency_num_samples_);
        durations_ms_jpg_.clear();
      }
    }
#endif
  }
}

void RingBuffer::mask_encoding_thread() {
  // Wait for a mask in mask_encoding_pool
  // Run encoding in own stream
  // Copy to cpu async and wait for completion
  // Mark mask as available
  auto at_stream = at::cuda::getStreamFromPool(false, 0);
  cudaStream_t stream = at_stream.stream();
  at::cuda::CUDAStreamGuard stream_guard(at_stream);
  torch::NoGradGuard no_grad;
  int cnt = 0;
  while (!stop_) {
    // Wait if empty
    std::vector<MaskEncodingQueueEntry> buffers = mask_encoding_queue_.try_pop();
    if (buffers.empty()) {
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
      continue;
    }
    // Do processing
    MaskEncodingQueueEntry buffer = buffers[0];
    cuda_error_check(cudaStreamWaitEvent(stream, buffer.event, 0));
    vci::interceptor::logger()->debug("mask encoding of frame {} {}", buffer.frame_idx, buffer.camera_idx);
    EncodedImage matte_enc = vci::gibbs::encode_mask(buffer.mask, threshold_).to(torch::Device(torch::kCPU), true);
    at_stream.synchronize();
    vci::interceptor::logger()->debug("mask encoding done of frame {} {}", buffer.frame_idx, buffer.camera_idx);
    cnt++;
    {
      std::lock_guard<std::recursive_mutex> lock(ring_buffer_mutex_);
      // Repeat missed frames
      if (mask_counters_[buffer.camera_idx] > 0) {
        while (mask_counters_[buffer.camera_idx] < buffer.frame_idx) {
          masks_[mask_counters_[buffer.camera_idx] % masks_.size()][buffer.camera_idx] =
              masks_[(mask_counters_[buffer.camera_idx] - 1) % masks_.size()][buffer.camera_idx];
          mask_counters_[buffer.camera_idx]++;
        }
      }
      // Insert new frame (maybe also fill previous if it was empty)
      while (mask_counters_[buffer.camera_idx] <= buffer.frame_idx) {
        masks_[mask_counters_[buffer.camera_idx] % masks_.size()][buffer.camera_idx] = matte_enc;
        mask_counters_[buffer.camera_idx]++;
      }
      // Update global counter
      update_counter();
    }
    // Clean Up
    return_event_to_pool(buffer.event);
#ifdef RING_BUFFER_LATENCY_TEST_ENABLE
    {
      auto end = std::chrono::steady_clock::now();
      auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - buffer.capture_time);
      std::lock_guard<std::mutex> lock(duration_mutex_);
      durations_ms_mask_.push_back(duration.count());
      if (durations_ms_mask_.size() == latency_num_samples_) {
        float sum = std::accumulate(durations_ms_mask_.begin(), durations_ms_mask_.end(), 0.0f);
        float mean = sum / durations_ms_mask_.size();
        float sq_sum =
            std::inner_product(durations_ms_mask_.begin(), durations_ms_mask_.end(), durations_ms_mask_.begin(), 0.0f);
        float variance = (sq_sum / durations_ms_mask_.size()) - (mean * mean);
        float stddev = std::sqrt(variance);
        vci::interceptor::logger()->info("Image to mask latency: {} ms (std: {}, n: {})", mean, stddev,
                                         latency_num_samples_);
        durations_ms_mask_.clear();
      }
    }
#endif
  }
  std::cout << "processed images: " << cnt << std::endl;
}

cudaEvent_t RingBuffer::get_event_from_pool() {
  cudaEvent_t event;
  if (event_pool_.empty()) {
    cuda_error_check(cudaEventCreate(&event));
  } else {
    std::lock_guard<std::mutex> lock(event_pool_mutex_);
    event = event_pool_.front();
    event_pool_.pop();
  }
  return event;
}

void RingBuffer::return_event_to_pool(cudaEvent_t event) {
  if (cudaEventQuery(event) == cudaSuccess) {
    std::lock_guard<std::mutex> lock(event_pool_mutex_);
    event_pool_.push(event);
  } else {
    cuda_error_check(cudaEventSynchronize(event));
    std::lock_guard<std::mutex> lock(event_pool_mutex_);
    event_pool_.push(event);
  }
}

void RingBuffer::update_counter() {
  std::lock_guard<std::recursive_mutex> lock(ring_buffer_mutex_);
  int min_idx = std::numeric_limits<int>::max();
  for (int i = 0; i < jpg_counters_.size(); ++i) {
    min_idx = std::min(min_idx, jpg_counters_[i]);
  }
  for (int i = 0; i < mask_counters_.size(); ++i) {
    min_idx = std::min(min_idx, mask_counters_[i]);
  }
  counter_ = min_idx;
}
