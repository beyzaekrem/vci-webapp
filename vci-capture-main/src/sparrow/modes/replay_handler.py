from __future__ import annotations

import re
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path
from threading import Event, Lock, Thread

import torch

import sparrow.gibbs_wrapper as gibbs
from sparrow.gibbs_wrapper import interceptor
from sparrow.image_processing.codecs import encode_images
from sparrow.image_processing.process_calibration_data import process_calibration_data
from sparrow.image_processing.process_images import process_images
from sparrow.image_processing.processing_steps import StepDefaults
from sparrow.mode_shared import CAMERA_MANAGER, CONTROL_MANAGER, PERSISTENT_RECORD
from sparrow.modes import common
from sparrow.modes.common import ImagePackage
from sparrow.modes.handler_exceptions import FrameIndexOutOfBoundsError, MissingBackgroundError, NoValidRecordingError
from sparrow.modes.mode import ModeHandler
from sparrow.modes.mode_util import get_info, require_parameter
from sparrow.utils import logger

from .mode_util import clean_requested_camera_ids


class ProcessingCache:
    """The ProcessingCache is used to interleave image processing and networking operations.

    First you have to call prepare to specify which frames to process and which function to use.
    The finished ImagePackages are placed into a size-limited cache.

    Images can be accessed from the cache with get. This will return an ImagePackage if possible and otherwise None.
    If you get None back, you can for example process the image yourself ad hoc.

    Calling get drains the cache, making space for the next image to be processed.
    The cache is inteded to be drained in the same order as the batch_reqeust queued up frames.
    """

    def __init__(self) -> None:
        self.cache_depth = 10
        self.batch_request: common.BatchImageRequest | None = None  # shared request parameters

        self._ready: dict[int, ImagePackage] = {}
        self._queued: deque[int] = deque()
        self._in_flight: int | None = None

        self._cancel_event = Event()
        self._worker: Thread | None = None
        self._lock = Lock()

        self._avg_processing_time: float = 0.0
        self._sample_count: int = 0

    @property
    def frame_indeces_in_cache(self) -> list[int]:
        return list(self._ready.keys())

    def prepare(self, batch_request: common.BatchImageRequest, process_fn: Callable) -> None:
        self.cancel()
        self._avg_processing_time = 0.0
        self._sample_count = 0

        logger.info(
            f"processing cache prepare {len(batch_request.frame_idx)} frames [{min(batch_request.frame_idx)}, {max(batch_request.frame_idx)}]"
        )
        self._cancel_event.clear()
        with self._lock:
            self.batch_request = batch_request
            self._queued = deque(batch_request.frame_idx)
            self._ready.clear()

        self._worker = Thread(target=self._run, args=(process_fn,), daemon=True)
        self._worker.start()

    def cancel(self) -> None:
        self._cancel_event.set()
        if self._worker and self._worker.is_alive():
            self._worker.join()
        with self._lock:
            self._queued.clear()
            self._ready.clear()
            self._in_flight = None

    def get(self, request: common.ImageAndMatteRequest, *, allow_wait: bool = True) -> ImagePackage | None:
        """Returns package if ready, one if queued/in-flight (caller should wait or fallback)"""
        logger.info(f"processing cache get {request.frame_idx}.... ")
        if self.batch_request and not self._params_match(request):
            logger.info("processing cache does not contain this request parameters")
            return None
        req_index = request.frame_idx

        with self._lock:
            # if we have the reqeusted image in cache we return it.
            if req_index in self._ready:
                logger.info(f"processing cache return image {req_index} immediately")
                return self._ready.pop(req_index)

        if not allow_wait:
            return None
        # if the iamge will be procssed soon, we wait for it.

        # The cache is full, so we cant savely wait, without risking a dead-lock.
        frames_ahead = self._frames_ahead(frame_idx=req_index)
        if frames_ahead is None:
            logger.info(f"processing cache requested iamge {req_index} is not queued")
            return None

        space_available = self.cache_depth - len(self._ready)
        if frames_ahead >= space_available:
            logger.info(f"processing cache No space left in cache. ad-hoc processing {req_index}.")
            return None

        estimated = self._estimated_wait(req_index)

        if estimated > (self._avg_processing_time * 2):
            logger.info(f"processing cache image {req_index} would take to long. return None")
            return None  # to far away, we do not wait.

        while not self._cancel_event.is_set():
            with self._lock:
                if req_index in self._ready:
                    logger.info(f"processing cache return image {req_index} after waiting")
                    return self._ready.pop(req_index)
                if req_index not in self._queued and req_index != self._in_flight:
                    logger.info(f"processing cache requested iamge {req_index} is not queued")
                    return None
            time.sleep(0.05)
        return None

    def _params_match(self, request: common.ImageAndMatteRequest) -> bool:
        if self.batch_request is None:
            return False
        return request.model_dump(exclude={"frame_idx"}) == self.batch_request.model_dump(exclude={"frame_idx"})

    def _estimated_wait(self, frame_idx: int) -> float | None:
        f = self._frames_ahead(frame_idx)
        if f is None:
            return None
        return f * self._avg_processing_time

    def _frames_ahead(self, frame_idx: int) -> int | None:
        with self._lock:
            if frame_idx == self._in_flight:
                return 1
            if frame_idx in self._queued:
                position = self._queued.index(frame_idx)
                return position + (1 if self._in_flight else 0)
        return None

    def _update_avg(self, elapsed: float) -> None:
        self._sample_count += 1
        self._avg_processing_time += (elapsed - self._avg_processing_time) / self._sample_count

    def _run(self, process_fn: Callable) -> None:
        while True:
            # we process and cache up to 10 frames. Then wait until the user drains the cache via GET_IMAGES
            while len(self._ready) >= self.cache_depth:
                if self._cancel_event.is_set():
                    return
                time.sleep(0.1)

            if self._cancel_event.is_set():
                break

            # retrive the next frame_index to process
            with self._lock:
                if not self._queued:
                    break
                frame_idx = self._queued.popleft()
                self._in_flight = frame_idx

            t0 = time.monotonic()
            request = self.batch_request.to_single_request(frame_idx=frame_idx)
            package = process_fn(request)
            elapsed = time.monotonic() - t0

            self._update_avg(elapsed)

            with self._lock:
                self._ready[frame_idx] = package
                self._in_flight = None


