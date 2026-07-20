#include <interceptor/buffer.h>

#include <iostream>

namespace vci {
namespace interceptor {

Buffer::~Buffer() {
}

boost::beast::flat_buffer& Buffer::GetBuffer() {
  return buffer_;
}

const unsigned char* Buffer::Data() {
  return (unsigned char*) buffer_.data().data();
}

size_t Buffer::Size() {
  return boost::asio::buffer_size(buffer_.data());
}

bool Buffer::Valid() {
  return active_;
}

void Buffer::Release() {
  if (active_) {
    active_ = false;
    buffer_.clear();
    BufferManager::ReleaseBuffer(shared_from_this());
  }
}

BufferManager& BufferManager::GetInstance() {
    static BufferManager instance;
    return instance;
}

std::shared_ptr<Buffer> BufferManager::GetNewBuffer() {
  BufferManager& bm = GetInstance();
  std::lock_guard<std::recursive_mutex> guard(bm.mutex_);
  std::shared_ptr<Buffer> new_buffer;
  if (bm.empty_buffers_.size() == 0) {
    bm.AddNewBuffer();
  }
  new_buffer = bm.empty_buffers_.front();
  new_buffer->active_ = true;
  bm.empty_buffers_.pop();
  bm.full_buffers_.push_back(new_buffer);
  return new_buffer;
}

void BufferManager::ReleaseBuffer(std::shared_ptr<Buffer> buffer) {
  BufferManager& bm = GetInstance();
  std::lock_guard<std::recursive_mutex> guard(bm.mutex_);
  auto it = std::find(bm.full_buffers_.begin(), bm.full_buffers_.end(), buffer);
  if (it != bm.full_buffers_.end()) {
      bm.full_buffers_.erase(it);
      bm.empty_buffers_.push(buffer);
  }
}

BufferManager::BufferManager() {
  for (int i=0; i<4; ++i) {
    AddNewBuffer();
  }
}

void BufferManager::AddNewBuffer() {
  std::lock_guard<std::recursive_mutex> guard(mutex_);
  empty_buffers_.push(std::make_shared<Buffer>());
}

} // namespace interceptor
} // namespace vci
