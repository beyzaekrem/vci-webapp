#include <cuda.h>
#include <cuda_runtime.h>

#include <ATen/cuda/ApplyGridUtils.cuh>
#include "flip.h"

namespace vci {
namespace gibbs {

template <typename scalar_t>
__global__ void flip_vertical_kernel(const torch::PackedTensorAccessor32<scalar_t, 3, torch::RestrictPtrTraits> input,
                                     torch::PackedTensorAccessor32<scalar_t, 3, torch::RestrictPtrTraits> output,
                                     const int height, const int width) {
  // Total number of elements (channels * height * width)
  const int total = output.size(0) * height * width;
  int index = blockIdx.x * blockDim.x + threadIdx.x;

  if (index < total) {
    // Calculate the 3D indices from the linear index
    int j = index % width;
    int i = (index / width) % height;
    int c = index / (width * height);
    // Vertical flip: reverse the row index
    output[c][i][j] = input[c][height - 1 - i][j];
  }
}

torch::Tensor flip_vertical(torch::Tensor input) {
  // Ensure the input is a CUDA tensor and has 3 dimensions [C, H, W]
  TORCH_CHECK(input.is_cuda(), "flip_vertical: input must be a CUDA tensor ");
  TORCH_CHECK(input.dim() == 3, "flip_vertical: input must be a 3D tensor [C, H, W]");

  const int channels = input.size(0);
  const int height = input.size(1);
  const int width = input.size(2);

  // Allocate output tensor with the same options as input
  auto output = torch::empty_like(input);

  const int total = channels * height * width;
  // Get CUDA launch configuration
  dim3 threads = at::cuda::getApplyBlock();
  dim3 blocks;
  at::cuda::getApplyGrid(total, blocks, input.device().index());

  // Dispatch based on the data type of the input
  AT_DISPATCH_FLOATING_TYPES_AND_HALF(input.scalar_type(), "flip_vertical", ([&] {
                                        flip_vertical_kernel<scalar_t><<<blocks, threads>>>(
                                            input.packed_accessor32<scalar_t, 3, torch::RestrictPtrTraits>(),
                                            output.packed_accessor32<scalar_t, 3, torch::RestrictPtrTraits>(), height,
                                            width);
                                      }));

  return output;
}

}  // namespace gibbs
}  // namespace vci
