#ifndef VCI_GIBBS_PROCESSING_COLOR_SUPERKERNEL
#define VCI_GIBBS_PROCESSING_COLOR_SUPERKERNEL

#include <torch/extension.h>
#include "buffer.h"
#include "image.h"

namespace vci {
namespace gibbs {

/**
 * @brief Process a color image
 */
GibbsImage& SuperkernelColor(GibbsImage& image, torch::Tensor white_balance, torch::Tensor colorcorrection,
                             torch::Tensor camera_matrix, torch::Tensor dist_coeffs);

GibbsImage CombinedKernel_Color(torch::Tensor buffer, const EntryInfo* entry_info, torch::Tensor white_balance,
                                torch::Tensor colorcorrection, torch::Tensor camera_matrix, torch::Tensor dist_coeffs);

}  // namespace gibbs
}  // namespace vci

#endif  // VCI_GIBBS_PROCESSING_COLOR_SUPERKERNEL