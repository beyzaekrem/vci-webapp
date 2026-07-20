#include <interceptor/util.h>

namespace vci {
namespace interceptor {

thread_local bool ThreadHelper::is_network_thread_ = false;

void ThreadHelper::mark_as_network_thread() {
  is_network_thread_ = true;
}

// Function to check if the current thread is a network thread
bool ThreadHelper::is_network_thread() {
  return is_network_thread_;
}

} // namespace interceptor
} // namespace vci
