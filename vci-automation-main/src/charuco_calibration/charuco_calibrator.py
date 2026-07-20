import contextlib
import json
from pathlib import Path

import numpy as np

from .board import Board
from .camera import Camera, compile_json_from_cameras, load_dome_format
from .dataset_triangulation import DatasetTriangulation
from .detection_data import (
    DetectionData,
)
from .exceptions import InvalidDetectionData
from .intrinsic import calibrate_intrinsics
from .mutlical_wrap.wrapper import MutliCalWrapper


class CharucoCalibrator:
    detection_data: DetectionData
    board: Board | None

    cameras: list[Camera] | None = None
    calib_json: dict | None = None
    bundle_adjust_system: MutliCalWrapper | None = None

    def __init__(self, detection_data: DetectionData | Path, board: Board | Path | None = None) -> None:
        if isinstance(detection_data, (Path, str)):
            self.detection_data = DetectionData.load_from_file(detection_data)
        else:
            self.detection_data = detection_data

        if self.detection_data is None:
            msg = "Detection Data missing"
            raise RuntimeError(msg)

        if isinstance(board, Path):
            self.board = Board(board)
        else:
            self.board = board

    def load_calibration_file(self, calibration_dict: dict, camera_names: list[str] | None = None) -> None:
        """
        Loads the calibrated camera data from a dome json file. Filters and sorts by camera_names.
        Sets self.cameras to the loaded data.

        Each camera contains (if available):
        * name
        * intrinsics
            * resolution
            * distortion_coefficients
            * camera_matrix
        * extrincis
            *view_matrix
        """
        if camera_names is None and self.detection_data is not None:
            camera_names = self.detection_data.camera_names
        self.cameras: list[Camera] = load_dome_format(calibration_dict, camera_names)

    def calibrate(self) -> None:
        self.intrinsic_calibration()
        self.extrinsic_calibration_bundle_adjust()

    def _check_data_exists(self, camera_filter: list[str] | None = None) -> None:
        if self.detection_data is None:
            msg = "Detection Data missing"
            raise RuntimeError(msg)
        if self.board is None:
            msg = "Board missing"
            raise RuntimeError(msg)
        if camera_filter:
            missing = [cam_id for cam_id in camera_filter if cam_id not in self.detection_data.camera_names]
            if len(missing) != 0:
                msg = f"Camera(s) {missing} are not present in detection_data."
                raise RuntimeError(msg)

    def _check_intrinsics_exist(self, camera_filter: list[str] | None = None) -> None:
        if self.cameras is None:
            msg = "Cannot calibrate extrinsic parameters without intrinsic info"
            raise InvalidDetectionData(msg)

        cameras = self.cameras
        if camera_filter:
            cameras = [cam for cam in cameras if cam.name in camera_filter]
            # if camera is not present, if has no calibration info at all.
            not_found = [cam_id for cam_id in camera_filter if cam_id not in [cam.name for cam in cameras]]
            if len(not_found) > 0:
                msg = f"Camera(s) missing intrinsic info: {not_found}"
                raise RuntimeError(msg)

        # explicitly check if intrinsic property is filled.
        missing_intrinsic = [cam.name for cam in cameras if cam.intrinsic is None]
        if len(missing_intrinsic) > 0:
            msg = f"Camera(s) missing intrinsic info: {missing_intrinsic}"
            raise RuntimeError(msg)

    def intrinsic_calibration(self, camera_filter: list[str] | None = None) -> None:
        self._check_data_exists(camera_filter)

        self.cameras: list[Camera] = []
        print("\nIntrinsic calibration...")

        for camera_idx in range(self.detection_data.camera_cnt):
            camera_name, detections_of_camera, resolution = self.detection_data.get_camera_data(camera_idx)
            if camera_filter is not None and camera_name not in camera_filter:
                continue
            with contextlib.suppress(InvalidDetectionData):
                camera_obj: Camera = Camera(camera_name)
                camera_with_intrisnics, err = calibrate_intrinsics(
                    camera_obj, detections_of_camera, self.board, resolution
                )
                print(f"{camera_name}     RMS={err:.2f}")
                self.cameras.append(camera_with_intrisnics)

        self.calib_json = compile_json_from_cameras(self.cameras)

    def extrinsic_calibration_bundle_adjust(self) -> None:
        """Calibrates the position of *all* cameras via bundle adjust.

        Raises:
            InvalidDetectionData: DetectionData is not complete.
        """
        self._check_data_exists()
        self._check_intrinsics_exist()
        self.bundle_adjust_system = MutliCalWrapper(self.detection_data, self.board, self.cameras)

        self.calib_json = compile_json_from_cameras(self.cameras, origin_desc=self.bundle_adjust_system.origin)

    def targeted_extrinsic_recalibration(self, selected_cameras: list[str] | str) -> DatasetTriangulation:
        if isinstance(selected_cameras, str):
            selected_cameras = [selected_cameras]
        self._check_data_exists(selected_cameras)
        self._check_intrinsics_exist(selected_cameras)

        # remove extriniscs from requested cameras.
        cameras_to_recalibrated = [cam for cam in self.cameras if cam.name in selected_cameras]
        for cam in cameras_to_recalibrated:
            cam.extrinsic_matrix = None

        triangulation = DatasetTriangulation(self.detection_data, self.cameras, anchor_cnt=5)

        mean_errors = {cam_id: np.mean(errors) for cam_id, errors in triangulation.camera_errors_pixel.items()}
        errors_to_large = {cam_id: error for cam_id, error in mean_errors.items() if error >= 1}
        if len(errors_to_large) > 1:
            msg = f"Pixel error is greater than 1 for one or more cameras: {errors_to_large}"
            raise RuntimeError(msg)

        for cam in cameras_to_recalibrated:
            triangulation.fit_camera(cam)

        self.calib_json = compile_json_from_cameras(self.cameras)
        return triangulation

    def _check_bundle_adjust(self) -> None:
        if self.bundle_adjust_system is None:
            msg = "Bundle Adjust System is empty. Cannot set origin."
            raise RuntimeError(msg)

    def set_origin_board(self, detection_index: int | None = None, *, center_of_cameras_bb: bool = True) -> dict:
        self._check_bundle_adjust()
        self.cameras = self.bundle_adjust_system.set_origin_board(
            detection_index=detection_index, center_of_cameras_bb=center_of_cameras_bb
        )
        self.calib_json = compile_json_from_cameras(self.cameras)
        return self.calib_json

    def set_origin_camera(self, camera_name: str) -> dict:
        self._check_bundle_adjust()
        self.cameras = self.bundle_adjust_system.set_origin_camera(camera_name)
        self.calib_json = compile_json_from_cameras(self.cameras, origin_desc=self.bundle_adjust_system.origin)
        return self.calib_json

    def save_json(self, filepath: str) -> dict:
        if self.calib_json is None:
            msg = "Calib is empty. Please calibrate first."
            raise RuntimeError(msg)
        with Path(filepath).open("w") as outfile:
            json.dump(self.calib_json, outfile, indent=2)
            print("saved local calibration file", filepath)
        return self.calib_json

    def check_accuracy(
        self,
        *,
        error_plot_path: str = "ReprojectionErrors.png",
        cameras_and_boards_plot_path: None | str = None,
        anchor_cnt: int = 3,
    ) -> DatasetTriangulation:
        """
        computes and plots the accuracy of the calibration by comparing re-projecting the detected points.

        Raises:
            MissingCalibrationData if cameras are missing intrincic or extrinsic info
        """
        if self.cameras is None:
            msg = "Missing cameras"
            raise RuntimeError(msg)
        triangulation = DatasetTriangulation(self.detection_data, self.cameras, anchor_cnt=anchor_cnt)
        triangulation.print_errors()
        if error_plot_path:
            triangulation.plot_camera_errors(error_plot_path)
        if cameras_and_boards_plot_path:
            triangulation.plot_3d_points_and_cameras(
                self.detection_data.origin_capture_idx,
                save_path=cameras_and_boards_plot_path,
            )
        return triangulation
