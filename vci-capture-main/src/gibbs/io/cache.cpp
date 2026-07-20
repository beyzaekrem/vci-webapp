#include "io/cache.h"

#include <fstream>
#include <iostream>
#include <nlohmann/json.hpp>
#include "processing/packing.h"
#include "processing/util.h"

#include <interceptor/logging.h>
#include <tuple>

using json = nlohmann::json;

// Deserialization function for EntryInfo
void from_json(const nlohmann::json& j, EntryInfo& info) {
  j.at("height").get_to(info.height);
  j.at("width").get_to(info.width);
  j.at("bit_depth").get_to(info.bit_depth);
  j.at("channels").get_to(info.channels);
  j.at("packed").get_to(info.packed);
  j.at("num_bytes").get_to(info.num_bytes);

  std::string image_type_str = j.at("image_type").get<std::string>();
  info.image_type = StringToImageType(image_type_str);
  if (j.contains("pixel_layout")) {
    std::string pixel_layout_str = j.at("pixel_layout").get<std::string>();
    info.pixel_layout = StringToPixelLayout(pixel_layout_str);
  }

  info.optional_data = std::monostate{};
  if (j.contains("depth_scale")) {
    float scale_value;
    j.at("depth_scale").get_to(scale_value);
    info.optional_data = scale_value;
  }
}

EntryInfo GetDefaultEntryInfo() {
  // is an entry info for a ximea camera (both color or mono)
  EntryInfo info;
  // info.camera_id = "undefined"; - as defaulted in EntryInfo definition
  info.height = 4608;
  info.width = 5328;
  info.bit_depth = 12;
  info.channels = 1;
  info.packed = true;
  info.pixel_layout = PixelLayout::BGGR;
  info.image_type = ImageType::Color;
  info.timestamp_us = 0;
  info.frame_number = 0;
  info.num_bytes = 36859904;  // 12 bit full resolution
  return info;
}

Cache::Cache(const std::string& cache_path) : cache_path_(cache_path) {}
std::optional<int> Cache::GetFps() {
  return fps_;
}

CacheReader::CacheReader(const std::string& cache_path) : Cache(cache_path) {
  std::ifstream if_stream(cache_path);
  if (!if_stream.is_open()) {
    throw std::runtime_error("Could not open cache file: " + cache_path);
  }
  json cache_data = json::parse(if_stream);

  if (cache_data.contains("dump_files")) {
    for (const auto& dump_file_json : cache_data["dump_files"]) {
      this->dump_files_.push_back(dump_file_json);
    }
  }
  if (cache_data.contains("dump_mapping")) {
    for (const auto& dump_mapping_i_json : cache_data["dump_mapping"]) {
      std::vector<Location> dump_mapping_i(dump_mapping_i_json.size());
      for (int j = 0; j < dump_mapping_i_json.size(); ++j) {
        dump_mapping_i[j].dump_file_idx = dump_mapping_i_json[j][0];
        dump_mapping_i[j].byte_offset = dump_mapping_i_json[j][1];
      }
      this->dump_mapping_.push_back(dump_mapping_i);
      framecount_.push_back(dump_mapping_i_json.size());
      std::cout << "Found " << framecount_ << " frames in cache." << std::endl;
    }
  }

  if (cache_data.contains("fps")) {
    const auto& fps_node = cache_data["fps"];
    if (!fps_node.is_null()) {
      fps_ = fps_node.get<int>();
    } else {
      fps_ = std::nullopt;  // Explicitly clear it if it was null
    }
  }

  if (cache_data.contains("camera_ids")) {
    camera_ids_ = cache_data["camera_ids"].get<std::vector<std::string>>();
  }

  if (cache_data.contains("format_info")) {
    this->format_info_ = cache_data["format_info"].get<std::vector<EntryInfo>>();
    this->num_cameras_ = this->format_info_.size();
  } else {
    for (int i = 0; i < this->dump_mapping_.size(); ++i) {
      this->format_info_.push_back(GetDefaultEntryInfo());
    }
  }
}

int CacheReader::FrameCount() {
  if (framecount_.empty()) {
    return 0;  // There are not images captured. Avoid segfaulting.
  }
  return framecount_[0];
}

std::optional<std::vector<std::string>> CacheReader::CameraIds() {
  return camera_ids_;
}

std::string CacheReader::CameraId(int camera_idx) {
  std::string camera_id = "unknown";
  if (camera_ids_.has_value() && camera_idx < camera_ids_->size()) {
    camera_id = camera_ids_->at(camera_idx);  // .at() provides bounds checking
  }
  return camera_id;
}

