#include "basler_camera.h"
#include <iostream>

using namespace Pylon;
using namespace std;
using namespace GenApi;

BaslerCamera::BaslerCamera(int id, CDeviceInfo pylonDeviceInfo) {
  std::cout << "creating basler camera " << id << std::endl;

  IPylonDevice* pylonDevice = CTlFactory::GetInstance().CreateDevice(pylonDeviceInfo);
  camera_.Attach(pylonDevice);
  nodemap_ = &camera_.GetNodeMap();

  info_.manufacturer = "Basler";
  info_.camera_type = ImageType::Color;
  info_.serialnumber = camera_.GetDeviceInfo().GetSerialNumber();
  info_.device_model_name = camera_.GetDeviceInfo().GetModelName();
  info_.capture_card_index = id;
  info_.camera_id = info_.serialnumber;
}

//-----------------------------------
// Open / Close
void BaslerCamera::OnOpen() {
  buffer_entry_ = std::make_unique<BaslerBufferEntry>(info_);  // info_ is now complete
  camera_.Open();
}

void BaslerCamera::OnClose() {
  try {
    if (camera_.IsPylonDeviceAttached()) {
      if (camera_.IsOpen()) {
        camera_.Close();
      }
      camera_.DetachDevice();
    }

    nodemap_ = nullptr;  // the nodemap dies when the device is detached
  } catch (const GenericException& e) {
    vci::interceptor::logger()->error("Error closing Basler camera {}: {}", info_.camera_id, e.GetDescription());
  }
}

//-----------------------------------
// Start / Stop
void BaslerCamera::OnStart() {
  camera_.OutputQueueSize = 10;
  camera_.StartGrabbing(GrabStrategy_LatestImages);  // GrabStrategy_UpcomingImage);
}

void BaslerCamera::OnStop() {
  if (camera_.IsPylonDeviceAttached() && camera_.IsGrabbing()) {
    camera_.StopGrabbing();
  }
}

//-----------------------------------
// Capture next frame
BufferEntry* BaslerCamera::CaptureNext(int timeout_ms) {
  if (!is_running_) {
    return nullptr;
  }
  bool success = camera_.RetrieveResult(timeout_ms, grab_, TimeoutHandling_Return);
  if (!success) {
    vci::interceptor::logger()->error("Basler RetriveResult operation has timed out");
    throw BufferTimeout();
  }

  if (!grab_->GrabSucceeded()) {
    throw BufferIncomplete();
  }

  buffer_entry_->Attach(grab_);
  return buffer_entry_.get();  // returns a BaslerBufferEntry which is a BufferEntry
}

//-----------------------------------
// parameter functions
void BaslerCamera::SetDefaultParameters() {
  try {
    nodemap_ = &camera_.GetNodeMap();

    // Basic Format Settings
    INodeMap* tl_nodemap = &camera_.GetTLNodeMap();
    CBooleanPtr output_packed_format(tl_nodemap->GetNode("OutputPackedFormats"));
    if (IsWritable(output_packed_format)) output_packed_format->SetValue(true);

    CEnumerationPtr pixelFormat(nodemap_->GetNode("PixelFormat"));
    pixelFormat->FromString("BayerRG12");

    SetBurstMode(-1);

    // Default to Software Trigger
    SetTriggerSouce(TriggerSource::Software);
    SetROI(4128, 2200);

  } catch (const GenericException& e) {
    vci::interceptor::logger()->error("Basler SetDefaultParameters failed: {}", e.GetDescription());
  }
}

