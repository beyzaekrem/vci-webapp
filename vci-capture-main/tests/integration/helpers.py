import time

from client import Client

from sparrow.calibration_data.calibration_data import CalibrationData
from sparrow.mode_shared.camera_manager import CameraManager


def ensure_calibration(calib_data: CalibrationData, camera_manager: CameraManager) -> None:
    assert set(calib_data.camera_ids) == set(
        camera_manager.camera_ids
    ), "calib-data should have all cameras, even uncalibrated."
    for cam_params in calib_data.camera_parameters.values():
        if cam_params.is_fully_calibrated:
            pass
        else:
            cam_params.fake_values(2200, 4128)
        if cam_params.rotation is None:
            cam_params.rotation = 0


### triggering
def exectue_software_triggers(camera_manager: CameraManager, cnt: int) -> None:
    for _ in range(cnt):
        camera_manager.execute_software_trigger()
        time.sleep(0.1)


def setup_software_trigger_single(client: Client) -> None:
    """setup for single trigger software. Must be called while cameras are stopped."""
    client.send("SET_TRIGGER_SOURCE", {"source": "Software"})
    set_auto_trigger(client, enabled=False, fps=20)


def setup_software_trigger_auto(client: Client, fps: int = 20) -> None:
    """setup for contious software triggers, timed with fps. Must be called while cameras are stopped"""
    client.send("SET_TRIGGER_SOURCE", {"source": "Software"})
    set_auto_trigger(client, enabled=True, fps=fps)


def set_auto_trigger(client: Client, *, enabled: bool, fps: int | None = None) -> None:
    """Starts/stops software auto trigger with fps. Can be called while cameras are running."""
    client.send("SET_SOFTWARE_AUTO_TRIGGER", {"enabled": enabled, "fps": fps})


# recordings
def set_recording_name(client: Client, recording_name: str, fps=None) -> str:
    client.send("SET_RECORDING_NAME", {"recording_name": recording_name, "fps": fps})
    d = client.get_status()
    assert d["recording_name"] == recording_name
    return recording_name
