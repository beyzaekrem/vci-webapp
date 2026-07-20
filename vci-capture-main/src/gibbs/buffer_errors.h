#ifndef CAPTN_BUFFER_ERRORS_H
#define CAPTN_BUFFER_ERRPRS_H

#include <fcntl.h>
#include <unistd.h>
#include <fstream>
#include <map>
#include <mutex>
#include <stdexcept>
#include <vector>

#include "util.h"

class AlreadyInQueueError : public ExceptionBase {
 public:
  AlreadyInQueueError();
};

class BufferIsLockedError : public ExceptionBase {
 public:
  BufferIsLockedError();
};

class TransportInterrupted : public ExceptionBase {
 public:
  TransportInterrupted();
};

class BufferTimeout : public ExceptionBase {
 public:
  BufferTimeout();
};

class GenTLError : public ExceptionBase {
  using ExceptionBase::ExceptionBase;
};

#endif  // CAPTN_BUFFER_ERRPRS_H
