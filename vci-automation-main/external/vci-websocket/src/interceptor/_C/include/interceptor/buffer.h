#ifndef VCI_INTERCEPTOR_BUFFER_H
#define VCI_INTERCEPTOR_BUFFER_H

#include <queue>
#include <mutex>
#include <memory>

#include <boost/beast/core.hpp>

namespace vci {
namespace interceptor {

class BufferManager;

class Buffer : public std::enable_shared_from_this<Buffer> {
public:
  Buffer() = default;
  ~Buffer();

  boost::beast::flat_buffer& GetBuffer();
  const unsigned char* Data();
  size_t Size();
  bool Valid();
  void Release();

  bool active_ = true;
private:
  boost::beast::flat_buffer buffer_;
};

class BufferManager {
public:
  BufferManager(const BufferManager&) = delete;
  BufferManager& operator=(const BufferManager&) = delete;
  static BufferManager& GetInstance();

  static std::shared_ptr<Buffer> GetNewBuffer();
  static void ReleaseBuffer(std::shared_ptr<Buffer> buffer);


private:
  BufferManager();
  void AddNewBuffer();

  std::recursive_mutex mutex_;
  std::vector<std::shared_ptr<Buffer>> full_buffers_;
  std::queue<std::shared_ptr<Buffer>> empty_buffers_;
};

} // namespace interceptor
} // namespace vci

#endif // VCI_INTERCEPTOR_BUFFER_H
