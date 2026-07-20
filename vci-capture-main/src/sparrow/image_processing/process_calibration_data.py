import copy

import numpy as np
from torch import nn

from sparrow.calibration_data.calibration_data import CalibrationData
from sparrow.calibration_data.camera_parameters import CameraParameters
from sparrow.modes.handler_exceptions import InvalidProcessingStepError
from sparrow.utils import logger

from . import processing_steps
from .processing_steps import de_wildcard

version = "3.0.0"


def process_calibration_data(
    camera_ids: list[str],
    calib_data: CalibrationData,
    steps: dict[str:[dict]],
) -> dict:
    logger.info(f"process_calibration_data  {steps}")
    steps = de_wildcard(steps, camera_ids)
    calib_json = {
        "meta": {"version": version},
        "cameras": [],
        "raw_calibration": [],
        "processing_applied": [],
    }
    camera_cnt = 0
    for camera_id in camera_ids:
        raw_calib: CameraParameters = calib_data.get(camera_id)
        if raw_calib is None:
            continue  # da machste nix
        if not isinstance(raw_calib, CameraParameters):
            msg = f"calib of {camera_id} is type {type(raw_calib)}"
            raise TypeError(msg)
        calib: CameraParameters = copy.deepcopy(raw_calib)  # create a copy of the calib data.
        # adjust the data so it matches the image that would get output by the processing steps

        steps_list: list = steps.get(camera_id, [])
        if not processing_steps.steps_contain(steps_list, "rotate"):
            steps_list.append({"rotate": {}})  # rotate with calibrated data

        applied_steps = []
        for step in steps_list:  # step is now {'white_balance': True}
            command, params = processing_steps.get_command(step)  # command = "white_balance", params = {}
            processor_function = STEP_PROCESSOR_MAP.get(command)
            if processor_function is None:
                msg = f"Processing step '{command}' is not recognized."
                raise InvalidProcessingStepError(msg)
            try:
                applied_parameters = processor_function(params, calib)  # peform step
                applied_steps.append({command: applied_parameters})

            except Exception as e:
                # oh, no the processing step failed for some reason
                error_context = (
                    f"\n----- Calibration Processing failed: ----\n"
                    f"Camera: {camera_id}\n"
                    f"Failed Step: {command}\n"
                    f"Full Steplist: {steps_list}\n"
                    f"Error: {e}\n"
                )
                logger.error(error_context)
                raise e  # noqa: TRY201 # TODO improve Error chaining

        calib_json["cameras"].append(calib.to_dict())
        calib_json["raw_calibration"].append(raw_calib.to_dict())
        calib_json["processing_applied"].append({"camera_id": camera_id, "steps": applied_steps})
        camera_cnt += 1

    calib_json["meta"]["calibration"] = calib_data.calib_info
    return calib_json


ParameterDict = dict[any]
"""
A variable dictionary contaiting the parameters applied druing a step
"""


def process_pass(params: dict, calib: CameraParameters) -> ParameterDict:  # noqa: ARG001
    return {}


def process_debayer(params: dict, calib: CameraParameters) -> ParameterDict:
    """Placeholder for debayering based on method param."""
    method = params.get("method", "malvar")
    if method == "malvar":
        method = "Malvar-He-Culter"
    factor = 1
    if method == "subsample":
        factor = 0.5

    ret = {"parameters": {"method": method, "bayer_pattern": "BGGR"}}

    if factor != 1:
        scale_resolution(calib, factor)

        camera_matrix = calib.get_parameter_as_list("camera_matrix")
        resolution = calib.get_parameter_as_list("resolution")

        scale_info = {"updated": {"intrinsics": {"camera_matrix": camera_matrix, "resolution": resolution}}}

        ret.update(scale_info)
    return ret


def process_superkernel(params: dict, calib: CameraParameters) -> ParameterDict:
    distortion_coefficients = calib.get_parameter_as_list("distortion_coefficients", params)
    camera_matrix = calib.get_parameter_as_list("camera_matrix", params)
    parameters = {"distortion_coefficients": distortion_coefficients, "camera_matrix": camera_matrix}

    calib.distortion_coefficients.fill_(0)
    calib.colorspace = "sRGB (IEC 61966-2-1)"
    updated = {
        "distortion_coefficients": calib.get_parameter_as_list("distortion_coefficients"),
        "colorspace": calib.colorspace,
        "is_linear": False,
    }
    try:
        white_balance_coefficients = calib.get_parameter_as_list("white_balance_coefficients", params)
        color_correction_matrix = calib.get_parameter_as_list("color_correction_matrix", params)
        parameters.update(
            {
                "white_balance_coefficients": white_balance_coefficients,
                "color_correction_matrix": color_correction_matrix,
            }
        )

        calib.white_balance_coefficients.fill_(1)
        nn.init.eye_(calib.color_correction_matrix.view(3, 3))
        updated.update(
            {
                "white_balance_coefficients": calib.get_parameter_as_list("white_balance_coefficients"),
                "color_correction_matrix": calib.get_parameter_as_list("color_correction_matrix"),
            }
        )
    except ValueError:
        pass

    return {"parameters": parameters, "updated": updated}
    # clips 0, 1


