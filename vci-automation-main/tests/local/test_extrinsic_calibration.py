# ruff: noqa: S101, N806, PLR2004, T201, TC002, INP001, RUF100
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from charuco_calibration.charuco_calibrator import CharucoCalibrator
from controller import Timer

### run with : python -m pytest tests/local -s


@pytest.fixture
def detection_folder(data_path: Path) -> Path:
    return data_path / "extrinsic_single_cameras"


@pytest.fixture
def detection_file(detection_folder: Path) -> Path:
    return detection_folder / "detections.json"


@pytest.fixture
def board_file(detection_folder: Path) -> Path:
    return detection_folder / "board.json"


@pytest.fixture
def calib_dict(detection_folder: Path) -> dict:
    path = detection_folder / "calibration_dome.json"
    with Path.open(path) as f:
        calib = json.load(f)
    return calib  # noqa: RET504


@pytest.fixture
def calibrator_full(detection_file: Path, calib_dict: dict, board_file: Path) -> CharucoCalibrator:
    calibrator = CharucoCalibrator(detection_data=detection_file, board=board_file)
    calibrator.load_calibration_file(calib_dict)
    return calibrator


@pytest.fixture
def calibrator(calibrator_full: CharucoCalibrator) -> CharucoCalibrator:
    calibrator_full.detection_data.reduce_set(15)  # for testcases: reduces amount of detections for speed
    return calibrator_full


def test_check_accuracy_fast(calibrator: CharucoCalibrator) -> None:

    with Timer("check_accuracy"):
        triangulation = calibrator.check_accuracy(error_plot_path=None, cameras_and_boards_plot_path=None)

    for cam_id in triangulation.camera_errors_pixel:
        errors_pixel = triangulation.camera_errors_pixel.get(cam_id, [])
        assert np.mean(errors_pixel) < 0.7, "pixel errors for this set of detections should be less that than 0.7"


def test_target_extrinsic_single_fast(calibrator: CharucoCalibrator) -> None:
    # input:
    # * full detection of all cameras. (with focus on one area of stage)
    # * previous calibration with enough extrinsics
    # * list of cameras to be re-calibrated.

    # this approach skips the bundle adjust, assuming that most cameras are perfectly calibrated.
    # the detected board points are triangualted with the "fixed" cameras and
    # used to place the selected cameras into the existing coordiate system.

    cameras_before = [copy.deepcopy(cam) for cam in calibrator.cameras]

    requested_cam = "C1001"

    triangulation = calibrator.targeted_extrinsic_recalibration([requested_cam])

    errors_pixel = triangulation.camera_errors_pixel.get(requested_cam, [])
    assert (
        np.mean(errors_pixel) < 0.3
    ), f"pixel errors for this set of detections should be less that than 0.3 but it is {np.mean(errors_pixel)}"

    for cam_before, cam_after in zip(cameras_before, calibrator.cameras, strict=True):
        assert cam_before.name == cam_after.name
        if cam_before.name != requested_cam:
            assert np.allclose(
                cam_before.extrinsic_matrix, cam_after.extrinsic_matrix
            ), f" Cameras position of {cam_after.name} is fixed and should stay the same."
        else:
            assert np.allclose(
                cam_before.extrinsic_matrix, cam_after.extrinsic_matrix, atol=1e-4
            ), f" Position of {cam_after.name} should be similar to before re-calibration."


# python -m pytest tests/local --runslow
@pytest.mark.slow
def test_target_extrnsic_multi(calibrator_full: CharucoCalibrator) -> None:
    cameras_before = [copy.deepcopy(cam) for cam in calibrator_full.cameras]

    requested_cams = calibrator_full.detection_data.camera_names[10:15]

    with Timer("base triangulation"):
        base_triangulation = calibrator_full.check_accuracy(
            error_plot_path=None, cameras_and_boards_plot_path=None, anchor_cnt=5
        )

    with Timer("trageted extrisnic_recalibration"):
        triangulation = calibrator_full.targeted_extrinsic_recalibration(requested_cams)

    print("before:")
    print(base_triangulation.print_errors(requested_cams))

    print("\nafter:")
    print(triangulation.print_errors(requested_cams))

    # check result accuracy
    for cam_id in requested_cams:
        errors_pixel = triangulation.camera_errors_pixel.get(cam_id, [])
        errors_pixel_base = base_triangulation.camera_errors_pixel.get(cam_id, [])
        new_mean = np.mean(errors_pixel)
        base_mean = np.mean(errors_pixel_base) * 1.5
        assert (
            new_mean <= base_mean
        ), f"reproection error for {cam_id} after re-calibration should be less that \
            base_error {base_mean} *1.5 pixels but it is {new_mean} pixels"

    for cam_before, cam_after in zip(cameras_before, calibrator_full.cameras, strict=True):
        if cam_before.name in requested_cams:
            # Separate Rotation and Translation for clearer debugging
            R_diff = cam_after.extrinsic_matrix[:3, :3] - cam_before.extrinsic_matrix[:3, :3]
            t_diff = cam_after.extrinsic_matrix[:3, 3] - cam_before.extrinsic_matrix[:3, 3]

            # Check Translation specifically (tolerance in your world units, e.g., 0.5mm)
            assert np.allclose(
                cam_after.extrinsic_matrix[:3, 3], cam_before.extrinsic_matrix[:3, 3], atol=1e-3
            ), f"Translation shift too high for {cam_after.name}: {t_diff}"

            # Check Rotation (tolerance in radians)
            assert np.allclose(
                cam_after.extrinsic_matrix[:3, :3], cam_before.extrinsic_matrix[:3, :3], atol=1e-4
            ), f"Rotation shift too high for {cam_after.name}: {R_diff}"
