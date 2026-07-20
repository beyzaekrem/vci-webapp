from __future__ import annotations

import copy
from dataclasses import dataclass, field

import numpy as np
import torch
from pyquaternion import Quaternion

import sparrow.calibration_data.calibration_math as calib_math
import sparrow.gibbs_wrapper as gibbs
from sparrow.modes.handler_exceptions import MalformedCalibrationError, MissingCalibrationError
from sparrow.utils import logger

default_device = "cuda:0" if torch.cuda.is_available() else "cpu"


@dataclass
class LegacyImportSettings:
    """Settings applied on import for older files."""

    c0004_is_origin: bool | str = "auto"
    """Move old calibrations where C0004 was at the origin"""

    up_is_down: bool | str = "auto"
    """Fix for old calibrations where up was pointing downwards."""

    correct_rotation: bool | str = True
    """Fix for calibrations performed on rotated images"""

    @classmethod
    def as_is(cls) -> LegacyImportSettings:
        """Import settings that do not modify the calibration."""
        return cls(c0004_is_origin=False, up_is_down=False, correct_rotation=False)


@dataclass
class ImportSettings:
    """Settings applied on import."""

    legacy: LegacyImportSettings = field(default_factory=LegacyImportSettings)

    @classmethod
    def as_is(cls) -> ImportSettings:
        """Import settings that do not modify the calibration."""
        return cls(legacy=LegacyImportSettings.as_is())


