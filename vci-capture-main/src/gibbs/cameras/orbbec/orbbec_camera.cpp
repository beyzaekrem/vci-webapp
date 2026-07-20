#include "orbbec_camera.h"
#include <interceptor/logging.h>
#include <cstdint>
#include <libobsensor/ObSensor.hpp>
#include <sstream>
#include <stdexcept>
#include "orbbec_buffer.h"
#include "property_lookup.hpp"

using namespace ob;

OrbbecCamera::OrbbecCamera(int id)
    : id_(id), ctx_(std::make_shared<Context>()) {  // save id and create orbbec context shared pointer so device list
                                                    // and pipeline etc can access it
  auto list = ctx_->queryDeviceList();              // get a list of the devices
  if (!list || id < 0 || id >= static_cast<int>(list->deviceCount()))
    throw std::runtime_error("invalid camera index");  // if there are index errors catch that
  dev_ = list->getDevice(id);

  auto info = dev_ ? dev_->getDeviceInfo() : nullptr;
  info_.serialnumber = info->serialNumber();
  info_.camera_id = info_.serialnumber;
  info_.camera_type = ImageType::Depth;
  info_.capture_card_index = id;
  info_.device_model_name = info->name();
  info_.manufacturer = "Basler";
}

void OrbbecCamera::SetDefaultParameters() {
  SetSecondary();
  if (dev_->isPropertySupported(OB_PROP_COLOR_AUTO_WHITE_BALANCE_BOOL, OB_PERMISSION_READ_WRITE)) {
    bool value = dev_->getBoolProperty(OB_PROP_COLOR_AUTO_WHITE_BALANCE_BOOL);
    dev_->setBoolProperty(OB_PROP_COLOR_AUTO_WHITE_BALANCE_BOOL, false);
    std::cout << "orbbec OB_PROP_COLOR_AUTO_WHITE_BALANCE_BOOL: " << value << std::endl;
  }
}

void OrbbecCamera::OnStart() {
  pipe_ = std::make_unique<ob::Pipeline>(dev_);
  auto cfg = std::make_shared<ob::Config>();
  std::shared_ptr<ob::StreamProfile> prof;

  pipe_->enableFrameSync();

  int fps = 15;  // TODO make fps available as parameter add argument parser to python side

  std::shared_ptr<ob::StreamProfile> color_prof;
  auto color_list = pipe_->getStreamProfileList(OB_SENSOR_COLOR);
  color_prof = color_list->getVideoStreamProfile(1920, 1080, OB_FORMAT_RGB, fps);

  std::shared_ptr<ob::StreamProfile> target_prof;
  auto sensor_type = (mode_ == ImageType::Depth) ? OB_SENSOR_DEPTH : OB_SENSOR_IR;
  auto target_list = pipe_->getStreamProfileList(sensor_type);
  target_prof = target_list->getVideoStreamProfile(640, 576, OB_FORMAT_Y16, fps);

  cfg->enableStream(color_prof);
  DebugProfile(color_prof);

  // Enable Depth or Mono stream
  if (mode_ == ImageType::Depth) {
    cfg->enableStream(target_prof);
    DebugProfile(target_prof);

    // Enable Hardware Alignment
    cfg->setAlignMode(ALIGN_D2C_HW_MODE);
    cfg->setFrameAggregateOutputMode(OB_FRAME_AGGREGATE_OUTPUT_ALL_TYPE_FRAME_REQUIRE);
  } else if (mode_ == ImageType::Mono) {
    throw std::runtime_error("OrbbecCamera Mono mode not yet implemented");
    // it should be identical to depth. But it didnt get aligned. So idk.
  }
  SetSecondary();
  pipe_->start(cfg);
}

void OrbbecCamera::OnOpen() {  // open the camera by creating the context and getting the device again, if it is already
                               // open, do nothing
  if (dev_) return;
  if (!ctx_) ctx_ = std::make_shared<Context>();
  auto list = ctx_->queryDeviceList();
  if (!list || id_ < 0 || id_ >= static_cast<int>(list->deviceCount()))
    throw std::runtime_error("invalid camera index");
  dev_ = list->getDevice(id_);
}

void OrbbecCamera::OnClose() {  // stop streaming and drop device and context
  Stop();
  dev_.reset();
  ctx_.reset();
}

void OrbbecCamera::SetMode(ImageType m) {
  if (mode_ == m) return;
  const bool was_running = IsRunning();
  if (was_running) Stop();
  mode_ = m;
  if (was_running) Start();
}

