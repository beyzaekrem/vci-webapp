#ifndef VCI_GIBBS_PROCESSING_COLOR_KERNELS
#define VCI_GIBBS_PROCESSING_COLOR_KERNELS

#include <torch/extension.h>
#include "image.h"

namespace vci {
namespace gibbs {

/**
 * @brief Apply white balance to color image
 */
GibbsImage& ApplyWhiteBalance(GibbsImage& image, torch::Tensor white_balance);

/**
 * @brief Apply white balance to bayer image
 */
GibbsImage& ApplyWhiteBalanceBayer(GibbsImage& image, torch::Tensor white_balance);

/**
 * @brief Apply color correction to color the image
 */
GibbsImage& ApplyColorCorrection(GibbsImage& image, torch::Tensor colorcorrection);

/**
 * @brief Convert color image from linear color space to sRGB
 */
GibbsImage& DelinearizeColor(GibbsImage& image);

/**
 * @brief Apply distortion correction to color image
 */
GibbsImage& ApplyDistortionCorrection(GibbsImage& image, torch::Tensor camera_matrix, torch::Tensor dist_coeffs);

/**
 * @brief Convert To Uint8 image
 */
GibbsImage& ConvertToUInt8(GibbsImage& image);

}  // namespace gibbs
}  // namespace vci

#endif  // VCI_GIBBS_PROCESSING_COLOR_KERNELS