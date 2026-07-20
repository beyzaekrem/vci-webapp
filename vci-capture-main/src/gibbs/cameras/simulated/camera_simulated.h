#ifndef CAPTN_SIMULATED_CAMERA_H
#define CAPTN_SIMULATED_CAMERA_H

#include <condition_variable>
#include <mutex>
#include <random>
#include <string>
#include <thread>
#include <vector>
#include "buffer.h"
#include "buffer_simulated.h"
#include "camera.h"
#include "util.h"

class SimulatedCamera : public Camera, NonCopyable {
 public:
  SimulatedCamera(int id, std::string serialnumber, int width = 640, int height = 480,
                  ImageType type = ImageType::Color, PixelLayout pixel_layout = PixelLayout::BGGR);
  ~SimulatedCamera() override = default;

  // General
  virtual void SetPrimary() {}
  virtual void SetSecondary() {}
  void OnOpen() {};
  void OnClose() {};
  int NumQueued() override;

  // Capture
  void OnStart() override;
  void OnStop() override;
  BufferEntry* CaptureNext(int timeout_ms = 200) override;

  void SetDefaultParameters() override;
  void OnSetTriggerSource(TriggerSource trigger_source) override;
  void SetExposure(int exposure) override;
  void SetGain(int gain) override;
  void PerformSoftwareTrigger() override;

  void InitializeBuffer();

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
  int GetCounter(int counter_selector) override;

 private:
  int exposure_ = -1;
  int gain_ = -1;
  int width_;
  int height_;
  int bit_depth_;
  PixelLayout pixel_layout_;

  // triggering
  std::atomic<int> images_in_buffer_{0};

  // image capture
  std::condition_variable cv_;
  std::mutex capture_mutex_;
  std::vector<uint8_t> dummy_frame_;
  std::unique_ptr<SimulatedBuffer> buffer_entry_;

  void GenerateDummyFrame();
  void HardwareTriggerThread();
};

#endif  // SIMULATED_CAMERA_H