void OrbbecCamera::SetExposure(int exposure) {
  if (dev_) {
    try {
      if (dev_->isPropertySupported(OB_PROP_COLOR_AUTO_EXPOSURE_BOOL, OB_PERMISSION_READ_WRITE)) {
        bool value = dev_->getBoolProperty(OB_PROP_COLOR_AUTO_EXPOSURE_BOOL);
        dev_->setBoolProperty(OB_PROP_COLOR_AUTO_EXPOSURE_BOOL, false);
        std::cout << "orbbec OB_PROP_COLOR_AUTO_EXPOSURE_BOOL: " << value << std::endl;
      }  // OB_PROP_COLOR_AUTO_EXPOSURE_PRIORITY_INT

      std::cout << "orbbec OB_PROP_COLOR_AUTO_EXPOSURE_PRIORITY_INT "
                << dev_->getIntProperty(OB_PROP_COLOR_AUTO_EXPOSURE_PRIORITY_INT) << std::endl;

      if (dev_->isPropertySupported(OB_PROP_COLOR_EXPOSURE_INT, OB_PERMISSION_READ)) {
        // get the value range
        OBIntPropertyRange valueRange = dev_->getIntPropertyRange(OB_PROP_COLOR_EXPOSURE_INT);
        std::cout << "Color current exposure max:" << valueRange.max << ", min:" << valueRange.min << std::endl;

        int value = dev_->getIntProperty(OB_PROP_COLOR_EXPOSURE_INT);
        std::cout << "Color current exposure:" << value << std::endl;
        if (dev_->isPropertySupported(OB_PROP_COLOR_EXPOSURE_INT, OB_PERMISSION_WRITE)) {
          std::cout << "Set color exposure:" << exposure << std::endl;
          dev_->setIntProperty(OB_PROP_COLOR_EXPOSURE_INT, exposure);

          int value = dev_->getIntProperty(OB_PROP_COLOR_EXPOSURE_INT);
          std::cout << "Exposure set to exposure:" << value << std::endl;
        } else {
          std::cerr << "Color exposure set property is not supported." << std::endl;
        }
      } else {
        std::cerr << "Color exposure get property is not supported." << std::endl;
      }

      if (dev_->isPropertySupported(OB_PROP_DEPTH_AUTO_EXPOSURE_BOOL, OB_PERMISSION_READ_WRITE)) {
        dev_->setBoolProperty(OB_PROP_DEPTH_AUTO_EXPOSURE_BOOL, false);
        std::cout << "orbbec OB_PROP_DEPTH_AUTO_EXPOSURE_BOOL: "
                  << dev_->getBoolProperty(OB_PROP_DEPTH_AUTO_EXPOSURE_BOOL) << std::endl;
      } else {
        std::cerr << "Depth depth auto exposure property is not supported." << std::endl;
      }

      if (dev_->isPropertySupported(OB_PROP_DEPTH_EXPOSURE_INT, OB_PERMISSION_READ_WRITE)) {
        dev_->setIntProperty(OB_PROP_DEPTH_EXPOSURE_INT, exposure);
        std::cout << "orbbec OB_PROP_DEPTH_EXPOSURE_INT: " << dev_->getIntProperty(OB_PROP_DEPTH_EXPOSURE_INT)
                  << std::endl;
      } else {
        std::cerr << "Depth exposure set property is not supported." << std::endl;
      }
    } catch (ob::Error& e) {
      std::cerr << "function:" << e.getFunction() << "\nargs:" << e.getArgs() << "\nmessage:" << e.what()
                << "\ntype:" << e.getExceptionType() << std::endl;
    }
  }
}

void OrbbecCamera::SetGain(int gain) {
  dev_->setIntProperty(OB_PROP_COLOR_GAIN_INT, gain);
}

int OrbbecCamera::GetExposure() const {
  return dev_->getIntProperty(OB_PROP_COLOR_EXPOSURE_INT);
}
int OrbbecCamera::GetGain() const {
  return dev_->getIntProperty(OB_PROP_COLOR_GAIN_INT);
}

void OrbbecCamera::DebugProfile(std::shared_ptr<ob::StreamProfile> prof) {
  if (auto v = prof->as<ob::VideoStreamProfile>()) {
    // quick visibility into what we got
    std::ostringstream oss;
    const char* mode_str = "Depth";
    if (mode_ == ImageType::Mono) mode_str = "Mono";
    if (mode_ == ImageType::Color) mode_str = "Color";
    oss << "[orbbec] Start mode=" << mode_str << " using format=" << static_cast<int>(v->format()) << " " << v->width()
        << "x" << v->height() << "@" << v->fps();
    fprintf(stderr, "%s\n", oss.str().c_str());
  }
}