void BaslerCamera::SetBurstMode(int burstFrames) {
  try {
    CEnumerationPtr triggerSelector(nodemap_->GetNode("TriggerSelector"));
    CEnumerationPtr triggerMode(nodemap_->GetNode("TriggerMode"));
    if (burstFrames > 1) {
      // --- ENABLE BURST MODE ---
      // one trigger captures 2, 3, ... 10 frames
      triggerSelector->FromString("FrameStart");
      triggerMode->FromString("Off");

      triggerSelector->FromString("FrameBurstStart");
      triggerMode->FromString("On");

      CIntegerPtr burstCount(nodemap_->GetNode("AcquisitionBurstFrameCount"));
      if (IsWritable(burstCount)) burstCount->SetValue(burstFrames);

      // Set the spacing between those burst frames
      CBooleanPtr frameRateEnable(nodemap_->GetNode("AcquisitionFrameRateEnable"));
      frameRateEnable->SetValue(true);
      CFloatPtr frameRate(nodemap_->GetNode("AcquisitionFrameRate"));
      frameRate->SetValue(60.0);

      vci::interceptor::logger()->info("Burst Mode ENABLED: {} frames per burst at 60 fps", burstFrames);
    } else {
      // --- DISABLE BURST MODE ---
      triggerSelector->FromString("FrameBurstStart");
      triggerMode->FromString("Off");

      triggerSelector->FromString("FrameStart");
      triggerMode->FromString("On");

      // AcquisitionFrameRateEnable OFF in single trigger
      // so the camera doesn't artificially delay the shot.
      CBooleanPtr frameRateEnable(nodemap_->GetNode("AcquisitionFrameRateEnable"));
      frameRateEnable->SetValue(false);

      vci::interceptor::logger()->info("Burst Mode DISABLED: Single frame trigger active");
    }

  } catch (const GenericException& e) {
    vci::interceptor::logger()->error("Basler SetBurstMode failed: {}", e.GetDescription());
  }
}

void BaslerCamera::SetROI(int width, int height) {
  try {
    CIntegerPtr widthMax(nodemap_->GetNode("WidthMax"));
    CIntegerPtr heightMax(nodemap_->GetNode("HeightMax"));

    // Force dimensions and offsets to be even (Bayer-safe)
    int targetWidth = (std::min(width, (int)widthMax->GetValue()) / 2) * 2;
    int targetHeight = (std::min(height, (int)heightMax->GetValue()) / 2) * 2;

    int offsetY = ((heightMax->GetValue() - targetHeight) / 4) * 2;  // Extra safe centering
    int offsetX = ((widthMax->GetValue() - targetWidth) / 4) * 2;

    CIntegerPtr(nodemap_->GetNode("OffsetX"))->SetValue(0);
    CIntegerPtr(nodemap_->GetNode("OffsetY"))->SetValue(0);

    CIntegerPtr(nodemap_->GetNode("Width"))->SetValue(targetWidth);
    CIntegerPtr(nodemap_->GetNode("Height"))->SetValue(targetHeight);

    CIntegerPtr(nodemap_->GetNode("OffsetX"))->SetValue(offsetX);
    CIntegerPtr(nodemap_->GetNode("OffsetY"))->SetValue(offsetY);

    vci::interceptor::logger()->info("Bayer-Safe ROI: {}x{} @ {},{}", targetWidth, targetHeight, offsetX, offsetY);
  } catch (const GenericException& e) {
    vci::interceptor::logger()->error("ROI Error: {}", e.GetDescription());
  }
}

void BaslerCamera::OnSetTriggerSource(TriggerSource source) {
  try {
    std::string s = "";
    switch (source) {
      case TriggerSource::Hardware:
        s = "Line1";
        break;
      default:
        s = "Software";
        break;
    }

    CEnumerationPtr source(nodemap_->GetNode("TriggerSource"));
    source->FromString(s.c_str());

    CIntegerPtr divider(nodemap_->GetNode("TriggerDivider"));
    if (IsWritable(divider)) {
      divider->SetValue(1);  // Hardware handles the "ignore 3" logic
    }
    vci::interceptor::logger()->info("Basler switched to Trigger Source: ", s);
  } catch (const GenericException& e) {
    vci::interceptor::logger()->error("EnableHardwareTrigger failed: {}", e.GetDescription());
  }
}

