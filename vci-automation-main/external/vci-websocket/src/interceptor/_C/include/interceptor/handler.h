#ifndef VCI_INTERCEPTOR_HANDLER_H
#define VCI_INTERCEPTOR_HANDLER_H

#include <interceptor/message.h>
#include <pybind11/functional.h>
#include <pybind11/pybind11.h>
#include <nlohmann/json.hpp>

#include <iostream>

namespace vci {
namespace interceptor {

class Connection;

using HandlerFunc = std::function<void(std::shared_ptr<MessageIn>)>;

std::string fix_docstring_indentation(const std::string& doc);

struct PathHander {
  std::string path;
  HandlerFunc func;
  std::string docstring;
  PathHander(std::string path_, HandlerFunc func_, std::string docstring_)
      : path(std::move(path_)), func(std::move(func_)), docstring(fix_docstring_indentation(docstring_)) {}
};

class MessageHandler {
 public:
  virtual bool dispatch(std::shared_ptr<MessageIn> message);
  virtual nlohmann::json get_interface_json();

  virtual void OnConnect(std::shared_ptr<Connection> connection) {};
  virtual void OnDisconnect(std::shared_ptr<Connection> connection, bool graceful) {};
  virtual bool OnMessage(std::shared_ptr<MessageIn> message) { return false; };
  virtual void OnError(std::shared_ptr<MessageIn> message) {};

 protected:
  void add_path_handler(PathHander path_handler);

 private:
  std::unordered_map<std::string, PathHander> path_handler_lookup_;
};

class PyMessageHandler : public MessageHandler {
 public:
  using MessageHandler::MessageHandler;
  bool dispatch(std::shared_ptr<MessageIn> message) override;

  void OnConnect(std::shared_ptr<Connection> connection) override;
  void OnDisconnect(std::shared_ptr<Connection> connection, bool graceful) override;
  bool OnMessage(std::shared_ptr<MessageIn> message) override;
  void OnError(std::shared_ptr<MessageIn> message) override;
  static void check_duplicates_and_docstrings(pybind11::object cls);
  void register_python_handlers();

 private:
  bool handlers_registered_ = false;  // Flag to avoid multiple registrations of handlers.
};

/**
 * @brief A decorator function that tags functions with their path.
 * @param path The path of the message.
 * @return The wrapping function.
 */
pybind11::object path_handler(const std::string& path);

pybind11::dict inspect_path_handlers(pybind11::object cls);

}  // namespace interceptor
}  // namespace vci

#endif  // VCI_INTERCEPTOR_HANDLER_H
