#ifndef VCI_INTERCEPTOR_CONNECTION_H
#define VCI_INTERCEPTOR_CONNECTION_H

#include <unordered_map>

#include <boost/asio.hpp>
#include <boost/asio/spawn.hpp>
#include <boost/asio/strand.hpp>
#include <boost/beast/core.hpp>
#include <boost/beast/websocket.hpp>

#include <interceptor/handler.h>
#include <interceptor/message.h>

namespace vci {
namespace interceptor {

class Connection;

class ConnectionHolder {
  friend class Connection;
  friend class ClientConnection;
  friend class ServerConnection;

 protected:
  /**
   * @brief Handle that the connection was opened correctly
   */
  virtual void connection_opened(std::shared_ptr<Connection> connection) = 0;

  /**
   * @brief Handle that the connection was not opened correctly
   */
  virtual void connection_not_opened(std::shared_ptr<Connection> connection) = 0;

  /**
   * @brief Handle that the connection was closed normal (graceful=true) or error (graceful=false)
   */
  virtual void connection_closed(std::shared_ptr<Connection> connection, bool graceful, bool await_handler) = 0;

  /**
   * @brief Return message handler
   */
  virtual std::shared_ptr<MessageHandler> handler() = 0;
};

class Connection : public std::enable_shared_from_this<Connection> {
 public:
  Connection(std::shared_ptr<boost::asio::io_context> ioc_net, std::shared_ptr<boost::asio::io_context> ioc_handler,
             std::shared_ptr<boost::asio::strand<boost::asio::io_context::executor_type>> strand_net,
             boost::asio::ip::tcp::socket&& socket, std::weak_ptr<ConnectionHolder> connection_holder);
  virtual ~Connection();

  virtual void Run() = 0;
  bool IsOpen();
  void stop();

  std::shared_ptr<MessagePromise> async_send(std::shared_ptr<MessageOut> message,
                                             MessageCallbackType callback = nullptr, float timeout_s = 0.f,
                                             bool send_and_forget = false);
  void async_send_and_forget(std::shared_ptr<MessageOut> message);
  bool is_queue_full() const;
  float Ping();

 protected:
  static std::shared_ptr<MessageHandler> GetHandler(std::weak_ptr<Connection> connection);
  /**
   * @brief Called after the initial handshake is performed
   *
   * Needs to be called from strand_net_
   */
  void OnAccept(boost::beast::error_code ec);

  void DoRead();
  void OnRead(boost::beast::error_code ec, std::size_t bytes_transferred);
  void FindAndExecuteCallback(std::shared_ptr<MessageIn> message);

  void DoSend();

  bool is_open_;
  std::shared_ptr<Buffer> current_buffer_;
  std::shared_ptr<boost::asio::io_context> ioc_net_;
  std::shared_ptr<boost::asio::io_context> ioc_handler_;
  std::shared_ptr<boost::asio::strand<boost::asio::io_context::executor_type>> strand_net_;
  boost::beast::websocket::stream<boost::beast::tcp_stream> ws_;
  std::weak_ptr<ConnectionHolder> connection_holder_;

  std::unordered_map<int, std::shared_ptr<MessagePromise>> promise_map_;
  std::mutex promise_map_mutex_;

  std::string endpoint_address_;
  int endpoint_port_;

  std::mutex send_queue_mutex_;
  std::queue<std::shared_ptr<SendBuffer>> send_queue_;
  /// Current amount of memory in the send queue
  size_t send_queue_size_ = 0;
  /// Soft threshold of data in the send queue. New messages can be added as long as the current size is below this
  /// limit. Default 1 GB.
  size_t max_send_queue_size_ = 1'000'000'000;
  /// Maximum number of messages that are allowed in the send queue at the same time. Default 1000.
  int max_send_queue_length_ = 1000;

  bool is_sending_ = false;
};

}  // namespace interceptor
}  // namespace vci

#endif  // VCI_INTERCEPTOR_CONNECTION_H
