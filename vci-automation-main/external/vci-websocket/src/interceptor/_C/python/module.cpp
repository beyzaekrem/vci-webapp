#include <interceptor/logging.h>
#include <pybind11/pybind11.h>

namespace py = pybind11;

namespace vci {
namespace interceptor {

extern void bindings(py::module_ &m);

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
  setup_logger(spdlog::level::info);
  bindings(m);
}

}  // namespace interceptor
}  // namespace vci