@dataclass
class CameraParameters:
    """
    Assortment of parameters for a camera.
    """

    camera_matrix: torch.tensor | None = None  # intrinsic, camera_matrix
    """
    Intrinsic camera parameters: [fx, 0, cx, 0, fy, cy, 0, 0, 1].

    Composed of the focal lengths fx and fy and the pricipal point cx and cy.
    Both are expressed in pixel units and are therefore dependant on resolution.
    This matrix describes how 3D points in the camera cooridnate system are projected onto the 2D image plane.
    Can be reshaped to a 3x3 matrix.
        |fx,  0, cx|
        | 0, fy, cy|
        | 0,  0,  1|
    """

    distortion_coefficients: torch.tensor | None = None
    """
    Describes radial (k) and tangential distortion (p) of the image: [k1, k2, p1, p2, k3].
    """

    resolution_tensor: torch.tensor | None = None
    """
    The pixel-resolution of the captured image [w, h]
    """
    resolution: np.array | None = None
    """
    The pixel-resolution of the captured image [w, h]. As numpy array
    """

    view_matrix: np.array | None = None
    """
    Pose of the camera expressed as a 4x4 matrix (flattened) in opencv style.

        z (forward into the scene, away from viewer)
      /
     /______ x (right)
     |
     |
     | y (down)


    The matrix is composed of rotation (rot) and translation(t)
     |rot 3x3 ,  t 3x1|
     | 0      ,  1    |
     The translation expresses the camera's position in the camera's coordinate frame.
     Use fuction world_pos() to get the actual world positon.
    """

    rotation: int = None
    """
    The rotation indicates how and if the captured image needs to be rotated for the subject to appear upright.
    Rotation is applied in 90 degree steps.

    -1 = 90 degree rotation to the right|
    1 = 90 degree rottation to the left|
    0 = no rotation
    """

    white_balance_coefficients: torch.tensor | None = None
    """
    Balance coefficents [r, g, b] applied to color channels to neutralize color casts,
    ensuring that white objects appear white.
    Normalized, so the smalles coefficient is 1.0
    """

    color_correction_matrix: torch.tensor = None
    """
    3x3 Matrix to correct color crosstalk between channels. Ensures accurate color reproduktion.
    """

    camera_id: str = ""
    """
    unique camera_id, e.g C0001 or M0001
    """

    colorspace: str = ""

    @property
    def is_fully_calibrated(self) -> bool:
        values = [self.camera_matrix, self.rotation, self.distortion_coefficients, self.resolution_tensor]
        if self.camera_type == gibbs.ImageType.Color:
            values.extend([self.white_balance_coefficients, self.color_correction_matrix])
        return not any(val is None for val in values)

    @property
    def camera_type(self) -> gibbs.ImageType:
        match self.camera_id[0]:
            case "C":
                return gibbs.ImageType.Color
            case "M":
                return gibbs.ImageType.Mono
            case "D":
                return gibbs.ImageType.Depth
            case _:
                return gibbs.ImageType.Undefined

    @property
    def is_color(self) -> bool:
        return self.camera_type == gibbs.ImageType.Color

    def __init__(self, calib: dict, rotation: int, import_settings: ImportSettings = None) -> None:
        self.camera_id = calib.get("camera_id")
        if self.camera_id is None:
            msg = "CameraParameter cannot be initialized without 'camera_id' key."
            raise KeyError(msg)

        self.rotation = rotation  # is the automatic rotation to have pretty image

        intrinsics = calib.get("intrinsics", {})

        self.white_balance_coefficients: torch.tensor = self._get_tensor_from_dict(
            "white_balance_coefficients", intrinsics
        )
        self.color_correction_matrix: torch.tensor = self._get_tensor_from_dict("color_correction_matrix", intrinsics)
        self.colorspace: str = intrinsics.get("colorspace", "linear")

        self.camera_matrix: torch.tensor = self._get_tensor_from_dict("camera_matrix", intrinsics)
        self.distortion_coefficients: torch.tensor = self._get_tensor_from_dict("distortion_coefficients", intrinsics)

        self.resolution_tensor: torch.tensor = self._get_tensor_from_dict("resolution", intrinsics, dtype=torch.int)
        self.resolution = intrinsics.get("resolution")  # w, h # numpy resolution
        if self.resolution is not None:
            self.resolution = np.array(self.resolution)

        self.view_matrix = calib.get("extrinsics", {}).get("view_matrix")  # view matrix is numpy
        if self.view_matrix is not None:
            self.view_matrix = np.array(self.view_matrix)
            try:
                self.rotation_quat()  # raises error if view_matrix is invalid
            except MissingCalibrationError:
                pass
            except ValueError as e:
                msg = f"Error: {e}"
                raise MalformedCalibrationError(msg) from e

        self._calibration_rotation = 0

        if import_settings is None:
            import_settings = ImportSettings()
            import_settings.as_is()

        if import_settings.legacy.correct_rotation and self.resolution is not None:
            if (
                self.resolution[0] < self.resolution[1]
            ):  # portrait mode [4608, 5328]. calibrated on rotated images. we dont want that anymore
                logger.debug(f"     {self.camera_id} calibration deprecated: done on rotated images. Undoing rotation")
                self.rotate_calibration(calibration_rotation=self.rotation, desired_rotation=0)
            else:
                pass  # is in landscape mode, aka calibrated on un-rotated images.

        if import_settings.legacy.c0004_is_origin and self.view_matrix is not None:
            # move to set origin to center of stage
            transform = np.array(
                [
                    [-0.04879129, 0.88650721, 0.46013540, -1.23611903],
                    [0.99240631, -0.00905192, 0.12267050, -1.52525949],
                    [0.11291330, 0.46262649, -0.87933373, 2.13573623],
                    [0.00000000, 0.00000000, 0.00000000, 1.00000000],
                ]
            )
            transform = calib_math.polar_reorthogonalize(transform, error=1e-5)
            logger.debug("Applying legacy transform because c0004_is_origin=True for camera %s", self.camera_id)
            view_matrix = self.view_matrix.reshape([4, 4]) @ np.linalg.inv(transform)
            self.view_matrix = view_matrix.flatten()

        if import_settings.legacy.up_is_down and self.view_matrix is not None:
            # Fix old calibrations where up was pointing downwards.
            fix_rot = np.diag([1.0, -1.0, -1.0, 1.0])
            logger.debug("Applying legacy up_is_down fix for camera %s", self.camera_id)
            self.view_matrix = self.view_matrix.reshape([4, 4]) @ fix_rot
            self.view_matrix = self.view_matrix.flatten()

    def get_shape(
        self, scale: float, channels: int | None = None, rotation: int | None = None, *, no_rotation: bool = False
    ) -> np.array:
        if channels is None:
            channels = 3 if self.is_color else None
        resolution = self.get_resolution_rotated(rotation, no_rotation=no_rotation)  # w,h
        if resolution is None:
            return None
        resolution = resolution * scale
        shape: np.array = resolution[::-1]  # h, w
        if channels is not None:
            shape: np.array = np.insert(shape, 0, channels)
        return shape.astype(int)

    def get_resolution_rotated(self, rotation: int | None = None, *, no_rotation: bool = False) -> np.array:
        if no_rotation:
            return self.resolution
        if rotation is None:
            rotation = self.rotation
        if rotation is not None and rotation % 2 == 1:
            return self.resolution[::-1]
        return self.resolution

    @staticmethod
    def _get_tensor_from_dict(key: str, data: dict, dtype: torch.dtype = torch.float) -> torch.tensor | None:
        if data is None:
            return None
        if key in data:
            return torch.tensor(data.get(key)).to(dtype).to(default_device)
        return None

    def to_dict(self) -> dict[str, any]:
        """
        Generates and returns a dict form this CameraParameters object.
        """
        ret = {"camera_id": self.camera_id, "camera_type": self.camera_type.name, "colorspace": self.colorspace}
        if self.view_matrix is not None:
            ret["extrinsics"] = {"view_matrix": self.view_matrix.tolist()}

        pairs: dict[str : torch.tensor] = {
            "camera_matrix": self.camera_matrix,
            "color_correction_matrix": self.color_correction_matrix,
            "distortion_coefficients": self.distortion_coefficients,
            "resolution": self.resolution_tensor,
            "white_balance_coefficients": self.white_balance_coefficients,
        }

        for key, value in pairs.items():
            if value is not None:
                if "intrinsics" not in ret:
                    ret["intrinsics"] = {}
                ret["intrinsics"][key] = value.cpu().flatten().tolist()

        return ret

    def get_parameter(
        self, param_name: str, overwrite_params: dict | None = None
    ) -> torch.tensor | np.array | list | None:
        """
        Returns a paramter by name. If the parameter exists in overwrite_params, returns that value instead.

        Raises:
            ValueError: the parmeter is missing
        """
        if overwrite_params is not None and param_name in overwrite_params:
            return overwrite_params[param_name]
        value = getattr(self, param_name, None)
        if value is None:
            msg = f"{self.camera_id} is missing parameter {param_name}"
            raise ValueError(msg)
        return value

    def get_tensor_with_fallback(
        self,
        param_name: str,
        overwrite_params: dict | None = None,
        device: torch.DeviceObjType = default_device,
        dtype: torch.dtype = torch.float,
    ) -> torch.tensor:
        """
        Returns a tensor parameter by name. If the parameter exists in overwrite_params,
        uses the values from there. Value is converted to tensor if it is not already a tensor.

        Raises:
            ValueError: The parameter doesn't exist
        """
        value = self.get_parameter(param_name, overwrite_params=overwrite_params)
        if not isinstance(value, torch.Tensor):
            value = torch.tensor(value, device=device, dtype=dtype)
        return value

    def get_parameter_as_list(self, param_name: str, overwrite_params: dict | None = None) -> list:
        """
        Returns a parameter by name as list object.
        If the paraemter exists in overwrite_params, uses the value from there.
        Value is converted to list if it is not already a list.
        """
        value: list | np.array | torch.Tensor = self.get_parameter(param_name, overwrite_params=overwrite_params)
        if isinstance(value, torch.Tensor):
            value = value.detach().cpu().flatten()
        if not isinstance(value, list):
            value = value.tolist()
        return value

    def __deepcopy__(self, memo) -> None:  # noqa: ANN001
        # Deep copy: creates a new object with copies of all attributes.
        cls = self.__class__
        new_instance = cls.__new__(cls)
        memo[id(self)] = new_instance
        for k, v in self.__dict__.items():
            new_instance.__dict__[k] = copy.deepcopy(v, memo)
        return new_instance

    def inherit_from(self, other: CameraParameters) -> None:
        """copies all parameters that are not None from the given CameraParameters object"""
        for field_name in self.__dataclass_fields__:
            if getattr(self, field_name) is None:
                setattr(self, field_name, getattr(other, field_name))

    def fake_values(self, height: float, width: float) -> None:
        c = {
            "camera_id": self.camera_id,
            "extrinsics":{
                "view_matrix": [
                    0.057500867569550314,
                    -0.9886522523685922,
                    0.13878174993586131,
                    -1.2723332444551951,
                    -0.9262448623995112,
                    -0.0009610157980932456,
                    0.37692112082920975,
                    0.035315495353038906,
                    -0.37251054361891683,
                    -0.15021917432587198,
                    -0.9157893286982511,
                    2.3572641771183953,
                    0.0,
                    0.0,
                    0.0,
                    1.0
                ]
            },
            "intrinsics": {
                "white_balance_coefficients": [2.3, 1.0, 1.50], #counters green color cast
                "color_correction_matrix": [
                    1.5744372074117523,
                    -0.3955642740775688,
                    -0.23034596787732894,
                    -0.5072192234835426,
                    1.9112154436338813,
                    -0.4186725657627202,
                    0.07756119622947827,
                    -0.6622262831588901,
                    1.603917606224097,
                ],
                "distortion_coefficients": [
                    -0.13852933850808535,
                    0.14813368676567032,
                    -0.00013188321898637858,
                    -0.00029014883322859815,
                    -0.04037557351872751,
                ],
                "camera_matrix": [
                    min(height, width) - 100,
                    0.0,
                    width / 2.0,
                    0.0,
                    min(height, width) - 100,
                    height / 2.0,
                    0.0,
                    0.0,
                    1.0,
                ],
                "resolution": [width, height],
            },
        }
        fake = CameraParameters(c, rotation=0)
        self.inherit_from(fake)

    def rotate_calibration(self, calibration_rotation: int | None = None, desired_rotation: int | None = None) -> None:
        """
        virutally rotates the camera. calibration_rotation is the assumed is-rotation. desired_rotation is
        the roatation you would like to get.
        Updates: resolution, camera_matrix and view_matrix in place.
        """
        if calibration_rotation is not None:  # user re-defines which rotation the calibration has.
            self._calibration_rotation = calibration_rotation  # for example set to 0 for un-roated calibrations

        if desired_rotation is None:
            desired_rotation = self.rotation

        diff = desired_rotation - self._calibration_rotation
        # Normalize diff to range [-1, 2]
        # This lets us handle jumps like -1 to 1 (diff = 2)
        # or 1 to -1 (diff = -2, which we can treat as 2 steps)
        steps = ((diff + 2) % 4) - 2
        if steps == 0:
            logger.debug(
                "    no rotation nessesary.. "
                f"Calibration_rotation: {self._calibration_rotation} -> desired {desired_rotation}"
            )
            return

        logger.debug(f"   Rotating: {self._calibration_rotation} -> {desired_rotation} ({steps} steps)")

        # Move in the required direction
        direction = 1 if steps > 0 else -1
        for _ in range(abs(steps)):
            self._apply_90_step(direction=direction)
        self._calibration_rotation = desired_rotation

    def _apply_90_step(self, direction: int) -> None:
        """
        direction = 1  : 90° CCW (Left)
        direction = -1 : 90° CW (Right)

        rot90 rotates counterclockwise by k*90 degrees, where k is an integer.
        """
        logger.debug(f"      {self.camera_id} calibration rot90: {direction}")
        w, h = self.resolution_tensor[0], self.resolution_tensor[1]
        new_k = self.camera_matrix.clone()

        fx, fy = self.camera_matrix[0], self.camera_matrix[4]
        cx, cy = self.camera_matrix[2], self.camera_matrix[5]

        # Create the extrinsic rotation matrix (around Z-axis)
        r_img = np.eye(4, dtype=np.float64)

        if direction == 1:  # CCW (Left)
            # Intrinsics
            new_k[0], new_k[4] = (
                fy,
                fx,
            )  # flip fy an fx

            new_k[2] = cy
            new_k[5] = w - cx

            # Distortion (p1, p2) -> (-p2, p1)
            if self.distortion_coefficients.numel() >= 4:  # noqa: PLR2004
                p1, p2 = self.distortion_coefficients[2].clone(), self.distortion_coefficients[3].clone()
                self.distortion_coefficients[2], self.distortion_coefficients[3] = -p2, p1

            # Extrinsics: X_new = Y_old, Y_new = -X_old
            r_img[0, 0], r_img[0, 1] = 0, 1
            r_img[1, 0], r_img[1, 1] = -1, 0
        else:  # CW (Right)
            # Intrinsics
            new_k[0], new_k[4] = fy, fx
            new_k[2] = h - cy
            new_k[5] = cx
            # Distortion (p1, p2) -> (p2, -p1)
            if self.distortion_coefficients.numel() >= 4:  # noqa: PLR2004
                p1, p2 = self.distortion_coefficients[2].clone(), self.distortion_coefficients[3].clone()
                self.distortion_coefficients[2], self.distortion_coefficients[3] = p2, -p1

            # Extrinsics: X_new = -Y_old, Y_new = X_old
            r_img[0, 0], r_img[0, 1] = 0, -1
            r_img[1, 0], r_img[1, 1] = 1, 0

        self.camera_matrix = new_k
        self.view_matrix = r_img @ self.view_matrix.reshape([4, 4])
        self.view_matrix = self.view_matrix.flatten()

        self.resolution_tensor = torch.stack([h, w])
        self.resolution = self.resolution[::-1]

    def world_pos(self) -> np.ndarray | None:
        """returns the world position of the camera"""
        if self.view_matrix is None:
            return None
        return calib_math.get_world_pos(self.view_matrix)

    def rotation_quat(self) -> Quaternion | None:
        """returns the rotation of the camera as quaternion"""
        if self.view_matrix is None:
            raise MissingCalibrationError(self.camera_id)
        view_matrix: np.ndarray = self.view_matrix
        extrinsic_matrix = view_matrix.reshape((4, 4))
        rot = extrinsic_matrix[:3, :3]
        q = Quaternion(matrix=rot)
        return Quaternion(-q.w, q.x, q.y, q.z)


