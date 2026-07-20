import helpers
import pytest
from client import Client, Response

from sparrow.mode_shared.camera_manager import CameraManager


@pytest.fixture(scope="module", autouse=True)
def switch_to_calibration(client: Client) -> None:
    client.switch_mode("calibration")


@pytest.fixture(scope="module", autouse=True)
def with_start_here(client: Client) -> None:
    helpers.setup_software_trigger_single(client)
    client.send("START")
    yield
    client.send("STOP")


def test_color_checker_detection(client: Client) -> None:

    r: Response = client.send("COLOR_CHECKER_DETECTION", {})
    d = r.assert_dict_contains(["frame_idx", "camera_ids", "swatches", "image_info"])
    assert d["image_info"] == [], "no images, requested should give us empty image_info"


def test_color_checker_detection_with_images(client: Client, camera_manager: CameraManager) -> None:
    r: Response = client.send("COLOR_CHECKER_DETECTION", {"rgb": True})
    r.get_dict()
    r.assert_contains_images(camera_manager.camera_cnt)


def test_color_checker_detection_camera_selection(client: Client, camera_manager: CameraManager) -> None:
    r: Response = client.send("COLOR_CHECKER_DETECTION", {"rgb": True, "camera_ids": camera_manager.camera_ids[:1]})
    r.get_dict()
    r.assert_contains_images(1)


def test_charuco_detection(client: Client) -> None:
    r: Response = client.send("CHARUCO_DETECTION")
    r.assert_dict_contains(["frame_idx", "camera_ids", "detection_success", "detections", "shapes", "image_info"])


def test_charuco_detection_images(client: Client, camera_manager: CameraManager) -> None:
    r: Response = client.send("CHARUCO_DETECTION", {"rgb": True})
    r.assert_contains_images(camera_manager.camera_cnt)


def test_charuco_detection_camera_selection(client: Client, camera_manager: CameraManager) -> None:
    r: Response = client.send("COLOR_CHECKER_DETECTION", {"rgb": True, "camera_ids": camera_manager.camera_ids[:1]})
    r.get_dict()
    r.assert_contains_images(1)


def test_calcualte_image_brightness(client: Client) -> None:
    r: Response = client.send("CALCULATE_IMAGE_BRIGHTNESS")
    r.assert_elemnt_cnt(1)
    r.assert_dict_contains(["brightnesses", "camera_ids"])


def test_flush_image_buffer(client: Client) -> None:
    r: Response = client.send("FLUSH_IMAGE_BUFFER")


def test_set_charuco_board(client: Client) -> None:
    parameters = {
        "dict_name": "4X4_1000",
        "size": [29, 19],
        "square_length": 0.040,
        "marker_length": 0.031,
    }
    r: Response = client.send("SET_CHARUCO_BOARD", parameters)
