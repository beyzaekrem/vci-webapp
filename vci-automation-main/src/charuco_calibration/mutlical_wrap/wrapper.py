# ruff: noqa: E402, INP001

import numpy as np
from structs.struct import struct

from charuco_calibration.camera import Camera

np.int = int  # noqa: NPY001
np.bool = bool  # patch for multical.

import pickle
from pathlib import Path

import numpy as np
from multical import tables
from multical.optimization.calibration import Calibration as multical_Calibration

from charuco_calibration.board import Board
from charuco_calibration.detection_data import DetectionData

from .run_extrinsic_calibration import extrinsic_calibration_bundle_adjust
from .transform_origin import set_origin_board_pose, set_origin_camera, update_extrinsics

# ANSI escape codes
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


class MutliCalWrapper:
    _calib: multical_Calibration | None = None
    origin: str | None = None

    def __init__(self, detection_data: DetectionData, board: Board, cameras: list[Camera]) -> None:
        self.detection_data = detection_data
        self.board = board
        self.cameras = cameras
        self.calibrate_extrinsics()

    def calibrate_extrinsics(self) -> list[Camera]:
        """Calibrates the position of *all* cameras via bundle adjust.

        Raises:
            InvalidDetectionData: DetectionData is not complete.
        """

        print("\nExtrinsic calibration...")
        self._calib = extrinsic_calibration_bundle_adjust(self.detection_data, self.board, self.cameras)

        print(f"\nDone with extrinsic bundle adjust for {len(self._calib.cameras.names)} cameras.")
        if sum(self._calib.camera_poses.valid) != len(self._calib.cameras.names):
            valid = sum(self._calib.camera_poses.valid)
            total = len(self._calib.cameras.names)
            failed = total - valid

            msg = (
                f"{BOLD}{RED}⚠️  WARNING: Failed to estimate positions for {failed}/{total} cameras. "
                f"These cameras were probably missing detections.{RESET}"
            )
            print(msg)

        self.cameras = update_extrinsics(self._calib, self.cameras)
        self.origin = f"Origin is camera {self._calib.cameras.names[0]}."

    def set_origin_board(
        self, detection_index: int | None = None, *, center_of_cameras_bb: bool = True
    ) -> list[Camera]:
        self._check_bundle_adjust()
        if detection_index is None:
            detection_index = self.detection_data.origin_capture_idx
        self._calib = set_origin_board_pose(self._calib, detection_index, center_of_cameras_bb)
        self.origin = "Origin is the stage center at floor level."
        return update_extrinsics(self._calib, self.cameras)

    def set_origin_camera(self, camera_name: str) -> list[Camera]:
        self._check_bundle_adjust()
        self._calib = set_origin_camera(self._calib, camera_name)
        self.origin = f"Origin is camera {camera_name}."
        return update_extrinsics(self._calib, self.cameras)

    def _check_bundle_adjust(self) -> None:
        if self._calib is None:
            msg = "Bundle Adjust Calib is empty."
            raise RuntimeError(msg)

    def dump_calib_pkl(self, filepath: str = "debug_calibration.pkl") -> None:
        self._check_bundle_adjust()
        with Path(filepath).open("wb") as f:
            pickle.dump(self._calib, f)

    def export_camera_and_boards(
        self,
        camera_names: list[str] | None = None,
        boardnames: list[str] | None = None,
    ) -> dict:

        calib = self._calib
        camera_poses = tables.inverse(calib.pose_estimates.camera)
        board_poses = tables.expand_boards(calib.pose_estimates)  # set of board poses for each image pair
        board_poses = struct(poses=board_poses.poses[0], valid=board_poses.valid[0])  # board poses for first image pair
        if camera_names is None:
            camera_names = [str(indx) for indx in range(len(camera_poses.poses))]
        if boardnames is None:
            boardnames = [str(indx) for indx in range(len(board_poses.poses))]

        valid_camera_poses = dict(zip(camera_names, camera_poses.poses, strict=True))
        camera_view_matrix_json = [
            {
                "camera_id": name,
                "extrinsics": {"view_matrix": valid_camera_poses[name].flatten().tolist()},
                "intrinsics": {
                    "camera_matrix": camera.intrinsic.flatten().tolist(),
                    "resolution": camera.image_size,
                    "distortion_coefficients": camera.dist.flatten().tolist(),
                },
                "intrinsics_auxiliary": {
                    "field_of_view_deg": [
                        np.rad2deg(2 * np.arctan2(camera.image_size[0], 2 * camera.intrinsic[0, 0])),
                        np.rad2deg(2 * np.arctan2(camera.image_size[1], 2 * camera.intrinsic[1, 1])),
                    ]
                },
            }
            for name, camera, valid in zip(camera_names, calib.cameras, camera_poses.valid, strict=True)
            if valid
        ]

        board_poses_json = [
            {
                "board_name": name,
                "extrinsics": {"view_matrix": extrinsicMatrix.flatten().tolist()},
            }
            for name, extrinsicMatrix, valid in zip(boardnames, board_poses.poses, board_poses.valid, strict=True)
            if valid
        ]

        return {
            "meta": "camera and board poses relative to camera 0",
            "cameras": camera_view_matrix_json,
            "boards": board_poses_json,
        }
