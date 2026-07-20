// orbbec_buffer.cpp
#include "orbbec_buffer.h"

struct FormatInfo {
  int bit_depth;
  int channels;
  bool packed;
  PixelLayout pixel_layout;
};

static const std::map<OBFormat, FormatInfo> format_map = {
    // depth and color
    {OBFormat::OB_FORMAT_Y8, {8, 1, true, PixelLayout::Mono}},
    {OBFormat::OB_FORMAT_Y16,
     {14, 1, false,
      PixelLayout::Mono}},  // mono images are 14 bit intensity. Each pixel takes up two full bytes (aka 16 bit)

    // color formats
    {OBFormat::OB_FORMAT_RGB888, {8, 3, true, PixelLayout::RGB}},  // = OB_FOMRAT_RGB = 22 in OB SDK
};

static const std::map<OBFormat, FormatInfo> format_map_mono = {
    {OBFormat::OB_FORMAT_Y16,
     {12, 1, false,
      PixelLayout::Mono}},  // each pixel has 12 bit of intensity. Each pixel takes up two full bytes (aka 16 bit).
};

static inline size_t bpp_from_bits(uint8_t bits) {  // not used as of now, but we should in the future, right now since
                                                    // i only handle RGB888 it is fine without it
  if (bits == 0) return 0;
  return (static_cast<size_t>(bits) + 7) / 8;
}
OrbbecBuffer::OrbbecBuffer(
    const CameraInfo* info, ImageType mode,
    std::shared_ptr<ob::Frame> frame)  // store the camera info and take ownership of the frame via the shared pointer
    : camera_info_(info), frame_(std::move(frame)) {
  if (!frame_) {
    throw std::runtime_error("Null Orbbec frame");
  }

  auto vf = frame_->as<ob::VideoFrame>();  // if we can view it as a video frame we can use the width and height, if not
                                           // we set them to 0
  if (!vf) {
    payload_bytes_ = 0;
    entry_info_.width = 0;
    entry_info_.height = 0;
    entry_info_.timestamp_us = 0;
    entry_info_.frame_number = 0;
    return;
  }
  // set the entry info with the width and height of the video frame, timestamp and frame number like done in the
  // simulated buffer the last two are not implemneted yet thus i set them to zero
  entry_info_.camera_id = info->camera_id;
  entry_info_.width = vf->width();
  entry_info_.height = vf->height();
  entry_info_.timestamp_us = vf->systemTimeStamp() * 1000;
  entry_info_.frame_number = vf->index();
  auto format = vf->format();

  // std::cout << format << std::endl;
  const std::map<OBFormat, FormatInfo>& selected_format_map = (mode == ImageType::Mono) ? format_map_mono : format_map;

  if (selected_format_map.find(format) == selected_format_map.end()) {
    // Use the name of the map in the error message for clarity.
    const std::string map_name = (mode == ImageType::Mono) ? "mono" : "color/depth";
    throw std::runtime_error("Unsupported Orbbec " + map_name +
                             " pixel format: " + std::to_string(static_cast<int>(format)));
  }

  const auto& format_info = selected_format_map.at(format);
  entry_info_.bit_depth = format_info.bit_depth;
  entry_info_.image_type = mode;
  entry_info_.channels = format_info.channels;
  entry_info_.packed = format_info.packed;
  entry_info_.pixel_layout = format_info.pixel_layout;  // Mono, RGB, BGR, etc
  if (mode == ImageType::Depth) {
    auto depth_frame = vf->as<ob::DepthFrame>();
    entry_info_.optional_data = depth_frame->getValueScale();  // depth in mm per capture intenstiy bit.
  }

  // Use actual byte count from the SDK. else later we can perhaps do width * height * bpp_from_bits(bit_depth) but for
  // now we just use the data size from the frame
  payload_bytes_ = frame_->dataSize();
  entry_info_.num_bytes = payload_bytes_;
}

OrbbecBuffer::~OrbbecBuffer() {  // on death we release the sdk frame
  Unlock();
}

const EntryInfo* OrbbecBuffer::Info()
    const {  // return the entry info which contains the width, height, format, timestamp and frame number
  return &entry_info_;
}

const char* OrbbecBuffer::Buffer() const {  // return the data pointer from the frame, if it is not set return nullptr
  if (frame_) return static_cast<char*>(frame_->data());
  return nullptr;
}

size_t OrbbecBuffer::PayloadBytes() const {  // the payload bytes which i set above
  return payload_bytes_;
}

const CameraInfo* OrbbecBuffer::GetCameraInfo() const {  // return the camera info which was set in the constructor
  return camera_info_;
}

size_t OrbbecBuffer::WriteTo(
    std::ofstream& out) const {  // write the data to the output file stream, if the frame is not set or the payload
                                 // bytes are 0 return 0 basically implemented like in the simulated buffer
  size_t stream_pos = out.tellp();
  if (!frame_ || payload_bytes_ == 0) {
    return 0;
  }
  out.write(static_cast<const char*>(frame_->data()), payload_bytes_);
  return stream_pos;  // this is the byte_offset used in the dump files
}

size_t OrbbecBuffer::WriteTo(int fp) const {  // chat gpt largely came up with this implementation it worked first try
                                              // hopefully there are not any bugs :D
  size_t stream_pos = lseek(fp, 0, SEEK_CUR);
  if (!frame_ || payload_bytes_ == 0)
    return stream_pos;  // if we dont have a frame or the payload bytes are 0 we cant write anything
  const char* p = static_cast<const char*>(frame_->data());  // get the data pointer from the frame and cast to char
                                                             // pointer which we can then use with ::write()

  size_t stat = write(fp, p, payload_bytes_);

  if (stat < 0) {
    vci::interceptor::logger()->error("orbbec camera: Error during file write.");
  }
  // std::cout << "OrbbecBuffer::WriteTo fp -> " << stream_pos << std::endl;
  return stream_pos;  // this is the byte_offset used in the dump files
}

void OrbbecBuffer::Unlock() {
  if (frame_) frame_.reset();
}

const std::shared_ptr<ob::Frame>& OrbbecBuffer::Frame() const {
  return frame_;
}