GibbsImage CacheReader::LoadFrame(int camera_idx, int frame_idx) {
  if (camera_idx < 0 || camera_idx >= dump_mapping_.size()) {
    vci::interceptor::logger()->error("Camera index {} out of bounds. Cache has {} cameras.", camera_idx,
                                      dump_mapping_.size());
    throw std::out_of_range("Invalid camera index (cache might be empty).");
  }

  if (frame_idx == -1) {
    vci::interceptor::logger()->error("No image for frame_index -1");
    throw std::invalid_argument("Frame index cannot be -1 (indicates no image).");
  }
  if (frame_idx >= framecount_[camera_idx]) {
    vci::interceptor::logger()->error("CacheReader frame index {} out of bounds. Camera {} has {} frames in dump.",
                                      frame_idx, camera_idx, framecount_[camera_idx]);
    std::ostringstream oss;
    oss << "CacheReader frame index " << frame_idx << " out of bounds. Camera " << camera_idx << " has "
        << framecount_[camera_idx] << " frames in dump.";

    // Throw std::out_of_range with the detailed string
    throw std::out_of_range(oss.str());
  }
  const Location& location = this->dump_mapping_[camera_idx][frame_idx];
  EntryInfo entry_info = format_info_[camera_idx];
  entry_info.frame_number = frame_idx;

  int num_bytes = entry_info.num_bytes;
  std::vector<char> buffer(num_bytes);

  std::ifstream if_stream(this->dump_files_[location.dump_file_idx], std::ios::binary);
  if (!if_stream) {
    vci::interceptor::logger()->error("Could not open file.");
  }
  if_stream.seekg(location.byte_offset, std::ios::beg);
  if (!if_stream) {
    vci::interceptor::logger()->error("Seek failed.");
  }
  if_stream.read(buffer.data(), num_bytes);
  if (!if_stream) {
    vci::interceptor::logger()->error("Read failed.");
  }
  if_stream.close();

  torch::Tensor image = vci::gibbs::BufferToDeviceAsync(buffer.data(), num_bytes, torch::Device(torch::kCUDA, 0));
  GibbsImage gibbsImage = vci::gibbs::UnpackBuffer(image, &entry_info);
  gibbsImage.camera_id = CameraId(camera_idx);
  return gibbsImage;
}

CacheWriter::CacheWriter(const std::string cache_path, const std::vector<std::string> dump_base_paths,
                         const std::vector<std::string> camera_ids)
    : Cache(cache_path),
      dump_info_(dump_base_paths.size()),
      dump_base_paths_(dump_base_paths),
      camera_ids_(camera_ids) {
  format_info_.resize(camera_ids_.size());
  num_cameras_ = camera_ids_.size();
}

CacheWriter::~CacheWriter() {
  for (int i = 0; i < this->dump_info_.size(); ++i) {
    if (this->dump_info_[i].fp >= 0) {
      close(this->dump_info_[i].fp);
      this->dump_info_[i].fp = -1;
    }
  }
}

void CacheWriter::SetFps(std::optional<int> fps) {
  fps_ = fps;
}

void CacheWriter::WriteFrame(int camera_idx, int frame_idx, int dump_idx, BufferEntry* buffer) {
  int dump_file_idx;
  size_t byte_offset;
  // Write to dump
  {
    // Grab corresponding dump info
    DumpInfo& info = this->dump_info_[dump_idx];
    std::lock_guard<std::mutex> dump_guard(info.mutex_);
    // (Re-)open file pointer
    if (info.counter % kFramesPerDump == 0) {
      if (info.fp >= 0) {
        close(info.fp);
        info.fp = -1;
      }
      std::string fname = this->dump_base_paths_[dump_idx] + std::string(".") +
                          std::to_string(info.previous_dump_files) + std::string(".dump");
      // Flags:
      // O_CREAT | O_EXCL: We need it to fail if the file exists, since overwriting is slow
      // O_WRONLY: Only write
      // O_DIRECT: Direct writing without memory copy
      // S_IRUSR | S_IWUSR: User has read and write permission
      info.fp = open(fname.c_str(), O_CREAT | O_EXCL | O_WRONLY | O_DIRECT, S_IRUSR | S_IWUSR);
      if (info.fp < 0) {
        vci::interceptor::logger()->error("Could not open file '{}'", fname.c_str());
      }
      info.previous_dump_files += 1;
      std::lock_guard<std::mutex> dump_files_guard(this->dump_files_mutex_);
      info.dump_file_idx = this->dump_files_.size();
      this->dump_files_.push_back(fname);
    }
    // Write buffer
    dump_file_idx = info.dump_file_idx;
    byte_offset = buffer->WriteTo(info.fp);
    info.counter += 1;
  }
  // Add to mapping
  {
    std::lock_guard<std::mutex> mapping_guard(this->dump_mapping_mutex_);
    if (this->dump_mapping_.size() < camera_idx + 1) {
      this->dump_mapping_.resize(camera_idx + 1);
    }
    if (this->dump_mapping_[camera_idx].size() < frame_idx + 1) {
      this->dump_mapping_[camera_idx].resize(frame_idx + 1);
    }
    this->dump_mapping_[camera_idx][frame_idx].dump_file_idx = dump_file_idx;
    this->dump_mapping_[camera_idx][frame_idx].byte_offset = byte_offset;
  }
  {
    if (frame_idx == 0) {
      const EntryInfo* b_info = buffer->Info();
      format_info_[camera_idx] = *b_info;
    }
  }
}

