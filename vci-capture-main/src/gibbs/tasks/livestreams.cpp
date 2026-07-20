#include "livestreams.h"
// CaptureStage

CaptureStage::CaptureStage(std::shared_ptr<Camera> cam, SmartQueue<BufferQueueEntry>& out_queue)
    : camera_(std::move(cam)), out_queue_(out_queue) {}

void CaptureStage::run() {
  while (running_) {
    if (!camera_->IsRunning()) {
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
      continue;
    } else {
      try {
        BufferEntry* entry = camera_->CaptureNext(1000);
        if (entry) {
          BufferQueueEntry e{
              .camera_idx = camera_->Info().capture_card_index, .frame_idx = next_idx_++, .entry = entry};
          out_queue_.push(std::move(e));
        }
      } catch (BufferTimeout e) {
        std::cout << "CaptureStage: Buffer timeout for camera " << camera_->Info().capture_card_index << std::endl;
      } catch (TransportInterrupted e) {
        std::cout << "CaptureStage: Transport interrupted for camera " << camera_->Info().capture_card_index
                  << std::endl;
      } catch (std::exception& e) {
        std::cout << "CaptureStage encountered an error: " << e.what() << std::endl;
      } catch (...) {
        std::cout << "CaptureStage encountered an unknown error." << std::endl;
      }
    }
  }
}

Livestream::Livestream(std::string id, int camera_idx, const ZoomParams& params, size_t buffer_size)
    : id_(std::move(id)),
      camera_idx_(camera_idx),
      params_(params),
      images_(buffer_size),
      counter_(-1),
      slot_mutex_(buffer_size) {}

void Livestream::PushImage(torch::Tensor jpeg_tensor) {
  if (images_.empty()) return;

  const size_t n = images_.size();
  const int next = counter_.load(std::memory_order_relaxed) + 1;
  const size_t slot = static_cast<size_t>(next) % n;

  // Debug sanity:
  assert(slot < slot_mutex_.size());
  assert(slot_mutex_.size() == images_.size());

  std::lock_guard<std::mutex> g(slot_mutex_[slot]);
  images_[slot] = std::move(jpeg_tensor);
  counter_.store(next, std::memory_order_release);
}

torch::Tensor Livestream::GetImage() const {
  if (images_.empty()) return {};
  const int idx = counter_.load(std::memory_order_acquire);
  if (idx < 0) return {};

  const size_t n = images_.size();
  const size_t slot = static_cast<size_t>(idx) % n;

  // Debug sanity:
  assert(slot < slot_mutex_.size());
  assert(slot_mutex_.size() == images_.size());

  std::lock_guard<std::mutex> g(slot_mutex_[slot]);
  return images_[slot];
}

MultiZoomStage::MultiZoomStage(SmartQueue<BufferQueueEntry>& in_queue,
                               std::vector<std::shared_ptr<Livestream>>& livestreams, std::mutex& livestreams_mutex)
    : in_queue_(in_queue), livestreams_(livestreams), livestreams_mutex_(livestreams_mutex) {}

cudaEvent_t MultiZoomStage::get_event() {
  cudaEvent_t ev;
  cudaEventCreate(&ev);
  return ev;
}

void MultiZoomStage::return_event(cudaEvent_t e) {
  cudaEventDestroy(e);
}