def get_camera_parameters(
    calibration_json: dict,
    requested_camera_ids: list[str] | None = None,
    rotations: dict[str:int] | None = None,
    import_settings: ImportSettings | None = None,
) -> dict[str, CameraParameters]:
    """
    Converts a calibration_data dict read from json to a dict of shape: {camera_id (str): parameters (CameraParameters)}
    If filter_by_camera_ids is not None, returns all cameras available in the calib_data.
    When filter_by_camera_ids is speficied, a CameraParamter will be returned for exactly those camera_ids.
    If the camera_id does not exist in calib_data, the respective CameraParameter has None values.

    Returns: CameraParameters dict, coordinate_system (str) and timestamp (str) entry.
    """
    if rotations is None:
        rotations = {}
    if calibration_json is None:
        calibration_json = {"cameras": []}

    if import_settings is None:
        import_settings = ImportSettings()
    _check_import_settings(calibration_json, import_settings)

    calib_entries: dict[str, dict] = {entry["camera_id"]: entry for entry in calibration_json["cameras"]}

    if requested_camera_ids is not None:
        selected_camera_ids = requested_camera_ids
    else:
        # load all available data.
        selected_camera_ids: list[str] = list(calib_entries.keys())  # from calibraiton_json
        selected_camera_ids.extend(list(rotations.keys()))  # and rotations file
        selected_camera_ids = list(set(selected_camera_ids))

    camera_calib: dict = {}
    for cam_id in selected_camera_ids:
        calib_entry: dict = calib_entries.get(cam_id, {"camera_id": cam_id})
        rot90: int | None = rotations.get(cam_id)
        camera_calib[cam_id] = CameraParameters(calib_entry, rot90, import_settings=import_settings)
    for entry in calibration_json["cameras"]:
        cam_id = entry["camera_id"]

    if requested_camera_ids is not None and sorted(camera_calib.keys()) != sorted(requested_camera_ids):
        msg = "Every requested camera_id should have a CameraParameters entry in the camera_calib."
        " Even if the are not present in the calib_data input"
        raise ValueError(msg)

    return camera_calib


