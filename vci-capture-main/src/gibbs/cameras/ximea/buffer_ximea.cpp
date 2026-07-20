#include "buffer_ximea.h"
#include "buffer.h"

#include <stdlib.h>
#include <cstring>
#include <iostream>

#include <interceptor/logging.h>

#include "util.h"
#include "xi_include.h"
#include "xi_util.h"

struct FormatInfo {
  ImageType image_type;
  int bit_depth;
  PixelLayout pixel_layout;
};

static const std::map<XI_GenTL_Image_Format_e, FormatInfo> format_map = {
    {XI_GenTL_Image_Format_BayerBG8, {ImageType::Color, 8, PixelLayout::BGGR}},
    {XI_GenTL_Image_Format_BayerBG10p, {ImageType::Color, 10, PixelLayout::BGGR}},
    {XI_GenTL_Image_Format_BayerBG12p, {ImageType::Color, 12, PixelLayout::BGGR}},
    {XI_GenTL_Image_Format_BayerRG12p, {ImageType::Color, 12, PixelLayout::RGGB}},
    {XI_GenTL_Image_Format_BayerGR12p, {ImageType::Color, 12, PixelLayout::RGGB}},
    {XI_GenTL_Image_Format_Mono8, {ImageType::Mono, 8, PixelLayout::Mono}},
    {XI_GenTL_Image_Format_Mono10p, {ImageType::Mono, 10, PixelLayout::Mono}},
    {XI_GenTL_Image_Format_Mono12p, {ImageType::Mono, 12, PixelLayout::Mono}},
};

XimeaBufferEntry::XimeaBufferEntry(const CameraInfo* info, GenTL::DS_HANDLE stream_handle, int payload_bytes)
    : camera_info_(info),
      stream_handle_(stream_handle),
      handle_(nullptr),
      data_(static_cast<char*>(aligned_alloc(4096, payload_bytes))),
      payload_bytes_(payload_bytes),
      lock_counter_(0) {
  Announce();
  Queue();
}

XimeaBufferEntry::~XimeaBufferEntry() {
  try {
    Revoke();
  } catch (ExceptionBase e) {
    vci::interceptor::logger()->error("Error");  // TODO: dump backtrace?
  }
}

void XimeaBufferEntry::Queue() {
  std::lock_guard<std::recursive_mutex> guard(state_mutex_);
  if (IsQueued()) {
    vci::interceptor::logger()->error("Buffer is already queued. Cannot queue again.");
  }
  if (lock_counter_ > 0) {
    vci::interceptor::logger()->critical("Buffer cannot be queued because it is still locked.");
  }
  GenTL::GC_ERROR stat = GenTL::DSQueueBuffer(stream_handle_, handle_);
  HandleGenTLErrors("DSQueueBuffer", stat);
}

void XimeaBufferEntry::FrameWasCaptured() {
  std::lock_guard<std::recursive_mutex> guard(state_mutex_);

  // size_t info_filled = GetBufferInfoSizeT(BUFFER_INFO_SIZE_FILLED);
  // size_t info_total = GetBufferInfoSizeT(BUFFER_INFO_DATA_SIZE);
  // if (info_filled < info_total) {
  //   std::cout << "Buffer only got " << info_filled << " out of " << info_total << std::endl;
  //   throw TransportInterrupted();
  // }
  bool new_data = GetBufferInfoBool(BUFFER_INFO_NEW_DATA);
  if (!new_data) {
    vci::interceptor::logger()->info("No new data");
    vci::interceptor::logger()->error("Buffer transport was interrupted. Data is invalid.");
  }

  bool is_incomplete = GetBufferInfoBool(BUFFER_INFO_IS_INCOMPLETE);
  if (is_incomplete) {
    vci::interceptor::logger()->info("Buffer info is incomplete.");
    Queue();
    vci::interceptor::logger()->error("Buffer is Incomplete. Data is invalid.");
  }
  info_.camera_id = camera_info_->camera_id;
  info_.height = GetBufferInfoSizeT(BUFFER_INFO_HEIGHT);
  info_.width = GetBufferInfoSizeT(BUFFER_INFO_WIDTH);
  info_.timestamp_us = GetBufferInfoUInt64(BUFFER_INFO_TIMESTAMP) / 1000ul;
  info_.frame_number = GetBufferInfoUInt64(BUFFER_INFO_FRAMEID);

  auto format = (XI_GenTL_Image_Format_e)GetBufferInfoUInt64(BUFFER_INFO_PIXELFORMAT);
  if (format_map.find(format) == format_map.end()) {
    throw std::runtime_error("Unsupported Ximea pixel format: " + std::to_string(format));
  }
  info_.image_type = format_map.at(format).image_type;
  info_.bit_depth = format_map.at(format).bit_depth;
  info_.pixel_layout = format_map.at(format).pixel_layout;
  info_.packed = true;
  info_.channels = 1;
  info_.num_bytes = payload_bytes_;
  lock_counter_ = 1;
}

