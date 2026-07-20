#ifndef VCI_GIBBS_PROCESSING_BAYER_H
#define VCI_GIBBS_PROCESSING_BAYER_H

#include <torch/extension.h>
#include "image.h"
namespace vci {
namespace gibbs {

/**
 * @brief Debayer the image using subsampling (each 2x2 becomes one RGB pixel)
 */
GibbsImage& DebayerSubsample(GibbsImage& image);

/**
 * @brief Debayer the image using interpolation. Images remains at full resolution.
 */
GibbsImage& DebayerLinearInterpolation(GibbsImage& image);

}  // namespace gibbs
}  // namespace vci

#endif  // VCI_GIBBS_PROCESSING_BAYER_H
