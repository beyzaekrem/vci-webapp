#include "util.h"

#include <cuda.h>
#include <cuda_runtime.h>
#include <ATen/cuda/CUDAContext.h>

namespace vci {
namespace gibbs {

torch::Tensor BufferEntryToDeviceAsync(BufferEntry* buffer_entry, torch::Device device) {
  // Create empty tensor
  torch::Tensor tensor = torch::empty(
    {static_cast<long>(buffer_entry->PayloadBytes())},
    torch::TensorOptions()
      .dtype(torch::kUInt8)
      .device(device));
  // Perform the asynchronous memory copy from the CPU to the tensor
  at::cuda::CUDAStream current_stream = at::cuda::getCurrentCUDAStream(device.index());
  cudaMemcpyAsync(
    tensor.data_ptr<unsigned char>(),
    buffer_entry->Buffer(),
    buffer_entry->PayloadBytes(),
    cudaMemcpyHostToDevice, current_stream.stream());
  // Return the created tensor
  return tensor;
}

torch::Tensor BufferToDeviceAsync(char* buffer, long payloadBytes, torch::Device device){
    // Create empty tensor
  torch::Tensor tensor = torch::empty(
    {payloadBytes},
    torch::TensorOptions()
      .dtype(torch::kUInt8)
      .device(device));
  // Perform the asynchronous memory copy from the CPU to the tensor
  at::cuda::CUDAStream current_stream = at::cuda::getCurrentCUDAStream(device.index());
  cudaMemcpyAsync(
    tensor.data_ptr<unsigned char>(),
    buffer,
    payloadBytes,
    cudaMemcpyHostToDevice, current_stream.stream());
  // Return the created tensor
  return tensor;
}

class TorchPayload : public vci::interceptor::Payload {
public:
  TorchPayload(torch::Tensor data)
    : Payload(
      reinterpret_cast<unsigned char*>(data.data_ptr()),
      data.numel() * data.element_size())
    , data_(data)  {
  }

private:
  torch::Tensor data_;
};

std::shared_ptr<vci::interceptor::Payload> WrapTorchTensor(torch::Tensor data) {
  return std::make_shared<TorchPayload>(data);
}

} // namespace gibbs
} // namespace vci
