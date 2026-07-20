#ifndef CAPTN_BASLER_CAMERA_H
#define CAPTN_BASLER_CAMERA_H

#include <pylon/BaslerUniversalInstantCamera.h>  // adjust if using specific camera headers
#include <pylon/PylonIncludes.h>
#include <atomic>
#include <condition_variable>
#include <mutex>
#include <thread>
#include <vector>
#include "basler_buffer.h"
#include "buffer.h"
#include "camera.h"

class BaslerCamera : public Camera {
 public:
  BaslerCamera(int index, Pylon::CDeviceInfo pylonDeviceInfo);
  ~BaslerCamera() override = default;

  void OnOpen() override;
  void OnClose() override;

  void OnStart() override;
  void OnStop() override;

  // Capture
  int NumQueued() override;
  int GetCounter(int counter_selector) override;
  BufferEntry* CaptureNext(int timeout_ms = 200) override;
  void PerformSoftwareTrigger() override;

  // Parameter shortcuts
  void SetDefaultParameters() override;
  void OnSetTriggerSource(TriggerSource trigger_source) override;
  void SetExposure(int exposure) override;
  void SetGain(int gain) override;
  void SetROI(int width, int height);
  void SetBurstMode(int burstFrames);

  int GetExposure() const override;
  int GetGain() const override;

  // Parameter accessors
  int GetParameterInt(const char* parameter) override;
  void SetParameterInt(const char* parameter, int value) override;
  float GetParameterFloat(const char* parameter) override;
  void SetParameterFloat(const char* parameter, float value) override;
  std::string GetParameterString(const char* parameter) override;

  std::string TryGetParameter(const char* parameter, const char* data_type) override;
  void TrySetParameter(const char* parameter, const char* data_type, const char* value) override;

  void SetBitDepth(int sensor_bit_depth, int out_bit_depth = 0, bool packing = true) override;

 private:
  std::unique_ptr<Pylon::CGrabResultData> CreateDeviceSpecificGrabResult();

  std::mutex capture_mutex_;
  size_t next_frame_index_;

  Pylon::CInstantCamera camera_;  // universal pylon(basler) camera

  Pylon::CGrabResultPtr grab_;                       // owns the acutal pylon frame memory
  std::unique_ptr<BaslerBufferEntry> buffer_entry_;  // wraps grab_ for our BufferEntry API

  GenApi::INodeMap* nodemap_;  // for camera parameter access
};

#endif  // CAPTN_BASLER_CAMERA_H
