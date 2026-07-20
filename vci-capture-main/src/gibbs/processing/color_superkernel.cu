#include "color_superkernel.h"

#include <cuda.h>
#include <cuda_runtime.h>

#include <ATen/cuda/ApplyGridUtils.cuh>

namespace vci {
namespace gibbs {

template <typename scalar_t>
__global__ void superkernel_color(
    const torch::PackedTensorAccessor32<scalar_t, 3, torch::RestrictPtrTraits> image,
    const torch::PackedTensorAccessor32<scalar_t, 1, torch::RestrictPtrTraits> white_balance,
    const torch::PackedTensorAccessor32<scalar_t, 1, torch::RestrictPtrTraits> colorcorrection,
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
    // for each index in the output_image
    int col = i % image.size(2);  // x
    int row = i / image.size(2);  // y

    // apply distortion to get position of input_pixel
    float u = (col - cx) / fx;
    float v = (row - cy) / fy;

    // radial distortion
    float r2 = u * u + v * v;
    float r4 = r2 * r2;
    float r6 = r4 * r2;
    float radial_dist = 1 + k1 * r2 + k2 * r4 + k3 * r6;
    // tangential distortion
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

      // r = image[0][row][col]; // do not undistort
      // g = image[1][row][col];
      // b = image[2][row][col];

      // perform image processing

      // apply white balance
      r = r * white_balance[0];
      g = g * white_balance[1];
      b = b * white_balance[2];

      // clip (0 1)
      r = min(max(r, 0.0f), 1.0f);
      g = min(max(g, 0.0f), 1.0f);
      b = min(max(b, 0.0f), 1.0f);

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

      image_out[0][row][col] = r;
      image_out[1][row][col] = g;
      image_out[2][row][col] = b;
    }
  }
}

GibbsImage& SuperkernelColor(GibbsImage& image, torch::Tensor white_balance, torch::Tensor colorcorrection,
                             torch::Tensor camera_matrix, torch::Tensor dist_coeffs) {
  // Create empty tensor
  TORCH_CHECK(image.is_rgb(), "input image must be RGB for SuperKernelColor ", image.repr())
  torch::Tensor image_out = torch::empty({3, image.size(1), image.size(2)},
                                         torch::TensorOptions().dtype(image.dtype()).device(image.device()));

  dim3 threads = at::cuda::getApplyBlock();
  dim3 blocks;
  at::cuda::getApplyGrid(image_out.numel() / 3, blocks, image.device().index());

  AT_DISPATCH_FLOATING_TYPES_AND_HALF(image.scalar_type(), "superkernel_color", ([&] {
                                        superkernel_color<scalar_t><<<blocks, threads>>>(
                                            image.pixels.packed_accessor32<scalar_t, 3, torch::RestrictPtrTraits>(),
                                            white_balance.packed_accessor32<scalar_t, 1, torch::RestrictPtrTraits>(),
                                            colorcorrection.packed_accessor32<scalar_t, 1, torch::RestrictPtrTraits>(),
                                            camera_matrix.packed_accessor32<scalar_t, 1, torch::RestrictPtrTraits>(),
                                            dist_coeffs.packed_accessor32<scalar_t, 1, torch::RestrictPtrTraits>(),
                                            image_out.packed_accessor32<scalar_t, 3, torch::RestrictPtrTraits>());
                                      }));
  image.pixels = image_out;
  return image;
}

enum PixelType { PIX_RED, PIX_BLUE, PIX_GREEN_RED_ROW, PIX_GREEN_BLUE_ROW };

