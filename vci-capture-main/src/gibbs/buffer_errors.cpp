#include "buffer_errors.h"

#include <cstring>
#include <iostream>
#include <stdlib.h>

#include "util.h"

AlreadyInQueueError::AlreadyInQueueError() : ExceptionBase(
  "Buffer is already queued. Cannot queue again.") {};

BufferIsLockedError::BufferIsLockedError() : ExceptionBase(
  "Buffer cannot be queued because it is still locked.") {};

TransportInterrupted::TransportInterrupted() : ExceptionBase(
  "Buffer transport was interrupted. Data is invalid.") {};

BufferTimeout::BufferTimeout() : ExceptionBase(
  "Buffer operation has timed out.") {};

