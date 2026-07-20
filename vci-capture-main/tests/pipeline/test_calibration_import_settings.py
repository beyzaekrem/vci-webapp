# ruff: noqa: S101, TC002  # noqa: INP001
from pathlib import Path

import numpy as np
import pytest
from pyquaternion import Quaternion

from sparrow import utils
from sparrow.calibration_data import CalibrationData, CameraParameters, ImportSettings
from sparrow.calibration_data.calibration_data import iso_format
from sparrow.calibration_data.camera_parameters import _check_import_settings

###  This file contains tests that check the import and conversion of calibration files.
###  specifically we are checking if adjusting the rotation (rot90), origin position
### and vertical axis works are expected
###  the test data is located in tests/data

### run with : python -m pytest tests/pipeline

# -- Helpers --


def unit_vector(vector: np.array) -> np.array:
    """Returns the unit vector of the vector."""
    return vector / np.linalg.norm(vector)


def angle_between(v1: np.array, v2: np.array) -> np.array:
    """Returns the angle in radians between vectors 'v1' and 'v2'::

    >>> angle_between((1, 0, 0), (0, 1, 0))
    1.5707963267948966
    >>> angle_between((1, 0, 0), (1, 0, 0))
    0.0
    >>> angle_between((1, 0, 0), (-1, 0, 0))
    3.141592653589793
    """
    v1_u = unit_vector(v1)
    v2_u = unit_vector(v2)
    return np.arccos(np.clip(np.dot(v1_u, v2_u), -1.0, 1.0))


def load_scenario(path: Path, rotations: dict, settings_dict: dict) -> tuple[CalibrationData, CalibrationData]:
    """Helper to apply legacy settings and load calibration."""
    # Load Original (As-Is)
    o = ImportSettings()
    o = o.as_is()
    orig = CalibrationData()
    orig.load(path, None, rotations, o)

    # Load Normalized
    n = ImportSettings()
    n = n.as_is()
    for key, value in settings_dict.items():
        setattr(n.legacy, key, value)
    norm = CalibrationData()
    norm.load(path, None, rotations, n)

    # filter out missing view_matrix
    orig.camera_parameters = {cam_id: entry for cam_id, entry in orig.camera_parameters.items() if entry.view_matrix is not None}
    norm.camera_parameters = {cam_id: entry for cam_id, entry in norm.camera_parameters.items() if cam_id in orig.camera_ids}

    return orig, norm


# -- test Fixtures --


@pytest.fixture(scope="module")
def rotations(config_folder: Path) -> dict:
    return utils.read_json_file(config_folder / "camera_rotations.json")


@pytest.fixture(scope="module")
def calib_old_rotation(config_folder: Path, rotations: dict) -> tuple[CalibrationData, CalibrationData]:
    path = config_folder / "2025_12_18_percaligo_001_calib.json"
    return load_scenario(path, rotations, {"correct_rotation": True})


@pytest.fixture(scope="module")
def calib_c0004_origin(config_folder: Path, rotations: dict) -> tuple[CalibrationData, CalibrationData]:
    path = config_folder / "bonn_tele_bench_001_calib.json"
    return load_scenario(path, rotations, {"correct_rotation": True, "c0004_is_origin": True})


@pytest.fixture(scope="module")
def calib_up_is_down(config_folder: Path, rotations: dict) -> tuple[CalibrationData, CalibrationData]:
    path = config_folder / "2025_12_18_percaligo_001_calib.json"
    return load_scenario(path, rotations, {"correct_rotation": True, "up_is_down": True})


@pytest.fixture(scope="module")
def calib_current(config_folder: Path, rotations: dict) -> tuple[CalibrationData, CalibrationData]:
    path = config_folder / "2026_01_28_voludogs_001_calib.json"
    return load_scenario(path, rotations, {})


@pytest.fixture(scope="module")
def up_dir() -> np.array:
    return np.array([0, -1, 0])


@pytest.fixture(scope="module")
def view_dir() -> np.array:
    return np.array([0, 0, 1])


@pytest.fixture(params=["calib_old_rotation", "calib_c0004_origin", "calib_up_is_down"])
def any_calib(request: str) -> tuple[dict, dict, dict]:
    """A generic fixture that yields each calibration scenario."""
    return request.getfixturevalue(request.param)


