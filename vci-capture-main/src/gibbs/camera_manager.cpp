#include "camera_manager.h"
#include <interceptor/logging.h>
#include <stdexcept>

#include "cameras/simulated/camera_simulated.h"

#ifdef ENABLE_BASLER_SUPPORT
#include <pylon/BaslerUniversalInstantCamera.h>
#include <pylon/PylonIncludes.h>
#include "cameras/basler/basler_camera.h"
#endif

// XIMEA support
#ifdef ENABLE_XIMEA_SUPPORT
#include "cameras/ximea/camera_ximea.h"
#endif

#ifdef ENABLE_ORBBEC_SUPPORT
#include <libobsensor/ObSensor.hpp>
#include "cameras/orbbec/orbbec_camera.h"
#endif

#include <fstream>
#include <nlohmann/json.hpp>
#include <stdexcept>
using json = nlohmann::json;

// switches to simualted cameras, rather then opening hardware cameras
static std::optional<std::string> s_pendingSimPath = std::nullopt;
void CameraManager::ConfigureSimulation(const std::string& path) {
  s_pendingSimPath = path;
}

CameraManager& CameraManager::getInstance() {
  std::lock_guard<std::recursive_mutex> guard(Mutex());
  static CameraManager instance(s_pendingSimPath);
  return instance;
}

void CameraManager::DisableApiLogging() {
  std::lock_guard<std::recursive_mutex> guard(Mutex());
#ifdef ENABLE_XIMEA_SUPPORT
  xiSetParamInt(nullptr, XI_PRM_DEBUG_LEVEL, XI_DL_DISABLED);
#endif
}

int CameraManager::NumCameras() {
  return static_cast<int>(getInstance().camera_list_.size());
}

std::shared_ptr<Camera> CameraManager::GetCameraById(int id) {
  std::lock_guard<std::recursive_mutex> guard(Mutex());
  int num_cameras = static_cast<int>(getInstance().camera_list_.size());
  if (id < 0 || id >= num_cameras) {
    vci::interceptor::logger()->error("Invalid Camera ID. Detected {} cameras, got id={}", num_cameras, id);
    return nullptr;
  }
  return getInstance().camera_list_[id];
}

std::shared_ptr<Camera> CameraManager::GetCameraBySerialNumber(const std::string& serialnumber) {
  std::lock_guard<std::recursive_mutex> guard(Mutex());
  for (auto& cam : getInstance().camera_list_) {
    if (cam->Info().serialnumber == serialnumber) {
      return cam;
    }
  }
  vci::interceptor::logger()->error("No camera with serial number {}", serialnumber);
  return nullptr;
}

CameraManager::CameraManager(std::optional<std::string> simulatedCamerasConfig) {
  if (simulatedCamerasConfig.has_value()) {
    vci::interceptor::logger()->info("Test Mode: Loading simulated cameras from {}", *simulatedCamerasConfig);
    try {
      RegisterFactory(std::make_unique<SimulatedCameraFactory>(*simulatedCamerasConfig));
    } catch (const std::exception& e) {
      std::cerr << "Failed to register SimulatedCameraFactory: " << e.what() << std::endl;
    }
  } else {
    // not simualted cameras requested. Opeing
    // #ifdef ENABLE_ORBBEC_SUPPORT

    // The Factoires are guarded with enable flags set by src/gibbs/CMakeLists.txt.
    // only create a factory if the nessesary SDK can be found.
#ifdef ENABLE_ORBBEC_SUPPORT
    try {
      RegisterFactory(std::make_unique<OrbbecCameraFactory>());
      vci::interceptor::logger()->debug("Orbbec Camera Factory Registered");
    } catch (const std::exception& e) {
      std::cerr << "Failed to register OrbbecCameraFactory: " << e.what() << std::endl;
    }
#endif

#ifdef ENABLE_XIMEA_SUPPORT
    try {
      RegisterFactory(std::make_unique<XimeaCameraFactory>());
      vci::interceptor::logger()->debug("Ximea Camera Factory Registered");
    } catch (const std::exception& e) {
      std::cerr << "Failed to register XimeaCameraFactory: " << e.what() << std::endl;
    }
#endif

#ifdef ENABLE_BASLER_SUPPORT
    try {
      RegisterFactory(std::make_unique<BaslerCameraFactory>());
      vci::interceptor::logger()->debug("Balser Camera Factory Registered");
    } catch (const std::exception& e) {
      std::cerr << "Failed to register BaslerCameraFactory: " << e.what() << std::endl;
    }
#endif
  }
  for (auto& factory : factories_) {
    vci::interceptor::logger()->debug("{} Factory creating camera...", factory->GetName());
    std::vector<std::shared_ptr<Camera>> cams = factory->CreateCameras();
    for (auto& cam : cams) {
      std::string sn = cam->Info().serialnumber;
      std::string tail = sn.substr(std::max<int>(0, static_cast<int>(sn.size()) - 4));
      char prefix;
      switch (cam->Info().camera_type) {
        case ImageType::Mono:
          prefix = 'M';
          break;
        case ImageType::Color:
          prefix = 'C';
          break;
        case ImageType::Depth:
          prefix = 'D';
          break;
        default:
          prefix = 'X';
          break;
      }
      cam->SetCameraId(prefix + tail);
    }
    camera_list_.insert(camera_list_.end(), cams.begin(), cams.end());
  }
  vci::interceptor::logger()->info("discovered {} cameras", camera_list_.size());
}

