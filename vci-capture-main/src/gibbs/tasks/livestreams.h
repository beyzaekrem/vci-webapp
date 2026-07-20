#ifndef RINGBUFFER_PIPELINE_H
#define RINGBUFFER_PIPELINE_H

#include "buffer.h"
#include "camera.h"
#include "io/cache.h"                  // BufferEntry
#include "processing/codec.h"          // vci::gibbs::encode_jpg
#include "processing/color_kernels.h"  // vci::gibbs::ConvertToUInt8
#include "processing/color_superkernel.h"
#include "processing/mono_superkernel.h"
#include "processing/packing.h"
#include "processing/util.h"            // vci::gibbs::BufferEntryToDeviceAsync
#include "processing/zoom.h"            // vci::gibbs::zoom(...)
#include "tasks/ring_buffer_capture.h"  // BufferQueueEntry, JpgEncodingQueueEntry, SmartQueue

#include <atomic>
#include <fstream>
#include <memory>
#include <mutex>
#include <sstream>
#include <thread>
#include <vector>

class IStage {
 public:
  virtual ~IStage() = default;
  virtual void run() = 0;
  virtual void stop() = 0;
};

template <typename In, typename Out>
class Stage : public IStage {
 public:
  virtual ~Stage() = default;
  // Implementations must override run()
  void stop() override {
    running_ = false;
  }

 protected:
  std::atomic<bool> running_{true};
};

// CaptureStage: grabs frames and pushes BufferQueueEntry
class CaptureStage : public Stage<void, BufferQueueEntry> {
 public:
  CaptureStage(std::shared_ptr<Camera> cam, SmartQueue<BufferQueueEntry>& out_queue);
  void run() override;
  void stop() override {
    Stage<void, BufferQueueEntry>::stop();
  }

 private:
  std::shared_ptr<Camera> camera_;
  SmartQueue<BufferQueueEntry>& out_queue_;
  int next_idx_{0};
};

class Pipeline {
 public:
  Pipeline() = default;
  virtual ~Pipeline() = default;

  /// Add a new stage to the pipeline. Ownership is shared_ptr<IStage>.
  void add_stage(std::shared_ptr<IStage> stage) {
    stages_.push_back(stage);
  }

  /// Start every stage in its own thread (in the order they were added).
  virtual void Run() {
    pybind11::gil_scoped_release release;  // Release the GIL
    is_running = true;
    for (auto& stage_ptr : stages_) {
      threads_.emplace_back([stage_ptr]() { stage_ptr->run(); });
    }
  }

  /// Stop all stages, then join all threads.
  virtual void Stop() {
    pybind11::gil_scoped_release release;  // Release the GIL
    try {
      // Tell each stage to stop
      for (auto& stage_ptr : stages_) {
        stage_ptr->stop();
      }
    } catch (const std::exception& e) {
      std::cerr << "Exception during stage stop: " << e.what() << std::endl;
    } catch (...) {
      std::cerr << "Unknown exception during stage stop." << std::endl;
    }
    // Join all threads
    for (auto& t : threads_) {
      if (t.joinable()) {
        t.join();
      }
    }
    threads_.clear();
    is_running = false;
  }

  virtual bool IsRunning() {
    return is_running;
  }

 protected:
  std::vector<std::shared_ptr<IStage>> stages_;
  std::vector<std::thread> threads_;
  std::atomic<bool> is_running = false;

  // TODO add event pool management
};

struct ZoomParams {
  float center_x;
  float center_y;
  std::pair<int, int> client_size;
  float zoom_factor;
};

// Each Livestream holds its own ring‐buffer of JPEG tensors and zoom params
class Livestream {
 public:
  Livestream(std::string id, int camera_idx, const ZoomParams& params, size_t buffer_size = 50);

  // Delete copy and move constructors/assignment operators
  Livestream(const Livestream&) = delete;
  Livestream& operator=(const Livestream&) = delete;
  Livestream(Livestream&&) = delete;
  Livestream& operator=(Livestream&&) = delete;

  /// Write a new JPEG tensor into this livestream’s ring buffer.
  void PushImage(torch::Tensor jpeg_tensor);

  /// Return the JPEG tensor at idx % buffer_size in a single-element vector.
  torch::Tensor GetImage() const;

  /// Accessors
  int CameraIndex() const {
    return camera_idx_;
  }
  const ZoomParams& Params() const {
    return params_;
  }
  void SetParams(const ZoomParams& params) {
    params_ = params;
  }
  const std::string& ID() const {
    return id_;
  }

 private:
  std::string id_;
  int camera_idx_;
  ZoomParams params_;

  // Ring buffer for JPEG‐encoded tensors
  std::vector<torch::Tensor> images_;
  mutable std::mutex images_mutex_;
  std::atomic<int> counter_;

  mutable std::vector<std::mutex> slot_mutex_;
};

// MultiZoomStage: pops PreprocessQueueEntry, performs zoom+JPEG for each Livestream, pushes into each Livestream
/**
 * Performs zooming for each Livestream and encodes the zoomed images to JPEG.
  //TODO instead of this stage, we might want to have a DistributeStage that distributes Images into multiple ZoomStages
 which then give the images to multiple JpegEncodeStages.
 */
class MultiZoomStage : public Stage<BufferQueueEntry, void> {
 public:
  MultiZoomStage(SmartQueue<BufferQueueEntry>& in_queue, std::vector<std::shared_ptr<Livestream>>& livestreams,
                 std::mutex& livestreams_mutex);
  void run() override;
  void stop() override {
    Stage<BufferQueueEntry, void>::stop();
  }

 private:
  SmartQueue<BufferQueueEntry>& in_queue_;
  std::vector<std::shared_ptr<Livestream>>& livestreams_;
  std::mutex& livestreams_mutex_;

  cudaEvent_t get_event();
  void return_event(cudaEvent_t e);
};

/**
 * Manages a set of livestreams and is a pipeline that:
 * - Captures frames from cameras (CaptureStage)
 * - Preprocesses them (e.g., undistorts, demosaics) (DemosaicUndistortStage)
 * - Performs zooming for each livestream (MultiZoomStage)
 */
class LivestreamPipeline : public Pipeline {
 public:
  LivestreamPipeline(std::vector<std::shared_ptr<Camera>> cameras,
                     std::vector<std::shared_ptr<Livestream>> livestreams);

  /// Dynamically add or remove a livestream
  void AddLivestream(std::shared_ptr<Livestream> ls);
  void RemoveLivestream(const std::string& id);
  std::shared_ptr<Livestream> GetLivestream(const std::string& id);
  std::vector<std::shared_ptr<Livestream>> GetLivestreams();

 private:
  // Queues between stages
  SmartQueue<BufferQueueEntry> buffer_queue_{32};

  // Cameras and Livestreams
  std::vector<std::shared_ptr<Camera>> cameras_;
  std::vector<std::shared_ptr<Livestream>> livestreams_;
  std::mutex livestreams_mutex_;

  // Stages
  std::vector<std::shared_ptr<CaptureStage>> capture_stages_;
  std::shared_ptr<MultiZoomStage> multizoom_stage_;
};

#endif  // RINGBUFFER_PIPELINE_H
