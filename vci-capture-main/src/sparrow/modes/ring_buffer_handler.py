import torch

import sparrow.gibbs_wrapper as gibbs
from sparrow.gibbs_wrapper import interceptor
from sparrow.image_processing.processing_steps import StepDefaults, append_step
from sparrow.mode_shared import CAMERA_MANAGER, CONTROL_MANAGER, PERSISTENT_DATA
from sparrow.mode_shared.matting_wrapper import MATTING
from sparrow.modes import common
from sparrow.modes.common import ImagePackage
from sparrow.modes.handler_exceptions import (
    CamerasStoppedError,
    FrameIndexOutOfBoundsError,
    MissingBackgroundError,
    MissingCalibrationError,
)
from sparrow.modes.mode import ModeHandler
from sparrow.modes.mode_util import clean_requested_camera_ids, filter_images, get_info, require_parameter
from sparrow.utils import logger

OVERWRITE_NO_ROTATION = False


class RingBufferHandler(ModeHandler):
    ring_buffer = None

    @classmethod
    def mode_name(cls) -> str:
        return "ring_buffer"

    # continously write images into ring-buffer.

    # listen to messages and return requested frames from ring-buffer
    # also return most recent frame. always write out which frame number we've sent.

    t_start_kernel = torch.cuda.Event(enable_timing=True)
    t_end_kernel = torch.cuda.Event(enable_timing=True)

    def __init__(self) -> None:
        super().__init__()

        logger.info("Initialize Ring Buffer Handler")
        self.selected_cameras = [c.camera_id for c in CAMERA_MANAGER.cameras if c.camera_type == gibbs.ImageType.Color]

        logger.info(f"Ring Buffer only opens Color cameras: {len(self.selected_cameras)} {self.selected_cameras}")
        # attempt to create the ring buffer. This fails if the cameras are not fully calibrated.
        # we dont throw the error here so the server will be in the ring_buffer mode.
        # switching mode should result in you actually entering the mode, even if you can't run it properly.
        # The Errors are thrown across network when the user calls Start as it attemps to build the ring_buffer task.
        try:
            self.create_ring_buffer(self.selected_cameras)
        except (MissingCalibrationError, MissingBackgroundError) as e:
            logger.warning(f"Could not initialize ring buffer task: {e}")

    def create_ring_buffer(self, camera_ids: list[str] | None = None) -> None:
        if camera_ids is None:
            self.selected_cameras = CAMERA_MANAGER.camera_ids
        else:
            self.selected_cameras = camera_ids

        calib_data = PERSISTENT_DATA.calibration_data
        calib_data.check_fully_calibrated(self.selected_cameras)

        rb_calibs: list[list[torch.tensor]] = []
        rotations: list[int] = []
        for cam_id in self.selected_cameras:
            c = calib_data.get(cam_id)
            parameters = [
                c.white_balance_coefficients,
                c.color_correction_matrix,
                c.camera_matrix,
                c.distortion_coefficients,
            ]
            parameters = [
                val if val is not None else torch.tensor([]) for val in parameters
            ]  # replace None values with empty tensor. happens for mono or depth cameras.

            rb_calibs.append(parameters)
            rotations.append(c.rotation)

        if OVERWRITE_NO_ROTATION:
            rotations = [0 for _ in range(self.selected_cameras)]  ## <--------------- disable rotations
            bg_steps = append_step(StepDefaults.RING_BUFFER, {"rotate": False})
        else:
            bg_steps = StepDefaults.RING_BUFFER

        background_images = self.get_ring_buffer_backgrounds(bg_steps)
        if len(background_images) != len(self.selected_cameras):
            msg = f"Expected {len(self.selected_cameras)} backgrounds but found {len(background_images)}"
            raise MissingBackgroundError(msg)

        logger.info(
            f"processed backgrounds passed into ring buffer shapes: {[(bg.camera_id, bg.shape) for bg in background_images]}"
        )

        cameras = [camera for camera in CAMERA_MANAGER.cameras if camera.camera_id in self.selected_cameras]

        self.ring_buffer = gibbs.tasks.RingBuffer(
            cameras,
            rb_calibs,
            rotations,
            MATTING.networks[MATTING.BACKGROUND_MATTING_V2_RGB_FLOAT16].net,
            background_images,
            0.5,
        )
        logger.info("Ring Buffer task initialized")
        return self.ring_buffer

    def get_ring_buffer_backgrounds(self, steps: dict[str : list[dict]]) -> list[gibbs.GibbsImage]:
        """returns the background iamges in a list, sorted like self.selected_cameras so it can be passed to gibbs.tasks.RingBuffer"""
        background_images: dict[str, gibbs.GibbsImage] = PERSISTENT_DATA.backgrounds.get_background_images(
            steps, PERSISTENT_DATA.calibration_data
        )
        return [background_images.get(cam_id) for cam_id in self.selected_cameras]

    def on_start(self) -> None:
        # Raises MissingBackgroundError, MissingCalibrationError
        logger.info("run ringbuffer")

        # stoping non-selected cameras.
        for cam in CAMERA_MANAGER.cameras:
            if cam.camera_id not in self.selected_cameras and cam.is_running():
                cam.stop()
        if self.ring_buffer is None:
            # create_ring_buffer failed when __init__ was called. We try again and throw the Error across Network
            self.create_ring_buffer(self.selected_cameras)
        self.ring_buffer.Run()

    def on_stop(self) -> None:
        logger.info("stop ringbuffer")
        if self.ring_buffer is not None:
            self.ring_buffer.Stop()
            torch.cuda.empty_cache()

    def get_status(self, *, verbose: bool) -> dict:  # noqa: ARG002
        frame_count = None if self.ring_buffer is None else self.ring_buffer.LastFrame()
        return {
            "num_cameras": len(self.selected_cameras),
            "camera_ids": self.selected_cameras,
            "frame_count": frame_count,
        }

    def on_get_images_from_ring_buffer(
        self, message: interceptor.MessageIn, *, rgb_default: bool, mattes_default: bool
    ) -> None:
        if not CAMERA_MANAGER.cameras_running or self.ring_buffer is None:
            msg = "get_images from ring buffer"
            raise CamerasStoppedError(msg)

        info = {}
        if len(message.payload) > 0:
            info = gibbs.interceptor.Payload.ToDict(message.payload[0])
        requested_camera_ids: list[int] = clean_requested_camera_ids(info.get("camera_ids"), self.selected_cameras)

        requested_frame = info.get("frame_idx", 0)
        get_rgb = info.get("rgb", rgb_default)
        get_mattes = info.get("mattes", mattes_default)

        if requested_frame < 0:
            requested_frame = self.ring_buffer.LastFrame()

        capture_info = ImagePackage(camera_ids=requested_camera_ids, frame_idx=requested_frame)

        if get_rgb:
            images = self.ring_buffer.GetImages(requested_frame)  # returns jpg encoded processed image
            if len(images) == 0:
                last = self.ring_buffer.LastFrame()
                valid_range = f"[{max(last-50, 0)}, {last}]"
                raise FrameIndexOutOfBoundsError(requested_frame, valid_range, frame_type="RGB")

            images = filter_images(images, requested_camera_ids)
            capture_info.add_images(images)

        if get_mattes:
            mattes = self.ring_buffer.GetMasks(requested_frame)  # returns jpg encoded processed image
            if len(mattes) == 0:
                last = self.ring_buffer.LastFrame()
                valid_range = f"[{max(last-50, 0)}, {last}]"
                raise FrameIndexOutOfBoundsError(requested_frame, valid_range, frame_type="Matte")

            mattes = filter_images(mattes, requested_camera_ids)

            capture_info.add_images(mattes)

        logger.info(
            f"Sending Images requestedframe {requested_frame}, {requested_camera_ids}. "
            f"Last captured {self.ring_buffer.LastFrame()}. Diff: {self.ring_buffer.LastFrame() - requested_frame}"
        )
        message.Acknowledge(capture_info.to_payload())
        logger.debug(f"Sending Images finished {requested_frame}, {len(requested_camera_ids)} {requested_camera_ids}")

    @interceptor.path_handler("GET_IMAGES")
    def _path_get_images(self, message: gibbs.interceptor.MessageIn) -> None:
        """
        Returns image from the ring_buffer.
        Images are allways processed with ["debayer_subsample", "superkernel"].
        Color/Mono images are encoded as jpg while mattes are encoded in binary.
        You may set the binarization threshold before starting the cameras with path SET_THRESHOLD

        Args:
            payload (list):
                A list containing:
                - 0 (json): {
                    "frame_idx" (int): requested frame. Index must be in range of ring_buffer size.
                    "camera_ids" (list[str], optional, default=None - all cameras): cameras to request images from
                    "rgb" (bool, optional, default=True): Set to True to request color and mono images
                    "mattes" (bool, optional, default=False): Set to True to request mattes
                    (foreground/background segmentation)
                }

        Returns:
            payload (list):
                A list containing:
                - 0 (json): The detection results as a JSON object with the following structure: {
                    "frame_idx" (int): Frame index
                    "camera_ids" (list[str]): ids of capture cameras,
                    "entry_infos": entry_infos,
                    "mattes" (bool): True - mattes included in payload
                    "rgb" (bool): True - images (mono or color) included in payload
                    "image_info" (list[dict]): each image and matte in the payload has a correspoding image_info entry
                                                of the following strcuture:{
                                                    "camera_id" (str): requested camera_id,
                                                    "format" (str): encoding_format,
                                                    "image_type" (str): describes image type. Options: ["rgb", "matte"]
                                                    "shape" (list[int]): image shape
                                                },
                }
                - 1-4 (bytes, optional): captured color/mono images if "rgb" option is set
                - 1-4 (bytes, optional): matte images if "mattes" option is set
        Raises:
            CamerasStoppedError
            FrameIndexOutOfBoundsError: The requested frame_idx is not in range of the ring_buffer
        """
        logger.info("Get_Images")
        self.on_get_images_from_ring_buffer(message, rgb_default=True, mattes_default=False)

    @interceptor.path_handler("GET_MATTES")
    def _path_get_mattes(self, message: gibbs.interceptor.MessageIn) -> None:
        """
        Returns mattes from the ring_buffer.
        Images are allways processed with ["debayer_subsample", "superkernel"].
        Color/Mono images are encoded as jpg while mattes are encoded in binary.
        You may set the binarization threshold before starting the cameras with path SET_THRESHOLD

        Args:
            payload (list):
                A list containing:
                - 0 (json): {
                    "frame_idx" (int): requested frame. Index must be in range of ring_buffer size.
                    "camera_ids" (list[str], optional, default=None - all cameras): cameras to request images from
                    "rgb" (bool, optional, default=False): set to True to request color and mono images
                    "mattes" (bool, optional, default=True): set to True to request mattes
                    (foreground/background segmentation)
                }

        Returns:
            payload (list):
                A list containing:
                - 0 (json): The detection results as a JSON object with the following structure: {
                    "frame_idx" (int): requested frame index
                    "camera_ids" (list[str]): requested camera_ids,
                    "entry_infos": entry_infos,
                    "mattes" (bool): True - mattes included in payload
                    "rgb" (bool): True - images (mono or color) included in payload
                    "image_info" (list[dict]): each image and matte in the payload has a correspoding image_info entry
                                                of the following strcuture:{
                                                    "camera_id" (str): requested camera_id,
                                                    "format" (str): encoding_format,
                                                    "image_type" (str): describes image type. Options: ["rgb", "matte"]
                                                    "shape" (list[int]): image shape
                                                },
                }
                - 1-4 (bytes, optional): captured color/mono images if "rgb" option is set
                - 1-4 (bytes, optional): matte images if "mattes" option is set
        Raises:
            CamerasStoppedError: The cameras are not running.
            FrameIndexOutOfBoundsError: The requested frame_idx is not in range of the ring_buffer
        """
        logger.info("Get_Mattes")
        self.on_get_images_from_ring_buffer(message, rgb_default=False, mattes_default=True)

    @interceptor.path_handler("SET_THRESHOLD")
    @CONTROL_MANAGER.protected_path()
    def _path_set_threshold(self, message: gibbs.interceptor.MessageIn) -> None:
        """
        Sets the binarization threshold for masks in the ring_buffer. (foreground/background segmenation)

        Converts soft masks (range [0, 1]) into binary foreground/background masks.
        Pixels with values >= threshold are set to foreground (1).

        A higher threshold results in a stricter foreground definition,
        effectively pruning semi-transparent or low-confidence edge regions.

        Args:
           payload (list):
                A list containing:
                - 0 (json): {
                    "threshold" (float): threshold value
                }

        Raises:
            ControlTakenError
        """
        info = get_info(message)
        new_val = require_parameter(info, "threshold")

        self.ring_buffer.SetThreshold(new_val)
        message.Acknowledge()

    @interceptor.path_handler("GET_BACKGROUND_IMAGE")
    def _path_get_background_image(self, message: gibbs.interceptor.MessageIn) -> None:
        """
        Returns background images.

        Args:
            payload (list):
                A list containing:
                - 0 (json): {
                    "camera_ids" (list[str], optional, default=None - all cameras): cameras to request backgrounds from
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
                    "camera_ids" (list[str]): requested camera_ids,
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
        package = common.process_and_package_backgrounds(request, self.get_ring_buffer_backgrounds)
        message.Acknowledge(package.to_payload())
