from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tests.orbbec.orbbec_capture_utils import (
    capture_color_frames,
    capture_orbbec_depth_frames,
    list_cameras,
    warmup_cameras,
)

from sparrow.gibbs_wrapper import ImageType
from sparrow.mode_shared import camera_manager

logger = logging.getLogger(__name__)

COLOR_FRAME_COUNT = 5
DEPTH_FRAME_COUNT = 10
WARMUP_ITERATIONS = 3


def _filter_color_cameras() -> None:
    """Limit the shared camera manager to color cameras only."""

    manager = camera_manager.CAMERA_MANAGER
    camera_ids = manager.camera_ids or []
    cameras = manager.cameras or []

    color_pairs = [
        (camera_id, cam) for camera_id, cam in zip(camera_ids, cameras) if cam and cam.camera_type == ImageType.Color
    ]
    non_color_cameras = [
        cam for camera_id, cam in zip(camera_ids, cameras) if cam and cam.camera_type != ImageType.Color
    ]

    for cam in non_color_cameras:
        if cam.is_running():
            cam.stop()
        if cam.is_open():
            cam.close()

    manager.camera_ids = [camera_id for camera_id, _ in color_pairs]
    manager.cameras = [cam for _, cam in color_pairs]


def _close_open_cameras() -> None:
    """Ensure every camera managed by the shared manager is closed."""

    manager = camera_manager.CAMERA_MANAGER
    for cam in manager.cameras or []:
        if cam.is_running():
            cam.stop()
        if cam.is_open():
            cam.close()
    manager.cameras = []
    manager.camera_ids = []


def run_color_capture_session(output_dir: Path) -> None:
    """Capture a burst of color frames and persist them to disk."""

    manager = camera_manager.CAMERA_MANAGER
    manager.setup_cameras()
    _filter_color_cameras()

    if not manager.cameras:
        logger.warning("No color cameras available; skipping color capture")
        return

    manager.start_cameras()
    try:
        camera_ids = manager.camera_ids or []
        warmup_cameras(camera_ids, iterations=WARMUP_ITERATIONS)
        capture_color_frames(output_dir, camera_ids, count=COLOR_FRAME_COUNT)
        logger.info("Color capture complete. Artifacts stored in %s", output_dir)
    finally:
        if manager.cameras_running:
            manager.stop_cameras()
        _close_open_cameras()


def run_depth_capture_session(output_dir: Path) -> None:
    """Capture a burst of depth frames from Orbbec cameras."""

    capture_orbbec_depth_frames(output_dir, count=DEPTH_FRAME_COUNT)
    logger.info("Depth capture complete. Artifacts stored in %s", output_dir)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    list_cameras()

    timestamp = datetime.now(tz=ZoneInfo("Europe/Berlin")).strftime("%Y%m%d_%H%M%S")
    session_dir = Path("images") / timestamp
    color_dir = session_dir / "color"
    depth_dir = session_dir / "depth"

    color_success = True
    depth_success = True

    logger.info("Starting color capture → %s", color_dir)
    try:
        run_color_capture_session(color_dir)
    except Exception:
        color_success = False
        logger.exception("Color capture failed")

    logger.info("Starting Orbbec depth capture → %s", depth_dir)
    try:
        run_depth_capture_session(depth_dir)
    except Exception:
        depth_success = False
        logger.exception("Depth capture failed")

    if not (color_success and depth_success):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
