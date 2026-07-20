#ifndef GIBBS_TASKS_CAPTURE_H
#define GIBBS_TASKS_CAPTURE_H

#include <memory>
#include <utility>
#include <vector>
#include <string>
#include <functional>
#include <mutex>
#include <torch/extension.h>

#include "camera.h"
#include "io/cache.h"

std::vector<int> CaptureToDiskDump(
  std::vector<std::shared_ptr<Camera>>& cameras,
  std::shared_ptr<CacheWriter> cache_writer,
  long runtime_limit_ms = 0,
  std::function<void()> callback = nullptr,
  bool track_performance = false
);

std::vector<BufferEntry*> CaptureAll(
  std::vector<std::shared_ptr<Camera>>& cameras,
  int timeout
);


#endif // GIBBS_TASKS_CAPTURE_H
