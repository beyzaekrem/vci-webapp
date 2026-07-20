#include "basler_buffer.h"

#include <stdlib.h>
#include <cstring>
#include <fstream>
#include <iostream>

#include <interceptor/logging.h>

#include "util.h"

struct FormatInfo {
  ImageType image_type;
  int bit_depth;
  PixelLayout pixel_layout;
};

const std::map<Pylon::EPixelType, FormatInfo> format_map = {
    {Pylon::PixelType_BayerRG8, {ImageType::Color, 8, PixelLayout::RGGB}},
    {Pylon::PixelType_BayerRG10p, {ImageType::Color, 10, PixelLayout::RGGB}},
    {Pylon::PixelType_BayerRG12p, {ImageType::Color, 12, PixelLayout::RGGB}},
    {Pylon::PixelType_BayerBG12p, {ImageType::Color, 12, PixelLayout::BGGR}},
    {Pylon::PixelType_Mono8, {ImageType::Mono, 8, PixelLayout::Mono}},
    {Pylon::PixelType_Mono10p, {ImageType::Mono, 10, PixelLayout::Mono}},
    {Pylon::PixelType_Mono12p, {ImageType::Mono, 12, PixelLayout::Mono}}};

BaslerBufferEntry::BaslerBufferEntry(const CameraInfo& info) : camera_info_(info) {
  // If you know the payload size up front, set it here. Otherwise, set it in Attach on first frame.
  payload_bytes_ = 0;
}

// Add buffer_data_ member to hold a copy of the buffer
// (in header: std::vector<char> buffer_data_;)

void BaslerBufferEntry::Attach(const Pylon::CGrabResultPtr& grab) {
  grab_ = grab;

  entry_info_.camera_id = camera_info_.camera_id;
  entry_info_.height = grab_->GetHeight();
  entry_info_.width = grab_->GetWidth();
  entry_info_.timestamp_us = static_cast<unsigned long>(grab_->GetTimeStamp());
  entry_info_.frame_number = grab_->GetBlockID();
  Pylon::EPixelType format = grab_->GetPixelType();

  if (format_map.find(format) == format_map.end()) {
    throw std::runtime_error("Unsupported Basler pixel format: " + std::to_string(format));
  }

  entry_info_.image_type = format_map.at(format).image_type;
  entry_info_.bit_depth = format_map.at(format).bit_depth;
  entry_info_.pixel_layout = format_map.at(format).pixel_layout;
  entry_info_.channels = 1;
  entry_info_.packed = true;

  // Pre-allocate buffer if not done yet
  size_t payload_size = grab_->GetPayloadSize();
  if (payload_bytes_ != payload_size) {
    payload_bytes_ = payload_size;
    buffer_data_.resize(payload_bytes_);
  }
  entry_info_.num_bytes = payload_bytes_;
  // Copy buffer data to local storage
  std::memcpy(buffer_data_.data(), grab_->GetBuffer(), payload_bytes_);
}

// Implement BufferEntry interface methods as needed...
const EntryInfo* BaslerBufferEntry::Info() const {
  return &entry_info_;
}

const char* BaslerBufferEntry::Buffer() const {
  // Return pointer to local buffer copy, or nullptr if empty
  return buffer_data_.empty() ? nullptr : buffer_data_.data();
}
size_t BaslerBufferEntry::PayloadBytes() const {
  // Return size of local buffer copy
  return payload_bytes_;
}
const CameraInfo* BaslerBufferEntry::GetCameraInfo() const {
  return &camera_info_;
}
size_t BaslerBufferEntry::WriteTo(std::ofstream& output_file_stream) const {
  output_file_stream.write(Buffer(), PayloadBytes());
  return PayloadBytes();
}
size_t BaslerBufferEntry::WriteTo(int fp) const {
  return ::write(fp, Buffer(), PayloadBytes());
}
void BaslerBufferEntry::Unlock() {
  // Nothing to do, Pylon manages memory via CGrabResultPtr
}