// For packed 12-bit bayer buffers. All bayer pattern supported.
template <PixelLayout PATTERN, typename scalar_t>
__global__ void combined_kernel(
    const torch::PackedTensorAccessor32<unsigned char, 1, torch::RestrictPtrTraits> buffer,
    const torch::PackedTensorAccessor32<scalar_t, 1, torch::RestrictPtrTraits> white_balance,
    const torch::PackedTensorAccessor32<scalar_t, 1, torch::RestrictPtrTraits> colorcorrection,
    const torch::PackedTensorAccessor32<scalar_t, 1, torch::RestrictPtrTraits> camera_matrix,
    const torch::PackedTensorAccessor32<scalar_t, 1, torch::RestrictPtrTraits> dist_coeffs,
    torch::PackedTensorAccessor32<scalar_t, 3, torch::RestrictPtrTraits> image_out) {
  int index = blockIdx.x * blockDim.x + threadIdx.x;
  int stride = blockDim.x * gridDim.x;
  int total_elements = image_out.size(1) * image_out.size(2);

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

  float width = image_out.size(2);
  float height = image_out.size(1);

  // for each index in the output_image(subsampled size)
  for (int i = index; i < total_elements; i += stride) {
    int col = i % image_out.size(2);  // output_pixel x
    int row = i / image_out.size(2);  // output pixel y
    // row/col is each pixel in the output image

    // apply distortion to get position of input_pixel
    float u = (col - cx) / fx;
    float v = (row - cy) / fy;
    float r2 = u * u + v * v;
    float radial_dist = 1 + k1 * r2 + k2 * r2 * r2 + k3 * r2 * r2 * r2;
    float x_distorted = u * radial_dist + 2 * p1 * u * v + p2 * (r2 + 2 * u * u);
    float y_distorted = v * radial_dist + p1 * (r2 + 2 * v * v) + 2 * p2 * u * v;

    int distorted_pixel_x = round(fx * x_distorted + cx);
    int distorted_pixel_y = round(fy * y_distorted + cy);

    // Only process valid pixels within the image boundaries
    if (distorted_pixel_x >= 0 && distorted_pixel_x < width && distorted_pixel_y >= 0 && distorted_pixel_y < height) {
      // for each pixel in the output_image (subsampled size)
      // each output pixel consists of four pixels in bayer image
      // the four bayer pixels are packed into 6 bytes. 3 consecutive bytes encode 2 pixels each for Bit-Depth 12.
      // let's call the 3 consecutive bytes a byte pack
      // we need to find the 2 byte packs that belong to our output pixel
      // the x location of the packs matches the x location of our output pixel. (The pack contains two bayer pixels in
      // x direction just like the output pixel) In y direction we always need two packs to get one pixel. Going down
      // one row of packs is + buffer/image width so when going down one pixel-row we need to go down two buffer rows
      // (row*2*width)

      // example with BGGR pattern:
      // [B G]0  [B G]1  [B G]2     byte_pack_idx
      // [G R]3  [G R]4  [G R]5
      //    (0,0)    (1,0)    (2,0) pixel x,y
      // [B G]6  [B G]7  [B G]8
      // [G R]9  [G R]10 [G R]11
      //    (0,1)    (1,1)    (2,1)
      // buffer width=3, height=4   12 bit buffer has same width and height*2
      // image  width=3, height=2

      // first byte pack:
      int byte_pack_idx = distorted_pixel_x + (distorted_pixel_y * 2 * width);
      int buffer_idx = byte_pack_idx * 3;
      unsigned char byte0 = buffer[buffer_idx];
      unsigned char byte1 = buffer[buffer_idx + 1];
      unsigned char byte2 = buffer[buffer_idx + 2];

      // second byte pack:
      byte_pack_idx += width;  // go one row down in buffer
      buffer_idx = byte_pack_idx * 3;
      unsigned char byte3 = buffer[buffer_idx];
      unsigned char byte4 = buffer[buffer_idx + 1];
      unsigned char byte5 = buffer[buffer_idx + 2];

      // get the four pixel values of the byte packs:
      //    [value0, value1]
      //    [value2, value3]
      uint16_t value0 = static_cast<uint16_t>(byte0) + 256 * static_cast<uint16_t>(byte1 % 16);
      uint16_t value1 = static_cast<uint16_t>(byte1 / 16) + 16 * static_cast<uint16_t>(byte2);

      uint16_t value2 = static_cast<uint16_t>(byte3) + 256 * static_cast<uint16_t>(byte4 % 16);
      uint16_t value3 = static_cast<uint16_t>(byte4 / 16) + 16 * static_cast<uint16_t>(byte5);

      // the four pixels values are merged into one rgb output pixel.
      //  patch:
      //      [p00, p01]
      //      [P10, p11]
      float p00, p01, p10, p11;
      // to float values
      p00 = static_cast<scalar_t>(value0) / scalar_t(4096);
      p01 = static_cast<scalar_t>(value1) / scalar_t(4096);
      p10 = static_cast<scalar_t>(value2) / scalar_t(4096);
      p11 = static_cast<scalar_t>(value3) / scalar_t(4096);

      float r, g, b;
      // get r,g,b channels from 2x2 patch (debayer subsample), according to bayer PATTERN
      if (PATTERN == PixelLayout::RGGB) {
        // [R G]  p00 p01
        // [G B]  p10 p11
        r = p00;
        g = 0.5f * (p01 + p10);
        b = p11;
      } else if (PATTERN == PixelLayout::BGGR) {
        // [B G]  p00 p01
        // [G R]  p10 p11
        r = p11;
        g = 0.5f * (p01 + p10);
        b = p00;
      } else if (PATTERN == PixelLayout::GRBG) {
        // [G R]  p00 p01
        // [B G]  p10 p11
        r = p01;
        g = 0.5f * (p00 + p11);
        b = p10;
      } else if (PATTERN == PixelLayout::GBRG) {
        // [G B]  p00 p01
        // [R G]  p10 p11
        r = p10;
        g = 0.5f * (p00 + p11);
        b = p01;
      }

      // Apply white balance
      r *= white_balance[0];
      g *= white_balance[1];
      b *= white_balance[2];

      // Clip to [0, 1]
      r = min(max(r, 0.0f), 1.0f);
      g = min(max(g, 0.0f), 1.0f);
      b = min(max(b, 0.0f), 1.0f);

      // Apply color correction matrix
      scalar_t new_r = colorcorrection[0] * r + colorcorrection[1] * g + colorcorrection[2] * b;
      scalar_t new_g = colorcorrection[3] * r + colorcorrection[4] * g + colorcorrection[5] * b;
      scalar_t new_b = colorcorrection[6] * r + colorcorrection[7] * g + colorcorrection[8] * b;

      // Convert to sRGB
      auto linearToSRGB = [] __device__(float c) -> float {
        return (c <= 0.0031308f) ? 12.92f * c : 1.055f * powf(c, 1.0f / 2.4f) - 0.055f;
      };

      image_out[0][row][col] = linearToSRGB(min(max(new_r, 0.0f), 1.0f));
      image_out[1][row][col] = linearToSRGB(min(max(new_g, 0.0f), 1.0f));
      image_out[2][row][col] = linearToSRGB(min(max(new_b, 0.0f), 1.0f));
    }
  }
}

