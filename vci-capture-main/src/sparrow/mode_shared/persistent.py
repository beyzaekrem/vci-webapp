from __future__ import annotations

import json
from pathlib import Path

import sparrow.gibbs_wrapper as gibbs
from sparrow.calibration_data import CalibrationData
from sparrow.calibration_data.background_images import BackgroundImages
from sparrow.utils import logger, read_json_file

from .persistent_paths import PERSISTENT_PATHS


class PersistentData:

    def __init__(self) -> None:
        self._camera_ids: list[str] = []
        self.backgrounds = BackgroundImages()
        self.calibration_data = CalibrationData()

    @property
    def camera_rotations(self) -> dict[str, int]:
        """
        The rotation settings of all cameras as dict of shape:
        {camera_id (str): rotation (int)}

        The rotation indicates how and if the captured image needs to be rotated for the subject to be upright.
        Rotation is applied in 90 degree steps.

        -1 = 90 degree rotation to the right|
        1 = 90 degree rottation to the left|
        0 = no rotation
        """
        return read_json_file(PERSISTENT_PATHS.rotation_file_path)

    def load(self, camera_ids: list[str]) -> None:
        """
        Loads the calibration_data (camera_matrix, distoriton_coefficients, ...),
        camera rotation and (raw) background images for the given camera_ids.
        If a camera is missing their info, the resulting CameraParameter entry in calib_data will contain None values.

        The data is loaded from the "live" version.
        calibration_dome.json, camera_rotations.json and persistent/background_raw_camera_id.pth
        """
        self.calibration_data.load(PERSISTENT_PATHS.calibration_file_path, camera_ids, self.camera_rotations)
        self.backgrounds.load(camera_ids, str(PERSISTENT_PATHS.background_images_path_pattern))
        self._camera_ids = camera_ids

    def save_calibration_json(self, new_calibration_json: dict) -> None:
        """
        Saves a given calibration_json as the new "live" data to file.
        Then re-loads with the data.

        Raises MalformedCalibrationError
        """
        self.calibration_data.load(new_calibration_json, self._camera_ids, self.camera_rotations)
        self.calibration_data.save(PERSISTENT_PATHS.calibration_file_path)
        self.load(self._camera_ids)

    def save_camera_rotations(self, new_camera_rotations: dict) -> None:
        """
        Saves a given camera_rotation dict as the new "live" data to file.
        Then re-loads with the new data.
        """
        logger.info("PERSISTENT save camera rotations.")
        with Path.open(self.rotation_file_path, "w") as file:
            json.dump(new_camera_rotations, file, indent=2)
        self.load(self._camera_ids)

    def save_background_images(
        self, raw_background_images: list[gibbs.GibbsImage] | dict[str, gibbs.GibbsImage]
    ) -> None:
        """
        Saves the given raw background images as the new "live" data to files.
        Resets the processed background cache.
        """
        logger.info(f"PERSISTENT save background images for {self._camera_ids}")
        self.backgrounds.set_background_images(raw_background_images)
        self.backgrounds.save(str(PERSISTENT_PATHS.background_images_path_pattern))

    def get_background_images(self, processing_steps: dict[str : list[dict]]) -> dict[str, gibbs.GibbsImage]:
        """
        Returns the background images processed with the requested steps.
        The backgrounds are cached. Requesting the same steps again, returns the background from cache.
        """
        return self.backgrounds.get_background_images(
            processing_steps=processing_steps, calib_data=self.calibration_data
        )


PERSISTENT_DATA = PersistentData()
