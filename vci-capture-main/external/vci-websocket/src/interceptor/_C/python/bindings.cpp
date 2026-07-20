#include <pybind11/chrono.h>
#include <pybind11/functional.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11_json.hpp>

#include <interceptor/client.h>
#include <interceptor/connection.h>
#include <interceptor/error.h>
#include <interceptor/handler.h>
#include <interceptor/logging.h>
#include <interceptor/message.h>
#include <interceptor/payload.h>
#include <interceptor/server.h>

namespace py = pybind11;

namespace vci {
namespace interceptor {

void bindings(py::module_& m) {
  auto& message_error = py::register_exception<MessageError>(m, "MessageError");
  auto& queue_full_error = py::register_exception<QueueFullError>(m, "QueueFullError", message_error);
  auto& connection_closed_error = py::register_exception<NotConnectedError>(m, "NotConnectedError", message_error);
  auto& invalid_message_error = py::register_exception<InvalidMessageError>(m, "InvalidMessageError", message_error);
  auto& path_does_not_exist_error =
      py::register_exception<PathDoesNotExistError>(m, "PathDoesNotExistError", message_error);
  auto& missing_acknowledge_error =
      py::register_exception<MissingAcknowledgeError>(m, "MissingAcknowledgeError", message_error);
  auto& path_handler_failed_error =
      py::register_exception<PathHandlerFailedError>(m, "PathHandlerFailedError", message_error);
  wrong_payload_error = py::register_exception<WrongPayloadError>(m, "WrongPayloadError", message_error);
  auto& cast_payload_error = py::register_exception<CastPayloadError>(m, "CastPayloadError", message_error);
  auto& timeout_error = py::register_exception<TimeoutError>(m, "TimeoutError", message_error);
  auto& path_already_defined_error = py::register_exception<PathAlreadyDefinedError>(m, "PathAlreadyDefinedError");

  py::enum_<PayloadType>(m, "PayloadType")
      .value("RawPtrPayload", PayloadType::RawPtrPayload)
      .value("StringPayload", PayloadType::StringPayload)
      .value("BsonPayload", PayloadType::BsonPayload)
      .export_values();

  py::enum_<MessageType>(m, "MessageType")
      .value("MessageTypeNotSet", MessageType::MessageTypeNotSet)
      .value("ProtocolMessage", MessageType::ProtocolMessage)
      .value("ErrorMessage", MessageType::ErrorMessage)
      .value("StandardMessage", MessageType::StandardMessage)
      .value("MonologueMessage", MessageType::MonologueMessage)
      .value("AcknowledeResponse", MessageType::AcknowledeResponse)
      .value("ErrorResponse", MessageType::ErrorResponse)
      .export_values();

  py::enum_<ClientState>(m, "ClientState")
      .value("DISCONNECTED", ClientState::DISCONNECTED)
      .value("RESOLVING", ClientState::RESOLVING)
      .value("RESOLVE_FAILED", ClientState::RESOLVE_FAILED)
      .value("TCP_CONNECTING", ClientState::TCP_CONNECTING)
      .value("TCP_CONNECTING_FAILED", ClientState::TCP_CONNECTING_FAILED)
      .value("CONNECTING", ClientState::CONNECTING)
      .value("CONNECTING_FAILED", ClientState::CONNECTING_FAILED)
      .value("CONNECTED", ClientState::CONNECTED)
      .value("CLOSED", ClientState::CLOSED)
      .value("STOPPING", ClientState::STOPPING)
      .export_values();

  auto client_cls = py::class_<PyClient, std::shared_ptr<PyClient>>(m, "Client");
  auto connection_cls = py::class_<Connection, std::shared_ptr<Connection>>(m, "Connection");
  auto message_handler_cls =
      py::class_<MessageHandler, std::shared_ptr<MessageHandler>, PyMessageHandler>(m, "MessageHandler");
  auto message_promise_cls = py::class_<MessagePromise, std::shared_ptr<MessagePromise>>(m, "MessagePromise");
  auto message_cls = py::class_<Message, std::shared_ptr<Message>>(m, "Message");
  auto message_in_cls = py::class_<MessageIn, Message, std::shared_ptr<MessageIn>>(m, "MessageIn");
  auto message_out_cls = py::class_<MessageOut, Message, std::shared_ptr<MessageOut>>(m, "MessageOut");
  auto payload_cls = py::class_<Payload, std::shared_ptr<Payload>>(m, "Payload");
  auto server_cls = py::class_<PyServer, std::shared_ptr<PyServer>>(m, "Server");

  client_cls
      .def(py::init<const std::string&, int, py::object, int, int>(), py::arg("host"), py::arg("port"),
           py::arg("handler") = nullptr, py::arg("num_threads_net") = 2, py::arg("num_threads_handler") = 0)
      .def("run", &PyClient::py_run, py::arg("blocking") = true)
      .def("is_connected", &PyClient::is_connected)
      .def("get_status", &PyClient::get_status)
      .def("wait_for_connection", &PyClient::wait_for_connection, py::arg("timeout_s"))
      .def("run_one_pending_handler", &PyClient::run_one_pending_handler)
      .def("stop", &PyClient::py_stop, py::arg("run_pending_handlers") = false)
      .def("set_handler", &PyClient::py_set_handler)
      .def("async_send", &PyClient::async_send, py::arg("message"), py::arg("callback") = nullptr,
           py::arg("timeout_s") = 0.f, py::arg("send_and_forget") = false,
           "Send the message asynchronously.\n"
           "\nArgs:\n"
           "  message: Message to be sent\n"
           "\nReturns:\n"
           "  Message promise to await response.\n"
           "\nRaises:\n"
           "  NotConnectedError: When no connection is active and the message cannot be sent\n")
      .def("is_queue_full", &PyClient::is_queue_full);

  connection_cls.def("IsOpen", &Connection::IsOpen)
      .def("async_send", &Connection::async_send, py::arg("message"), py::arg("callback") = nullptr,
           py::arg("timeout_s") = 0.f, py::arg("send_and_forget") = false)
      .def_property_readonly("endpoint_address", &Connection::get_endpoint_address)
      .def_property_readonly("endpoint_port", &Connection::get_endpoint_port)
      .def("is_queue_full", &Connection::is_queue_full)
      .def("Ping", &Connection::Ping);

  message_handler_cls.def(py::init<>())
      .def("OnConnect", &MessageHandler::OnConnect)
      .def("OnDisconnect", &MessageHandler::OnDisconnect)
      .def("OnMessage", &MessageHandler::OnMessage)
      .def("OnError", &MessageHandler::OnError)
      .def("dispatch", &MessageHandler::dispatch)
      .def_property_readonly_static("__init_subclass__", [](py::object cls) {
        PyMessageHandler::check_duplicates_and_docstrings(cls);
        return py::cpp_function([]() { return; });
      });

  message_promise_cls.def("wait", &MessagePromise::py_wait)
      .def("wait_for", &MessagePromise::py_wait_for, py::arg("timeout_s"))
      .def("get", &MessagePromise::get);

  message_cls.def_property_readonly("id", &Message::id)
      .def_property_readonly("type", &Message::type)
      .def("is_error", &Message::is_error)
      .def_property_readonly("path", &Message::path)
      .def_property_readonly("error", &Message::error)
      .def_property_readonly("payload", &Message::payload);

  message_in_cls.def(py::init<>())
      .def("Acknowledge", &MessageIn::PyAcknowledge, py::arg("payload") = py::none())
      .def("ErrorResponse", &MessageIn::ErrorResponse, py::arg("error") = std::string("Error"),
           py::arg("payload") = std::vector<std::shared_ptr<Payload>>())
      .def("connection", [](MessageIn& self) { return self.connection().lock(); });

  message_out_cls
      .def(py::init<const std::string&, std::vector<std::shared_ptr<Payload>>>(), py::arg("path"),
           py::arg("payload") = std::vector<std::shared_ptr<Payload>>())
      .def(py::init<const std::string&, std::shared_ptr<Payload>>(), py::arg("path"), py::arg("payload"));

  payload_cls.def_static("WrapPyBytes", &Payload::WrapPyBytes, py::arg("data"))
      .def_static("FromString", &Payload::FromString)
      .def_static("FromDict", &Payload::FromDict)
      .def("PyMemoryView", &Payload::PyMemoryView)
      .def("ToString", &Payload::ToString)
      .def("ToDict", &Payload::ToDict)
      .def("Data", &Payload::Data)
      .def("Size", &Payload::Size)
      .def("Type", &Payload::Type);

  server_cls
      .def(py::init<int, py::object, int, int>(), py::arg("port"), py::arg("handler") = nullptr,
           py::arg("num_threads_net") = 2, py::arg("num_threads_handler") = 0)
      .def("run", &PyServer::py_run, py::arg("blocking") = true)
      .def("is_running", &PyServer::is_running)
      .def("run_one_pending_handler", &PyServer::run_one_pending_handler)
      .def("stop", &PyServer::py_stop, py::arg("run_pending_handlers") = false)
      .def("set_handler", &PyServer::py_set_handler);

  m.def("path_handler", &path_handler, py::arg("path"),
        "Decorator to automatically register a Python method as a handler for a specific path.\n"
        "\nHandlers are not inherited by other classes.\n"
        "\nArgs:\n"
        "  path: The path for which the handler should be registered.\n"
        "\nReturns:\n"
        "  A function that registers the decorated method to be called instead of OnMessage for the "
        "given path.\n");

  m.def("inspect_path_handlers", &inspect_path_handlers, py::arg("cls"),
        "Inspect all path handlers defined in a Python class.\n"
        "\nArgs:\n"
        "  cls: The Python class to inspect.\n"
        "\nReturns:\n"
        "  A list of tuples where each tuple contains the path and the docstring of a handler.\n"
        "  Handlers are identified by the presence of the '_path_handler' attribute.\n");

  // logging
  py::enum_<spdlog::level::level_enum>(m, "log_level")
      .value("trace", spdlog::level::level_enum::trace)
      .value("debug", spdlog::level::level_enum::debug)
      .value("info", spdlog::level::level_enum::info)
      .value("warn", spdlog::level::level_enum::warn)
      .value("err", spdlog::level::level_enum::err)
      .value("critical", spdlog::level::level_enum::critical)
      .value("off", spdlog::level::level_enum::off)
      .export_values();
  m.def("setup_logger", &setup_logger, py::arg("level_console"), py::arg("level_file"),
        "Creates a new logger with the given log levels for console and file.");
}

}  // namespace interceptor
}  // namespace vci
