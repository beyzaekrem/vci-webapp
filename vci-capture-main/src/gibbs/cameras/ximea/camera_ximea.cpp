#include "camera_ximea.h"

#include <cmath>
#include <iostream>

#include <interceptor/logging.h>

// include pybind headers for gil_scoped_release
#include <pybind11/functional.h>
#include <pybind11/stl.h>
#include "xi_util.h"
namespace py = pybind11;

bool DeviceNameIsColor(const std::string device_model_name) {
  std::vector<const char*> color_cameras{"MX245CG-SY-X4G3-FF"};
  std::vector<const char*> mono_cameras{"MX245MG-SY-X4G3-FF"};
  for (int i = 0; i < color_cameras.size(); ++i) {
    if (device_model_name == color_cameras[i]) {
      return true;
    }
  }
  for (int i = 0; i < mono_cameras.size(); ++i) {
    if (device_model_name == mono_cameras[i]) {
      return false;
    }
  }
  vci::interceptor::logger()->error("Unknown device name {}", device_model_name.c_str());
  return false;
}

XimeaCamera::XimeaCamera(int id, int buffer_length)
    : has_lut_(false), xi_handle_(nullptr), buffer_(&info_, buffer_length) {
  info_.capture_card_index = id;
  info_.manufacturer = "Ximea";

  vci::interceptor::logger()->debug("Initializing Ximea camera {} ...", id);

  XI_RETURN stat;
  char value[256];

  // ---  get serial number ---
  stat = xiGetDeviceInfoString(info_.capture_card_index, XI_PRM_DEVICE_SN, value, 256);
  if (stat != XI_OK) {
    vci::interceptor::logger()->error(
        "Error retrieving camera info: Getting XI_PRM_DEVICE_SN for camera {} failed with code {}.",
        info_.capture_card_index, stat);
    throw CameraInvalidException("Ximea Camera serial number could not be retrieved");
  }
  info_.serialnumber = std::string(value);
  if (info_.serialnumber.empty()) {
    throw CameraInvalidException("Ximea Camera returned an empty serial number");
  }
  vci::interceptor::logger()->debug("Ximea camera {} - serial number: {}", id, info_.serialnumber);
  if (info_.serialnumber.front() == 'F') {
    throw CameraInvalidException("Ximea Camera is not properly connected (SN: " + info_.serialnumber +
                                 "). Restarting the computer may help");
  }

  // --- get device model name (contains info if camera is color CG or momo MG)----
  stat = xiGetDeviceInfoString(info_.capture_card_index, XI_PRM_DEVICE_NAME, value, 256);
  if (stat != XI_OK) {
    vci::interceptor::logger()->error(
        "Error retrieving camera info: Getting XI_PRM_DEVICE_NAME for camera {} failed with code {}.",
        info_.capture_card_index, stat);
  }
  info_.device_model_name = std::string(value);
  vci::interceptor::logger()->debug("Ximea camera {} - device model name: {}", id, info_.device_model_name);

  info_.camera_type = ImageType::Mono;
  if (DeviceNameIsColor(info_.device_model_name)) {
    info_.camera_type = ImageType::Color;
  }

  info_.camera_id = info_.serialnumber;
  vci::interceptor::logger()->debug("Initialized Ximea camera {} SN: {}", id, info_.camera_id);
}

