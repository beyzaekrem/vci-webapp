from __future__ import annotations

import sparrow.gibbs_wrapper as gibbs


class VciError(Exception):
    pass


class ControlTakenError(VciError):
    """Raised when an action is requested on a server performing a protected task."""

    def __init__(self) -> None:
        super().__init__("Control is currently held by another connection. Try again later.")


class MissingCalibrationError(VciError):
    def __init__(self, camera_ids: list[str] | None, action: str | None = None) -> None:
        m = "Missing Calibration."
        if camera_ids is not None:
            m = f"Missing Calibration for {camera_ids}."
        if action is not None:
            m = m + f" Unable to perform {action}."
        super().__init__(m)


class ProcessingFailedError(VciError):
    pass


class InvalidProcessingStepError(VciError):
    def __init__(self, processing_step: str, context: str = "") -> None:
        super().__init__(f"Processing step {processing_step} cannot be performed. {context}")


class ModeUnknownError(VciError):
    def __init__(self, mode: str, known_modes: str) -> None:
        super().__init__(f"Unknown Mode {mode}. Valid options: {known_modes}")


class MalformedCalibrationError(VciError):
    def __init__(self, error: str) -> None:
        super().__init__(f"Calibration File is malformed. {error}")


class CamerasRunningError(VciError):
    def __init__(self, action: str) -> None:
        super().__init__(f"Action {action} cannot be performed while the Cameras are running.")


class CamerasStoppedError(VciError):
    def __init__(self, action: str) -> None:
        super().__init__(f"Action {action} cannot be performed while the Cameras are stopped.")


class NoValidRecordingError(VciError):
    def __init__(self, recording_name: str) -> None:
        super().__init__(f"Recording {recording_name} cannot be loaded. It does not exist.")


class MissingBackgroundError(VciError):
    def __init__(self, camera_id: str | None = None) -> None:
        m = "Missing Background"
        if camera_id is not None:
            m = f"Missing Background for {camera_id}."
        super().__init__(m)


class FrameIndexOutOfBoundsError(VciError):
    def __init__(self, requested_frame: str, frame_range: str | None = None, frame_type: str | None = None) -> None:
        m = f"Frame {requested_frame} is out of bounds."
        if frame_type is not None:
            m = f"{frame_type} frame {requested_frame} is out of bounds."
        if frame_range is not None:
            m = m + f"Valid range: {frame_range}"
        super().__init__(m)


class MissingFrameError(VciError):
    def __init__(self, camera_id: str) -> None:
        super().__init__(f"Frame is missing for camera {camera_id}.")


class MattingFailedError(VciError):
    def __init__(self, image: gibbs.GibbsImage, bg: gibbs.GibbsImage, network: str, error: str) -> None:
        super().__init__(f"Matting {network} failed for image: {image} and background: {bg}. Error: {error}")


class NotInitializedError(ValueError):
    def __init__(self, thing: str) -> None:
        super().__init__(f"{thing} has not been inizialized.")


class CaptureTimeoutError(VciError):
    def __init__(self, camera_id: str) -> None:
        super().__init__(f"Camera {camera_id} timed out.")
