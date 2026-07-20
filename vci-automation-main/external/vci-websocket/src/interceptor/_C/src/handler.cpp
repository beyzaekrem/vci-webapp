#include <interceptor/connection.h>
#include <interceptor/handler.h>
#include <interceptor/logging.h>

namespace vci {
namespace interceptor {

bool is_blank(const std::string& s) {
  return std::all_of(s.begin(), s.end(), [](unsigned char c) { return std::isspace(c); });
}

std::string fix_docstring_indentation(const std::string& doc) {
  // To vector
  std::istringstream stream(doc);
  std::string line;
  std::vector<std::string> lines;
  bool started_with_empty = false;
  while (std::getline(stream, line)) {
    if (lines.empty() && is_blank(line)) {
      // Ignore leading empty lines
      started_with_empty = true;
    } else {
      lines.push_back(line);
    }
  }

  // Skip the first line (if non-empty) for indent detection
  size_t min_indent = std::string::npos;
  int start_idx = started_with_empty ? 0 : 1;
  for (int i = start_idx; i < lines.size(); ++i) {
    const auto& l = lines[i];
    if (!l.empty()) {
      size_t indent = l.find_first_not_of(' ');
      if (indent != std::string::npos) {
        min_indent = std::min(min_indent, indent);
      }
    }
  }
  if (min_indent == std::string::npos) {
    min_indent = 0;
  }

  // Now reassemble
  std::string result;
  for (const auto& l : lines) {
    if (l.size() >= min_indent && is_blank(l.substr(0, min_indent))) {
      result += l.substr(min_indent);
    } else {
      result += l;
    }
    result += "\n";
  }
  return result;
}

bool MessageHandler::dispatch(std::shared_ptr<MessageIn> message) {
  // TODO logging
  if (message->path() == "INTERFACE") {
    message->Acknowledge(Payload::FromJson(get_interface_json()));
    return true;
  }
  auto it = path_handler_lookup_.find(message->path());
  if (it != path_handler_lookup_.end()) {
    auto path_handler = it->second;
    path_handler.func(message);
    return true;
  } else {
    return OnMessage(message);
  }
}

nlohmann::json MessageHandler::get_interface_json() {
  nlohmann::json interface_dict;
  if (path_handler_lookup_.empty()) {
    interface_dict["INTERFACE"] = "No path defined.";
  }
  for (const auto& it : path_handler_lookup_) {
    interface_dict[it.second.path] = it.second.docstring;
  }
  return interface_dict;
}

void MessageHandler::add_path_handler(PathHander path_handler) {
  if (path_handler.path == "INTERFACE") {
    logger()->error("Path handler for path INTERFACE is reserved. Please use another name.");
    return;
  }
  auto it = path_handler_lookup_.find(path_handler.path);
  if (it != path_handler_lookup_.end()) {
    throw PathAlreadyDefinedError(path_handler.path);
  }
  path_handler_lookup_.insert({path_handler.path, path_handler});
}

bool PyMessageHandler::dispatch(std::shared_ptr<MessageIn> message) {
  register_python_handlers();
  try {
    // checks if the python object cooresponding to "this" C++ object implements a dispatch method
    pybind11::gil_scoped_acquire gil;
    pybind11::object self_py = pybind11::cast(this);

    if (pybind11::object override = pybind11::get_override(this, "dispatch")) {
      return override(message).cast<bool>();
    } else {
      return MessageHandler::dispatch(message);  // fallback to base C++ behavior
    }

  } catch (pybind11::error_already_set& e) {
    if (e.matches(PyExc_KeyboardInterrupt)) {
      message->SkipResponse();
      throw;
    }

    const char* msg = e.what();

    if (e.matches(wrong_payload_error)) {
      if (message->has_responded()) {
        logger()->warn(
            "MessageHandler::dispatch raised a WrongPayloadError (ID: {}) but has already responded. "
            "Error:\n##########\n{}##########",
            message->id(), msg);
      } else {
        logger()->debug(
            "MessageHandler::dispatch raised a WrongPayloadError (ID: {}), will relay to connection. "
            "Error:\n##########\n{}##########",
            message->id(), msg);
        nlohmann::json error_data;
        error_data["what"] = msg + 19;
        message->ErrorResponse(WrongPayloadError::error_string, {Payload::FromJson(error_data)});
      }
      return true;
    }

    if (message->has_responded()) {
      logger()->error(
          "Got a Python error in MessageHandler::dispatch (ID: {}). Will ignore it, because message has responded "
          "already. "
          "Error:\n##########\n{}##########",
          message->id(), msg);
    } else if (msg) {
      logger()->warn(
          "Got a Python error in MessageHandler::dispatch (ID: {}). Will relay to "
          "connection. Error:\n##########\n{}##########",
          message->id(), msg);
      message->ErrorResponse(PathHandlerFailedError::error_string, {Payload::FromString(msg)});
    }

    return true;
  } catch (WrongPayloadError&) {
  }

  return false;
}

void PyMessageHandler::OnConnect(std::shared_ptr<Connection> connection) {
  PYBIND11_OVERRIDE(void, MessageHandler, OnConnect, connection);
}

void PyMessageHandler::OnDisconnect(std::shared_ptr<Connection> connection, bool graceful) {
  PYBIND11_OVERRIDE(void, MessageHandler, OnDisconnect, connection, graceful);
}

bool PyMessageHandler::OnMessage(std::shared_ptr<MessageIn> message) {
  PYBIND11_OVERRIDE(bool, MessageHandler, OnMessage, message);
}

void PyMessageHandler::OnError(std::shared_ptr<MessageIn> message) {
  PYBIND11_OVERRIDE(void, MessageHandler, OnError, message);
}

void PyMessageHandler::check_duplicates_and_docstrings(pybind11::object cls) {
  auto attributes = pybind11::dict(cls.attr("__dict__"));
  pybind11::list existing_paths;
  for (auto attr : attributes) {
    std::string name = pybind11::str(attr.first);
    pybind11::object value = pybind11::reinterpret_borrow<pybind11::object>(attr.second);
    if (pybind11::hasattr(value, "_path_handler")) {
      // Duplicates
      std::string path = pybind11::str(value.attr("_path_handler"));
      if (existing_paths.contains(path)) {
        throw PathAlreadyDefinedError(path, pybind11::str(cls.attr("__name__")));
      }
      existing_paths.append(path);
      // Docstring
      std::string docstring;
      if (pybind11::hasattr(value, "__doc__")) {
        pybind11::object doc = value.attr("__doc__");
        if (!doc.is_none()) {
          docstring = std::string(pybind11::str(doc));
        }
      }
      if (docstring.empty()) {
        logger()->warn("Empty docstring for handler function {} of path {} in class {}. Please add a docstring.", name,
                       path, pybind11::cast<std::string>(pybind11::str(cls.attr("__name__"))));
      }
    }
  }
}

void PyMessageHandler::register_python_handlers() {
  if (!handlers_registered_) {
    pybind11::gil_scoped_acquire acquire;
    auto self = pybind11::cast(this);
    auto cls = self.get_type();
    auto attributes = pybind11::dict(cls.attr("__dict__"));
    for (auto attr : attributes) {
      std::string name = pybind11::str(attr.first);
      pybind11::object value = pybind11::reinterpret_borrow<pybind11::object>(attr.second);
      if (pybind11::hasattr(value, "_path_handler")) {
        std::string path = pybind11::str(value.attr("_path_handler"));
        pybind11::function func = self.attr(name.c_str());
        // Get docstring
        std::string docstring;
        if (pybind11::hasattr(value, "__doc__")) {
          pybind11::object doc = value.attr("__doc__");
          if (!doc.is_none()) {
            docstring = std::string(pybind11::str(doc));
          }
        }
        // Add message handler
        PathHander path_handler(
            path,
            [func](std::shared_ptr<MessageIn> message) {
              pybind11::gil_scoped_acquire acquire;
              func(message);
            },
            docstring);
        logger()->debug("Registering handler {} for path {}", name, path);
        add_path_handler(path_handler);
      }
    }
    handlers_registered_ = true;
  }
}

pybind11::object path_handler(const std::string& path) {
  return pybind11::cpp_function([path](pybind11::function func) -> pybind11::function {
    func.attr("_path_handler") = pybind11::str(path);
    return func;
  });
}

pybind11::dict inspect_path_handlers(pybind11::object cls) {
  pybind11::dict path_handlers;

  pybind11::object dir_func = pybind11::module_::import("builtins").attr("dir");
  pybind11::list attributes = dir_func(cls);
  for (auto attr_name_obj : attributes) {
    std::string attr_name = pybind11::cast<std::string>(attr_name_obj);
    pybind11::object attr = cls.attr(attr_name.c_str());

    if (pybind11::isinstance<pybind11::function>(attr) && pybind11::hasattr(attr, "_path_handler")) {
      pybind11::object path = attr.attr("_path_handler");
      std::string docstring = "";
      if (pybind11::hasattr(attr, "__doc__") && !attr.attr("__doc__").is_none()) {
        docstring = pybind11::cast<std::string>(attr.attr("__doc__"));
      }
      path_handlers[path] = fix_docstring_indentation(docstring);
    }
  }

  return path_handlers;
}

}  // namespace interceptor
}  // namespace vci
