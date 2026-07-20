from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sparrow.calibration_data.camera_parameters import CameraParameters, ImportSettings, get_camera_parameters
from sparrow.modes.handler_exceptions import MalformedCalibrationError, MissingCalibrationError
from sparrow.utils import logger, read_json_file


class CalibrationData:
    def __init__(self) -> None:
        self.camera_parameters: dict[str, CameraParameters] = {}
        self.calib_json: dict
        self.calib_info: dict | None = None
        """  keys: "coordinate_system", "matrix_layout", "timestamp" """

    def __repr__(self) -> str:
        return f"CalibrationData(camera_ids={self.camera_ids}, calib_info={self.calib_info})"
    @property
    def camera_ids(self) -> list[str]:
        return list(self.camera_parameters.keys())

    def get(self, camera_id: str, default: None = None) -> CameraParameters:
        return self.camera_parameters.get(camera_id, default)

    def load(
        self,
        calibration_json: Path | dict,
        camera_ids: list[str] | None,
        rotations: dict,
        import_settings: ImportSettings | None = None,
    ) -> None:
        """
        :returns:
        dict of CameraParameters for all camera_ids (dict[camera_id(str): CameraParameters]),
        unchanged calibration_json (dict),
        calibration info (dict)
        """
        logger.info("Loading camera calibration data")
        if isinstance(calibration_json, Path):
            calibration_json = read_json_file(calibration_json)

        self.calib_json = calibration_json
        self.camera_parameters: dict[str, CameraParameters] = get_camera_parameters(
            self.calib_json, camera_ids, rotations, import_settings
        )
        self.calib_info: dict = get_calibration_info(self.calib_json)

        assert self.camera_parameters is not None, "calib_data should never be none"
        assert not any(
            c_param is None for c_param in self.camera_parameters
        ), "camera_parametes should never be none, even if no calibration was found"
        if camera_ids:
            assert set(camera_ids) == set(
                self.camera_parameters.keys()
            ), "each requested camera_id should have a CameraParameters object, even if it isnt calibrated"

    def save(self, file_path: Path) -> dict[str, CameraParameters]:
        """
        Raises MalformedCalibrationError
        """
        # check if json is valid
        try:
            with Path.open(file_path, "w") as file:
                json.dump(self.calib_json, file, indent=2)
            logger.debug(f"new calibration file has been saved to {file_path}")
        except Exception as e:
            raise MalformedCalibrationError(e) from e

    def get_number_cameras_by_type(self) -> dict[str, int]:
        """
        Counts how many cameras have the same camera_type in the calib_data.
        Returns a dict of shape: {camera_type(str): count(int)}
        """
        counts: dict = {}
        for cam_param in self.camera_parameters.values():
            camera_type = cam_param.camera_type
            counts[camera_type] = counts.get(camera_type, 0) + 1
        return counts

    def check_fully_calibrated(self, camera_ids: list[str] | None = None) -> None:
        if camera_ids is None:
            camera_ids = self.camera_ids
        calibs: list[CameraParameters] = [self.camera_parameters.get(cam_id) for cam_id in camera_ids]
        missing = [calib for calib in calibs if not calib.is_fully_calibrated]
        if missing:
            raise MissingCalibrationError(missing)

    def get_calibration_timestamp(self) -> str:
        if self.calib_info is None:
            return None
        return self.calib_info.get("timestamp")

    def fake_calib(self, height: int, width: int, camera_ids: list[str] | None = None) -> None:
        if camera_ids is None:
            camera_ids = self.camera_ids
        for cam_id in self.camera_ids:
            if cam_id not in self.camera_parameters:
                self.camera_parameters[cam_id] = CameraParameters({"camera_id": cam_id}, 0, 12)
        for cam_id in self.camera_parameters:  # fills missing values with default values
            p: CameraParameters = self.camera_parameters[cam_id]
            p.fake_values(height, width)
            self.camera_parameters[cam_id] = p


def get_calibration_info(calibration_json: dict) -> dict:
    logger.debug(calibration_json.get("meta", "calib has no meta. possibly no calibration data found"))
    if "meta" in calibration_json and isinstance(
        calibration_json["meta"], dict
    ):  # if calibration_dome (raw) has version 3+ meta info
        logger.info("(raw) calibration dome is version 3+")
        return calibration_json["meta"]["calibration"]

    logger.info("(raw) calibration dome is version 2 or less.")
    # older meta info or missing entirely.
    timestamp = iso_format(calibration_json.get("timestamp"))
    coordinate_system = calibration_json.get("meta")
    coordinate_system = "Extrinsics (world-to-camera) use OpenCV coordinate system (x-right, y-down, z-forward into the scene). Origin is the stage center at floor level."
    ret = {"coordinate_system": coordinate_system, "matrix_layout": "row_major", "timestamp": timestamp}
    logger.info(f"calibration info: {ret}")
    return ret


def iso_format(timestamp: str | None) -> str | None:
    if not timestamp:
        return None

    try:
        # check for ISO 8601 format
        dt = datetime.fromisoformat(timestamp)
        # if timezone info exist, original string ist fine and returned.
        if dt.tzinfo is not None:
            return timestamp
    except ValueError:
        try:
            # check for YYYY.MM.DD HH:MM format
            dt = datetime.strptime(timestamp, "%Y.%m.%d %H:%M")  # noqa: DTZ007
        except ValueError:
            # unknown format.
            logger.warning(
                f"calibration file contains unknown timestamp format: {timestamp}. Cannot be converted to iso."
            )
            return timestamp

    # attach berlin timezone
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("Europe/Berlin"))

    return dt.replace(microsecond=0).isoformat()
