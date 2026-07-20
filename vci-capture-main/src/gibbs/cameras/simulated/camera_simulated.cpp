#include "camera_simulated.h"
#include "buffer.h"
#include "buffer_simulated.h"

#include <interceptor/logging.h>
#include <chrono>
#include <random>
#include <stdexcept>
#include <thread>

SimulatedCamera::SimulatedCamera(int id, std::string serialnumber, int width, int height, ImageType type,
                                 PixelLayout pixel_layout)
    : width_(width), height_(height), bit_depth_(12), pixel_layout_(pixel_layout) {
  info_.camera_type = type;
  info_.capture_card_index = id;
  info_.serialnumber = serialnumber;
  info_.camera_id = "SIM_" + serialnumber;
  info_.device_model_name = "Simulated";
  info_.manufacturer = "Simulated";

  InitializeBuffer();
}

// ------ state -------

void SimulatedCamera::OnStop() {
  std::unique_lock<std::mutex> lock(capture_mutex_);
  images_in_buffer_ = 0;
}

void SimulatedCamera::OnStart() {
  std::unique_lock<std::mutex> lock(capture_mutex_);
  images_in_buffer_ = 0;
}

// ---- settings -----

// gain and exposure - currently only stored and not used for buffer. ----
void SimulatedCamera::SetDefaultParameters() {
  trigger_source_ = TriggerSource::Software;
}

void SimulatedCamera::SetExposure(int exposure) {
  exposure_ = exposure;
}
void SimulatedCamera::SetGain(int gain) {
  gain_ = gain;
}
int SimulatedCamera::GetExposure() const {
  return exposure_;
}
int SimulatedCamera::GetGain() const {
  return gain_;
}

// simulation specific function.
void SimulatedCamera::InitializeBuffer() {
  if (is_running_) {
    vci::interceptor::logger()->error("Buffer cannot be initiliazed while camera is running");
    throw std::runtime_error("Buffer cannot be initiliazed while camera is running");
  }
  vci::interceptor::logger()->debug(
      "Initializing Simualted Buffer with width {}, height {}, bit_depth {}, pixel_layout {}", width_, height_,
      bit_depth_, PixelLayoutToString(pixel_layout_));
  buffer_entry_ = std::make_unique<SimulatedBuffer>(&info_, width_, height_, bit_depth_, pixel_layout_);
}

// -- triggering ----
// The Simulated camera can pretend to be hardware triggered with a set frame rate.
void SimulatedCamera::OnSetTriggerSource(TriggerSource source) {
  if (source == TriggerSource::Hardware) {
    throw std::runtime_error("Simulated Cmaera does not support hardware triggering");
  }
}

void SimulatedCamera::PerformSoftwareTrigger() {
  std::unique_lock<std::mutex> lock(capture_mutex_);
  images_in_buffer_++;
  cv_.notify_one();
  vci::interceptor::logger()->debug("void SimulatedCamera::PerformSoftwareTrigger {} {}", info_.camera_id,
                                    images_in_buffer_.load());
}

// --- Capture -----

BufferEntry* SimulatedCamera::CaptureNext(int timeout_ms) {
  std::unique_lock<std::mutex> lock(capture_mutex_);
  vci::interceptor::logger()->debug("SimulatedCamera::CaptureNext {} in buffer: {}", info_.camera_id,
                                    images_in_buffer_.load());
  // Wait until images_in_buffer_ > 0 OR timeout reached
  bool success = cv_.wait_for(lock, std::chrono::milliseconds(timeout_ms),
                              [this] { return images_in_buffer_ > 0 || !is_running_; });
  if (!success || !is_running_) {
    throw BufferTimeout();
  }
  images_in_buffer_--;
  return buffer_entry_->CaputreNext();
}

// -- other stuff

int SimulatedCamera::GetParameterInt(const char* parameter) {
  std::string_view p(parameter);

  if (p == "width") {
    return width_;
  }
  if (p == "height") {
    return height_;
  }
  if (p == "pixel_layout") {
    return static_cast<int>(pixel_layout_);
  }
  if (p == "bit_depth") {
    return bit_depth_;
  }
  vci::interceptor::logger()->warn("Unknown parameter name for Simulated Camera: {}", parameter);
  return 0;
}
void SimulatedCamera::SetParameterInt(const char* parameter, int value) {
  std::string_view p(parameter);
  if (p == "width") {
    width_ = value;
    SimulatedCamera::InitializeBuffer();
    return;
  }
  if (p == "height") {
    height_ = value;
    SimulatedCamera::InitializeBuffer();
    return;
  }
  if (p == "pixel_layout") {
    pixel_layout_ = static_cast<PixelLayout>(value);
    SimulatedCamera::InitializeBuffer();
    return;
  }
  if (p == "bit_depth") {
    bit_depth_ = value;
    SimulatedCamera::InitializeBuffer();
    return;
  }
  vci::interceptor::logger()->warn("Unknown parameter name for Simulated Camera: {}", parameter);
}
float SimulatedCamera::GetParameterFloat(const char* parameter) {
  return 0;
}
void SimulatedCamera::SetParameterFloat(const char* parameter, float value) {}
std::string SimulatedCamera::GetParameterString(const char* parameter) {
  return "simulated";
}
std::string SimulatedCamera::TryGetParameter(const char* parameter, const char* data_type) {
  return "simualted";
}
void SimulatedCamera::TrySetParameter(const char* parameter, const char* data_type, const char* value) {}
void SimulatedCamera::SetBitDepth(int sensor_bit_depth, int out_bit_depth, bool packing) {}
int SimulatedCamera::GetCounter(int counter_selector) {
  return 0;
}

int SimulatedCamera::NumQueued() {
  return 0;
}