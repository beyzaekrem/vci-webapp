#ifndef CAPTN_IMAGE_H
#define CAPTN_IMAGE_H

#include <stdlib.h>
#include <cstring>
#include <iostream>

#include <interceptor/logging.h>

#include <algorithm>  // for std::ranges::transform
#include <cctype>     // for std::tolower
#include <cstddef>
#include <string>
#include <variant>

#include <torch/extension.h>
#include "buffer.h"  // PixelLayout is passed through by Buffer

enum class DataCategory { Image, Matte, Background, Mean, Undefined };
const char* DataCategoryToString(DataCategory type);
std::string to_lower(std::string data);

struct GibbsImage {
  torch::Tensor pixels;
  std::string camera_id = "undefined";
  PixelLayout pixel_layout = PixelLayout::Undefined;  // BGGR, RGGB, RGB, Mono
  ImageType image_type = ImageType::Undefined;        // color, mono, depth

  DataCategory data_category = DataCategory::Image;  // "image", "matte", "background"

  // Default Constructor
  GibbsImage() = default;

  // Initializer Constructor
  GibbsImage(torch::Tensor t, std::string camera_id, ImageType image_type, PixelLayout l)
      : pixels(t), camera_id(camera_id), image_type(image_type), pixel_layout(l) {}

  int64_t size(int64_t dim) const {
    return pixels.size(dim);
  }

  // Returns the device (e.g., cuda:0)
  at::Device device() const {
    return pixels.device();
  }

  caffe2::TypeMeta dtype() const {
    return pixels.dtype();
  }

  // Returns the shape as a list of integers
  c10::IntArrayRef shape() const {
    return pixels.sizes();
  }

  // Creates a clone of the GibbsImage, copying metadata and pixels.
  GibbsImage clone() const {
    GibbsImage new_img = *this;       // Shallow copy metadata and tensor pointer
    new_img.pixels = pixels.clone();  // Deep copy the actual GPU pixel data
    return new_img;
  }

  // Creates a cone of the GibbsImage, copiyng over all metadata, and explicitly setting the pixels to the passed
  // tensor.
  GibbsImage clone_with_pixels(torch::Tensor set_pixels) const {
    GibbsImage new_img = *this;   // Shallow copy metadata
    new_img.pixels = set_pixels;  // set the pixels tensor we are given.
    return new_img;
  }

  // Releases pixel Memory, and reseting metadata to Undefined.
  void release() {
    pixels = torch::Tensor();  // Release Memory
    camera_id = "undefined";
    data_category = DataCategory::Undefined;
    pixel_layout = PixelLayout::Undefined;
    image_type = ImageType::Undefined;
  }
  // Returns true if the pixels tensor is defined and none-empty.
  bool is_valid() const {
    return pixels.defined() && pixels.numel() > 0;
  }

  // Returns the number of dimensions (e.g., 2 for mono, 3 for RGB)
  int64_t ndim() const {
    return pixels.dim();
  }

  c10::ScalarType scalar_type() const {
    return pixels.scalar_type();
  }

  // Checks if the image has 2-dimenstional pixel data, (could be bayer or mono image)
  bool is_mono_ndim() const {
    return pixel_layout == PixelLayout::Mono || pixels.dim() == 2;
  }

  bool defined() const {
    return pixels.defined();
  }

  // Checks if the image has a bayer pixellayout and 2-dimenstional pixel data.
  bool is_bayer() const;

  // Checks if the image has a mono pixellayout and 2-dimenstional pixel data.
  bool is_mono() const;

  // Checks if the image has the RGB pixellayout and 3-dimenstional pixel data.
  bool is_rgb() const;

  GibbsImage to(at::Device device, bool non_blocking) {
    pixels = pixels.to(device, non_blocking);
    return *this;
  }
  GibbsImage cuda(bool non_blocking = false) {
    return to(at::kCUDA, non_blocking);
  }
  GibbsImage cpu(bool non_blocking = false) {
    return to(at::kCPU, non_blocking);
  }

  bool is_cuda() const {
    return pixels.is_cuda();
  }

  torch::Tensor get_mattable_tensor(torch::Dtype dtype) {
    torch::Tensor mattable = pixels.to(dtype);

    // Ensure we have a channel dimension [C, H, W]
    // If shape is [H, W], unsqueeze(0) makes it [1, H, W]
    if (mattable.dim() == 2) {
      mattable = mattable.unsqueeze(0);
    }

    // Expand 1 channel to 3 channels if necessary
    // This is a view: memory is NOT copied.
    if (mattable.size(0) == 1) {
      mattable = mattable.expand({3, -1, -1});
    }
    return mattable.unsqueeze(0);  // another unsqueeze - [1, 3, H, W]
  }

  static GibbsImage from_legacy(torch::Tensor t, std::string camera_id, ImageType default_type = ImageType::Color,
                                PixelLayout default_layout = PixelLayout::BGGR);

  void save_to_pth(const std::string& filepath) const;
  static GibbsImage load_from_pth(const std::string& filepath);

  std::string repr() {
    std::stringstream ss;
    ss << "<GibbsImage camera_id=" << camera_id << " shape=" << pixels.sizes()
       << " pixel_layout=" << PixelLayoutToString(pixel_layout) << " image_type=" << ImageTypeToString(image_type)
       << " data_category=" << DataCategoryToString(data_category) << " device=" << pixels.device() << ">";
    return ss.str();
  }
};

struct EncodedImage {
  torch::Tensor data;                // encoded tensor, shape and dim depends on format
  std::string format = "undefined";  // "jpg", "png", "avif"

  // parsed from GibbsImage
  std::string camera_id = "undefined";
  DataCategory data_category = DataCategory::Undefined;  // "image", "matte", "background"
  ImageType image_type = ImageType::Undefined;           // "color", "mono", etc.
  std::vector<int64_t> shape;                            // The ORIGINAL [C, H, W] before encoding

  EncodedImage() = default;

  EncodedImage to(at::Device device, bool non_blocking) {
    data = data.to(device, non_blocking);
    return *this;
  }

  EncodedImage cuda(bool non_blocking = false) {
    return this->to(at::kCUDA, non_blocking);
  }
  EncodedImage cpu(bool non_blocking = false) {
    return this->to(at::kCPU, non_blocking);
  }

  bool is_cuda() {
    return data.is_cuda();
  }

  EncodedImage(torch::Tensor encoded_data, const GibbsImage& source, std::string format)
      : data(encoded_data),
        camera_id(source.camera_id),
        data_category(source.data_category),
        image_type(source.image_type),
        shape(source.pixels.sizes().vec()),  // Take shape from the tensor
        format(std::move(format)) {};

  // Helper to return the metadata as a Python dictionary
  py::dict to_dict() const {
    py::dict d;
    d["camera_id"] = camera_id;
    d["data_category"] = to_lower(DataCategoryToString(data_category));
    d["image_type"] = to_lower(ImageTypeToString(image_type));
    d["shape"] = shape;
    d["format"] = format;
    return d;
  }

  std::string repr() {
    std::stringstream ss;
    ss << "<EncodedImage camera_id=" << camera_id << " shape=" << data.sizes()
       << " image_type=" << ImageTypeToString(image_type) << " data_category=" << DataCategoryToString(data_category)
       << " format=" << format << " device=" << data.device() << ">";
    return ss.str();
  }
};

#endif  // CAPTN_IMAGE_H