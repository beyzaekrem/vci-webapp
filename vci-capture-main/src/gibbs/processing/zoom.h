#ifndef ZOOM_H
#define ZOOM_H

#include <torch/extension.h>
#include "image.h"
namespace vci {
namespace gibbs {

GibbsImage zoom(GibbsImage input, float center_x, float center_y, std::pair<int, int> client_size, float zoom_factor,
                bool copy);

}  // namespace gibbs
}  // namespace vci

#endif  // ZOOM_H
