#ifndef VCI_GIBBS_CODEC_VIDEO_H
#define VCI_GIBBS_CODEC_VIDEO_H

#include <torch/extension.h>

#include <cuda_runtime_api.h>


namespace vci {
namespace gibbs {


void encode_video(std::vector<torch::Tensor> video);


} // namespace gibbs
} // namespace vci

#endif // VCI_GIBBS_CODEC_VIDEO_H
