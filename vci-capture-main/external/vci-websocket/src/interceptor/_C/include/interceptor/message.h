#ifndef VCI_INTERCEPTOR_MESSAGE_H
#define VCI_INTERCEPTOR_MESSAGE_H

#include <chrono>
#include <functional>
#include <future>
#include <memory>
#include <string>

#include "nlohmann/json.hpp"

#include <interceptor/buffer.h>
#include <interceptor/error.h>
#include <interceptor/payload.h>

namespace vci {
namespace interceptor {

// Forward Declarations
class Message;
class MessageIn;
class Connection;

/// Callback type for message responses
using MessageCallbackType = std::function<void(std::shared_ptr<MessageIn>)>;

enum MessageType {
  MessageTypeNotSet = 0,   // Messages type not set properly
  ProtocolMessage = 1,     // Messages not intended for clients
  ErrorMessage = 2,        // Error messages that are not the result of a message
  StandardMessage = 3,     // Normal message which waits for a response
  MonologueMessage = 4,    // Normal message which does not expect a response
  AcknowledeResponse = 5,  // Acknowledge response of a StandardMessage
  ErrorResponse = 6        // Error response of a StandardMessage
};

std::string MessageTypeToString(MessageType type);

/**
 * @brief Hold all data needed for immediately sending a message
 *
 * The header is bson encoded and the buffer that contains the header and payloads can be passed directly to
 * async_write. A reference to the payloads is kept to keep the underlying data valid.
 */
struct SendBuffer {
  int id;
  MessageType message_type;
  std::vector<std::shared_ptr<Payload>> payload;
  std::vector<uint8_t> header;
  std::vector<boost::asio::const_buffer> buffer;
  size_t size;

  SendBuffer(int id_, MessageType message_type_, std::vector<std::shared_ptr<Payload>> payload_,
             std::vector<uint8_t> header_, std::vector<boost::asio::const_buffer> buffer_);
};

/**
 * @brief Returned from async send methods to wait for a response.
 *
 */
class MessagePromise {
  friend Connection;

 public:
  MessagePromise(MessageCallbackType callback = nullptr);
  MessagePromise(MessagePromise&& other);
  MessagePromise& operator=(MessagePromise&& other);

  MessagePromise(const MessagePromise&) = delete;
  MessagePromise& operator=(const MessagePromise&) = delete;

  /**
   * @brief Wait until the response message is received.
   *
   * If an error occurs, the error message can be retrieved using get().
   *
   * @return std::shared_ptr<MessageIn>
   *
   * @exception PathDoesNotExistError
   * @exception MissingAcknowledgeError
   * @exception PathHandlerFailedError
   */
  std::shared_ptr<MessageIn> wait();
  std::shared_ptr<MessageIn> py_wait();

  /**
   * @brief Wait until the response message is received.
   *
   * If an error occurs, the error message can be retrieved using get().
   *
   * @return std::shared_ptr<MessageIn> Response Message
   *
   * @exception TimeoutError When no response is received within timeout_ms
   * @exception PathDoesNotExistError
   * @exception MissingAcknowledgeError
   * @exception PathHandlerFailedError
   */
  std::shared_ptr<MessageIn> wait_for(float timeout_s);
  std::shared_ptr<MessageIn> py_wait_for(float timeout_s);

  /**
   * @brief Returns the message after it has been received and waited for
   *
   * @return std::shared_ptr<MessageIn> The received message or nullptr
   */
  std::shared_ptr<MessageIn> get();

  /**
   * @brief Get the callback
   *
   * @return MessageCallbackType
   */
  MessageCallbackType get_callback();

 protected:
  /**
   * @brief Sets the received message and fulfill future
   *
   * @param message The received message (error or normal)
   */
  void done(std::shared_ptr<MessageIn> message);

 private:
  /// Optional callback for when the message is received. Can be used as an alternative to wait
  MessageCallbackType callback_;
  /// The received message (if any)
  std::shared_ptr<MessageIn> message_ = nullptr;

  std::promise<std::shared_ptr<MessageIn>> promise_;
  std::future<std::shared_ptr<MessageIn>> future_;
  std::mutex mutex_;
};

class Message {
 public:
  int id() const;
  MessageType type() const;
  bool is_error() const;
  bool is_response() const;
  const std::string& path() const;
  const std::string& error() const;
  const std::vector<std::shared_ptr<Payload>>& payload() const;

 protected:
  Message() = default;
  Message(int id, MessageType type = MessageTypeNotSet, const std::string& path = "", const std::string& error = "",
          std::vector<std::shared_ptr<Payload>> payload = std::vector<std::shared_ptr<Payload>>());

 protected:
  int id_ = -1;
  MessageType type_;
  std::string path_;
  std::string error_;
  std::vector<std::shared_ptr<Payload>> payload_;
};

class MessageOut : public Message, public std::enable_shared_from_this<MessageOut> {
  friend class Connection;
  friend class MessageIn;

 public:
  MessageOut() = default;
  MessageOut(const std::string& path, std::shared_ptr<Payload> payload);
  MessageOut(const std::string& path,
             std::vector<std::shared_ptr<Payload>> payload = std::vector<std::shared_ptr<Payload>>());

 protected:
  std::shared_ptr<SendBuffer> make_send_buffer(int id);
  static std::shared_ptr<MessageOut> MakeProtocolMessage(const std::string& path = "",
                                                         std::vector<std::shared_ptr<Payload>> payload = {});
  static std::shared_ptr<MessageOut> MakeAcknowledgeResponse(int original_id, std::string original_path,
                                                             std::vector<std::shared_ptr<Payload>> payload);
  static std::shared_ptr<MessageOut> MakeErrorResponse(int original_id, std::string original_path, std::string error,
                                                       std::vector<std::shared_ptr<Payload>> payload);
};

class MessageIn : public Message, public std::enable_shared_from_this<MessageIn> {
 public:
  MessageIn() = default;
  MessageIn(std::weak_ptr<Connection> connection, std::shared_ptr<Buffer> buffer);
  ~MessageIn();

  /**
   * @brief Acknowledge successful handling of the message. Optionally including data
   */
  void Acknowledge(std::shared_ptr<Payload> payload);
  /**
   * @brief Acknowledge successful handling of the message. Optionally including data
   */
  void Acknowledge(std::vector<std::shared_ptr<Payload>> payload = {});
  /**
   * @brief Acknowledge successful handling of the message. Optionally including data
   */
  void PyAcknowledge(pybind11::object object);
  /**
   * @brief Send an error response to the message. Optionally including data
   */
  void ErrorResponse(std::string error, std::vector<std::shared_ptr<Payload>> payload = {});
  /**
   * @brief Send an error response that the payload was incorrect
   */
  void WrongPayloadResponse(const std::string& description);
  /**
   * @brief Mark as has responded, even without a response. Usefull when shutting down
   */
  void SkipResponse();

  /**
   * @brief true if the message has been responded to
   */
  bool has_responded() const { return has_responded_; }

  std::weak_ptr<Connection> connection() const;

 private:
  std::weak_ptr<Connection> connection_;
  std::shared_ptr<Buffer> buffer_;
  bool has_responded_ = false;
};

}  // namespace interceptor
}  // namespace vci

#endif  // VCI_INTERCEPTOR_MESSAGE_H
