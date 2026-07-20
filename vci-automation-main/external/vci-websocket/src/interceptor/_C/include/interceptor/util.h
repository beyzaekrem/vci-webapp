#ifndef VCI_INTERCEPTOR_UTIL_H
#define VCI_INTERCEPTOR_UTIL_H

#include <thread>

namespace vci {
namespace interceptor {

class ThreadHelper {
public:
  static void mark_as_network_thread();
  static bool is_network_thread();
private:
  static thread_local bool is_network_thread_;
};

} // namespace interceptor
} // namespace vci

#endif // VCI_INTERCEPTOR_MESSAGE_H
