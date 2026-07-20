#include <iostream>
#include <fstream>
#include <sstream>
#include <thread>
#include <queue>
#include <omp.h>
#include "processing/bayer.h"
#include "processing/codec.h"
#include "processing/packing.h"
#include "processing/util.h"
#include "processing/color_kernels.h"
#include "processing/color_superkernel.h"
#include "processing/mono_kernels.h"
#include "processing/mono_superkernel.h"

#include "tasks/capture.h"

#include <interceptor/logging.h>

#include <cuda_runtime.h>

void WriteCsvFile(const std::string &csv_string, std::string fname) {
  std::ofstream csv_file(fname);
  csv_file << csv_string;
  csv_file.close();
}

std::vector<int> CaptureToDiskDump(
    std::vector<std::shared_ptr<Camera>>& cameras,
    std::shared_ptr<CacheWriter> cache_writer,
    long runtime_limit_ms,
    std::function<void()> callback,
    bool track_performance) {
  // Settings
  auto runtime = std::chrono::milliseconds(runtime_limit_ms);
  const int num_cameras = cameras.size();
  const int num_dumps = cache_writer->GetNumDumps();

  // State
  int num_finished = 0;
  std::vector<std::vector<int>> per_camera_fps(num_cameras);
  std::vector<std::vector<int>> per_file_fps(num_dumps);
  std::vector<std::vector<int>> per_buffer_size(num_cameras);
  std::vector<std::vector<EntryInfo>> per_camera_entry_info(num_cameras);
  std::vector<std::vector<std::pair<std::string, long long>>> per_camera_counters(num_cameras);

  std::vector<int> return_frame_counter (num_cameras);


  // Capture and write variables
  auto capture_start = std::chrono::system_clock::now();
  // Each camera capture thread immediately puts new frames into new_frames_queues
  std::vector<std::queue<WriteQueueEntry>> new_frames_queues(num_cameras);
  std::vector<std::mutex> new_frames_queues_mutex(num_cameras);
  // Entries are assigned to write_queues by the scheduler thread
  std::vector<std::queue<WriteQueueEntry>> write_queues(num_dumps);
  std::vector<std::mutex> write_queues_mutex(num_dumps);
  // Keep track of the total number of frames assigned to each dump
  // Used to attempt balanced writing
  std::vector<int> assigned_frames(num_dumps, 0);
  // Not sure of that's needed
  std::mutex api_lock;


  // Capture Parallel
  #pragma omp parallel num_threads(num_cameras + num_dumps + 2)
  {
    int thread_idx = omp_get_thread_num();
    if (thread_idx < num_cameras) {
      // *************************************
      // Capture Threads (One per camera)
      // *************************************
      // Init
      int camera_idx = thread_idx;
      auto start = capture_start;
      int frame_counter = 0;
      int frame_counter_total = 0;
      unsigned long first_frame_us = 0;
      unsigned long last_frame_us;
      // per_camera_counters[camera_idx].push_back({
      //   "XI_CNT_SEL_API_SKIPPED_FRAMES",
      //   cameras[camera_idx]->GetCounter(XI_COUNTER_SELECTOR::XI_CNT_SEL_API_SKIPPED_FRAMES)
      // });
      // per_camera_counters[camera_idx].push_back({
      //   "XI_CNT_SEL_FRAME_BUFFER_OVERFLOW",
      //   cameras[camera_idx]->GetCounter(XI_COUNTER_SELECTOR::XI_CNT_SEL_FRAME_BUFFER_OVERFLOW)
      // });
      // per_camera_counters[camera_idx].push_back({
      //   "XI_CNT_SEL_FRAME_MISSED_TRIGGER_DUETO_FRAME_BUFFER_OVR",
      //   cameras[camera_idx]->GetCounter(XI_COUNTER_SELECTOR::XI_CNT_SEL_FRAME_MISSED_TRIGGER_DUETO_FRAME_BUFFER_OVR)
      // });
      // per_camera_counters[camera_idx].push_back({
      //   "XI_CNT_SEL_FRAME_MISSED_TRIGGER_DUETO_OVERLAP",
      //   cameras[camera_idx]->GetCounter(XI_COUNTER_SELECTOR::XI_CNT_SEL_FRAME_MISSED_TRIGGER_DUETO_OVERLAP)
      // });
      // per_camera_counters[camera_idx].push_back({
      //   "XI_CNT_SEL_TRANSPORT_SKIPPED_FRAMES",
      //   cameras[camera_idx]->GetCounter(XI_COUNTER_SELECTOR::XI_CNT_SEL_TRANSPORT_SKIPPED_FRAMES)
      // });
      // per_camera_counters[camera_idx].push_back({
      //   "XI_CNT_SEL_TRANSPORT_TRANSFERRED_FRAMES",
      //   cameras[camera_idx]->GetCounter(XI_COUNTER_SELECTOR::XI_CNT_SEL_TRANSPORT_TRANSFERRED_FRAMES)
      // });
      cameras[camera_idx]->Start();
      while (std::chrono::system_clock::now() - capture_start < runtime) {
        // Capture
        try {
          BufferEntry* entry = cameras[camera_idx]->CaptureNext(1000);
          int frame_number = entry->Info()->frame_number;
          per_camera_entry_info[camera_idx].push_back(*entry->Info());
          frame_counter += 1;
          frame_counter_total +=1;
          if (first_frame_us == 0) {
            first_frame_us = entry->Info()->timestamp_us;
          } else {
            last_frame_us = entry->Info()->timestamp_us;
          }
          new_frames_queues_mutex[camera_idx].lock();
          new_frames_queues[camera_idx].push({entry, camera_idx, frame_counter_total - 1});
          new_frames_queues_mutex[camera_idx].unlock();
        } catch (BufferTimeout e) {
          vci::interceptor::logger()->warn("BufferTimeout! (Camera: {}, Frame Count {})", camera_idx, frame_counter_total);
        } catch (TransportInterrupted e) {
          vci::interceptor::logger()->warn("TransportInterrupted! (Camera: {}, Frame Counte: {})", camera_idx, frame_counter_total);
        }
        // Logging
        auto end = std::chrono::system_clock::now();
        if (end - start > std::chrono::seconds(1)) {
          per_camera_fps[camera_idx].push_back(frame_counter);
          start = start + std::chrono::seconds(1);
          frame_counter = 0;
        }
      }
      cameras[camera_idx]->Stop();
      // per_camera_counters[camera_idx][0].second = cameras[camera_idx]->GetCounter(XI_COUNTER_SELECTOR::XI_CNT_SEL_API_SKIPPED_FRAMES) - per_camera_counters[camera_idx][0].second;
      // per_camera_counters[camera_idx][1].second = cameras[camera_idx]->GetCounter(XI_COUNTER_SELECTOR::XI_CNT_SEL_FRAME_BUFFER_OVERFLOW) - per_camera_counters[camera_idx][1].second;
      // per_camera_counters[camera_idx][2].second = cameras[camera_idx]->GetCounter(XI_COUNTER_SELECTOR::XI_CNT_SEL_FRAME_MISSED_TRIGGER_DUETO_FRAME_BUFFER_OVR) - per_camera_counters[camera_idx][2].second;
      // per_camera_counters[camera_idx][3].second = cameras[camera_idx]->GetCounter(XI_COUNTER_SELECTOR::XI_CNT_SEL_FRAME_MISSED_TRIGGER_DUETO_OVERLAP) - per_camera_counters[camera_idx][3].second;
      // per_camera_counters[camera_idx][4].second = cameras[camera_idx]->GetCounter(XI_COUNTER_SELECTOR::XI_CNT_SEL_TRANSPORT_SKIPPED_FRAMES) - per_camera_counters[camera_idx][4].second;
      // per_camera_counters[camera_idx][5].second = cameras[camera_idx]->GetCounter(XI_COUNTER_SELECTOR::XI_CNT_SEL_TRANSPORT_TRANSFERRED_FRAMES) - per_camera_counters[camera_idx][5].second;
      // Cleanup
      #pragma omp atomic
      num_finished += 1;
      unsigned long time_diff_us = last_frame_us - first_frame_us;
      per_camera_counters[camera_idx].push_back({
        "TIMESTAMP_DELTA_US", time_diff_us});
      return_frame_counter[camera_idx] = frame_counter_total;
      #pragma omp critical
      {
        for (int i=0; i< per_camera_counters[camera_idx].size(); ++i) {
          vci::interceptor::logger()->info("Camera {}, {}: {}", camera_idx, per_camera_counters[camera_idx][i].first, per_camera_counters[camera_idx][i].second);
        }
        vci::interceptor::logger()->info("Camera {}, total: {}", camera_idx, frame_counter_total);
      }
    } else if (thread_idx < num_cameras + num_dumps) {
      // *************************************
      // Write Threads (One per target file)
      // *************************************
      // Init
      int dump_idx = thread_idx - num_cameras;
      auto start = capture_start;
      int frame_counter = 0;
      while (num_finished < num_cameras) {
        WriteQueueEntry entry;
        if (!write_queues[dump_idx].empty()) {
          write_queues_mutex[dump_idx].lock();
          if (!write_queues[dump_idx].empty()) {
            entry = write_queues[dump_idx].front();
            write_queues[dump_idx].pop();
          }
          write_queues_mutex[dump_idx].unlock();
          if (entry.buffer != nullptr) {
            if (true) {
              cache_writer->WriteFrame(entry.camera_index, entry.frame_index, dump_idx, entry.buffer);
            } else {
              std::this_thread::sleep_for(std::chrono::milliseconds(2));
            }
            api_lock.lock();
            entry.buffer->Unlock();
            api_lock.unlock();
            frame_counter += 1;
          }
        } else {
          std::this_thread::sleep_for(std::chrono::milliseconds(2));
        }
        // Logging
        auto end = std::chrono::system_clock::now();
        if (end - start > std::chrono::seconds(1)) {
          per_file_fps[dump_idx].push_back(frame_counter);
          start = start + std::chrono::seconds(1);
          frame_counter = 0;
        }
      }
    } else if (thread_idx < num_cameras + num_dumps + 1) {
      // *************************************
      // Scheduler Thread
      // *************************************
      WriteQueueEntry write_entry;
      int camera_idx = 0;
      int candidate = -1;
      while (num_finished < num_cameras) {
        // Get entry
        if (write_entry.buffer == nullptr) {
          if (new_frames_queues[camera_idx].size() > 0) {
            new_frames_queues_mutex[camera_idx].lock();
            write_entry = new_frames_queues[camera_idx].front();
            new_frames_queues[camera_idx].pop();
            new_frames_queues_mutex[camera_idx].unlock();
            camera_idx = (camera_idx + 1) % num_cameras;
          }
        }
        // Get candidate
        if (write_entry.buffer != nullptr) {
          int candidate_assigned_frames = 0;
          // std::cout << "Search candidate" << std::endl;
          for (int i=0; i<write_queues.size(); ++i) {
            // Only queues that have less than five entries
            if (write_queues[i].size() < 5) {
              // Select the one with the least assigned frames
              if (candidate == -1 || assigned_frames[i] < candidate_assigned_frames) {
                candidate = i;
                candidate_assigned_frames = assigned_frames[i];
              }
            }
          }
        }
        // Write entry to candidate (if both exist, otherwise wait a bit)
        if (write_entry.buffer != nullptr && candidate >= 0) {
          write_queues_mutex[candidate].lock();
          write_queues[candidate].push(write_entry);
          write_queues_mutex[candidate].unlock();
          assigned_frames[candidate] += 1;
          write_entry = WriteQueueEntry();
          candidate = -1;
        } else {
          std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
      }
    } else {
      // *************************************
      // Logging Thread
      // *************************************
      auto start = capture_start;
      while (num_finished < num_cameras) {
        auto end = std::chrono::system_clock::now();
        if (end - start > std::chrono::seconds(1)) {
          for (int i=0; i<num_cameras; ++i) {
            per_buffer_size[i].push_back(cameras[i]->NumQueued());
          }
          start = start + std::chrono::seconds(1);
          cache_writer->WriteCache();
        }
        if (callback != nullptr) {
          // settings.callback();
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
      }
    }
  }
  return return_frame_counter;
}

std::vector<BufferEntry*> CaptureAll(
    std::vector<std::shared_ptr<Camera>>& cameras,
    int timeout) {
  std::vector<BufferEntry*> buffers(cameras.size(), nullptr);
  for (int camera_idx = 0; camera_idx < cameras.size(); ++camera_idx) {
    try {
      buffers[camera_idx]  = cameras[camera_idx]->CaptureNext(timeout);
    } catch (BufferTimeout e) {
      vci::interceptor::logger()->warn("Buffertimeout! Camera: {}", camera_idx);
    } catch (TransportInterrupted e) {
      vci::interceptor::logger()->warn("TransportInterrupted! Camera: {}", camera_idx);
    } catch(BufferIncomplete e){
      vci::interceptor::logger()->warn("BufferIncomplete! Camera: {}", camera_idx);
    }
  }
  return buffers;
}
