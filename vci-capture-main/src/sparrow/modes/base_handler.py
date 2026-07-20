from __future__ import annotations

import os

from sparrow.gibbs_wrapper import ImageType, interceptor
from sparrow.image_processing import process_calibration_data
from sparrow.mode_shared import CAMERA_MANAGER, CONTROL_MANAGER, PERSISTENT_DATA, PERSISTENT_RECORD
from sparrow.modes.calibration_handler import CalibrationHandler
from sparrow.modes.handler_exceptions import CamerasRunningError, MissingCalibrationError, ModeUnknownError
from sparrow.modes.livestream_handler import LivestreamHandler
from sparrow.modes.mode import ModeHandler  # noqa: TC001
from sparrow.modes.mode_util import clean_requested_camera_ids, get_info, require_parameter
from sparrow.modes.record_handler import RecordHandle
from sparrow.modes.replay_handler import ReplayHandler
from sparrow.modes.ring_buffer_handler import RingBufferHandler
from sparrow.modes.single_image_handler import SingleImageHandler
from sparrow.utils import current_time_iso, logger

# register modes
MODE_CLASSES: list[ModeHandler] = [
    SingleImageHandler,
    RingBufferHandler,
    RecordHandle,
    ReplayHandler,
    CalibrationHandler,
    LivestreamHandler,
]
MODES: dict[str, ModeHandler] = {mode.mode_name(): mode for mode in MODE_CLASSES}