void XimeaCamera::SetDefaultParameters() {
  SetParameterInt("imgdataformat", 7);  // XI_FRM_TRANSPORT_DATA
  SetBitDepth(12);
  SetParameterInt("gpi_selector", 2);      // XI_PRM_GPI_SELECTOR, XI_GPI_PORT2
  SetParameterInt("gpi_mode", 1);          // XI_PRM_GPI_MODE, XI_GPI_TRIGGER
  SetParameterInt("trigger_source", 1);    // XI_PRM_TRG_SOURCE, XI_TRG_EDGE_RISING
  SetParameterInt("trigger_selector", 0);  // XI_PRM_TRG_SELECTOR, XI_TRG_SEL_FRAME_START
  SetParameterInt("trigger_overlap", 0);   // XI_PRM_TRG_OVERLAP, XI_TRG_OVERLAP_OFF
  // TODO triggering on falling edge instead of rising edge fits better with IR projector timing ???
  // The cameras are ~ 0.2 ms slower

  // Sets transport buffer to 128 MiB.
  SetParameterInt("acq_transport_buffer_size", 134217728);
  // Sets the number of host side buffers to 10 (or higher, e.g., 20)
  SetParameterInt("buffers_queue_size", 10);

  // camera.set_parameter_int("recent_frame", 1)  # XI_PRM_RECENT_FRAME, XI_ON  # noqa: ERA001
  //  camera.set_buffer_length(100)  # noqa: ERA001
  // camera.allocate_buffer()  # noqa: ERA001
}

void XimeaCamera::OnSetTriggerSource(TriggerSource trigger_source) {
  switch (trigger_source) {
    case TriggerSource::Hardware:
      SetParameterInt("trigger_source", 1);  // XI_PRM_TRG_SOURCE, XI_TRG_EDGE_RISING
      break;
    case TriggerSource::Software:
      SetParameterInt("trigger_source", 3);  // XI_PRM_TRG_SOURCE, XI_TRG_SOFTWARE
    default:
      break;
  }
}

void XimeaCamera::PerformSoftwareTrigger() {
  SetParameterInt("trigger_software", 1);
}

void XimeaCamera::SetExposure(int exposure) {
  SetParameterInt("exposure", exposure);
}
void XimeaCamera::SetGain(int gain) {
  SetParameterInt("gain", gain);
}

int XimeaCamera::GetExposure() const {
  return const_cast<XimeaCamera*>(this)->GetParameterInt("exposure");
}
int XimeaCamera::GetGain() const {
  return const_cast<XimeaCamera*>(this)->GetParameterInt("gain");
}

void XimeaCamera::OnOpen() {
  XI_RETURN stat = xiOpenDevice(info_.capture_card_index, &xi_handle_);
  if (stat != XI_OK) {
    xi_handle_ = nullptr;
    vci::interceptor::logger()->error("Opening camera {} failed with code {}.", info_.capture_card_index, stat);
    throw std::runtime_error(XiErrorString(stat));
  }
  // Enable GenTL
  try {
    stat = xiSetParamInt(xi_handle_, XI_PRM_GENTL_DATASTREAM_ENABLED, XI_ON);
    if (stat != XI_OK) {
      vci::interceptor::logger()->error("Setting parameter '{}' of camera {} failed with error {} (value={}).",
                                        XI_PRM_GENTL_DATASTREAM_ENABLED, info_.capture_card_index,
                                        XiErrorString(stat).c_str(),
                                        1);  // XI_ON = 1
    }
    GenTL::DS_HANDLE stream_handle;
    stat = xiGetParamString(xi_handle_, XI_PRM_GENTL_DATASTREAM_CONTEXT, &stream_handle, sizeof(void*));
    if (stat != XI_OK) {
      vci::interceptor::logger()->error(
          "Getting parameter 'XI_PRM_GENTL_DATASTREAM_CONTEXT' of camera {} failed with error {}.",
          info_.capture_card_index, XiErrorString(stat).c_str());
    }
    buffer_.InitializeStream(stream_handle);
  } catch (...) {  // TODO?
    xiCloseDevice(xi_handle_);
    xi_handle_ == nullptr;
    throw;
  }
}

void XimeaCamera::OnClose() {
  buffer_.CloseStream();
  if (xi_handle_ != nullptr) {
    XI_RETURN stat = xiCloseDevice(xi_handle_);
    xi_handle_ = nullptr;
    if (stat != XI_OK) {
      vci::interceptor::logger()->error("Closing camera {} failed with code {}.", info_.capture_card_index, stat);
    }
  }
}

HANDLE XimeaCamera::Handle() {
  return xi_handle_;
}

void XimeaCamera::OnStart() {
  AllocateBuffer();
  buffer_.ForceQueue();
  // Start Acquisition
  buffer_.Start();
  is_running_ = true;
}

