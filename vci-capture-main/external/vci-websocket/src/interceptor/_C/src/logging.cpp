#include <interceptor/logging.h>
#include "spdlog/sinks/null_sink.h"
#include "spdlog/sinks/rotating_file_sink.h"
#include "spdlog/sinks/stdout_color_sinks.h"

namespace vci {
namespace interceptor {

std::shared_ptr<spdlog::logger> logger_ = spdlog::null_logger_mt("null");

std::shared_ptr<spdlog::logger> logger() {
  return logger_;
}

void setup_logger(
    spdlog::level::level_enum level_console,
    spdlog::level::level_enum level_file) {
  // Create new logger
  auto console_sink = std::make_shared<spdlog::sinks::stdout_color_sink_mt>();
  console_sink->set_level(level_console);
  auto file_sink = std::make_shared<spdlog::sinks::rotating_file_sink_mt>("/tmp/log_interceptor.txt", 1024*1024, 1);
  file_sink->set_level(level_file);
  std::vector<spdlog::sink_ptr> sinks {console_sink, file_sink};
  auto new_logger = std::make_shared<spdlog::logger>("interceptor", sinks.begin(), sinks.end());
  new_logger->set_level(std::min(level_console, level_file));

  // Set
  logger_ = new_logger;
  logger_->debug("Initialized default logger with console level '{}' and file level '{}'",
    spdlog::level::to_string_view(level_console),
    spdlog::level::to_string_view(level_file));
}

void set_logger(std::shared_ptr<spdlog::logger> logger_new) {
  logger_ = logger_new;
}

} // namespace interceptor
} // namespace vci
