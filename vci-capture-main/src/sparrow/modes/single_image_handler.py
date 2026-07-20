from __future__ import annotations

import torch

from sparrow.gibbs_wrapper import GibbsImage, interceptor
from sparrow.mode_shared import CAMERA_MANAGER, CONTROL_MANAGER, PERSISTENT_DATA
from sparrow.modes import common
from sparrow.modes.handler_exceptions import MissingBackgroundError
from sparrow.modes.mode import ModeHandler
from sparrow.modes.mode_util import get_info
from sparrow.utils import logger


class SingleImageHandler(ModeHandler):

    @classmethod
    def mode_name(cls) -> str:
        return "single"

    t_start_kernel = torch.cuda.Event(enable_timing=True)
    t_end_kernel = torch.cuda.Event(enable_timing=True)

    def __init__(self) -> None:
        super().__init__()
        self.frame_counter = -1

    def on_start(self) -> None:
        self.frame_counter = -1

    def get_status(self, *, verbose: bool) -> dict:  # noqa: ARG002
        return {
            "num_cameras": CAMERA_MANAGER.camera_cnt,
            "camera_ids": CAMERA_MANAGER.camera_ids,
            "frame_count": self.frame_counter,
        }

    def take_background_image(self, message: interceptor.MessageIn) -> None:
        # get raw images
        raw_images = CAMERA_MANAGER.capture_images()
        num_invalid = sum([1 if image is None else 0 for image in raw_images])
        if num_invalid > 0:
            missing_cameras = [
                camera_id
                for camera_id, raw_image in zip(CAMERA_MANAGER.camera_ids, raw_images, strict=True)
                if raw_image is None
            ]
            raise MissingBackgroundError(missing_cameras)

        logger.info(f"captured background images: {len(raw_images)}")
        PERSISTENT_DATA.save_background_images(raw_images)
        message.Acknowledge()

    def capture_images(
        self, requested_camera_ids: list[str] | None = None, requested_frame_idx: int = -1  # noqa: ARG002
    ) -> tuple[list[GibbsImage | None], int]:
        self.frame_counter += 1
        raw_images = CAMERA_MANAGER.capture_images(requested_camera_ids)
        return raw_images, self.frame_counter

    @interceptor.path_handler("GET_IMAGES")
    @CONTROL_MANAGER.protected_path()
    def _path_get_images(self, message: interceptor.MessageIn) -> None:
        """
        Captures and returns the next image.

        Args:
            payload (list):
                A list containing:
                - 0 (json): {
                    "camera_ids" (list[str], optional, default=None - all cameras): cameras to capture with
                    "steps" (list[str], optional, default=["debayer_malvar", "superkernel"])
                                                processing steps applied to the captured image.
                    "rgb" (bool, optional, default=True): set to True to request color and mono images
                    "format" (str, optional, default="jpg"): encoding format of the requested images
                    "quality" (int, optional, default="98"): encoding quality of the requested images.
                    "mattes" (bool, optional, default=False): set to True to request mattes
                                                                (forgrond/background segmentation)
                    "matte_format" (str, optional, default="png"): encoding format of the mattes.
                    "threshold" (float, optional, default=0.5): binarization threshold if using binary encoding_format
                }

        Returns:
            payload (list):
                A list containing:
                - 0 (json): The detection results as a JSON object with the following structure: {
                    "frame_idx" (int): Frame index. (Frame index is set to 0 when Starting the mode)
                    "camera_ids" (list[str]): Requested camera_ids,
                    "entry_infos": entry_infos,
                    "mattes" (bool): True if mattes are included in payload
                    "rgb" (bool): True if images (mono or color) included in payload
                    "image_info" (list[dict]): each image and matte in the payload has a correspoding image_info entry
                                                of the following strcuture:{
                                                    "camera_id" (str): id the the capture camera
                                                    "format" (str): encoding_format,
                                                    "image_type" (str): describes image type.
                                                                        Options:["rgb", "matte"]
                                                    "shape" (list[int]): image shape
                                                },
                }
                - 1-4 (bytes, optional): captured color/mono images if "rgb" option is set
                - 1-4 (bytes, optional): matte images if "mattes" option is set
        Raises:
            InvalidProcessingStepError: The combination of processing steps was invalid.
            CamerasStoppedError
            ControlTakenError
        """
        request_params = common.ImageAndMatteRequest.from_message(message)
        image_package = common.process_and_package(
            request_params, self.capture_images, PERSISTENT_DATA.get_background_images, PERSISTENT_DATA.calibration_data
        )
        message.Acknowledge(image_package.to_payload())

    @interceptor.path_handler("SKIP_NEXT_FRAME")
    @CONTROL_MANAGER.protected_path()
    def _path_skip_next_frame(self, message: interceptor.MessageIn) -> None:
        """
        Removes the next frame from buffer without counting it or returning it.

        Returns:
            Acknowledge
        Raises:
            CamerasStoppedError
            ControlTakenError
        """
        CAMERA_MANAGER.capture_images([])
        message.Acknowledge()

    @interceptor.path_handler("GET_BACKGROUND_IMAGE")
    def _path_get_background_image(self, message: interceptor.MessageIn) -> None:
        """
        Returns background images.

        Args:
            payload (list):
                A list containing:
                - 0 (json): {
                    "camera_ids" (list[str], optional, default=None - all cameras): cameras to return backgrounds from
                    "steps" (list[str], optional, default=None): processing steps applied to the background images.
                                                                None: Re-uses last processing used for matting.
                    "format" (str, optional, default="jpg"): encoding format of the images
                    "quality" (int, optional, default="98"): encoding quality of the images.
                }

        Returns:
            payload (list):
                A list containing:
                - 0 (json): The detection results as a JSON object with the following structure: {
                    "frame_idx" (int): -1
                    "camera_ids" (list[str]): ids of capture cameras,
                    "image_info" (list[dict]): each image and matte in the payload has a correspoding image_info entry
                                                of the following strcuture:{
                                                    "camera_id" (str): id the the capture camera
                                                    "format" (str): encoding_format,
                                                    "image_type" (str): "background"
                                                    "shape" (list[int]): image shape
                                                },
                }
                - 1-4 (bytes, optional): background images
        """
        request = common.BaseImageRequest.from_message(message)
        image_packag = common.process_and_package_backgrounds(request, PERSISTENT_DATA.get_background_images)
        message.Acknowledge(image_packag.to_payload())

    @interceptor.path_handler("TAKE_BACKGROUND_IMAGE")
    @CONTROL_MANAGER.protected_path()
    def _path_take_background_image(self, message: interceptor.MessageIn) -> None:
        """
        Capture and save new background images.

        Returns:
            Acknowledge

        Raises:
            CamerasStoppedError
            MissingBackgroundError: Background capture failed.
            ControlTakenError
        """
        self.take_background_image(message)

    @interceptor.path_handler("FLUSH_IMAGE_BUFFER")
    @CONTROL_MANAGER.protected_path()
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
            ControlTakenError
        """
        info = get_info(message)
        timeout_ms = info.get("timeout_ms", 10)
        max_images = info.get("max_images", 40)

        CAMERA_MANAGER.flush_buffers(timeout_ms, max_images)
        message.Acknowledge()
