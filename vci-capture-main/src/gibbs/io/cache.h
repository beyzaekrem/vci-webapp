#ifndef GIBBS_IO_CACHE_H
#define GIBBS_IO_CACHE_H

#include <torch/extension.h>
#include <string>
#include <vector>

#include "buffer.h"
#include "camera.h"
#include "image.h"
#include "util.h"

struct Location {
  int dump_file_idx;
  size_t byte_offset;
};

struct DumpInfo {
  /// @brief Current dump file pointer
  int fp = -1;
  /// @brief Count number of frames for current dump file
  int counter = 0;
  /// @brief Count number of preceding dump files
  int previous_dump_files = 0;
  /// @brief Index of the current dump file in the in the dump files list
  int dump_file_idx = -1;
  /// @brief Protect this dump info
  std::mutex mutex_;
};

/**
 * @brief A continuous recording of multiple cameras on one machine
 *
 * On disk:
 * - Main file <name>.cache
 *   - contains all meta information
 * - Dump files <name>.<idx>.dump
 *   - binary dumps of the transport data
 */
class Cache {
 public:
  std::optional<int> GetFps();

 protected:
  Cache(const std::string& cache_path);

  /// @brief Number of cameras contained in the dump
  int num_cameras_;

  /// @brief Path to the cache file
  const std::string cache_path_;

  /// @brief List of all used dump files
  std::vector<std::string> dump_files_;

  /// @brief Protect dump_files_
  std::mutex dump_files_mutex_;

  /// @brief Mapping from (camera_index, frame_index) to (dump_file_index, offset)
  std::vector<std::vector<Location>> dump_mapping_;

  /// @brief Protect mapping_
  std::mutex dump_mapping_mutex_;

  std::vector<EntryInfo> format_info_;

  std::optional<int> fps_;
};

class CacheReader : public Cache {
 public:
  CacheReader(const std::string& cache_path);

  GibbsImage LoadFrame(int camera_idx, int frame_idx);
  std::string CameraId(int camera_idx);
  int FrameCount();
  std::optional<std::vector<std::string>> CameraIds();

 private:
  std::vector<int> framecount_;
  std::optional<std::vector<std::string>> camera_ids_;
};

class CacheWriter : public Cache, public NonCopyable {
 public:
  CacheWriter(const std::string cache_path, const std::vector<std::string> dump_base_paths,
              const std::vector<std::string> camera_ids);
  ~CacheWriter();

  void WriteFrame(int camera_idx, int frame_idx, int dump_idx, BufferEntry* buffer);
  void SetFps(std::optional<int> fps);
  void WriteCache();

  int GetNumDumps() const;

 private:
  static const int kFramesPerDump = 1000;

  /// @brief Base paths of the dump files
  const std::vector<std::string> dump_base_paths_;
  const std::vector<std::string> camera_ids_;

  /// @brief Track information of all current dump files
  std::vector<DumpInfo> dump_info_;
};

#endif  // GIBBS_IO_CACHE_H
