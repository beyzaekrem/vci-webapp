#include "codec.h"

#include <interceptor/logging.h>

#include <ATen/cuda/CUDAContext.h>

#define CHECK_NVJPEG(call)                                              \
  {                                                                     \
    nvjpegStatus_t _e = (call);                                         \
    if (_e != NVJPEG_STATUS_SUCCESS) {                                  \
      std::stringstream msg;                                            \
      msg << "NVJPEG failure: '#" << _e << "' at " << __FILE__ << ": "; \
      msg << __LINE__ << std::endl;                                     \
      vci::interceptor::logger()->error("{}", msg.str());               \
    }                                                                   \
  }

namespace vci {
namespace gibbs {

int dev_malloc(void** p, size_t s) {
  return (int)cudaMalloc(p, s);
}

int dev_free(void* p) {
  return (int)cudaFree(p);
}

JpgEncoder::JpgEncoder() : dev_allocator({&dev_malloc, &dev_free}) {
  CHECK_NVJPEG(nvjpegCreate(NVJPEG_BACKEND_GPU_HYBRID, &dev_allocator, &nvjpeg_handle));
  CHECK_NVJPEG(nvjpegJpegStreamCreate(nvjpeg_handle, &nvjpeg_jpeg_stream));
  CHECK_NVJPEG(nvjpegEncoderStateCreate(nvjpeg_handle, &nvjpeg_encoder_state, NULL));
  CHECK_NVJPEG(nvjpegEncoderParamsCreate(nvjpeg_handle, &nvjpeg_encode_params, NULL));
}

JpgEncoder::~JpgEncoder() {
  if (nvjpeg_jpeg_stream) {
    CHECK_NVJPEG(nvjpegJpegStreamDestroy(nvjpeg_jpeg_stream));
  }
  if (nvjpeg_encode_params) {
    CHECK_NVJPEG(nvjpegEncoderParamsDestroy(nvjpeg_encode_params));
  }
  if (nvjpeg_encoder_state) {
    CHECK_NVJPEG(nvjpegEncoderStateDestroy(nvjpeg_encoder_state));
  }
  if (nvjpeg_handle) {
    CHECK_NVJPEG(nvjpegDestroy(nvjpeg_handle));
  }
}

torch::Tensor JpgEncoder::encode(torch::Tensor image, int quality) {
  if (image.dim() != 3) {
    interceptor::logger()->error("Image must be 3xHxW.");
    throw std::invalid_argument("Image must be 3xHxW.");
  }

  int C = image.size(0);
  int H = image.size(1);
  int W = image.size(2);

  if (C != 3) {
    interceptor::logger()->error("Number of channels msut be 3.");
    throw std::invalid_argument("Number of channels must be 3.");
  }

  if (!image.device().is_cuda()) {
    interceptor::logger()->error("Only implemented for cuda tensors.");
    throw std::invalid_argument("Only implemented for cuda tensors.");
  }

  // Stream
  auto current_stream = at::cuda::getCurrentCUDAStream(image.device().index()).stream();

  // Settings
  CHECK_NVJPEG(nvjpegEncoderParamsSetQuality(nvjpeg_encode_params, quality, NULL));
  // CHECK_NVJPEG(nvjpegEncoderParamsSetOptimizedHuffman(nvjpeg_encode_params, 1, NULL));
  nvjpegChromaSubsampling_t subsampling = NVJPEG_CSS_444;
  CHECK_NVJPEG(nvjpegEncoderParamsSetSamplingFactors(nvjpeg_encode_params, subsampling, NULL));

  // Image Format
  nvjpegImage_t image_desc;
  image_desc.channel[0] = static_cast<unsigned char*>(image[0][0][0].data_ptr());
  image_desc.channel[1] = static_cast<unsigned char*>(image[1][0][0].data_ptr());
  image_desc.channel[2] = static_cast<unsigned char*>(image[2][0][0].data_ptr());
  image_desc.pitch[0] = W;
  image_desc.pitch[1] = W;
  image_desc.pitch[2] = W;

  // Encode
  CHECK_NVJPEG(nvjpegEncodeImage(nvjpeg_handle, nvjpeg_encoder_state, nvjpeg_encode_params, &image_desc,
                                 NVJPEG_INPUT_RGB, W, H, current_stream));

  // Get Size
  size_t length;
  CHECK_NVJPEG(nvjpegEncodeRetrieveBitstreamDevice(nvjpeg_handle, nvjpeg_encoder_state, NULL, &length, current_stream));

  // Same device and data type as input
  torch::TensorOptions options = torch::TensorOptions().dtype(torch::kUInt8).device(image.device());
  torch::Tensor output = at::empty({(long)length}, options);
  CHECK_NVJPEG(nvjpegEncodeRetrieveBitstreamDevice(
      nvjpeg_handle, nvjpeg_encoder_state, static_cast<unsigned char*>(output[0].data_ptr()), &length, current_stream));

  return output;
}

JpgDecoder::JpgDecoder() : dev_allocator({&dev_malloc, &dev_free}) {
  CHECK_NVJPEG(nvjpegCreate(NVJPEG_BACKEND_GPU_HYBRID, &dev_allocator, &nvjpeg_handle));
  CHECK_NVJPEG(nvjpegJpegStateCreate(nvjpeg_handle, &nvjpeg_decoder_state));
}

torch::Tensor JpgDecoder::decode(torch::Tensor jpg_image) {
  if (jpg_image.dim() != 1) {
    vci::interceptor::logger()->error("Image must be single dimension.");
  }

  int N = jpg_image.size(0);

  if (!jpg_image.device().is_cuda()) {
    vci::interceptor::logger()->error("Only implemented for cuda tensors.");
  }

  // Get Info
  torch::Tensor jpg_image_host = jpg_image.cpu();
  int nComponent = 0;
  nvjpegChromaSubsampling_t subsampling;
  int widths[NVJPEG_MAX_COMPONENT];
  int heights[NVJPEG_MAX_COMPONENT];
  CHECK_NVJPEG(nvjpegGetImageInfo(nvjpeg_handle, static_cast<unsigned char*>(jpg_image_host[0].data_ptr()), N,
                                  &nComponent, &subsampling, widths, heights));

  // Output tensor
  torch::TensorOptions options = torch::TensorOptions().dtype(torch::kUInt8).device(jpg_image.device());
  torch::Tensor image = at::empty({3, heights[0], widths[0]}, options);
  nvjpegImage_t image_desc;
  image_desc.channel[0] = static_cast<unsigned char*>(image[0][0][0].data_ptr());
  image_desc.channel[1] = static_cast<unsigned char*>(image[1][0][0].data_ptr());
  image_desc.channel[2] = static_cast<unsigned char*>(image[2][0][0].data_ptr());
  image_desc.pitch[0] = widths[0];
  image_desc.pitch[1] = widths[0];
  image_desc.pitch[2] = widths[0];

  CHECK_NVJPEG(nvjpegDecode(nvjpeg_handle, nvjpeg_decoder_state,
                            static_cast<unsigned char*>(jpg_image_host[0].data_ptr()), N, NVJPEG_OUTPUT_RGB,
                            &image_desc, NULL));

  return image;
}

EncodedImage encode_jpg(GibbsImage& image, int quality) {
  thread_local static JpgEncoder encoder;
  return EncodedImage(encoder.encode(image.pixels, quality), image, "jpg");
}

EncodedImage encode_mask(GibbsImage& mask, float threshold) {
  // Threshold if needed
  torch::Tensor mask_t = mask.pixels;
  if (mask_t.scalar_type() != torch::kBool) {
    mask_t = mask_t.gt(threshold);
  }
  // First entry is 0 or 1
  torch::Tensor leading_one = mask_t.index({0, 0}).to(torch::kInt32).view({1});
  // Count consecutive
  auto compressed = std::get<2>(torch::unique_consecutive(mask_t.flatten(),
                                                          /*return_inverse = */ false,
                                                          /*return_counts = */ true));
  return EncodedImage(torch::cat({leading_one, torch::cumsum(compressed, 0).to(torch::kInt32)}), mask, "binary");
}

}  // namespace gibbs
}  // namespace vci

#undef CHECK_NVJPEG