bool XimeaBufferEntry::Lock() {
  std::lock_guard<std::recursive_mutex> guard(state_mutex_);
  if (lock_counter_ == 0) {
    return false;
  }
  lock_counter_ += 1;
  return true;
}

void XimeaBufferEntry::Unlock() {
  std::lock_guard<std::recursive_mutex> guard(state_mutex_);
  if (lock_counter_ > 0) {
    lock_counter_ -= 1;
    if (lock_counter_ == 0) {
      Queue();
    }
  }
}

void XimeaBufferEntry::Announce() {
  if (handle_ == nullptr) {
    GenTL::GC_ERROR stat = GenTL::DSAnnounceBuffer(stream_handle_, data_, payload_bytes_, nullptr, &handle_);
    HandleGenTLErrors("DSAnnounceBuffer", stat);
  }
}

void XimeaBufferEntry::Revoke() {
  std::lock_guard<std::recursive_mutex> guard(state_mutex_);
  if (handle_ != nullptr) {
    GenTL::GC_ERROR stat = GenTL::DSRevokeBuffer(stream_handle_, handle_, nullptr, nullptr);
    HandleGenTLErrors("DSRevokeBuffer", stat);
    handle_ = nullptr;
  }
}

bool XimeaBufferEntry::IsQueued() const {
  return GetBufferInfoBool(BUFFER_INFO_IS_QUEUED);
}

bool XimeaBufferEntry::IsLocked() const {
  return lock_counter_ > 0;
}

const char* XimeaBufferEntry::Buffer() const {
  return data_;
}

size_t XimeaBufferEntry::PayloadBytes() const {
  return payload_bytes_;
}

const EntryInfo* XimeaBufferEntry::Info() const {
  return &info_;
}

GenTL::BUFFER_HANDLE XimeaBufferEntry::Handle() {
  return handle_;
}

const CameraInfo* XimeaBufferEntry::GetCameraInfo() const {
  return camera_info_;
}

size_t XimeaBufferEntry::WriteTo(std::ofstream& output_file_stream) const {
  size_t stream_pos = output_file_stream.tellp();
  output_file_stream.write((char*)data_, payload_bytes_);
  if ((output_file_stream.rdstate() & std::ofstream::failbit) != 0) {
    vci::interceptor::logger()->error("Error during file write.");
  }
  return stream_pos;  // this is the byte_offset used in the dump files
}

size_t XimeaBufferEntry::WriteTo(int fp) const {
  size_t stream_pos = lseek(fp, 0, SEEK_CUR);
  size_t stat = write(fp, data_, payload_bytes_);
  if (stat < 0) {
    vci::interceptor::logger()->error("ximea camera: Error during file write.");
  }
  // std::cout << "XimeaBufferEntry::WriteTo -> " << stream_pos << std::endl;
  return stream_pos;  // this is the byte_offset used in the dump files
}

void XimeaBufferEntry::GetBufferInfo(GenTL::BUFFER_INFO_CMD cmd, GenTL::INFO_DATATYPE datatype, void* value,
                                     size_t value_size) const {
  GenTL::GC_ERROR stat = GenTL::DSGetBufferInfo(stream_handle_, handle_, cmd, &datatype, value, &value_size);
  HandleGenTLErrors("DSGetBufferInfo", stat);
}

bool XimeaBufferEntry::GetBufferInfoBool(GenTL::BUFFER_INFO_CMD cmd) const {
  bool8_t value = 0;
  GetBufferInfo(cmd, INFO_DATATYPE_BOOL8, &value, sizeof(value));
  return value;
}

size_t XimeaBufferEntry::GetBufferInfoSizeT(GenTL::BUFFER_INFO_CMD cmd) const {
  size_t value = 0;
  GetBufferInfo(cmd, INFO_DATATYPE_SIZET, &value, sizeof(value));
  return value;
}

uint32_t XimeaBufferEntry::GetBufferInfoUInt32(GenTL::BUFFER_INFO_CMD cmd) const {
  uint32_t value = 0;
  GetBufferInfo(cmd, INFO_DATATYPE_UINT32, &value, sizeof(value));
  return value;
}

uint64_t XimeaBufferEntry::GetBufferInfoUInt64(GenTL::BUFFER_INFO_CMD cmd) const {
  uint64_t value = 0;
  GetBufferInfo(cmd, INFO_DATATYPE_UINT64, &value, sizeof(value));
  return value;
}

char* XimeaBufferEntry::GetBufferInfoPtr(GenTL::BUFFER_INFO_CMD cmd) const {
  char* value = 0;
  GetBufferInfo(cmd, INFO_DATATYPE_PTR, &value, sizeof(value));
  return value;
}

// Ximea Frame Buffer

FrameBuffer::FrameBuffer(const CameraInfo* info, int length)
    : camera_info_(info), length_(length), payload_bytes_(0), stream_handle_(nullptr), event_handle_(nullptr) {}

FrameBuffer::~FrameBuffer() {
  try {
    Free();
  } catch (ExceptionBase e) {
    vci::interceptor::logger()->error("{}", e.what());
  }
}

