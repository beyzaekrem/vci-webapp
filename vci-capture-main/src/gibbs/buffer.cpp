#include "buffer.h"
#include <interceptor/logging.h>
#include <stdlib.h>
#include <cstring>
#include <iostream>

#include "util.h"

AlreadyInQueueError::AlreadyInQueueError() : ExceptionBase("Buffer is already queued. Cannot queue again.") {};

BufferIsLockedError::BufferIsLockedError() : ExceptionBase("Buffer cannot be queued because it is still locked.") {};

TransportInterrupted::TransportInterrupted() : ExceptionBase("Buffer transport was interrupted. Data is invalid.") {};

BufferIncomplete::BufferIncomplete() : ExceptionBase("Buffer is Incomplete. Data is invalid.") {};

BufferTimeout::BufferTimeout() : ExceptionBase("Buffer operation has timed out.") {};

// Helper function to convert enum to string (used for JSON writing)
const char* ImageTypeToString(ImageType type) {
  switch (type) {
    case ImageType::Color:
      return "Color";
    case ImageType::Mono:
      return "Mono";
    case ImageType::Depth:
      return "Depth";
    default:
      return "Undefined";
  }
}
// Helper function to convert string to enum (used for JSON reading)
ImageType StringToImageType(const std::string& str) {
  if (str == "Color") return ImageType::Color;
  if (str == "Mono") return ImageType::Mono;
  if (str == "Depth") return ImageType::Depth;
  return ImageType::Undefined;
}

// Helper function to convert enum to string (used for JSON writing)
const char* PixelLayoutToString(PixelLayout type) {
  switch (type) {
    case PixelLayout::RGGB:
      return "RGGB";
    case PixelLayout::BGGR:
      return "BGGR";
    case PixelLayout::RGB:
      return "RGB";
    case PixelLayout::BGR:
      return "BGR";
    case PixelLayout::Mono:
      return "Mono";
    case PixelLayout::GBRG:
      return "GBRG";
    case PixelLayout::GRBG:
      return "GRBG";
    default:
      return "Undefined";
  }
}
// Helper function to convert string to enum (used for JSON reading)
PixelLayout StringToPixelLayout(const std::string& str) {
  if (str == "RGGB") return PixelLayout::RGGB;
  if (str == "BGGR") return PixelLayout::BGGR;
  if (str == "GRBG") return PixelLayout::GRBG;
  if (str == "GBRG") return PixelLayout::GBRG;
  if (str == "RGB") return PixelLayout::RGB;
  if (str == "BGR") return PixelLayout::BGR;
  if (str == "Mono") return PixelLayout::Mono;
  return PixelLayout::Undefined;
}
bool PixelLayoutIsBayer(PixelLayout pixel_layout) {
  return (pixel_layout == PixelLayout::RGGB || pixel_layout == PixelLayout::BGGR || pixel_layout == PixelLayout::GRBG ||
          pixel_layout == PixelLayout::GBRG);
}