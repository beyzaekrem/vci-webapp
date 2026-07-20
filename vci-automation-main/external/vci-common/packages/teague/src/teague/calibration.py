from __future__ import annotations

import json
import logging
import sys
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

try:
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    _HAS_MATPLOTLIB = True
except Exception:
    plt = None  # type: ignore
    Line2D = None  # type: ignore
    _HAS_MATPLOTLIB = False


from teague.util import rotation_to_quaternion

# Module logger
logger = logging.getLogger(__name__)


@dataclass
class LegacyImportSettings:
    """Settings applied on import for older files."""

    c0004_is_origin: bool | str = "auto"
    """Move old calibrations where C0004 was at the origin"""

    up_is_down: bool | str = "auto"
    """Fix for old calibrations where up was pointing downwards."""

    @classmethod
    def as_is(cls) -> LegacyImportSettings:
        """Import settings that do not modify the calibration."""
        return cls(c0004_is_origin=False, up_is_down=False)


@dataclass
class ImportSettings:
    """Settings applied on import."""

    legacy: LegacyImportSettings = field(default_factory=LegacyImportSettings)

    @classmethod
    def as_is(cls) -> ImportSettings:
        """Import settings that do not modify the calibration."""
        return cls(legacy=LegacyImportSettings.as_is())


