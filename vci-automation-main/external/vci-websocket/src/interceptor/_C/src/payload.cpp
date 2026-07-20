#include <interceptor/payload.h>

#include <iostream>

#include <interceptor/error.h>
#include <pybind11_json.hpp>

namespace vci {
namespace interceptor {

std::string PayloadTypeToString(PayloadType type) {
  switch (type) {
    case RawPtrPayload:
      return "RawPtrPayload";
    case StringPayload:
      return "StringPayload";
    case BsonPayload:
      return "BsonPayload";
    default:
      return "UnknownPayloadType";
  }
}

Payload::Payload(const unsigned char* data, size_t size, PayloadType type) : data_(data), size_(size), type_(type) {}

const unsigned char* Payload::Data() const {
  if (data_ != nullptr) {
    return data_;
  } else {
    return buffer_.data();
  }
}

size_t Payload::Size() const {
  if (data_ != nullptr) {
    return size_;
  } else {
    return buffer_.size();
  }
  return size_;
}

PayloadType Payload::Type() const {
  return type_;
}

std::shared_ptr<Payload> Payload::WrapRawPtr(const unsigned char* data, size_t size, PayloadType type) {
  return std::make_shared<Payload>(data, size, type);
}

std::shared_ptr<Payload> Payload::WrapPyBytes(const pybind11::bytes& data) {
  return std::make_shared<PyBytesPayload>(data);
}

std::shared_ptr<Payload> Payload::FromString(const std::string& data) {
  auto payload = std::make_shared<Payload>();
  payload->buffer_.assign(data.begin(), data.end());
  payload->type_ = PayloadType::StringPayload;
  return payload;
}

std::shared_ptr<Payload> Payload::FromJson(const nlohmann::json& json) {
  std::vector<uint8_t> bson_buffer = nlohmann::json::to_bson(json);
  auto payload = std::make_shared<Payload>();
  payload->buffer_.assign(std::make_move_iterator(bson_buffer.begin()), std::make_move_iterator(bson_buffer.end()));
  payload->type_ = PayloadType::BsonPayload;
  return payload;
}

std::shared_ptr<Payload> Payload::FromDict(const pybind11::dict& py_dict) {
  return FromJson(py_dict);
}

pybind11::memoryview Payload::PyMemoryView() {
  return pybind11::memoryview::from_memory(Data(), Size());
}

std::string Payload::ToString() {
  if (type_ != PayloadType::StringPayload) {
    throw CastPayloadError(PayloadTypeToString(type_), "string");
  }
  return std::string(Data(), Data() + Size());
}

nlohmann::json Payload::ToJson() {
  if (type_ != PayloadType::BsonPayload) {
    throw CastPayloadError(PayloadTypeToString(type_), "json");
  }
  return nlohmann::json::from_bson(Data(), Data() + Size());
}

pybind11::dict Payload::ToDict() {
  if (type_ != PayloadType::BsonPayload) {
    throw CastPayloadError(PayloadTypeToString(type_), "dict");
  }
  return ToJson();
}

PyBytesPayload::PyBytesPayload(const pybind11::bytes& data)
    : Payload(reinterpret_cast<const unsigned char*>(PyBytes_AsString(data.ptr())), PyBytes_Size(data.ptr()),
              PayloadType::RawPtrPayload),
      data_(std::make_shared<ByteWrapper>()) {
  data_->data = data;  // Store the bytes in a shared_ptr to keep it alive
}
}  // namespace interceptor
}  // namespace vci