void OrbbecCamera::OnStop() {  // stop streams and reset the pipeline
  if (!IsRunning()) return;
  pipe_->stop();
  pipe_.reset();
  is_running_ = false;
}

BufferEntry* OrbbecCamera::CaptureNext(
    int timeout_ms) {  // first check if it has started if not throw and error, then wait for frames, which can take a
                       // little so there is the param how long we wait,
  if (!IsRunning()) {
    return nullptr;
  }
  std::shared_ptr<ob::FrameSet> fs = pipe_->waitForFrames(timeout_ms);
  if (!fs) {
    vci::interceptor::logger()->info("[orbbec] wait for Frames timed out.");
    throw BufferTimeout();  // <- capture_next relies on Timeout being thrown when no image is triggered.
  }
  // auto align = std::make_shared<ob::Align>(OB_STREAM_COLOR);
  // std::shared_ptr<ob::FrameSet> aligned_fs = align->process(fs);

  std::shared_ptr<ob::Frame> f;
  if (mode_ == ImageType::Depth) {
    auto depth = fs->depthFrame();  // get the depth frame from the frameset
    if (!depth) {
      std::cerr << "[orbbec] Warning: depth frame is null\n";
      return nullptr;
    }
    f = depth;
  } else if (mode_ == ImageType::Mono) {  // Mode::MONO
    auto ir = fs->irFrame();              // get the IR (mono) frame from the frameset
    if (!ir) {
      std::cerr << "[orbbec] Warning: IR frame is null\n";
      return nullptr;
    }
    f = ir;
  } else {  // Mode::COLOR
    auto color = fs->colorFrame();
    if (!color) {
      std::cerr << "[orbbec] Warning: color frame is null\n";
      return nullptr;
    }
    f = color;
  }

  return new OrbbecBuffer(nullptr, mode_,
                          f);  // this sdk frame we got above is now wrapped into our orbbec buffer class which is my
                               // best try of implementing the buffer. it is very similar to the simulated buffer file
}

int OrbbecCamera::GetParameterInt(const char* parameter) {
  auto it = kPropNameToId.find(parameter);
  if (it == kPropNameToId.end()) throw std::invalid_argument(std::string("unknown OB property: ") + parameter);

  try {
    return dev_->getIntProperty(it->second);
  } catch (const Error& e1) {
    try {
      return dev_->getBoolProperty(it->second) ? 1 : 0;
    } catch (const Error& e2) {
      std::ostringstream oss;
      oss << "getIntProperty(\"" << parameter << "\") failed: " << e1.getMessage()
          << " ; getBoolProperty fallback failed: " << e2.getMessage() << " (type "
          << static_cast<int>(e2.getExceptionType()) << ')';
      throw std::runtime_error(oss.str());
    }
  }
}

float OrbbecCamera::GetParameterFloat(const char* parameter) {
  auto it = kPropNameToId.find(parameter);
  if (it == kPropNameToId.end()) throw std::invalid_argument(std::string("unknown OB property: ") + parameter);

  try {
    return dev_->getFloatProperty(it->second);
  } catch (const Error& e) {
    std::ostringstream oss;
    oss << "getFloatProperty(\"" << parameter << "\") failed: " << e.getMessage() << " (type "
        << static_cast<int>(e.getExceptionType()) << ')';
    throw std::runtime_error(oss.str());
  }
}

void OrbbecCamera::SetParameterInt(const char* parameter, int value) {
  if (std::strcmp(parameter, "trigger_source") == 0) {
    if (value == 1) {  // use hardware trigger
      return;
    } else {
      throw std::invalid_argument(std::string("Orbbec cameras dont support software trigger"));
    }
  }
  if (std::strcmp(parameter, "trigger_software") == 0) {
    return;
  }
  if (std::strcmp(parameter, "depth_mode") == 0) {
    // std::cout << "SetParameter Int passes through to Set Mode" << std::endl;
    SetMode(static_cast<ImageType>(value));
    return;
  }
  //   std::cout << "Try to find OB Paramter..." << std::endl;
  auto it = kPropNameToId.find(parameter);
  if (it == kPropNameToId.end()) {
    throw std::invalid_argument(std::string("unknown OB property: ") + parameter);
  }
  try {
    dev_->setIntProperty(it->second, value);
  } catch (const Error& e1) {
    try {
      dev_->setBoolProperty(it->second, value != 0);
    } catch (const Error& e2) {
      std::ostringstream oss;
      oss << "setIntProperty(\"" << parameter << "\", " << value << ") failed: " << e1.getMessage() << " (type "
          << static_cast<int>(e1.getExceptionType()) << "); setBoolProperty fallback failed: " << e2.getMessage()
          << " (type " << static_cast<int>(e2.getExceptionType()) << ')';
      std::cout << oss.str();
      throw std::runtime_error(oss.str());
    }
  }
}

