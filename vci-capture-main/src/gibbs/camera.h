#ifndef CAPTN_CAMERA_H
#define CAPTN_CAMERA_H

#include <stdlib.h>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include <interceptor/logging.h>
#include <pybind11/pybind11.h>
#include "buffer.h"
namespace py = pybind11;

enum class TriggerSource { Hardware, Software };
TriggerSource StringToTriggerSource(std::string str);
std::string TriggerSourceToString(TriggerSource source);

class ManifestEntry {
 public:
  ManifestEntry(std::string xiapi_par, std::string display_name, std::string description) {
    dict_["Xiapi_Par"] = xiapi_par;
    dict_["DisplayName"] = display_name;
    dict_["Description"] = description;
  }

  ManifestEntry& Visibility(std::string v) {
    dict_["Visibility"] = v;
    return *this;
  }
  ManifestEntry& AccessMode(std::string v) {
    dict_["ImposedAccessMode"] = v;
    return *this;
  }
  ManifestEntry& DataType(std::string v) {
    dict_["DataType"] = v;
    return *this;
  }
  ManifestEntry& ManifestGroup(std::string v) {
    dict_["ManifestGroup"] = v;
    return *this;
  }
  ManifestEntry& Representation(std::string v) {
    dict_["Representation"] = v;
    return *this;
  }
  ManifestEntry& PValue(std::string v) {
    dict_["pValue"] = v;
    return *this;
  }
  ManifestEntry& PMin(std::string v) {
    dict_["pMin"] = v;
    return *this;
  }
  ManifestEntry& PMax(std::string v) {
    dict_["pMax"] = v;
    return *this;
  }
  ManifestEntry& RegisterInfo(py::dict v) {
    dict_["RegisterInfoFromManifest"] = v;
    return *this;
  }

  py::dict Build() const {
    return dict_;
  }

 private:
  py::dict dict_;
};

class Camera {
 public:
  virtual ~Camera() {
    try {
      StopSoftwareAutoTrigger();
      Close();
    } catch (std::runtime_error e) {
      vci::interceptor::logger()->error("{}", e.what());
    }
  }

  CameraInfo Info() const {
    return info_;
  }
  void SetCameraId(std::string camera_id) {
    info_.camera_id = camera_id;
  }

  py::dict to_dict() const {
    py::dict d;
    d["camera_id"] = Info().camera_id;
    d["manufacturer"] = Info().manufacturer;
    d["running"] = is_running_.load();
    d["image_type"] = ImageTypeToString(Info().camera_type);
    d["exposure"] = GetExposure();
    d["gain"] = GetGain();
    d["trigger_source"] = TriggerSourceToString(trigger_source_);
    return d;
  }

  // --- State ---
  virtual void OnOpen() = 0;
  virtual void OnStart() = 0;
  virtual void OnClose() = 0;
  virtual void OnStop() = 0;

  void Open() {
    std::lock_guard<std::recursive_mutex> guard(state_mutex_);
    if (!is_open_) {
      OnOpen();
    }
    is_open_ = true;
  };

  void Close() {
    // If we are still running, stop everything properly first
    if (is_running_) {
      Stop();
    }

    std::lock_guard<std::recursive_mutex> guard(state_mutex_);
    if (is_open_) {
      try {
        OnClose();  // Virtual hook for specific hardware close
      } catch (const ExceptionBase& e) {
        //
      }
      is_open_ = false;
    }
  }

  void Start() {
    std::lock_guard<std::recursive_mutex> guard(state_mutex_);
    Open();  // ensure the camera is open.
    if (!is_running_) {
      OnStart();  // hareware specifc open task
      is_running_ = true;
    }
  }

  bool IsRunning() {
    return is_running_;
  }
  bool IsOpen() {
    return is_open_;
  }

  void Stop() {
    std::lock_guard<std::recursive_mutex> guard(state_mutex_);
    if (!is_running_) return;

    // Kill the software thread first
    StopSoftwareAutoTrigger();

    // Specialized Cleanup: Call the specific camera's logic
    OnStop();

    is_running_ = false;
  }

  // --- triggering ---

  virtual void OnSetTriggerSource(TriggerSource trigger_source) = 0;
  virtual void PerformSoftwareTrigger() = 0;

  void SetTriggerSouce(TriggerSource source) {
    if (is_running_) {
      throw std::runtime_error("Cannot set trigger source while camera is running.");
    }
    trigger_source_ = source;
  }
  TriggerSource GetTriggerSource() {
    return trigger_source_;
  }

