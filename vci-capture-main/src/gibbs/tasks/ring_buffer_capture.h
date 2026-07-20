#ifndef GIBBS_TASKS_RINGBUFFER_H
#define GIBBS_TASKS_RINGBUFFER_H

#include <ATen/cuda/CUDAContext.h>
#include <torch/extension.h>
#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <utility>
#include <vector>

#include "camera.h"
#include "image.h"
#include "io/cache.h"
#include "tasks/matting.h"

// #define RING_BUFFER_LATENCY_TEST_ENABLE
// #define RING_BUFFER_LOG_CAMERA_FPS

struct BufferQueueEntry {
  int camera_idx;
  int frame_idx;
  BufferEntry* entry;
#ifdef RING_BUFFER_LATENCY_TEST_ENABLE
  std::chrono::time_point<std::chrono::steady_clock> capture_time;
#endif
};

struct MattingQueueEntry {
  int camera_idx;
  int frame_idx;
  GibbsImage image;
  cudaEvent_t event;
#ifdef RING_BUFFER_LATENCY_TEST_ENABLE
  std::chrono::time_point<std::chrono::steady_clock> capture_time;
#endif
};

struct JpgEncodingQueueEntry {
  BufferEntry* entry;
  int camera_idx;
  int frame_idx;
  GibbsImage image;
  cudaEvent_t event;
#ifdef RING_BUFFER_LATENCY_TEST_ENABLE
  std::chrono::time_point<std::chrono::steady_clock> capture_time;
#endif
};

struct MaskEncodingQueueEntry {
  int camera_idx;
  int frame_idx;
  GibbsImage mask;
  cudaEvent_t event;
#ifdef RING_BUFFER_LATENCY_TEST_ENABLE
  std::chrono::time_point<std::chrono::steady_clock> capture_time;
#endif
};

template <class EntryType>
class SmartQueue {
 public:
  SmartQueue(int capacity) : capacity_(capacity) {}

  int capacity() const {
    return capacity_;
  }

  int size() const {
    return queue_.size();
  }

  void flush() {
    std::lock_guard<std::mutex> lock(queue_mutex_);
    while (!queue_.empty()) {
      queue_.pop();
    }
  }

  // Push entry to queue
  bool push(const EntryType& entry) {
    if (queue_.size() > capacity_) {
      return false;
    }
    std::lock_guard<std::mutex> lock(queue_mutex_);
    queue_.push(entry);
    return true;
  }
  bool push(EntryType&& entry) {
    if (queue_.size() > capacity_) {
      return false;
    }
    std::lock_guard<std::mutex> lock(queue_mutex_);
    queue_.push(std::move(entry));
    return true;
  }

  // Attempt to remove exactly count elements from the queue and return as vector
  // If not enough elements, return empty vector
  std::vector<EntryType> try_pop(int count = 1) {
    std::lock_guard<std::mutex> lock(queue_mutex_);
    if (queue_.size() < static_cast<size_t>(count)) {
      return {};
    }
    std::vector<EntryType> result;
    result.reserve(count);
    for (int i = 0; i < count; ++i) {
      result.push_back(std::move(queue_.front()));
      queue_.pop();
    }
    return result;
  }

 private:
  int capacity_;
  std::queue<EntryType> queue_;
  std::mutex queue_mutex_;
};

class RingBuffer {
 public:
  RingBuffer(std::vector<std::shared_ptr<Camera>> cameras, std::vector<std::vector<torch::Tensor>> calibration_data,
             std::vector<int> rotations, std::shared_ptr<vci::gibbs::Matting> matting_network,
             std::vector<GibbsImage> background_images, float threshold);
  ~RingBuffer();
  void Run();
  void Stop();

  int LastFrame();
  std::vector<EncodedImage> GetMasks(int frame_idx);
  std::vector<EncodedImage> GetImages(int frame_idx);
  void SetThreshold(float threshold);
  bool IsRunning();

 private:
  void capture_thread(int idx);
  void CheckIndex(int frame_idx, int stack_size);
  void image_processing_thread();
  void matting_thread();
  void jpg_encoding_thread();
  void mask_encoding_thread();

  cudaEvent_t get_event_from_pool();
  void return_event_to_pool(cudaEvent_t event);

  void update_counter();

  std::vector<std::shared_ptr<Camera>> cameras_;
  std::vector<std::vector<torch::Tensor>> calibration_data_;
  std::vector<int> rotations_;
  std::shared_ptr<vci::gibbs::Matting> matting_network_;
  std::vector<GibbsImage> background_images_;
  float threshold_;

  std::vector<std::thread> threads_;
  bool stop_;
  bool is_running_;
  std::mutex control_mutex_;

  int counter_;
  std::vector<int> jpg_counters_;
  std::vector<int> mask_counters_;
  std::vector<std::vector<EncodedImage>> masks_;
  std::vector<std::vector<EncodedImage>> images_;
  std::recursive_mutex ring_buffer_mutex_;

  SmartQueue<BufferQueueEntry> buffer_queue_;
  SmartQueue<MattingQueueEntry> matting_queue_;
  SmartQueue<JpgEncodingQueueEntry> jpg_encoding_queue_;
  SmartQueue<MaskEncodingQueueEntry> mask_encoding_queue_;

  std::queue<cudaEvent_t> event_pool_;
  std::mutex event_pool_mutex_;

#ifdef RING_BUFFER_LATENCY_TEST_ENABLE
  std::vector<float> durations_ms_jpg_;
  std::vector<float> durations_ms_mask_;
  const int latency_num_samples_ = 500;
  std::mutex duration_mutex_;
#endif
};

#endif  // GIBBS_TASKS_RINGBUFFER_H