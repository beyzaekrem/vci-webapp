#ifndef VCI_INTERCEPTOR_ERROR_H
#define VCI_INTERCEPTOR_ERROR_H

#include <pybind11/pybind11.h>
#include <exception>
#include <string>

namespace vci {
namespace interceptor {

/**
 * @brief Base class of all message related errors
 */
class MessageError : public std::exception {
 public:
  virtual const char* what() const noexcept override;
  std::string message_ = "Generic Message Error";
};

// MARK: Send Errors

/**
 * @brief A message cannot be sent because the message queue is full.
 */
class QueueFullError : public MessageError {
 public:
  enum class Reason { MaxSendQueueLength, MaxBufferSize };
  static QueueFullError max_send_queue_length_error(int max_length);
  static QueueFullError max_buffer_size_error(size_t max_buffer_size);

  Reason reason() const;

 private:
  Reason reason_;
};

/**
 * @brief An action cannot be performed, because the connection is closed.
 */
class NotConnectedError : public MessageError {
 public:
  NotConnectedError();
};

// MARK: Read Errors

/**
 * @brief Could not parse the incoming message header
 */
class InvalidMessageError : public MessageError {
 public:
  InvalidMessageError();
};

/**
 * @brief There is no handler for the specified path
 */
class PathDoesNotExistError : public MessageError {
 public:
  static constexpr const char* error_string = "INTERCEPTOR::PathDoesNotExist";
  PathDoesNotExistError(const std::string& path);
};

/**
 * @brief No error occured, but the message was not acknowledged
 */
class MissingAcknowledgeError : public MessageError {
 public:
  static constexpr const char* error_string = "INTERCEPTOR::MissingAcknowledge";
  MissingAcknowledgeError();
};

/**
 * @brief An error occued during execution of the path handler
 */
class PathHandlerFailedError : public MessageError {
 public:
  static constexpr const char* error_string = "INTERCEPTOR::PathHandlerFailed";
  PathHandlerFailedError(const std::string& error);
};

/**
 * @brief The payload did not follow the required specifications
 */
class WrongPayloadError : public MessageError {
 public:
  static constexpr const char* error_string = "INTERCEPTOR::WrongPayloadError";
  WrongPayloadError(const std::string& description);
};

/**
 * @brief The payload cannot be cast to the desiged format
 */
class CastPayloadError : public MessageError {
 public:
  static constexpr const char* error_string = "INTERCEPTOR::IncompatiblePayloadError";
  CastPayloadError(const std::string& payload_type, const std::string& target_format);
};

class TimeoutError : public MessageError {
 public:
  TimeoutError(const std::string& action, float timeout_s);
};

// MARK: Handler Errors

class PathAlreadyDefinedError : public std::exception {
 public:
  PathAlreadyDefinedError(std::string path);
  PathAlreadyDefinedError(std::string path, std::string cls_name);
  virtual const char* what() const noexcept override;
  std::string message_;
};

// MARK: Python Bindings

extern pybind11::object wrong_payload_error;

}  // namespace interceptor
}  // namespace vci

#endif  // VCI_INTERCEPTOR_ERROR_H