void MultiZoomStage::run() {
  while (running_) {
    auto items = in_queue_.try_pop();
    if (items.empty()) {
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
      continue;
    }
    auto buf = std::move(items[0]);
    int cam_idx = buf.camera_idx;
    int frame_idx = buf.frame_idx;
    // Move the raw BufferEntry onto CUDA
    torch::Tensor raw = vci::gibbs::BufferEntryToDeviceAsync(buf.entry, torch::Device(torch::kCUDA, 0));

    // Apply demosaic & undistort
    GibbsImage image;
    // Prepare all parameters for demosaic & undistort
    auto opts = raw.options().dtype(torch::kFloat32);
    auto wb = torch::tensor({1.9f, 1.0f, 1.5f}, opts);   // white-balance for RGB
    auto cc = torch::eye(3, opts).view({9});             // identity 3×3 color matrix
    auto cam = torch::tensor({1, 0, 0, 0, 1, 0}, opts);  // fx=fy=1, cx=cy=0
    auto dc = torch::zeros({5}, opts);                   // no distortion
    auto info = buf.entry->Info();
    if (info->image_type == ImageType::Color) {
      image = vci::gibbs::CombinedKernel_Color(raw, info, wb, cc, cam, dc);
    } else {
      image = vci::gibbs::CombinedKernel_Mono(raw, info, cam, dc);
      image.pixels = image.pixels.unsqueeze(0).expand({3, image.size(0), image.size(1)});
    }

    // For every Livestream whose camera_idx matches, perform zoom + JPEG
    std::vector<std::shared_ptr<Livestream>> streams;
    {
      std::lock_guard<std::mutex> lg(livestreams_mutex_);  // <— the reference member
      streams = livestreams_;                              // copy shared_ptrs
    }
    // now iterate 'streams' safely
    for (auto& ls_ptr : streams) {
      if (ls_ptr->CameraIndex() != cam_idx) {
        continue;
      }
      const ZoomParams& z = ls_ptr->Params();
      // Zoom on CUDA

      GibbsImage zoomed = vci::gibbs::zoom(image, z.center_x, z.center_y, z.client_size, z.zoom_factor, true);

      // Record & wait for CUDA event
      cudaEvent_t event = get_event();
      cudaEventRecord(event, 0);
      cudaStreamWaitEvent(0, event, 0);

      // Encode to JPEG on GPU, copy to CPU
      EncodedImage encoded = vci::gibbs::encode_jpg(vci::gibbs::ConvertToUInt8(zoomed), 95);
      encoded.cpu(true);

      // Synchronize & cleanup
      cudaEventSynchronize(event);
      return_event(event);

      // Store into this livestream’s ring buffer
      ls_ptr->PushImage(std::move(encoded.data));
    }

    buf.entry->Unlock();
  }
}

LivestreamPipeline::LivestreamPipeline(std::vector<std::shared_ptr<Camera>> cameras,
                                       std::vector<std::shared_ptr<Livestream>> livestreams)
    : cameras_(std::move(cameras)), livestreams_(std::move(livestreams)) {
  // One CaptureStage per camera
  for (auto& cam_ptr : cameras_) {
    auto cap = std::make_shared<CaptureStage>(cam_ptr, buffer_queue_);
    capture_stages_.push_back(cap);
    add_stage(cap);
  }

  // One MultiZoomStage
  multizoom_stage_ = std::make_shared<MultiZoomStage>(buffer_queue_, livestreams_, livestreams_mutex_);
  add_stage(multizoom_stage_);
}

void LivestreamPipeline::AddLivestream(std::shared_ptr<Livestream> ls) {
  std::lock_guard<std::mutex> lg(livestreams_mutex_);
  livestreams_.push_back(std::move(ls));
}

void LivestreamPipeline::RemoveLivestream(const std::string& id) {
  std::lock_guard<std::mutex> lg(livestreams_mutex_);
  livestreams_.erase(
      std::remove_if(livestreams_.begin(), livestreams_.end(), [&id](auto& ptr) { return ptr->ID() == id; }),
      livestreams_.end());
}

std::shared_ptr<Livestream> LivestreamPipeline::GetLivestream(const std::string& id) {
  std::lock_guard<std::mutex> lg(livestreams_mutex_);
  auto it = std::find_if(livestreams_.begin(), livestreams_.end(),
                         [&id](const std::shared_ptr<Livestream>& ls) { return ls->ID() == id; });
  if (it != livestreams_.end()) {
    return *it;
  }
  return nullptr;
}
std::vector<std::shared_ptr<Livestream>> LivestreamPipeline::GetLivestreams() {
  std::lock_guard<std::mutex> lg(livestreams_mutex_);
  return livestreams_;
}