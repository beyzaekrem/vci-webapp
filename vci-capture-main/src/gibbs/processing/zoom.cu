#include <cuda.h>
#include <cuda_runtime.h>
#include <ATen/cuda/ApplyGridUtils.cuh>
#include "zoom.h"

namespace vci {
namespace gibbs {

// CUDA kernel for zooming with nearest-neighbor interpolation.
template <typename scalar_t>
__global__ void zoom_kernel(const torch::PackedTensorAccessor32<scalar_t, 3, torch::RestrictPtrTraits> input,
                            torch::PackedTensorAccessor32<scalar_t, 3, torch::RestrictPtrTraits> output,
                            const int input_height, const int input_width, const int output_height,
                            const int output_width, const float center_x, const float center_y,
                            const float zoom_factor) {
  // Compute the ROI in the input image.
  // The ROI size is defined as the output size scaled down by the zoom factor.
  float roi_w = output_width / zoom_factor;
  float roi_h = output_height / zoom_factor;
  // The top-left corner of the ROI in the input image.
  float roi_left = center_x - roi_w / 2.0f;
  float roi_top = center_y - roi_h / 2.0f;
  // Scale factors to map output pixel coordinates to the ROI.
  float scale_x = roi_w / output_width;
  float scale_y = roi_h / output_height;

  // Total number of output elements (channels * height * width)
  const int total = output.size(0) * output_height * output_width;
  int index = blockIdx.x * blockDim.x + threadIdx.x;

  if (index < total) {
    // Compute channel, row, and column indices for the output pixel.
    int j = index % output_width;
    int i = (index / output_width) % output_height;
    int c = index / (output_width * output_height);

    // Map the output pixel (i,j) to a coordinate in the input ROI.
    // The formula uses the "center" of the pixel.
    float in_x_float = roi_left + (j + 0.5f) * scale_x - 0.5f;
    float in_y_float = roi_top + (i + 0.5f) * scale_y - 0.5f;
    int in_x = roundf(in_x_float);
    int in_y = roundf(in_y_float);

    // If the computed coordinate is within the input image, sample the pixel.
    // Otherwise, set the output pixel to 0 (black border).
    if (in_x >= 0 && in_x < input_width && in_y >= 0 && in_y < input_height) {
      output[c][i][j] = input[c][in_y][in_x];
    } else {
      output[c][i][j] = static_cast<scalar_t>(0);
    }
  }
}

/**
 * Automatic White Balance (AWB) function via Shades of Gray.
 */
torch::Tensor awb_shades_of_gray(torch::Tensor input, double p = 4.0, double eps = 1e-6) {
  TORCH_CHECK(input.is_cuda(), "awb_shades_of_gray: input must be CUDA");
  TORCH_CHECK(input.dim() == 3, "awb_shades_of_gray: input must be [C,H,W]");

  auto sizes = input.sizes();
  int64_t C = sizes[0], H = sizes[1], W = sizes[2];

  auto abs_pow = input.abs().pow(p);

  // Average over spatial dims
  auto mean_pow = abs_pow.view({C, -1}).mean(/*dim=*/1, /*keepdim=*/false).add(eps);

  // Minkowski norm
  auto norm = mean_pow.pow(1.0 / p).view({C, 1, 1});

  // Gray level = average of channel norms
  auto gray = norm.mean();

  // Compute per-channel gains and apply
  auto gains = gray / norm;
  auto output = input * gains;

  return output;
}

// Host function to launch the zoom kernel.
// 'client_size' is a pair (output_width, output_height)
GibbsImage zoom(GibbsImage input, float center_x, float center_y, std::pair<int, int> client_size, float zoom_factor,
                bool copy) {
  TORCH_CHECK(input.is_cuda(), "zoom: input must be a CUDA tensor ", input.repr());
  TORCH_CHECK(input.ndim() == 3, "zoom: input must be a 3D tensor [C, H, W] ", input.repr());

  const int channels = input.size(0);
  const int input_height = input.size(1);
  const int input_width = input.size(2);
  const int output_width = client_size.first;
  const int output_height = client_size.second;

  // Allocate the output tensor with the same options as the input.
  auto output = torch::empty({channels, output_height, output_width}, input.pixels.options());

  const int total = channels * output_height * output_width;
  // Get CUDA launch configuration.
  dim3 threads = at::cuda::getApplyBlock();
  dim3 blocks;
  at::cuda::getApplyGrid(total, blocks, input.device().index());

  // apply awb
  // input = awb_shades_of_gray(input);

  // Dispatch kernel based on the input data type.
  AT_DISPATCH_FLOATING_TYPES_AND_HALF(input.scalar_type(), "zoom", ([&] {
                                        zoom_kernel<scalar_t><<<blocks, threads>>>(
                                            input.pixels.packed_accessor32<scalar_t, 3, torch::RestrictPtrTraits>(),
                                            output.packed_accessor32<scalar_t, 3, torch::RestrictPtrTraits>(),
                                            input_height, input_width, output_height, output_width, center_x, center_y,
                                            zoom_factor);
                                      }));

  if (copy) {
    GibbsImage result = input.clone_with_pixels(output);
    return result;
  } else {
    input.pixels = output;
    return input;
  }
}

}  // namespace gibbs
}  // namespace vci
