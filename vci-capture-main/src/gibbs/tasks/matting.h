#ifndef GIBBS_TASKS_MATTING_H
#define GIBBS_TASKS_MATTING_H

#include <ATen/core/Dict.h>
#include <pybind11/pybind11.h>
#include <torch/script.h>
#include <string>

#include "image.h"

namespace vci {
namespace gibbs {

struct MattingOut {
  torch::Tensor mask;
  torch::Tensor foreground;
};

class Matting {
 public:
  Matting(std::string pt_path);

  torch::Dtype dtype() const;
  MattingOut forward(torch::Tensor foreground, torch::Tensor background);
  GibbsImage infer(GibbsImage foreground, GibbsImage background);

 private:
  torch::jit::script::Module module_;
  torch::Dtype dtype_;
};

}  // namespace gibbs
}  // namespace vci

#endif  // GIBBS_TASKS_MATTING_H
