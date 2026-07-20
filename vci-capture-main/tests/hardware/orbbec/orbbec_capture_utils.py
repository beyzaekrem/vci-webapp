from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

from sparrow.calibration_data.calibration_data import CameraParameters
from sparrow.image_processing.process_images import process_images
from sparrow.mode_shared import camera_manager

logger = logging.getLogger(__name__)

# Constants describing accepted channel layouts for the processed images. We
# accept either channel-first (C, H, W) or channel-last (H, W, C) arrays and
# convert as needed before saving to disk.
SINGLE_CHANNEL = 1
RGB_CHANNELS = 3
RGBA_CHANNELS = 4
CHANNEL_FIRST_VALID = (SINGLE_CHANNEL, RGB_CHANNELS, RGBA_CHANNELS)
CHANNEL_LAST_VALID = (RGB_CHANNELS, RGBA_CHANNELS)


def list_cameras() -> None:
    """Log a summary of connected cameras using the shared camera manager."""

    camera_ids, cameras = camera_manager.CAMERA_MANAGER.get_camera_ids_without_opening_cameras()
    logger.info("Camera IDs: %s", camera_ids)
    logger.info("Total cameras: %d", len(cameras))
    logger.info("Summary:")

    for cam_id, cam in zip(camera_ids, cameras):
        logger.info(
            "  %s: type=%s, serial=%s, manufacturer=%s",
            cam_id,
            cam.camera_type.name,
            cam.info().serialnumber,
            cam.info().manufacturer,
        )


def _ensure_channel_last(array: np.ndarray) -> np.ndarray:
    """Ensure tensors are channel-last (H, W, C) before writing PNGs."""

    if array.ndim == 3 and array.shape[0] in CHANNEL_FIRST_VALID:  # noqa: PLR2004
        # Move the channel axis to the end for OpenCV compatibility.
        return np.moveaxis(array, 0, -1)
    return array


def _to_png_image(array: np.ndarray) -> np.ndarray:
    """Convert normalized or high bit-depth arrays into uint8 RGB/gray PNGs."""

    if array.dtype == np.uint8:
        # Collapse single-channel arrays to 2D so OpenCV writes a grayscale PNG.
        if array.ndim == 3 and array.shape[2] == SINGLE_CHANNEL:  # noqa: PLR2004
            return array[:, :, 0]
        return array

    # Normalize floating point / high-range arrays into 0-255.
    arr = array.astype(np.float32, copy=False)
    arr = np.clip(arr, 0.0, 1.0)
    arr = (arr * 255.0).astype(np.uint8)

    if arr.ndim == 3 and arr.shape[2] == SINGLE_CHANNEL:  # noqa: PLR2004
        # Keep grayscale images single-channel.
        return arr[:, :, 0]
    if arr.ndim == 3 and arr.shape[2] >= RGB_CHANNELS:  # noqa: PLR2004
        # Drop alpha if present; PNG writer handles 3-channel RGB.
        return arr[..., :RGB_CHANNELS]
    if arr.ndim == 2:  # noqa: PLR2004
        return arr
    # Fallback: create a black RGB image if dimensions are unexpected.
    return np.zeros((*arr.shape[:2], RGB_CHANNELS), dtype=np.uint8)


def warmup_cameras(camera_ids: list[str], iterations: int = 3) -> None:
    """Pull a few frames to stabilize exposure on each camera."""

    try:
        for _ in range(iterations):
            camera_manager.CAMERA_MANAGER.capture_images(camera_ids)
    except Exception as exc:  # noqa: BLE001
        # Warmup failures are non-fatal; log at debug level for diagnosis.
        logger.debug("Warmup capture failed: %s", exc)


def capture_color_frames(output_dir: Path, camera_ids: list[str], count: int = 5) -> None:
    """Capture color frames for the provided camera ids."""

    # Organize outputs per session, ensuring the root directory exists.
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load per-camera calibration so we can run the standard processing steps.
    color_calibs = {cam_id: CameraParameters({"camera_id": cam_id}, 0, 12) for cam_id in camera_ids}
    color_steps = ["debayer_subsample", "non_linear", "overwrite_no_rotation"]

    # Create subdirectories per camera for easier inspection.
    for cam_id in camera_ids:
        (output_dir / cam_id).mkdir(parents=True, exist_ok=True)

    for frame_idx in range(count):
        raw_images, infos = camera_manager.CAMERA_MANAGER.capture_images(camera_ids)
        infos = [bi.to_dict() for bi in infos]
        for cam_id, tensor, info in zip(camera_ids, raw_images, infos):
            if tensor is None:
                logger.warning("Camera %s returned no data on frame %d", cam_id, frame_idx)
                continue

            # Apply sensor-specific processing (debayer, color correction, etc.).
            processed = process_images([tensor], [cam_id], color_calibs, color_steps)[0]
            array = processed.detach().cpu().numpy()
            array = _ensure_channel_last(array)
            image = _to_png_image(array)

            png_path = output_dir / cam_id / f"frame_{frame_idx:04d}.png"
            cv2.imwrite(str(png_path), image)

            # Log extra debugging metadata such as capture timestamp, if present.
            logger.debug(
                "Frame %04d for %s captured (timestamp %s)",
                frame_idx,
                cam_id,
                info.get("timestamp_us") if isinstance(info, dict) else None,
            )
