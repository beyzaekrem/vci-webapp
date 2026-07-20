#include <interceptor/message.h>

#include <iostream>

#include <interceptor/connection.h>
#include <interceptor/logging.h>

namespace vci {
namespace interceptor {

std::string MessageTypeToString(MessageType type) {
  switch (type) {
    case MessageTypeNotSet:
      return "MessageTypeNotSet";
    case ProtocolMessage:
      return "ProtocolMessage";
    case ErrorMessage:
      return "ErrorMessage";
    case StandardMessage:
      return "StandardMessage";
    case MonologueMessage:
      return "MonologueMessage";
    case AcknowledeResponse:
      return "AcknowledeResponse";
    case ErrorResponse:
      return "ErrorResponse";
    default:
      return "UnknownMessageType";
  }
}

SendBuffer::SendBuffer(int id_, MessageType message_type_, std::vector<std::shared_ptr<Payload>> payload_,
                       std::vector<uint8_t> header_, std::vector<boost::asio::const_buffer> buffer_)
    : id(id_),
      message_type(message_type_),
      payload(std::move(payload_)),
      header(std::move(header_)),
      buffer(std::move(buffer_)),
      size(0) {
  for (const auto& b : buffer) {
    size += b.size();
  }
}

MessagePromise::MessagePromise(MessageCallbackType callback)
    : callback_(std::move(callback)), promise_(), future_(promise_.get_future()) {}

MessagePromise::MessagePromise(MessagePromise&& other)
    : callback_(std::move(other.callback_)), promise_(std::move(other.promise_)), future_(std::move(other.future_)) {}

MessagePromise& MessagePromise::operator=(MessagePromise&& other) {
  if (this != &other) {
    callback_ = std::move(other.callback_);
    promise_ = std::move(other.promise_);
    future_ = std::move(other.future_);
  }
  return *this;
}

std::shared_ptr<MessageIn> MessagePromise::wait() {
  return wait_for(-1);
}

std::shared_ptr<MessageIn> MessagePromise::py_wait() {
  pybind11::gil_scoped_release release;
  return wait();
}

std::shared_ptr<MessageIn> MessagePromise::wait_for(float timeout_s) {
  if (message_ != nullptr) {
    return message_;
  }
  // Split waiting into shorter waits to avoid hanging indefinitely
  int timeout_ms = timeout_s <= 0 ? timeout_s : ceilf(1000.f * timeout_s);
  int remaining_timout_ms = timeout_ms;
  while (remaining_timout_ms != 0) {
    int short_timeout_ms = 100;
    if (remaining_timout_ms > 0 && remaining_timout_ms < short_timeout_ms) {
      short_timeout_ms = remaining_timout_ms;
    }
    if (future_.wait_for(std::chrono::milliseconds(short_timeout_ms)) == std::future_status::ready) {
      message_ = future_.get();
      if (message_->is_error()) {
        if (message_->error() == PathDoesNotExistError::error_string) {
          // PathDoesNotExistError
          logger()->warn("Received error message (ID: {}): Path {} does not exist.", message_->id(), message_->path());
          throw PathDoesNotExistError(message_->path());
        } else if (message_->error() == MissingAcknowledgeError::error_string) {
          // MissingAcknowledgeError
          logger()->warn("Received error message (ID: {}): Missing acknowledge.", message_->id());
          throw MissingAcknowledgeError();
        } else if (message_->error() == PathHandlerFailedError::error_string) {
          // PathHandlerFailedError
          std::string error_message;
          if (message_->payload().size() > 0) {
            try {
              error_message = message_->payload()[0]->ToString();
            } catch (...) {
              error_message = "Error message could not be parsed.";
            }
          }
          logger()->warn("Received error message (ID: {}): Path handler failed: {}", message_->id(), error_message);
          throw PathHandlerFailedError(error_message);
        } else if (message_->error() == WrongPayloadError::error_string) {
          // WrongPayloadError
          std::string error_message;
          if (message_->payload().size() > 0) {
            try {
              error_message = message_->payload()[0]->ToJson()["what"];
            } catch (...) {
              error_message = "Error message could not be parsed.";
            }
          }
          logger()->warn("Received error message (ID: {}): Wrong payload: {}", message_->id(), error_message);
          throw WrongPayloadError(error_message);
        } else {
          logger()->warn("Received error message (ID: {}): Unspecified error.", message_->id());
        }
      }
      return message_;
    }
    if (remaining_timout_ms > 0) {
      remaining_timout_ms -= short_timeout_ms;
    }
  }
  throw TimeoutError("MessagePromise::wait", timeout_s);
}

std::shared_ptr<MessageIn> MessagePromise::py_wait_for(float timeout_s) {
  pybind11::gil_scoped_release release;
  return wait_for(timeout_s);
}

std::shared_ptr<MessageIn> MessagePromise::get() {
  return message_;
}

MessageCallbackType MessagePromise::get_callback() {
  return callback_;
}

void MessagePromise::done(std::shared_ptr<MessageIn> message) {
  promise_.set_value(message);
}

Message::Message(int id, MessageType type, const std::string& path, const std::string& error,
                 std::vector<std::shared_ptr<Payload>> payload)
    : id_(id), type_(type), path_(path), error_(error), payload_(payload) {}

int Message::id() const {
  return id_;
}
MessageType Message::type() const {
  return type_;
}

bool Message::is_error() const {
  return (type_ == ErrorMessage || type_ == ErrorResponse);
}

bool Message::is_response() const {
  return (type_ == AcknowledeResponse || type_ == ErrorResponse);
}

const std::string& Message::path() const {
  return path_;
}

const std::string& Message::error() const {
  return error_;
}

const std::vector<std::shared_ptr<Payload>>& Message::payload() const {
  return payload_;
}

MessageOut::MessageOut(const std::string& path, std::shared_ptr<Payload> payload)
    : MessageOut(path, std::vector<std::shared_ptr<Payload>>({payload})) {}

MessageOut::MessageOut(const std::string& path, std::vector<std::shared_ptr<Payload>> payload)
    : Message(-1, MessageTypeNotSet, path, "", payload) {}

std::shared_ptr<SendBuffer> MessageOut::make_send_buffer(int id) {
  //////////////////////////////////////////////////////////////////////////////
  // Validate
  //////////////////////////////////////////////////////////////////////////////
  // Set Type depending on available callback
  if (type_ == MessageTypeNotSet || type_ == StandardMessage || type_ == MonologueMessage) {
    // if (callback_) {
    type_ = StandardMessage;
    // } else {
    //   type_ = MonologueMessage;
    // }
  }

  //////////////////////////////////////////////////////////////////////////////
  // Bson encode header
  //////////////////////////////////////////////////////////////////////////////
  nlohmann::json data = {
      {"TYPE", type_},
      {"ID", id},
  };
  if (path_.size() > 0) {
    data["PATH"] = path_;
  }
  if (error_.size() > 0) {
    data["ERROR"] = error_;
  }
  if (payload_.size() > 0) {
    nlohmann::json payload_data = nlohmann::json::array();
    for (const auto& payload : payload_) {
      if (payload == nullptr) {
        logger()->error("Nullptr payload");
      }
      payload_data.push_back({
          {"SIZE", payload->Size()},
          {"TYPE", payload->Type()},
      });
      // ADD META
    }
    data["PAYLOAD"] = payload_data;
  }
  auto header = nlohmann::json::to_bson(data);

  //////////////////////////////////////////////////////////////////////////////
  // Build buffer list
  //////////////////////////////////////////////////////////////////////////////
  std::vector<boost::asio::const_buffer> buffer;
  buffer.reserve(1 + payload_.size());
  buffer.push_back(boost::asio::const_buffer(header.data(), header.size()));
  for (auto& payload : payload_) {
    buffer.push_back(boost::asio::const_buffer(payload->Data(), payload->Size()));
  }
  return std::make_shared<SendBuffer>(id, type_, payload_, std::move(header), std::move(buffer));
}

std::shared_ptr<MessageOut> MessageOut::MakeProtocolMessage(const std::string& path,
                                                            std::vector<std::shared_ptr<Payload>> payload) {
  auto message = std::make_shared<MessageOut>();
  message->type_ = ProtocolMessage;
  message->path_ = path, message->payload_ = payload;
  return message;
}

std::shared_ptr<MessageOut> MessageOut::MakeAcknowledgeResponse(int original_id, std::string original_path,
                                                                std::vector<std::shared_ptr<Payload>> payload) {
  auto message = std::make_shared<MessageOut>();
  message->id_ = original_id;
  message->type_ = AcknowledeResponse;
  message->path_ = original_path, message->payload_ = payload;
  return message;
}

std::shared_ptr<MessageOut> MessageOut::MakeErrorResponse(int original_id, std::string original_path, std::string error,
                                                          std::vector<std::shared_ptr<Payload>> payload) {
  auto message = std::make_shared<MessageOut>();
  message->id_ = original_id;
  message->type_ = ErrorResponse;
  message->path_ = original_path;
  message->error_ = error;
  message->payload_ = payload;
  return message;
}

MessageIn::MessageIn(std::weak_ptr<Connection> connection, std::shared_ptr<Buffer> buffer)
    : Message(), connection_(connection), buffer_(buffer) {
  const unsigned char* buffer_ptr = buffer_->Data();
  // Parse header
  int32_t header_size = *reinterpret_cast<const int32_t*>(buffer_ptr);
  nlohmann::json header;
  try {
    header = nlohmann::json::from_bson(buffer_->Data(), buffer_->Data() + header_size);
  } catch (nlohmann::json::parse_error& e) {
    throw InvalidMessageError();
  }
  buffer_ptr += header_size;
  type_ = static_cast<MessageType>(header["TYPE"]);
  id_ = header["ID"];
  path_ = header.value("PATH", "");
  error_ = header.value("ERROR", "");
  // std::cout << "Got message:" << std::endl <<
  //   "- TYPE: " << MessageTypeToString(type_)  << std::endl <<
  //   "- ID: " << id_  << std::endl <<
  //   "- PATH: " << path_  << std::endl <<
  //   "- ERROR: " << error_  << std::endl;
  // Add payload
  if (header["PAYLOAD"].size() > 0) {
    // std::cout << "Payloads: (" << header["PAYLOAD"].size() << ")" << std::endl;
    for (nlohmann::json::iterator it = header["PAYLOAD"].begin(); it != header["PAYLOAD"].end(); ++it) {
      size_t payload_size = (*it)["SIZE"];
      PayloadType type = static_cast<PayloadType>((*it)["TYPE"]);
      payload_.push_back(Payload::WrapRawPtr(buffer_ptr, payload_size, type));
      buffer_ptr += payload_size;
      // std::cout << "  - Payload size: " << payload_size << std::endl;
      // std::cout << "  - Payload type: " << payload_type << std::endl;
    }
  }
}

MessageIn::~MessageIn() {
  buffer_->Release();
  // std::cout << "MessageIn Destructor (" << id_ << ")" << std::endl;
  if (type_ == StandardMessage && !has_responded_) {
    logger()->warn("Missing acknowledge for message PATH={}, sending MissingAcknowledgeError", path_);
    try {
      ErrorResponse(MissingAcknowledgeError::error_string);
    } catch (NotConnectedError& e) {
      // Ignore
    } catch (QueueFullError& e) {
      // Ignore
    } catch (...) {
      logger()->warn("Unexpected error in automatic Error response.");
    }
  }
}

void MessageIn::Acknowledge(std::shared_ptr<Payload> payload) {
  Acknowledge(std::vector<std::shared_ptr<Payload>>{payload});
}

void MessageIn::Acknowledge(std::vector<std::shared_ptr<Payload>> payload) {
  if (!has_responded_ && (type_ == StandardMessage || type_ == ProtocolMessage)) {
    has_responded_ = true;
    if (std::shared_ptr<Connection> connection = connection_.lock()) {
      try {
        auto message = MessageOut::MakeAcknowledgeResponse(id_, path_, payload);
        connection->async_send_and_forget(std::move(message));
      } catch (NotConnectedError& e) {
        logger()->debug("Failed to send acknowledge message, connection closed.");
      } catch (QueueFullError& e) {
        logger()->warn("Failed to send acknowledge message, queue full.");
      }
    }
  }
}

void MessageIn::PyAcknowledge(pybind11::object object) {
  if (object.is_none()) {
    Acknowledge();
  } else if (pybind11::isinstance<Payload>(object)) {
    Acknowledge(object.cast<std::shared_ptr<Payload>>());
  } else if (pybind11::isinstance<pybind11::sequence>(object)) {
    std::vector<std::shared_ptr<Payload>> payloads;
    for (auto item : object.cast<pybind11::sequence>()) {
      if (!pybind11::isinstance<Payload>(item)) {
        throw std::runtime_error("All elements must be Payloads.");
        // TODO: Better error
      }
      payloads.push_back(item.cast<std::shared_ptr<Payload>>());
    }
    Acknowledge(payloads);
  } else {
    throw std::runtime_error("Invalid type passed to PyAcknowledge.");
    // TODO: Better error
  }
}

void MessageIn::ErrorResponse(std::string error, std::vector<std::shared_ptr<Payload>> payload) {
  // std::cout << "MessageIn::ErrorResponse" << std::endl;
  if (!has_responded_ && type_ == StandardMessage) {
    has_responded_ = true;
    if (std::shared_ptr<Connection> connection = connection_.lock()) {
      auto message = MessageOut::MakeErrorResponse(id_, path_, error, payload);
      connection->async_send_and_forget(std::move(message));
    }
  }
}

void MessageIn::WrongPayloadResponse(const std::string& description) {
  if (!has_responded_ && type_ == StandardMessage) {
    has_responded_ = true;
    if (std::shared_ptr<Connection> connection = connection_.lock()) {
      nlohmann::json error_data;
      error_data["description"] = description;
      auto message =
          MessageOut::MakeErrorResponse(id_, path_, WrongPayloadError::error_string, {Payload::FromJson(error_data)});
      connection->async_send_and_forget(std::move(message));
    }
  }
}

void MessageIn::SkipResponse() {
  has_responded_ = true;
}

std::weak_ptr<Connection> MessageIn::connection() const {
  return connection_;
}

}  // namespace interceptor
}  // namespace vci
