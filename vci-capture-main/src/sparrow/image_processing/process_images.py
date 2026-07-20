import torch
import torch.nn.functional as torch_funtional
from debayer import Debayer5x5, Layout

import sparrow.gibbs_wrapper as gibbs
from sparrow.calibration_data.calibration_data import CalibrationData
from sparrow.calibration_data.calibration_math import check_resolution, scale_intrincis_matrix
from sparrow.calibration_data.camera_parameters import EMPTY_CAMERA_PARAMETERS, CameraParameters
from sparrow.image_processing import processing_steps
from sparrow.modes.handler_exceptions import InvalidProcessingStepError
from sparrow.utils.logging import logger


class DebayerMalvar:
    def __init__(self) -> None:
        # create and cache all 4 debayer kernels.
        self.debayer_kernels: list[gibbs.PixelLayout : Debayer5x5] = {
            pixellayout: Debayer5x5(layout=Layout[pixellayout.name]).cuda()
            for pixellayout in gibbs.PixelLayout.all
            if pixellayout.name in Layout.__members__
        }

    def debayer(self, image: gibbs.GibbsImage) -> gibbs.GibbsImage:
        if image.pixel_layout in self.debayer_kernels:
            assert image.is_bayer(), f"Input Image should be bayer image but is: {image.pixel_layout.name}"
            kernel = self.debayer_kernels[image.pixel_layout]
            image.pixels = kernel(image.pixels.unsqueeze(0).unsqueeze(0))
            image.pixels.squeeze_()
            image.pixel_layout = gibbs.PixelLayout.RGB
            return image
        msg = f"Debayer_Malvar for pixel_layout {image.pixel_layout} is not implemented."
        raise ValueError(msg)


DEBAYER_MALVAR = DebayerMalvar()


# region process images
def process_images(
    images: list[gibbs.GibbsImage],
    calib_data: CalibrationData | None,
    steps: dict[str:[dict]],
    *,
    in_place: bool = True,
) -> list[gibbs.GibbsImage]:
    """
    Processes images in-place according to a list of steps, applied in the exact order specified.

    By default, a "rotate" step is added and performed last unless explicitly disabled via
    {"rotate": {"enabled": False}}. Steps use `calib_data` (e.g.,
    white balance, distortion) unless parameters are explicitly overridden within the step dict.

    Note: Some processing steps and by extensions entire sequences do not require `calib_data` at all.
    For example this is used during the calibration itself.

    Args:
        images (list[gibbs.GibbsImage]): Images to modify in-place.
        camera_ids (list[str]): Camera IDs corresponding to the `images` list.
        calib_data (CalibrationData): contains CameraParameters keyed by
                        camera_id used for some processing steps.
                        Can be None if the requested steps do not require calibration data.
        steps (dict[str, list[dict]]): Mapping of camera_id (supports wildcards)
            to a sequence of step dictionaries. Each step is a single-key
            dict where the key is the command name and the value is its parameters.

            Example:
                {
                    "C*": [{"debayer": {"method": "subsample"}}, # parameters depend on command
                        {"white_balance": {"white_balance_coefficients": [1,2,1]}}, # overridden wb_coefficients
                        {"non_linear": {}}],
                    "M*": [{"non_linear": {}}, {"hist_scale": {}}]
                }
        in_place: The image processing is performed in-place

    Raises:
        InvalidProcessingStepError: Processing step cannot be applied to the image.
        * The step is incompatible with the image type (e.g., color_correction cannot be applied to mono images).
        * Or the step order is invalid (e.g., color_correction before debayer).
        * Or the step command doesn't exist.
        MissingCalibrationError: A processing step requires calibration properties
            that are missing from `calib_data`.

    Returns:
        list[gibbs.GibbsImage]: The list of processed images (modified in-place).
    """
    assert all(
        isinstance(img, gibbs.GibbsImage) for img in images
    ), f"images passed are not (all) GibbsImage {[type(img) for img in images]}"
    if not in_place:
        images = [i.clone() for i in images]
    steps = processing_steps.de_wildcard(steps, [i.camera_id for i in images])
    if calib_data is None:
        calib_data = {}
    for image in images:
        if image is None:
            continue  # this happens on some older recordings.
        if image.camera_id == "undefined":
            msg = f"Image has 'undefined' camera_id {image}"
            raise ValueError(msg)

        calib: CameraParameters = calib_data.get(image.camera_id, EMPTY_CAMERA_PARAMETERS)

        if calib is None:
            msg = "CameraParameters should never be None"
            raise TypeError(msg)
        steps_list: list = steps.get(image.camera_id, [])

        # pre-process the calibration steps: Injects Default Rotation if not otherwise specified by user
        if not processing_steps.steps_contain(steps_list, "rotate"):
            steps_list.append({"rotate": {}})  # rotate with calibrated data

        # follow the user passed processing steps.
        # camera_steps is a list of dicts: steps.get(camera_id) returns a list
        # Example: camera_steps = [{"white_balance": True}, {"debayer": {"method": "malvar"}}]  # noqa: ERA001
        for step in steps_list:  # step is now {'white_balance': True}
            command, params = processing_steps.get_command(step)  # command = "white_balance", params = {}
            processor_function = STEP_PROCESSOR_MAP.get(command)
            if processor_function is None:
                msg = f"Processing step '{command}' is not recognized."
                raise InvalidProcessingStepError(msg)
            try:
                ret = processor_function(image, params, calib)  # peform step
                assert image == ret, f"{command} {image.camera_id} {params}, image should be muated in-place"
            except Exception as e:
                # oh, no the processing step failed for some reason
                error_context = (
                    f"\n----- Image Processing failed: ----\n"
                    f"Image: {image}\n"
                    f"Failed Step: {command}\n"
                    f"Full Steplist: {steps_list}\n"
                    f"Error: {e}\n"
                )
                logger.error(error_context)
                raise e  # noqa: TRY201
            if image is None:
                msg = f"Image should not be None here. failed Step: {command} for {image.camera_id}"
                raise RuntimeError(msg)
    return images


