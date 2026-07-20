#ifndef FLIP_VERTICAL_H
#define FLIP_VERTICAL_H

#include <torch/extension.h>

namespace vci
{
    namespace gibbs
    {

        /// Flips a CUDA tensor vertically. The input tensor is expected to be 3D [C, H, W].
        torch::Tensor flip_vertical(torch::Tensor input);

    } // namespace gibbs
} // namespace vci

#endif // FLIP_VERTICAL_H