void CameraManager::RegisterFactory(std::unique_ptr<CameraFactory> factory) {
  factories_.emplace_back(std::move(factory));
}

std::recursive_mutex& CameraManager::Mutex() {
  static std::recursive_mutex mutex;
  return mutex;
}

#ifdef ENABLE_XIMEA_SUPPORT
XimeaCameraFactory::XimeaCameraFactory() = default;
XimeaCameraFactory::~XimeaCameraFactory() = default;

int XimeaCameraFactory::NumCameras() {
  DWORD num_cameras = 0;
  XI_RETURN stat = xiGetNumberDevices(&num_cameras);
  if (stat != XI_OK) {
    vci::interceptor::logger()->error("XimeaCameraFactory: Failed to get number of devices. xiGetNumberDevices() = {}",
                                      stat);
    return 0;
  }
  return static_cast<int>(num_cameras);
}

std::vector<std::shared_ptr<Camera>> XimeaCameraFactory::CreateCameras() {
  std::vector<std::shared_ptr<Camera>> cameras;
  int num_cameras = NumCameras();
  for (int i = 0; i < num_cameras; ++i) {
    try {
      std::shared_ptr<XimeaCamera> cam = std::make_shared<XimeaCamera>(i);
      cameras.push_back(cam);
    } catch (const std::exception& e) {
      vci::interceptor::logger()->error("XimeaCameraFactory: Failed to initialize camera {}: {}", i, e.what());
    }
  }
  return cameras;
}
#endif  // ENABLE_XIMEA_SUPPORT

SimulatedCameraFactory::SimulatedCameraFactory(const std::string& config_path) {
  std::ifstream file(config_path);
  if (!file.is_open()) {
    vci::interceptor::logger()->error("Simulated camera factory file not found {}", config_path);
    throw std::runtime_error("Simulated camera factory file not found");
  }
  json j;
  file >> j;
  for (const auto& cam : j["cameras"]) {
    SimConfig cfg;
    cfg.serial = cam.at("serialnumber").get<std::string>();
    cfg.width = cam.at("resolution")[0];
    cfg.height = cam.at("resolution")[1];
    std::string type_str = cam.at("type").get<std::string>();
    cfg.type = StringToImageType(type_str);
    if (cfg.type == ImageType::Undefined) {
      throw std::runtime_error("Invalid camera type: " + type_str);
    }

    std::string pixel_layout = cam.at("pixel_layout").get<std::string>();
    cfg.pixel_layout = StringToPixelLayout(pixel_layout);

    // std::cout << "Adding simualted " << type_str << " camera " << cfg.serial << std::endl;
    config_.push_back(cfg);
  }
  file.close();
}