def process_undistort(params: dict, calib: CameraParameters) -> ParameterDict:
    distortion_coefficients = calib.get_parameter_as_list("distortion_coefficients", params)
    camera_matrix = calib.get_parameter_as_list("camera_matrix", params)
    parameters = {"distortion_coefficients": distortion_coefficients, "camera_matrix": camera_matrix}

    calib.distortion_coefficients.fill_(0)
    updated = {"distortion_coefficients": calib.get_parameter_as_list("distortion_coefficients")}

    return {"parameters": parameters, "updated": updated}


def process_flip_vertically(params: dict, calib: CameraParameters) -> ParameterDict:
    msg = "process_flip_vertically not implemented in process_calibration"
    raise NotImplementedError(msg)


def process_size_scale(params: dict, calib: CameraParameters) -> ParameterDict:
    factor = params.get("factor", 0.25)
    scale_resolution(calib, factor)

    ret = {"parameters": {"factor": factor}}
    if factor != 0:
        ret.update(
            {
                "updated": {
                    "intrinsics": {
                        "camera_matrix": calib.get_parameter_as_list("camera_matrix"),
                        "resolution": calib.get_parameter_as_list("resolution"),
                    }
                }
            }
        )
    return ret


def process_rotation(params: dict, calib: CameraParameters) -> ParameterDict:
    if params.get("enabled") is False:
        return {"parameters": {"enabled": False}}

    rotation_value = calib.get_parameter("rotation", params)

    calib.rotate_calibration(desired_rotation=rotation_value)

    camera_matrix = calib.get_parameter_as_list("camera_matrix")
    resolution = calib.get_parameter_as_list("resolution")
    view_matrix = calib.get_parameter_as_list("view_matrix")

    return {
        "parameters": {"rot90": rotation_value},
        "updated": {
            "extrinsic": {"view_matrix": view_matrix},
            "intrinsics": {"camera_matrix": camera_matrix, "resolution": resolution},
        },
    }


def process_white_balance(params: dict, calib: CameraParameters) -> ParameterDict:
    wb: list = calib.get_parameter_as_list("white_balance_coefficients", params)
    calib.white_balance_coefficients.fill_(1)  # wb_coefificents are 1 after they have been applied to the image.

    return {
        "parameters": {"white_balance_coefficients": wb},
        "updated": {"white_balance_coefficients": calib.get_parameter_as_list("white_balance_coefficients")},
    }
    # clip 0, 1


def process_color_correction(params: dict, calib: CameraParameters) -> ParameterDict:
    color_correction_matrix = calib.get_parameter_as_list("color_correction_matrix", params)
    nn.init.eye_(calib.color_correction_matrix.view(3, 3))

    return {
        "parameters": {"color_correction_matrix": color_correction_matrix},
        "updated": {"color_correction_matrix": calib.get_parameter_as_list("color_correction_matrix")},
    }
    # clips 0,1


def process_linear(params: dict, calib: CameraParameters) -> ParameterDict:  # noqa: ARG001
    calib.colorspace = "sRGB (IEC 61966-2-1)"
    return {
        "updated": {"colorspace": calib.colorspace, "is_linear": False},
    }
    # clipping 0,1


def process_hist_scale(params: dict, calib: CameraParameters) -> ParameterDict:  # noqa: ARG001
    low = params.get("low", 10 / 255)
    high = params.get("high", 95 / 255)
    # clipping 0,1

    return {"parameters": {"low": low, "hight": high}}


def process_depth_scale(params: dict, calib: CameraParameters) -> ParameterDict:  # noqa: ARG001
    capture_depth = params.get("capture_max", 16384)  # capture_depth * depth scale
    output_range = params.get("output_range", [8192, 16384])
    unit = params.get("unit", "mm")
    # clipping 0,1
    return {"parameters": {"capture_max": capture_depth, "output_range": output_range, "unit": unit}}


STEP_PROCESSOR_MAP = {
    "non_linear": process_linear,
    "white_balance": process_white_balance,
    "debayer": process_debayer,
    "rotate": process_rotation,
    "superkernel": process_superkernel,
    "undistort": process_undistort,
    "flip_vertically": process_flip_vertically,
    "size_scale": process_size_scale,
    "hist_scale": process_hist_scale,
    "color_correction": process_color_correction,
    "depth_scale": process_depth_scale,
    "annotate": process_pass,
}


## helper


def scale_resolution(params: CameraParameters, scale_factor: float) -> None:
    params.resolution = np.array(params.resolution) * scale_factor
    params.resolution_tensor = params.resolution_tensor * scale_factor
    params.camera_matrix = params.camera_matrix * scale_factor
    params.camera_matrix[-1] = 1
