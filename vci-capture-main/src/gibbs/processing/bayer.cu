#include "bayer.h"

#include <cuda.h>
#include <cuda_runtime.h>

#include <ATen/cuda/ApplyGridUtils.cuh>

namespace vci {
namespace gibbs {

template <PixelLayout PATTERN, typename scalar_t>
__global__ void debayer_subsample_kernel(
    const torch::PackedTensorAccessor32<scalar_t, 2, torch::RestrictPtrTraits> image,
    torch::PackedTensorAccessor32<scalar_t, 3, torch::RestrictPtrTraits> image_out) {
  int index = blockIdx.x * blockDim.x + threadIdx.x;
  int stride = blockDim.x * gridDim.x;
  int total_elements = image_out.size(1) * image_out.size(2);
  for (int i = index; i < total_elements; i += stride) {
    // iterate over the pixel of output image (3 channel)
    int row = i / image_out.size(2);
    int col = i % image_out.size(2);

    // we take a 2x2 patch of mono pixels (in the input image) and merge then into one (output) color pixel.
    //  patch:
    //      [p00, p01]
    //      [P10, p11]
    // row*2 and col*2 points to the upper left pixel of the 2x2 block.
    // we do +1 to move right/down to collect the other pixels.
    // Extract the 2x2 quad
    const scalar_t p00 = image[row * 2][col * 2];
    const scalar_t p01 = image[row * 2][col * 2 + 1];
    const scalar_t p10 = image[row * 2 + 1][col * 2];
    const scalar_t p11 = image[row * 2 + 1][col * 2 + 1];

    // now we assign the red green and blue pixels according to the bayer PATTERN - Green pixels are merged.
    if (PATTERN == PixelLayout::RGGB) {
      // [R G]  p00 p01
      // [G B]  p10 p11
      image_out[0][row][col] = p00;                 // R
      image_out[1][row][col] = 0.5f * (p01 + p10);  // G
      image_out[2][row][col] = p11;                 // B
    } else if (PATTERN == PixelLayout::BGGR) {
      // [B G]  p00 p01
      // [G R]  p10 p11
      image_out[0][row][col] = p11;                 // R
      image_out[1][row][col] = 0.5f * (p01 + p10);  // G
      image_out[2][row][col] = p00;                 // B
    } else if (PATTERN == PixelLayout::GRBG) {
      // [G R]  p00 p01
      // [B G]  p10 p11
      image_out[0][row][col] = p01;                 // R
      image_out[1][row][col] = 0.5f * (p00 + p11);  // G
      image_out[2][row][col] = p10;                 // B
    } else if (PATTERN == PixelLayout::GBRG) {
      // [G B]  p00 p01
      // [R G]  p10 p11
      image_out[0][row][col] = p10;                 // R
      image_out[1][row][col] = 0.5f * (p00 + p11);  // G
      image_out[2][row][col] = p01;                 // B
    }
    // out: 3 channel rgb image
  }
}

GibbsImage& DebayerSubsample(GibbsImage& image) {
  TORCH_CHECK(image.is_bayer(),
              "GibbsImage must have a bayer pattern as PixelLayout to perform DebayerSubsample " + image.repr());

  // Create empty tensor
  torch::Tensor image_out = torch::empty({3, image.size(0) / 2, image.size(1) / 2},
                                         torch::TensorOptions().dtype(image.dtype()).device(image.device()));

  at::DeviceGuard guard(image.device());
  dim3 threads = at::cuda::getApplyBlock();
  dim3 blocks;
  at::cuda::getApplyGrid(image_out.numel() / 3, blocks, image.device().index());

  // Launch the kernel with type dispatch
  AT_DISPATCH_FLOATING_TYPES_AND_HALF(
      image.scalar_type(), "debayer_subsample_kernel", ([&] {
        auto input_accessor = image.pixels.packed_accessor32<scalar_t, 2, torch::RestrictPtrTraits>();
        auto output_accessor = image_out.packed_accessor32<scalar_t, 3, torch::RestrictPtrTraits>();

        switch (image.pixel_layout) {
          case PixelLayout::RGGB:
            debayer_subsample_kernel<PixelLayout::RGGB, scalar_t><<<blocks, threads>>>(input_accessor, output_accessor);
            break;
          case PixelLayout::BGGR:
            debayer_subsample_kernel<PixelLayout::BGGR, scalar_t><<<blocks, threads>>>(input_accessor, output_accessor);
            break;
          case PixelLayout::GBRG:
            debayer_subsample_kernel<PixelLayout::GBRG, scalar_t><<<blocks, threads>>>(input_accessor, output_accessor);
            break;
          case PixelLayout::GRBG:
            debayer_subsample_kernel<PixelLayout::GRBG, scalar_t><<<blocks, threads>>>(input_accessor, output_accessor);
            break;

          default:
            TORCH_CHECK(false, "Unsupported PixelLayout: ", (int)image.pixel_layout);
        }
      }));
  image.pixels = image_out;
  image.pixel_layout = PixelLayout::RGB;
  return image;
}

enum PixelType { PIX_RED, PIX_BLUE, PIX_GREEN_RED_ROW, PIX_GREEN_BLUE_ROW };

template <PixelLayout PATTERN, typename scalar_t>
__global__ void debayer_linear_interpolation_kernel(
    const torch::PackedTensorAccessor32<scalar_t, 2, torch::RestrictPtrTraits> image,
    torch::PackedTensorAccessor32<scalar_t, 3, torch::RestrictPtrTraits> image_out, int width, int height) {
  int x = blockIdx.x * blockDim.x + threadIdx.x;
  int y = blockIdx.y * blockDim.y + threadIdx.y;

  if (x >= width || y >= height) return;

  // --- 1. Memory-Safe Clamped Indices ---
  int xp = max(0, x - 1);
  int xn = min(width - 1, x + 1);
  int yp = max(0, y - 1);
  int yn = min(height - 1, y + 1);

  bool has_u = (y > 0), has_d = (y < height - 1);
  bool has_l = (x > 0), has_r = (x < width - 1);

  // --- 2. Pattern Mapping (Resolved at Compile Time) ---
  PixelType p_type;
  bool is_even_y = (y % 2 == 0);
  bool is_even_x = (x % 2 == 0);

  // 1. Map coordinates to a PixelType based on the Template Pattern
  if (PATTERN == PixelLayout::RGGB) {
    if (is_even_y && is_even_x)
      p_type = PIX_RED;
    else if (is_even_y && !is_even_x)
      p_type = PIX_GREEN_RED_ROW;
    else if (!is_even_y && is_even_x)
      p_type = PIX_GREEN_BLUE_ROW;
    else
      p_type = PIX_BLUE;
  } else if (PATTERN == PixelLayout::BGGR) {
    if (is_even_y && is_even_x)
      p_type = PIX_BLUE;
    else if (is_even_y && !is_even_x)
      p_type = PIX_GREEN_BLUE_ROW;
    else if (!is_even_y && is_even_x)
      p_type = PIX_GREEN_RED_ROW;
    else
      p_type = PIX_RED;
  } else if (PATTERN == PixelLayout::GRBG) {
    if (is_even_y && is_even_x)
      p_type = PIX_GREEN_RED_ROW;
    else if (is_even_y && !is_even_x)
      p_type = PIX_RED;
    else if (!is_even_y && is_even_x)
      p_type = PIX_BLUE;
    else
      p_type = PIX_GREEN_BLUE_ROW;
  } else if (PATTERN == PixelLayout::GBRG) {
    if (is_even_y && is_even_x)
      p_type = PIX_GREEN_BLUE_ROW;
    else if (is_even_y && !is_even_x)
      p_type = PIX_BLUE;
    else if (!is_even_y && is_even_x)
      p_type = PIX_RED;
    else
      p_type = PIX_GREEN_RED_ROW;
  }
  // The template compiles a separate kernel for each dispatched PixelLayout PATTERN.
  // each version has its PATTERN if/else optiminied out.

  scalar_t r = 0, g = 0, b = 0, n = 0;

  // --- 3. Unified Interpolation Logic ---
  if (p_type == PIX_RED || p_type == PIX_BLUE) {
    // We are at a Pure Color site
    scalar_t val = image[y][x];
    if (p_type == PIX_RED)
      r = val;
    else
      b = val;

    // Green Interpolation (The "Cross")
    n = (scalar_t)has_u + (scalar_t)has_d + (scalar_t)has_l + (scalar_t)has_r;
    g = (image[yp][x] + image[yn][x] + image[y][xp] + image[y][xn]) / n;

    // Opposite Color Interpolation (The "Corners")
    n = (scalar_t)(has_u && has_l) + (scalar_t)(has_u && has_r) + (scalar_t)(has_d && has_l) +
        (scalar_t)(has_d && has_r);
    scalar_t corners = (image[yp][xp] + image[yp][xn] + image[yn][xp] + image[yn][xn]) / n;
    if (p_type == PIX_RED)
      b = corners;
    else
      r = corners;

  } else if (p_type == PIX_GREEN_RED_ROW) {
    // We are at Green, but the Red pixels are Left/Right
    g = image[y][x];
    r = (image[y][xp] + image[y][xn]) / ((scalar_t)has_l + (scalar_t)has_r);
    b = (image[yp][x] + image[yn][x]) / ((scalar_t)has_u + (scalar_t)has_d);

  } else if (p_type == PIX_GREEN_BLUE_ROW) {
    // We are at Green, but the Blue pixels are Left/Right
    g = image[y][x];
    b = (image[y][xp] + image[y][xn]) / ((scalar_t)has_l + (scalar_t)has_r);
    r = (image[yp][x] + image[yn][x]) / ((scalar_t)has_u + (scalar_t)has_d);
  }

  // --- 4. Final Output ---
  image_out[0][y][x] = r;
  image_out[1][y][x] = g;
  image_out[2][y][x] = b;
}

GibbsImage& DebayerLinearInterpolation(GibbsImage& image) {
  TORCH_CHECK(
      image.is_bayer(),
      "GibbsImage must have a bayer pattern as PixelLayout to perform DebayerLinearInterpolation " + image.repr());

  // Create an output tensor with the same height and width as the input
  torch::Tensor image_out = torch::empty({3, image.size(0), image.size(1)},
                                         torch::TensorOptions().dtype(image.dtype()).device(image.device()));

  // Define CUDA kernel launch parameters
  const int width = image.size(1);
  const int height = image.size(0);

  at::DeviceGuard guard(image.device());
  dim3 threads(16, 16);
  dim3 blocks((width + threads.x - 1) / threads.x, (height + threads.y - 1) / threads.y);

  // Launch the kernel with type dispatch
  AT_DISPATCH_FLOATING_TYPES_AND_HALF(
      image.scalar_type(), "debayer_cuda", ([&] {
        // We extract the accessors here to kinput_image the kernel call lean
        auto input_accessor = image.pixels.packed_accessor32<scalar_t, 2, torch::RestrictPtrTraits>();
        auto output_accessor = image_out.packed_accessor32<scalar_t, 3, torch::RestrictPtrTraits>();

        switch (image.pixel_layout) {
          case PixelLayout::RGGB:
            debayer_linear_interpolation_kernel<PixelLayout::RGGB, scalar_t>
                <<<blocks, threads>>>(input_accessor, output_accessor, width, height);
            break;
          case PixelLayout::BGGR:
            debayer_linear_interpolation_kernel<PixelLayout::BGGR, scalar_t>
                <<<blocks, threads>>>(input_accessor, output_accessor, width, height);
            break;
          case PixelLayout::GBRG:
            debayer_linear_interpolation_kernel<PixelLayout::GBRG, scalar_t>
                <<<blocks, threads>>>(input_accessor, output_accessor, width, height);
            break;
          case PixelLayout::GRBG:
            debayer_linear_interpolation_kernel<PixelLayout::GRBG, scalar_t>
                <<<blocks, threads>>>(input_accessor, output_accessor, width, height);
            break;
          default:
            TORCH_CHECK(false, "Unsupported PixelLayout: ", (int)image.pixel_layout);
        }
      }));

  image.pixels = image_out;
  image.pixel_layout = PixelLayout::RGB;
  return image;
}

}  // namespace gibbs
}  // namespace vci
