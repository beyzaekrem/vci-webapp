/**
 * This module defines the CameraSystemData interface, which represents the data structure
 * containing information about the camera system retrieved from the capture server.
 * It includes details such as camera count, parameters, handle information, parameter JSON, extended manifest, and serial number information.
 * This interface is used in the CaptureServerConnection class to store and manage the camera system data received from the capture server.
 * @packageDocumentation
 */

/**
 * Data structure that contains a lot of information from the capture server, including camera count, parameters, handle information,
 * parameter JSON, extended manifest, and serial number information.
 *
 * @property camera_count - The total number of cameras in the system.
 * @property camera_parameters - The parameters associated with the cameras.
 * @property handle_info - An object mapping string keys to string values containing handle-related information.
 * @property parameter_json - Available parameters.
 * @property extended_manifest - An array containing the xiApi manifests for each camera, but extended with additional information and parsed as JSON.
 * @property serial_numbers - Information about the serial numbers of the cameras.
 */
export interface CameraSystemData {
  camera_count: number;
  camera_parameters: CameraParams;
  handle_info: { [key: string]: string };
  parameter_json: any;
  extended_manifest: ExtendedManifestArray;
  serial_numbers: SerialNumberInfo;

}

/**
 * Serial number lookup information for cameras.
 */
interface SerialNumberInfo {
  by_sn: { [key: string]: number };
  by_index: { [key: number]: string };
  cam_shorthands: { [key: number]: string };
}

/**
 * Array of parameter blocks for each camera.
 */
interface CameraParams extends Array<Params> {
}

/**
 * Parameters for a single camera.
 */
export interface Params {
  device_sn: Param;
  device_manifest: Param;
  stream_running: Param;
  rel_zoom_center_x: Param;
  width: Param;
  height: Param;
  exposure: Param;
  vertical_flip: Param;
  trigger_source: Param;
}

export interface XiError {
  errorType: string;
  errorMessage: string;
}

/**
 * Value container returned by the camera API.
 */
export interface RegisterValue {
  value: string;
  error: XiError;
}

/**
 * Parameter value with bounds and increment.
 */
export interface Param {
  value: RegisterValue | undefined
  minVal: RegisterValue | undefined
  maxVal: RegisterValue | undefined
  inc: RegisterValue | undefined
}

/**
 * Array of manifest entries for a camera.
 */
interface ExtendedManifestArray extends Array<ExtendedManifest> { }

/**
 * Manifest entries for a single camera.
 */
export interface ExtendedManifest extends Array<ManifestParam> { }

/**
 * Common fields for manifest parameters.
 */
export interface ManifestParam {
  ManifestGroup: string;
}

/**
 * Manifest entry for a XiAPI parameter.
 */
export interface ManifestXiParam extends ManifestParam {
  Xiapi_Par: string;
  DataType: string;
  Description: string;
  DisplayName: string;
  ImposedAccessMode: string;
  currentValue: Param;
  EnumEntry: Array<EnumEntry>;
}

/**
 * Manifest entry for a register parameter.
 */
export interface ManifestRegisterParam extends ManifestParam {
  Name: string;
}

/**
 * Enum entry for a manifest parameter.
 */
interface EnumEntry {
  Value: string;
  DisplayName: string;
}
