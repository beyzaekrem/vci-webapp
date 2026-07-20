#include <pybind11/functional.h>
#include <pybind11/stl.h>
#include <torch/extension.h>

#include <interceptor/logging.h>
#include <fstream>
#include "buffer.h"
#include "camera.h"
#include "camera_manager.h"
#include "codec/video.h"
#include "image.h"
#include "io/cache.h"
#include "tasks/capture.h"
#include "tasks/livestreams.h"
#include "tasks/matting.h"
#include "tasks/record_capture.h"
#include "tasks/ring_buffer_capture.h"

// Submodules
namespace vci {
namespace interceptor {
extern void bindings(py::module_& m);
}  // namespace interceptor
namespace gibbs {
extern void processing_bindings(py::module_& m);
}  // namespace gibbs
}  // namespace vci

namespace py = pybind11;

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
  auto m_interceptor = m.def_submodule("interceptor", "VCI Interceptor");
  vci::interceptor::bindings(m_interceptor);
  vci::interceptor::setup_logger();

  auto entry_info_cls = py::class_<EntryInfo>(m, "EntryInfo");
  auto buffer_entry_cls = py::class_<BufferEntry>(m, "BufferEntry");
  buffer_entry_cls.def("unlock", &BufferEntry::Unlock)
      .def("info", &BufferEntry::Info, py::return_value_policy::reference)
      .def("payload_bytes", &BufferEntry::PayloadBytes)
      .def("to_bytes",
           [](BufferEntry& be) {
             const char* p = be.Buffer();
             const size_t n = be.PayloadBytes();
             if (!p || n == 0) return py::bytes();
             return py::bytes(p, n);
           })
      .def("write_to_path", [](BufferEntry& be, const std::string& path) {
        std::ofstream ofs(path, std::ios::binary);
        if (!ofs) throw std::runtime_error("failed to open output file: " + path);
        be.WriteTo(ofs);
        ofs.close();
      });

  py::register_exception<BufferTimeout>(m, "BufferTimeout");
  py::register_exception<TransportInterrupted>(m, "TransportInterrupted");

  py::register_exception<CameraParameterError>(m, "CameraParameterError");

  entry_info_cls
      .def_readwrite("image_type", &EntryInfo::image_type)  // returns an ImageType
      .def_readwrite("packed", &EntryInfo::packed)
      .def_readwrite("bit_depth", &EntryInfo::bit_depth)
      .def_readwrite("height", &EntryInfo::height)
      .def_readwrite("width", &EntryInfo::width)
      .def_readwrite("pixel_layout", &EntryInfo::pixel_layout)
      .def_readwrite("timestamp_us", &EntryInfo::timestamp_us)
      .def_readwrite("frame_number", &EntryInfo::frame_number)
      .def_readwrite("optional_data", &EntryInfo::optional_data);

  buffer_entry_cls.def("unlock", &BufferEntry::Unlock)
      .def("info", &BufferEntry::Info, py::return_value_policy::reference)
      .def("payload_bytes", &BufferEntry::PayloadBytes)
      .def("write_to_path",
           [](BufferEntry& b, const std::string& path) {
             std::ofstream ofs(path, std::ios::binary);
             if (!ofs) throw std::runtime_error("failed to open: " + path);
             b.WriteTo(ofs);
             ofs.close();
           })
      .def("to_bytes", [](BufferEntry& b) {
        const char* p = b.Buffer();
        const size_t n = b.PayloadBytes();
        if (!p || n == 0) return py::bytes();
        return py::bytes(p, n);
      });

  auto raw_image_cls =
      py::class_<GibbsImage>(m, "GibbsImage", "Wrapped tensor. Contains meta information for downstream processing");
  raw_image_cls
      .def(py::init<torch::Tensor, std::string, ImageType, PixelLayout>(), py::arg("tensor"), py::arg("camera_id"),
           py::arg("image_type"), py::arg("pixel_layout"))
      .def("__repr__", &GibbsImage::repr)
      .def_readwrite("pixels", &GibbsImage::pixels)
      .def_readwrite("pixel_layout", &GibbsImage::pixel_layout)
      .def_readwrite("camera_id", &GibbsImage::camera_id)
      .def_readwrite("image_type", &GibbsImage::image_type)
      .def_readwrite("data_category", &GibbsImage::data_category)

      .def("cuda", &GibbsImage::cuda, "Moves the pixel data to cuda", py::arg("non_blocking") = false)
      .def("cpu", &GibbsImage::cpu, "Moves the pixel data to cpu", py::arg("non_blocking") = false)
      .def("release", &GibbsImage::release, "Clears data and releases Memory")
      .def("from_legacy", &GibbsImage::from_legacy)
      .def_property_readonly("device", &GibbsImage::device)
      .def_property_readonly("defined", &GibbsImage::defined)
      .def_property_readonly("shape",
                             [](const GibbsImage& self) {
                               // Convert C++ sizes to a Python-friendly tuple
                               return py::tuple(py::cast(self.shape()));
                             })
      .def_property_readonly("ndim", &GibbsImage::ndim)
      .def_property_readonly("dtype", &GibbsImage::scalar_type)
      .def("is_bayer", &GibbsImage::is_bayer,
           "Returns true if the image has a bayer pixel_layout [RGGB, BGGR, GRBG, GBRG] and pixel-data is "
           "2-dimensional [H, W]")
      .def("is_mono", &GibbsImage::is_mono,
           "Returns true if the pixel_layout is Mono and image has shape: [1, H, W] or [H, W]")
      .def("is_rgb", &GibbsImage::is_rgb, "Returns ture if the pixel_layout is RGB and has shape [3, H, W]")
      .def("is_mono_ndim", &GibbsImage::is_mono_ndim,
           "Returns true if the image-data is 2-dimenstional [H, W]. Typically the pixel_layout could Mono or a bayer "
           "pattern.")
      .def("clone", &GibbsImage::clone, "Returns a deep copy of the image and its metadata")
      .def("get_mattable_tensor", &GibbsImage::get_mattable_tensor,
           "Returns a mattable, copy of the pixels with shape [1, 3, H, W]")

      .def("save_to_pth", &GibbsImage::save_to_pth,
           "Saves the GibbsImage into a torch archive, perserving its meta info.")
      .def("load_from_pth", &GibbsImage::load_from_pth,
           "Loads GibbsImage from torch archive, recovering tis meta info.");

  py::class_<EncodedImage>(m, "EncodedImage")
      // Constructor: Allows creating from Python for testing
      .def(py::init<torch::Tensor, const GibbsImage&, std::string>(), py::arg("data"), py::arg("source"),
           py::arg("format"))

      // Properties (Mapped to your ImageInfo dataclass fields)
      .def_readwrite("data", &EncodedImage::data)
      .def_readwrite("camera_id", &EncodedImage::camera_id)
      .def_readwrite("data_category", &EncodedImage::data_category)
      .def_readwrite("image_type", &EncodedImage::image_type)
      .def_readwrite("shape", &EncodedImage::shape)
      .def_readwrite("format", &EncodedImage::format)

      .def("cuda", &EncodedImage::cuda, "Moves the pixel data to cuda", py::arg("non_blocking") = false)
      .def("cpu", &EncodedImage::cpu, "Moves the pixel data to cpu", py::arg("non_blocking") = false)

      // Conversion to Dict for API Payloads
      .def("to_dict", &EncodedImage::to_dict, "Converts metadata into a dictionary")
      .def("__repr__", &EncodedImage::repr);

  py::enum_<ImageType>(m, "ImageType")
      .value("Color", ImageType::Color)
      .value("Mono", ImageType::Mono)
      .value("Depth", ImageType::Depth)
      .value("Undefined", ImageType::Undefined)
      .export_values();
  py::enum_<DataCategory>(m, "DataCategory")
      .value("Image", DataCategory::Image)
      .value("Matte", DataCategory::Matte)
      .value("Background", DataCategory::Background)
      .value("Mean", DataCategory::Mean)
      .value("Undefined", DataCategory::Undefined)
      .export_values();
  py::enum_<TriggerSource>(m, "TriggerSource")
      .value("Hardware", TriggerSource::Hardware)
      .value("Software", TriggerSource::Software)
      .export_values();

  auto py_pixel_layout = py::enum_<PixelLayout>(m, "PixelLayout")
                             .value("RGGB", PixelLayout::RGGB)
                             .value("BGGR", PixelLayout::BGGR)
                             .value("GBRG", PixelLayout::GBRG)
                             .value("GRBG", PixelLayout::GRBG)
                             .value("RGB", PixelLayout::RGB)
                             .value("BGR", PixelLayout::BGR)
                             .value("Mono", PixelLayout::Mono)
                             .value("Undefined", PixelLayout::Undefined)
                             .export_values()
                             .def(py::init([](py::object arg) {
                               if (py::isinstance<py::str>(arg)) {
                                 return StringToPixelLayout(arg.cast<std::string>());
                               }
                               if (py::isinstance<py::int_>(arg)) {
                                 return static_cast<PixelLayout>(arg.cast<int>());
                               }
                               throw py::type_error("PixelLayout constructor accepts str or int");
                             }));
  py_pixel_layout.def_property_readonly_static("all", [](py::object /* self */) {
    return std::vector<PixelLayout>{PixelLayout::RGGB, PixelLayout::BGGR, PixelLayout::GBRG, PixelLayout::GRBG,
                                    PixelLayout::RGB,  PixelLayout::BGR,  PixelLayout::Mono, PixelLayout::Undefined};
  });

  py::class_<CameraInfo, std::shared_ptr<CameraInfo>>(m, "CameraInfo")
      .def_readonly("camera_id", &CameraInfo::camera_id)
      .def_readonly("camera_type", &CameraInfo::camera_type)
      .def_readonly("manufacturer", &CameraInfo::manufacturer)
      .def_readonly("device_model_name", &CameraInfo::device_model_name)
      .def_readonly("capture_card_index", &CameraInfo::capture_card_index)
      .def_readonly("serialnumber", &CameraInfo::serialnumber);

  py::class_<Camera, std::shared_ptr<Camera>>(m, "Camera")
      .def("info", &Camera::Info)
      .def_property_readonly("camera_id", [](const Camera& self) { return self.Info().camera_id; })
      .def_property_readonly("camera_type", [](const Camera& self) { return self.Info().camera_type; })
      .def_property_readonly("manufacturer", [](const Camera& self) { return self.Info().manufacturer; })
      .def_property_readonly("serialnumber", [](const Camera& self) { return self.Info().serialnumber; })
      .def("to_dict", &Camera::to_dict, "Returns metadata and current status as dict")
      // state
      .def("open", &Camera::Open, "Initializes the hardware connection.")
      .def("close", &Camera::Close, "Closes the hardware connection.")
      .def("is_open", &Camera::IsOpen, "returns true if the hardware connection is open.")
      .def("start", &Camera::Start,
           "Starts the camera. When started the camera, a trigger signal capuse the camera to capture and image to its "
           "internal buffer. The image cam be retrieved from the buffer by calling caputre_next, either directly or "
           "via gibbs.tasks.")
      .def("stop", &Camera::Stop, "Stops the camera. Image triggers are ignored and images in buffer are flushed.")
      .def("is_running", &Camera::IsRunning, "returns true if the cameras is listening for triggers to caputre images.")
      // triggering
      .def("set_trigger_source", &Camera::SetTriggerSouce,
           "The trigger source indicates which the trigger signals will be accepted. Image can either be triggered by "
           "an external hardware singal generator or by the camera itself (aka sofware trigger). When setting to "
           "software trigger you must use the other camera methods to trigger images.")
      .def_property_readonly("trigger_source", &Camera::GetTriggerSource,
                             "The aktive trigger source. Software or Hardware.")
      .def("perform_software_trigger", &Camera::PerformSoftwareTrigger,
           "When trigger source is set to software, this triggers a single image to be captured to buffer.")
      .def("set_software_fps", &Camera::SetSoftwareFPS,
           "When trigger source is set to software, this sets the frame rate for the auto trigger.")
      .def("start_software_auto_trigger", &Camera::StartSoftwareAutoTrigger,
           "Starts continously triggering via software trigger. Stopping the cameras, stops the auto trigger.")
      .def("stop_software_auto_trigger", &Camera::StopSoftwareAutoTrigger,
           "Stops continously triggering via software trigger.")
      // get image
      .def("capture_next", &Camera::CaptureNext, py::return_value_policy::take_ownership,
           "Retrives an image from the cameras internal buffer. Raises a BufferTimeout if no images have been "
           "triggered.")

      // set parameters
      .def("set_default_parameters", &Camera::SetDefaultParameters,
           "Sets the default camera settings - bit depth, image format, trigger source, etc.")
      .def("set_primary", &Camera::SetPrimary)
      .def("set_secondary", &Camera::SetSecondary)

      .def("set_exposure", &Camera::SetExposure)
      .def("set_gain", &Camera::SetGain)
      .def("get_exposure", &Camera::GetExposure)
      .def("get_gain", &Camera::GetGain)
      .def("get_parameter_int", &Camera::GetParameterInt)
      .def("set_parameter_int", &Camera::SetParameterInt)
      .def("get_parameter_float", &Camera::GetParameterFloat)
      .def("set_parameter_float", &Camera::SetParameterFloat)
      .def("get_parameter_string", &Camera::GetParameterString)
      .def("try_get_parameter", &Camera::TryGetParameter)
      .def("try_set_parameter", &Camera::TrySetParameter)

      .def("get_manifest", &Camera::GetManifest,
           "Returns a dictioanry manifest describing camera paramters supported by web-app")

      .def("set_bit_depth", &Camera::SetBitDepth, "Set bit depth of output, sensor and enables/disable packing",
           py::arg("sensor_bit_depth"), py::arg("out_bit_depth") = 0, py::arg("packing") = true);

  // CameraManager
  py::class_<CameraManager>(m, "CameraManager")
      .def("configure_simulation", &CameraManager::ConfigureSimulation)
      .def("disable_api_logging", &CameraManager::DisableApiLogging)
      .def("num_cameras", &CameraManager::NumCameras)
      .def("get_camera_by_id", &CameraManager::GetCameraById);

  // ---- Codec / IO / Tasks / Processing ----

  auto m_codec = m.def_submodule("codec", "Encoding and Decoding");
  m_codec.def("encode_video", vci::gibbs::encode_video);

  auto m_io = m.def_submodule("io", "Input/Output Module");
  py::class_<Cache>(m_io, "Cache");
  py::class_<CacheReader, std::shared_ptr<CacheReader>>(m_io, "CacheReader")
      .def(py::init<const std::string&>(), py::arg("cache_path"))
      .def("load_frame", &CacheReader::LoadFrame, py::arg("camera_idx"), py::arg("frame_index"))
      .def_property_readonly("frame_count", &CacheReader::FrameCount)
      .def_property_readonly("camera_ids", &CacheReader::CameraIds)
      .def_property_readonly("fps", &CacheReader::GetFps, "meta info: frames per second or replay speed.");

  py::class_<CacheWriter, std::shared_ptr<CacheWriter>>(m_io, "CacheWriter")
      .def(py::init<const std::string, const std::vector<std::string>, const std::vector<std::string>>(),
           py::arg("cache_path"), py::arg("dump_base_paths"), py::arg("camera_ids"))
      .def_property_readonly("fps", &CacheWriter::GetFps, "meta info: frames per second or replay speed.")
      .def("set_fps", &CacheWriter::SetFps);

  auto m_tasks = m.def_submodule("tasks", "Tasks Module");
  m_tasks.def("capture_to_disk_dump", CaptureToDiskDump);
  m_tasks.def("capture_all", CaptureAll, py::return_value_policy::reference);

  auto m_processing = m.def_submodule("processing", "VCI Gibbs Processing");
  vci::gibbs::processing_bindings(m_processing);

  auto matting_out_cls = py::class_<vci::gibbs::MattingOut>(m_tasks, "MattingOut");
  matting_out_cls.def_readwrite("mask", &vci::gibbs::MattingOut::mask)
      .def_readwrite("foreground", &vci::gibbs::MattingOut::foreground);

  auto matting_cls = py::class_<vci::gibbs::Matting, std::shared_ptr<vci::gibbs::Matting>>(m_tasks, "Matting");
  matting_cls.def(py::init<std::string>(), py::arg("pt_path"))
      .def("dtype", &vci::gibbs::Matting::dtype)
      .def("forward", &vci::gibbs::Matting::forward, py::arg("foreground"), py::arg("background"))
      .def("__call__", &vci::gibbs::Matting::forward, py::arg("foreground"), py::arg("background"))  // Add this line;
      .def("infer", &vci::gibbs::Matting::infer, py::arg("foreground"), py::arg("background"));

  auto ring_buffer_cls = py::class_<RingBuffer>(m_tasks, "RingBuffer");
  ring_buffer_cls
      .def(py::init<std::vector<std::shared_ptr<Camera>>, std::vector<std::vector<torch::Tensor>>, std::vector<int>,
                    std::shared_ptr<vci::gibbs::Matting>, std::vector<GibbsImage>, float>(),
           py::arg("cameras"), py::arg("calibration_data"), py::arg("rotations"), py::arg("matting_network"),
           py::arg("background_images"), py::arg("threshold"))
      .def("Run", &RingBuffer::Run)
      .def("Stop", &RingBuffer::Stop)
      .def("LastFrame", &RingBuffer::LastFrame)
      .def("GetMasks", &RingBuffer::GetMasks)
      .def("GetImages", &RingBuffer::GetImages)
      .def("SetThreshold", &RingBuffer::SetThreshold)
      .def("isRunning", &RingBuffer::IsRunning);

  auto record_capture_cls = py::class_<RecordCapture>(m_tasks, "RecordCapture");
  record_capture_cls
      .def(py::init<std::vector<std::shared_ptr<Camera>>, std::shared_ptr<CacheWriter>>(), py::arg("cameras"),
           py::arg("cache_writer"))
      .def("Run", &RecordCapture::Run)
      .def("Stop", &RecordCapture::Stop)
      .def("SquenceLength", &RecordCapture::SquenceLength)
      .def("isRunning", &RecordCapture::IsRunning)
      .def("SetSkipFrames", &RecordCapture::SetSkipFrames)
      .def("SkipNextFrame", &RecordCapture::SkipNextFrame);

  py::class_<ZoomParams>(m_tasks, "ZoomParams")
      .def(py::init<float, float, std::pair<int, int>, float>(), py::arg("center_x"), py::arg("center_y"),
           py::arg("client_size"), py::arg("zoom_factor"))
      .def_readwrite("center_x", &ZoomParams::center_x)
      .def_readwrite("center_y", &ZoomParams::center_y)
      .def_readwrite("client_size", &ZoomParams::client_size)
      .def_readwrite("zoom_factor", &ZoomParams::zoom_factor);

  py::class_<Livestream, std::shared_ptr<Livestream>>(m_tasks, "Livestream")
      .def(py::init<std::string, int, const ZoomParams&, size_t>(), py::arg("id"), py::arg("camera_idx"),
           py::arg("params"), py::arg("buffer_size") = 50)
      .def("GetImage", &Livestream::GetImage)
      .def("SetParams", &Livestream::SetParams, py::arg("params"))
      .def_property_readonly("Params", &Livestream::Params, py::return_value_policy::reference)
      .def("CameraIndex", &Livestream::CameraIndex)
      .def("ID", &Livestream::ID);

  py::class_<LivestreamPipeline>(m_tasks, "LivestreamPipeline")
      .def(py::init<std::vector<std::shared_ptr<Camera>>, std::vector<std::shared_ptr<Livestream>>>(),
           py::arg("cameras"), py::arg("livestreams"))
      .def("Run", &LivestreamPipeline::Run)
      .def("Stop", &LivestreamPipeline::Stop)
      .def_property_readonly("is_running", &LivestreamPipeline::IsRunning)
      .def("AddLivestream", &LivestreamPipeline::AddLivestream, py::arg("livestream"))
      .def("RemoveLivestream", &LivestreamPipeline::RemoveLivestream, py::arg("id"))
      .def("GetLivestream", &LivestreamPipeline::GetLivestream, py::arg("id"))
      .def("GetLivestreams", &LivestreamPipeline::GetLivestreams);
}
