

#include "image.h"
#include <interceptor/logging.h>
#include <stdlib.h>
#include <cstring>
#include <iostream>

#include "util.h"

const char* DataCategoryToString(DataCategory type) {
  switch (type) {
    case DataCategory::Image:
      return "Image";
    case DataCategory::Matte:
      return "Matte";
    case DataCategory::Background:
      return "Background";
    case DataCategory::Mean:
      return "Mean";
    default:
      return "Undefined";
  }
}

std::string to_lower(std::string data) {
  std::transform(data.begin(), data.end(), data.begin(), [](unsigned char c) { return std::tolower(c); });
  return data;
}

GibbsImage GibbsImage::from_legacy(torch::Tensor t, std::string camera_id, ImageType default_type,
                                   PixelLayout default_layout) {
  // You could add a check here to ensure 't' is actually
  // a raw-looking tensor (e.g. 2D or 1-channel)
  return GibbsImage(t, camera_id, default_type, default_layout);
}

bool GibbsImage::is_bayer() const {
  // Is the enum set to a Bayer pattern?
  bool has_bayer_label = PixelLayoutIsBayer(pixel_layout);

  if (has_bayer_label) {
    // Physical Check: image data MUST be 2D (Height x Width)
    // If it's 3D, someone likely already debayered it or passed an RGB image. In any case, we cant have the
    // pixel_layout mismatching with the data.
    if (pixels.dim() != 2) {
      throw std::runtime_error(std::string("Type Error: Image has a Bayer Layout enum (") +
                               PixelLayoutToString(pixel_layout) + ") but the tensor is " +
                               std::to_string(pixels.dim()) + "D. " + "Bayer kernels require 2D tensors.");
    }
    return true;
  }

  return false;
}

bool GibbsImage::is_mono() const {
  bool has_mono_label = (pixel_layout == PixelLayout::Mono);
  if (has_mono_label) {
    // Physical Check: Mono images should generally be 2D.
    // If they are 3D, the first dimension (channels) must be 1.
    if (pixels.dim() == 3 && pixels.size(0) != 1) {
      throw std::runtime_error("Type Error: Layout is Mono but tensor has " + std::to_string(pixels.size(0)) +
                               " channels.");
    }
  }
  return has_mono_label;
}

bool GibbsImage::is_rgb() const {
  // Layout Check
  bool has_color_label = (pixel_layout == PixelLayout::RGB);

  // thorw runtime erros if the pixel data shape or dimestions dont match.
  if (has_color_label) {
    // Physical Check: Color data must be 3D [C, H, W]
    if (pixels.dim() != 3) {
      throw std::runtime_error("Type Error: Layout is Color but tensor is " + std::to_string(pixels.dim()) +
                               "D. Expected 3D.");
    }
    // Channel Check: must have 3 channels. No [1,H,W]!
    if (pixels.size(0) < 3) {
      throw std::runtime_error("Type Error: Color pixel_layout requires 3 channels, found " +
                               std::to_string(pixels.size(0)));
    }
  }
  return has_color_label;
}

void GibbsImage::save_to_pth(const std::string& filepath) const {
  torch::serialize::OutputArchive archive;

  // Saves a cpu copy of the pixels to pth.
  // original pixels say unchanged.
  at::Tensor cpu_pixels = pixels.to(torch::kCPU).contiguous();
  archive.write("pixels", cpu_pixels);

  // Wrap strings/enums into tensors
  auto id_t = torch::from_blob((void*)camera_id.data(), {(long)camera_id.size()}, torch::kInt8).clone();
  auto meta_t = torch::tensor({(int)image_type, (int)pixel_layout, (int)data_category}, torch::kInt32);

  archive.write("camera_id", id_t);
  archive.write("meta", meta_t);

  archive.save_to(filepath);
}

GibbsImage GibbsImage::load_from_pth(const std::string& filepath) {
  torch::serialize::InputArchive archive;
  archive.load_from(filepath);

  torch::Tensor pix, id_t, meta_t;

  // Read them back using the same keys
  archive.read("pixels", pix);
  archive.read("camera_id", id_t);
  archive.read("meta", meta_t);

  // Convert back to strings/enums
  std::string id(reinterpret_cast<char*>(id_t.data_ptr()), id_t.numel());

  GibbsImage img(pix, id, (ImageType)meta_t[0].item<int>(), (PixelLayout)meta_t[1].item<int>());
  img.data_category = (DataCategory)meta_t[2].item<int>();

  return img;
}