# endregion


# region process step
# ruff: noqa: ARG001
def process_non_linear(image: gibbs.GibbsImage, params: dict, calib: CameraParameters) -> gibbs.GibbsImage:
    """Applies non-linear delinearization based on image dimensions."""
    # The logic correctly checks dimensions for color/mono delinearization
    if image.is_mono_ndim():
        return gibbs.processing.delinearize_mono(image)
    return gibbs.processing.delinearize_color(image)


def process_white_balance(image: gibbs.GibbsImage, params: dict, calib: CameraParameters) -> gibbs.GibbsImage:
    """Applies white balance, allowing user to overwrite calibrated coefficients."""

    wb_coefficients = calib.get_tensor_with_fallback("white_balance_coefficients", params, image.device)

    if image.is_bayer():
        return gibbs.processing.apply_white_balance_bayer(image, wb_coefficients)
    if image.is_rgb():
        return gibbs.processing.apply_white_balance(image, wb_coefficients)
    msg = "white_balance"
    raise InvalidProcessingStepError(msg, "Image must be rgb or bayer image.")


def process_debayer(image: gibbs.GibbsImage, params: dict, calib: CameraParameters) -> gibbs.GibbsImage:
    """Placeholder for debayering based on method param."""
    method = params.get("method", "malvar")  # Defaults if no method is specified
    pattern_overwrite = params.get("pattern")
    if pattern_overwrite:
        pattern_overwrite = pattern_overwrite.upper()
        if pattern_overwrite in [a.name for a in gibbs.PixelLayout.all]:
            image.pixel_layout = gibbs.PixelLayout(pattern_overwrite)
        else:
            msg = f"overwrite parameter 'pattern' must be a valid bayer pattern. passed: {pattern_overwrite}"
            raise ValueError(msg)

    if method == "interpolate":
        return gibbs.processing.debayer_interpolate(image)
    if method == "malvar":
        return DEBAYER_MALVAR.debayer(image)
    if method == "subsample":
        return gibbs.processing.debayer_subsample(image)
    raise InvalidProcessingStepError(method, f"Debayer method '{method}' is not recognized.")


def process_superkernel(image: gibbs.GibbsImage, params: dict, calib: CameraParameters) -> gibbs.GibbsImage:
    distortion_coeffs: torch.tensor = calib.get_tensor_with_fallback("distortion_coefficients", params, image.device)
    intrinsic_matrix: torch.tensor = calib.get_tensor_with_fallback("camera_matrix", params, image.device)
    resolution: list = calib.get_parameter("resolution", params)

    check_resolution(image.shape, resolution, allow_scale=True)  # gard against illegal image rotation before this step
    intrinsic_matrix = scale_intrincis_matrix(intrinsic_matrix, image.shape, resolution)

    if image.is_mono():
        return gibbs.processing.superkernel_mono(image, intrinsic_matrix, distortion_coeffs)
    if image.is_rgb():
        wb_coefficients = calib.get_tensor_with_fallback("white_balance_coefficients", params, image.device)
        color_correction_matrix = calib.get_tensor_with_fallback("color_correction_matrix", params, image.device)
        return gibbs.processing.superkernel_color(  # ~0.25 ms
            image, wb_coefficients, color_correction_matrix, intrinsic_matrix, distortion_coeffs
        )
    # is_bayer or bgr
    msg = "superkernel"
    raise InvalidProcessingStepError(msg, f"Image must be Mono or RGB. Given PixelLayout: {image.pixel_layout.name}")


def process_undistort(image: gibbs.GibbsImage, params: dict, calib: CameraParameters) -> gibbs.GibbsImage:
    distortion_coeffs: torch.tensor = calib.get_tensor_with_fallback("distortion_coefficients", params, image.device)
    intrinsic_matrix: torch.tensor = calib.get_tensor_with_fallback("camera_matrix", params, image.device)
    resolution: list = calib.get_parameter("resolution", params)

    check_resolution(image.shape, resolution, allow_scale=True)
    intrinsic_matrix = scale_intrincis_matrix(intrinsic_matrix, image.shape, resolution)

    if image.is_mono_ndim():
        return gibbs.processing.undistort_mono(image, intrinsic_matrix, distortion_coeffs)
    return gibbs.processing.undistort_color(image, intrinsic_matrix, distortion_coeffs)


