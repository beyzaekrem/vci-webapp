import pytest

from sparrow.mode_shared.persistent import PersistentData
from sparrow.mode_shared.persistent_paths import PERSISTENT_PATHS
from sparrow.modes import handler_exceptions as h_errors
from sparrow.modes.base_handler import BaseHandler
from sparrow.modes.ring_buffer_handler import RingBufferHandler

###  Test cases for functionality of the basehandler / common across all handlers

### run with : python -m pytest tests/pipeline


# ---- tests -----


def test_init_uncalibrated(base_handler: BaseHandler, fully_uncalibrated: PersistentData) -> None:
    base_handler.switch_mode("ring_buffer")
    status = base_handler.get_status(verbose=False)
    assert (
        status.get("mode") == "ring_buffer"
    ), "mode switch to ring buffer should work even if cameras are not calibrated"


def test_run_uncalibrated(fully_uncalibrated: RingBufferHandler) -> None:
    uncalibrated_ring_buffer = RingBufferHandler()
    with pytest.raises(h_errors.MissingCalibrationError):
        uncalibrated_ring_buffer.create_ring_buffer(camera_ids=["C9999"])
    with pytest.raises(h_errors.MissingCalibrationError):
        uncalibrated_ring_buffer.on_start()


def test_run_calibrated(fully_calibrated: PersistentData) -> None:
    print("config_root", PERSISTENT_PATHS.config_root)
    rh = RingBufferHandler()
    rh.create_ring_buffer(camera_ids=["C9999"])
    rh.on_start()
    rh.on_stop()