bool OrbbecCamera::SupportsProperty(const char* property_name) const {
  if (!dev_) throw std::runtime_error("device not open");
  auto it = kPropNameToId.find(property_name);
  if (it == kPropNameToId.end()) throw std::invalid_argument(std::string("unknown OB property: ") + property_name);

  try {
    if (dev_->isPropertySupported(it->second, OB_PERMISSION_READ_WRITE)) return true;
    if (dev_->isPropertySupported(it->second, OB_PERMISSION_WRITE)) return true;
    if (dev_->isPropertySupported(it->second, OB_PERMISSION_READ)) return true;
    return false;
  } catch (const Error& e) {
    std::ostringstream oss;
    oss << "isPropertySupported(\"" << property_name << "\") failed: " << e.getMessage() << " (type "
        << static_cast<int>(e.getExceptionType()) << ')';
    throw std::runtime_error(oss.str());
  }
}

std::vector<std::string> OrbbecCamera::GetSupportedProperties() const {
  if (!dev_) throw std::runtime_error("device not open");
  std::vector<std::string> supported;
  supported.reserve(kPropNameToId.size());

  for (const auto& [name, property_id] : kPropNameToId) {
    try {
      if (dev_->isPropertySupported(property_id, OB_PERMISSION_READ_WRITE) ||
          dev_->isPropertySupported(property_id, OB_PERMISSION_WRITE) ||
          dev_->isPropertySupported(property_id, OB_PERMISSION_READ)) {
        supported.emplace_back(name);
      }
    } catch (...) {
    }
  }

  return supported;
}

void OrbbecCamera::PerformSoftwareTrigger() {
  if (!dev_) return;
  try {
    dev_->setBoolProperty(OB_PROP_CAPTURE_IMAGE_SIGNAL_BOOL, true);
  } catch (...) {
  }
}
void OrbbecCamera::SetPrimary() {
  if (!dev_) throw std::runtime_error("device not open");
  OBMultiDeviceSyncConfig cfg{};
  cfg.syncMode = OB_MULTI_DEVICE_SYNC_MODE_PRIMARY;
  cfg.triggerOutEnable = true;
  cfg.framesPerTrigger = 1;
  dev_->setMultiDeviceSyncConfig(cfg);
}

void OrbbecCamera::SetSecondary() {
  if (!dev_) throw std::runtime_error("device not open");
  OBMultiDeviceSyncConfig cfg{};
  cfg.syncMode = OB_MULTI_DEVICE_SYNC_MODE_SECONDARY;
  cfg.framesPerTrigger = 1;
  std::cout << "Orbbec camers set to SYNC_MODE_SECONDARY" << std::endl;
  dev_->setMultiDeviceSyncConfig(cfg);
}

void OrbbecCamera::OnSetTriggerSource(
    TriggerSource trigger_source) {  // This will work if we connect ethernet cables between the cameras probably
                                     // havent tested but the function theoretically exist...
  if (!dev_) throw std::runtime_error("device not open");

  switch (trigger_source) {
    case TriggerSource::Software:
      //   OBMultiDeviceSyncConfig cfg{};
      //   cfg.syncMode = OB_MULTI_DEVICE_SYNC_MODE_SOFTWARE_TRIGGERING;
      //   cfg.framesPerTrigger = 1;
      //   dev_->setMultiDeviceSyncConfig(cfg);
      break;

    default:
      // if (!dev_) throw std::runtime_error("device not open");

      // // Mode 1 is usually Hardware Trigger for most Orbbec models
      // // Mode 0 is Free-run, Mode 2 is Software Trigger
      // try {
      //   // Stop the pipeline if it's running before changing trigger modes
      //   if (IsRunning()) pipe_->stop();

      //   // 1. Set the trigger mode property directly
      //   dev_->setIntProperty(OB_PROP_DEVICE_TRIGGER_MODE_INT, 1);

      //   // 2. Set the delay to 0 (or match your Ximea latency)
      //   dev_->setIntProperty(OB_PROP_TRIGGER2IMAGE_DELAY_US_INT, 0);

      //   std::cout << "Trigger mode set via Property API" << std::endl;

      //   if (IsRunning()) pipe_->start(cfg_);  // Re-start with new config
      // } catch (const ob::Error& e) {
      //   throw std::runtime_error("Failed to set HW trigger: " + std::string(e.getMessage()));
      // }
      break;
  }
}

int OrbbecCamera::GetCounter(int counter_selector) {
  return 0;
}
