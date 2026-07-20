#ifndef CAPTN_BUFFER_ENTRY_H
#define CAPTN_BUFFER_ENTRY_H

#include <stdlib.h>
#include <cstring>
#include <iostream>

#include <interceptor/logging.h>

#include <cstddef>
#include <string>
#include <variant>

#include "util.h"

class AlreadyInQueueError : public ExceptionBase {
 public:
  AlreadyInQueueError();
};

class BufferIsLockedError : public ExceptionBase {
 public:
  BufferIsLockedError();
};

class TransportInterrupted : public ExceptionBase {
 public:
  TransportInterrupted();
};

class BufferIncomplete : public ExceptionBase {
 public:
  BufferIncomplete();
};

class BufferTimeout : public ExceptionBase {
 public:
  BufferTimeout();
};

class GenTLError : public ExceptionBase {
  using ExceptionBase::ExceptionBase;
};

enum class ImageType { Color, Mono, Depth, Undefined };
const char* ImageTypeToString(ImageType type);
ImageType StringToImageType(const std::string& str);

enum class PixelLayout { RGGB, BGGR, GRBG, GBRG, RGB, BGR, Mono, Undefined };
const char* PixelLayoutToString(PixelLayout type);
PixelLayout StringToPixelLayout(const std::string& str);
bool PixelLayoutIsBayer(PixelLayout);

/**
 * @brief
 * Information tied to a Camera instance.
 * It contains info about the camera, that gets passed to captured BufferInfos and later to GibbsImages for downstream
 * processing and identification.
 */
struct CameraInfo {
  std::string camera_id;     // unique. prefix camera_type, suffix last 4 numbers of SN. Assigned by CameraManager.cpp
  ImageType camera_type;     // fixed, native ImageType. Some cameras can have a diverging "current_state"
  std::string manufacturer;  // name of device manufacturer. Ximea, Basler, Simulated, etc ...
  std::string device_model_name;
  int capture_card_index;    // The index by which this camera is locally adressed by its capture_card / API
  std::string serialnumber;  // used for creating the camera_id (prefix by camera_type, suffix last 4 numbers of SN)
};

/**
 * @brief
 * Information tied to a BufferEntry (raw image info returned by cameras).
 * This contains information about how to *unpack the Buffer* into a GibbsImage.
 * Addtionally, contains information that gets passed onto GibbsImage (e.g pixel_layout)
 * for downstream processing.
 * EntryInfo is stored and read from disk by the io cache reader & writer along with BufferEntries.
 */
struct EntryInfo {
 public:
  std::string camera_id = "undefined";
  int height = 512;                              // height in pixels
  int width = 512;                               // width in pixels
  PixelLayout pixel_layout = PixelLayout::BGGR;  // BGGR, RGGB, MONO, RGB
  int bit_depth = 12;                            // itensity bit depth. e.g 8, 10, 12, 14, 16
  int channels = 3;                              // 1 or 3 channels. 1 for mono or raw bayer image.
  bool packed = false;                           // flats if the intenity range is packed in the image_buffer or not
  ImageType image_type = ImageType::Color;       // color, mono, depth or undefined
  int num_bytes = 10000;                         // height*width*channels * (bytes per pixel)
  int unsigned long timestamp_us = 0;
  unsigned long frame_number = 0;  // the frame number as per the camera api

  // store depth scale as an optional parameter
  // std::monostate is a placeholder for types that don't need a custom parameter
  std::variant<std::monostate, float> optional_data;
};
/**
 * @brief
 * wrapper for raw image info returned by a camera.
 * Contains the bytes of a single frame.
 * Information about how to parse and process the BufferEntry is stored in EntryInfo.
 */
class BufferEntry {
 public:
  virtual ~BufferEntry() = default;

  virtual const EntryInfo* Info() const = 0;
  virtual const char* Buffer() const = 0;
  virtual size_t PayloadBytes() const = 0;
  virtual const CameraInfo* GetCameraInfo() const = 0;

  // for writing to file
  virtual size_t WriteTo(std::ofstream& output_file_stream) const = 0;
  virtual size_t WriteTo(int fp) const = 0;

  // lets the buffer know that it can release its data
  virtual void Unlock() = 0;
};

struct WriteQueueEntry {
  BufferEntry* buffer = nullptr;
  int camera_index = 0;
  int frame_index = 0;
};

#endif  // CAPTN_BUFFER_ENTRY_H
