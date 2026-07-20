import sparrow.gibbs_wrapper as gibbs
from sparrow.gibbs_wrapper import interceptor
from sparrow.mode_shared import CAMERA_MANAGER, CONTROL_MANAGER, PERSISTENT_RECORD
from sparrow.modes.handler_exceptions import (
    CamerasRunningError,
    NoValidRecordingError,
)
from sparrow.modes.mode import ModeHandler
from sparrow.modes.mode_util import get_info, require_parameter
from sparrow.utils import logger


class RecordHandle(ModeHandler):
    # record sequence to storage

    @classmethod
    def mode_name(cls) -> str:
        return "record"

    def __init__(self) -> None:
        super().__init__()
        logger.info("Initialize Record Handler")
        self.recording_name: str = "Not selected"
        self.recorder: gibbs.tasks.RecordCapture = None

    def set_recording_name(self, name: str, fps: int | None = None) -> None:
        self.recording_name = name
        PERSISTENT_RECORD.delete_recording(self.recording_name)
        PERSISTENT_RECORD.save_current_data_for_recording(CAMERA_MANAGER.camera_ids, self.recording_name)

        logger.info(f"Set up CacheWriter for {self.recording_name} Cameras: {CAMERA_MANAGER.camera_ids}")
        cache_location = str(PERSISTENT_RECORD.cache_location)
        dump_locations = [str(loc) for loc in PERSISTENT_RECORD.dump_locations]
        logger.info(f"cache_location {cache_location}")
        logger.debug(f"dump_locations {dump_locations}")

        cache_writer = gibbs.io.CacheWriter(cache_location, dump_locations, CAMERA_MANAGER.camera_ids)
        cache_writer.set_fps(fps)
        self.recorder = gibbs.tasks.RecordCapture(CAMERA_MANAGER.cameras, cache_writer)

    def on_start(self) -> None:
        if self.recorder is None:
            raise NoValidRecordingError(self.recording_name)
        self.recorder.Run()

    def on_stop(self) -> None:
        if self.recorder is not None:
            logger.debug("Stopping Recording...")
            self.recorder.Stop()
            logger.info("Stopped Recording")

    def get_status(self, *, verbose: bool) -> dict:
        if self.recorder is not None:
            status = {
                "num_cameras": CAMERA_MANAGER.camera_cnt,
                "camera_ids": CAMERA_MANAGER.camera_ids,
                "frame_count": self.recorder.SquenceLength(),
                "recording": self.recorder.isRunning(),
                "recording_name": self.recording_name,
            }
        else:
            status = {
                "num_cameras": CAMERA_MANAGER.camera_cnt,
                "camera_ids": CAMERA_MANAGER.camera_ids,
                "frame_count": -1,
                "recording": False,
                "recording_name": self.recording_name,
            }
        if verbose:
            verbose_extras = {
                "available_recordings": PERSISTENT_RECORD.get_available_recordings(),
            }
            status.update(verbose_extras)
        return status

    @interceptor.path_handler("SET_RECORDING_NAME")
    @CONTROL_MANAGER.protected_path()
    def _path_set_recording_name(self, message: gibbs.interceptor.MessageIn) -> None:
        """
        Creates a recording of the given name.

        Call START to start the recorder and the cameras.
        All images triggered next, will be saved into the recording.
        Call STOP to end the recording.

        The recorded names are accesible in replay mode via the given name.
        The current background images and current calibration data are saved under the recording name.

        If a previous recording of the same name exists, it is overwritten.
        Recordings can be deleted with the replay handlers DELETE_RECORDING.

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
        val = require_parameter(info, "recording_name")
        fps = info.get("fps", None)
        self.set_recording_name(val, fps)

        message.Acknowledge()

    @interceptor.path_handler("SET_SKIP_FRAMES")
    @CONTROL_MANAGER.protected_path()
    def _path_set_skip_frames(self, message: gibbs.interceptor.MessageIn) -> None:
        """
        Sets skip frame for the recorder. Skips n frames and saves frame n+1.
        This can for example be used to skip each other frame to allow the IR projectos to heat up before each frame.

        Args:
            payload (list):
                A list containing:
                - 0 (json): {
                    \"skip\" (int): amount of frames to be skipped
                }

        Returns:
            Acknowledge
        Raises:
            CamerasRunningError: Skip frames cannot be set while the cameras/recorder is running
            NoValidRecordingError: No recording name set.
            ControlTakenError
        """

        if self.recorder is not None and self.recorder.isRunning():
            msg = "set skip frames"
            raise CamerasRunningError(msg)

        info = get_info(message)
        new_val = require_parameter(info, "skip")

        logger.info(f"Setting skip frames {new_val}")
        if self.recorder is not None:
            self.recorder.SetSkipFrames(new_val)
            message.Acknowledge()
        else:
            raise NoValidRecordingError(self.recording_name)

    @interceptor.path_handler("SKIP_NEXT_FRAME")
    @CONTROL_MANAGER.protected_path()
    def _path_skip_next_frame(self, message: interceptor.MessageIn) -> None:
        """
        Recorder ignores the next frame that is tiggered.
        This can for example be used to skip the first frame of a continous recording to allow
        IR projectors to heat up by triggering once.

        Returns:
            Acknowledge
        Raises:
            NoValidRecordingError: No recording name set.
            ControlTakenError
        """

        if self.recorder is not None:
            self.recorder.SkipNextFrame()
            message.Acknowledge()
        else:
            raise NoValidRecordingError(self.recording_name)
