#ifndef CAPTN_UTIL_H
#define CAPTN_UTIL_H
#include <cuda_runtime_api.h>
#include <memory>
#include <stdexcept>
#include <string>

class ExceptionBase : public std::exception {
 public:
  ExceptionBase(const std::string& description);
  virtual const char* what() const noexcept;

 private:
  const std::string description_;
};

class NotImplementedError : public ExceptionBase {
 public:
  NotImplementedError();
};

class CudaError : public ExceptionBase {
 public:
  CudaError(std::string description);
};

class NonCopyable {
 public:
  NonCopyable(const NonCopyable&) = delete;
  NonCopyable& operator=(const NonCopyable&) = delete;

 protected:
  NonCopyable() = default;
  ~NonCopyable() = default;
};

class CameraInvalidException : public std::runtime_error {
 public:
  CameraInvalidException(const std::string& desc);
};

class NotDuringCaptureError : public ExceptionBase {
 public:
  NotDuringCaptureError(const std::string& action);
};

class WrongOrderError : public ExceptionBase {
 public:
  WrongOrderError(const std::string& first, const std::string& second);
};

class InvalidArgumentError : public ExceptionBase {
 public:
  InvalidArgumentError(const std::string& description);
};

class CameraParameterError : public ExceptionBase {
 public:
  CameraParameterError(const std::string& desc);
};

class FrameSkippedError : public ExceptionBase {
 public:
  FrameSkippedError(std::string description);
};

class CacheWriterError : public ExceptionBase {
 public:
  CacheWriterError(std::string description);
};

template <typename... Args>
std::string StringFormat(const std::string& format, Args... args) {
  int size_s = std::snprintf(nullptr, 0, format.c_str(), args...) + 1;  // Extra space for '\0'
  if (size_s <= 0) {
    throw std::runtime_error("Error during formatting.");
  }
  auto size = static_cast<size_t>(size_s);
  std::unique_ptr<char[]> buf(new char[size]);
  std::snprintf(buf.get(), size, format.c_str(), args...);
  return std::string(buf.get(), buf.get() + size - 1);  // We don't want the '\0' inside
}

#define cuda_error_check(cmd)                                                                                 \
  {                                                                                                           \
    cudaError_t e = (cmd);                                                                                    \
    if (e != cudaSuccess) {                                                                                   \
      throw CudaError(                                                                                        \
          StringFormat("Cuda Error during %s (%s:%d): %s", #cmd, __FILE__, __LINE__, cudaGetErrorString(e))); \
    }                                                                                                         \
  }

#endif  // CAPTN_UTIL_H
