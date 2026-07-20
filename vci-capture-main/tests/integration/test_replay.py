# ruff: noqa: S101, N806, PLR2004, T201, TC002, INP001, RUF100

import time
from pathlib import Path

import helpers
import pytest
from client import Client, Response

from sparrow.image_processing.processing_steps import StepDefaults

## fixtures


@pytest.fixture(scope="module", autouse=True)
def switch_to_replay(client: Client) -> None:
    client.switch_mode("replay")


@pytest.fixture(scope="module")
def record_save_path(data_path: Path) -> Path:
    return data_path / "media"


@pytest.fixture(params=["recording_001"])
def any_recording_name(request: str) -> str:
    return request.param


@pytest.fixture
def with_valid_recording(client: Client, any_recording_name: str) -> None:
    helpers.set_recording_name(client, any_recording_name)


## tests


def test_get_images(client: Client, with_valid_recording) -> None:
    r: Response = client.send("GET_IMAGES", {"steps": StepDefaults.SMOL})


def test_get_images_with_mattes(client: Client, with_valid_recording) -> None:
    r: Response = client.send("GET_IMAGES", {"steps": StepDefaults.SMOL, "mattes": True})


def test_get_calibration_file(client: Client, with_valid_recording) -> None:
    r: Response = client.send("GET_CALIBRATION_FILE", {"steps": StepDefaults.SMOL})


def test_get_background_image(client: Client, with_valid_recording) -> None:
    r: Response = client.send("GET_BACKGROUND_IMAGE", {"steps": StepDefaults.SMOL})


def test_get_mean_image(client: Client, with_valid_recording) -> None:
    r: Response = client.send("GET_MEAN_IMAGE", {"steps": StepDefaults.SMOL})


def test_delete_recording(client: Client) -> None:
    r: Response = client.send("DELETE_RECORDING", {"recording_name": "_fake"})


def test_delete_deprecated_background(client: Client) -> None:
    r: Response = client.send("DELETE_DEPRECATED_BACKGROUND", {"recording_name": "_fake"})


def test_get_status(client: Client) -> None:
    r: Response = client.send("STATUS", {"verbose": True})


def test_set_fps(client: Client, any_recording_name: str) -> None:
    r: Response = client.send("SET_FPS", {"fps": 20, "recording_name": any_recording_name})


def test_set_fps_unknown_name(client: Client) -> None:
    with pytest.raises(Exception) as e:
        r: Response = client.send("SET_FPS", {"fps": 20, "recording_name": "this_recording_doesnt_exist"})


def test_set_fps_pass_string(client: Client) -> None:
    with pytest.raises(Exception) as e:
        r: Response = client.send("SET_FPS", {"fps": "20", "recording_name": any_recording_name})


def test_prepare_images(client: Client, with_valid_recording) -> None:
    r: Response = client.send("PREPARE_IMAGES", {"frame_idx": [0, 1, 2]})
    client.send("GET_IMAGES", {"frame_idx": 0})
    client.send("GET_IMAGES", {"frame_idx": 1})


def test_prepare_images_cache_depth(client: Client, with_valid_recording) -> None:
    r: Response = client.send("PREPARE_IMAGES", {"frame_idx": [0, 1, 2] * 10})
    time.sleep(20)


# def test_frame_zero_background(client: Client) -> None:
#     r: Response = client.send("FRAME_ZERO_BACKGROUND")


# def test_set_camera_ids_as_capture(client: Client) -> None:
#     r: Response = client.send("SET_CAMERA_IDS_AS_CAPTURE")
