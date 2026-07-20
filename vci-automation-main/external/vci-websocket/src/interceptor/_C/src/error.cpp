
#include <interceptor/error.h>

namespace vci {
namespace interceptor {

const char* MessageError::what() const noexcept {
  return message_.c_str();
}

InvalidMessageError::InvalidMessageError() {
  message_ = "Could not parse the incoming message.";
}

QueueFullError QueueFullError::max_send_queue_length_error(int max_length) {
  QueueFullError error;
  error.reason_ = Reason::MaxSendQueueLength;
  error.message_ = "Queue Full, maximum number of messages reached (" + std::to_string(max_length) + ").";
  return error;
}

QueueFullError QueueFullError::max_buffer_size_error(size_t max_buffer_size) {
  QueueFullError error;
  error.reason_ = Reason::MaxBufferSize;
  error.message_ = "Queue Full, maximum send buffer size reached (" + std::to_string(max_buffer_size) + ").";
  return error;
}

QueueFullError::Reason QueueFullError::reason() const {
  return reason_;
}

NotConnectedError::NotConnectedError() {
  message_ = "Connection is not open, cannot send messages.";
}

PathDoesNotExistError::PathDoesNotExistError(const std::string& path) {
  message_ = "Path '" + path + "' does not exist.";
}

MissingAcknowledgeError::MissingAcknowledgeError() {
  message_ = "Missing acknowledge.";
}

PathHandlerFailedError::PathHandlerFailedError(const std::string& error) {
  message_ = "Path handler failed with the following error:\n" + error;
}

WrongPayloadError::WrongPayloadError(const std::string& description) {
  message_ = description;
}

CastPayloadError::CastPayloadError(const std::string& payload_type, const std::string& target_format) {
  message_ = "Cannot convert payload of type '" + payload_type + "' to '" + target_format + "'.";
}

TimeoutError::TimeoutError(const std::string& action, float timeout_s) {
  if (timeout_s > 0) {
    message_ = "Operation '" + action + "' timed out after " + std::to_string(timeout_s) + " s.";
  } else {
    message_ = "Operation '" + action + "' timed out.";
  }
}

PathAlreadyDefinedError::PathAlreadyDefinedError(std::string path) {
  message_ = "Path '" + path + "' is already defined.";
}

PathAlreadyDefinedError::PathAlreadyDefinedError(std::string path, std::string cls_name) {
  message_ = "Path '" + path + "' is already defined in handler '" + cls_name + "'.";
}

const char* PathAlreadyDefinedError::what() const noexcept {
  return message_.c_str();
};

pybind11::object wrong_payload_error;

}  // namespace interceptor
}  // namespace vci