class BaseHandler(interceptor.MessageHandler):

    def __init__(self, server: interceptor.Server | None = None) -> None:
        interceptor.MessageHandler.__init__(self)
        self.server = server
        self.connections: list[interceptor.Connection] = []  # TODO: Move functionality to interceptor

        CAMERA_MANAGER.setup_cameras()
        PERSISTENT_DATA.load(CAMERA_MANAGER.camera_ids)

        self.activeHandler: ModeHandler = MODES.get("single")()

    def OnConnect(self, connection: interceptor.Connection) -> None:  # noqa: N802
        self.connections.append(connection)
        logger.info(
            f"BaseHandler::OnConnect - connections: {len(self.connections)} {[c.endpoint_address for c in self.connections]}"
        )

    def OnDisconnect(  # noqa: N802
        self, connection: interceptor.Connection, graceful: bool  # noqa: ARG002, FBT001
    ) -> None:
        logger.info("BaseHandler::OnDisconnect")
        self.connections.remove(connection)
        CONTROL_MANAGER.attempt_release_control(connection)
        if len(self.connections) == 0:
            CONTROL_MANAGER.release_control(None, force=True)
            logger.info("BaseHandler::OnDisconnect: Stopping all cameras")
            self.activeHandler.on_stop()
            # TODO if we stop the cameras here, we get a buffer timeout when we start them again
            """
            for camera in CAMERA_MANAGER.cameras:
                if camera.is_running():
                    camera.stop()
                    logger.debug(f"Camera {camera.id()} stopped.")
            """
            logger.info("Connection disconnected")

    def switch_mode(self, next_mode: str) -> None:
        """instantiates the next_mode. Can throw an error. For example MissingBackground or NoCalibration"""
        if next_mode in MODES:
            self.activeHandler.on_stop()
            mode_cls = MODES.get(next_mode)
            if not mode_cls.mode_protected:
                # if the mode is not protected, we give up control after the switch.
                # e.g the livestream mode is not protected. For one we can have mulitple
                # connections asking for livestream and for another
                # the livestream should take lower priority compared to capture or ring_buffer reconstruction.
                CONTROL_MANAGER.release_control(None, force=True)
            self.activeHandler = mode_cls()
        else:
            raise ModeUnknownError(next_mode, list(MODES.keys()))

    def dispatch(self, message: interceptor.MessageIn) -> bool:
        """Overwritten dispatch function to first relay to the active Handler."""
        if self.activeHandler is not None:
            is_done = self.activeHandler.dispatch(message)
            if is_done:
                return True
        return super().dispatch(message)

    def get_status(self, *, verbose: bool) -> None:
        status = self.activeHandler.get_status(verbose=verbose)
        status["mode"] = self.activeHandler.mode_name()
        return status

    @interceptor.path_handler("GET_CAMERA_INFO")
    def _path_get_camera_info(self, message: interceptor.MessageIn) -> None:
        """
        Returns the number of connected cameras, their camera_id and per-camera-info

        Args:
           None

        Returns:
            payload (list):
                A list containing:
                - 0 (json): A JSON object with the following structure: {
                    "num_cameras" (int): Amount of connected cameras.
                    "camera_ids" (list(str)): List of camera_ids.
                    "camera_info" (list(dict)): each connected camera has a correspnding camera_info entry
                                        of the following structure:{
                                            "camera_id" (str): id of the camera,
                                            "manufacturer" (str): manufacturer,
                                            "running" (bool): True if the camera is running,
                                            "image_type" (str): Image type captured by this camera.
                                                ("color", "mono" or "depth")
                                            "exposure" (int): current exposure time in milliseconds,
                                            "gain" (int): current gain
                                        }
                }
        """
        camera_info = {
            "num_cameras": CAMERA_MANAGER.camera_cnt,
            "camera_ids": CAMERA_MANAGER.camera_ids,
            "camera_info": CAMERA_MANAGER.get_camera_info(),
        }
        payload = interceptor.Payload.FromDict(camera_info)
        message.Acknowledge([payload])

    @interceptor.path_handler("STATUS")
    def _path_status(self, message: interceptor.MessageIn) -> None:
        """
        Returns the current status of the server.

        Args:
           None

        Returns:
            payload (list):
                A list containing:
                - 0 (json): A JSON object with the following structure: {
                    "mode" (str): The current operational state (e.g., 'single', 'ring_buffer', 'record').
                    "camera_ids (list(str)): Identifiers for cameras available in current mode.
                    "frame_count" (int): Total frames processed in the current mode since last start.
                }
        """  # TODO doc of activeHandler get status
        info = get_info(message, required=False)
        verbose = info.get("verbose", False)
        status = self.get_status(verbose=verbose)
        payload = interceptor.Payload.FromDict(status)
        message.Acknowledge([payload])

    @interceptor.path_handler("RECORDING_INFO")
    def _path_recording_info(self, message: interceptor.MessageIn) -> None:
        """
        Returns the names of all stored recordings.

        Args:
           None

        Returns:
            payload (list):
                A list containing:
                - 0 (json): A JSON object with the following structure: {
                    "available_recordings" (list(str)): The names of the sored recordings.
                }
        """
        recording_info = {
            "available_recordings": PERSISTENT_RECORD.get_available_recordings(),
        }
        payload = interceptor.Payload.FromDict(recording_info)
        message.Acknowledge([payload])

    @interceptor.path_handler("SET_TRIGGER_SOURCE")
    def _path_set_trigger_source(self, message: interceptor.MessageIn) -> None:
        """
        Sets the trigger source of all cameras. Choices: ["hardware", "software"].
        By default the server initializes cameras in hardware mode.
        In hardware mode, images are triggered by an external trigger source (controlled by vci-control).

        In software mode, images are triggered automatically in "single" and "calibraiton mode".

        Args:
           payload (list):
                A list containing:
                - 0 (json): {
                    "key" (int): Some identifier.
                    "other_key" (str, optional, default='something'): Some string value.
                    "<some_id>" (int): Dynamic ID key.
                }

        Returns:
            payload (list):
                A list containing:
                - 0 (json): A JSON object with the following structure: {...}
                - 1-4 (bytes): images.
        Raises:
            SomeError: something went wrong
        """
        info = get_info(message, required=False)
        source: str = require_parameter(info, "source", str)
        CAMERA_MANAGER.set_trigger_source(source)
        message.Acknowledge()

    @interceptor.path_handler("SET_SOFTWARE_AUTO_TRIGGER")
    def _path_set_software_auto_trigger(self, message: interceptor.MessageIn) -> None:
        """
        Starts and Stops the fps timed software auto trigger.

        Args:
           payload (list):
                A list containing:
                - 0 (json): {
                    "enabled" (bool, optional): True - starts auto trigger. False - stops auto trigger.
                    "fps" (int, optional): Sets the fps for the auto trigger.
                }
        """
        info = get_info(message)
        enabled = info.get("enabled")
        fps = info.get("fps")

        for c in CAMERA_MANAGER.cameras:
            if fps is not None:
                c.set_software_fps(fps)
            if enabled is not None:
                if enabled:
                    c.start_software_auto_trigger()
                else:
                    c.stop_software_auto_trigger()
        message.Acknowledge()

    @interceptor.path_handler("SOFTWARE_TRIGGER_SINGLE")
    def _path_software_trigger_single(self, message: interceptor.MessageIn) -> None:
        """
        Execute a single software trigger.
        """
        for c in CAMERA_MANAGER.cameras:
            c.perform_software_trigger()
        message.Acknowledge()

    @interceptor.path_handler("SET_DEPTH_MODE")
    @CONTROL_MANAGER.protected_path()
    def _path_set_depth_mode(self, message: interceptor.MessageIn) -> None:
        """
        Select image capture mode for depth cameras (orbbec).
        Can either capture depth images, color images or mono images.

        Args:
           payload (list):
                A list containing:
                - 0 (json): {
                    "depth_mode" (str): Select the image capture mode. Options: ["depth", "color", "mono"].
                }

        Returns:
            Acknowledge
            ControlTakenError
        """
        info = get_info(message, required=True)
        depth_mode = require_parameter(info, "depth_mode", str)
        CAMERA_MANAGER.set_depth_mode(depth_mode)
        message.Acknowledge()

    @interceptor.path_handler("SET_PARAMETERS")
    @CONTROL_MANAGER.protected_path()
    def _path_set_parameters(self, message: interceptor.MessageIn) -> None:
        """
        Set camera parameters like software_trigger, exposure, gain, etc...
        You may only set parameters when cameras are not running.

        Args:
           payload (list):
                A list containing:
                - 0 (json): {
                    "camera_type" (str, optional, default="all"): Select which cameras to apply the parameters to.
                                                                        Options: ["color", "mono", "all"]
                    "int:trigger_source" (int, optional): 1 use hardware trigger. 3 use software trigger
                    "int:exposure" (int, optional): sets expsoure time in miroseconds. (1 ms = 1000 microseconds)
                    "int:gain" (int, optional): sets gain.
                    "int:<parameter_name>" (int, optional): set another int parameter that is supported by ximea.
                }

        Returns:
            Acknowledge

        Raises:
            ControlTakenError
        """
        parameters = get_info(message, required=True)

        camera_type: str = parameters.pop("camera_type", None)
        if camera_type is not None:
            camera_type: ImageType = getattr(ImageType, camera_type.capitalize(), None)
            if camera_type is None:
                msg = f"Invalid camera_type: {camera_type}"
                raise interceptor.WrongPayloadError(msg)

        CAMERA_MANAGER.set_parameters_dict(parameters, camera_type=camera_type)
        message.Acknowledge()

    @interceptor.path_handler("SET_CALIBRATION_FILE")
    @CONTROL_MANAGER.protected_path()
    def _path_set_calibration_file(self, message: interceptor.MessageIn) -> None:
        """
        Set the raw calibration json. Deletes previous calibration data.

        Args:
           payload (list):
                A list containing:
                - 0 (json): calibration file

        Returns:
            Acknowledge

        Raises:
            MalformedCalibrationError: The calibration file has an incorrect format.
            ControlTakenError
        """
        calibration_data = get_info(message, required=True)
        PERSISTENT_DATA.save_calibration_json(calibration_data)
        message.Acknowledge()

    @interceptor.path_handler("GET_CALIBRATION_FILE")
    def _path_get_calibration_file(self, message: interceptor.MessageIn) -> None:
        """
        Returns the calibration dict processed with the given processing steps.

        The "cameras" section of the return data contains the calib data updated to reflect the processing applied.
        Therefore "cameras" matches images processed with the same steps.
        For example, if the procesing calls for a rotation (rot90), the intrinsics, resolution and view-matrix are
        updated to reflect this change.
        The section "processing_applied" documents the steps performed during processing along with the parameters used
        and the changes caused to the calibration data.
        The section "raw_calibration" is the original calibration data before processing.

        Returns:
            payload (list):
                A list containing:
                - 0 (json): calibration file

        Raises:
            MissingCalibrationError: No calibration exists.
        """
        info = get_info(message)
        processing_steps = require_parameter(info, "steps", dict)
        requested_camera_ids: list[int] = clean_requested_camera_ids(info.get("camera_ids"), CAMERA_MANAGER.camera_ids)
        calibration_dict: dict = process_calibration_data(
            requested_camera_ids, PERSISTENT_DATA.calibration_data, processing_steps
        )
        calibration_dict["meta"]["name"] = "live"
        calibration_dict["meta"]["capture"] = {
            "timestamp": current_time_iso(),
            "number_cameras": PERSISTENT_DATA.calibration_data.get_number_cameras_by_type(),
        }
        message.Acknowledge([interceptor.Payload.FromDict(calibration_dict)])

    @interceptor.path_handler("GET_RAW_CALIBRATION")
    def _path_get_raw_calibration_file(self, message: interceptor.MessageIn) -> None:
        """
        Returns the raw calibration json.


        Returns:
            payload (list):
                A list containing:
                - 0 (json): calibration file

        Raises:
            MissingCalibrationError: No calibration exists.
        """
        calib_json = PERSISTENT_DATA.calibration_data.calib_json
        message.Acknowledge([interceptor.Payload.FromDict(calib_json)])

    @interceptor.path_handler("SET_CAMERA_ROTATIONS")
    @CONTROL_MANAGER.protected_path()
    def _path_set_camera_rotations(self, message: interceptor.MessageIn) -> None:
        """
        Set camera rotations. Deletes previous rotations.

        Args:
           payload (list):
                A list containing:
                - 0 (json): {
                    "<camera_id>" (str): 90° rotation of the camera id. 1 rotation to the left. -1 rotate to the right.
                                        0 no rotation
                    "<camera_id2>" (str): the same
                }

        Returns:
            Acknowledge

        Raises:
            ControlTakenError
        """
        rotation_data = get_info(message, required=True)
        PERSISTENT_DATA.save_camera_rotations(rotation_data)
        message.Acknowledge()

    @interceptor.path_handler("GET_CAMERA_ROTATIONS")
    def _path_get_camera_rotations(self, message: interceptor.MessageIn) -> None:
        """
        Returns the camera rotation dictionary.

        Returns:
            payload (list):
                A list containing:
                - 0 (json): A JSON object with the following structure: {
                    "<camera_id>" (str): 90° rotation of the camera id. 1 rotation to the left. -1 rotate to the right.
                                        0 no rotation
                    "<camera_id2>" (str): the same
                }

        Returns:
            Acknowledge

        Raises:
            MissingCalibrationError: No rotation dictionary exits.
        """
        rotation_data = PERSISTENT_DATA.camera_rotations
        if rotation_data is None:
            raise MissingCalibrationError
        message.Acknowledge([interceptor.Payload.FromDict(rotation_data)])

    @interceptor.path_handler("START")
    @CONTROL_MANAGER.protected_path()
    def _path_start(self, message: interceptor.MessageIn) -> None:
        """
        Start the cameras and the current server mode.
        Cameras need to be started to capture images.
        The replay buffer does not require you to start the cameras.

        You can not set camera parameters while the cameras are running.

        Returns:
            Acknowledge

        Raises:
            MissingBackgroundError
            MissingCalibrationError
            ControlTakenError
        """
        if CAMERA_MANAGER.force_software_trigger:
            CAMERA_MANAGER.set_trigger_source("Software")

        CAMERA_MANAGER.start_cameras()
        logger.info("cameras are started\n")
        self.activeHandler.on_start()
        message.Acknowledge()

    @interceptor.path_handler("STOP")
    @CONTROL_MANAGER.protected_path()
    def _path_stop(self, message: interceptor.MessageIn) -> None:
        """
        Stops cameras and the current server mode.
        You can set camera parameters while the cameras are stopped.

        Returns:
            Acknowledge

        Raises:
            ControlTakenError
        """
        self.activeHandler.on_stop()
        logger.info("stopping cameras ...")
        CAMERA_MANAGER.stop_cameras()
        message.Acknowledge()

    @interceptor.path_handler("HARD_RESET")
    def _path_hard_reset(self, message: interceptor.MessageIn) -> None:
        """
        Resets the server. Recompiles the code, applying any changes. Re-opens the cameras on startup.

        Returns:
            Acknowledge

        """
        # Hard reset should always result in the programming shutting down
        try:
            logger.info("Hard reset!")
            CAMERA_MANAGER.stop_cameras()  # I've had some cases where the camera is in a weird state that causes errors
            message.Acknowledge()

            if self.server:
                logger.info("Close connections gracefully")
                self.server.stop()
            logger.info("\nSparrow terminating due to HARD_RESET\n")
        except Exception as e:  # noqa: BLE001
            logger.error(e)
        logger.info("Exiting")
        os._exit(0)

    @interceptor.path_handler("SET_IGNORE_CAMERAS")
    def _path_set_ignore_cameras(self, message: interceptor.MessageIn) -> None:
        """
        Set which cameras should be ignored on server startup. Call "CAMERA_SETUP" for changes to take effect.

        Args:
           payload (list):
                A list containing:
                - 0 (json): {
                    "color_only" (bool): True - opens only color cameras. False - opens all cameras (color and mono)
                    "camera_list" (list[str]): list of camera ids to be ignored. Deletes previous camera_list.
                }

        Returns:
            payload (list):
                A list containing:
                - 0 (json): A JSON object with the following structure: {...}
                - 1-4 (bytes): Binary JPG images.
        """
        info = get_info(message, required=True)
        color_only = require_parameter(info, "color_only")
        camera_list = info.get(
            "camera_list", []
        )  # pass None to remove all cameras from ignore list. Pass [] for no modification
        CAMERA_MANAGER.set_ignore_cameras(only_open_color_cameras=color_only, camera_list=camera_list)
        message.Acknowledge()

    @interceptor.path_handler("CAMERA_SETUP")
    @CONTROL_MANAGER.protected_path()
    def _path_camera_setup(self, message: interceptor.MessageIn) -> None:
        """
        Closes running/open cameras and runs camera setup again.

        Raises:
            CamerasRunningError
        """

        if CAMERA_MANAGER.cameras_running:
            action = "camera setup"
            raise CamerasRunningError(action)
        CAMERA_MANAGER.close_cameras()
        CAMERA_MANAGER.setup_cameras()
        PERSISTENT_DATA.load(CAMERA_MANAGER.camera_ids)
        message.Acknowledge()

    @interceptor.path_handler("SWITCH_MODE")
    def _path_switch_mode(self, message: interceptor.MessageIn) -> None:
        """
        Switches the Server Mode. Stops last running Mode and initializes the new one.
        (Re-initializes if you already in the mode)

        modes:
        single: capture single frames. Capture background image. You can request any image format and processing steps.
        ring_buffer: real-time reconstruction. Saves images continously into a buffer.
                    You can request any frame from the buffer.
        record: save raw images to the servers hard drive
        replay: replay images from the servers hard drive. You can request any image format and procesing steps.
        calibration: performs tasks for camera calibration (e.g.: charuco board detection)

        Args:
           payload (list):
                A list containing:
                - 0 (json): {
                    "mode" (str): The mode name
                }

        Returns:
            Acknowledge

        Raises:
            MissingCalibrationError: When you switch to ring_buffer and cameras are not fully calibrated.
            MissingBackgroundError: When you switch to ring_buffer and cameras are missing a background
            ControlTakenError
        """
        info = get_info(message, required=True)
        next_mode = require_parameter(info, "mode")
        self.switch_mode(next_mode)
        message.Acknowledge()

    @interceptor.path_handler("TAKE_CONTROL")
    @CONTROL_MANAGER.protected_path()
    def _path_take_control(self, message: interceptor.MessageIn) -> None:
        """
        Take active control of the server.
        If another connection has control, ControlTakenError is raised.
        If force=True is passed, you forcefully release their control and assume it yourself.

        Args:
           payload (list):
                A list containing:
                - 0 (json): {
                    "force" (bool): False. If another connection had control, they loose it.
                }

        Raises:
            ControlTakenError
        """
        info = get_info(message)
        force = info.get("force", False)

        CONTROL_MANAGER.take_control(message.connection(), force=force)
        message.Acknowledge()

    @interceptor.path_handler("RELEASE_CONTROL")
    def _path_control_release(self, message: interceptor.MessageIn) -> None:
        """
        Release active control of the server, if you had it.
        If another connection has control, ControlerTakenError is raised.
        If force=True is passed you forcefully release their control.

        Args:
           payload (list):
                A list containing:
                - 0 (json): {
                    "force" (bool): False. If another connection had control, they loose it.
                }

        Raises:
            ControlTakenError
        """
        info = get_info(message)
        force = info.get("force", False)

        CONTROL_MANAGER.release_control(message.connection(), force=force)
        message.Acknowledge()
