// camera_manager.h
#ifndef CAPTN_CAMERA_MANAGER_H
#define CAPTN_CAMERA_MANAGER_H

#include <memory>
#include <mutex>
#include <optional>
#include <vector>
#include "camera.h"

class CameraFactory {
 public:
  virtual ~CameraFactory() = default;
  virtual std::vector<std::shared_ptr<Camera>> CreateCameras() = 0;
  virtual std::string GetName() = 0;
};

class CameraManager {
 public:
  CameraManager(CameraManager const&) = delete;
  void operator=(CameraManager const&) = delete;

  static void ConfigureSimulation(const std::string& path);

  static CameraManager& getInstance();

  static void DisableApiLogging();

  static int NumCameras();
  static std::shared_ptr<Camera> GetCameraById(int id);
  static std::shared_ptr<Camera> GetCameraBySerialNumber(const std::string& serialnumber);

 private:
  CameraManager(std::optional<std::string> simulatedCamerasConfig);
  static std::recursive_mutex& Mutex();
  void RegisterFactory(std::unique_ptr<CameraFactory> factory);

  std::vector<std::shared_ptr<Camera>> camera_list_;
  std::vector<std::unique_ptr<CameraFactory>> factories_;
};

class XimeaCameraFactory : public CameraFactory {
 public:
  XimeaCameraFactory();
  ~XimeaCameraFactory() override;

  int NumCameras();
  std::vector<std::shared_ptr<Camera>> CreateCameras() override;
  std::string GetName() {
    return "Ximea";
  }
};

class SimulatedCameraFactory : public CameraFactory {
 public:
  SimulatedCameraFactory(const std::string& config_path);
  std::vector<std::shared_ptr<Camera>> CreateCameras() override;
  std::string GetName() {
    return "Simulated";
  }

 private:
  struct SimConfig {
    std::string serial;
    int width;
    int height;
    ImageType type;
    PixelLayout pixel_layout;
  };

  std::vector<SimConfig> config_;
};

class OrbbecCameraFactory : public CameraFactory {
 public:
  OrbbecCameraFactory();
  ~OrbbecCameraFactory() override = default;

  int NumCameras();
  std::vector<std::shared_ptr<Camera>> CreateCameras() override;
  std::string GetName() {
    return "Orbbec";
  }
};

class BaslerCameraFactory : public CameraFactory {
 public:
  BaslerCameraFactory();
  ~BaslerCameraFactory() override;
  std::vector<std::shared_ptr<Camera>> CreateCameras() override;
  std::vector<std::weak_ptr<Camera>> created_cameras_;
  std::string GetName() {
    return "Basler";
  }
};

#endif  // CAPTN_CAMERA_MANAGER_H