def _check_import_settings(calibration: dict, import_settings: ImportSettings) -> None:
    # Check if new format and return
    if "meta" in calibration and "version" in calibration["meta"]:
        logger.debug("New format detected")
        is_new_format = True
    else:
        logger.debug("Old format detected")
        is_new_format = False
    logger.debug("treating new format as old")
    is_new_format = False
    if is_new_format:
        import_settings.legacy = LegacyImportSettings.as_is()
        return
    # Apply legacy import settings
    if import_settings.legacy.c0004_is_origin == "auto":
        camera_config_c0004 = next((cam for cam in calibration["cameras"] if cam["camera_id"] == "C0004"), None)
        if camera_config_c0004 is not None:
            logger.debug("Found C0004 in calibration; testing if at origin")
            c0004_calibration = CameraParameters(camera_config_c0004, 0, ImportSettings.as_is())
            pos_norm = float(np.linalg.norm(c0004_calibration.world_pos()))
            logger.debug("C0004 position norm = %s", pos_norm)
            if pos_norm < 1e-3:  # noqa: PLR2004
                import_settings.legacy.c0004_is_origin = True
                logger.info("Detected legacy calibration: C0004 at origin -> setting c0004_is_origin=True")
            else:
                import_settings.legacy.c0004_is_origin = False
                logger.info("C0004 not at origin (norm=%s) -> setting c0004_is_origin=False", pos_norm)
        else:
            import_settings.legacy.c0004_is_origin = False
            logger.debug("C0004 not found in calibration; c0004_is_origin set to False")
    if import_settings.legacy.up_is_down == "auto":
        if import_settings.legacy.c0004_is_origin:
            # If C0004 is used as origin, we assume up is correct unless explicitly flagged otherwise
            import_settings.legacy.up_is_down = False
            logger.debug("c0004_is_origin=True so up_is_down set to False")
        else:
            logger.debug("Auto-detecting up direction from camera positions")
            cameras: list[CameraParameters] = [
                CameraParameters(cam, 0, ImportSettings.as_is()) for cam in calibration["cameras"]
            ]
            cameras = [c for c in cameras if c.view_matrix is not None]
            if len(cameras) != 0:
                positions = np.stack([cam.world_pos() for cam in cameras], axis=0)
                center = positions.mean(axis=0)
                logger.debug("Computed camera center = %s", center)
                # If the mean Y is negative we assume up was inverted in legacy files
                if center[1] > 0:
                    import_settings.legacy.up_is_down = True
                    logger.info("Detected legacy calibration: average camera Y > 0 -> setting up_is_down=True")
                else:
                    import_settings.legacy.up_is_down = False
                    logger.info("Average camera Y <= 0 -> setting up_is_down=False")
            else:
                # there are not view_matrices calibrated so it doesnt matter anyway.
                import_settings.legacy.up_is_down = False


EMPTY_CAMERA_PARAMETERS = CameraParameters({"camera_id": "EMPTY"}, None, None)
