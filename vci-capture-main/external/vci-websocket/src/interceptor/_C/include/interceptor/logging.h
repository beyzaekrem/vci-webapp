#ifndef VCI_INTERCEPTOR_LOGGING_H
#define VCI_INTERCEPTOR_LOGGING_H

#include "spdlog/spdlog.h"

namespace vci {
namespace interceptor {

std::shared_ptr<spdlog::logger> logger();

void setup_logger(spdlog::level::level_enum level_console = spdlog::level::warn,
                  spdlog::level::level_enum level_file = spdlog::level::info);

void set_logger(std::shared_ptr<spdlog::logger> logger);

}  // namespace interceptor
}  // namespace vci

#endif  // VCI_INTERCEPTOR_LOGGING_H
