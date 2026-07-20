#ifndef VCI_GIBBS_PROCESSING_PACKING_H
#define VCI_GIBBS_PROCESSING_PACKING_H

#include <torch/extension.h>

#include "buffer.h"
#include "image.h"

namespace vci {
namespace gibbs {

/**
 * @brief Unpack buffer to float tensor and normalize to [0,1]
 */
GibbsImage UnpackBuffer(torch::Tensor buffer, const EntryInfo* entry_info);

}  // namespace gibbs
}  // namespace vci

#endif  // VCI_GIBBS_PROCESSING_PACKING_H
