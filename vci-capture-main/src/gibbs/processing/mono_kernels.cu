#include "mono_kernels.h"

#include <cuda.h>
#include <cuda_runtime.h>

#include <ATen/cuda/ApplyGridUtils.cuh>

namespace vci {
namespace gibbs {

template <typename scalar_t>
__global__ void delinearize_mono_kernel(torch::PackedTensorAccessor32<scalar_t, 2, torch::RestrictPtrTraits> image) {
  int index = blockIdx.x * blockDim.x + threadIdx.x;
  int stride = blockDim.x * gridDim.x;  // = number of threads
  int total_elements = image.size(0) * image.size(1);
  // IN-PLACE!

  for (int i = index; i < total_elements; i += stride) {
    int col = i % image.size(1);  // x
    int row = i / image.size(1);  // y

    // get pixel color
    float gray = image[row][col];

    // Convert from linear RGB to sRGB
    auto linearToSRGB = [] __device__(float c) -> float {
      if (c <= 0.0031308f) {
        return 12.92f * c;
      } else {
        return 1.055f * powf(c, 1.0f / 2.4f) - 0.055f;
      }
    };
    gray = linearToSRGB(gray);
    // clip (0 1)
    gray = min(max(gray, 0.0f), 1.0f);

    // udpate pixel color
    image[row][col] = gray;
  }
}

GibbsImage& DelinearizeMono(GibbsImage& image) {
  // modification truly in-place
  TORCH_CHECK(image.is_mono(), "GibbsImage& must be Mono");
  at::DeviceGuard guard(image.device());
  const int64_t numel = image.pixels.numel();

  dim3 threads = at::cuda::getApplyBlock();
  dim3 blocks;
  at::cuda::getApplyGrid(numel, blocks, image.device().index());

  AT_DISPATCH_FLOATING_TYPES_AND_HALF(image.scalar_type(), "delinearize_mono_kernel", ([&] {
                                        delinearize_mono_kernel<scalar_t><<<blocks, threads>>>(
                                            image.pixels.packed_accessor32<scalar_t, 2, torch::RestrictPtrTraits>());
                                      }));
  return image;
}

template <typename scalar_t>
__global__ void apply_distortion_correction_mono(
    const torch::PackedTensorAccessor32<scalar_t, 2, torch::RestrictPtrTraits> image,
    const torch::PackedTensorAccessor32<scalar_t, 1, torch::RestrictPtrTraits> camera_matrix,
    const torch::PackedTensorAccessor32<scalar_t, 1, torch::RestrictPtrTraits> dist_coeffs,
    torch::PackedTensorAccessor32<scalar_t, 2, torch::RestrictPtrTraits> image_out) {
  int index = blockIdx.x * blockDim.x + threadIdx.x;
  int stride = blockDim.x * gridDim.x;  // = number of threads
  int total_elements = image.size(0) * image.size(1);

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

  float width = image.size(1);
  float height = image.size(0);

  for (int i = index; i < total_elements; i += stride) {
    int col = i % image.size(1);  // x
    int row = i / image.size(1);  // y

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
      auto value = image[distorted_pixel_y][distorted_pixel_x];

      image_out[row][col] = value;
    }
  }
}

GibbsImage& ApplyDistortionCorrectionMono(GibbsImage& image, torch::Tensor camera_matrix, torch::Tensor dist_coeffs) {
  TORCH_CHECK(image.is_mono(), "GibbsImage& must be Mono");
  // Create empty tensor
  torch::Tensor image_out =
      torch::empty({image.size(0), image.size(1)}, torch::TensorOptions().dtype(image.dtype()).device(image.device()));
  at::DeviceGuard guard(image.device());
  dim3 threads = at::cuda::getApplyBlock();
  dim3 blocks;
  at::cuda::getApplyGrid(image_out.numel(), blocks, image.device().index());

  AT_DISPATCH_FLOATING_TYPES_AND_HALF(image.scalar_type(), "apply_distortion_correction_mono", ([&] {
                                        apply_distortion_correction_mono<scalar_t><<<blocks, threads>>>(
                                            image.pixels.packed_accessor32<scalar_t, 2, torch::RestrictPtrTraits>(),
                                            camera_matrix.packed_accessor32<scalar_t, 1, torch::RestrictPtrTraits>(),
                                            dist_coeffs.packed_accessor32<scalar_t, 1, torch::RestrictPtrTraits>(),
                                            image_out.packed_accessor32<scalar_t, 2, torch::RestrictPtrTraits>());
                                      }));
  image.pixels = image_out;
  return image;
}

}  // namespace gibbs
}  // namespace vci