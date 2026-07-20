import datetime
from zoneinfo import ZoneInfo

import numpy as np


class Camera:
    class NotCalibratedError(Exception):
        pass

    extrinsic_matrix = None

    def __init__(self, name: str) -> None:
        self.name = name

    def set_intrisics(self, intrinsic: np.array, distortion_coeff: np.array, image_size: np.array) -> None:
        self.intrinsic: np.array = intrinsic
        self.distortion_coeff = distortion_coeff
        self.image_size = image_size

    @property
    def rot(self) -> np.ndarray:
        if self.extrinsic_matrix is None:
            return None
        return self.extrinsic_matrix[:3, :3]  # R

    @property
    def t(self) -> np.ndarray:
        if self.extrinsic_matrix is None:
            return None
        return self.extrinsic_matrix[:3, 3]  # T

    @property
    def world_pos(self) -> np.ndarray:
        if self.extrinsic_matrix is None:
            return None
        return -self.rot.T @ self.t

    @property
    def projection_matrix(self) -> np.ndarray:
        """The projection matrix (3x4) maps 3D points in the real world (in homogenous coordiantes)
        to a 2D (pixel) position on the image plane.
        The projection matrix contains both the intrinic and the extrinic infos of the camera.

        Returns:
            np.ndarray: projection_matrix shape (3, 4)
        Raises:
            NotCalibratedError: camera is missing intrinsic or extrinsic calibration.
        """
        if self.intrinsic is not None and self.extrinsic_matrix is not None:
            intrinsic = self.intrinsic
            extrinsic = self.extrinsic_matrix

            rotation = extrinsic[:3, :3]
            translation = extrinsic[:3, 3].reshape(3, 1)

            rot_t = np.hstack((rotation, translation))  # shape (3, 4)
            return intrinsic @ rot_t  # projection matrix: shape (3, 4)
        msg = "Camera not fully calibrated"
        raise self.NotCalibratedError(msg)

    def reproject(self, world_point_3d: np.array) -> np.array:
        """Reprojects a world point onto the image plane.

        Args:
            world_point_3d (np.array): 3d world position

        Returns:
            np.array: 2D pxiel positon.
        """
        world_point_homog = np.append(world_point_3d, 1.0)
        proj = self.projection_matrix @ world_point_homog
        return proj[:2] / proj[2]


def load_dome_format(calibration_dict: dict, camera_names: list[str] | None = None) -> list[Camera]:
    """Loads the calibrated camera data from a dome json file. Filters and sorts by camera_names.

    Each camera contains (if available):

    intrinsics - resolution, distortion_coefficients, camera_matrix

    extrincis - view_matrix
    """

    calibration_cameras = calibration_dict["cameras"]

    calibrated_cameras: dict[str, Camera] = {}
    # loads all cameras from json
    for calib in calibration_cameras:

        camera_id = calib.get("camera_id", "Err")

        extrinsic_matrix = calib.get("extrinsics", {}).get("view_matrix", None)
        if extrinsic_matrix is not None:
            extrinsic_matrix = np.array(extrinsic_matrix).reshape((4, 4))

        intrinsics = calib.get("intrinsics")
        resolution = np.array(intrinsics.get("resolution"))
        distortion = np.array(intrinsics.get("distortion_coefficients"))
        intrinsic_matrix = intrinsics.get("camera_matrix")
        if intrinsic_matrix is not None:
            intrinsic_matrix = np.array(intrinsic_matrix).reshape((3, 3))

        c: Camera = Camera(camera_id)
        c.set_intrisics(intrinsic_matrix, distortion, resolution)
        c.extrinsic_matrix = extrinsic_matrix

        calibrated_cameras[camera_id] = c

    if camera_names is not None:  # filters and sorts by camera_names, if given
        return [calibrated_cameras.get(camera_id) for camera_id in camera_names]
    return list(calibrated_cameras.values())


def compile_json_from_cameras(
    cameras: list[Camera], origin_desc: str = "Origin is the stage center at floor level."
) -> dict:
    camera_configs: list[dict] = []
    for camera in cameras:
        entry = {"camera_id": camera.name}
        if camera.intrinsic is not None:
            entry["intrinsics"] = {
                "camera_matrix": camera.intrinsic.flatten().tolist(),
                "resolution": [int(r) for r in camera.image_size],
                "distortion_coefficients": camera.distortion_coeff.flatten().tolist(),
            }
        if camera.extrinsic_matrix is not None:
            entry["extrinsics"] = {"view_matrix": camera.extrinsic_matrix.flatten().tolist()}
        camera_configs.append(entry)

    timestamp = datetime.datetime.now(tz=ZoneInfo("Europe/Berlin")).isoformat()
    coordinate_system = f"Extrinsics (world-to-camera) use OpenCV coordinate system (x-right, y-down, z-forward into the scene). {origin_desc}"
    calibration_info = {"coordinate_system": coordinate_system, "matrix_layout": "row_major", "timestamp": timestamp}

    return {
        "meta": {"calibration": calibration_info},
        "cameras": camera_configs,
    }
