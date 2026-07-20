#include <interceptor/connection.h>
#include <interceptor/logging.h>

namespace vci {
namespace interceptor {

Connection::Connection(std::shared_ptr<boost::asio::io_context> ioc_net,
                       std::shared_ptr<boost::asio::io_context> ioc_handler,
                       std::shared_ptr<boost::asio::strand<boost::asio::io_context::executor_type>> strand_net,
                       boost::asio::ip::tcp::socket&& socket, std::weak_ptr<ConnectionHolder> connection_holder)
    : is_open_(false),
      current_buffer_(nullptr),
      ioc_net_(ioc_net),
      ioc_handler_(ioc_handler),
      strand_net_(strand_net),
      ws_(std::move(socket)),
      connection_holder_(connection_holder),
      promise_map_() {
  // Store info
  auto remote_endpoint = ws_.next_layer().socket().remote_endpoint();
  endpoint_address_ = remote_endpoint.address().to_string();
  endpoint_port_ = remote_endpoint.port();
}

Connection::~Connection() {}

bool Connection::IsOpen() {
  return is_open_;
}

void Connection::stop() {
  // Don't do anything if already stopped
  if (!is_open_) {
    return;
  }
  // Dispatch close call to net strand and create future to wait for later
  logger()->debug("Connection ({}:{}) stop() called. Attempting to close gracefully.", endpoint_address_,
                  endpoint_port_);
  std::promise<void> promise;
  std::future<void> future = promise.get_future();
  boost::asio::dispatch(*strand_net_, [self = shared_from_this(), promise = std::move(promise)]() mutable {
    if (self->is_open_) {
      // Async close if open
      self->is_open_ = false;
      self->ws_.async_close(boost::beast::websocket::close_code::normal,
                            [self, promise = std::move(promise)](boost::system::error_code ec) mutable {
                              // Not on any strand
                              bool graceful = true;
                              if (ec) {
                                graceful = false;
                                logger()->error("Connection: Failed to close websocket connection: {}", ec.message());
                              }
                              if (auto connection_holder = self->connection_holder_.lock()) {
                                connection_holder->connection_closed(self, graceful, false);
                              }
                              promise.set_value();
                            });
    }
  });
  // Wait as long as the io_context is not stopped
  while (!ioc_net_->stopped()) {
    if (future.wait_for(std::chrono::microseconds(1)) == std::future_status::timeout) {
      // Not done yet, continue waiting, polling to avoid potential deadlock
      ioc_net_->poll_one();
    } else {
      // Promise fulfilled, done
      break;
    }
  }
}

std::shared_ptr<MessagePromise> Connection::async_send(std::shared_ptr<MessageOut> message,
                                                       MessageCallbackType callback, float timeout_s,
                                                       bool send_and_forget) {
  // Check
  if (!is_open_) {
    if (message->is_error()) {
      logger()->debug("Connection ({}:{}) attempting to send message {} (ERROR={}), but not open.", endpoint_address_,
                      endpoint_port_, MessageTypeToString(message->type()), message->error(), message->is_response());
    } else {
      logger()->debug("Connection ({}:{}) attempting to send message {} (PATH={}), but not open.", endpoint_address_,
                      endpoint_port_, MessageTypeToString(message->type()), message->path(), message->is_response());
    }
    throw NotConnectedError();
  }
  // Message id
  int id = message->id();
  if (id < 0) {
    static int counter = 0;
    static std::mutex mtx;
    std::lock_guard<std::mutex> lock(mtx);
    if (counter == std::numeric_limits<int>::max()) {
      counter = 0;
    }
    id = counter++;
  }
  // Promise if required
  std::shared_ptr<MessagePromise> promise;
  if (!send_and_forget) {
    promise = std::make_shared<MessagePromise>(callback);
    {
      std::lock_guard<std::mutex> lock(promise_map_mutex_);
      promise_map_[id] = promise;
    }
  }
  // Timeout
  if (timeout_s > 0) {
    throw std::runtime_error("Timeout not implemented");
    // boost::asio::steady_timer timer(*ioc_net_,
    // boost::asio::chrono::milliseconds(timeout_ms)); timer.async_wait([self,
    // timer = std::move(timer), id](const boost::system::error_code& ec) {
    //     if (!ec) {
    //       // Remove callback
    //       auto callback = self->callback_map_.find(id);
    //       if (callback != self->callback_map_.end()) {
    //         // Oh no, still there
    //         // TODO: Error handling
    //         self->callback_map_.erase(id);
    //       } else {
    //         // Nothing to do, has been processed
    //       }
    //     }
    // });
  }
  // Build message and add to queue
  auto send_buffer = message->make_send_buffer(id);
  logger()->debug("Connection ({}:{}) adding message to send queue (ID: {})", endpoint_address_, endpoint_port_, id);
  {
    std::lock_guard<std::mutex> lock(send_queue_mutex_);
    // Full check
    if (send_queue_.size() >= max_send_queue_length_) {
      throw QueueFullError::max_send_queue_length_error(max_send_queue_length_);
    }
    if (send_queue_size_ >= max_send_queue_size_) {
      throw QueueFullError::max_buffer_size_error(max_send_queue_size_);
    }
    send_queue_size_ += send_buffer->size;
    send_queue_.push(send_buffer);
  }
  DoSend();
  return promise;
}

void Connection::async_send_and_forget(std::shared_ptr<MessageOut> message) {
  Connection::async_send(std::move(message), nullptr, 0, true);
}

bool Connection::is_queue_full() const {
  if (send_queue_.size() >= max_send_queue_length_) {
    return true;
  }
  if (send_queue_size_ >= max_send_queue_size_) {
    return true;
  }
  return false;
}

float Connection::Ping() {
  auto start_time = std::chrono::high_resolution_clock::now();
  auto message = MessageOut::MakeProtocolMessage("PING", {});
  auto promise = async_send(message);
  // Wait until we get a response
  // TODO: Keep ioc_net busy
  auto pong = promise->wait_for(1.f);
  if (pong == nullptr) {
    logger()->warn("No Ping after 1s...");
    return 1.f;
  }
  auto end_time = std::chrono::high_resolution_clock::now();
  auto elapsed_time = std::chrono::duration_cast<std::chrono::nanoseconds>(end_time - start_time);
  return static_cast<float>(elapsed_time.count()) / 1.0e6f;
}

std::shared_ptr<MessageHandler> Connection::GetHandler(std::weak_ptr<Connection> connection) {
  if (auto connection_shared = connection.lock()) {
    if (auto connection_holder = connection_shared->connection_holder_.lock()) {
      return connection_holder->handler();
    }
  }
  return nullptr;
}

void Connection::OnAccept(boost::beast::error_code ec) {
  if (ec) {
    if (auto connection_holder = connection_holder_.lock()) {
      connection_holder->connection_not_opened(shared_from_this());
    }
    return;
  }
  is_open_ = true;
  //
  logger()->debug("Connection: OnAccept / is open (Endpoint {}:{})", endpoint_address_, endpoint_port_);
  DoRead();
  if (auto connection_holder = connection_holder_.lock()) {
    connection_holder->connection_opened(shared_from_this());
  }
}

void Connection::DoRead() {
  // Check if connection is open and no read in progress (current_buffer_)
  if (is_open_ && current_buffer_ == nullptr) {
    // Read a message into our buffer
    current_buffer_ = BufferManager::GetNewBuffer();
    ws_.async_read(
        current_buffer_->GetBuffer(),
        boost::asio::bind_executor(
            *strand_net_, [self_weak = weak_from_this()](boost::beast::error_code ec, std::size_t bytes_transferred) {
              if (auto self = self_weak.lock()) {
                self->OnRead(ec, bytes_transferred);
              }
            }));
  }
}

void Connection::OnRead(boost::beast::error_code ec, std::size_t bytes_transferred) {
  boost::ignore_unused(bytes_transferred);
  // Already closed
  if (!is_open_) {
    if (ec == boost::asio::error::operation_aborted) {
      // Expected behavior
      logger()->debug("Connection ({}:{}) OnRead ASIO operation aborted after stopping (as expected).",
                      endpoint_address_, endpoint_port_);
    } else {
      logger()->debug("Connection ({}:{}) received a message, but was already closed (not expected).",
                      endpoint_address_, endpoint_port_);
    }
    return;
  }
  // Close on Error
  if (ec) {
    if (ec == boost::beast::websocket::error::closed) {
      // Debug, too common
      logger()->debug("Connection ({}:{}) received a close message.", endpoint_address_, endpoint_port_);
    } else if (ec == boost::asio::error::eof) {
      // Debug, too common
      logger()->debug("Connection ({}:{}) received an EOF.", endpoint_address_, endpoint_port_);
    } else {
      logger()->error("Connection: OnRead got error {}, {}: {}", ec.category().name(), ec.value(), ec.message());
    }
    current_buffer_->Release();
    is_open_ = false;
    // Clear queue
    {
      std::lock_guard<std::mutex> lock(send_queue_mutex_);
      int num_abandoned_msg = send_queue_.size();
      while (!send_queue_.empty()) {
        send_queue_.pop();
      }
      if (num_abandoned_msg > 0) {
        logger()->warn("Closing connection ({}:{}) resulted in {} messages not being sent.", endpoint_address_,
                       endpoint_port_, num_abandoned_msg);
      }
    }
    if (auto connection_holder = connection_holder_.lock()) {
      connection_holder->connection_closed(shared_from_this(), ec == boost::beast::websocket::error::closed, true);
    }
    return;
  }

  // Start another read
  auto buffer = std::move(current_buffer_);
  DoRead();

  // Build message
  std::shared_ptr<MessageIn> message;
  try {
    message = std::make_shared<MessageIn>(weak_from_this(), std::move(buffer));
  } catch (InvalidMessageError& e) {
    logger()->error("Connection ({}:{}) Received invalid message!", endpoint_address_, endpoint_port_);
    return;
  }

  // Handle message
  if (message->type() == ProtocolMessage) {
    if (message->path() == "PING") {
      logger()->debug("Connection ({}:{}) received PING (ID: {})", endpoint_address_, endpoint_port_, message->id());
      message->Acknowledge();
    } else {
      logger()->error("Connection: ProtocolMessage path '{}' undefined.", message->path());
    }
  } else if (message->type() == ErrorMessage) {
    logger()->debug("Connection ({}:{}) received error message (ID: {})", endpoint_address_, endpoint_port_,
                    message->id());
    auto handler = GetHandler(shared_from_this());
    if (handler) {
      boost::asio::dispatch(*ioc_handler_, [message = std::move(message)]() {
        if (auto handler = GetHandler(message->connection())) {
          handler->OnError(message);
        }
      });
    }
  } else if (message->type() == StandardMessage || message->type() == MonologueMessage) {
    logger()->debug("Connection ({}:{}) received standard message (ID: {})", endpoint_address_, endpoint_port_,
                    message->id());
    auto handler = GetHandler(shared_from_this());
    if (handler) {
      boost::asio::dispatch(*ioc_handler_, [message = std::move(message)]() {
        if (auto handler = GetHandler(message->connection())) {
          try {
            bool handled = handler->dispatch(message);
            if (!handled &&
                !message->has_responded()) {  // Check if dispatch return was a lie and user has responded #trustissues
              logger()->error("Connection: No handler for message path {}", message->path());
              message->ErrorResponse(PathDoesNotExistError::error_string);
            }
          } catch (NotConnectedError& e) {
            logger()->debug("Connection could not respond to message, connection already closed (ID: {})",
                            message->id());
          }
        }
      });
    }
  } else if (message->type() == AcknowledeResponse || message->type() == ErrorResponse) {
    logger()->debug("Connection ({}:{}) received response (ID: {})", endpoint_address_, endpoint_port_, message->id());
    FindAndExecuteCallback(std::move(message));
  } else {
    logger()->error("Connection: Unkown message type: {}", int(message->type()));
    // TODO: Handle
  }
}

void Connection::FindAndExecuteCallback(std::shared_ptr<MessageIn> message) {
  std::lock_guard<std::mutex> lock(promise_map_mutex_);
  const int id = message->id();
  auto promise_entry = promise_map_.find(message->id());
  if (promise_entry != promise_map_.end()) {
    auto promise = std::move(promise_entry->second);
    // Call Done
    promise->done(message);
    // Dispatch Callback if needed
    if (auto callback = promise->get_callback()) {
      boost::asio::dispatch(*ioc_handler_, [message = std::move(message), callback]() { callback(message); });
    }
    promise_map_.erase(promise_entry);
  } else {
    logger()->error("Connection ({}:{}) received response for id {} but no callback was found.", endpoint_address_,
                    endpoint_port_, id);
    // TODO: Call Handler on error
  }
}

void Connection::DoSend() {
  // Quick Stop
  if (send_queue_.empty()) {
    return;
  }
  // Call on network strand
  boost::asio::dispatch(*strand_net_, [self_weak = weak_from_this()]() {
    if (auto self = self_weak.lock()) {
      // Closed
      if (!self->is_open_) {
        logger()->debug("Connection ({}:{}) cannot Send, connection is closed.", self->endpoint_address_,
                        self->endpoint_port_);
        return;
      }
      // Only one
      if (self->is_sending_) {
        logger()->debug("Connection ({}:{}) cannot Send, send in progress", self->endpoint_address_,
                        self->endpoint_port_);
        return;
      }
      // Grab buffer
      std::shared_ptr<SendBuffer> send_buffer;
      {
        std::lock_guard<std::mutex> lock(self->send_queue_mutex_);
        if (self->send_queue_.empty()) {
          return;
        }
        send_buffer = self->send_queue_.front();
        self->send_queue_.pop();
        self->send_queue_size_ -= send_buffer->size;
      }
      // Log
      if (send_buffer->message_type == AcknowledeResponse || send_buffer->message_type == ErrorResponse) {
        logger()->debug("Connection ({}:{}) sending response (ID: {})", self->endpoint_address_, self->endpoint_port_,
                        send_buffer->id);
      } else {
        logger()->debug("Connection ({}:{}) sending {} (ID: {})", self->endpoint_address_, self->endpoint_port_,
                        MessageTypeToString(send_buffer->message_type), send_buffer->id);
      }
      // Write
      self->is_sending_ = true;
      self->ws_.async_write(
          send_buffer->buffer, [self_weak,
                                send_buffer](  // Keep the send_buffer alive until write is finished
                                   boost::system::error_code const& ec, size_t bytes_transferred) mutable {
            // Log
            if (ec) {
              logger()->error("Connection: async_write (ID: {}) failed: {}", send_buffer->id, ec.message());
            } else {
              logger()->debug("Connection: async_write finished (ID: {})", send_buffer->id);
            }
            // Set done and send more
            if (auto self = self_weak.lock()) {
              self->is_sending_ = false;
              self->DoSend();
            } else {
              logger()->warn(
                  "Connection no longer valid, cannot write additional "
                  "messages.");
            }
          });
    } else {
      logger()->warn("Connection no longer valid, cannot write message.");
    }
  });
}

}  // namespace interceptor
}  // namespace vci
