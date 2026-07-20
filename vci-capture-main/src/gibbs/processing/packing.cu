#include "packing.h"

#include <cuda.h>
#include <cuda_runtime.h>

#include <ATen/cuda/ApplyGridUtils.cuh>

namespace vci {
namespace gibbs {

template <typename scalar_t>
__global__ void unpack_16_bit_kernel(
    const torch::PackedTensorAccessor32<unsigned char, 1, torch::RestrictPtrTraits> buffer,
    torch::PackedTensorAccessor32<scalar_t, 2, torch::RestrictPtrTraits> image) {
  // each pixel has 16 bit of intensity and is in 2 bytes of memory
  int index = blockIdx.x * blockDim.x + threadIdx.x;
  int stride = blockDim.x * gridDim.x;
  int total_elements = image.size(0) * image.size(1);

  for (int i = index; i < total_elements; i += stride) {
    int buffer_idx = i * 2;  // 2 bytes per pixel
    unsigned char byte0 = buffer[buffer_idx];
    unsigned char byte1 = buffer[buffer_idx + 1];
    uint16_t value = static_cast<uint16_t>(byte0) + (static_cast<uint16_t>(byte1) << 8);
    int row = i / image.size(1);
    int col = i % image.size(1);

    image[row][col] = static_cast<scalar_t>(value) / static_cast<scalar_t>(65536);
  }
}

template <typename scalar_t>
__global__ void unpack_12_bit_kernel(
    const torch::PackedTensorAccessor32<unsigned char, 1, torch::RestrictPtrTraits> buffer,
    torch::PackedTensorAccessor32<scalar_t, 2, torch::RestrictPtrTraits> image) {
  // each pixel has 12 bit of intensity. Two pixels are packed together into 3 bytes.
  int index = blockIdx.x * blockDim.x + threadIdx.x;
  int stride = blockDim.x * gridDim.x;
  int total_elements = image.size(0) * image.size(1) / 2;
  for (int i = index; i < total_elements; i += stride) {
    // packs 2 pixels in 3 bytes
    int buffer_idx = i * 3;
    unsigned char byte0 = buffer[buffer_idx];
    unsigned char byte1 = buffer[buffer_idx + 1];
    unsigned char byte2 = buffer[buffer_idx + 2];

    uint16_t value0 = static_cast<uint16_t>(byte0) + 256 * static_cast<uint16_t>(byte1 % 16);
    int row = (2 * i) / image.size(1);
    int col = (2 * i) % image.size(1);
    image[row][col] = static_cast<scalar_t>(value0) / scalar_t(4096);

    uint16_t value1 = static_cast<uint16_t>(byte1 / 16) + 16 * static_cast<uint16_t>(byte2);
    row = (2 * i + 1) / image.size(1);
    col = (2 * i + 1) % image.size(1);
    image[row][col] = static_cast<scalar_t>(value1) / scalar_t(4096);
  }
}

template <typename scalar_t>
__global__ void non_packed_12_bit_kernel(
    const torch::PackedTensorAccessor32<unsigned char, 1, torch::RestrictPtrTraits> buffer,
    torch::PackedTensorAccessor32<scalar_t, 2, torch::RestrictPtrTraits> image) {
  // each pixel has 12 bit of intensity. Each pixel takes up two full bytes (aka 16 bit).
  int index = blockIdx.x * blockDim.x + threadIdx.x;
  int stride = blockDim.x * gridDim.x;
  int total_elements = image.size(0) * image.size(1);

  for (int i = index; i < total_elements; i += stride) {
    int buffer_idx = i * 2;  // 2 bytes per pixel
    unsigned char byte0 = buffer[buffer_idx];
    unsigned char byte1 = buffer[buffer_idx + 1];
    uint16_t value = static_cast<uint16_t>(byte0) + (static_cast<uint16_t>(byte1) << 8);
    int row = i / image.size(1);
    int col = i % image.size(1);

    image[row][col] = static_cast<scalar_t>(value) / static_cast<scalar_t>(4096);
  }
}

template <typename scalar_t>
__global__ void non_packed_14_bit_kernel(
    const torch::PackedTensorAccessor32<unsigned char, 1, torch::RestrictPtrTraits> buffer,
    torch::PackedTensorAccessor32<scalar_t, 2, torch::RestrictPtrTraits> image) {
  // each pixel has 12 bit of intensity. Each pixel takes up two full bytes (aka 16 bit).
  int index = blockIdx.x * blockDim.x + threadIdx.x;
  int stride = blockDim.x * gridDim.x;
  int total_elements = image.size(0) * image.size(1);

  for (int i = index; i < total_elements; i += stride) {
    int buffer_idx = i * 2;  // 2 bytes per pixel
    unsigned char byte0 = buffer[buffer_idx];
    unsigned char byte1 = buffer[buffer_idx + 1];
    uint16_t value = static_cast<uint16_t>(byte0) + (static_cast<uint16_t>(byte1) << 8);
    int row = i / image.size(1);
    int col = i % image.size(1);

    image[row][col] = static_cast<scalar_t>(value) / static_cast<scalar_t>(16384);
  }
}

template <typename scalar_t>
__global__ void unpack_10_bit_kernel(
    const torch::PackedTensorAccessor32<unsigned char, 1, torch::RestrictPtrTraits> buffer,
    torch::PackedTensorAccessor32<scalar_t, 2, torch::RestrictPtrTraits> image) {
  // each pixel has 10 bit of intensity. 4 pixels are packed together into 5 bytes.
  int index = blockIdx.x * blockDim.x + threadIdx.x;
  int stride = blockDim.x * gridDim.x;
  int total_elements = image.size(0) * image.size(1) / 4;
  for (int i = index; i < total_elements; i += stride) {
    int buffer_idx = i * 5;
    unsigned char byte0 = buffer[buffer_idx];
    unsigned char byte1 = buffer[buffer_idx + 1];
    unsigned char byte2 = buffer[buffer_idx + 2];
    unsigned char byte3 = buffer[buffer_idx + 3];
    unsigned char byte4 = buffer[buffer_idx + 4];

    uint16_t value0 = static_cast<uint16_t>(byte0) + 256 * static_cast<uint16_t>(byte1 % 4);
    int row = (4 * i) / image.size(1);
    int col = (4 * i) % image.size(1);
    image[row][col] = static_cast<scalar_t>(value0) / scalar_t(1024);

    uint16_t value1 = static_cast<uint16_t>(byte1 / 4) + 64 * static_cast<uint16_t>(byte2 % 16);
    row = (4 * i + 1) / image.size(1);
    col = (4 * i + 1) % image.size(1);
    image[row][col] = static_cast<scalar_t>(value1) / scalar_t(1024);

    uint16_t value2 = static_cast<uint16_t>(byte2 / 16) + 16 * static_cast<uint16_t>(byte3 % 64);
    row = (4 * i + 2) / image.size(1);
    col = (4 * i + 2) % image.size(1);
    image[row][col] = static_cast<scalar_t>(value2) / scalar_t(1024);

    uint16_t value3 = static_cast<uint16_t>(byte3 / 64) + 4 * static_cast<uint16_t>(byte4);
    row = (4 * i + 3) / image.size(1);
    col = (4 * i + 3) % image.size(1);
    image[row][col] = static_cast<scalar_t>(value3) / scalar_t(1024);
  }
}

template <typename scalar_t>
__global__ void unpack_8_bit_kernel(
    const torch::PackedTensorAccessor32<unsigned char, 1, torch::RestrictPtrTraits> buffer,
    torch::PackedTensorAccessor32<scalar_t, 2, torch::RestrictPtrTraits> image) {
  // each pixel has 8 bit of intensity and takes up one byte.
  int index = blockIdx.x * blockDim.x + threadIdx.x;
  int stride = blockDim.x * gridDim.x;
  int total_elements = image.size(0) * image.size(1);
  for (int i = index; i < total_elements; i += stride) {
    unsigned char byte = buffer[i];

    uint16_t value = static_cast<uint16_t>(byte);
    int row = (i) / image.size(1);
    int col = (i) % image.size(1);
    image[row][col] = static_cast<scalar_t>(value) / scalar_t(256);
  }
}

template <typename scalar_t>
__global__ void unpack_8_bit_rgb_kernel(
    const torch::PackedTensorAccessor32<unsigned char, 1, torch::RestrictPtrTraits> buffer,
    torch::PackedTensorAccessor32<scalar_t, 3, torch::RestrictPtrTraits> image, bool bgr) {
  int index = blockIdx.x * blockDim.x + threadIdx.x;
  int stride = blockDim.x * gridDim.x;

  int height = image.size(1);
  int width = image.size(2);
  int total_pixels = height * width;

  for (int i = index; i < total_pixels; i += stride) {
    int buffer_idx = i * 3;  // 3 bytes per pixel

    unsigned char c0 = buffer[buffer_idx + 0];
    unsigned char c1 = buffer[buffer_idx + 1];
    unsigned char c2 = buffer[buffer_idx + 2];

    scalar_t v0 = static_cast<scalar_t>(c0) / static_cast<scalar_t>(255.0f);
    scalar_t v1 = static_cast<scalar_t>(c1) / static_cast<scalar_t>(255.0f);
    scalar_t v2 = static_cast<scalar_t>(c2) / static_cast<scalar_t>(255.0f);

    int row = i / width;
    int col = i % width;

    if (bgr) {
      image[0][row][col] = v2;
      image[1][row][col] = v1;
      image[2][row][col] = v0;
    } else {  // it should be this for the orbbec cams

      image[0][row][col] = v0;
      image[1][row][col] = v1;
      image[2][row][col] = v2;
    }
  }
}

GibbsImage UnpackBuffer(torch::Tensor buffer, const EntryInfo* entry_info) {
  // transforms an input image buffer, of different intenstiy bit depths into a float with range [0,1]

  // Create empty tensor
  int channels = entry_info->channels;
  torch::Tensor image;
  if (channels == 1) {
    image = torch::empty({entry_info->height, entry_info->width},
                         torch::TensorOptions().dtype(torch::kFloat32).device(buffer.device()));
  } else {
    image = torch::empty({channels, entry_info->height, entry_info->width},
                         torch::TensorOptions().dtype(torch::kFloat32).device(buffer.device()));
  }

  // Perform the asynchronous memory copy from the CPU to the tensor
  // at::cuda::CUDAStream current_stream = at::cuda::getCurrentCUDAStream(device.index());
  // cudaMemcpyAsync(
  //   tensor.data_ptr<unsigned char>(),
  //   buffer_entry->Buffer(),
  //   buffer_entry->PayloadBytes(),
  //   cudaMemcpyHostToDevice, current_stream.stream());
  // Return the created tensor

  // const int threads = 256;
  // const int blocks = (image.numel() + threads - 1) / threads;

  if (entry_info->bit_depth == 16) {  // each pixel has 16 bit of intensity and is in 2 bytes of memory
    dim3 threads = at::cuda::getApplyBlock();
    dim3 blocks;
    at::cuda::getApplyGrid(image.numel(), blocks, buffer.device().index());

    unpack_16_bit_kernel<float>
        <<<blocks, threads>>>(buffer.packed_accessor32<unsigned char, 1, torch::RestrictPtrTraits>(),
                              image.packed_accessor32<float, 2, torch::RestrictPtrTraits>());
  } else if (entry_info->bit_depth == 12 && entry_info->packed == false) {
    // 12 bits of intensity information none-packed aka in 2 bytes (16 bits) of memory
    dim3 threads = at::cuda::getApplyBlock();
    dim3 blocks;
    at::cuda::getApplyGrid(image.numel(), blocks, buffer.device().index());

    non_packed_12_bit_kernel<float>
        <<<blocks, threads>>>(buffer.packed_accessor32<unsigned char, 1, torch::RestrictPtrTraits>(),
                              image.packed_accessor32<float, 2, torch::RestrictPtrTraits>());
  } else if (entry_info->bit_depth == 14 && entry_info->packed == false) {
    // 12 bits of intensity information none-packed aka in 2 bytes (16 bits) of memory
    dim3 threads = at::cuda::getApplyBlock();
    dim3 blocks;
    at::cuda::getApplyGrid(image.numel(), blocks, buffer.device().index());

    non_packed_14_bit_kernel<float>
        <<<blocks, threads>>>(buffer.packed_accessor32<unsigned char, 1, torch::RestrictPtrTraits>(),
                              image.packed_accessor32<float, 2, torch::RestrictPtrTraits>());
  } else if (entry_info->bit_depth == 12 &&
             entry_info->packed) {  // each pixel has 12 bit of intensity. Two pixels are packed together into 3 bytes.
    dim3 threads = at::cuda::getApplyBlock();
    dim3 blocks;
    at::cuda::getApplyGrid(image.numel() / 2, blocks, buffer.device().index());
    unpack_12_bit_kernel<float>
        <<<blocks, threads>>>(buffer.packed_accessor32<unsigned char, 1, torch::RestrictPtrTraits>(),
                              image.packed_accessor32<float, 2, torch::RestrictPtrTraits>());
  } else if (entry_info->bit_depth == 10 &&
             entry_info->packed) {  // each pixel has 10 bit of intensity. 4 pixels are packed together into 5 bytes.
    dim3 threads = at::cuda::getApplyBlock();
    dim3 blocks;
    at::cuda::getApplyGrid(image.numel() / 4, blocks, buffer.device().index());

    unpack_10_bit_kernel<float>
        <<<blocks, threads>>>(buffer.packed_accessor32<unsigned char, 1, torch::RestrictPtrTraits>(),
                              image.packed_accessor32<float, 2, torch::RestrictPtrTraits>());
  } else if (entry_info->bit_depth == 8 && channels == 1) {  // each pixel has 8 bit of intensity and takes up one byte.
    dim3 threads = at::cuda::getApplyBlock();
    dim3 blocks;
    at::cuda::getApplyGrid(image.numel(), blocks, buffer.device().index());

    unpack_8_bit_kernel<float>
        <<<blocks, threads>>>(buffer.packed_accessor32<unsigned char, 1, torch::RestrictPtrTraits>(),
                              image.packed_accessor32<float, 2, torch::RestrictPtrTraits>());
  } else if (entry_info->bit_depth == 8 && channels == 3) {
    dim3 threads = at::cuda::getApplyBlock();
    dim3 blocks;

    // only one work item per pixel, not per channel
    at::cuda::getApplyGrid(entry_info->height * entry_info->width, blocks, buffer.device().index());

    bool bgr = entry_info->pixel_layout == PixelLayout::BGR;  // undefined is RGB
    unpack_8_bit_rgb_kernel<float>
        <<<blocks, threads>>>(buffer.packed_accessor32<unsigned char, 1, torch::RestrictPtrTraits>(),
                              image.packed_accessor32<float, 3, torch::RestrictPtrTraits>(), bgr);
  } else {
    throw std::runtime_error("Unpacking for bit depth " + std::to_string(entry_info->bit_depth) +
                             " is not implemented.");
  }

  return GibbsImage(image, entry_info->camera_id, entry_info->image_type, entry_info->pixel_layout);
}

}  // namespace gibbs
}  // namespace vci