void CacheWriter::WriteCache() {
  std::ofstream file_stream;
  file_stream.open(this->cache_path_, std::ios_base::out | std::ios_base::trunc);
  file_stream << "{" << std::endl;

  // camera ids
  file_stream << "  \"camera_ids\": [" << std::endl;
  for (int i = 0; i < this->camera_ids_.size(); ++i) {
    file_stream << "    \"" << this->camera_ids_[i] << "\"";
    if (i < this->camera_ids_.size() - 1) {
      file_stream << ",";
    }
    file_stream << std::endl;
  }
  file_stream << "  ]," << std::endl;

  if (fps_.has_value()) {  // optional<int> fps
    const int fps_value = *fps_;
    file_stream << " \"fps\": " << fps_value << "," << std::endl;
  }

  // camera_stream_info_
  file_stream << "  \"format_info\": [" << std::endl;
  for (size_t i = 0; i < this->format_info_.size(); i++) {
    const EntryInfo& info = this->format_info_[i];
    file_stream << "    {" << std::endl;
    file_stream << "      \"height\": " << info.height << "," << std::endl;
    file_stream << "      \"width\": " << info.width << "," << std::endl;
    file_stream << "      \"pixel_layout\": \"" << (PixelLayoutToString(info.pixel_layout)) << "\"," << std::endl;
    file_stream << "      \"bit_depth\": " << info.bit_depth << "," << std::endl;
    file_stream << "      \"channels\": " << info.channels << "," << std::endl;
    file_stream << "      \"packed\": " << (info.packed ? "true" : "false") << "," << std::endl;
    file_stream << "      \"image_type\": \"" << (ImageTypeToString(info.image_type)) << "\"," << std::endl;
    if (info.image_type == ImageType::Depth) {
      const float* depth_scale = std::get_if<float>(&info.optional_data);
      file_stream << "      \"depth_scale\": " << *depth_scale << "," << std::endl;
    }
    file_stream << "      \"num_bytes\": " << (info.num_bytes) << std::endl;
    file_stream << "    }";
    if (i < this->format_info_.size() - 1) {
      file_stream << ",";
    }
    file_stream << std::endl;
  }
  file_stream << "  ]," << std::endl;

  // Dump Files
  file_stream << "  \"dump_files\": [" << std::endl;
  for (int i = 0; i < this->dump_files_.size(); ++i) {
    file_stream << "    \"" << this->dump_files_[i] << "\"";
    if (i < this->dump_files_.size() - 1) {
      file_stream << ",";
    }
    file_stream << std::endl;
  }
  file_stream << "  ]," << std::endl;

  // Meta
  // -- pass --

  // Mapping
  file_stream << "  \"dump_mapping\": [" << std::endl;
  for (int i = 0; i < this->dump_mapping_.size(); ++i) {
    file_stream << "    [";
    for (int j = 0; j < this->dump_mapping_[i].size(); ++j) {
      file_stream << "[" << this->dump_mapping_[i][j].dump_file_idx << "," << this->dump_mapping_[i][j].byte_offset
                  << "]";
      if (j < this->dump_mapping_[i].size() - 1) {
        file_stream << ",";
      }
    }
    file_stream << "]";
    if (i < this->dump_mapping_.size() - 1) {
      file_stream << ",";
    }
    file_stream << std::endl;
  }
  file_stream << "  ]" << std::endl;
  // Eof
  file_stream << "}" << std::endl;
  file_stream.close();
}

int CacheWriter::GetNumDumps() const {
  return this->dump_base_paths_.size();
}
