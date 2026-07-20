from __future__ import annotations

import sys
from dataclasses import dataclass

import torch
from natsort import natsorted

import sparrow.gibbs_wrapper as gibbs
from sparrow.gibbs_wrapper import ImageType, interceptor
from sparrow.modes.handler_exceptions import CamerasStoppedError, CaptureTimeoutError
from sparrow.utils import logger, read_json_file, write_json_file

from .persistent_paths import PERSISTENT_PATHS

gibbs.CameraManager.disable_api_logging()


@dataclass()
class ExposureSetting:
    exposure_ms: int
    gain: int


class CameraManager:

    force_software_trigger: bool = False  # testability: disables hardware triggers everywhere.
    camera_type = ImageType

    def __init__(self) -> None:
        self.cameras_by_id: dict[str, gibbs.Camera] = {}
        # default exposure and gain. User may change these with SET_PARAMETER message
        self.exposure_settings = {
            ImageType.Color: ExposureSetting(exposure_ms=10000, gain=0),  # 10 ms exposure
            ImageType.Mono: ExposureSetting(exposure_ms=1000, gain=12),  # 1 ms exposure
            ImageType.Depth: ExposureSetting(exposure_ms=30, gain=0),  # 30 ms exposure
        }

    @property
    def camera_cnt(self) -> int:
        return len(self.cameras)

    @property
    def cameras(self) -> list[gibbs.Camera]:
        return list(self.cameras_by_id.values())

    @property
    def camera_ids(self) -> list[str]:
        return list(self.cameras_by_id.keys())

    # region opening cameras
    def configure_simulation(self, simualted_camera_config_path: str | None) -> None:
        """disables hardware cameras and uses simulated cameras instead. You should run this before setup_cameras"""
        gibbs.CameraManager.configure_simulation(simualted_camera_config_path)

    def close_cameras(self) -> None:
        """Stops and closes all open cameras."""
        logger.info(f"CameraManager: closing {self.camera_cnt} cameras")
        for camera in self.cameras:
            if camera.is_open():
                if camera.is_running():
                    camera.stop()
                camera.close()
                logger.info(f"Closed {camera.camera_id}")
        self.cameras_by_id = {}

    def setup_cameras(self, requested_camera_ids: list[str] | None = None) -> None:
        """Opens and sets default parameters of cameras.
        Automatically reads from persistent/config/camera_ignore.json to determine which cameras to filter for."""
        if self.camera_cnt > 0:
            logger.info("CameraManager: ignoring setup_cameras call. Cameras are already opened.")
            return

        self.cameras_by_id = self.get_camera_ids_without_opening_cameras()
        logger.info(f"Connected cameras: {self.camera_ids}")
        self._filter_cameras(requested_camera_ids)
        self._open_cameras()
        self._set_default_parameters()
        logger.info(f"Open cameras: {self.camera_ids}\n")

    @staticmethod
    def get_camera_ids_without_opening_cameras() -> dict[str, gibbs.Camera]:
        """Quickly retrieve camera ids and cameras without opening them

        Returns:
            tuple[list[str], list[gibbs.Camera]]
        """
        cameras: list[gibbs.Camera] = [
            gibbs.CameraManager.get_camera_by_id(i) for i in range(gibbs.CameraManager.num_cameras())
        ]
        ids_and_cameras = [(camera.camera_id, camera) for camera in cameras]
        ids_and_cameras = natsorted(ids_and_cameras, key=lambda x: x[0])
        return dict(ids_and_cameras)

    def _filter_cameras(self, requested_camera_ids: list[str] | None = None) -> None:
        """filters cameras and camera_ids to remove mono cameras or
        specific camera_ids as described in camera_ignore.json
        """
        self._load_ignore_cameras()

        filtered_cameras: dict[str, gibbs.Camera] = {}

        for camera_id, camera in self.cameras_by_id.items():
            if (
                self.only_open_color_cameras and camera.camera_type != ImageType.Color
            ):  # optionally filter mono/depth cameras
                continue
            if camera_id in self.disable_cameras_on_load:  # optionally filter by camera id
                continue

            if requested_camera_ids is not None and camera_id not in requested_camera_ids:
                continue

            filtered_cameras[camera_id] = camera

        self.cameras_by_id = filtered_cameras

    def _open_cameras(self) -> None:
        """attempt to open cameras. Will exit the program if we cannot open the cameras"""
        for idx, camera in enumerate(self.cameras):
            logger.info(
                f"Opening {camera.camera_id} {camera.camera_type.name} "
                f"{camera.manufacturer} - {idx}/{len(self.cameras)} SN: {camera.info().serialnumber} ... "
            )
            try:
                camera.open()
            except RuntimeError as e:
                logger.error(f"\nError when opening {camera.manufacturer} {camera.info().capture_card_index}: {e}")
                if "XI_RESOURCE_OR_FUNCTION_LOCKED" in str(e):
                    logger.error("Cameras may already be occupied (opened) by another process.")
                logger.error("exit")
                sys.exit(57)

    def _set_default_parameters(self) -> None:
        """Set some default parameters here
        Including:
        - 12 bit
        - transport data
        - Exposure and Gain
        - IR projector trigger
        - Harware Trigger setting
        """
        for idx, camera in enumerate(self.cameras):
            logger.info(f"Setting {camera.camera_id} parameters {idx}/{len(self.cameras)}")
            camera.open()

            camera.set_default_parameters()
            if camera.camera_type in self.exposure_settings:
                setting = self.exposure_settings[camera.camera_type]
                camera.set_exposure(setting.exposure_ms)
                camera.set_gain(setting.gain)

    def _load_ignore_cameras(self) -> None:
        data = read_json_file(PERSISTENT_PATHS.camera_ignore_file_path)
        logger.debug(f"load ignore cameras, data {data} file path: {PERSISTENT_PATHS.camera_ignore_file_path}")
        if data is None:
            self.only_open_color_cameras = False
            self.disable_cameras_on_load = []
            self.force_software_trigger = False
        else:
            self.only_open_color_cameras = data.get("only_open_color_cameras", False)
            self.disable_cameras_on_load = data.get("disable_cameras_on_load", [])
            self.force_software_trigger = data.get("force_software_trigger", False)
        logger.info(f"   only_open_color_cameras {self.only_open_color_cameras}")
        logger.info(f"   disable_cameras_on_load {natsorted(self.disable_cameras_on_load)}")

    def set_ignore_cameras(
        self, *, only_open_color_cameras: bool = False, camera_list: list[str] | None = None
    ) -> None:
        data = read_json_file(PERSISTENT_PATHS.camera_ignore_file_path)
        data["only_open_color_cameras"] = only_open_color_cameras
        data["disable_cameras_on_load"] = camera_list
        write_json_file(PERSISTENT_PATHS.camera_ignore_file_path, data)

    # endregion

    # region trigger control

    def set_software_trigger(self) -> None:
        self.set_trigger_source("Software")

    def set_trigger_source(self, source: str) -> None:
        """Sets the trigger souce. Choice: [Hardware, Software]

        Args:
            source (str): new source

        Raises CamerasRunningError (from C++)
        """
        source = getattr(gibbs.TriggerSource, source.capitalize(), None)
        for camera in self.cameras:
            camera.set_trigger_source(source)

    def get_trigger_source(self) -> str:
        s = [c.trigger_source for c in self.cameras]
        if len(set(s)) != 1:
            msg = f"All cameras should have the same trigger source. But is: {[(c.camera_id, c.trigger_source) for c in self.cameras]}"
            raise RuntimeError(msg)
        return s[0].name

    def execute_software_trigger(self) -> None:
        for camera in self.cameras:
            camera.perform_software_trigger()

    def start_software_auto_trigger(self) -> None:
        for camera in self.cameras:
            camera.start_software_auto_trigger()

    def stop_software_auto_trigger(self) -> None:
        for camera in self.cameras:
            camera.stop_software_auto_trigger()

    # endregion

    # region set parameters
    def set_parameter(self, parameter_name: str, value: int, *, camera_type: None | ImageType) -> None:
        for camera in self.cameras:
            if camera_type is None or camera_type == camera.camera_type:
                if parameter_name == "exposure":
                    camera.set_exposure(value)
                elif parameter_name == "gain":
                    camera.set_gain(value)
                else:
                    camera.set_parameter_int(parameter_name, value)

    def set_parameters_dict(self, parameters: dict, *, camera_type: None | ImageType) -> None:
        for key, value in parameters.items():
            parameter_type, parameter_name = key.split(":", 1)
            if parameter_type == "int":
                logger.info(f"set_parameter_int({parameter_name}, {value})")
                self.set_parameter(parameter_name, value, camera_type=camera_type)
            else:
                msg = f"Unknown parameter type: {parameter_type} in {key}"
                raise interceptor.WrongPayloadError(msg)

    def set_depth_mode(self, depth_mode: str) -> None:
        depth_as_int = {
            "color": 0,
            "mono": 1,
            "depth": 2,
        }  # this is kinda ugly but it doesn't require us to bind orbbec stuff.
        # avoiding orbbec binding so OrbbecSDK isn't needed when system doesn't use Orbbec Cameras.
        logger.info(f"Set depth mode to {depth_mode}")
        self.set_parameter("depth_mode", depth_as_int[depth_mode.lower()], camera_type=ImageType.Depth)

    # endregion

    # region camera state
    def start_cameras(self) -> None:
        for camera in self.cameras:
            if not camera.is_running():
                camera.start()

    def stop_cameras(self) -> None:
        for camera in self.cameras:
            if camera.is_running():
                camera.stop()

    @property
    def cameras_running(self) -> bool:
        return any(camera.is_running() for camera in self.cameras)

    def get_camera_info(self) -> list[dict]:
        return [camera.to_dict() for camera in self.cameras]

    # endregion

    # region image capture

    def capture_images(
        self,
        requested_camera_ids: list[str] | None = None,
        timeout_ms: int = 10 * 1000,
        *,
        execute_software_trigger: bool = True,
    ) -> list[gibbs.GibbsImage]:
        """
        Grabs the latest image from the image buffers.
        Returns a list of images as torch tensor and a list of image_info dicts.

        An image_info has the following shape:
                {
                    "bit_depth": int,
                    "height": int,
                    "width": int,
                    "timestamp_us": int,
                    "frame_number": int,
                    "image_type": str, choices=["mono", "color", "depth"],
                    "optional_data": any, additional info like depth_scale
                }

        Raises:
            CamerasStoppedError, CaptureTimeoutError
        """
        if not self.cameras_running:
            msg = "capture images"
            raise CamerasStoppedError(msg)
        if requested_camera_ids is None:
            requested_camera_ids = self.camera_ids
        logger.info(f"CameraManager capture images for {requested_camera_ids}")

        # capture one image by each connected camera
        # Wait until we capture the first image. capture_next does not trigger an image capture.
        # It simply waits for the camera to provide the next image.
        # The physical trigger box is used to trigger an image capture
        # (telling the camera to physically start exposing etc.)
        # For testing purposes, a software trigger may be used.
        # This does not allow you to synchronize between different capture-servers though.
        if execute_software_trigger:
            self.execute_software_trigger()

        logger.info("gibbs.tasks.capture_all waiting for trigger ...")
        buffer_entries = gibbs.tasks.capture_all(self.cameras, timeout_ms)
        # buffer_entires contain captured images

        raw_images = []
        for buffer_entry, camera_id in zip(buffer_entries, self.camera_ids, strict=True):
            if camera_id not in requested_camera_ids:
                if buffer_entry is not None:
                    buffer_entry.unlock()  # always unlock buffer_enties
                continue
            # we want this buffer but its timed out
            if buffer_entry is None:  # or buffer_entry == 0:
                raise CaptureTimeoutError(camera_id)

            # Move to GPU
            raw_buffer: torch.tensor = gibbs.processing.buffer_entry_to_device_async(
                buffer_entry, torch.device("cuda:0")
            )
            # unpack buffer into a float tensor [0,1], respecting bit-depth and image size.
            image: gibbs.GibbsImage = gibbs.processing.unpack_buffer(raw_buffer, buffer_entry.info())
            assert image.camera_id != "undefined", "Capture gibbsImage is missing camera_id"
            buffer_entry.unlock()
            raw_images.append(image)

        return raw_images

    def flush_buffers(self, timeout_ms: int, max_images: int) -> None:
        """
        Flushes the buffer of all cameras.

        Raises:
            CamerasStoppedError
        """
        if not self.cameras_running:
            msg = "flush buffers"
            raise CamerasStoppedError(msg)

        active_cameras = self.cameras_by_id.copy()
        counter = dict.fromkeys(self.camera_ids, 0)
        for _ in range(max_images):
            if not active_cameras:  # is empty []
                logger.info(f"self flushed images: {counter}")
                break

            buffer_entries = gibbs.tasks.capture_all(list(active_cameras.values()), timeout_ms)

            next_active: dict[str, gibbs.Camera] = {}
            for cam_id, entry in zip(active_cameras, buffer_entries, strict=True):
                if entry is not None:
                    entry.unlock()
                    counter[cam_id] += 1
                    next_active[cam_id] = active_cameras[cam_id]

            active_cameras = next_active
        else:
            logger.info(f"flush buffers failed. Stopped after {max_images}.")


CAMERA_MANAGER = CameraManager()
"""Shared CameraManager instance"""
