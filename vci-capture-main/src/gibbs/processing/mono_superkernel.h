#ifndef VCI_GIBBS_PROCESSING_SUPERKERNEL_MONO
#define VCI_GIBBS_PROCESSING_SUPERKERNEL_MONO

#include <torch/extension.h>
#include "buffer.h"
#include "image.h"

namespace vci {
namespace gibbs {

/**
 * @brief Apply processing to mono images
 */
GibbsImage& SuperkernelMono(GibbsImage& image, torch::Tensor camera_matrix, torch::Tensor dist_coeffs);

GibbsImage CombinedKernel_Mono(torch::Tensor buffer, const EntryInfo* entry_info, torch::Tensor camera_matrix,
                               torch::Tensor dist_coeffs);
}  // namespace gibbs
}  // namespace vci

#endif  // VCI_GIBBS_PROCESSING_SUPERKERNEL_MONO