void BaslerCamera::SetExposure(int exposure) {
  SetParameterFloat("ExposureTime", exposure);
}
void BaslerCamera::SetGain(int gain) {
  SetParameterFloat("Gain", gain);
}

int BaslerCamera::GetExposure() const {
  return const_cast<BaslerCamera*>(this)->GetParameterInt("ExposureTime");
}
int BaslerCamera::GetGain() const {
  return const_cast<BaslerCamera*>(this)->GetParameterInt("Gain");
}

int BaslerCamera::GetParameterInt(const char* parameter) {
  try {
    GenApi::CIntegerPtr intNode = nodemap_->GetNode(parameter);
    if (GenApi::IsAvailable(intNode) && GenApi::IsReadable(intNode)) {
      return intNode->GetValue();
    } else {
      vci::interceptor::logger()->error("Balser camera could not get int {}. It is not available or not readable.",
                                        parameter);
      return 0;
    }
  } catch (const GenericException& e) {
    vci::interceptor::logger()->error("Error getting int parameter {}: {}", parameter, e.GetDescription());
    return 0;
  }
}
void BaslerCamera::SetParameterInt(const char* parameter, int value) {
  GenApi::CIntegerPtr parameterNode = nodemap_->GetNode(parameter);
  if (GenApi::IsAvailable(parameterNode) && GenApi::IsWritable(parameterNode)) {
    parameterNode->SetValue(value);
  } else {
    vci::interceptor::logger()->error("Balser camera could not set int {} to {}. It is not available or not writable.",
                                      parameter, value);
  }
}

float BaslerCamera::GetParameterFloat(const char* parameter) {
  try {
    GenApi::CFloatPtr floatNode = nodemap_->GetNode(parameter);
    if (GenApi::IsAvailable(floatNode) && GenApi::IsReadable(floatNode)) {
      return static_cast<float>(floatNode->GetValue());
    } else {
      vci::interceptor::logger()->error("Balser camera could not get float {}. It is not available or not readable.",
                                        parameter);
      return 0.0f;
    }
  } catch (const GenericException& e) {
    vci::interceptor::logger()->error("Error getting float parameter {}: {}", parameter, e.GetDescription());
    return 0.0f;
  }
}
void BaslerCamera::SetParameterFloat(const char* parameter, float value) {
  GenApi::CFloatPtr floatNode = nodemap_->GetNode(parameter);
  if (GenApi::IsAvailable(floatNode) && GenApi::IsWritable(floatNode)) {
    floatNode->SetValue(static_cast<double>(value));
  } else {
    vci::interceptor::logger()->error(
        "Balser camera could not set float {} to {}. It is not available or not writable.", parameter, value);
  }
}
std::string BaslerCamera::GetParameterString(const char* parameter) {
  try {
    GenApi::CStringPtr stringNode = nodemap_->GetNode(parameter);
    if (GenApi::IsAvailable(stringNode) && GenApi::IsReadable(stringNode)) {
      return std::string(stringNode->GetValue());
    } else {
      vci::interceptor::logger()->error("Balser camera could not get string {}. It is not available or not readable.",
                                        parameter);
      return "";
    }
  } catch (const GenericException& e) {
    vci::interceptor::logger()->error("Error getting string parameter {}: {}", parameter, e.GetDescription());
    return "";
  }
}
std::string BaslerCamera::TryGetParameter(const char*, const char*) {
  return "";
}
void BaslerCamera::TrySetParameter(const char*, const char*, const char*) {}
void BaslerCamera::SetBitDepth(int, int, bool) {}
int BaslerCamera::NumQueued() {
  return 0;
}
int BaslerCamera::GetCounter(int) {
  return 0;
}
void BaslerCamera::PerformSoftwareTrigger() {
  CCommandPtr triggerSoftware(nodemap_->GetNode("TriggerSoftware"));
  triggerSoftware->Execute();
  vci::interceptor::logger()->debug("Basler Software Trigger Executed");
}
