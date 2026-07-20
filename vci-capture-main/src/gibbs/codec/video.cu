#include "video.h"

// extern "C" {
// #include <libavcodec/avcodec.h>
// #include <libavutil/hwcontext.h>
// #include <libavutil/pixdesc.h>
// }

// #include "nvEncodeAPI.h"
// #include "NvCodecUtils.h"
// #include "NvEncoder/NvEncoderCuda.h"
// #include "NvEncoder/NvEncoderOutputInVidMemCuda.h"

namespace vci {
namespace gibbs {

void encode_video(std::vector<torch::Tensor> video) {
//   int width = 100;
//   int height = 100;
//   int fps = 30;

//   const AVCodec* codec = avcodec_find_encoder_by_name("h264_nvenc");
//   if (!codec) {
//       std::cerr << "Error: NVENC encoder not found!" << std::endl;
//       // TODO: Error
//       return;
//   }

//   AVCodecContext* codec_ctx = avcodec_alloc_context3(codec);
//   if (!codec_ctx) {
//       std::cerr << "Error: Failed to allocate codec context!" << std::endl;
//       // TODO: Error
//       return;
//   }

//   codec_ctx->width = width;
//   codec_ctx->height = height;
//   codec_ctx->time_base = {1, fps};
//   codec_ctx->framerate = {fps, 1};
//   codec_ctx->gop_size = 10;
//   codec_ctx->max_b_frames = 2;
//   codec_ctx->pix_fmt = AV_PIX_FMT_CUDA;

//   // Open encoder
//   if (avcodec_open2(codec_ctx, codec, nullptr) < 0) {
//       std::cerr << "Error: Could not open codec!" << std::endl;
//       avcodec_free_context(&codec_ctx);
//       // TODO: Error
//       return;
//   }

//   std::cout << "Made a context!" << std::endl;
}

} // namespace gibbs
} // namespace vci
