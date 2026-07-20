#include "tasks/matting.h"

namespace vci {
namespace gibbs {

Matting::Matting(std::string pt_path) {
  try {
    module_ = torch::jit::load(pt_path);
    module_.to(torch::Device(torch::kCUDA, 0));
  } catch (const c10::Error& e) {
    std::cerr << "error loading the model\n";
  }
  // Warm Up and dtype check
  bool found_dtype = false;
  std::vector<torch::Dtype> dtypes{torch::kFloat16, torch::kFloat32};
  for (const auto& dtype : dtypes) {
    try {
      auto tensor = torch::rand({1, 3, 2304, 2664}, torch::TensorOptions().dtype(dtype).device(torch::kCUDA));
      forward(tensor, tensor);
      forward(tensor, tensor);
      dtype_ = dtype;
      found_dtype = true;
      break;
    } catch (const c10::Error& e) {
      // Did't work
    }
  }
  if (!found_dtype) {
    throw std::runtime_error("Cannot perform forward pass through matting network");
  }
}

torch::Dtype Matting::dtype() const {
  return dtype_;
}

MattingOut Matting::forward(torch::Tensor foreground, torch::Tensor background) {
  // Prepare inputs
  std::vector<torch::jit::IValue> inputs;
  inputs.push_back(foreground);
  inputs.push_back(background);
  // Call Module
  auto output = module_.forward(inputs).toTuple();
  // Return Outputs
  auto mask = output->elements()[0].toTensor();
  auto foreground_out = output->elements()[1].toTensor();
  // Cast back if needed
  // if (mask.dtype() != foreground.dtype()) {
  //   mask = mask.to(foreground.dtype());
  // }
  // if (foreground_out.dtype() != foreground.dtype()) {
  //   foreground_out = foreground_out.to(foreground.dtype());
  // }
  return MattingOut{mask, foreground};
}

GibbsImage Matting::infer(GibbsImage foreground, GibbsImage background) {
  torch::Tensor mask;
  TORCH_CHECK(foreground.image_type == background.image_type, "Foreground and background image types must match.")

  torch::Tensor fg = foreground.get_mattable_tensor(dtype());
  torch::Tensor bg = background.get_mattable_tensor(dtype());
  mask = forward(fg, bg).mask[0][0].to(torch::kFloat32);
  auto ret = GibbsImage(mask, foreground.camera_id, foreground.image_type, foreground.pixel_layout);
  ret.data_category = DataCategory::Matte;
  return ret;
}

}  // namespace gibbs
}  // namespace vci
