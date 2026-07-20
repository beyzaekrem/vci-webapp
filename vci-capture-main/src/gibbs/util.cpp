#include "util.h"

ExceptionBase::ExceptionBase(const std::string& description) : description_(description) {}

const char* ExceptionBase::what() const noexcept {
  return description_.c_str();
}

NotImplementedError::NotImplementedError() : ExceptionBase("Function not implemented") {}

CudaError::CudaError(std::string description) : ExceptionBase(description) {}

CameraInvalidException::CameraInvalidException(const std::string& desc) : std::runtime_error(desc) {}

NotDuringCaptureError::NotDuringCaptureError(const std::string& action)
    : ExceptionBase(StringFormat("Action '%s' not possible while capturing is active.", action.c_str())) {}

FrameSkippedError::FrameSkippedError(std::string description) : ExceptionBase(description) {}
CacheWriterError::CacheWriterError(std::string description) : ExceptionBase(description) {}

/**
 * @brief Construct a new Wrong Order Error:: Wrong Order Error object.
 *
 * @param first Initial action that was executed.
 * @param second Second action, that is not possible after the first.
 */
WrongOrderError::WrongOrderError(const std::string& first, const std::string& second)
    : ExceptionBase(StringFormat("Cannot call '%s' after '%s'.", second.c_str(), first.c_str())) {}

InvalidArgumentError::InvalidArgumentError(const std::string& description) : ExceptionBase(description) {}

CameraParameterError::CameraParameterError(const std::string& description) : ExceptionBase(description) {}