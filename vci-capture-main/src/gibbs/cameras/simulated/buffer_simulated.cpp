#include "buffer_simulated.h"

#include <interceptor/logging.h>
#include <unistd.h>
#include <cstring>
#include <random>

namespace {

static void FillRangeWithNoise(std::vector<char>& buffer, size_t start, size_t end, uint8_t center, uint8_t spread) {
  std::uniform_int_distribution<int> dist(std::max(0, (int)center - (int)spread),
                                          std::min(255, (int)center + (int)spread));
  static std::default_random_engine rng(std::random_device{}());
  for (size_t i = start; i < end; ++i) {
    buffer[i] = static_cast<char>(dist(rng));
  }
}

static void FillBufferWithNoise(std::vector<char>& buffer) {
  FillRangeWithNoise(buffer, 0, buffer.size(), 200, 1);
}

static void DrawScanlineOnBuffer(std::vector<char>& data, const EntryInfo& info, float position) {
  size_t bytes_per_row = 0;
  switch (info.bit_depth) {
    case 10:
      bytes_per_row = (info.width * 5) / 4;
      break;
    case 12:
      bytes_per_row = (info.width * 3) / 2;
      break;
    case 14:
      bytes_per_row = (info.width * 7) / 4;
      break;
    case 16:
      bytes_per_row = info.width * 2;
      break;
    default:
      bytes_per_row = info.width;
      break;
  }

  int stripe_height = std::max(1, info.height / 20);
  int stripe_row = (int)(position * info.height);
  int stripe_row_end = std::min(stripe_row + stripe_height, (int)info.height);

  size_t start = stripe_row * bytes_per_row;
  size_t end = stripe_row_end * bytes_per_row;
  end = std::min(end, data.size());

  FillRangeWithNoise(data, start, end, 20, 1);
}

}  // namespace

SimulatedBuffer::SimulatedBuffer(const CameraInfo* info, int width, int height, int bit_depth, PixelLayout pixel_layout)
    : camera_info_(info) {
  entry_info_template_.camera_id = camera_info_->camera_id;
  entry_info_template_.height = height;
  entry_info_template_.width = width;
  entry_info_template_.image_type = camera_info_->camera_type;
  entry_info_template_.bit_depth = bit_depth;
  entry_info_template_.channels = 1;
  entry_info_template_.timestamp_us = 0;
  entry_info_template_.frame_number = 0;
  entry_info_template_.pixel_layout = pixel_layout;
  entry_info_template_.packed = true;

  size_t num_pixels = width * height;

  size_t total_bytes = 0;

  switch (bit_depth) {
    case 10:
      // 4 pixels = 5 bytes -> (num_pixels * 5) / 4
      total_bytes = (num_pixels * 5) / 4;
      break;
    case 12:
      // 2 pixels = 3 bytes -> (num_pixels * 3) / 2
      total_bytes = (num_pixels * 3) / 2;
      break;
    case 14:
      // 4 pixels = 7 bytes -> (num_pixels * 7) / 4
      total_bytes = (num_pixels * 7) / 4;
      break;
    case 16:
      total_bytes = num_pixels * 2;
      break;
    default:
      total_bytes = num_pixels;  // Default to 8-bit (1 byte)
      break;
  }

  int uniqze_frames = 20;
  data_list_.resize(uniqze_frames, std::vector<char>(total_bytes));
  for (int i = 0; i < data_list_.size(); i++) {
    auto& frame = data_list_[i];
    FillBufferWithNoise(frame);
    DrawScanlineOnBuffer(frame, entry_info_template_, (float)i / data_list_.size());
  }
  entry_info_template_.num_bytes = data_list_[0].size();
}

SimulatedBufferEntry* SimulatedBuffer::CaputreNext() {
  EntryInfo info = entry_info_template_;
  info.camera_id = camera_info_->camera_id;
  info.timestamp_us = static_cast<uint64_t>(
      std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now().time_since_epoch())
          .count());
  info.frame_number = ++frame_number_;

  const std::vector<char>* frame = &data_list_[current_frame_idx_];
  current_frame_idx_ = (current_frame_idx_ + 1) % data_list_.size();

  return new SimulatedBufferEntry(camera_info_, info, frame);
}

//// ------------ Buffer Entry --------------
SimulatedBufferEntry::SimulatedBufferEntry(const CameraInfo* camera_info, EntryInfo entry_info,
                                           const std::vector<char>* frame_data)
    : camera_info_(camera_info), entry_info_(entry_info), data_(frame_data) {}

const EntryInfo* SimulatedBufferEntry::Info() const {
  return &entry_info_;
}

const char* SimulatedBufferEntry::Buffer() const {
  return const_cast<char*>(data_->data());
}

size_t SimulatedBufferEntry::PayloadBytes() const {
  return data_->size();
}

const CameraInfo* SimulatedBufferEntry::GetCameraInfo() const {
  return camera_info_;
}

size_t SimulatedBufferEntry::WriteTo(std::ofstream& output_file_stream) const {
  size_t stream_pos = output_file_stream.tellp();
  output_file_stream.write(data_->data(), data_->size());
  if ((output_file_stream.rdstate() & std::ofstream::failbit) != 0) {
    vci::interceptor::logger()->error("Error during simulated file write.");
  }
  return stream_pos;
}

size_t SimulatedBufferEntry::WriteTo(int fp) const {
  size_t stream_pos = lseek(fp, 0, SEEK_CUR);
  ssize_t stat = write(fp, data_->data(), data_->size());
  if (stat < 0) {
    vci::interceptor::logger()->error("Error during simulated file write.");
  }
  return stream_pos;
}

void SimulatedBufferEntry::Unlock() {
  delete this;  // pipeline is done; safe because pool's data_list_ is untouched
}