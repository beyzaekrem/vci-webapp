# ruff: noqa: S101, N806, PLR2004, T201, TC002, INP001, RUF100
from pathlib import Path

import helpers
import pytest
from client import Client, Response

from sparrow.calibration_data.background_images import BackgroundImages
from sparrow.image_processing.processing_steps import StepDefaults
from sparrow.mode_shared.camera_manager import CameraManager


@pytest.fixture(scope="module", autouse=True)
def switch_mode(client: Client) -> None:
    client.switch_mode("single")


@pytest.fixture(scope="module", autouse=True)
def with_start_here(client) -> None:
    client.send("START")
    yield
    client.send("STOP")


def test_get_images(client: Client, camera_manager: CameraManager) -> None:
    r: Response = client.send("GET_IMAGES")
    r.assert_contains_images(camera_manager.camera_cnt)


def test_get_images_with_mattes(client: Client, camera_manager: CameraManager) -> None:
    r: Response = client.send("GET_IMAGES", {"mattes": True})
    r.assert_contains_images(camera_manager.camera_cnt * 2)


def test_get_background_image(client: Client, camera_manager: CameraManager) -> None:
    r: Response = client.send("GET_BACKGROUND_IMAGE", {"steps": StepDefaults.SMOL})
    r.assert_contains_images(camera_manager.camera_cnt)


def test_flush_image_buffer(client: Client, camera_manager) -> None:
    helpers.exectue_software_triggers(camera_manager, 2)
    r: Response = client.send("FLUSH_IMAGE_BUFFER")


def test_skip_next_frame(client: Client, camera_manager) -> None:
    r: Response = client.send("SKIP_NEXT_FRAME")
    helpers.exectue_software_triggers(camera_manager, 1)
    r: Response = client.send("GET_IMAGES")


def test_take_background_image(client: Client, with_persistent_path) -> None:
    path_should_exist = BackgroundImages.resolve_camera_id(with_persistent_path.background_images_path_pattern, "C7777")
    Path.mkdir(Path(path_should_exist).parent, exist_ok=True)
    r: Response = client.send("TAKE_BACKGROUND_IMAGE")
    print("path_should_exist", path_should_exist)
    assert Path(path_should_exist).exists(), f"background image should exist {path_should_exist}"