void FrameBuffer::InitializeStream(GenTL::DS_HANDLE stream_handle) {
  GenTL::GC_ERROR stat = GenTL::GCRegisterEvent(stream_handle, EVENT_NEW_BUFFER, &event_handle_);
  HandleGenTLErrors("GCRegisterEvent", stat);
  stream_handle_ = stream_handle;
}

void FrameBuffer::CloseStream() {
  Free();
}

void FrameBuffer::Start() {
  // Try to queue all buffers not currently queued
  for (int i = 0; i < buffer_.size(); ++i) {
    if (!buffer_[i]->IsQueued()) {
      buffer_[i]->Queue();
    }
  }
  GenTL::GC_ERROR stat;
  uint32_t flag = 1;
  size_t flag_size = sizeof(size_t);
  stat = GenTL::DSStartAcquisition(stream_handle_, ACQ_START_FLAGS_DEFAULT, GENTL_INFINITE);
  HandleGenTLErrors("DSStartAcquisition", stat);
  stat = GenTL::GCWritePort(stream_handle_, 0x200310, &flag, &flag_size);
  HandleGenTLErrors("GCWritePort", stat);
}

void FrameBuffer::Stop() {
  size_t flag_size = sizeof(size_t);
  uint32_t flag = 0;
  GenTL::GC_ERROR stat;
  stat = GenTL::GCWritePort(stream_handle_, 0x200320, &flag, &flag_size);
  HandleGenTLErrors("GCWritePort", stat);
  stat = GenTL::DSStopAcquisition(stream_handle_, ACQ_STOP_FLAGS_DEFAULT);
  HandleGenTLErrors("DSStopAcquisition", stat);
  stat = GenTL::DSFlushQueue(stream_handle_, ACQ_QUEUE_ALL_DISCARD);
  HandleGenTLErrors("DSFlushQueue", stat);
}

XimeaBufferEntry* FrameBuffer::CaptureNext(int timeout_ms) {
  GenTL::EVENT_NEW_BUFFER_DATA data;
  size_t buff_size = sizeof(data);
  memset(&data, 0, sizeof(data));
  GenTL::GC_ERROR stat = GenTL::EventGetData(event_handle_, &data, &buff_size, timeout_ms);
  if (stat == GenTL::GC_ERROR_LIST::GC_ERR_TIMEOUT) {
    vci::interceptor::logger()->error("Buffer operation has timed out.");
    throw BufferTimeout();  // <- capture_next relies on Timeout being thrown when no image is triggered
  }
  HandleGenTLErrors("EventGetData", stat);
  // Success
  XimeaBufferEntry* entry = buffer_map_[data.BufferHandle];
  if (entry->Handle() !=
      data.BufferHandle) {  // <- this seg faults when Buffer operation has timed out (entry is invalid)
    vci::interceptor::logger()->error("Mismatch between entry handle and data buffer handle.");
  }
  entry->FrameWasCaptured();
  return entry;
}

void FrameBuffer::SetLength(int length) {
  if (length != length_) {
    length_ = length;
    if (buffer_.size() > length_) {
      Free();
    }
  }
}

void FrameBuffer::SetPayload(int payload_bytes) {
  if (payload_bytes_ != payload_bytes) {
    Free();
    payload_bytes_ = payload_bytes;
  }
}

void FrameBuffer::Allocate() {
  if (buffer_.size() == length_) {
    return;
  }
  if (payload_bytes_ == 0) {
    vci::interceptor::logger()->error("Payload not set.");
  }
  if (stream_handle_ == nullptr) {
    vci::interceptor::logger()->error("Stream handle not set.");
  }
  if (event_handle_ == nullptr) {
    vci::interceptor::logger()->error("Event handle not set.");
  }
  int old_length = buffer_.size();
  buffer_.resize(length_);
  for (int i = old_length; i < length_; ++i) {
    buffer_[i] = new XimeaBufferEntry(camera_info_, stream_handle_, payload_bytes_);
    buffer_map_[buffer_[i]->Handle()] = buffer_[i];
  }
}

void FrameBuffer::Free() {
  if (buffer_.size() == 0) {
    return;
  }
  GenTL::GC_ERROR stat = GenTL::DSFlushQueue(stream_handle_, ACQ_QUEUE_ALL_DISCARD);
  HandleGenTLErrors("DSFlushQueue", stat);
  for (int i = 0; i < buffer_.size(); ++i) {
    buffer_[i]->Revoke();
    delete buffer_[i];
  }
  buffer_.clear();
  buffer_map_.clear();
}

void FrameBuffer::ForceQueue() {
  for (int i = 0; i < buffer_.size(); ++i) {
    while (buffer_[i]->IsLocked()) {
      buffer_[i]->Unlock();
    }
    if (!buffer_[i]->IsQueued()) {
      buffer_[i]->Queue();
    }
  }
}

int FrameBuffer::NumQueued() {
  int num_queued = 0;
  for (const auto* entry : buffer_) {
    if (entry != nullptr && entry->IsQueued()) {
      num_queued += 1;
    }
  }
  return num_queued;
}
