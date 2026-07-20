// orbbec_buffer.h
#ifndef ORBBEC_BUFFER_H
#define ORBBEC_BUFFER_H

#include <unistd.h>
#include <fstream>
#include <libobsensor/ObSensor.hpp>
#include <memory>
#include <stdexcept>
#include "buffer.h"
#include "orbbec_camera.h"

class OrbbecBuffer : public BufferEntry {
 public:
  OrbbecBuffer(const CameraInfo* info, ImageType mode, std::shared_ptr<ob::Frame> frame);
  ~OrbbecBuffer() override;

  const EntryInfo* Info() const override;
  const char* Buffer() const override;
  size_t PayloadBytes() const override;
  const CameraInfo* GetCameraInfo() const override;

  size_t WriteTo(std::ofstream& output_file_stream) const override;
  size_t WriteTo(int fp) const override;

  void Unlock() override;

  const std::shared_ptr<ob::Frame>& Frame() const;

 private:
  const CameraInfo* camera_info_;
  EntryInfo entry_info_;
  std::shared_ptr<ob::Frame> frame_;
  size_t payload_bytes_{0};
};

#endif