class ReplayHandler(ModeHandler):

    @classmethod
    def mode_name(cls) -> str:
        return "replay"

    t_start_kernel = torch.cuda.Event(enable_timing=True)
    t_end_kernel = torch.cuda.Event(enable_timing=True)

    def __init__(self) -> None:
        super().__init__()
        logger.info("Initialize ReplayHandler")

        self.recording_name = "Not selected"

        # read from saved recording
        self.recording_camera_ids = None
        self.cache_reader = None
        self._processing_cache = ProcessingCache()

    def on_stop(self) -> None:
        self._processing_cache.cancel()

    def set_recording_name(self, name: str) -> None:
        self.recording_name = name
        self.create_cache_reader()
        self._processing_cache.cancel()

    def create_cache_reader(self) -> None:
        cache_path: Path = PERSISTENT_RECORD.get_cache_location(self.recording_name)
        logger.info(f"Creating Cache Reader for {self.recording_name}, cache location: {cache_path}")
        if not cache_path.exists():
            logger.error(f"ReplayHandler: Unable to load sequence. {cache_path} does not exist")
            tried_to_load = self.recording_name
            self.recording_name = "Not selected"
            self.cache_reader = None
            raise NoValidRecordingError(tried_to_load)
        self.cache_reader = gibbs.io.CacheReader(
            str(cache_path),
        )
        self.recording_camera_ids = self.cache_reader.camera_ids
        if self.recording_camera_ids is None:
            logger.warning(
                "Recording does not contain camera_ids information. Find capture cameras from saved backgrounds ..."
            )

            directory = Path("/media/ssd0")

            pattern = re.compile(rf"{self.recording_name}_background_(.*)\.pth")

            files = [
                (file.stat().st_mtime, file, pattern.fullmatch(file.name).group(1))
                for file in directory.glob(f"{self.recording_name}_background_*.pth")
                if pattern.fullmatch(file.name)
            ]
            files.sort()
            logger.warning(files)
            matches = [wildcard for _, _, wildcard in files]
            matches = [match for match in matches if "background" not in match]
            logger.warning(
                f"According to saved (processed) backgrounds. {self.recording_name} was captured with {matches}"
            )
            self.recording_camera_ids = matches
        else:
            logger.info(f"Cache was recorded with cameras: {self.recording_camera_ids}")
        # load saved calibration data for the selected recording_name
        # load raw background images

        PERSISTENT_RECORD.load(self.recording_camera_ids, self.recording_name)

        logger.info(f"Sequence length {self.cache_reader.frame_count}")

    def process_and_package(self, request: common.ImageAndMatteRequest) -> common.ImagePackage:
        return common.process_and_package(
            request, self.retrieve_images, PERSISTENT_RECORD.get_background_images, PERSISTENT_RECORD.calib_data
        )

    def retrieve_images(
        self, requested_camera_ids: list[str] | None = None, requested_frame: int = 0
    ) -> tuple[list[gibbs.GibbsImage], int]:
        requested_camera_ids = clean_requested_camera_ids(requested_camera_ids, self.recording_camera_ids)
        logger.info(f"replay_handle retrive_images {requested_camera_ids} {requested_frame}")

        if requested_frame < 0 or requested_frame >= self.cache_reader.frame_count:
            raise FrameIndexOutOfBoundsError(requested_frame, f"[0, {self.cache_reader.frame_count}")

        # load frames of the requested camera_ids

        frame_count = [
            (camera_idx, requested_frame)
            for camera_idx, cam_id in enumerate(self.recording_camera_ids)
            if cam_id in requested_camera_ids
        ]
        logger.info(
            f"replay_handler loading frame {requested_frame} for {requested_camera_ids} from cache at {frame_count}"
        )
        raw_images: list[gibbs.GibbsImage] = []
        for camera_idx, cam_id in enumerate(self.recording_camera_ids):
            if cam_id in requested_camera_ids:
                image = self.cache_reader.load_frame(camera_idx, requested_frame)
                if image.camera_id == "undefined":
                    msg = f"image.camera_id should not be undefined {image}"
                    raise ValueError(msg)
                raw_images.append(image)
        logger.info("Frame loaded")
        return raw_images, requested_frame

    def get_status(self, *, verbose: bool) -> dict:
        status = {
            "num_cameras": (
                CAMERA_MANAGER.camera_cnt if self.recording_camera_ids is None else len(self.recording_camera_ids)
            ),
            "camera_ids": CAMERA_MANAGER.camera_ids if self.recording_camera_ids is None else self.recording_camera_ids,
            "frame_count": -1 if self.cache_reader is None else self.cache_reader.frame_count,
            "recording_name": self.recording_name,
            "capture_timestamp": PERSISTENT_RECORD.get_capture_timestamp(),
            "calibration_timestamp": PERSISTENT_RECORD.calib_data.get_calibration_timestamp(),
            "fps": None if self.cache_reader is None else self.cache_reader.fps,
        }
        if verbose:
            verbose_extras = {
                "available_recordings": PERSISTENT_RECORD.get_available_recordings(),
                "paths": [str(p) for p in PERSISTENT_RECORD.get_all_file_names()],
            }
            status.update(verbose_extras)
        return status

    @interceptor.path_handler("SET_RECORDING_NAME")
    @CONTROL_MANAGER.protected_path()
    def _path_set_recording_name(self, message: interceptor.MessageIn) -> None:
        """
        Sets the name of the current recording. Prepares to replay the recording of this name.

        Args:
            payload (list):
                A list containing:
                - 0 (json): {
                    \"recording_name\" (str): name of recording
                }

        Returns:
            Acknowledge

        Raises:
            NoValidRecordingError: The selected recording does not exist.
            ControlTakenError
        """
        info = get_info(message)
        val = require_parameter(info, "recording_name", str)
        self.set_recording_name(val)
        message.Acknowledge()

    @interceptor.path_handler("PREPARE_IMAGES")
    def _path_prepare_images(self, message: interceptor.MessageIn) -> None:
        if self.cache_reader is None:
            raise NoValidRecordingError(self.recording_name)

        batch_request = common.BatchImageRequest.from_message(message)
        self._processing_cache.prepare(batch_request, self.process_and_package)
        message.Acknowledge()

    @interceptor.path_handler("GET_IMAGES")
    def _path_get_images(self, message: interceptor.MessageIn) -> None:
        """
        Returns images from selected recording. Does not require cameras to be started.

        Args:
            payload (list):
                A list containing:
                - 0 (json): {
                    "frame_idx" (int): requested frame_idx
                    "camera_ids" (list[str], optional, default=None - all cameras): cameras to request images from
                    "steps" (list[str], optional, default=["debayer_malvar", "superkernel"])
                                                processing steps applied to the saved image.
                    "rgb" (bool, optional, default=True): set to True to request images (mono or color)
                    "format" (str, optional, default="jpg"): encoding format of the images
                    "quality" (int, optional, default="98"): encoding quality of the images.
                    "mattes" (bool, optional, default=False): set to True to request mattes (segmentation)
                    "matte_format" (str, optional, default="png"): encoding format of the matte.
                    "threshold" (float, optional, default=0.5): binarization threshold if using binary encoding_format
                }

        Returns:
            payload (list):
                A list containing:
                - 0 (json): The detection results as a JSON object with the following structure: {
                    "frame_idx" (int): requested frame_idx,
                    "camera_ids" (list[str]): requested camera_ids,
                    "entry_infos": entry_infos,
                    "mattes" (bool): True if mattes are included in payload
                    "rgb" (bool): True if images (mono or color) are included in payload
                    "image_info" (list[dict]): each image and matte in the payload has a correspoding image_info entry
                                                of the following strcuture:{
                                                    "camera_id" (str): id the the capture camera
                                                    "format" (str): encoding_format,
                                                    "image_type" (str): describes image type. Options: ["rgb", "matte]
                                                    "shape" (list[int]): image shape
                                                },
                }
                - 1-4 (bytes, optional): captured color/mono images if "rgb" option is set
                - 1-4 (bytes, optional): matte images if "mattes" option is set

        Raises:
            FrameIndexOutOfBoundsError: Selected recording does not contain requested frame_idx
            NoValidRecordingError: There is no recording selected
            InvalidProcessingStepError: The combination of processing steps was invalid.
        """
        if self.cache_reader is None:
            raise NoValidRecordingError(self.recording_name)

        request_prams = common.ImageAndMatteRequest.from_message(message)

        # using processing_cache if possible.

        package = self._processing_cache.get(request_prams, allow_wait=True)
        if package is None:
            package = self.process_and_package(request_prams)
        message.Acknowledge(package.to_payload())

    @interceptor.path_handler("GET_CALIBRATION_FILE")
    def _path_get_calibration_file(self, message: interceptor.MessageIn) -> None:
        """
        Returns the calibration json.


        Returns:
            payload (list):
                A list containing:
                - 0 (json): calibration file

        Raises:
            MissingCalibrationError: No calibration exists for the recording
            NoValidRecordingError: There is no recording selected
        """
        if self.cache_reader is None:
            raise NoValidRecordingError(self.recording_name)
        info = get_info(message)
        processing_steps = info.get("steps", None)

        requested_camera_ids: list[int] = clean_requested_camera_ids(info.get("camera_ids"), self.recording_camera_ids)

        calibration_dict = process_calibration_data(
            requested_camera_ids, PERSISTENT_RECORD.calib_data, processing_steps
        )
        calibration_dict["meta"]["name"] = self.recording_name
        calibration_dict["meta"]["capture"] = {
            "timestamp": PERSISTENT_RECORD.get_capture_timestamp(),
            "number_frames": self.cache_reader.frame_count,
            "fps": self.cache_reader.fps,
            "number_cameras": PERSISTENT_RECORD.calib_data.get_number_cameras_by_type(),
        }

        message.Acknowledge([interceptor.Payload.FromDict(calibration_dict)])

    @interceptor.path_handler("GET_BACKGROUND_IMAGE")
    def _path_get_background_image(self, message: interceptor.MessageIn) -> None:
        """
        Returns background images.

        Args:
            payload (list):
                A list containing:
                - 0 (json): {
                    "camera_ids" (list[str], optional, default=None - all cameras): cameras to request backgrounds from
                    "steps" (list[str], optional, default=None): processing steps applied to the background images.
                                                                None: Re-uses last processing used for matting.
                    "format" (str, optional, default="jpg"): Encoding format of the images
                    "quality" (int, optional, default="98"): Encoding quality of the images.
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
        Raises:
            NoValidRecordingError: There is no recording selected
        """
        if self.cache_reader is None:
            raise NoValidRecordingError(self.recording_name)
        request = common.BaseImageRequest.from_message(message)
        image_package = common.process_and_package_backgrounds(request, PERSISTENT_RECORD.get_background_images)
        message.Acknowledge(image_package.to_payload())

    @interceptor.path_handler("GET_MEAN_IMAGE")
    def _path_get_mean_image(self, message: gibbs.interceptor.MessageIn) -> None:
        """
        Calcualtes and returns the mean image over mutliple frames. Does not require cameras to be started.

        Args:
            payload (list):
                A list containing:
                - 0 (json): {
                    "image_cnt": Number of frames to be averaged
                    "camera_ids" (list[str], optional, default=None - all cameras): cameras to request images from
                    "steps" (list[str], optional, default=["debayer_malvar", "superkernel"])
                                                processing steps applied to the saved image.
                    "rgb" (bool, optional, default=True): set to True to request color and mono images
                    "format" (str, optional, default="jpg"): encoding format of the return images
                    "quality" (int, optional, default="98"): encoding quality of the return images.
                }

        Returns:
            payload (list):
                A list containing:
                - 0 (json): The detection results as a JSON object with the following structure: {
                    "frame_idx" (int): image_cnt
                    "camera_ids" (list[str]): requested camera_ids,
                    "entry_infos": entry_infos,
                    "mattes" (bool): False (mattes are not supported)
                    "rgb" (bool): True if images (mono or color) are included in payload
                    "image_info" (list[dict]): each image and matte in the payload has a correspoding image_info entry
                                                of the following strcuture:{
                                                    "camera_id" (str): id the the capture camera
                                                    "format" (str): encoding_format,
                                                    "image_type" (str): "mean"
                                                    "shape" (list[int]): image shape
                                                },
                }
                - 1-4 (bytes, optional): mean images
        Raises:
            NoValidRecordingError: There is no recording selected
            InvalidProcessingStepError: The combination of processing steps was invalid.
        """
        if self.cache_reader is None:
            raise NoValidRecordingError(self.recording_name)

        info = get_info(message)
        processing_steps = info.get("steps", StepDefaults.PROCESSED)
        requested_camera_ids: list[int] = clean_requested_camera_ids(info.get("camera_ids"), self.recording_camera_ids)
        get_rgb = info.get("rgb", True)
        enc_format = info.get("format", "png")
        enc_quality = info.get("quality", 98)

        image_cnt = info.get("image_cnt")
        if image_cnt is None:
            image_cnt = self.cache_reader.frame_count
        elif image_cnt == 0:
            msg = "image_count must be > 0"
            raise ValueError(msg)
        if self.cache_reader.frame_count <= 0:
            msg = "recording has 0 frames. Cannot create mean image"
            raise RuntimeError(msg)

        image_cnt = min(image_cnt, self.cache_reader.frame_count)  # do not exceed how many images are in the capture
        assert image_cnt != 0, "this shouldnt be thrown now."

        images: list[gibbs.GibbsImage] = []
        for camera_id in requested_camera_ids:
            raw_images: list[gibbs.GibbsImage] = [
                self.retrieve_images([camera_id], requested_frame=f)[0][0] for f in range(image_cnt)
            ]
            all_images = process_images(raw_images, PERSISTENT_RECORD.calib_data, processing_steps)

            stacked_tensor = torch.stack([image.pixels for image in all_images])

            first_image = all_images[0]
            img = gibbs.GibbsImage(
                stacked_tensor.mean(dim=0),
                camera_id,
                first_image.image_type,
                first_image.pixel_layout,
            )
            img.data_category = gibbs.DataCategory.Mean
            images.append(img)

            # release memory
            for img in all_images:
                img.release()
            del stacked_tensor

        capture_info = common.ImagePackage(frame_idx=image_cnt, camera_ids=requested_camera_ids)
        if get_rgb:
            logger.info("encode images")
            capture_info.add_images(encode_images(images, enc_format, quality=enc_quality))
        logger.info("send images")
        message.Acknowledge(capture_info.to_payload())

    @interceptor.path_handler("DELETE_RECORDING")
    @CONTROL_MANAGER.protected_path()
    def _path_delete_recording(self, message: interceptor.MessageIn) -> None:
        """
        Deletes recording of the given name. Deletes cache, dumps, calib file and raw backgrounds

        Args:
           payload (list):
                A list containing:
                - 0 (json): {
                    \"recording_name\" (str): name for recording.
                }

        Returns:
            Acknowledge
        Raises:
            ControlTakenError
        """
        info = get_info(message)
        # user has to re-send the recording to help prevent mistakes
        recording_to_delete = require_parameter(info, "recording_name", str)
        PERSISTENT_RECORD.delete_recording(recording_to_delete)
        message.Acknowledge()

    @interceptor.path_handler("RENAME_RECORDING")
    @CONTROL_MANAGER.protected_path()  # if someone else is currently replaying this recording, we *cannot* rename it.
    # having RENAME only in replay-handler protects us from renaming an ongoing recording.
    def _path_rename_recording(self, message: interceptor.MessageIn) -> None:
        """
        Renames a recording with the given old_name to new_name.

        Args:
           payload (list):
                A list containing:
                - 0 (json): {
                    "old_name" (str): old/current name of recording.
                    "new_name" (str): new name for recording.
                }

        Raises:
            ValueError: A recording called <new_name> aready exists.
            FileNotFoundError: There is no recoring called old_name - dump files refered to
                    in the recording cache cannot be found.
        """
        info = get_info(message, required=True)
        old_name = require_parameter(info, "old_name", str)
        new_name = require_parameter(info, "new_name", str)
        PERSISTENT_RECORD.rename_recording(old_name=old_name, new_name=new_name)
        message.Acknowledge()

    @interceptor.path_handler("SET_CALIBRATION_FILE")
    @CONTROL_MANAGER.protected_path()
    def _path_set_calibration_file(self, message: interceptor.MessageIn) -> None:
        """
        Overwrites the calibration file of the currently selected recording.

        Args:
           payload (list):
                A list containing:
                - 0 (json): calibration file

        Returns:
            Acknowledge

        Raises:
            MalformedCalibrationError: The calibration file has an incorrect format.
            NoValidRecordingError: There is no recording selected
            ControlTakenError
        """
        if self.cache_reader is None:
            raise NoValidRecordingError(self.recording_name)
        calibration_data = get_info(message, required=True)
        logger.info(
            f"Overwriting calibration file for {self.recording_name}. "
            "Timestamp: {calibration_data.get('Timestamp', 'no timestamp provided')}"
        )
        PERSISTENT_RECORD.overwrite_calibration_json(calibration_data)
        message.Acknowledge()

    @interceptor.path_handler("DELETE_DEPRECATED_BACKGROUND")
    @CONTROL_MANAGER.protected_path()
    def _path_delete_deprecated_background(self, message: interceptor.MessageIn) -> None:
        """
        For updating old captures ....
        """
        info = get_info(message)
        recording_to_delete = require_parameter(info, "recording_name", str)
        PERSISTENT_RECORD.delete_deprecated_backgrounds(recording_to_delete)
        message.Acknowledge()

    @interceptor.path_handler("FRAME_ZERO_BACKGROUND")
    @CONTROL_MANAGER.protected_path()
    def _path_frame_zero_background(self, message: interceptor.MessageIn) -> None:
        """
        For updating old captures ....
        """
        if self.cache_reader is None:
            raise NoValidRecordingError(self.recording_name)
        path_pattern = str(PERSISTENT_RECORD._image_path)  # noqa: SLF001
        for camera_id in self.recording_camera_ids:
            image_path = path_pattern.replace("<camera_id>", camera_id)
            if not Path(image_path).exists():
                raw_images, _, _ = self.retrieve_images(self.recording_camera_ids, 0)
                num_invalid = sum([1 if image is None else 0 for image in raw_images])
                if num_invalid > 0:
                    missing_cameras = [
                        camera_id
                        for camera_id, raw_image in zip(self.recording_camera_ids, raw_images, strict=True)
                        if raw_image is None
                    ]
                    raise MissingBackgroundError(missing_cameras)
                PERSISTENT_RECORD.overwrite_background_images(self.recording_camera_ids, raw_images)
                message.Acknowledge()
        message.Acknowledge()

    @interceptor.path_handler("SET_CAMERA_IDS_AS_CAPTURE")
    @CONTROL_MANAGER.protected_path()
    def _path_set_camera_ids_as_capture(self, message: interceptor.MessageIn) -> None:
        """
        For updating old captures ....
        """
        info = get_info(message)
        requested_camera_ids: list[int] = info.get("camera_ids", None)
        if requested_camera_ids is None:
            requested_camera_ids = self.recording_camera_ids

        if not PERSISTENT_RECORD.recording_exists(self.recording_name):
            self.cache_reader = None
            raise NoValidRecordingError(self.recording_name)

        camera_ids_on_file = self.cache_reader.camera_ids
        if camera_ids_on_file is None:
            logger.info(f"Overwriting recording camera ids. Setting to {requested_camera_ids}")
            PERSISTENT_RECORD.update_cache(self.recording_name, {"camera_ids": requested_camera_ids})
        message.Acknowledge()

    @interceptor.path_handler("SET_FPS")
    @CONTROL_MANAGER.protected_path()
    def _path_set_fps(self, message: interceptor.MessageIn) -> None:
        """
        Sets the recording meta-data fps to the given value.

        """
        info = get_info(message, required=True)
        new_fps = require_parameter(info, "fps", (int, None))
        recording_name = require_parameter(info, "recording_name", str)

        if not PERSISTENT_RECORD.recording_exists(recording_name):
            self.cache_reader = None
            raise NoValidRecordingError(recording_name)

        logger.info(f"Settings fps of {recording_name} to {new_fps}")
        PERSISTENT_RECORD.update_cache(recording_name, {"fps": new_fps})
        message.Acknowledge()