def process_flip_vertically(image: gibbs.GibbsImage, params: dict, calib: CameraParameters) -> gibbs.GibbsImage:
    image.pixels = gibbs.processing.flip_vertical(image.pixels)
    if image.is_bayer():
        # when flipping a bayer image, the pixel layout is mirrored.
        v_flip_map = {
            gibbs.PixelLayout.RGGB: gibbs.PixelLayout.GBRG,
            gibbs.PixelLayout.GBRG: gibbs.PixelLayout.RGGB,
            gibbs.PixelLayout.BGGR: gibbs.PixelLayout.GRBG,
            gibbs.PixelLayout.GRBG: gibbs.PixelLayout.BGGR,
        }
        image.pixel_layout = v_flip_map.get(image.pixel_layout, image.pixel_layout)
    return image


def process_size_scale(image: gibbs.GibbsImage, params: dict, calib: CameraParameters) -> gibbs.GibbsImage:
    """prams (dict) of shape: {"factor": [float], "mode": [str]}"""
    factor = params.get("factor", 0.25)
    mode = params.get("mode", "bilinear")
    if image.is_mono_ndim():
        image.pixels = torch_funtional.interpolate(
            image.pixels.unsqueeze(0).unsqueeze(0), scale_factor=factor, mode=mode, align_corners=False
        )
        image.pixels.squeeze_()
        image.pixels.squeeze_()
        return image
    image.pixels = torch_funtional.interpolate(
        image.pixels.unsqueeze(0), scale_factor=factor, mode=mode, align_corners=False
    )
    image.pixels.squeeze_()
    return image


def process_depth_scale(image: gibbs.GibbsImage, params: dict, calib: CameraParameters) -> gibbs.GibbsImage:
    # user inputs desired depth range for the image in mm
    capture_depth = params.get("capture_max", 16384)  # capture_depth * depth scale
    output_range = params.get("output_range", [8192, 16384])
    output_low, output_hight = output_range[0], output_range[1]

    if output_hight > capture_depth:
        msg = "scale_depth"
        raise InvalidProcessingStepError(
            msg, f"The max_m cannot be higher than caputre_max. Maximum depth: {capture_depth}"
        )

    high = output_hight / capture_depth  # 0.5
    low = output_low / capture_depth  # 0.1

    # scale image intensity to match
    image.pixels = (image.pixels - low) / (high - low)
    image.pixels.clamp_(0, 1)
    return image


def process_hist_scale(image: gibbs.GibbsImage, params: dict, calib: CameraParameters) -> gibbs.GibbsImage:
    low = params.get("low", 10 / 255)
    high = params.get("high", 95 / 255)
    image.pixels = (image.pixels - low) / (high - low)
    image.pixels.clamp_(0, 1)
    return image


def process_color_correction(image: gibbs.GibbsImage, params: dict, calib: CameraParameters) -> gibbs.GibbsImage:
    color_correction_matrix = calib.get_tensor_with_fallback("color_correction_matrix", params, image.device)
    return gibbs.processing.apply_color_correction(image, color_correction_matrix)


def process_rotation(image: gibbs.GibbsImage, params: dict, calib: CameraParameters) -> gibbs.GibbsImage:
    """Applies rotation, allowing parameters like 'rotation' (e.g., 1, 2, 3) or 'enabled': False."""
    # Check for explicit disable flag (e.g., {"rotate": {"enabled": False}})
    if params.get("enabled") is False:
        return image

    # Get the rotation parameter (default to 1, meaning 90 degrees)
    rotation_value = params.get("rot90")
    if rotation_value is None:
        if calib is None or calib.rotation is None:
            msg = "Missing rotation info"
            raise ValueError(msg)
        rotation_value = calib.rotation

    if rotation_value != 0:
        dims_dict: dict[int:tuple] = {2: (0, 1), 3: (1, 2)}
        if image.ndim not in dims_dict:
            raise InvalidProcessingStepError(
                "rotation",
                f"Invalid image shape. image.ndim is {image.ndim} {image} should be in {list(dims_dict.keys())}",
            )
        image.pixels = image.pixels.rot90(k=rotation_value, dims=dims_dict[image.ndim])

    return image


def process_pass(image: gibbs.GibbsImage, *args, **kwargs) -> gibbs.GibbsImage:  # noqa: ANN002, ANN003
    return image


def process_subsample(image: gibbs.GibbsImage, params: dict, *args, **kwargs) -> gibbs.GibbsImage:
    stride = params.get("stride", 2)
    if image.is_mono_ndim():
        image.pixels = image.pixels[0::stride, 0::stride].clone()
    else:
        image.pixels = image.pixels[
            :, 0::stride, 0::stride
        ].clone()  # clone is important here, so we actually allcoate smaller memory.
    return image


# endregion

STEP_PROCESSOR_MAP = {
    "non_linear": process_non_linear,
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
    "subsample": process_subsample,
    "annotate": process_pass,
}
