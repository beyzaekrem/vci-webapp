#ifndef VCI_GIBBS_PROCESSING_CODEC_H
#define VCI_GIBBS_PROCESSING_CODEC_H

#include <torch/extension.h>

#include <cuda_runtime_api.h>
#include <nvjpeg.h>
#include "image.h"

namespace vci {
namespace gibbs {

class JpgEncoder {
 public:
  JpgEncoder();
  ~JpgEncoder();

  torch::Tensor encode(torch::Tensor image, int quality);

 private:
  nvjpegHandle_t nvjpeg_handle;
  nvjpegJpegStream_t nvjpeg_jpeg_stream;
  nvjpegEncoderParams_t nvjpeg_encode_params;
  nvjpegEncoderState_t nvjpeg_encoder_state;
  nvjpegDevAllocator_t dev_allocator;
};

class JpgDecoder {
 public:
  JpgDecoder();

  torch::Tensor decode(torch::Tensor jpg_image);

 private:
  nvjpegHandle_t nvjpeg_handle;
  nvjpegJpegState_t nvjpeg_decoder_state;
  nvjpegDevAllocator_t dev_allocator;
};

/**
 * @brief Encode the (3xHxW) image as a jpg buffer (L)
 */
EncodedImage encode_jpg(GibbsImage& image, int quality);

/**
 * @brief Encode the (HxW) mask using run-length encoding (L)
 */
EncodedImage encode_mask(GibbsImage& mask, float threshold);

}  // namespace gibbs
}  // namespace vci

#endif  // VCI_GIBBS_PROCESSING_BAYER_H
