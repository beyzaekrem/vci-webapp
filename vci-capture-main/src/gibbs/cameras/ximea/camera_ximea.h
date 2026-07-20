#ifndef CAPTN_XIMEA_CAMERA_H
#define CAPTN_XIMEA_CAMERA_H
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>

#include "buffer.h"
#include "buffer_ximea.h"
#include "camera.h"
#include "util.h"
#include "xi_include.h"
#include "xi_util.h"

/**
 * @brief Control XIMEA camera
 *
 * For buffering, we don't use the XIMEA XPI and instead use the GenTL API for
 * more control. One advantage is that we can prohibit overwriting of buffers
 * which would lead to missing data without us knowing. If there is no more
 * space in the buffer we can see that one or more frames are missing.
 *
 */
class XimeaCamera : public Camera, NonCopyable {
 public:
  XimeaCamera(int id, int buffer_length = 8);
  ~XimeaCamera() override = default;

  void OnOpen() override;
  void OnClose() override;

  HANDLE Handle();
  void OnStart() override;
  void OnStop() override;
  void AllocateBuffer();
  int NumQueued() override;
  /**
   * @brief Returns a reference to the buffer entry of the captured frame
   */
  XimeaBufferEntry* CaptureNext(int timeout_ms = 200) override;
  void PerformSoftwareTrigger() override;

  void SetDefaultParameters() override;
  void OnSetTriggerSource(TriggerSource trigger_source) override;
  void SetExposure(int exposure) override;
  void SetGain(int gain) override;

  int GetExposure() const override;
  int GetGain() const override;

  int GetParameterInt(const char* parameter) override;
  void SetParameterInt(const char* parameter, int value) override;
  float GetParameterFloat(const char* parameter) override;
  void SetParameterFloat(const char* parameter, float value) override;
  std::string GetParameterString(const char* parameter) override;

  std::string TryGetParameter(const char* parameter, const char* data_type) override;
  void TrySetParameter(const char* parameter, const char* data_type, const char* value) override;

  void SetBitDepth(int sensor_bit_depth, int out_bit_depth = 0, bool packing = true) override;

  float GetTemperatureSensorBoard();
  void SetLookupTable(const std::vector<int>& lut);
  int GetBufferLength();
  void SetBufferLength(int buffer_length);

  int GetCounter(int counter) override;

 private:
  // General Info
  bool has_lut_;

  // Handle and State
  HANDLE xi_handle_;
  std::recursive_mutex state_mutex_;

  /// Frame buffer
  FrameBuffer buffer_;
  std::mutex capture_mutex_;

  int GetParameterIntHelper(const char* parameter, XI_RETURN& stat);
  float GetParameterFloatHelper(const char* parameter, XI_RETURN& stat);
  std::string GetParameterStringHelper(const char* parameter, XI_RETURN& stat);
  virtual void SetPrimary() {}
  virtual void SetSecondary() {}
};

#endif  // CAPTN_CAMERA_H
