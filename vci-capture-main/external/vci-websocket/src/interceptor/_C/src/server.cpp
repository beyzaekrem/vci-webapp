#include <interceptor/server.h>

#include <iostream>
#include <string>

#include <interceptor/logging.h>
#include <pybind11/pybind11.h>

namespace vci {
namespace interceptor {

ServerConnection::ServerConnection(
    std::shared_ptr<boost::asio::io_context> ioc_net, std::shared_ptr<boost::asio::io_context> ioc_handler,
    std::shared_ptr<boost::asio::strand<boost::asio::io_context::executor_type>> strand_net,
    boost::asio::ip::tcp::socket&& socket, std::shared_ptr<boost::asio::ssl::context> ssl_context,
    std::weak_ptr<ConnectionHolder> connection_holder)
    : Connection(ioc_net, ioc_handler, strand_net, std::move(socket), connection_holder),
      ssl_stream_(std::move(socket), *ssl_context) {}

ServerConnection::~ServerConnection() {}

const bool use_ssl = false;

void ServerConnection::Run() {
  boost::asio::dispatch(*strand_net_, [self_weak = weak_from_this()]() {
    if (auto self_base = self_weak.lock()) {
      auto self = std::static_pointer_cast<ServerConnection>(self_base);
      // Set suggested timeout settings for the websocket
      self->ws_.set_option(boost::beast::websocket::stream_base::timeout::suggested(boost::beast::role_type::server));

      // Disable compression
      boost::beast::websocket::permessage_deflate deflate_opt;
      deflate_opt.client_enable = false;
      deflate_opt.server_enable = false;
      self->ws_.set_option(deflate_opt);

      // Max message length, fragmentation, and binary
      self->ws_.read_message_max(1024 * 1024 * 1024);
      self->ws_.auto_fragment(false);
      self->ws_.binary(true);

      // Accept the websocket handshake
      if (!use_ssl) {
        self->ws_.async_accept(boost::asio::bind_executor(*self->strand_net_, [self_weak](boost::beast::error_code ec) {
          if (auto self_base = self_weak.lock()) {
            auto self = std::static_pointer_cast<ServerConnection>(self_base);
            self->OnAccept(ec);
          }
        }));
      } else {
        // Perform the SSL handshake
        // Needs to be tested with SSL certificate
        self->ssl_stream_.async_handshake(
            boost::asio::ssl::stream_base::server,
            boost::asio::bind_executor(*self->strand_net_, [self_weak](boost::beast::error_code ec) {
              if (auto self_base = self_weak.lock()) {
                auto self = std::static_pointer_cast<ServerConnection>(self_base);
                if (!ec) {
                  // Once SSL handshake succeeds, accept the WebSocket
                  self->ws_.async_accept(
                      boost::asio::bind_executor(*self->strand_net_, [self_weak](boost::beast::error_code ec) {
                        if (auto self_base = self_weak.lock()) {
                          auto self = std::static_pointer_cast<ServerConnection>(self_base);
                          self->OnAccept(ec);
                        }
                      }));
                } else {
                  // Handle SSL handshake error
                }
              }
            }));
      }
    }
  });
}

Server::Server(int port, std::shared_ptr<MessageHandler> handler, int num_threads_net, int num_threads_handler)
    : port_(port),
      is_running_(false),
      handler_(handler),
      num_threads_net_(num_threads_net),
      num_threads_handler_(num_threads_handler),
      ioc_net_(),
      ioc_handler_(),
      strand_(),
      acceptor_(),
      connections_(),
      threads_(),
      mutex_(),
      ssl_context_(std::make_shared<boost::asio::ssl::context>(boost::asio::ssl::context::tls_server)) {
  if (use_ssl) {
    ssl_context_->use_certificate_chain_file("path/to/certificate.pem");
    ssl_context_->use_private_key_file("path/to/private_key.pem", boost::asio::ssl::context::pem);
  }
}

Server::~Server() {
  stop(false);
}

void Server::run(bool blocking, bool stop_on_termination_signal) {
  {
    // Check state
    std::lock_guard<std::mutex> guard(mutex_);
    if (is_running_) {
      return;
    }
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
    acceptor_ = std::make_shared<boost::asio::ip::tcp::acceptor>(*ioc_net_);
    // Start Acceptor
    boost::beast::error_code ec;
    auto const address = boost::asio::ip::make_address("0.0.0.0");
    auto const port_short = static_cast<unsigned short>(port_);
    const auto endpoint = boost::asio::ip::tcp::endpoint{address, port_short};
    acceptor_->open(endpoint.protocol(), ec);
    if (ec) {
      throw std::runtime_error("Cannot open acceptor");
    }
    acceptor_->set_option(boost::asio::socket_base::reuse_address(true), ec);
    if (ec) {
      throw std::runtime_error("Could not enable address reuse");
    }
    acceptor_->bind(endpoint, ec);
    if (ec) {
      throw std::runtime_error("Cannot bind port");
    }
    acceptor_->listen(boost::asio::socket_base::max_listen_connections, ec);
    if (ec) {
      throw std::runtime_error("Could not start listen");
    }
    do_accept();
    // Run the I/O service on the requested number of threads
    for (int i = 0; i < num_threads_net_; ++i) {
      threads_.emplace_back([this, ioc = this->ioc_net_] { ioc->run(); });
    }
    for (int i = 0; i < num_threads_handler_; ++i) {
      threads_.emplace_back([this, ioc = this->ioc_handler_] { ioc->run(); });
    }
    is_running_ = true;
  }
  if (blocking) {
    if (stop_on_termination_signal) {
      // Handle termination
      boost::asio::signal_set net_signals(*ioc_handler_, SIGINT, SIGTERM);
      net_signals.async_wait([this](boost::system::error_code ec, int signal_number) {
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

bool Server::is_running() const {
  return is_running_;
}

void Server::run_one_pending_handler() {
  if (auto ioc_handler = ioc_handler_) {
    ioc_handler->poll_one();
  }
}

void Server::run_all_pending_handlers() {
  if (auto ioc_handler = ioc_handler_) {
    while (ioc_handler->poll_one()) {
    }
  }
}

void Server::stop(bool run_pending_handlers) {
  std::lock_guard<std::mutex> guard(mutex_);
  if (!is_running_) {
    return;
  }
  // Stop Acceptor
  acceptor_->close();
  // Close all connections, keep copy to move deletion to later
  auto connections = connections_;
  for (auto& connection : connections) {
    connection->stop();
  }
  connections_.clear();
  // Stop networking io_context
  ioc_net_->stop();
  // Stop handler io_context
  if (run_pending_handlers) {
    while (ioc_handler_->poll_one()) {
    }
  }
  ioc_handler_->stop();
  handler_work_guard_->reset();
  connections.clear();
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
  acceptor_ = nullptr;
  handler_work_guard_ = nullptr;
  strand_ = nullptr;
  ioc_net_ = nullptr;
  ioc_handler_ = nullptr;
  is_running_ = false;
}

void Server::set_handler(std::shared_ptr<MessageHandler> handler) {
  handler_ = handler;
}

void Server::connection_opened(std::shared_ptr<Connection> connection) {
  boost::asio::dispatch(*ioc_handler_, [handler_weak = std::weak_ptr<MessageHandler>(handler_),
                                        self_weak = std::weak_ptr<Connection>(connection)]() {
    if (auto handler = handler_weak.lock()) {
      if (auto self = self_weak.lock()) {
        handler->OnConnect(self);
      }
    }
  });
}

void Server::connection_not_opened(std::shared_ptr<Connection> connection) {
  remove_connection(connection);
}

void Server::connection_closed(std::shared_ptr<Connection> connection, bool graceful, bool await_handler) {
  if (!is_running_) {
    return;
  }
  // Dispatch call handler
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

  // Remove from list
  remove_connection(connection);
}

void Server::remove_connection(std::shared_ptr<Connection> connection) {
  std::lock_guard<std::mutex> guard(connections_mutex_);
  connections_.erase(std::remove(connections_.begin(), connections_.end(), connection), connections_.end());
}

std::shared_ptr<MessageHandler> Server::handler() {
  return handler_;
}

void Server::do_accept() {
  acceptor_->async_accept(
      boost::asio::bind_executor(*strand_, boost::beast::bind_front_handler(&Server::on_accept, shared_from_this())));
}

void Server::on_accept(boost::beast::error_code ec, boost::asio::ip::tcp::socket socket) {
  if (ec) {
    if (ec == boost::asio::error::operation_aborted) {
      // acceptor canceled, do not start again
      return;
    } else {
      logger()->error("Server: Error accepting new connection: {}", ec.message());
    }
  } else {
    auto new_connection = std::make_shared<ServerConnection>(
        ioc_net_, ioc_handler_,
        std::make_shared<boost::asio::strand<boost::asio::io_context::executor_type>>(ioc_net_->get_executor()),
        std::move(socket), this->ssl_context_, weak_from_this());
    {
      std::lock_guard<std::mutex> guard(connections_mutex_);
      connections_.push_back(new_connection);
    }
    new_connection->Run();
  }
  do_accept();
}

PyServer::PyServer(int port, pybind11::object handler, int num_threads_net, int num_threads_handler)
    : Server(port, handler.cast<std::shared_ptr<MessageHandler>>(), num_threads_net, num_threads_handler),
      py_handler_(handler),
      timer_() {
  if (num_threads_handler > 0) {
    logger()->warn(
        "PyServer: Starting background handler threads may lead to errors. "
        "Better use Server.run(blocking=True), Server.run_one_pending_handler(), or "
        "Server.run_all_pending_handlers().");
  }
}

void PyServer::py_run(bool blocking) {
  if (is_running_) {
    return;
  }
  pybind11::gil_scoped_release release;
  had_error_signal_ = false;
  if (blocking) {
    ioc_handler_ = std::make_shared<boost::asio::io_context>();
    timer_ = std::make_shared<boost::asio::steady_timer>(*ioc_handler_);
    check_signals();
    std::shared_ptr<boost::asio::io_context> ioc = ioc_handler_;
    Server::run(blocking, false);
    timer_ = nullptr;
  } else {
    Server::run(blocking, false);
  }
  if (had_error_signal_) {
    pybind11::gil_scoped_acquire acquire;
    throw pybind11::error_already_set();
  }
}

void PyServer::py_stop(bool run_pending_handlers) {
  pybind11::gil_scoped_release release;
  Server::stop(run_pending_handlers);
}

void PyServer::py_set_handler(pybind11::object handler) {
  Server::set_handler(handler.cast<std::shared_ptr<MessageHandler>>());
  py_handler_ = handler;
}

void PyServer::check_signals() {
  if (timer_) {
    timer_->expires_after(boost::asio::chrono::milliseconds(100));
    timer_->async_wait(boost::beast::bind_front_handler(&PyServer::on_check_signals,
                                                        std::static_pointer_cast<PyServer>(shared_from_this())));
  }
}

void PyServer::on_check_signals(boost::system::error_code ec) {
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
