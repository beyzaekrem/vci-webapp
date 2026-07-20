# ruff: noqa: S101, N806, PLR2004, T201, TC002, INP001, RUF100
import time
from collections.abc import Generator

import pytest
from client import Client, Response
from helpers import set_auto_trigger, setup_software_trigger_auto, setup_software_trigger_single

from sparrow.calibration_data.camera_parameters import CameraParameters
from sparrow.image_processing.process_calibration_data import scale_resolution
from sparrow.image_processing.process_images import process_size_scale
from sparrow.mode_shared.camera_manager import CameraManager
from sparrow.mode_shared.persistent import PersistentData

### fixtures


@pytest.fixture(scope="module", autouse=True)
def switch_mode(client: Client, with_resolution) -> None:
    client.switch_mode("ring_buffer")


@pytest.fixture(scope="module")
def test_resolution() -> int:
    return 1024


@pytest.fixture(scope="module")
def with_resolution(
    camera_manager: CameraManager, persistent_data: PersistentData, test_resolution: int
) -> Generator[None]:
    """Sets the image resolution of the simulated cameras to test_resolution (width)"""
    previous_resolution = {}
    for cam in camera_manager.cameras:
        if cam.manufacturer != "Simulated":
            continue

        previous_w = cam.get_parameter_int("width")
        print("previous_w", previous_w)
        previous_h = cam.get_parameter_int("height")
        scale_factor: Response = test_resolution // previous_w
        previous_resolution[cam.camera_id] = (previous_w, previous_h)

        # set camera buffer output resolution.
        cam.set_parameter_int("width", previous_w * scale_factor)
        cam.set_parameter_int("height", previous_h * scale_factor)
        # scale calibration data resolution.
        params: CameraParameters = persistent_data.calibration_data.get(cam.camera_id)
        scale_resolution(params, scale_factor)
        # scale background image.
        bg_img = persistent_data.backgrounds.raw_background_images[cam.camera_id]

        print(f"{cam.camera_id} bg_img shape before: {bg_img.shape}")
        process_size_scale(bg_img, {"factor": 2}, params)
        print(f"{cam.camera_id} bg_img after: {bg_img.shape}")
    persistent_data.backgrounds.clear_cache()

    yield

    camera_manager.stop_cameras()
    for cam in camera_manager.cameras:
        w, h = previous_resolution[cam.camera_id]
        cam.set_parameter_int("width", w)
        cam.set_parameter_int("height", h)
    # undo scale of calbration data and background images
    persistent_data.load(camera_manager.camera_ids)


@pytest.fixture
def with_start(client: Client) -> None:
    client.send("STOP")
    setup_software_trigger_single(client)
    client.send("START")
    print("------------ Ring Buffer STARTED --------------")
    time.sleep(0.5)
    yield
    time.sleep(0.2)
    print("STOP...")
    client.send("STOP")
    print("------------ Ring Buffer Stopped --------------")


### helpers
def trigger_single(client: Client) -> None:
    client.send("SOFTWARE_TRIGGER_SINGLE")


def get_ring_buffer_cameras(client: Client) -> list[str]:
    r: Response = client.send("STATUS")
    d = r.get_dict()
    return d["camera_ids"]


## tests


def test_opens_only_color(client: Client) -> None:
    selected_camera_ids = get_ring_buffer_cameras(client)
    assert all(
        c[0] == "C" for c in selected_camera_ids
    ), f"ring buffer should open some cameras  only open color cameras. openend: {selected_camera_ids}"


def test_get_background_image(client: Client, camera_manager: CameraManager) -> None:
    selected_camera_ids = get_ring_buffer_cameras(client)

    r: Response = client.send("GET_BACKGROUND_IMAGE")
    r.assert_contains_images(len(selected_camera_ids))
    d = r.get_dict()
    info = d["image_info"]
    print(info)
    for entry in info:
        shape = entry["shape"]
        assert shape == [3, 1024, 1024], f"shape should be [3, 1024, 1024] but is {shape}"


def test_set_threshold(client: Client) -> None:
    r: Response = client.send("SET_THRESHOLD", {"threshold": 0.5})


def test_run(client: Client) -> None:
    setup_software_trigger_auto(client, 20)  # set to 20 fps auto-trigger
    client.send("START")
    time.sleep(5)
    set_auto_trigger(client, enabled=False)  # stops auto trigger
    time.sleep(0.5)
    r: Response = client.send("STATUS")
    client.send("STOP")
    fc = r.get_dict()["frame_count"]
    assert fc > 0, "frame count should be > 0"


def test_get_images(client: Client, with_start) -> None:
    trigger_single(client)
    time.sleep(2)
    r: Response = client.send("STATUS")
    d = r.get_dict()
    print(d)
    r: Response = client.send("GET_IMAGES")


def test_get_mattes(client: Client, with_start) -> None:
    trigger_single(client)
    time.sleep(2)
    r: Response = client.send("GET_MATTES")
