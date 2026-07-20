#include <interceptor/client.h>
#include <interceptor/logging.h>

namespace vci {
namespace interceptor {

ClientConnection::ClientConnection(
    std::shared_ptr<boost::asio::io_context> ioc_net, std::shared_ptr<boost::asio::io_context> ioc_handler,
    std::shared_ptr<boost::asio::strand<boost::asio::io_context::executor_type>> strand_net,
    boost::asio::ip::tcp::socket&& socket, std::weak_ptr<ConnectionHolder> connection_holder)
    : Connection(ioc_net, ioc_handler, strand_net, std::move(socket), connection_holder) {}

ClientConnection::~ClientConnection() {}

void ClientConnection::Run() {
  boost::asio::dispatch(*ioc_net_, [self_weak = weak_from_this()]() {
    if (auto self_base = self_weak.lock()) {
      auto self = std::static_pointer_cast<ClientConnection>(self_base);
      // Set suggested timeout settings for the websocket
      self->ws_.set_option(boost::beast::websocket::stream_base::timeout::suggested(boost::beast::role_type::client));

      // Disable compression
      boost::beast::websocket::permessage_deflate deflate_opt;
      deflate_opt.client_enable = false;
      deflate_opt.server_enable = false;
      self->ws_.set_option(deflate_opt);

      // Max message length, fragmentation, and binary
      self->ws_.read_message_max(1024 * 1024 * 1024);
      self->ws_.auto_fragment(false);
      self->ws_.binary(true);

      logger()->debug("ClientConnection: Initiating websocket handshake ({}:{})", self->endpoint_address_,
                      self->endpoint_port_);
      self->ws_.async_handshake(
          "localhost", "/", boost::asio::bind_executor(*self->strand_net_, [self_weak](boost::beast::error_code ec) {
            if (auto self_base = self_weak.lock()) {
              auto self = std::static_pointer_cast<ClientConnection>(self_base);
              self->OnAccept(ec);
            }
          }));
    }
  });
}

Client::Client(const std::string& host, int port, std::shared_ptr<MessageHandler> handler, int num_threads_net,
               int num_threads_handler)
    : host_(host),
      port_(port),
      state_(ClientState::DISCONNECTED),
      handler_(handler),
      num_threads_net_(num_threads_net),
      num_threads_handler_(num_threads_handler),
      ioc_net_(),
      ioc_handler_(),
      strand_(),
      resolver_(),
      resolved_address_(),
      socket_(),
      connection_(),
      threads_(),
      mutex_() {}

Client::~Client() {
  stop(false);
}

void Client::run(bool blocking, bool stop_on_termination_signal) {
  {
    // Check state
    std::lock_guard<std::mutex> guard(mutex_);
    if (state_ != ClientState::DISCONNECTED) {
      logger()->warn("Client: Can only run() Client when in state DISCONNECTED. Call ignored.");
      return;
    }
    logger()->debug("Client: Run started ({}:{})", host_, port_);
    state_ = ClientState::RESOLVING;
    // Init members
    if (ioc_net_ == nullptr) {
      ioc_net_ = std::make_shared<boost::asio::io_context>();
    }
    if (ioc_handler_ == nullptr) {
      ioc_handler_ = std::make_shared<boost::asio::io_context>();
    }
    handler_work_guard_ = std::make_shared<boost::asio::executor_work_guard<boost::asio::io_context::executor_type>>(
        boost::asio::make_work_guard(*ioc_handler_));
    strand_ = std::make_shared<boost::asio::strand<boost::asio::io_context::executor_type>>(ioc_net_->get_executor());
    resolver_ = std::make_shared<boost::asio::ip::tcp::resolver>(*ioc_net_);
    socket_ = std::make_shared<boost::asio::ip::tcp::socket>(*ioc_net_);
    // Start address resolve
    resolver_->async_resolve(host_, std::to_string(port_),
                             boost::beast::bind_front_handler(&Client::on_resolve, shared_from_this()));
    // Run the I/O service on the requested number of threads
    for (int i = 0; i < num_threads_net_; ++i) {
      threads_.emplace_back([this] { ioc_net_->run(); });
    }
    for (int i = 0; i < num_threads_handler_; ++i) {
      threads_.emplace_back([this] { ioc_handler_->run(); });
    }
  }
  if (blocking) {
    if (stop_on_termination_signal) {
      // Handle termination
      boost::asio::signal_set net_signals(*ioc_handler_, SIGINT, SIGTERM);
      net_signals.async_wait([this](boost::system::error_code ec, int signal_number) {
        if (ec == boost::asio::error::operation_aborted) {
          return;
        }
        if (!ec) {
          this->stop(false);
        }
      });
      ioc_handler_->run();
    } else {
      ioc_handler_->run();
    }
  }
}

bool Client::is_connected() const {
  return state_ == ClientState::CONNECTED;
}

ClientState Client::get_status() const {
  return state_;
}

void Client::wait_for_connection(float timeout_s) {
  auto end_time =
      std::chrono::high_resolution_clock::now() + std::chrono::milliseconds(long(ceilf(1000.f * timeout_s)));
  while (true) {
    if (std::chrono::high_resolution_clock::now() >= end_time) {
      throw TimeoutError("Client::wait_for_connection", timeout_s);
    } else if (int(state_) <= 0 || state_ == ClientState::STOPPING) {
      throw NotConnectedError();
    } else if (state_ == ClientState::CONNECTED) {
      return;
    }
    std::this_thread::sleep_for(std::chrono::nanoseconds(10));
  }
}

void Client::run_one_pending_handler() {
  if (auto ioc_handler = ioc_handler_) {
    ioc_handler->poll_one();
  }
}

void Client::run_all_pending_handlers() {
  if (auto ioc_handler = ioc_handler_) {
    while (ioc_handler->poll_one()) {
    }
  }
}

void Client::stop(bool run_pending_handlers) {
  {
    std::lock_guard<std::mutex> guard(mutex_);
    if (state_ == ClientState::STOPPING || state_ == ClientState::DISCONNECTED) {
      return;
    }
    state_ = ClientState::STOPPING;
  }
  // Stop resolver
  resolver_->cancel();
  // Close connection
  auto connection = connection_;
  if (connection_) {
    connection_->stop();
  }
  connection_.reset();
  // Stop networking io_context
  ioc_net_->stop();

  // Stop handler io_context
  if (run_pending_handlers) {
    while (ioc_handler_->poll_one()) {
    }
  }
  ioc_handler_->stop();
  handler_work_guard_->reset();
  connection.reset();
  // Join all threads
  for (auto& thread : threads_) {
    if (thread.joinable()) {
      if (thread.get_id() == std::this_thread::get_id()) {
        thread.detach();
      } else {
        thread.join();
      }
    }
  }
  threads_.clear();
  // Close all
  resolver_ = nullptr;
  handler_work_guard_ = nullptr;
  strand_ = nullptr;
  ioc_net_ = nullptr;
  ioc_handler_ = nullptr;
  state_ = ClientState::DISCONNECTED;
}

void Client::set_handler(std::shared_ptr<MessageHandler> handler) {
  handler_ = handler;
}

std::shared_ptr<MessagePromise> Client::async_send(std::shared_ptr<MessageOut> message, MessageCallbackType callback,
                                                   float timeout_s, bool send_and_forget) {
  if (state_ == ClientState::CONNECTED) {
    return connection_->async_send(message, callback, timeout_s, send_and_forget);
  }
  return nullptr;
}

void Client::async_send_and_forget(std::shared_ptr<MessageOut> message) {
  if (state_ == ClientState::CONNECTED) {
    connection_->async_send_and_forget(message);
  }
}

bool Client::is_queue_full() const {
  if (state_ == ClientState::CONNECTED) {
    return connection_->is_queue_full();
  }
  return true;
}

void Client::connection_opened(std::shared_ptr<Connection> connection) {
  state_ = ClientState::CONNECTED;
  boost::asio::dispatch(*ioc_handler_, [handler_weak = std::weak_ptr<MessageHandler>(handler_),
                                        self_weak = std::weak_ptr<Connection>(connection)]() {
    if (auto handler = handler_weak.lock()) {
      if (auto self = self_weak.lock()) {
        handler->OnConnect(self);
      }
    }
  });
}

void Client::connection_not_opened(std::shared_ptr<Connection> connection) {
  state_ = ClientState::CONNECTING_FAILED;
  stop(true);
}

void Client::connection_closed(std::shared_ptr<Connection> connection, bool graceful, bool await_handler) {
  // Dispatch call handler
  if (auto ioc_handler = ioc_handler_) {
    std::promise<void> promise;
    std::future<void> future = promise.get_future();
    boost::asio::post(*ioc_handler_, [handler_weak = std::weak_ptr<MessageHandler>(handler_),
                                      connection_weak = std::weak_ptr<Connection>(connection), graceful,
                                      promise = std::move(promise)]() mutable {
      if (auto handler = handler_weak.lock()) {
        if (auto connection = connection_weak.lock()) {
          handler->OnDisconnect(connection, graceful);
        } else {
          handler->OnDisconnect(nullptr, graceful);
        }
      }
      promise.set_value();
    });
    if (await_handler) {
      future.wait();
    }
  }
  // Remove connection
  stop(true);
}

std::shared_ptr<MessageHandler> Client::handler() {
  return handler_;
}

void Client::on_resolve(boost::beast::error_code ec, boost::asio::ip::tcp::resolver::results_type results) {
  if (ec) {
    state_ = ClientState::RESOLVE_FAILED;
    if (ec == boost::asio::error::operation_aborted) {
      // resolver canceled, ignore
    } else {
      logger()->error("Client: Error resolving address: {}", ec.message());
      stop(true);
    }
    return;
  }
  resolved_address_ = results;
  logger()->debug("Client: Resolve successful ({}:{} -> {},{}). Attempting TCP connection.", host_, port_,
                  resolved_address_.begin()->endpoint().address().to_string(),
                  resolved_address_.begin()->endpoint().port());
  // Attempt connect
  state_ = ClientState::TCP_CONNECTING;
  boost::asio::async_connect(*socket_, results,
                             boost::beast::bind_front_handler(&Client::on_connect, shared_from_this()));
}

void Client::on_connect(boost::system::error_code ec, boost::asio::ip::tcp::resolver::endpoint_type endpoint) {
  if (ec) {
    if (ec != boost::asio::error::operation_aborted) {
      state_ = ClientState::TCP_CONNECTING_FAILED;
      logger()->error("Client: error connecting: {}", ec.message());
      stop(false);
    }
    return;
  }

  state_ = ClientState::CONNECTING;
  connection_ =
      std::make_shared<ClientConnection>(ioc_net_, ioc_handler_, strand_, std::move(*socket_), weak_from_this());
  socket_.reset();
  connection_->Run();
}

PyClient::PyClient(const std::string& host, int port, pybind11::object handler, int num_threads_net,
                   int num_threads_handler)
    : Client(host, port, handler.cast<std::shared_ptr<MessageHandler>>(), num_threads_net, num_threads_handler),
      py_handler_(handler) {
  if (num_threads_handler > 0) {
    logger()->warn(
        "PyClient: Starting background handler threads may lead to errors. "
        "Better use Client.run(blocking=True), Client.run_one_pending_handler(), or "
        "Client.run_all_pending_handlers().");
  }
}

void PyClient::py_run(bool blocking) {
  if (state_ != ClientState::DISCONNECTED) {
    return;
  }
  pybind11::gil_scoped_release release;
  had_error_signal_ = false;
  if (blocking) {
    ioc_handler_ = std::make_shared<boost::asio::io_context>();
    timer_ = std::make_shared<boost::asio::steady_timer>(*ioc_handler_);
    check_signals();
    std::shared_ptr<boost::asio::io_context> ioc = ioc_handler_;
    Client::run(blocking, false);
    timer_ = nullptr;
  } else {
    Client::run(blocking, false);
  }
  if (had_error_signal_) {
    pybind11::gil_scoped_acquire acquire;
    throw pybind11::error_already_set();
  }
}

void PyClient::py_stop(bool run_pending_handlers) {
  pybind11::gil_scoped_release release;
  Client::stop(run_pending_handlers);
}

void PyClient::py_set_handler(pybind11::object handler) {
  Client::set_handler(handler.cast<std::shared_ptr<MessageHandler>>());
  py_handler_ = handler;
}

void PyClient::check_signals() {
  if (timer_) {
    timer_->expires_after(boost::asio::chrono::milliseconds(100));
    timer_->async_wait(boost::beast::bind_front_handler(&PyClient::on_check_signals,
                                                        std::static_pointer_cast<PyClient>(shared_from_this())));
  }
}

void PyClient::on_check_signals(boost::system::error_code ec) {
  if (ec == boost::asio::error::operation_aborted) {
    return;
  }
  {
    pybind11::gil_scoped_acquire aquire;
    had_error_signal_ = PyErr_CheckSignals() != 0;
  }
  if (had_error_signal_) {
    stop(false);
  } else {
    check_signals();
  }
}

}  // namespace interceptor
}  // namespace vci
