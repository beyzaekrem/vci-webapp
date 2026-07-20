#ifndef GIBBS_TASKS_RECORDCAPTURE_H
#define GIBBS_TASKS_RECORDCAPTURE_H

#include <torch/extension.h>
#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <utility>
#include <vector>

#include "buffer.h"
#include "camera.h"
#include "io/cache.h"

class RecordCapture {
 public:
  RecordCapture(std::vector<std::shared_ptr<Camera>> cameras, std::shared_ptr<CacheWriter> cache_writer);
  void Run();
  void Stop();
  int SquenceLength();
  bool IsRunning();
  void SetSkipFrames(int skip);
  void SkipNextFrame();

 private:
  void CaptureThread(int idx);
  void WriteThread(int idx);
  void SchedulerThread();
  void Support();

  std::vector<std::shared_ptr<Camera>> cameras_;
  std::vector<std::vector<torch::Tensor>> calibration_data_;
  pybind11::object matting_network_;
  std::vector<torch::Tensor> background_images_;

  std::vector<std::thread> capture_threads_;
  std::vector<std::thread> threads_;
  std::mutex lock_;

  bool stop_capture_;             // stops the image capture threads
  bool capture_done_;             // capture is done
  bool finish_and_stop_writing_;  // asks the WriterThreads to stop after writing their current frames
  bool is_running_;               // capture record is running
  int counter_;
  std::vector<std::queue<WriteQueueEntry>> new_frames_queues_;
  std::vector<std::queue<WriteQueueEntry>> write_queues_;
  std::vector<int> assigned_frames_;

  std::shared_ptr<CacheWriter> cache_writer_;

  int skip_frames_;
  std::vector<bool> skip_next_;

  std::vector<int> frame_indeces_;
};

#endif  // GIBBS_TASKS_RECORDCAPTURE_H