class CameraCalibration(torch.nn.Module):

    def __init__(
        self,
        config: dict,
        import_settings: ImportSettings = ImportSettings(),
        device: torch.Device | str = "cuda:0",
        dtype: torch.dtype = torch.float,
    ) -> None:
        super().__init__()
        # Type checking
        if not isinstance(config, dict):
            msg = f"Expected config to be dict but got {type(config)}"
            raise ValueError(msg)
        device = torch.device(device)
        # Parse config
        try:
            self.id = config["camera_id"]
            """Descriptive Name or ID."""
            logger.debug("Creating CameraCalibration for id=%s", self.id)
            extrinsics = torch.tensor(config["extrinsics"]["view_matrix"], device=device, dtype=dtype).view(4, 4)
            """World to Camera Projection Matrix [4x4]"""
            intrinsics = torch.tensor(config["intrinsics"]["camera_matrix"], device=device, dtype=dtype).view(3, 3)
            """Intrinsic Matrix [3x3]."""
            self.resolution = config["intrinsics"]["resolution"]
            """Resolution (W,H)."""
            distortion = torch.tensor(config["intrinsics"]["distortion_coefficients"], device=device, dtype=dtype)
            """OpenCV distortion coefficients."""
        except KeyError as e:
            msg = f"Missing key in camera calibration config: {e} ({config})"
            logger.error(msg)
            raise ValueError(msg) from e

        self.register_buffer("extrinsics", extrinsics)
        self.register_buffer("intrinsics", intrinsics)
        self.register_buffer("distortion", distortion)

        if import_settings.legacy.c0004_is_origin:
            transform = torch.tensor(
                [
                    [-0.04879129, 0.88650721, 0.46013540, -1.23611903],
                    [0.99240631, -0.00905192, 0.12267050, -1.52525949],
                    [0.11291330, 0.46262649, -0.87933373, 2.13573623],
                    [0.00000000, 0.00000000, 0.00000000, 1.00000000],
                ],
                device=device,
                dtype=dtype,
            )
            logger.debug("Applying legacy transform because c0004_is_origin=True for camera %s", self.id)
            self.extrinsics = extrinsics @ torch.linalg.inv(transform)

        if import_settings.legacy.up_is_down:
            # Fix old calibrations where up was pointing downwards.
            fix_rot = torch.diag(torch.tensor([1.0, -1.0, -1.0, 1.0], device=device, dtype=dtype))
            logger.debug("Applying legacy up_is_down fix for camera %s", self.id)
            self.extrinsics = self.extrinsics @ fix_rot

    def __repr__(self) -> str:
        return (
            f"CameraCalibration(id={self.id}, "
            f"resolution={self.resolution}, "
            f"intrinsics=\n{self.intrinsics.cpu().numpy()}, "
            f"extrinsics=\n{self.extrinsics.cpu().numpy()})"
        )

    def downsample(self, factor: float = 2) -> Self:
        camera_down = deepcopy(self)
        camera_down.resolution = tuple(x // factor for x in camera_down.resolution)
        true_factor_x = self.resolution[0] / camera_down.resolution[0]
        true_factor_y = self.resolution[1] / camera_down.resolution[1]
        camera_down.intrinsics[0, :] = camera_down.intrinsics[0, :] / true_factor_x
        camera_down.intrinsics[1, :] = camera_down.intrinsics[1, :] / true_factor_y
        return camera_down

    def get_position(self) -> torch.Tensor:
        """Camera Position

        Returns:
            torch.Tensor: 3D Camera position in world space [3,]
        """
        camera_to_world = torch.linalg.inv(self.extrinsics)
        return camera_to_world[:3, 3]

    def get_right(self) -> torch.Tensor:
        """Right Vector

        Returns:
            torch.Tensor: 3D right vector world space [3,]
        """
        return self.extrinsics[0, :3]

    def get_up(self) -> torch.Tensor:
        """Up Vector

        Returns:
            torch.Tensor: 3D up vector world space [3,]
        """
        return -self.extrinsics[1, :3]

    def get_fwd(self) -> torch.Tensor:
        """Forward Vector

        Returns:
            torch.Tensor: 3D forward vector world space [3,]
        """
        return self.extrinsics[2, :3]

    def get_quaternion_world_to_camera(self) -> torch.Tensor:
        """Get world to camera rotation as quaternion (w, x, y, z)

        Returns:
            torch.Tensor: Quaternion [4,]
        """
        return rotation_to_quaternion(self.extrinsics[:3, :3])

    def get_quaternion_camera_to_world(self) -> torch.Tensor:
        """Get camera to world rotation as quaternion (w, x, y, z)

        Returns:
            torch.Tensor: Quaternion [4,]
        """
        return rotation_to_quaternion(self.extrinsics[:3, :3].T)

    def get_full_image_coords(self):
        y, x = torch.meshgrid(
            torch.arange(self.resolution[1], device=self.extrinsics.device),
            torch.arange(self.resolution[0], device=self.extrinsics.device),
            indexing="ij",
        )
        return torch.stack([x, y], dim=-1)  # (H, W, 2)

    def get_ray_samples(
        self,
        pixel_coords: torch.Tensor,
        n: int,
        near: float = 0.1,
        far: float = 100,
        random_jitter: bool = False,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Get sample positions along the ray

        Args:
            n (int): Number of sample points
            pixel_coords (torch.Tensor): Sample positions in image coordinates [..., 2]

        Returns:
            torch.Tensor: 3d coordinates along the rays [..., N, 3]
            torch.Tensor: Depths [..., N, 1]
        """
        device = self.extrinsics.device
        dtype = self.extrinsics.dtype
        shape = pixel_coords.shape[:-1]

        # Intrinsics inverse for back-projection.
        K_inv = torch.linalg.inv(self.intrinsics)

        # Homogeneous pixel coordinates [u, v, 1].
        pixel_coords = pixel_coords.to(device=device, dtype=dtype).view(-1, 2)
        ones = torch.ones_like(pixel_coords[:, :1])
        uv1 = torch.cat([pixel_coords, ones], dim=-1)  # [B, 3]

        # TODO: Add distortion handling

        # Camera-space ray directions (not normalized): dir_cam = K^{-1} [u, v, 1]^T
        dir_cam = (K_inv @ uv1.t()).t()  # [B, 3]

        # Camera-to-world transform.
        cam_to_world = torch.linalg.inv(self.extrinsics)
        R_wc = cam_to_world[:3, :3]  # [3, 3]
        t_wc = cam_to_world[:3, 3]  # [3]

        # World-space ray directions.
        dir_world = (R_wc @ dir_cam.t()).t()  # [B, 3]

        # Depths to sample along the ray (near -> far).
        z = torch.linspace(near, far, n, device=device, dtype=dtype).view(1, n, 1)
        if random_jitter:
            delta = (far - near) / np.clip(n - 1, 1, np.inf)
            z = z + delta * (torch.rand((pixel_coords.shape[0], n, 1), device=device, dtype=dtype) - 0.5)
        else:
            z = z.expand((pixel_coords.shape[0], -1, -1))

        # Sample points: X(z) = t_wc + z * dir_world
        points = t_wc.view(1, 1, 3) + z * dir_world.view(-1, 1, 3)  # [B, N, 3]
        return points.view(*shape, n, 3), z.view(*shape, n, 1)


class Calibration(torch.nn.Module):

    def __init__(
        self,
        calibration: str | Path | dict,
        load_color: bool = True,
        load_mono: bool = False,
        load_depth: bool = False,
        import_settings: ImportSettings = ImportSettings(),
        device: torch.Device | str = "cuda:0",
        dtype: torch.dtype = torch.float,
    ) -> None:
        super().__init__()
        self.device = torch.device(device)
        self.dtype = dtype
        logger.debug("Initializing Calibration with device=%s dtype=%s", self.device, self.dtype)
        if isinstance(calibration, (str, Path)):
            calibration = Path(calibration)
            logger.debug("Loading calibration from path: %s", str(calibration))
            if calibration.is_dir():
                calibration = calibration / "calibration_dome.json"
            with calibration.open() as fp:
                calibration = json.load(fp)
        elif not isinstance(calibration, dict):
            msg = f"Expected calibration to be dict, str or Path but got {type(calibration)}"
            raise ValueError(msg)
        self.cameras: dict[str, CameraCalibration] = torch.nn.ModuleDict()
        self.import_settings = import_settings
        self._check_import_settings(calibration)
        for camera_config in calibration["cameras"]:
            if camera_config["camera_id"][0] == "C":
                if load_color is False:
                    continue
            elif camera_config["camera_id"][0] == "M":
                if load_mono is False:
                    continue
            elif camera_config["camera_id"][0] == "D":
                if load_depth is False:
                    continue
            else:
                msg = f"Unexpected camera id: {camera_config['camera_id']}"
                raise ValueError(msg)
            try:
                self.cameras[camera_config["camera_id"]] = CameraCalibration(
                    camera_config, import_settings, self.device, self.dtype
                )
            except ValueError as e:
                logger.warning("Loading camera %s failed: %s", camera_config["camera_id"], e)

    def _check_import_settings(self, calibration: dict) -> None:
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
            self.import_settings.legacy = LegacyImportSettings.as_is()
            return
        # Apply legacy import settings
        if self.import_settings.legacy.c0004_is_origin == "auto":
            camera_config_c0004 = next((cam for cam in calibration["cameras"] if cam["camera_id"] == "C0004"), None)
            if camera_config_c0004 is not None:
                logger.debug("Found C0004 in calibration; testing if at origin")
                c0004_calibration = CameraCalibration(
                    camera_config_c0004, ImportSettings.as_is(), self.device, self.dtype
                )
                pos_norm = float(c0004_calibration.get_position().norm())
                logger.debug("C0004 position norm = %s", pos_norm)
                if pos_norm < 1e-3:
                    self.import_settings.legacy.c0004_is_origin = True
                    logger.info("Detected legacy calibration: C0004 at origin -> setting c0004_is_origin=True")
                else:
                    self.import_settings.legacy.c0004_is_origin = False
                    logger.info("C0004 not at origin (norm=%s) -> setting c0004_is_origin=False", pos_norm)
            else:
                self.import_settings.legacy.c0004_is_origin = False
                logger.debug("C0004 not found in calibration; c0004_is_origin set to False")
        if self.import_settings.legacy.up_is_down == "auto":
            if self.import_settings.legacy.c0004_is_origin:
                # If C0004 is used as origin, we assume up is correct unless explicitly flagged otherwise
                self.import_settings.legacy.up_is_down = False
                logger.debug("c0004_is_origin=True so up_is_down set to False")
            else:
                logger.debug("Auto-detecting up direction from camera positions")
                cameras = [
                    CameraCalibration(cam, ImportSettings.as_is(), self.device, self.dtype)
                    for cam in calibration["cameras"]
                ]
                positions = torch.stack([cam.get_position() for cam in cameras], dim=0)
                center = positions.mean(dim=0)
                logger.debug("Computed camera center = %s", center.cpu().numpy())
                # If the mean Y is negative we assume up was inverted in legacy files
                if center[1] > 0:
                    self.import_settings.legacy.up_is_down = True
                    logger.info("Detected legacy calibration: average camera Y > 0 -> setting up_is_down=True")
                else:
                    self.import_settings.legacy.up_is_down = False
                    logger.info("Average camera Y <= 0 -> setting up_is_down=False")

    def get_bbox(self) -> torch.Tensor:
        """Bounding Box containing all cameras

        Returns:
            torch.Tensor: BBox limits min/max [2,3]
        """
        pos = torch.stack([camera.get_position() for camera in self.cameras])
        return torch.stack((pos.min(dim=0)[0], pos.max(dim=0)[0]))

    def plot_3d(self, arrow_length: float = 0.5, label_size: int = 10) -> plt.Figure:
        # Ensure matplotlib is available at runtime
        if not _HAS_MATPLOTLIB:
            raise RuntimeError(
                "matplotlib is required for Recording.plot_3d but it is not installed. "
                "Install matplotlib or import this module only when plotting is needed."
            )

        # Gather camera info
        pos = []
        fwd = []
        up = []
        right = []
        labels = []
        for camera in self.cameras:
            pos.append(camera.get_position())
            fwd.append(camera.get_fwd())
            up.append(camera.get_up())
            right.append(camera.get_right())
            labels.append(camera.id)
        pos = torch.stack(pos, 0).detach().cpu().numpy()
        fwd = torch.stack(fwd, 0).detach().cpu().numpy()
        up = torch.stack(up, 0).detach().cpu().numpy()
        right = torch.stack(right, 0).detach().cpu().numpy()

        figure = plt.figure()
        ax = figure.add_subplot(111, projection="3d")

        # Unpack X, Y, Z from positions
        x, y, z = pos[:, 0], pos[:, 1], pos[:, 2]

        # Scatter plot
        ax.scatter(x, y, z)
        u, v, w = fwd[:, 0], fwd[:, 1], fwd[:, 2]
        ax.quiver(x, y, z, u, v, w, length=arrow_length, normalize=True, color="red")
        u, v, w = up[:, 0], up[:, 1], up[:, 2]
        ax.quiver(x, y, z, u, v, w, length=arrow_length, normalize=True, color="green")
        u, v, w = right[:, 0], right[:, 1], right[:, 2]
        ax.quiver(x, y, z, u, v, w, length=arrow_length, normalize=True, color="blue")

        if label_size > 0:
            for i in range(pos.shape[0]):
                ax.text(x[i], y[i], z[i], labels[i], size=label_size, zorder=1, color="black")

        # Scaling
        mins = pos.min(axis=0)
        maxs = pos.max(axis=0)
        center = (mins + maxs) / 2.0
        half_sizes = (maxs - mins) / 2.0
        radius = half_sizes.max() + arrow_length
        ax.set_xlim(center[0] - radius, center[0] + radius)
        ax.set_ylim(center[1] - radius, center[1] + radius)
        ax.set_zlim(center[2] - radius, center[2] + radius)
        ax.set_box_aspect([1, 1, 1])  # keep the box cubic too

        # Axis labels
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")
        ax.set_box_aspect([1, 1, 1])

        # Legend for quivers
        legend_elements = [
            Line2D([0], [0], color="red", lw=2, label="Forward"),
            Line2D([0], [0], color="green", lw=2, label="Up"),
            Line2D([0], [0], color="blue", lw=2, label="Right"),
        ]
        ax.legend(handles=legend_elements, loc="upper right")

        plt.tight_layout()
        return figure, ax