void XimeaCamera::OnStop() {
  buffer_.Stop();
}

void XimeaCamera::AllocateBuffer() {
  std::lock_guard<std::recursive_mutex> guard(state_mutex_);
  int payload_bytes = GetParameterInt(XI_PRM_IMAGE_PAYLOAD_SIZE);
  buffer_.SetPayload(payload_bytes);
  buffer_.Allocate();
}

int XimeaCamera::NumQueued() {
  return buffer_.NumQueued();
}

XimeaBufferEntry* XimeaCamera::CaptureNext(int timeout_ms) {
  if (!is_running_) {
    return nullptr;
  }
  std::lock_guard<std::mutex> capture_guard(capture_mutex_);
  return buffer_.CaptureNext(timeout_ms);
}

/**
 * @brief Get an integer parameter and the error code if it fails. Helper function that is reused in GetParameterInt and
 * TryGetParameter.
 */
int XimeaCamera::GetParameterIntHelper(const char* parameter, XI_RETURN& stat) {
  int value = 0;
  {
    py::gil_scoped_release release;
    stat = xiGetParamInt(xi_handle_, parameter, &value);
  }
  return value;
}

/**
 * @brief Get a float parameter and the error code if it fails. Helper function that is reused in GetParameterFloat and
 * TryGetParameter.
 */
float XimeaCamera::GetParameterFloatHelper(const char* parameter, XI_RETURN& stat) {
  float value = 0.f;
  {
    py::gil_scoped_release release;
    stat = xiGetParamFloat(xi_handle_, parameter, &value);
  }
  return value;
}

/**
 * @brief Get a string parameter and the error code if it fails. Helper function that is reused in GetParameterString
 * and TryGetParameter.
 */
std::string XimeaCamera::GetParameterStringHelper(const char* parameter, XI_RETURN& stat) {
  size_t SIZE = 10000;
  if (std::string(parameter) == "device_manifest") {
    SIZE = 2 * 1024 * 1024;
  }
  char* cval = new char[SIZE];
  {
    py::gil_scoped_release release;
    stat = xiGetParamString(xi_handle_, parameter, cval, SIZE);
  }
  std::string result(cval);
  delete[] cval;
  return result;
}

int XimeaCamera::GetParameterInt(const char* parameter) {
  Open();
  XI_RETURN stat;
  int value = this->GetParameterIntHelper(parameter, stat);
  if (stat != XI_OK) {
    vci::interceptor::logger()->error("Getting parameter '{}' of camera {} failed with error {}.", parameter,
                                      info_.capture_card_index, XiErrorString(stat).c_str());
  }
  return value;
}

void XimeaCamera::SetParameterInt(const char* parameter, int value) {
  Open();
  XI_RETURN stat = xiSetParamInt(xi_handle_, parameter, value);
  if (stat != XI_OK) {
    vci::interceptor::logger()->error("Setting parameter '{}' of camera {} failed with error {} (value={}).", parameter,
                                      info_.capture_card_index, XiErrorString(stat).c_str(), value);
  }
}

float XimeaCamera::GetParameterFloat(const char* parameter) {
  Open();
  XI_RETURN stat;
  float value = this->GetParameterFloatHelper(parameter, stat);
  if (stat != XI_OK) {
    vci::interceptor::logger()->error("Getting parameter '{}' of camera {} failed with error {}.", parameter,
                                      info_.capture_card_index, XiErrorString(stat).c_str());
  }
  return value;
}

void XimeaCamera::SetParameterFloat(const char* parameter, float value) {
  Open();
  XI_RETURN stat = xiSetParamFloat(xi_handle_, parameter, value);
  if (stat != XI_OK) {
    vci::interceptor::logger()->error("Setting parameter '{}' of camera {} failed with error {} (value={}).", parameter,
                                      info_.capture_card_index, XiErrorString(stat).c_str(), value);
  }
}