GibbsImage CombinedKernel_Color(torch::Tensor buffer, const EntryInfo* entry_info, torch::Tensor white_balance,
                                torch::Tensor colorcorrection, torch::Tensor camera_matrix, torch::Tensor dist_coeffs) {
  TORCH_CHECK(entry_info->bit_depth == 12, "buffer bit-depth must be 12 bit")
  TORCH_CHECK(entry_info->packed, "buffer must be packed")
  TORCH_CHECK(PixelLayoutIsBayer(entry_info->pixel_layout), "Pixel layout must be bayer but is {}")

  // Create an output tensor for the image (3-channel: RGB)
  torch::Tensor image_out = torch::empty({3, entry_info->height / 2, entry_info->width / 2},
                                         torch::TensorOptions()
                                             .dtype(torch::kFloat32)  // Output in float32
                                             .device(buffer.device()));

  // Set block and grid dimensions for CUDA
  dim3 threads = at::cuda::getApplyBlock();
  dim3 blocks;
  at::cuda::getApplyGrid(image_out.numel() / 3, blocks, buffer.device().index());  // Adjusted for 3 channels
  auto current_stream = at::cuda::getCurrentCUDAStream(buffer.device().index()).stream();

  // Dispatch kernel
  AT_DISPATCH_FLOATING_TYPES_AND_HALF(
      torch::kFloat32, "combined_kernel", ([&] {
        auto buffer_accessor =
            buffer.packed_accessor32<unsigned char, 1, torch::RestrictPtrTraits>();  // Packed buffer accessor
        auto ouput_accessor =
            image_out.packed_accessor32<scalar_t, 3, torch::RestrictPtrTraits>();  // Output image (3-channel) accessor
        auto wb_accessor =
            white_balance.packed_accessor32<scalar_t, 1, torch::RestrictPtrTraits>();  // White balance accessor
        auto cc_accessor =
            colorcorrection
                .packed_accessor32<scalar_t, 1, torch::RestrictPtrTraits>();  // Color correction matrix accessor
        auto c_matrix_accessor =
            camera_matrix.packed_accessor32<scalar_t, 1, torch::RestrictPtrTraits>();  // Camera matrix accessor
        auto dist_coeffs_accessor =
            dist_coeffs.packed_accessor32<scalar_t, 1, torch::RestrictPtrTraits>();  // Distortion coefficients accessor

        switch (entry_info->pixel_layout) {
          case PixelLayout::RGGB:
            combined_kernel<PixelLayout::RGGB, scalar_t><<<blocks, threads, 0, current_stream>>>(
                buffer_accessor, wb_accessor, cc_accessor, c_matrix_accessor, dist_coeffs_accessor, ouput_accessor);
            break;
          case PixelLayout::BGGR:
            combined_kernel<PixelLayout::BGGR, scalar_t><<<blocks, threads, 0, current_stream>>>(
                buffer_accessor, wb_accessor, cc_accessor, c_matrix_accessor, dist_coeffs_accessor, ouput_accessor);
            break;
          case PixelLayout::GBRG:
            combined_kernel<PixelLayout::GBRG, scalar_t><<<blocks, threads, 0, current_stream>>>(
                buffer_accessor, wb_accessor, cc_accessor, c_matrix_accessor, dist_coeffs_accessor, ouput_accessor);
            break;
          case PixelLayout::GRBG:
            combined_kernel<PixelLayout::GRBG, scalar_t><<<blocks, threads, 0, current_stream>>>(
                buffer_accessor, wb_accessor, cc_accessor, c_matrix_accessor, dist_coeffs_accessor, ouput_accessor);
            break;
          default:
            TORCH_CHECK(false, "Unsupported PixelLayout ", (int)entry_info->pixel_layout);
        }
      }));
  return GibbsImage(image_out, entry_info->camera_id, entry_info->image_type, PixelLayout::RGB);
}

}  // namespace gibbs
}  // namespace vci