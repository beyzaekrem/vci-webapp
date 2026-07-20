#ifndef VCI_GIBBS_PROCESSING_UTIL_H
#define VCI_GIBBS_PROCESSING_UTIL_H

#include <torch/extension.h>

#include "interceptor/payload.h"

#include "buffer.h"
#include "image.h"

namespace vci {
namespace gibbs {

/**
 * @brief Copy cpu buffer to torch tensor on device
 */
torch::Tensor BufferEntryToDeviceAsync(BufferEntry* buffer_entry, torch::Device device);

/**
 * @brief Copy cpu buffer to torch tensor on device
 */
torch::Tensor BufferToDeviceAsync(char* buffer, long payloadBytes, torch::Device device);

std::shared_ptr<vci::interceptor::Payload> WrapTorchTensor(torch::Tensor data);

}  // namespace gibbs
}  // namespace vci

#endif  // VCI_GIBBS_PROCESSING_UTIL_H
