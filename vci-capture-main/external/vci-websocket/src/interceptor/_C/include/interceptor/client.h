#ifndef VCI_INTERCEPTOR_CLIENT_H
#define VCI_INTERCEPTOR_CLIENT_H

#include <memory>
#include <stdexcept>
#include <thread>

#include <pybind11/pybind11.h>
#include <boost/asio.hpp>
#include <boost/asio/strand.hpp>
#include <boost/beast/core.hpp>
#include <boost/beast/websocket.hpp>

#include <interceptor/buffer.h>
#include <interceptor/connection.h>
#include <interceptor/message.h>

namespace vci {
namespace interceptor {

class ClientConnection : public Connection {
 public:
  ClientConnection(std::shared_ptr<boost::asio::io_context> ioc_net,
                   std::shared_ptr<boost::asio::io_context> ioc_handler,
                   std::shared_ptr<boost::asio::strand<boost::asio::io_context::executor_type>> strand_net,
                   boost::asio::ip::tcp::socket&& socket, std::weak_ptr<ConnectionHolder> connection_holder);
  ~ClientConnection();
  void Run();
};

enum class ClientState {
  /// @brief Client not yet started or has stopped
  DISCONNECTED = 0,
  /// @brief Address resolve running
  RESOLVING = 1,
  /// @brief Address resolve failed
  RESOLVE_FAILED = -1,
  /// @brief
  TCP_CONNECTING = 2,
  /// @brief
  TCP_CONNECTING_FAILED = -2,
  /// @brief
  CONNECTING = 3,
  /// @brief
  CONNECTING_FAILED = -3,
  /// @brief
  CONNECTED = 4,
  /// @brief
  CLOSED = -4,
  /// @brief
  STOPPING = 5
  /// @brief
};

class Client : public ConnectionHolder, public std::enable_shared_from_this<Client> {
 public:
  Client(const std::string& host, int port, std::shared_ptr<MessageHandler> handler = nullptr, int num_threads_net = 2,
         int num_threads_handler = 0);
  ~Client();

  /**
   * @brief Start the server and launch IO threads
   *
   * @param blocking Whether the current thread should keep executing all handlers
   * @param stop_on_termination_signal Whether a signal handler should be installed that stops the
   *        server on SIGINT or SIGTERM
   */
  void run(bool blocking = true, bool stop_on_termination_signal = false);

  /**
   * @brief Returns True if the ClientState is CONNECTED
   */
  bool is_connected() const;

  /**
   * @brief Returns the current client state
   */
  ClientState get_status() const;

  void wait_for_connection(float timeout_s = 10.f);

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

  std::shared_ptr<MessagePromise> async_send(std::shared_ptr<MessageOut> message,
                                             MessageCallbackType callback = nullptr, float timeout_s = 0.f,
                                             bool send_and_forget = false);
  void async_send_and_forget(std::shared_ptr<MessageOut> message);
  bool is_queue_full() const;

 protected:
  void connection_opened(std::shared_ptr<Connection> connection);
  void connection_not_opened(std::shared_ptr<Connection> connection);
  void connection_closed(std::shared_ptr<Connection> connection, bool graceful, bool await_handler);
  std::shared_ptr<MessageHandler> handler();

  /**
   * @brief Handle resolved hostname and send connection request
   */
  void on_resolve(boost::beast::error_code ec, boost::asio::ip::tcp::resolver::results_type results);

  /**
   * @brief Handle established TCP connection and initiate websocket connection
   */
  void on_connect(boost::system::error_code ec, boost::asio::ip::tcp::resolver::endpoint_type endpoint);

  /// @brief Host address to connect to
  std::string host_;
  /// @brief Host port to connect to
  int port_;
  /// @brief Connection state of the client
  ClientState state_;
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
  /// @brief Strand for synced access
  std::shared_ptr<boost::asio::strand<boost::asio::io_context::executor_type>> strand_;
  /// @brief DNS resolver
  std::shared_ptr<boost::asio::ip::tcp::resolver> resolver_;
  /// @brief Resolved ip address
  boost::asio::ip::tcp::resolver::results_type resolved_address_;
  /// @brief TCP Socket
  std::shared_ptr<boost::asio::ip::tcp::socket> socket_;
  /// @brief Client Connection
  std::shared_ptr<ClientConnection> connection_;
  /// @brief threads running the io contexts
  std::vector<std::thread> threads_;
  /// @brief Server state mutex
  std::mutex mutex_;
};

class __attribute__((visibility("default"))) PyClient : public Client {
 public:
  PyClient(const std::string& host, int port, pybind11::object handler = pybind11::none(), int num_threads_net = 2,
           int num_threads_handler = 0);
  void py_run(bool blocking = true);
  void py_stop(bool run_pending_handlers);
  void py_set_handler(pybind11::object handler);

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

#endif  // VCI_INTERCEPTOR_CLIENT_H
