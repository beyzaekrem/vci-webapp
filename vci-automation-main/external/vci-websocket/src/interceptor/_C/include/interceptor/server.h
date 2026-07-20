#ifndef VCI_INTERCEPTOR_SERVER_H
#define VCI_INTERCEPTOR_SERVER_H

#include <memory>
#include <stdexcept>
#include <thread>

#include <boost/asio.hpp>
#include <boost/asio/ssl.hpp>
#include <boost/asio/strand.hpp>
#include <boost/beast/core.hpp>
#include <boost/beast/websocket.hpp>

#include <interceptor/buffer.h>
#include <interceptor/connection.h>
#include <interceptor/message.h>

namespace vci {
namespace interceptor {

class ServerConnection : public Connection {
 public:
  ServerConnection(std::shared_ptr<boost::asio::io_context> ioc_net,
                   std::shared_ptr<boost::asio::io_context> ioc_handler,
                   std::shared_ptr<boost::asio::strand<boost::asio::io_context::executor_type>> strand_net,
                   boost::asio::ip::tcp::socket&& socket, std::shared_ptr<boost::asio::ssl::context> ssl_context,
                   std::weak_ptr<ConnectionHolder> connection_holder);
  ~ServerConnection();
  void Run();

 protected:
  boost::asio::ssl::stream<boost::asio::ip::tcp::socket> ssl_stream_;
};

class Server : public ConnectionHolder, public std::enable_shared_from_this<Server> {
 public:
  Server(int port, std::shared_ptr<MessageHandler> handler = nullptr, int num_threads_net = 2,
         int num_threads_handler = 0);
  ~Server();

  /**
   * @brief Start the server and launch IO threads
   *
   * @param blocking Whether the current thread should keep executing all handlers
   * @param stop_on_termination_signal Whether a signal handler should be installed that stops the
   *        server on SIGINT or SIGTERM
   */
  void run(bool blocking = true, bool stop_on_termination_signal = false);

  bool is_running() const;

  /**
   * @brief Run at most one pending handler and return
   *
   */
  void run_one_pending_handler();

  /**
   * @brief Run all pending handlers and return when no more handlers are pending
   *
   */
  void run_all_pending_handlers();

  void stop(bool run_pending_handlers);

  void set_handler(std::shared_ptr<MessageHandler> handler);

 protected:
  void connection_opened(std::shared_ptr<Connection> connection);
  void connection_not_opened(std::shared_ptr<Connection> connection);
  void connection_closed(std::shared_ptr<Connection> connection, bool graceful, bool await_handler);
  void remove_connection(std::shared_ptr<Connection> connection);
  std::shared_ptr<MessageHandler> handler();

  /**
   * @brief Waits for incoming TCP connections, which are handled by OnAccept
   */
  void do_accept();
  /**
   * @brief Accepts a new TCP connection and initiates the ServerConnection
   */
  void on_accept(boost::beast::error_code ec, boost::asio::ip::tcp::socket socket);

  /// @brief Port to listen on
  int port_;
  /// @brief If the server is running
  bool is_running_;
  /// @brief Current callback handler
  std::shared_ptr<MessageHandler> handler_;
  /// @brief Number of threads running the ioc_net_
  int num_threads_net_;
  /// @brief Number of threads running the ioc_handler_
  int num_threads_handler_;
  /// @brief IO Context running all networking threads
  std::shared_ptr<boost::asio::io_context> ioc_net_;
  /// @brief IO Context running all handler threads
  std::shared_ptr<boost::asio::io_context> ioc_handler_;
  /// @brief Work Guard
  std::shared_ptr<boost::asio::executor_work_guard<boost::asio::io_context::executor_type>> handler_work_guard_;
  /// @brief Strand for synced access to the acceptor_
  std::shared_ptr<boost::asio::strand<boost::asio::io_context::executor_type>> strand_;
  /// @brief TCP acceptor
  std::shared_ptr<boost::asio::ip::tcp::acceptor> acceptor_;
  /// @brief List of open connections
  std::vector<std::shared_ptr<ServerConnection>> connections_;
  /// @brief Connection list mutex
  std::mutex connections_mutex_;
  /// @brief threads running the io contexts
  std::vector<std::thread> threads_;
  /// @brief Server state mutex
  std::mutex mutex_;

 private:
  std::shared_ptr<boost::asio::ssl::context> ssl_context_;
};

class __attribute__((visibility("default"))) PyServer : public Server {
 public:
  PyServer(int port, pybind11::object handler = pybind11::none(), int num_threads_net = 2, int num_threads_handler = 0);
  void py_run(bool blocking = true);
  void py_stop(bool run_pending_handlers);
  void py_set_handler(pybind11::object handler_pyobj);

 private:
  /// @brief Need to periodically check signals in Python if blocking
  void check_signals();
  void on_check_signals(boost::system::error_code ec);
  pybind11::object py_handler_;
  std::shared_ptr<boost::asio::steady_timer> timer_;
  bool had_error_signal_;
};

}  // namespace interceptor
}  // namespace vci

#endif  // VCI_INTERCEPTOR_SERVER_H