std::string XimeaCamera::GetParameterString(const char* parameter) {
  Open();
  XI_RETURN stat;
  std::string value = this->GetParameterStringHelper(parameter, stat);
  if (stat != XI_OK) {
    vci::interceptor::logger()->error("Getting parameter '{}' of camera {} failed with error {}.", parameter,
                                      info_.capture_card_index, XiErrorString(stat).c_str());
  }
  return value;
}

/**
 * @brief Attempts to retrieve a parameter from the camera and returns it as a string.
 * Throws an exception without logging it if the parameter cannot be retrieved.
 * Use this if you want to handle the error yourself, e.g. if you do not know beforehand if the parameter exists
 * (XI_PARAM_CONDITIONALLY_NOT_AVAILABLE etc).
 *
 * @param parameter The name of the parameter to retrieve.
 * @param data_type The data type of the parameter ("int", "float", or "string").
 * @return The parameter value as a string.
 * @throws std::runtime_error If there is an error retrieving the parameter.
 * @throws std::invalid_argument If an invalid data type is specified.
 */
std::string XimeaCamera::TryGetParameter(const char* parameter, const char* data_type) {
  Open();
  XI_RETURN stat;
  std::string result;

  if (std::string(data_type) == "int") {
    int value = this->GetParameterIntHelper(parameter, stat);
    result = std::to_string(value);
  } else if (std::string(data_type) == "float") {
    float value = this->GetParameterFloatHelper(parameter, stat);
    result = std::to_string(value);
  } else if (std::string(data_type) == "string") {
    std::string value = this->GetParameterStringHelper(parameter, stat);
    result = value;
  } else {
    throw std::invalid_argument("Invalid data type specified");
  }

  if (stat != XI_OK) {
    throw CameraParameterError(XiErrorString(stat));
  }

  return result;
}

/**
 * @brief Attempts to set a parameter of the camera.
 * Throws an exception without logging it if the parameter cannot be set.
 * Use this if you want to handle the error yourself, e.g. if you do not know beforehand if the parameter can be set.
 * @param parameter The name of the parameter to set.
 * @param data_type The data type of the parameter ("int", "float", or "string").
 * @param value The value to set the parameter to.
 * @throws std::runtime_error If there is an error setting the parameter.
 * @throws std::invalid_argument If an invalid data type is specified.
 */
void XimeaCamera::TrySetParameter(const char* parameter, const char* data_type, const char* value) {
  Open();
  XI_RETURN stat;
  if (std::string(data_type) == "int") {
    int int_value = std::stoi(value);
    stat = xiSetParamInt(xi_handle_, parameter, int_value);
    if (stat != XI_OK) {
      throw std::runtime_error(XiErrorString(stat));
    }
  } else if (std::string(data_type) == "float") {
    float float_value = std::stof(value);
    stat = xiSetParamFloat(xi_handle_, parameter, float_value);
    if (stat != XI_OK) {
      throw std::runtime_error(XiErrorString(stat));
    }
  } else if (std::string(data_type) == "string") {
    throw std::invalid_argument("Cannot set string parameters");
  } else {
    throw std::invalid_argument("Invalid data type specified");
  }
}

float XimeaCamera::GetTemperatureSensorBoard() {
  SetParameterInt(XI_PRM_TEMP_SELECTOR, XI_TEMP_SENSOR_BOARD);
  return GetParameterFloat(XI_PRM_TEMP);
}

/**
 * @brief Sets the sensor and output bit depth.
 *
 * Needs to be called before setting the lut.
 *
 * @param sensor_bit_depth
 * @param out_bit_depth
 * @param packing
 */
