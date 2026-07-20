#include "camera.h"
#include <string>

std::string TriggerSourceToString(TriggerSource source) {
  switch (source) {
    case TriggerSource::Hardware:
      return "Hardware";
      break;

    default:
      return "Software";
      break;
  }
}
TriggerSource StringToTriggerSource(std::string str) {
  if (str == "Hardware") return TriggerSource::Hardware;
  if (str == "Software") return TriggerSource::Software;
  throw std::runtime_error("unknown strigger source");
}