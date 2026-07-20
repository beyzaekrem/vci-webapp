import copy

import numpy as np
import torch
from PIL import Image

import sparrow.gibbs_wrapper as gibbs
from sparrow.calibration_data.camera_parameters import EMPTY_CAMERA_PARAMETERS, CameraParameters, get_camera_parameters
from sparrow.gibbs_wrapper import interceptor
from sparrow.image_processing.charuco_detection import CharucoDetector
from sparrow.image_processing.codecs import encode_images
from sparrow.image_processing.color_calibration import ColorCalibrator
from sparrow.image_processing.process_images import process_images
from sparrow.image_processing.processing_steps import StepDefaults, append_step, steps_contain
from sparrow.mode_shared import CAMERA_MANAGER, CONTROL_MANAGER, PERSISTENT_DATA
from sparrow.modes.common import ImagePackage
from sparrow.modes.mode import ModeHandler
from sparrow.utils import logger

from .handler_exceptions import MissingCalibrationError
from .mode_util import clean_requested_camera_ids, get_info, require_parameter

IS_MONO_DIM = 2
IS_COLOR_DIM = 3


class CalibrationHandler(ModeHandler):
    @classmethod
    def mode_name(cls) -> str:
        return "calibration"

    # record sequence to storage

    def __init__(self) -> None:
        super().__init__()
        logger.info("Initialize Calibration Handler")

        self.color_calibrator = ColorCalibrator()
        self.charuco_detector = CharucoDetector()
        self.frame_counter = -1

    def get_status(self, *, verbose: bool) -> dict:  # noqa: ARG002
        return {
            "num_cameras": CAMERA_MANAGER.camera_cnt,
            "camera_ids": CAMERA_MANAGER.camera_ids,
        }

    def charuco_detection(
        self,
        requested_camera_ids: list[str],
        detection_processing_steps: dict[str : list[dict]],
        processing_steps: dict[str : list[dict]],
        *,
        get_rgb: bool,
    ) -> tuple[dict, list[gibbs.GibbsImage]]:
        logger.debug("capture image for charuco detection")
        self.frame_counter += 1
        raw_images = CAMERA_MANAGER.capture_images(requested_camera_ids)
        logger.debug("process image")
        # TODO: UPDATE GibbsImage
        images: list[gibbs.GibbsImage] = process_images(
            raw_images, PERSISTENT_DATA.calibration_data, detection_processing_steps
        )
        logger.debug("detect charuco board")

        detections, detection_success = self.charuco_detector.detect_board(images)

        if get_rgb:
            logger.debug("prepare rgb image to return")
            if steps_contain(
                processing_steps, "annotate"
            ):  # if any image is supposed to be annotated we just annotate all.
                logger.debug("annotate return image")
                self.charuco_detector.annotate_images(images, detections)

        logger.debug(f"return images len {len(images)}")

        detection_info = {
            "detection_success": detection_success,
            "detections": detections,
            "shapes": [image.shape if image is not None else None for image in images],
        }
        return detection_info, images

    def color_checker_detection(
        self,
        requested_camera_ids: list[str],
        detection_processing_steps: dict[str : list[dict]],
        padding: int,
        method: callable,
        processing_steps: dict[str : list[dict]],
        overexposure_limit: float,
        underexposure_limit: float,
        *,
        get_rgb: bool,
    ) -> tuple[dict, list[gibbs.GibbsImage]]:
        # COLOR_CHECKER_DETECTION
        # capture image
        logger.debug("capture image for color checker detection")
        self.frame_counter += 1
        raw_images = CAMERA_MANAGER.capture_images(requested_camera_ids)
        frame_idx = self.frame_counter
        logger.debug("process image")
        images: list[gibbs.GibbsImage] = process_images(
            raw_images, PERSISTENT_DATA.calibration_data, detection_processing_steps, in_place=False
        )
        logger.debug("detect color checker")
        all_swatches = []
        annotations = []
        calibration_entries: dict = []
        detection_success: list[bool] = []
        max_exposures: list[float] = []
        exposure_limit_tests: list[str] = []
        in_exposure_range: list[bool] = []
        for image in images:

            # perform detection + color calibration on it
            img = image.cpu().pixels.numpy()
            if image.ndim == IS_COLOR_DIM:
                img = np.transpose(img, (1, 2, 0))  # From (3, 2304, 2664) to (2304, 2664, 3)
            white_balance, correction_matrix, swatches, annotation_overlay = self.color_calibrator.calibrate_color(
                img, padding, method, annotation_info=f"{image.camera_id} frame {frame_idx}"
            )
            # check detection and calibration results

            if steps_contain(processing_steps, "annotate"):
                annotations.append(annotation_overlay)

            if swatches is not None:  # detection succeeded
                logger.debug(f"color checker detection succeded for {image.camera_id}")
                detection_success.append(True)
                all_swatches.append(swatches.flatten().tolist())
                # max value of the white swatch. If it's overexposed the color calibration failes.
                # For our images it tints the image pink/green.
                max_exposure = round(float(np.max(swatches[18])), 2)
                max_exposures.append(max_exposure)
                # check exposure limit
                if max_exposure > overexposure_limit:
                    exposure_limit_tests.append("overexposed")
                    in_exposure_range.append(False)
                elif max_exposure < underexposure_limit:
                    exposure_limit_tests.append("underexposed")
                    in_exposure_range.append(False)
                else:
                    exposure_limit_tests.append("exposure good")
                    in_exposure_range.append(True)

                if white_balance is not None:  # calibration entry to color cameras
                    calibration_entries.append(
                        {
                            "camera_id": image.camera_id,
                            "intrinsics": {
                                "white_balance_coefficients": white_balance.flatten().tolist(),
                                "color_correction_matrix": correction_matrix.flatten().tolist(),
                            },
                        }
                    )
                else:
                    # no calibration entry for mono cameras. we only want to check the brightness/exposure limits
                    calibration_entries.append({})
            else:  # detection failed
                logger.debug(f"color checker detection failed for {image.camera_id}")
                detection_success.append(False)
                all_swatches.append(None)
                max_exposures.append(-1)
                exposure_limit_tests.append("no detection")
                calibration_entries.append({"camera_id": image.camera_id})
                in_exposure_range.append(False)

        logger.debug(f"len annotations {len(annotations)}")
        return_images: list[gibbs.GibbsImage] = []
        if get_rgb:
            logger.debug("prepare rgb image to return")
            new_calib_data = {}
            new_camera_parameters: dict[str, CameraParameters] = get_camera_parameters(
                {"cameras": calibration_entries}, PERSISTENT_DATA.camera_rotations
            )
            for cam_id in requested_camera_ids:
                # we create a copy of the previous calib and update it with the data was just captured,
                # so we can process an example image with the new color calibration.
                # we do NOT keep the calib data, that decision is up to the API user.
                prev_param: CameraParameters = PERSISTENT_DATA.calibration_data.get(cam_id, EMPTY_CAMERA_PARAMETERS)
                prev_param = copy.deepcopy(prev_param)
                new_param: CameraParameters = new_camera_parameters.get(cam_id, EMPTY_CAMERA_PARAMETERS)
                new_param.inherit_from(prev_param)
                new_calib_data[cam_id] = new_param

            images = raw_images
            images = process_images(images, new_calib_data, processing_steps)
            if steps_contain(processing_steps, "annotate"):
                logger.debug("annotate return image")
                for annotation, image in zip(annotations, images, strict=True):
                    annotation_np = torch.from_numpy(annotation)
                    if annotation_np.ndim == IS_COLOR_DIM:
                        annotation_np = annotation_np.permute(2, 0, 1)
                    annotation_np = annotation_np.to("cuda:0")
                    image.pixels = torch.clamp((image.pixels + annotation_np), 0.0, 1.0)
            return_images = images

        logger.debug(f"return images len {len(return_images)}")
        logger.debug(f"max_exposures {max_exposures}")
        # format results
        detection_info = {
            "frame_idx": frame_idx,
            "camera_ids": requested_camera_ids,
            "detection_success": detection_success,
            "swatches": all_swatches,
            "calib_file_entries": calibration_entries,
            "max_exposures": max_exposures,
            "in_exposure_limit": in_exposure_range,
            "exposure_limit_tests": exposure_limit_tests,
            "exposure_limit": [underexposure_limit, overexposure_limit],
        }

        return detection_info, return_images

    def calculate_image_brightness(
        self, requested_camera_ids: list[str], processing_steps: dict[str : list[dict]]
    ) -> tuple[dict, list[gibbs.GibbsImage]]:
        # get overall image brightness between 0 and 1. Can be used to adjust exposure when gain or illumination
        # changes to match image brightness
        self.frame_counter += 1
        raw_images = CAMERA_MANAGER.capture_images(requested_camera_ids)
        frame_idx = self.frame_counter
        images = process_images(raw_images, PERSISTENT_DATA.calibration_data, processing_steps)
        brightnesses: list[float] = []
        for image in images:
            img = image.cpu().pixels.numpy()
            if img.ndim == IS_COLOR_DIM:
                img = np.transpose(img, (1, 2, 0))  # From (3, 2304, 2664) to (2304, 2664, 3)
            # with PIl Image
            pil_image = Image.fromarray((img * 255).astype(np.uint8))
            greyscale_image = pil_image.convert("L")
            histogram = greyscale_image.histogram()
            pixels = sum(histogram)
            brightness = scale = len(histogram)

            for index in range(scale):
                ratio = histogram[index] / pixels
                brightness += ratio * (-scale + index)

            max_brightness = 255
            brightnesses.append(1 if brightness == max_brightness else brightness / scale)

        info = {
            "frame_idx": frame_idx,
            "camera_ids": requested_camera_ids,
            "brightnesses": brightnesses,
        }
        return info, images

    @interceptor.path_handler("COLOR_CHECKER_DETECTION")
    def _path_color_checker_detection(self, message: interceptor.MessageIn) -> None:
        """

        Captures an image and performs color checker detection on it.
        We are expecting a x-rite 24 color board. The detection is based on aruco
        codes taped to the corners of the board.

        Returns the detected swatches and calcualted white_balance coefficients and color correction matrices.
        The server does not save the calibration result.

        Args:
            payload (list):
                A list containing:
                - 0 (json): {
                    "camera_ids" (list[str], optional, default=None - all cameras): cameras to perform detection with
                    "detection_processing_steps" (list[str], optional, default=["debayer_subsample"]): The processing
                                            steps applied to the image before perfoming the color checker detection.
                    "padding" (float, optional, default=0.7): Padding size added around each color patch.
                    "method" (str, optional, default="Cheung 2004"): method used to calcualte color correction matrix.
                    "overexposure_limit" (float, optional, default=0.95): limits how hight the exposure per channel
                                                                        is allowed to be on the white patch.
                    "underexposure_limit" (float, optional, default=0.8): limits how low the exposure per channel
                                                                        is allowed to be on the white patch.
                    "rgb" (bool, optional, default=False): set to True to request images
                    "steps" (list[str], optional, default=["debayer_subsample", "white_balance", "color_correction",
                    "non_linear", "annotate"]): processing steps applied to the return images. The step "annotate"
                                                is supported here.
                    "format" (str, optional, default="jpg"): encoding format of the images
                    "quality" (int, optional, default="98"): encoding quality of the images.
                }

        Returns:
            payload (list):
                A list containing:
                - 0 (json): The detection results as a JSON object with the following structure: {
                    "frame_idx" (int): frame index of capture.
                    "camera_ids" (list[str]): requested camera_ids,
                    "entry_infos": entry_infos,
                    "detection_success" (list[bool]): a bool for each camera_id that indicates detection success,
                    "swatches" list[list[float]]: detected colors for the 24 patches of the x-rite board for each camera
                    "calib_file_entries" list[dict | None]: calibration entires for each camera
                                                            with the following strcture:{
                                                                "camera_id" (str)
                                                                "intrinsics" : {
                                                                        "white_balance_coefficients" (list[float])
                                                                        "color_correction_matrix" (list[float])
                                                                    }
                                                            }
                    "max_exposures" list[float]: highest image value of the white patch in any channel, for every camera
                    "in_exposure_limit" list[bool]: indicated if the image was over or underexposed
                    given the max_exposure value and the exposure_limit,
                    "exposure_limit_tests" list[str]: inidcated the detection and exposure test result.
                                            Options: ["no detection", "overexposed", "underexposed", "exposure good"]
                    "exposure_limit" list[float]: [underexposure_limit, overexposure_limit],
                    "get_rgb": True if images (mono or color) included in payload,
                    "image_info" (list[dict]): each image in the payload has a correspoding image_info entry
                                                of the following strcuture:{
                                                    "camera_id" (str): id the the capture camera
                                                    "format" (str): encoding_format,
                                                    "image_type" (str): "rgb"
                                                    "shape" (list[int]): image shape
                                                },
                }
                - 1-4 (bytes, optional): images processed using the new data. Optionally with annotation.
        Raises:
            CamerasStoppedError
            InvalidProcessingStepError
        """

        # COLOR_CHECKER_DETECTION
        logger.info("color checker detection")
        info = get_info(message)
        # processing steps should be only a debayering step. Though which one is used doesn't really matter.
        detection_processing_steps = info.get("detection_processing_steps", StepDefaults.COLOR_CHECKER)
        padding = info.get("padding", 0.7)
        method = info.get("method", "Cheung 2004")
        overexposure_limit = info.get("overexposure_limit", 0.95)
        underexposure_limit = info.get("underexposure_limit", 0.8)

        # we can return an rgb image. This will be processed using the new data, if the detection worked.
        #  User may also add detection annotation though steps
        get_rgb = info.get("rgb", False)
        processing_steps = info.get("steps", append_step(StepDefaults.COLOR_CHECKER, {"annotate": {}}))
        enc_format = info.get("format", "jpg")  # jpg, exr
        enc_quality = info.get("quality", 98)
        requested_camera_ids: list[int] = clean_requested_camera_ids(info.get("camera_ids"), CAMERA_MANAGER.camera_ids)

        detection_info, images = self.color_checker_detection(
            requested_camera_ids,
            detection_processing_steps,
            padding,
            method,
            processing_steps,
            overexposure_limit,
            underexposure_limit,
            get_rgb=get_rgb,
        )
        logger.info(f"detection_success {detection_info.get('detection_success')}")

        package = ImagePackage(extra_info=detection_info, frame_idx=self.frame_counter, camera_ids=requested_camera_ids)
        if get_rgb:
            package.add_images(encode_images(images, enc_format, quality=enc_quality))

        logger.info("send acknowledge message")
        message.Acknowledge(package.to_payload())

    @interceptor.path_handler("SET_CHARUCO_BOARD")
    @CONTROL_MANAGER.protected_path()
    def _path_set_charuco_board(self, message: interceptor.MessageIn) -> None:
        """
        Creates a charuco board object given the new parameters to perform detections with.

        Args:
           payload (list):
                A list containing:
                - 0 (json): {
                    "dict_name" (str): name of the aruco dicionary used by the board. (e.g: "4X4_1000")
                    "size" (tuple[int]): the size of the aurco board. (e.g.: (29,19))
                    "square_length" (float): the length of a single board square in meters. (e.g: 0.040 = 4 cm)
                    "marker_length" (float): the length of a single aruco marker in meters. (e.g: 0.031 = 3.1 cm)
                }

        Returns:
            Acknowledge
        Raises:
            Whichever Errors occur if you input invalid board parameters.
            ControlTakenError
        """
        info = get_info(message)
        # processing steps should be only a debayering step. Though which one is used doesn't really matter.
        dict_name = require_parameter(info, "dict_name")
        size = require_parameter(info, "size")
        square_length = require_parameter(info, "square_length")
        marker_length = require_parameter(info, "marker_length")

        self.charuco_detector.set_board(dict_name, size, square_length, marker_length)
        logger.debug(f"set charuco board {dict_name}, {size}, {square_length}, {marker_length}")
        message.Acknowledge()

    @interceptor.path_handler("CHARUCO_DETECTION")
    def _path_charuco_detection(self, message: interceptor.MessageIn) -> None:
        """

        Captures an image and performs charuco board detection on it. Returns the detected corners and ids.
        You can request an annotated image displaying the detection result.

        Args:
            payload (list):
                A list containing:
                - 0 (json): {
                    "camera_ids" (list[str], optional, default=None - all cameras): cameras to perform detection with
                    "detection_processing_steps" (list[str], optional, default=["debayer_subsample"]): The processing
                                            steps applied to the image before perfoming the color checker detection.
                    "padding" (float, optional, default=0.7): Padding size added around each color patch.
                    "method" (str, optional, default="Cheung 2004"): method used to calcualte color correction matrix.
                    "overexposure_limit" (float, optional, default=0.95): limits how hight the exposure per channel
                                                                        is allowed to be on the white patch.
                    "underexposure_limit" (float, optional, default=0.8): limits how low the exposure per channel
                                                                        is allowed to be on the white patch.
                    "rgb" (bool, optional, default=False): set to True to request images
                    "steps" (list[str], optional, default=["debayer_subsample", "white_balance", "color_correction",
                    "non_linear", "annotate"]): Processing steps applied to the return images. The step "annotate"
                                                is supported here.
                    "format" (str, optional, default="jpg"): encoding format of the images
                    "quality" (int, optional, default="98"): encoding quality of the images.
                }

        Returns:
            payload (list):
                A list containing:
                - 0 (json): The detection results as a JSON object with the following structure: {
                    "frame_idx" (int): frameidx of capture,
                    "camera_ids" (list[str]): requested camera_ids,
                    "detection_success" (list[bool]): a bool for each camera_id that indicates detection success
                    "detections" (list[dict]): each captured image has a corresponding detection entry
                                                of the following structure:{
                                                    "corners" (list[int]): pixel locations of detected corners
                                                    "ids" list[int]: charuco id of detected corners
                                                }
                    "shapes": tesnor shape per camera [(C), H, W]
                    "get_rgb": True if images (mono or color) included in payload,
                    "image_info" (list[dict]): each image in the payload has a correspoding image_info entry
                                                of the following structure:{
                                                    "camera_id" (str): id the the capture camera
                                                    "format" (str): encoding_format,
                                                    "image_type" (str): "rgb"
                                                    "shape" (list[int]): image shape
                                                },
                }
                - 1-4 (bytes, optional): images processed using the new data. Optionally with annotation.
        Raises:
            MissingCalibrationError: all cameras need to have their rotation set
            CamerasStoppedError
            InvalidProcessingStepError
        """
        info = get_info(message)
        # processing steps should be only a debayering step. Though which one is used doesn't really matter.
        detection_processing_steps = info.get("detection_processing_steps", StepDefaults.DEBAYERED)
        requested_camera_ids: list[int] = clean_requested_camera_ids(info.get("camera_ids"), CAMERA_MANAGER.camera_ids)

        # we can return an rgb image.
        # User may add detection annotation though step "annotate"
        get_rgb = info.get("rgb", False)
        processing_steps = info.get("steps", append_step(StepDefaults.UNCALIBRATED, "annotate"))
        enc_format = info.get("format", "jpg")  # jpg, exr
        enc_quality = info.get("quality", 98)

        for camera_id in requested_camera_ids:
            c: CameraParameters = PERSISTENT_DATA.calibration_data.get(camera_id)
            if c is None or c.rotation is None:
                raise MissingCalibrationError(camera_id, "charuco detetection. Perform rotation calibration")

        detection_info, images = self.charuco_detection(
            requested_camera_ids, detection_processing_steps, processing_steps, get_rgb=get_rgb
        )

        package = ImagePackage(extra_info=detection_info, camera_ids=requested_camera_ids, frame_idx=self.frame_counter)
        logger.info(f"detection_sucess {detection_info.get('detection_success')}")
        if get_rgb:
            logger.info("encode return images")
            package.add_images(encode_images(images, enc_format, quality=enc_quality))
        logger.info("send acknowledge message")
        message.Acknowledge(package.to_payload())

    @interceptor.path_handler("CALCULATE_IMAGE_BRIGHTNESS")
    def _path_calculate_image_brightness(self, message: interceptor.MessageIn) -> None:
        """

        Captures an image and calcualtes the average image brightness.

        Args:
            payload (list):
                A list containing:
                - 0 (json): {
                    "camera_ids" (list[str], optional, default=None - all cameras): cameras to perform brightness
                    calcualtion with
                    "steps" (list[str], optional, default=["debayer_subsample", "white_balance", "color_correction",
                    "non_linear"]):
                }

        Returns:
            payload (list):
                A list containing:
                - 0 (json): The detection results as a JSON object with the following structure: {
                    "frame_idx": frame_idx,
                    "camera_ids": requested camera_ids,
                    "entry_infos": entry_infos,
                    "brightnesses" (list[float]): a float value in range [0, 1] indicating the average image brighntess,
                      for each camera
                    "image_info": [],
                }
        Raises:
            CamerasStoppedError
            InvalidProcessingStepError
        """
        logger.info("get image brightness")
        info = get_info(message)
        requested_camera_ids: list[int] = clean_requested_camera_ids(info.get("camera_ids"), CAMERA_MANAGER.camera_ids)
        processing_steps = info.get("steps", StepDefaults.COLOR_PRETTY)

        brightness_info, _ = self.calculate_image_brightness(requested_camera_ids, processing_steps)
        logger.info("send acknowledge message")
        message.Acknowledge([interceptor.Payload.FromDict(brightness_info)])

    @interceptor.path_handler("FLUSH_IMAGE_BUFFER")
    def _path_flush_buffer(self, message: interceptor.MessageIn) -> None:
        """
        Explicitly flushes the image buffer of all cameras.

        Args:
           payload (list):
                A list containing:
                - 0 (json): {
                    "timeout_ms" (int): timeout per image-get. default: 10 ms
                    "max_images" (int): number of maximum images that are fushed. Default: 4000 images.
                    Avoid endless loop!
                }

        Returns:
            Acknowledge
        Raises:
            CamerasStoppedError
        """
        info = get_info(message)
        timeout_ms = info.get("timeout_ms", 10)
        max_images = info.get("max_images", 4000)

        CAMERA_MANAGER.flush_buffers(timeout_ms, max_images)
        message.Acknowledge()
