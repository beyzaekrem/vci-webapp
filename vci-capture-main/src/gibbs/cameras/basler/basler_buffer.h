#ifndef CAPTN_BASLER_BUFFER_H
#define CAPTN_BASLER_BUFFER_H

#include <pylon/PylonIncludes.h>
#include <map>
#include "buffer.h"

class BaslerBufferEntry : public BufferEntry {
 public:
  BaslerBufferEntry(const CameraInfo& info);
  void Attach(const Pylon::CGrabResultPtr& grab);

  // Implement BufferEntry interface
  const EntryInfo* Info() const override;
  const char* Buffer() const override;
  size_t PayloadBytes() const override;
  const CameraInfo* GetCameraInfo() const override;
  size_t WriteTo(std::ofstream& output_file_stream) const override;
  size_t WriteTo(int fp) const override;
  void Unlock() override;

 private:
  CameraInfo camera_info_;
  EntryInfo entry_info_;
  Pylon::CGrabResultPtr grab_;
  std::vector<char> buffer_data_;  // Holds a copy of the buffer data
  size_t payload_bytes_ = 0;       // Pre-allocated buffer size
};

#endif  // CAPTN_BASLER_BUFFER_H