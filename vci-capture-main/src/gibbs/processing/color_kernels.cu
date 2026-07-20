#include "color_kernels.h"

#include <cuda.h>
#include <cuda_runtime.h>

#include <ATen/cuda/ApplyGridUtils.cuh>

namespace vci {
namespace gibbs {

// RGB image
template <typename scalar_t>
__global__ void apply_white_balance(
    torch::PackedTensorAccessor32<scalar_t, 3, torch::RestrictPtrTraits> image,
    const torch::PackedTensorAccessor32<scalar_t, 1, torch::RestrictPtrTraits> white_balance) {
  int index = blockIdx.x * blockDim.x + threadIdx.x;
  int stride = blockDim.x * gridDim.x;  // = number of threads
  int total_elements = image.size(1) * image.size(2);

  for (int i = index; i < total_elements; i += stride) {
    int col = i % image.size(2);  // x
    int row = i / image.size(2);  // y

    auto r = image[0][row][col];
    auto g = image[1][row][col];
    auto b = image[2][row][col];

    // apply white balance
    r = r * white_balance[0];
    g = g * white_balance[1];
    b = b * white_balance[2];

    // clip (0 1)
    r = min(max(r, 0.0f), 1.0f);
    g = min(max(g, 0.0f), 1.0f);
    b = min(max(b, 0.0f), 1.0f);

    image[0][row][col] = r;
    image[1][row][col] = g;
    image[2][row][col] = b;
  }
}

GibbsImage& ApplyWhiteBalance(GibbsImage& image, torch::Tensor white_balance) {
  TORCH_CHECK(image.is_rgb(), "GibbsImage must be RGB image", image.repr());
  // Create empty tensor
  at::DeviceGuard guard(image.device());
  dim3 threads = at::cuda::getApplyBlock();
  dim3 blocks;
  at::cuda::getApplyGrid(image.pixels.numel() / 3, blocks, image.device().index());

  AT_DISPATCH_FLOATING_TYPES_AND_HALF(image.scalar_type(), "apply_white_balance", ([&] {
                                        apply_white_balance<scalar_t><<<blocks, threads>>>(
                                            image.pixels.packed_accessor32<scalar_t, 3, torch::RestrictPtrTraits>(),
                                            white_balance.packed_accessor32<scalar_t, 1, torch::RestrictPtrTraits>());
                                      }));

  return image;
}

template <PixelLayout PATTERN, typename scalar_t>
__global__ void apply_white_balance_bayer(
    torch::PackedTensorAccessor32<scalar_t, 2, torch::RestrictPtrTraits> image,
    const torch::PackedTensorAccessor32<scalar_t, 1, torch::RestrictPtrTraits> gains) {
  int index = blockIdx.x * blockDim.x + threadIdx.x;
  int stride = blockDim.x * gridDim.x;
  int total_elements = image.size(0) * image.size(1);

  for (int i = index; i < total_elements; i += stride) {
    int row = i / image.size(1);
    int col = i % image.size(1);

    // Determine if we are in an even/odd row or column
    bool r_odd = (row % 2);
    bool c_odd = (col % 2);

    int wb_idx;  // 0:R, 1:G, 2:B

    if (PATTERN == PixelLayout::RGGB) {
      // [R G] row 0
      // [G B] row 1
      if (!r_odd)
        wb_idx = (!c_odd) ? 0 : 1;
      else
        wb_idx = (!c_odd) ? 1 : 2;
    } else if (PATTERN == PixelLayout::BGGR) {
      // [B G] row 0
      // [G R] row 1
      if (!r_odd)
        wb_idx = (!c_odd) ? 2 : 1;
      else
        wb_idx = (!c_odd) ? 1 : 0;
    } else if (PATTERN == PixelLayout::GRBG) {
      // [G R] row 0
      // [B G] row 1
      if (!r_odd)
        wb_idx = (!c_odd) ? 1 : 0;
      else
        wb_idx = (!c_odd) ? 2 : 1;
    } else if (PATTERN == PixelLayout::GBRG) {
      // [G B] row 0
      // [R G] row 1
      if (!r_odd)
        wb_idx = (!c_odd) ? 1 : 2;
      else
        wb_idx = (!c_odd) ? 0 : 1;
    }

    // Apply wb coefficients in-place
    image[row][col] = static_cast<scalar_t>(image[row][col] * gains[wb_idx]);
  }
}

GibbsImage& ApplyWhiteBalanceBayer(GibbsImage& image, torch::Tensor white_balance) {
  TORCH_CHECK(image.is_bayer(), "GibbsImage must have a bayer pattern as PixelLayout ", image.repr());

  TORCH_CHECK(white_balance.size(0) == 3, "white_balance must be tensor like [R,G,B]", white_balance);
  at::DeviceGuard guard(image.device());
  dim3 threads = at::cuda::getApplyBlock();
  dim3 blocks;
  at::cuda::getApplyGrid(image.pixels.numel(), blocks, image.device().index());

  AT_DISPATCH_FLOATING_TYPES_AND_HALF(
      image.scalar_type(), "apply_white_balance_bayer", ([&] {
        auto in_place_accessor = image.pixels.packed_accessor32<scalar_t, 2, torch::RestrictPtrTraits>();
        auto wb_accessor = white_balance.packed_accessor32<scalar_t, 1, torch::RestrictPtrTraits>();

        switch (image.pixel_layout) {
          case PixelLayout::BGGR:
            apply_white_balance_bayer<PixelLayout::BGGR, scalar_t><<<blocks, threads>>>(in_place_accessor, wb_accessor);
            break;
          case PixelLayout::RGGB:
            apply_white_balance_bayer<PixelLayout::RGGB, scalar_t><<<blocks, threads>>>(in_place_accessor, wb_accessor);
            break;
          case PixelLayout::GBRG:
            apply_white_balance_bayer<PixelLayout::GBRG, scalar_t><<<blocks, threads>>>(in_place_accessor, wb_accessor);
            break;
          case PixelLayout::GRBG:
            apply_white_balance_bayer<PixelLayout::GRBG, scalar_t><<<blocks, threads>>>(in_place_accessor, wb_accessor);
            break;
          default:
            TORCH_CHECK(false, "Unsupported PixelLayout: ", (int)image.pixel_layout);
        }
      }));
  return image;
}

template <typename scalar_t>
__global__ void apply_color_correction(
    torch::PackedTensorAccessor32<scalar_t, 3, torch::RestrictPtrTraits> image,
    const torch::PackedTensorAccessor32<scalar_t, 1, torch::RestrictPtrTraits> colorcorrection) {
  int index = blockIdx.x * blockDim.x + threadIdx.x;
  int stride = blockDim.x * gridDim.x;  // = number of threads
  int total_elements = image.size(1) * image.size(2);

  for (int i = index; i < total_elements; i += stride) {
    int col = i % image.size(2);  // x
    int row = i / image.size(2);  // y

    auto r = image[0][row][col];
    auto g = image[1][row][col];
    auto b = image[2][row][col];

    // Apply the color correction matrix
    auto new_r = colorcorrection[0] * r + colorcorrection[1] * g + colorcorrection[2] * b;
    auto new_g = colorcorrection[3] * r + colorcorrection[4] * g + colorcorrection[5] * b;
    auto new_b = colorcorrection[6] * r + colorcorrection[7] * g + colorcorrection[8] * b;
    r = new_r;
    g = new_g;
    b = new_b;

    // clip (0 1)
    r = min(max(r, 0.0f), 1.0f);
    g = min(max(g, 0.0f), 1.0f);
    b = min(max(b, 0.0f), 1.0f);

    // apply white_balance coefficients in place.
    image[0][row][col] = r;
    image[1][row][col] = g;
    image[2][row][col] = b;
  }
}

GibbsImage& ApplyColorCorrection(GibbsImage& image, torch::Tensor colorcorrection) {
  TORCH_CHECK(image.is_rgb(), "GibbsImage must be RGB image ", image.repr());

  at::DeviceGuard guard(image.device());
  dim3 threads = at::cuda::getApplyBlock();
  dim3 blocks;
  at::cuda::getApplyGrid(image.pixels.numel() / 3, blocks, image.device().index());

  AT_DISPATCH_FLOATING_TYPES_AND_HALF(image.scalar_type(), "apply_color_correction", ([&] {
                                        apply_color_correction<scalar_t><<<blocks, threads>>>(
                                            image.pixels.packed_accessor32<scalar_t, 3, torch::RestrictPtrTraits>(),
                                            colorcorrection.packed_accessor32<scalar_t, 1, torch::RestrictPtrTraits>());
                                      }));
  return image;
}

template <typename scalar_t>
__global__ void apply_distortion_correction(
    const torch::PackedTensorAccessor32<scalar_t, 3, torch::RestrictPtrTraits> image,
    const torch::PackedTensorAccessor32<scalar_t, 1, torch::RestrictPtrTraits> camera_matrix,
    const torch::PackedTensorAccessor32<scalar_t, 1, torch::RestrictPtrTraits> dist_coeffs,
    torch::PackedTensorAccessor32<scalar_t, 3, torch::RestrictPtrTraits> image_out) {
  int index = blockIdx.x * blockDim.x + threadIdx.x;
  int stride = blockDim.x * gridDim.x;  // = number of threads
  int total_elements = image.size(1) * image.size(2);

  // Camera matrix parameters
  float fx = camera_matrix[0];
  float fy = camera_matrix[4];
  float cx = camera_matrix[2];
  float cy = camera_matrix[5];

  // Distortion coefficients
  float k1 = dist_coeffs[0];
  float k2 = dist_coeffs[1];
  float p1 = dist_coeffs[2];
  float p2 = dist_coeffs[3];
  float k3 = dist_coeffs[4];

  float width = image.size(2);
  float height = image.size(1);

  for (int i = index; i < total_elements; i += stride) {
    int col = i % image.size(2);  // x
    int row = i / image.size(2);  // y

    // Normalize pixel coordinates
    float u = (col - cx) / fx;
    float v = (row - cy) / fy;

    // Calculate radial distortion
    float r2 = u * u + v * v;
    float r4 = r2 * r2;
    float r6 = r4 * r2;
    float radial_dist = 1 + k1 * r2 + k2 * r4 + k3 * r6;

    // Calculate tangential distortion
    float x_distorted = u * radial_dist + 2 * p1 * u * v + p2 * (r2 + 2 * u * u);
    float y_distorted = v * radial_dist + p1 * (r2 + 2 * v * v) + 2 * p2 * u * v;

    // Map back to pixel coordinates
    int distorted_pixel_x = round(fx * x_distorted + cx);
    int distorted_pixel_y = round(fy * y_distorted + cy);

    // Only process valid pixels within the image boundaries
    if (distorted_pixel_x >= 0 && distorted_pixel_x < width && distorted_pixel_y >= 0 && distorted_pixel_y < height) {
      // grab color of pixel at distorted row/col for our output pixel at row/col
      auto r = image[0][distorted_pixel_y][distorted_pixel_x];
      auto g = image[1][distorted_pixel_y][distorted_pixel_x];
      auto b = image[2][distorted_pixel_y][distorted_pixel_x];

      image_out[0][row][col] = r;
      image_out[1][row][col] = g;
      image_out[2][row][col] = b;
    }
  }
}

GibbsImage& ApplyDistortionCorrection(GibbsImage& image, torch::Tensor camera_matrix, torch::Tensor dist_coeffs) {
  TORCH_CHECK(image.is_rgb(), "GibbsImage must be RGB image ", image.repr());
  // Create empty tensor
  torch::Tensor image_out = torch::empty({3, image.size(1), image.size(2)},
                                         torch::TensorOptions().dtype(image.dtype()).device(image.device()));

  dim3 threads = at::cuda::getApplyBlock();
  dim3 blocks;
  at::DeviceGuard guard(image.device());
  at::cuda::getApplyGrid(image_out.numel() / 3, blocks, image.device().index());

  AT_DISPATCH_FLOATING_TYPES_AND_HALF(image.scalar_type(), "apply_distortion_correction", ([&] {
                                        apply_distortion_correction<scalar_t><<<blocks, threads>>>(
                                            image.pixels.packed_accessor32<scalar_t, 3, torch::RestrictPtrTraits>(),
                                            camera_matrix.packed_accessor32<scalar_t, 1, torch::RestrictPtrTraits>(),
                                            dist_coeffs.packed_accessor32<scalar_t, 1, torch::RestrictPtrTraits>(),
                                            image_out.packed_accessor32<scalar_t, 3, torch::RestrictPtrTraits>());
                                      }));
  image.pixels = image_out;
  return image;
}

template <typename scalar_t>
__global__ void convert_linear_to_srgb_kernel(
    torch::PackedTensorAccessor32<scalar_t, 3, torch::RestrictPtrTraits> image) {
  int index = blockIdx.x * blockDim.x + threadIdx.x;
  int stride = blockDim.x * gridDim.x;  // = number of threads
  int total_elements = image.size(1) * image.size(2);

  float width = image.size(2);
  float height = image.size(1);

  for (int i = index; i < total_elements; i += stride) {
    int col = i % image.size(2);  // x
    int row = i / image.size(2);  // y

    // get pixel colors
    float r = image[0][row][col];
    float g = image[1][row][col];
    float b = image[2][row][col];

    // do something cool with pixel
    // Convert from linear RGB to sRGB
    auto linearToSRGB = [] __device__(float c) -> float {
      if (c <= 0.0031308f) {
        return 12.92f * c;
      } else {
        return 1.055f * powf(c, 1.0f / 2.4f) - 0.055f;
      }
    };

    r = linearToSRGB(r);
    g = linearToSRGB(g);
    b = linearToSRGB(b);

    // clip (0 1)
    r = min(max(r, 0.0f), 1.0f);
    g = min(max(g, 0.0f), 1.0f);
    b = min(max(b, 0.0f), 1.0f);

    // update write pixel colors in-place
    image[0][row][col] = r;
    image[1][row][col] = g;
    image[2][row][col] = b;
  }
}

GibbsImage& DelinearizeColor(GibbsImage& image) {
  TORCH_CHECK(image.is_rgb(), "GibbsImage must be RGB image ", image.repr());
  // Create empty tensor
  at::DeviceGuard guard(image.device());
  dim3 threads = at::cuda::getApplyBlock();
  dim3 blocks;
  at::cuda::getApplyGrid(image.pixels.numel() / 3, blocks, image.device().index());

  AT_DISPATCH_FLOATING_TYPES_AND_HALF(image.scalar_type(), "convert_linear_to_srgb_kernel", ([&] {
                                        convert_linear_to_srgb_kernel<scalar_t><<<blocks, threads>>>(
                                            image.pixels.packed_accessor32<scalar_t, 3, torch::RestrictPtrTraits>());
                                      }));
  return image;
}

template <typename scalar_t>
__global__ void convert_to_uint8_kernel(
    const torch::PackedTensorAccessor32<scalar_t, 3, torch::RestrictPtrTraits> image,
    torch::PackedTensorAccessor32<uint8_t, 3, torch::RestrictPtrTraits> image_out) {
  int index = blockIdx.x * blockDim.x + threadIdx.x;
  int stride = blockDim.x * gridDim.x;  // = number of threads
  int total_elements = image.size(1) * image.size(2);

  for (int i = index; i < total_elements; i += stride) {
    int col = i % image.size(2);  // x
    int row = i / image.size(2);  // y

    float r_ = image[0][row][col];
    float g_ = image[1][row][col];
    float b_ = image[2][row][col];

    // Clip float values to the range [0, 1]
    r_ = min(max(r_, 0.0f), 1.0f);
    g_ = min(max(g_, 0.0f), 1.0f);
    b_ = min(max(b_, 0.0f), 1.0f);

    // Convert to 0-255 range and cast to uint8_t
    uint8_t r = static_cast<uint8_t>(255.0f * r_);
    uint8_t g = static_cast<uint8_t>(255.0f * g_);
    uint8_t b = static_cast<uint8_t>(255.0f * b_);

    image_out[0][row][col] = r;
    image_out[1][row][col] = g;
    image_out[2][row][col] = b;
  }
}

GibbsImage& ConvertToUInt8(GibbsImage& image) {
  // Create an empty output tensor of type uint8
  torch::Tensor image_out = torch::empty({3, image.size(1), image.size(2)},
                                         torch::TensorOptions().dtype(torch::kUInt8).device(image.device()));

  // Set block and grid sizes
  dim3 threads = at::cuda::getApplyBlock();
  dim3 blocks;
  at::cuda::getApplyGrid(image_out.numel() / 3, blocks, image.device().index());
  at::cuda::CUDAStream current_stream = at::cuda::getCurrentCUDAStream(image.device().index());

  // Launch the kernel with proper type casting for input and output
  AT_DISPATCH_FLOATING_TYPES_AND_HALF(image.scalar_type(), "convert_to_uint8_kernel", ([&] {
                                        convert_to_uint8_kernel<scalar_t>
                                            <<<blocks, threads, 0, current_stream.stream()>>>(
                                                image.pixels.packed_accessor32<scalar_t, 3, torch::RestrictPtrTraits>(),
                                                image_out.packed_accessor32<uint8_t, 3, torch::RestrictPtrTraits>());
                                      }));
  image.pixels = image_out;
  return image;
}

}  // namespace gibbs
}  // namespace vci