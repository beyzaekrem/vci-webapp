#ifndef CAPTN_SIMULATED_BUFFER_H
#define CAPTN_SIMULATED_BUFFER_H

#include <fstream>
#include <string>
#include <vector>

#include "buffer.h"  // for EntryInfo and CameraInfo
/**
 * @brief Buffer Entry of simulated camera
 */
class SimulatedBufferEntry : public BufferEntry {
 public:
  // Pool constructs entries directly
  SimulatedBufferEntry(const CameraInfo* camera_info, EntryInfo entry_info, const std::vector<char>* frame_data);

  const EntryInfo* Info() const override;
  const CameraInfo* GetCameraInfo() const override;
  const char* Buffer() const override;
  size_t PayloadBytes() const override;
  size_t WriteTo(std::ofstream&) const override;
  size_t WriteTo(int fp) const override;
  void Unlock() override;  // deletes this

 private:
  const CameraInfo* camera_info_;
  EntryInfo entry_info_;
  const std::vector<char>* data_;  // non-owning ptr into pool
};

/**
 * @brief Buffer of simualted camera. Constructs frames (BufferEntry) and returns them on CaptureNext.
 */
class SimulatedBuffer {
 public:
  /**
   * @param info Pointer to the simulated camera info.
   * @param width Frame width in pixels.
   * @param height Frame height in pixels.
   * @param bit_depth Bit depth per pixel channel (e.g., 8 or 12).
   * @param is_color Whether this buffer represents a color image.
   */
  SimulatedBuffer(const CameraInfo* info, int width, int height, int bit_depth, PixelLayout pixel_layout);
  SimulatedBufferEntry* CaputreNext();

 private:
  const CameraInfo* camera_info_;
  EntryInfo entry_info_template_;
  std::vector<char> data_;
  std::vector<std::vector<char>> data_list_;
  size_t current_frame_idx_ = 0;
  uint64_t frame_number_ = 0;
};

#endif  // CAPTN_SIMULATED_BUFFER_ENTRY_