void XimeaCamera::SetBitDepth(int sensor_bit_depth, int out_bit_depth, bool packing) {
  if (has_lut_) {
    vci::interceptor::logger()->error("Cannot call 'SetBitLength' after 'SetLookupTable'.");
  }
  // Default to same bit depth
  if (out_bit_depth <= 0) {
    out_bit_depth = sensor_bit_depth;
  }
  // Sensor bit depth
  if (sensor_bit_depth == 8 || sensor_bit_depth == 10 || sensor_bit_depth == 12) {
    SetParameterInt(XI_PRM_SENSOR_DATA_BIT_DEPTH, XI_BIT_DEPTH(sensor_bit_depth));
  } else {
    vci::interceptor::logger()->error("Bit depth of sensor must be 8, 10 or 12, got {}", sensor_bit_depth);
  }
  // Output bit depth
  if (out_bit_depth == 8 || out_bit_depth == 10 || out_bit_depth == 12) {
    SetParameterInt(XI_PRM_OUTPUT_DATA_BIT_DEPTH, XI_BIT_DEPTH(out_bit_depth));
  } else {
    vci::interceptor::logger()->error("Bit depth of output must be 8, 10 or 12, got {}", out_bit_depth);
  }
  // Packing
  if (out_bit_depth > 8 && packing) {
    SetParameterInt(XI_PRM_OUTPUT_DATA_PACKING, XI_ON);
  } else {
    SetParameterInt(XI_PRM_OUTPUT_DATA_PACKING, XI_OFF);
  }
}

/**
 * @brief Set camera look-up table.
 *
 * Internally, the camera uses a 12bit to 12bit lut no matter the set bit depth.
 * Since that is annoying to handle, this function does the conversion for you.
 * So if the sensor uses n bits, the lut vector should be 2^n long.
 * If the output bit depth is m bits, the entries in the vector should be
 * between 0 and 2^m.
 *
 * @param lut Mapping of values i to lut[i]
 *
 * @exception InvalidArgumentError lut has the wrong length or values outside
 *            the range
 */
void XimeaCamera::SetLookupTable(const std::vector<int>& lut) {
  has_lut_ = true;
  // Check sensor bit depth
  int sensor_bit_depth = GetParameterInt(XI_PRM_SENSOR_DATA_BIT_DEPTH);
  int lut_length = std::pow(2, sensor_bit_depth);
  if (lut_length != lut.size()) {
    vci::interceptor::logger()->error("LUT has wrong length for {} bit sensor. Expected {}, got {}", sensor_bit_depth,
                                      lut_length, lut.size());
  }
  int idx_multiplier = std::pow(2, 12 - sensor_bit_depth);
  // Check output bit depth
  int output_bit_depth = GetParameterInt(XI_PRM_OUTPUT_DATA_BIT_DEPTH);
  int max_value = std::pow(2, output_bit_depth);
  int value_mutliplier = std::pow(2, 12 - output_bit_depth);
  SetParameterInt(XI_PRM_LUT_EN, XI_ON);
  for (int i = 0; i < lut_length; ++i) {
    int value = lut[i];
    if (value < 0 || value >= max_value) {
      vci::interceptor::logger()->error("Invalid LUT value for {} bit output. Mus be in range [0, {}), got {}",
                                        output_bit_depth, max_value, value);
    }
    SetParameterInt(XI_PRM_LUT_INDEX, idx_multiplier * i);
    SetParameterInt(XI_PRM_LUT_VALUE, value_mutliplier * lut[i]);
  }
}

int XimeaCamera::GetBufferLength() {
  return GetParameterInt(XI_PRM_BUFFERS_QUEUE_SIZE);
}

/**
 * @brief Sets the buffer length.
 *
 * Opens the camera if needed. Only works when no acquisition is running.
 *
 * Does not change the buffer immediately, but only resizes the
 * Camera#buffer_ vector for the meta infromation of the frames.
 * The resizing happens before starting a capture.
 *
 * @param buffer_length Length of the buffer in frames
 *
 * @exception NotDuringCaptureError Only allowed while not capturing
 */
void XimeaCamera::SetBufferLength(int buffer_length) {
  if (is_running_) {
    vci::interceptor::logger()->error("Action 'SetBufferLength' not possible while capturing is active.");
  }
  buffer_.SetLength(buffer_length);
}

int XimeaCamera::GetCounter(int counter) {
  Open();
  SetParameterInt(XI_PRM_COUNTER_SELECTOR, counter);
  return GetParameterInt(XI_PRM_COUNTER_VALUE);
}
