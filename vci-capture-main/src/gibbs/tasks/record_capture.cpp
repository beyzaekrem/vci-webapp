#include <omp.h>
#include <fstream>
#include <iostream>
#include <queue>
#include <sstream>
#include <thread>
#include "processing/bayer.h"
#include "processing/codec.h"
#include "processing/color_kernels.h"
#include "processing/color_superkernel.h"
#include "processing/mono_kernels.h"
#include "processing/mono_superkernel.h"
#include "processing/packing.h"
#include "processing/util.h"
#include "util.h"

#include "record_capture.h"

#include <interceptor/logging.h>

#include <cuda_runtime.h>

RecordCapture::RecordCapture(std::vector<std::shared_ptr<Camera>> cameras, std::shared_ptr<CacheWriter> cache_writer)
    : cameras_(cameras),
      is_running_(false),
      new_frames_queues_(cameras.size()),
      write_queues_(cache_writer->GetNumDumps()),
      cache_writer_(cache_writer),
      assigned_frames_(cache_writer->GetNumDumps(), 0),
      skip_frames_(0),
      skip_next_(cameras.size()),
      frame_indeces_(cameras.size(), -1) {
  for (int i = 0; i < cameras_.size(); i++) {
    skip_next_[i] = false;
  }
}

void RecordCapture::Run() {
  pybind11::gil_scoped_release release;  // Release the GIL
  if (is_running_) {
    return;
  }
  counter_ = 0;
  stop_capture_ = false;
  capture_done_ = false;
  finish_and_stop_writing_ = false;
  for (int i = 0; i < cameras_.size(); i++) {
    capture_threads_.emplace_back(&RecordCapture::CaptureThread, this, i);
  }
  for (int i = 0; i < cache_writer_->GetNumDumps(); i++) {
    threads_.emplace_back(&RecordCapture::WriteThread, this, i);
  }
  threads_.emplace_back(&RecordCapture::SchedulerThread, this);
  threads_.emplace_back(&RecordCapture::Support, this);

  is_running_ = true;
}

void RecordCapture::Stop() {
  pybind11::gil_scoped_release release;

  if (is_running_ == false) {
    return;
  }

  // stop capture threads
  stop_capture_ = true;
  for (int i = 0; i < capture_threads_.size(); i++) {
    capture_threads_[i].join();
  }  // wait for capture to stop

  capture_done_ = true;
  // let Scheduler and Writer Threads write the remaining frames
  // wait for all threads to be done.
  for (int i = 0; i < threads_.size(); ++i) {
    threads_[i].join();
  }
  threads_.clear();
  std::cout << "clearing queues" << std::endl;
  // clear frames queues. Though they should already be empty.
  for (int i = 0; i < new_frames_queues_.size(); ++i) {
    while (!new_frames_queues_[i].empty()) {
      new_frames_queues_[i].front().buffer->Unlock();
      new_frames_queues_[i].pop();
    }
  }
  for (int i = 0; i < write_queues_.size(); ++i) {
    while (!write_queues_[i].empty()) {
      write_queues_[i].front().buffer->Unlock();
      write_queues_[i].pop();
    }
  }
  cache_writer_->WriteCache();

  is_running_ = false;
  std::cout << "Written Frames: " << frame_indeces_ << std::endl;
}

int RecordCapture::SquenceLength() {
  return counter_;
}

bool RecordCapture::IsRunning() {
  return is_running_;
}

void RecordCapture::SetSkipFrames(int skip) {
  skip_frames_ = skip;
}

void RecordCapture::SkipNextFrame() {
  for (int i = 0; i < cameras_.size(); i++) {
    skip_next_[i] = true;
  }
}

void RecordCapture::CaptureThread(int idx) {
  {
    std::lock_guard<std::mutex> guard(lock_);
    vci::interceptor::logger()->info("CaptureThread {}", idx);
  }
  int write_cnt = 0;
  int n = 0;
  int last_frame_number = -1;
  int current_frame_number = -1;
  while (!stop_capture_) {
    BufferEntry* entry = nullptr;
    try {
      std::cout << "recordCapture get image of " << idx << "..." << std::endl;
      entry = cameras_[idx]->CaptureNext(1000);
      std::cout << "recordCapture got image of " << idx << std::endl;

      current_frame_number = entry->Info()->frame_number;
      if (last_frame_number != -1 && current_frame_number != last_frame_number + 1) {
        vci::interceptor::logger()->error("Frame Skipped! Camera: {} expected frame {} but got frame {}.", idx,
                                          last_frame_number + 1, current_frame_number);
        throw FrameSkippedError("Frame Skipped!");
      }
      last_frame_number = current_frame_number;
    } catch (BufferTimeout e) {
      vci::interceptor::logger()->warn("BufferTimeout! Camera: {}", idx);
      continue;
    } catch (TransportInterrupted e) {
      vci::interceptor::logger()->warn("TransporInterrupted! Camera: {}", idx);
    }
    {
      if ((n - skip_frames_) % (skip_frames_ + 1) == 0 && !skip_next_[idx]) {
        std::lock_guard<std::mutex> guard(lock_);
        new_frames_queues_[idx].push({entry, idx, write_cnt});

        if (entry == nullptr) {
          vci::interceptor::logger()->info("Camera {} capture EMPTY frame {}.", idx, n);
        } else {
          vci::interceptor::logger()->info("Camera {} captured frame {}.", idx, n);
        }
        write_cnt++;
      } else {
        // skip image
        skip_next_[idx] = false;
        entry->Unlock();
      }
      n++;
    }
    if (idx == 0) {
      std::cout << "counter_ = write_cnt; " << counter_ << std::endl;
      counter_ = write_cnt;
    }
  }
  std::cout << "CaptureThread " << idx << " captured " << n << " frames" << std::endl;
}