# -- tests --


def test_landscape_calib(any_calib: tuple[CalibrationData, CalibrationData]) -> None:
    _, calib_data = any_calib
    for camera_id in calib_data.camera_ids:
        c: CameraParameters = calib_data.get(camera_id)
        res = c.resolution
        assert np.allclose(
            res, np.array([5328, 4608])
        ), f"camera {camera_id} should have resolution {[5328, 4608]} in normalized import, but its resolution is {res}"


def test_quaternion_castable(any_calib: tuple[CalibrationData, CalibrationData]) -> None:
    orig, norm = any_calib
    for cam_id in orig.camera_ids:
        c1: CameraParameters = orig.get(cam_id)
        c2: CameraParameters = norm.get(cam_id)
        assert c1.camera_id == c2.camera_id, "camera names should be the same"
        c1.rotation_quat()  # shouldn't fail
        c2.rotation_quat()


def test_internal_validity(
    any_calib: tuple[CalibrationData, CalibrationData], up_dir: np.array, view_dir: np.array
) -> None:
    orig, norm = any_calib
    for cam_id in orig.camera_ids:
        c2: CameraParameters = norm.get(cam_id)
        q2: Quaternion = c2.rotation_quat()

        view_2 = q2.rotate(view_dir)
        up2 = q2.rotate(up_dir)

        dot = np.dot(up2, view_2)
        assert np.isclose(dot, 0), "the up vector after rotation should be orthogonal to its view vector"


def test_rotation_position_stays_the_same(calib_old_rotation: tuple[CalibrationData, CalibrationData]) -> None:
    orig, norm = calib_old_rotation
    for cam_id in orig.camera_ids:
        c1: CameraParameters = orig.get(cam_id)
        c2: CameraParameters = norm.get(cam_id)
        assert c1.camera_id == c2.camera_id, "camera names should be the same"
        assert (c1.world_pos() == c2.world_pos()).all(), "world positon of camera should stay the same after rotation"


def test_rotation_viewing_direction_invariance(
    calib_old_rotation: tuple[CalibrationData, CalibrationData], view_dir: np.array
) -> None:
    orig, norm = calib_old_rotation
    for cam_id in orig.camera_ids:
        c1: CameraParameters = orig.get(cam_id)
        c2: CameraParameters = norm.get(cam_id)
        assert c1.camera_id == c2.camera_id, "camera names should be the same"
        q1: Quaternion = c1.rotation_quat()  # shouldn't fail
        q2: Quaternion = c2.rotation_quat()

        view_1 = q1.rotate(view_dir)
        view_2 = q2.rotate(view_dir)
        assert np.isclose(view_1, view_2).all(), "the View direction of the camera should stay the same after rotation"


def test_rotation_up_dir(calib_old_rotation: tuple[CalibrationData, CalibrationData], up_dir: np.array) -> None:
    orig, norm = calib_old_rotation
    for cam_id in orig.camera_ids:
        c1: CameraParameters = orig.get(cam_id)
        c2: CameraParameters = norm.get(cam_id)
        assert c1.camera_id == c2.camera_id, "camera names should be the same"
        q1: Quaternion = c1.rotation_quat()  # shouldn't fail
        q2: Quaternion = c2.rotation_quat()

        up1 = q1.rotate(up_dir)
        up2 = q2.rotate(up_dir)
        assert not np.isclose(
            up1, up2
        ).any(), "the up direction of the camera should *not* stay the same after rotation"


def test_rotation_up_dir_change(calib_old_rotation: tuple[CalibrationData, CalibrationData], up_dir: np.array) -> None:
    orig, norm = calib_old_rotation
    for cam_id in orig.camera_ids:
        c1: CameraParameters = orig.get(cam_id)
        c2: CameraParameters = norm.get(cam_id)
        assert c1.camera_id == c2.camera_id, "camera names should be the same"
        q1: Quaternion = c1.rotation_quat()  # shouldn't fail
        q2: Quaternion = c2.rotation_quat()

        up1 = q1.rotate(up_dir)
        up2 = q2.rotate(up_dir)

        dot = np.dot(up1, up2)

        assert np.isclose(
            dot, 0, atol=1e-7
        ), "the up vector after rotation is expected to be orthogonal to the previous up vector"


