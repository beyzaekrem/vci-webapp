#ifndef CAPTN_XI_UTIL_H
#define CAPTN_XI_TIL_H

#include <string>
#include <stdexcept>
#include "xi_include.h"
#include "util.h" // uses our custom StringFormat function
#include <interceptor/logging.h>

void HandleGenTLErrors(const std::string& action, GenTL::GC_ERROR stat);

std::string XiErrorString(XI_RETURN code);

#endif // CAPTN_XI_UTIL_H
