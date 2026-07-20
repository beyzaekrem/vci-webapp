from __future__ import annotations

import argparse
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

import cv2
import helpers

import sparrow.gibbs_wrapper as g
from sparrow.mode_shared import CAMERA_MANAGER, LOG  # noqa: F401

# ruff: noqa: ANN001

logger = logging.getLogger(__name__)

# ---------- Config ----------
MAX_CAMERA_INDEX = 2
FRAME_COUNT = 100
CAPTURE_TIMEOUT_MS = 2000
START_DELAY_SEC = 0.1
OUTPUT_ROOT = Path("hardwaretrigger_result_images")
COLOR_EXPOSURE_US = 300
COLOR_GAIN = 0

# Sync helpers
SETTLE_SEC = 0.5
BARRIER_SLACK_SEC = 0.2


def _find_orbbec_cameras() -> list:
    cameras: list = []
    for idx in range(MAX_CAMERA_INDEX):
        cam = None
        with suppress(Exception):
            cam = g.CameraManager.get_camera_by_id(idx)
        if cam and cam.camera_type == g.ImageType.Depth:
            cameras.append(cam)
    return cameras


def _set_roles(cameras: list, primary_mode: int) -> None:
    if not cameras:
        return
    if primary_mode:
        with suppress(Exception):
            cameras[0].set_primary()
        remainder = cameras[1:]
    else:
        remainder = cameras
    for cam in remainder:
        with suppress(Exception):
            cam.set_secondary()


def _set_color_mode(cameras: list) -> None:
    for cam in cameras:
        _set_single_color_mode(cam)


def _set_single_color_mode(cam) -> None:
    try:
        g.set_orbbec_mode(cam, g.OrbbecMode.COLOR)
    except RuntimeError as err:
        logger.warning("Failed to put %s into COLOR mode: %s", cam.camera_id, err)


def _configure_color_exposure(cam) -> None:
    with suppress(Exception):
        cam.set_parameter_int("OB_PROP_COLOR_AUTO_EXPOSURE_BOOL", 0)
    with suppress(Exception):
        cam.set_parameter_int("OB_PROP_COLOR_GAIN_INT", COLOR_GAIN)
    with suppress(Exception):
        cam.set_parameter_int("OB_PROP_COLOR_EXPOSURE_INT", COLOR_EXPOSURE_US)


def _apply_color_settings(cameras: list) -> None:
    for cam in cameras:
        _configure_color_exposure(cam)


# ---------- Stream control (synced start/stop) ----------
def _start_streams(cameras: list) -> None:
    # Start all cameras without staggering to avoid buffer/phase offsets; then warm-up
    for cam in cameras:
        with suppress(Exception):
            cam.start()
    time.sleep(SETTLE_SEC)


def _stop_streams(cameras: list) -> None:
    for cam in cameras:
        with suppress(Exception):
            cam.stop()
    time.sleep(START_DELAY_SEC)
    for cam in cameras:
        with suppress(Exception):
            cam.close()


def _extract_frame_meta(entry):
    """
    Try to read a hardware frame id or timestamp if exposed by the SDK.
    Returns (frame_id, ts_ns) where either may be None.
    """
    frame_id = None
    ts_ns = None
    for name in ("frame_id", "frame_index", "index", "id"):
        with suppress(Exception, AttributeError):
            val = getattr(entry, name)
            frame_id = val() if callable(val) else val
            break
    for name in ("timestamp_ns", "ts_ns", "timestamp", "time_ns"):
        with suppress(Exception, AttributeError):
            val = getattr(entry, name)
            ts_ns = val() if callable(val) else val
            break
    return frame_id, ts_ns


def _capture_color_frames(cameras: list, output_dir: Path) -> None:
    if not cameras:
        return

    barrier = threading.Barrier(parties=len(cameras))
    barrier_lock = threading.Lock()

    def _capture_once(cam) -> tuple[g.BufferEntry | None, object]:
        try:
            barrier.wait(timeout=BARRIER_SLACK_SEC)
        except threading.BrokenBarrierError:
            return None, cam
        entry = None
        with suppress(Exception):
            entry = cam.capture_next(CAPTURE_TIMEOUT_MS)
        return entry, cam

    with ThreadPoolExecutor(max_workers=len(cameras)) as executor:
        for frame_idx in range(FRAME_COUNT):
            with barrier_lock:
                barrier.reset()

            futures = {executor.submit(_capture_once, cam): cam for cam in cameras}

            collected: list[tuple[object, g.BufferEntry | None]] = []
            for fut in as_completed(futures):
                entry, cam = fut.result()
                collected.append((cam, entry))

            chosen_frame_id = None
            id_counts = {}
            for cam, entry in collected:
                if not entry:
                    continue
                fid, _ = _extract_frame_meta(entry)
                if fid is not None:
                    id_counts[fid] = id_counts.get(fid, 0) + 1
            if id_counts:
                chosen_frame_id = max(id_counts.items(), key=lambda kv: kv[1])[0]

            for cam, entry in collected:
                if not entry:
                    logger.warning("No color frame from %s during iteration %s", cam.camera_id, frame_idx)
                    continue
                try:
                    if chosen_frame_id is not None:
                        fid, _ = _extract_frame_meta(entry)
                        if fid != chosen_frame_id:
                            with suppress(Exception):
                                entry.unlock()
                            continue

                    cam_dir = output_dir / cam.camera_id
                    cam_dir.mkdir(parents=True, exist_ok=True)
                    filename = cam_dir / f"frame_{frame_idx:04d}.png"
                    image = helpers.color_entry_to_bgr(entry)
                    cv2.imwrite(str(filename), image)
                    logger.info("Saved %s", filename)
                finally:
                    with suppress(Exception):
                        entry.unlock()


def _create_output_dir() -> Path:
    OUTPUT_ROOT.mkdir(exist_ok=True)
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    capture_dir = OUTPUT_ROOT / timestamp
    capture_dir.mkdir(exist_ok=True)
    return capture_dir


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture color frames from Orbbec cameras.")
    parser.add_argument(
        "--primary-mode",
        type=int,
        choices=(0, 1),
        default=1,
        help="Use 1 to mark the first camera primary, or 0 to run all cameras as secondary.",
    )
    return parser.parse_args()


# ---------- Main ----------
def main() -> None:
    args = _parse_args()
    logging.basicConfig(level=logging.INFO)
    cameras = _find_orbbec_cameras()
    if not cameras:
        raise SystemExit("No Orbbec cameras detected.")
    logger.info("Found %s Orbbec camera(s)", len(cameras))

    _set_roles(cameras, primary_mode=args.primary_mode)
    if args.primary_mode:
        logger.info(
            "Configured %s as primary; %s secondary camera(s)",
            cameras[0].camera_id,
            max(len(cameras) - 1, 0),
        )
    else:
        logger.info("Configured all %s camera(s) as secondary", len(cameras))

    _set_color_mode(cameras)
    _apply_color_settings(cameras)

    output_dir = _create_output_dir()
    _start_streams(cameras)
    try:
        _capture_color_frames(cameras, output_dir)
    finally:
        _stop_streams(cameras)


if __name__ == "__main__":
    main()