void RecordCapture::WriteThread(int idx) {
  // one thread per dump
  {
    std::lock_guard<std::mutex> guard(lock_);
    std::cout << "WriteThread " << idx << std::endl;
  }
  int n = 0;
  while (!finish_and_stop_writing_ || !write_queues_[idx].empty()) {
    // stop when Scheduler tells us we will recieve no more frames and when we've written all our frames.
    WriteQueueEntry entry;
    if (!write_queues_[idx].empty()) {
      // write_queues_mutex[idx].lock();
      {
        std::lock_guard<std::mutex> guard(lock_);
        if (!write_queues_[idx].empty()) {
          entry = write_queues_[idx].front();
          write_queues_[idx].pop();
        }
      }
      // write_queues_mutex[idx].unlock();
      if (entry.buffer != nullptr) {
        if (true) {
          cache_writer_->WriteFrame(entry.camera_index, entry.frame_index, idx, entry.buffer);
          if (entry.frame_index > frame_indeces_[entry.camera_index]) {
            frame_indeces_[entry.camera_index]++;
            std::cout << "frame_indeces_[entry.camera_index]++:" << frame_indeces_ << std::endl;
          }
        } else {
          std::this_thread::sleep_for(std::chrono::milliseconds(2));
        }
        {
          std::lock_guard<std::mutex> guard(lock_);
          entry.buffer->Unlock();
          n++;
        }
      }
    } else {
      std::this_thread::sleep_for(std::chrono::milliseconds(2));
    }
  }
  std::cout << "Write Thread " << idx << " wrote " << n << " frames" << std::endl;
}

void RecordCapture::SchedulerThread() {
  {
    std::lock_guard<std::mutex> guard(lock_);
    vci::interceptor::logger()->info("Scheduler Thread");  // Do we really need this? - could be used in debug() so it
                                                           // is not saved and only for debugging?
  }
  WriteQueueEntry write_entry;
  int camera_idx = 0;
  int candidate = -1;
  int num_cameras = cameras_.size();
  while (true) {
    if (capture_done_) {
      // no new images are being captured. But we still want to write the last images before we stop
      // we only exit if all new_frames_queues_ are empty.
      bool frames_left = false;
      for (int i = 0; i < new_frames_queues_.size(); i++) {
        if (new_frames_queues_[i].size() > 0) {
          frames_left = true;
          camera_idx = i;
          break;
        }
      }
      if (!frames_left) {
        break;  // All queues empty, exit thread
      }
    }
    // Get entry
    if (write_entry.buffer == nullptr) {
      if (new_frames_queues_[camera_idx].size() > 0) {
        {
          std::lock_guard<std::mutex> guard(lock_);
          // new_frames_queues_mutex[camera_idx].lock();
          write_entry = new_frames_queues_[camera_idx].front();
          new_frames_queues_[camera_idx].pop();
          // new_frames_queues_mutex[camera_idx].unlock();
        }
        camera_idx = (camera_idx + 1) % num_cameras;
      }
    }
    // Get candidate
    if (write_entry.buffer != nullptr) {
      int candidate_assigned_frames = 0;
      // std::cout << "Search candidate" << std::endl;
      for (int i = 0; i < write_queues_.size(); ++i) {
        // Only queues that have less than five entries
        if (write_queues_[i].size() < 5) {
          // Select the one with the least assigned frames
          if (candidate == -1 || assigned_frames_[i] < candidate_assigned_frames) {
            candidate = i;
            candidate_assigned_frames = assigned_frames_[i];
          }
        } else {
          std::cout << "write queue of " << i << " is full (5)" << std::endl;
        }
      }
    }
    // Write entry to candidate (if both exist, otherwise wait a bit)
    if (write_entry.buffer != nullptr && candidate >= 0) {
      {
        std::lock_guard<std::mutex> guard(lock_);
        // write_queues_mutex[candidate].lock();
        write_queues_[candidate].push(write_entry);
        // write_queues_mutex[candidate].unlock();
      }
      assigned_frames_[candidate] += 1;
      write_entry = WriteQueueEntry();
      candidate = -1;
    } else {
      if (write_entry.buffer != nullptr) {
        vci::interceptor::logger()->error("No candidate found for write entry from camera {} frame {}.",
                                          write_entry.camera_index, write_entry.frame_index);
        throw CacheWriterError("No Cache Writer is free to write the current frame");
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
  }
  finish_and_stop_writing_ = true;  // Asks the WriterThreads to stop after writing their current frames
}

void RecordCapture::Support() {
  while (!stop_capture_) {
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
  }
}
