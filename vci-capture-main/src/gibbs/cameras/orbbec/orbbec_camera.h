#pragma once
#include <libobsensor/ObSensor.hpp>
#include <memory>
#include <string>
#include <vector>
#include "buffer.h"
#include "camera.h"

class OrbbecCamera : public Camera {
 public:
  explicit OrbbecCamera(int id);
  ~OrbbecCamera() override = default;
  void SetMode(ImageType m);

  void OnOpen() override;
  void OnClose() override;

  void OnStart() override;
  void OnStop() override;

  int NumQueued() override {
    return 0;
  }

  BufferEntry* CaptureNext(int timeout_ms = 200) override;

  void SetDefaultParameters() override;
  void PerformSoftwareTrigger() override;
  void OnSetTriggerSource(TriggerSource trigger_source) override;

  void SetExposure(int) override;
  void SetGain(int) override;
  int GetExposure() const override;
  int GetGain() const override;

  int GetParameterInt(const char*) override;
  void SetParameterInt(const char*, int) override;
  float GetParameterFloat(const char*) override;
  void SetParameterFloat(const char*, float) override {}
  std::string GetParameterString(const char*) override {
    return {};
  }

  std::string TryGetParameter(const char*, const char*) override {
    return {};
  }
  void TrySetParameter(const char*, const char*, const char*) override {}
  ImageType GetMode() const {
    return mode_;
  }
  void SetBitDepth(int, int = 0, bool = true) override {}
  void SetPrimary();
  void SetSecondary();
  int GetCounter(int counter_selector) override;
  bool SupportsProperty(const char* property_name) const;
  std::vector<std::string> GetSupportedProperties() const;

 private:
  std::shared_ptr<ob::StreamProfile> GetColorProfile();
  std::shared_ptr<ob::StreamProfile> GetMonoProfile();
  std::shared_ptr<ob::StreamProfile> GetDepthProfile();
  std::shared_ptr<ob::Config> createHwD2CAlignConfig();
  bool checkIfSupportHWD2CAlign(std::shared_ptr<ob::StreamProfile> colorStreamProfile,
                                std::shared_ptr<ob::StreamProfile> depthStreamProfile);
  void DebugProfile(std::shared_ptr<ob::StreamProfile> prof);

  ImageType mode_ = ImageType::Depth;
  int id_;
  std::shared_ptr<ob::Context> ctx_;
  std::shared_ptr<ob::Device> dev_;
  std::unique_ptr<ob::Pipeline> pipe_;
};