def test_origin_centered_on_c0004(calib_c0004_origin: tuple[CalibrationData, CalibrationData]) -> None:
    (
        orig,
        _,
    ) = calib_c0004_origin
    assert "C0004" in orig.camera_ids
    # The world position of the specific origin camera must be (0,0,0)
    assert np.isclose(
        orig.get("C0004").world_pos(), [0, 0, 0], atol=1e-7
    ).all(), "sanity check: C0004 should be center initially"


def test_origin_shifted(calib_c0004_origin: tuple[CalibrationData, CalibrationData]) -> None:
    _, norm = calib_c0004_origin
    assert "C0004" in norm.camera_ids, "C0004 should be in calibration"
    assert not np.isclose(norm.get("C0004").world_pos(), [0, 0, 0], atol=1e-7).all()


def test_origin_shift_preserves_relative_geometry(calib_c0004_origin: tuple[CalibrationData, CalibrationData]) -> None:
    orig, norm = calib_c0004_origin
    # Distance between any two cameras should be identical before and after shift
    cams = orig.camera_ids[:2]
    dist_orig = np.linalg.norm(orig.get(cams[0]).world_pos() - orig.get(cams[1]).world_pos())
    dist_norm = np.linalg.norm(norm.get(cams[0]).world_pos() - norm.get(cams[1]).world_pos())
    assert np.isclose(dist_orig, dist_norm), "The distances between cameras should be preserverd in origin shift"


def test_up_is_down_position(calib_up_is_down: tuple[CalibrationData, CalibrationData]) -> None:
    orig, norm = calib_up_is_down
    for cam_id in orig.camera_ids:
        c1: CameraParameters = orig.get(cam_id)
        c2: CameraParameters = norm.get(cam_id)
        assert not np.allclose(
            c1.world_pos(), c2.world_pos(), atol=1e-7
        ), "The world pos should not be the same anymore"


def test_up_is_down_position_2(calib_up_is_down: tuple[CalibrationData, CalibrationData]) -> None:
    orig, norm = calib_up_is_down
    for cam_id in orig.camera_ids:
        c1: CameraParameters = orig.get(cam_id)
        c2: CameraParameters = norm.get(cam_id)
        p1 = c1.world_pos() * np.array([1.0, -1.0, -1.0])
        p2 = c2.world_pos()
        assert np.allclose(p2, p1, atol=1e-7), "The world pos should have it's y inverted"


def test_up_is_down_inverts_y(calib_up_is_down: tuple[CalibrationData, CalibrationData], up_dir: np.array) -> None:
    orig, norm = calib_up_is_down
    for cam_id, c1 in orig.camera_parameters.items():
        c2 = norm.get(cam_id)
        u1 = c1.rotation_quat().rotate(up_dir)
        u2 = c2.rotation_quat().rotate(up_dir)
        # In this mode, the new UP should be exactly the opposite of the old UP
        assert not np.allclose(u1, u2, atol=1e-7), "The new Up should have changed"


def test_up_is_down_preserves_relative_geometry(calib_up_is_down: tuple[CalibrationData, CalibrationData]) -> None:
    orig, norm = calib_up_is_down
    # Distance between any two cameras should be identical before and after shift
    cams = orig.camera_ids[:2]
    dist_orig = np.linalg.norm(orig.get(cams[0]).world_pos() - orig.get(cams[1]).world_pos())
    dist_norm = np.linalg.norm(norm.get(cams[0]).world_pos() - norm.get(cams[1]).world_pos())
    assert np.isclose(dist_orig, dist_norm), "The distances between cameras should be preserverd in origin shift"


def test_find_import_settings_rot(calib_old_rotation: tuple[CalibrationData, CalibrationData]) -> None:
    original, _ = calib_old_rotation
    settings = ImportSettings()
    _check_import_settings(original.calib_json, settings)

    assert settings.legacy.correct_rotation  # should be true and have effekt
    assert settings.legacy.up_is_down
    assert not settings.legacy.c0004_is_origin