std::vector<std::shared_ptr<Camera>> SimulatedCameraFactory::CreateCameras() {
  std::vector<std::shared_ptr<Camera>> cameras;
  for (size_t i = 0; i < config_.size(); ++i) {
    const auto& cfg = config_[i];
    auto cam = std::make_shared<SimulatedCamera>(static_cast<int>(i), cfg.serial, cfg.width, cfg.height, cfg.type,
                                                 cfg.pixel_layout);
    cameras.push_back(cam);
  }
  return cameras;
}

#ifdef ENABLE_ORBBEC_SUPPORT
OrbbecCameraFactory::OrbbecCameraFactory() = default;

int OrbbecCameraFactory::NumCameras() {
  try {
    ob::Context ctx;
    auto devList = ctx.queryDeviceList();
    const int count = static_cast<int>(devList->deviceCount());
    if (count == 0) {
      vci::interceptor::logger()->warn("OrbbecCameraFactory: Device not found!");
      return 0;
    }
    return count;
  } catch (const ob::Error& e) {
    vci::interceptor::logger()->error("OrbbecCameraFactory: queryDeviceList failed: {} (type {})", e.getMessage(),
                                      static_cast<int>(e.getExceptionType()));
    return 0;
  } catch (const std::exception& e) {
    vci::interceptor::logger()->error("OrbbecCameraFactory: {}", e.what());
    return 0;
  }
}
std::vector<std::shared_ptr<Camera>> OrbbecCameraFactory::CreateCameras() {
  std::vector<std::shared_ptr<Camera>> cameras;
  try {
    ob::Context ctx;
    auto devList = ctx.queryDeviceList();
    const int n = static_cast<int>(devList->deviceCount());
    if (n == 0) {
      vci::interceptor::logger()->warn("OrbbecCameraFactory: no devices found");
      return cameras;
    }
    cameras.reserve(n);
    for (int i = 0; i < n; ++i) {
      try {
        cameras.emplace_back(std::make_shared<OrbbecCamera>(i));
      } catch (const std::exception& e) {
        vci::interceptor::logger()->error("OrbbecCameraFactory: failed to initialize device {}: {}", i, e.what());
      }
    }
  } catch (const ob::Error& e) {
    vci::interceptor::logger()->error("OrbbecCameraFactory: queryDeviceList failed: {} (type {})", e.getMessage(),
                                      static_cast<int>(e.getExceptionType()));
  } catch (const std::exception& e) {
    vci::interceptor::logger()->error("OrbbecCameraFactory: {}", e.what());
  }
  return cameras;
}
#endif  // ENABLE_ORBBEC_SUPPORT

#ifdef ENABLE_BASLER_SUPPORT
BaslerCameraFactory::BaslerCameraFactory() {
  Pylon::PylonInitialize();
}

BaslerCameraFactory::~BaslerCameraFactory() {
  // explicitly destroy Basler cameras before calling PylonTerminate. Otherwise we get a segfault.
  for (auto& weak_camera : created_cameras_) {
    // created_cameras_ is a weak pointer list so the user can delete the cameras without us keeping them alive.
    // So we need to check if the camera still exists before trying to clean it up.
    std::shared_ptr<Camera> camera = weak_camera.lock();
    if (camera) {
      camera->Close();
    }
  }
  Pylon::PylonTerminate();
}

std::vector<std::shared_ptr<Camera>> BaslerCameraFactory::CreateCameras() {
  std::vector<std::shared_ptr<Camera>> cameras;
  Pylon::DeviceInfoList devices;
  Pylon::CTlFactory::GetInstance().EnumerateDevices(devices);
  if (devices.size() == 0) {
    vci::interceptor::logger()->warn("BaslerCameraFactory: no devices found");
    return cameras;
  }
  for (int i = 0; i < devices.size(); i++) {
    try {
      std::shared_ptr<BaslerCamera> cam = std::make_shared<BaslerCamera>(static_cast<int>(i), devices[i]);
      cameras.push_back(cam);
      created_cameras_.push_back(cam);
    } catch (const std::exception& e) {
      vci::interceptor::logger()->error("BaslerCameraFactory: Failed to initialize Balser camera {}: {}", i, e.what());
    }
  }
  return cameras;
}
#endif  // ENABLE_BASLER_SUPPORT