  void SetSoftwareFPS(double fps) {
    trigger_interval_ms_ = static_cast<int>(1000.0 / fps);
  }

  void StartSoftwareAutoTrigger() {
    if (trigger_source_ != TriggerSource::Software) {
      // Log: "Auto-trigger ignored: Camera is in Hardware mode"
      return;
    }

    std::lock_guard<std::mutex> lock(trigger_mutex_);
    if (auto_trigger_active_) return;

    auto_trigger_active_ = true;

    auto_trigger_thread_ = std::thread([this]() {
      while (auto_trigger_active_) {
        this->PerformSoftwareTrigger();
        // Wait for the interval OR for the CV to be notified (shutdown)
        std::unique_lock<std::mutex> lock(trigger_mutex_);
        trigger_cv_.wait_for(lock, std::chrono::milliseconds(trigger_interval_ms_.load()),
                             [this] { return !auto_trigger_active_; });
      }
    });
  }

  void StopSoftwareAutoTrigger() {
    {
      std::lock_guard<std::mutex> lock(trigger_mutex_);
      auto_trigger_active_ = false;
    }
    if (auto_trigger_thread_.joinable()) {
      auto_trigger_thread_.join();
    }
    }

  virtual int NumQueued() = 0;
  // For XIMEA cameras, GetCounter may be implemented in derived class
  virtual int GetCounter(int counter_selector) = 0;

  virtual BufferEntry* CaptureNext(int timeout_ms = 200) = 0;

  // Sets hardware specifc default parameters for vci-setup.
  virtual void SetDefaultParameters() = 0;

  virtual void SetExposure(int exposure) = 0;
  virtual void SetGain(int gain) = 0;

  virtual int GetExposure() const = 0;
  virtual int GetGain() const = 0;

  // parameter acessors
  virtual int GetParameterInt(const char* parameter) = 0;
  virtual void SetParameterInt(const char* parameter, int value) = 0;
  virtual float GetParameterFloat(const char* parameter) = 0;
  virtual void SetParameterFloat(const char* parameter, float value) = 0;
  virtual std::string GetParameterString(const char* parameter) = 0;

  virtual std::string TryGetParameter(const char* parameter, const char* data_type) = 0;
  virtual void TrySetParameter(const char* parameter, const char* data_type, const char* value) = 0;

  virtual void SetBitDepth(int sensor_bit_depth, int out_bit_depth = 0, bool packing = true) = 0;
  virtual void SetPrimary() {};
  virtual void SetSecondary() {};

  py::list GetManifest() const {
    py::list manifest;

    manifest.append(
        ManifestEntry("exposure", "Exposure time", "Exposure time in microseconds")
            .Visibility("Beginner")
            .AccessMode("RW")
            .DataType("Float")
            .ManifestGroup("Basic")
            .Representation("Logarithmic")
            .PMin("ExposureTimeMinReg")
            .PMax("ExposureTimeMaxReg")
            .PValue("ExposureTimeReg")
            .RegisterInfo(py::dict(py::arg("xiApiPar") = "exposure", py::arg("Name") = "ExposureTimeReg",
                                   py::arg("DataType") = "FloatReg", py::arg("ManifestGroup") = "Basic Registers",
                                   py::arg("NameFromManifest") = "ExposureTimeReg"))
            .Build());

    manifest.append(ManifestEntry("gain", "Gain", "Gain in dB")
                        .Visibility("Beginner")
                        .AccessMode("RW")
                        .DataType("Float")
                        .ManifestGroup("Basic")
                        .PMin("GainMinReg")
                        .PMax("GainMaxReg")
                        .PValue("GainReg")
                        .RegisterInfo(py::dict(
                            py::arg("xiApiPar") = "gain", py::arg("Name") = "GainReg", py::arg("DataType") = "FloatReg",
                            py::arg("ManifestGroup") = "Basic Registers", py::arg("NameFromManifest") = "GainReg"))
                        .Build());

    return manifest;
  }

 protected:
  CameraInfo info_;

  // State
  std::recursive_mutex state_mutex_;
  std::atomic<bool> is_open_ = false;
  std::atomic<bool> is_running_ = false;
  TriggerSource trigger_source_ = TriggerSource::Hardware;

  // Software Triggering:
  std::atomic<bool> auto_trigger_active_{false};
  std::atomic<int> trigger_interval_ms_{100};
  std::thread auto_trigger_thread_;
  std::mutex trigger_mutex_;
  std::condition_variable trigger_cv_;
};

#endif
