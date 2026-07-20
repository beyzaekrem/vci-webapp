#include "xi_util.h"


void HandleGenTLErrors(const std::string& action, GenTL::GC_ERROR stat) {
  if (stat != GC_ERR_SUCCESS) {
    vci::interceptor::logger()->error("{} failed with error {}", action.c_str(), stat);
  }
}

std::string XiErrorString(XI_RETURN code) {
  switch (code) {
    case XI_OK: return "XI_OK (Function call succeeded)";
    case XI_INVALID_HANDLE: return "XI_INVALID_HANDLE (Invalid handle)";
    case XI_READREG: return "XI_READREG (Register read error)";
    case XI_WRITEREG: return "XI_WRITEREG (Register write error)";
    case XI_FREE_RESOURCES: return "XI_FREE_RESOURCES (Freeing resources error)";
    case XI_FREE_CHANNEL: return "XI_FREE_CHANNEL (Freeing channel error)";
    case XI_FREE_BANDWIDTH: return "XI_FREE_BANDWIDTH (Freeing bandwith error)";
    case XI_READBLK: return "XI_READBLK (Read block error)";
    case XI_WRITEBLK: return "XI_WRITEBLK (Write block error)";
    case XI_NO_IMAGE: return "XI_NO_IMAGE (No image)";
    case XI_TIMEOUT: return "XI_TIMEOUT (Timeout)";
    case XI_INVALID_ARG: return "XI_INVALID_ARG (Invalid arguments supplied)";
    case XI_NOT_SUPPORTED: return "XI_NOT_SUPPORTED (Not supported)";
    case XI_ISOCH_ATTACH_BUFFERS: return "XI_ISOCH_ATTACH_BUFFERS (Attach buffers error)";
    case XI_GET_OVERLAPPED_RESULT: return "XI_GET_OVERLAPPED_RESULT (Overlapped result)";
    case XI_MEMORY_ALLOCATION: return "XI_MEMORY_ALLOCATION (Memory allocation error)";
    case XI_DLLCONTEXTISNULL: return "XI_DLLCONTEXTISNULL (DLL context is NULL)";
    case XI_DLLCONTEXTISNONZERO: return "XI_DLLCONTEXTISNONZERO (DLL context is non zero)";
    case XI_DLLCONTEXTEXIST: return "XI_DLLCONTEXTEXIST (DLL context exists)";
    case XI_TOOMANYDEVICES: return "XI_TOOMANYDEVICES (Too many devices connected)";
    case XI_ERRORCAMCONTEXT: return "XI_ERRORCAMCONTEXT (Camera context error)";
    case XI_UNKNOWN_HARDWARE: return "XI_UNKNOWN_HARDWARE (Unknown hardware)";
    case XI_INVALID_TM_FILE: return "XI_INVALID_TM_FILE (Invalid TM file)";
    case XI_INVALID_TM_TAG: return "XI_INVALID_TM_TAG (Invalid TM tag)";
    case XI_INCOMPLETE_TM: return "XI_INCOMPLETE_TM (Incomplete TM)";
    case XI_BUS_RESET_FAILED: return "XI_BUS_RESET_FAILED (Bus reset error)";
    case XI_NOT_IMPLEMENTED: return "XI_NOT_IMPLEMENTED (Not implemented)";
    case XI_SHADING_TOOBRIGHT: return "XI_SHADING_TOOBRIGHT (Shading is too bright)";
    case XI_SHADING_TOODARK: return "XI_SHADING_TOODARK (Shading is too dark)";
    case XI_TOO_LOW_GAIN: return "XI_TOO_LOW_GAIN (Gain is too low)";
    case XI_INVALID_BPL: return "XI_INVALID_BPL (Invalid sensor defect correction list)";
    case XI_BPL_REALLOC: return "XI_BPL_REALLOC (Error while sensor defect correction list reallocation)";
    case XI_INVALID_PIXEL_LIST: return "XI_INVALID_PIXEL_LIST (Invalid pixel list)";
    case XI_INVALID_FFS: return "XI_INVALID_FFS (Invalid Flash File System)";
    case XI_INVALID_PROFILE: return "XI_INVALID_PROFILE (Invalid profile)";
    case XI_INVALID_CALIBRATION: return "XI_INVALID_CALIBRATION (Invalid calibration)";
    case XI_INVALID_BUFFER: return "XI_INVALID_BUFFER (Invalid buffer)";
    case XI_INVALID_DATA: return "XI_INVALID_DATA (Invalid data)";
    case XI_TGBUSY: return "XI_TGBUSY (Timing generator is busy)";
    case XI_IO_WRONG: return "XI_IO_WRONG (Wrong operation open/write/read/close)";
    case XI_ACQUISITION_ALREADY_UP: return "XI_ACQUISITION_ALREADY_UP (Acquisition already started)";
    case XI_OLD_DRIVER_VERSION: return "XI_OLD_DRIVER_VERSION (Old version of device driver installed to the system.)";
    case XI_GET_LAST_ERROR: return "XI_GET_LAST_ERROR (To get error code please call GetLastError function.)";
    case XI_CANT_PROCESS: return "XI_CANT_PROCESS (Data cannot be processed)";
    case XI_ACQUISITION_STOPED: return "XI_ACQUISITION_STOPED (Acquisition is stopped. It needs to be started to perform operation.)";
    case XI_ACQUISITION_STOPED_WERR: return "XI_ACQUISITION_STOPED_WERR (Acquisition has been stopped with an error.)";
    case XI_INVALID_INPUT_ICC_PROFILE: return "XI_INVALID_INPUT_ICC_PROFILE (Input ICC profile missing or corrupted)";
    case XI_INVALID_OUTPUT_ICC_PROFILE: return "XI_INVALID_OUTPUT_ICC_PROFILE (Output ICC profile missing or corrupted)";
    case XI_DEVICE_NOT_READY: return "XI_DEVICE_NOT_READY (Device not ready to operate)";
    case XI_SHADING_TOOCONTRAST: return "XI_SHADING_TOOCONTRAST (Shading is too contrast)";
    case XI_ALREADY_INITIALIZED: return "XI_ALREADY_INITIALIZED (Module already initialized)";
    case XI_NOT_ENOUGH_PRIVILEGES: return "XI_NOT_ENOUGH_PRIVILEGES (Application does not have enough privileges (one or more app))";
    case XI_NOT_COMPATIBLE_DRIVER: return "XI_NOT_COMPATIBLE_DRIVER (Installed driver is not compatible with current software)";
    case XI_TM_INVALID_RESOURCE: return "XI_TM_INVALID_RESOURCE (TM file was not loaded successfully from resources)";
    case XI_DEVICE_HAS_BEEN_RESETED: return "XI_DEVICE_HAS_BEEN_RESETED (Device has been reset, abnormal initial state)";
    case XI_NO_DEVICES_FOUND: return "XI_NO_DEVICES_FOUND (No Devices Found)";
    case XI_RESOURCE_OR_FUNCTION_LOCKED: return "XI_RESOURCE_OR_FUNCTION_LOCKED (Resource (device) or function locked by mutex)";
    case XI_BUFFER_SIZE_TOO_SMALL: return "XI_BUFFER_SIZE_TOO_SMALL (Buffer provided by user is too small)";
    case XI_COULDNT_INIT_PROCESSOR: return "XI_COULDNT_INIT_PROCESSOR (Could not initialize processor.)";
    case XI_NOT_INITIALIZED: return "XI_NOT_INITIALIZED (The object/module/procedure/process being referred to has not been started.)";
    case XI_RESOURCE_NOT_FOUND: return "XI_RESOURCE_NOT_FOUND (Resource not found(could be processor, file, item...).)";
    case XI_UNKNOWN_PARAM: return "XI_UNKNOWN_PARAM (Unknown parameter)";
    case XI_WRONG_PARAM_VALUE: return "XI_WRONG_PARAM_VALUE (Wrong parameter value)";
    case XI_WRONG_PARAM_TYPE: return "XI_WRONG_PARAM_TYPE (Wrong parameter type)";
    case XI_WRONG_PARAM_SIZE: return "XI_WRONG_PARAM_SIZE (Wrong parameter size)";
    case XI_BUFFER_TOO_SMALL: return "XI_BUFFER_TOO_SMALL (Input buffer is too small)";
    case XI_NOT_SUPPORTED_PARAM: return "XI_NOT_SUPPORTED_PARAM (Parameter is not supported)";
    case XI_NOT_SUPPORTED_PARAM_INFO: return "XI_NOT_SUPPORTED_PARAM_INFO (Parameter info not supported)";
    case XI_NOT_SUPPORTED_DATA_FORMAT: return "XI_NOT_SUPPORTED_DATA_FORMAT (Data format is not supported)";
    case XI_READ_ONLY_PARAM: return "XI_READ_ONLY_PARAM (Read only parameter)";
    case XI_BANDWIDTH_NOT_SUPPORTED: return "XI_BANDWIDTH_NOT_SUPPORTED (This camera does not support currently available bandwidth)";
    case XI_INVALID_FFS_FILE_NAME: return "XI_INVALID_FFS_FILE_NAME (FFS file selector is invalid or NULL)";
    case XI_FFS_FILE_NOT_FOUND: return "XI_FFS_FILE_NOT_FOUND (FFS file not found)";
    case XI_PARAM_NOT_SETTABLE: return "XI_PARAM_NOT_SETTABLE (Parameter value cannot be set (might be out of range or invalid).)";
    case XI_SAFE_POLICY_NOT_SUPPORTED: return "XI_SAFE_POLICY_NOT_SUPPORTED (Safe buffer policy is not supported. E.g. when transport target is set to GPU (GPUDirect).)";
    case XI_GPUDIRECT_NOT_AVAILABLE: return "XI_GPUDIRECT_NOT_AVAILABLE (GPUDirect is not available. E.g. platform isn't supported or CUDA toolkit isn't installed.)";
    case XI_INCORRECT_SENS_ID_CHECK: return "XI_INCORRECT_SENS_ID_CHECK (Incorrect sensor board unique identifier checksum.)";
    case XI_INCORRECT_FPGA_TYPE: return "XI_INCORRECT_FPGA_TYPE (Incorrect or unknown FPGA firmware type used for camera.)";
    case XI_PARAM_CONDITIONALLY_NOT_AVAILABLE: return "XI_PARAM_CONDITIONALLY_NOT_AVAILABLE (Parameter is not available in current context. Available only if another feature is turned on.)";
    case XI_ERR_FRAME_BUFFER_RAM_INIT: return "XI_ERR_FRAME_BUFFER_RAM_INIT (Frame buffer RAM initialization error.)";
    case XI_PROC_OTHER_ERROR: return "XI_PROC_OTHER_ERROR (Processing error - other)";
    case XI_PROC_PROCESSING_ERROR: return "XI_PROC_PROCESSING_ERROR (Error while image processing.)";
    case XI_PROC_INPUT_FORMAT_UNSUPPORTED: return "XI_PROC_INPUT_FORMAT_UNSUPPORTED (Input format is not supported for processing.)";
    case XI_PROC_OUTPUT_FORMAT_UNSUPPORTED: return "XI_PROC_OUTPUT_FORMAT_UNSUPPORTED (Output format is not supported for processing.)";
    case XI_OUT_OF_RANGE: return "XI_OUT_OF_RANGE (Parameter value is out of range)";
    default: return StringFormat("Code %d (Unknown Error)", int(code));
  }
}



