#include <torch/extension.h>

#include "bayer.h"
#include "codec.h"
#include "packing.h"
#include "util.h"
#include "color_kernels.h"
#include "color_superkernel.h"
#include "mono_kernels.h"
#include "mono_superkernel.h"
#include "flip.h"
#include "zoom.h"

namespace vci {
namespace gibbs {

void processing_bindings(py::module_ &m) {
  // bayer
  m.def("debayer_subsample", &DebayerSubsample);
  m.def("debayer_interpolate", &DebayerLinearInterpolation);

  // codec
  m.def("encode_jpg", &encode_jpg);
  m.def("encode_mask", &encode_mask);

  // packing
  m.def("unpack_buffer", &UnpackBuffer);

  // util
  m.def("WrapTorchTensor", &WrapTorchTensor);

  m.def("buffer_entry_to_device_async", &BufferEntryToDeviceAsync);

  // color kernels
  m.def("apply_white_balance", &ApplyWhiteBalance);
  m.def("apply_white_balance_bayer", &ApplyWhiteBalanceBayer);
  m.def("apply_color_correction", &ApplyColorCorrection);
  m.def("delinearize_color", &DelinearizeColor);
  m.def("undistort_color", &ApplyDistortionCorrection);

  // color superkernel
  m.def("superkernel_color", &SuperkernelColor);


  // mono kernels
  m.def("delinearize_mono", &DelinearizeMono);
  m.def("undistort_mono", &ApplyDistortionCorrectionMono);

  // mono superkernel
  m.def("superkernel_mono", &SuperkernelMono);

  // flip
  m.def("flip_vertical", &flip_vertical);

  // zoom
  m.def("zoom", &zoom);
}

} // namespace gibbs
} // namespace vci
