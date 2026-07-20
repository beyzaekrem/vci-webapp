# ruff: noqa: S101, N806, PLR2004, T201, TC002, INP001, RUF100, ARG001
import time
from pathlib import Path

import pytest
from client import Client, Response
from helpers import exectue_software_triggers, set_recording_name, setup_software_trigger_single

from sparrow.mode_shared.persistent_record import PERSISTENT_RECORD


## fixtures
@pytest.fixture(scope="module", autouse=True)
def switch_to_record(client: Client) -> None:
    client.switch_mode("record")


@pytest.fixture(scope="module")
def record_save_path(tmp_path: Path) -> Path:
    return tmp_path / "media"


@pytest.fixture
def recording_name() -> str:
    return "_integration_test"


@pytest.fixture
def with_valid_recording(client: Client, recording_name: str) -> None:
    set_recording_name(client, recording_name=recording_name, fps=10)
    setup_software_trigger_single(client)


@pytest.fixture
def with_start(client: Client) -> None:
    client.send("START")
    yield
    client.send("STOP")


## tests


def test_no_fps_set(client: Client, recording_name: str) -> None:
    set_recording_name(client, recording_name=recording_name, fps=None)


def test_record(client: Client, with_valid_recording, camera_manager, with_start) -> None:
    exectue_software_triggers(camera_manager, 3)

    time.sleep(1)
    client.assert_frame_count(3)


def test_set_skip_frames(client: Client, with_valid_recording, camera_manager) -> None:
    r: Response = client.send("SET_SKIP_FRAMES", {"skip": 2})

    client.send("START")
    exectue_software_triggers(camera_manager, 3)
    time.sleep(1)
    client.assert_frame_count(1)
    client.send("STOP")


def test_skip_next_frame(client: Client, with_valid_recording, camera_manager, with_start) -> None:
    exectue_software_triggers(camera_manager, 1)

    r: Response = client.send("SKIP_NEXT_FRAME")
    exectue_software_triggers(camera_manager, 2)
    s = client.get_status()

    time.sleep(1)
    client.assert_frame_count(2)


def test_replayable(client: Client, with_valid_recording, camera_manager, with_start, recording_name):
    exectue_software_triggers(camera_manager, 3)
    time.sleep(1)
    client.send("STOP")

    assert PERSISTENT_RECORD.cache_location is not None, "cache location should not be None."

    client.switch_mode("replay")
    client.send("SET_RECORDING_NAME", {"recording_name": recording_name})

    assert PERSISTENT_RECORD.cache_location is not None, "cache location should not be None."

    s = client.get_status()
    assert s["recording_name"] == recording_name

    r: Response = client.send("GET_IMAGES")
    r.assert_contains_images(camera_manager.camera_cnt)
    client.switch_mode("record")
