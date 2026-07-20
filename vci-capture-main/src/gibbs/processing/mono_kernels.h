#ifndef VCI_GIBBS_PROCESSING_MONO_KERNELS
#define VCI_GIBBS_PROCESSING_MONO_KERNELS

#include <torch/extension.h>
#include "image.h"

namespace vci {
namespace gibbs {

/**
 * @brief Convert mono image from linear color space to sRGB
 */
GibbsImage& DelinearizeMono(GibbsImage& image);

/**
 * @brief Apply distortion correction to mono image
 */
GibbsImage& ApplyDistortionCorrectionMono(GibbsImage& image, torch::Tensor camera_matrix, torch::Tensor dist_coeffs);

}  // namespace gibbs
}  // namespace vci

#endif  // VCI_GIBBS_PROCESSING_MONO_KERNELS