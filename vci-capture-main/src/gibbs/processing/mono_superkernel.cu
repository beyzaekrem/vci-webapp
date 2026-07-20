#include "mono_superkernel.h"

#include <cuda.h>
#include <cuda_runtime.h>

#include <ATen/cuda/ApplyGridUtils.cuh>

namespace vci {
namespace gibbs {

template <typename scalar_t>
__global__ void superkernel_mono(
    const torch::PackedTensorAccessor32<scalar_t, 2, torch::RestrictPtrTraits> image,
    const torch::PackedTensorAccessor32<scalar_t, 1, torch::RestrictPtrTraits> camera_matrix,
    const torch::PackedTensorAccessor32<scalar_t, 1, torch::RestrictPtrTraits> dist_coeffs,
    torch::PackedTensorAccessor32<scalar_t, 2, torch::RestrictPtrTraits> image_out) {
  int index = blockIdx.x * blockDim.x + threadIdx.x;
  int stride = blockDim.x * gridDim.x;
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

    float x_distorted = u * radial_dist + 2 * p1 * u * v + p2 * (r2 + 2 * u * u);
    float y_distorted = v * radial_dist + p1 * (r2 + 2 * v * v) + 2 * p2 * u * v;

    // we read distorted pixel from input image (buffer) and draw row/col.
    int distorted_pixel_x = round(fx * x_distorted + cx);
    int distorted_pixel_y = round(fy * y_distorted + cy);

    // Only process valid pixels within the image boundaries
    if (distorted_pixel_x >= 0 && distorted_pixel_x < width && distorted_pixel_y >= 0 && distorted_pixel_y < height) {
      float gray = image[distorted_pixel_y][distorted_pixel_x];

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

      // write pixel colors into output image
      image_out[row][col] = gray;
    }
  }
}

GibbsImage& SuperkernelMono(GibbsImage& image, torch::Tensor camera_matrix, torch::Tensor dist_coeffs) {
  // Create empty tensor
  torch::Tensor image_out =
      torch::empty({image.size(0), image.size(1)}, torch::TensorOptions().dtype(image.dtype()).device(image.device()));

  dim3 threads = at::cuda::getApplyBlock();
  dim3 blocks;
  at::cuda::getApplyGrid(image_out.numel(), blocks, image.device().index());

  AT_DISPATCH_FLOATING_TYPES_AND_HALF(image.scalar_type(), "superkernel_mono", ([&] {
                                        superkernel_mono<scalar_t><<<blocks, threads>>>(
                                            image.pixels.packed_accessor32<scalar_t, 2, torch::RestrictPtrTraits>(),
                                            camera_matrix.packed_accessor32<scalar_t, 1, torch::RestrictPtrTraits>(),
                                            dist_coeffs.packed_accessor32<scalar_t, 1, torch::RestrictPtrTraits>(),
                                            image_out.packed_accessor32<scalar_t, 2, torch::RestrictPtrTraits>());
                                      }));
  image.pixels = image_out;
  return image;
}

template <typename scalar_t>
__global__ void combined_kernel_mono(
    const torch::PackedTensorAccessor32<unsigned char, 1, torch::RestrictPtrTraits> buffer,
    const torch::PackedTensorAccessor32<scalar_t, 1, torch::RestrictPtrTraits> camera_matrix,
    const torch::PackedTensorAccessor32<scalar_t, 1, torch::RestrictPtrTraits> dist_coeffs,
    torch::PackedTensorAccessor32<scalar_t, 2, torch::RestrictPtrTraits> image_out) {
  int index = blockIdx.x * blockDim.x + threadIdx.x;
  int stride = blockDim.x * gridDim.x;

  float width = image_out.size(1);  // for singel channel output_image. ndims=2 [H, W]
  float height = image_out.size(0);

  int total_elements = height * width;

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

  for (int i = index; i < total_elements; i += stride) {
    // for each index in the output_image (full size)
    int col = i % image_out.size(1);  // x
    int row = i / image_out.size(1);  // y

    // apply distortion to get position of input_pixel
    float u = (col - cx) / fx;
    float v = (row - cy) / fy;
    float r2 = u * u + v * v;
    float r4 = r2 * r2;
    float r6 = r4 * r2;
    float radial_dist = 1 + k1 * r2 + k2 * r4 + k3 * r6;
    float x_distorted = u * radial_dist + 2 * p1 * u * v + p2 * (r2 + 2 * u * u);
    float y_distorted = v * radial_dist + p1 * (r2 + 2 * v * v) + 2 * p2 * u * v;
    int distorted_pixel_x = round(fx * x_distorted + cx);
    int distorted_pixel_y = round(fy * y_distorted + cy);

    // Only process valid pixels within the image boundaries
    if (distorted_pixel_x >= 0 && distorted_pixel_x < width && distorted_pixel_y >= 0 && distorted_pixel_y < height) {
      // for each pixel in the output_image (full size)

      // in the Bit-Depth 12 buffer 3 consecutive bytes encode 2 pixels.
      // we call the 3 consecutive bytes a byte pack

      // image and buffer are related like this:
      // [pixel xy, xy] byte_pack_idx
      // [G00, G10]0  [G20, G30]1  [G40, G50]2   (go down a row(y) with +width)
      // [G01, G11]3  [G21, G31]4  [G41, G51]5
      // [G02, G12]6  [G22, G32]7  [G42, G52]8
      // [G03, G13]9  [G23, G33]10 [G43, G53]11
      // buffer width=3, height=4    12 bit buffer has width/2 and same height
      // image  width=6, height=4
      // Gxy -> G23 (2/2+3*3) = 10
      //        G33 (3/2+3*3) = 10

      // I don't understand but we need to go y/2 as well. I must be missing something

      // get our byte pack:
      int byte_pack_idx = (distorted_pixel_x / 2) + ((distorted_pixel_y / 2) * width);
      int buffer_idx = byte_pack_idx * 3;

      uint16_t value;
      // our byte pack has two gray values [G0,G1]
      if (col % 2 == 0) {
        // even pixels in x direction are the first value of the byte pack G0
        unsigned char byte0 = buffer[buffer_idx];
        unsigned char byte1 = buffer[buffer_idx + 1];
        value = static_cast<uint16_t>(byte0) + 256 * static_cast<uint16_t>(byte1 % 16);
      } else {
        // odd pixels in x direction are the second value of the byte pack G1
        unsigned char byte1 = buffer[buffer_idx + 1];
        unsigned char byte2 = buffer[buffer_idx + 2];
        value = static_cast<uint16_t>(byte1 / 16) + 16 * static_cast<uint16_t>(byte2);
      }
      // unfortunately we need to read byte1 twice to read the entire frame.
      // this is nessesary since we have to handle each pixel individually so we can undistort the image.
      // reading both values at once gives us nothing since we don't know where to put them.
      // We are iterating over the output_image, not the input images because calculating the distortion is easy
      // but calcualting the undisortion is not
      // A pre-computed distortion map would probably fix it

      // to float
      float gray;
      gray = static_cast<scalar_t>(value) / scalar_t(4096);

      // Convert from linear RGB to sRGB
      auto linearToSRGB = [] __device__(float c) -> float {
        if (c <= 0.0031308f) {
          return 12.92f * c;
        } else {
          return 1.055f * powf(c, 1.0f / 2.4f) - 0.055f;
        }
      };
      gray = linearToSRGB(gray);

      // Rescale into desired range after non-linear mapping
      float low = 10.0f / 255.0f;
      float high = 95.0f / 255.0f;
      gray = (gray - low) / (high - low);
      gray = min(max(gray, 0.0f), 1.0f);

      // write pixel colors into output image
      image_out[row][col] = gray;  // for singel channel output_image. ndims=2 [H, W]
    }
  }
}

GibbsImage CombinedKernel_Mono(torch::Tensor buffer, const EntryInfo* entry_info, torch::Tensor camera_matrix,
                               torch::Tensor dist_coeffs) {
  // this returns a mono channel image [H, W]. Expand without memory copy for matting and encoding
  torch::Tensor image_out = torch::empty({entry_info->height, entry_info->width},
                                         torch::TensorOptions().dtype(torch::kFloat32).device(buffer.device()));
  dim3 threads = at::cuda::getApplyBlock();
  dim3 blocks;

  at::cuda::getApplyGrid(image_out.numel(), blocks, buffer.device().index());
  at::cuda::CUDAStream current_stream = at::cuda::getCurrentCUDAStream(buffer.device().index());

  AT_DISPATCH_FLOATING_TYPES_AND_HALF(torch::kFloat32, "combined_kernel_mono", ([&] {
                                        combined_kernel_mono<scalar_t><<<blocks, threads, 0, current_stream.stream()>>>(
                                            buffer.packed_accessor32<unsigned char, 1, torch::RestrictPtrTraits>(),
                                            camera_matrix.packed_accessor32<scalar_t, 1, torch::RestrictPtrTraits>(),
                                            dist_coeffs.packed_accessor32<scalar_t, 1, torch::RestrictPtrTraits>(),
                                            image_out.packed_accessor32<scalar_t, 2, torch::RestrictPtrTraits>());
                                      }));

  return GibbsImage(image_out, entry_info->camera_id, entry_info->image_type, entry_info->pixel_layout);
}

}  // namespace gibbs
}  // namespace vci