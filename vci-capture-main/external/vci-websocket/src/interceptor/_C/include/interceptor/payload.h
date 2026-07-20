#ifndef VCI_INTERCEPTOR_PAYLOAD_H
#define VCI_INTERCEPTOR_PAYLOAD_H

#include <memory.h>

#include <pybind11/pybind11.h>
#include "nlohmann/json.hpp"

namespace vci {
namespace interceptor {

enum PayloadType {
  RawPtrPayload = 0,  // Raw buffer
  StringPayload = 1,  // String
  BsonPayload = 2,    // bson (Can be cast from/to json and python dict)
};

std::string PayloadTypeToString(PayloadType type);

/**
 * @brief Payload of a message
 */
class Payload {
  // Need convenience functions to convert strings and stuff
 public:
  Payload() = default;
  Payload(const unsigned char* data, size_t size, PayloadType type_ = PayloadType::RawPtrPayload);
  virtual ~Payload() = default;

  const unsigned char* Data() const;
  size_t Size() const;
  PayloadType Type() const;
  nlohmann::json get_meta() const;

  // "Wrap" methods reference the data without any copy
  // (fast, but make sure to not change before send is finished)
  static std::shared_ptr<Payload> WrapRawPtr(const unsigned char* data, size_t size,
                                             PayloadType type = PayloadType::RawPtrPayload);
  static std::shared_ptr<Payload> WrapPyBytes(const pybind11::bytes& data);

  // "From" methods make a copy whenn called
  // (slower than wrap, but safer)
  static std::shared_ptr<Payload> FromString(const std::string& data);
  static std::shared_ptr<Payload> FromJson(const nlohmann::json& json);
  static std::shared_ptr<Payload> FromDict(const pybind11::dict& py_dict);

  pybind11::memoryview PyMemoryView();
  std::string ToString();
  nlohmann::json ToJson();
  pybind11::dict ToDict();

 private:
  const unsigned char* data_ = nullptr;
  size_t size_ = 0;
  PayloadType type_;
  nlohmann::json meta_;                // For internal use
  std::vector<unsigned char> buffer_;  // For converted data
};

/**
 * @brief Wrapper for pybind11::bytes to keep it alive but allow acquiring the GIL before destruction
 */
struct __attribute__((visibility("default"))) ByteWrapper {
  pybind11::bytes data;
};

/**
 * @brief Extension that stores the underlying bytes object to avoid destruction
 *
 */
class __attribute__((visibility("default"))) PyBytesPayload : public Payload {
 public:
  PyBytesPayload(const pybind11::bytes& data);

  ~PyBytesPayload() {
    pybind11::gil_scoped_acquire acquire;  // Ensure GIL is held during destruction
    data_ = nullptr;
  }

 private:
  std::shared_ptr<ByteWrapper> data_;
};

}  // namespace interceptor
}  // namespace vci

#endif  // VCI_INTERCEPTOR_PAYLOAD_H