def test_find_import_settings_origin(calib_c0004_origin: tuple[CalibrationData, CalibrationData]) -> None:
    (
        original,
        _,
    ) = calib_c0004_origin
    settings = ImportSettings()
    _check_import_settings(original.calib_json, settings)

    assert settings.legacy.correct_rotation  # should be true but have no effect
    assert not settings.legacy.up_is_down
    assert settings.legacy.c0004_is_origin


def test_find_import_settings_up_is_down(calib_up_is_down: tuple[CalibrationData, CalibrationData]) -> None:
    orig, _ = calib_up_is_down
    settings = ImportSettings()
    _check_import_settings(orig.calib_json, settings)

    assert settings.legacy.correct_rotation  # should be true but have no effect
    assert settings.legacy.up_is_down
    assert not settings.legacy.c0004_is_origin


def test_find_import_settings_current(calib_current: tuple[CalibrationData, CalibrationData]) -> None:
    orig, _ = calib_current
    settings = ImportSettings()
    _check_import_settings(orig.calib_json, settings)

    assert settings.legacy.correct_rotation  # should be true but have no effect
    assert not settings.legacy.up_is_down
    assert not settings.legacy.c0004_is_origin


def test_timestamp_old() -> None:
    timestamp = "2025.04.02 18:51"
    output = iso_format(timestamp)
    assert output == "2025-04-02T18:51:00+02:00"


def test_timestamp_new() -> None:
    timestamp = "2026-02-05T14:29:47+01:00"
    output = iso_format(timestamp)
    assert output == timestamp


def test_timestamp_nonesense() -> None:
    timestamp = "today is today"
    output = iso_format(timestamp)
    assert timestamp == output


def test_timestamp_unknown_format() -> None:
    timestamp = "24.12.2025 20:00"
    output = iso_format(timestamp)
    assert timestamp == output


def test_timestamp_none() -> None:
    timestamp = None
    output = iso_format(timestamp)
    assert output is None


def test_no_calibration_found() -> None:
    camera_ids = ["C0001", "C0002", "C0003"]
    c = CalibrationData()
    c.load(Path("lalalala_I_dont_exist_hahahahha.json"), ["C0001", "C0002", "C0003"], None)

    assert c.camera_ids == camera_ids


def test_resolution_rotated(calib_current: tuple[CalibrationData, CalibrationData]) -> None:
    (
        _,
        norm,
    ) = calib_current
    c0: CameraParameters = norm.get("C0000")
    assert np.allclose(
        c0.get_resolution_rotated(),
        np.array([4608, 5328]),
    )


def test_resolution_overwrite_no_rotated(calib_current: tuple[CalibrationData, CalibrationData]) -> None:
    _, calib_data = calib_current
    c0: CameraParameters = calib_data.get("C0000")
    assert np.allclose(
        c0.get_resolution_rotated(no_rotation=True),
        np.array([5328, 4608]),  # W, H
    )


def test_get_shape_color(any_calib: tuple[CalibrationData, CalibrationData]) -> None:
    _, calib_data = any_calib

    c0: CameraParameters = calib_data.get("C0000")
    shape = c0.get_shape(scale=0.5)
    assert np.allclose(
        shape,
        np.array([3, 5328 // 2, 4608 // 2]),  # C, H, W
    )


def test_get_shape_color_mask(any_calib: tuple[CalibrationData, CalibrationData]) -> None:
    _, calib_data = any_calib

    c0: CameraParameters = calib_data.get("C0000")
    shape = c0.get_shape(scale=0.5)
    actual_shape = shape[-2:]
    expected_shape = np.array([5328 // 2, 4608 // 2])  # C, H, W
    assert np.allclose(actual_shape, expected_shape), f"Expected shape {expected_shape} but is {actual_shape}"


def test_get_shape_mono(calib_current: tuple[CalibrationData, CalibrationData]) -> None:
    _, calib_data = calib_current

    c0: CameraParameters = calib_data.get("M0001")
    shape = c0.get_shape(scale=1)
    assert np.allclose(
        shape,
        np.array([5328, 4608]),  # C, H, W
    )
