from __future__ import annotations

import logging
import signal
import sys
import time

# ruff: noqa: ANN001
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

import cv2
import tests.orbbec.helpers as helpers

import sparrow.gibbs_wrapper as g

LOGGER = logging.getLogger("await_trigger_signal")

MAX_CAMERA_INDEX = 64
START_DELAY_SEC = 0.1
CAPTURE_TIMEOUT_MS = 2000
CAPTURE_LIMIT = 50
OUTPUT_ROOT = Path("hardwaretrigger_result_images")


def _iter_cameras() -> list[g.Camera]:
    cameras: list[g.Camera] = []
    for index in range(MAX_CAMERA_INDEX):
        camera = None
        with suppress(Exception):
            camera = g.CameraManager.get_camera_by_id(index)
        if camera:
            cameras.append(camera)
    return cameras


def _target_cameras() -> list[g.Camera]:
    return [camera for camera in _iter_cameras() if camera.manufacturer in {"Ximea", "Orbbec"}]


def _open_camera(camera) -> None:
    with suppress(Exception):
        if hasattr(camera, "is_open") and camera.is_open():
            return
        camera.open()


def _create_output_dir() -> Path:
    OUTPUT_ROOT.mkdir(exist_ok=True)
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    target = OUTPUT_ROOT / timestamp
    target.mkdir(exist_ok=True)
    return target


def _save_frame(camera, entry, output_dir: Path, frame_index: int) -> Path:
    cam_dir = output_dir / camera.camera_id
    cam_dir.mkdir(parents=True, exist_ok=True)
    filename = cam_dir / f"frame_{frame_index:04d}.png"
    image = helpers.color_entry_to_bgr(entry)
    cv2.imwrite(str(filename), image)
    return filename


def _capture_frames(
    cameras: list[g.Camera],
    output_dir: Path,
    frame_limit: int,
    should_continue,
) -> dict[str, int]:
    counts: dict[str, int] = {camera.camera_id: 0 for camera in cameras}
    if not cameras:
        return counts
    while should_continue() and any(count < frame_limit for count in counts.values()):
        for camera in cameras:
            if not should_continue():
                break
            camera_id = camera.camera_id
            if counts[camera_id] >= frame_limit:
                continue
            entry = None
            with suppress(Exception):
                entry = camera.capture_next(CAPTURE_TIMEOUT_MS)
            if entry is None:
                continue
            try:
                frame_path = _save_frame(camera, entry, output_dir, counts[camera_id])
                counts[camera_id] += 1
                LOGGER.info(
                    "Captured %s (camera %s, frame %s/%s)",
                    frame_path,
                    camera_id,
                    counts[camera_id],
                    frame_limit,
                )
            finally:
                with suppress(Exception):
                    entry.unlock()
    return counts


def _set_hardware_trigger(camera) -> None:
    if camera.device_name() == "Femto Mega":
        LOGGER.info("Hardware trigger already active on %s (Femto Mega)", camera.camera_id)
        return
    _open_camera(camera)
    try:
        camera.set_hardware_trigger()
    except AttributeError:
        LOGGER.warning("%s does not expose set_hardware_trigger()", camera.camera_id)
    except RuntimeError as err:
        LOGGER.warning("Failed to enable hardware trigger on %s: %s", camera.camera_id, err)
    else:
        LOGGER.info(
            "Hardware trigger enabled on %s (%s)",
            camera.camera_id,
            camera.manufacturer,
        )


def _set_secondary(camera) -> None:
    with suppress(Exception):
        camera.set_secondary()


def _start(camera) -> None:
    with suppress(Exception):
        camera.start()


def _stop(camera) -> None:
    with suppress(Exception):
        camera.stop()
    with suppress(Exception):
        camera.close()


def _apply_orbbec_color(camera) -> None:
    if camera.camera_type == g.ImageType.Depth:
        with suppress(Exception):
            g.set_orbbec_mode(camera, g.OrbbecMode.COLOR)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    cameras = list(_target_cameras())
    if not cameras:
        LOGGER.error("No Ximea or Orbbec cameras detected.")
        raise SystemExit(1)

    for camera in cameras:
        _apply_orbbec_color(camera)
        _set_hardware_trigger(camera)
        _set_secondary(camera)

    LOGGER.info("Starting %s camera(s) in secondary mode awaiting external trigger", len(cameras))

    for camera in cameras:
        _start(camera)
        time.sleep(START_DELAY_SEC)

    output_dir = _create_output_dir()
    LOGGER.info(
        "All cameras started. Awaiting trigger to capture up to %s frames per camera into %s",
        CAPTURE_LIMIT,
        output_dir,
    )

    should_run = True

    def _handle_signal(signum, _frame=None) -> None:
        nonlocal should_run
        LOGGER.info("Received signal %s, stopping cameras", signum)
        should_run = False

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    counts: dict[str, int] = {camera.camera_id: 0 for camera in cameras}
    try:
        counts = _capture_frames(cameras, output_dir, CAPTURE_LIMIT, lambda: should_run)
    finally:
        for camera in cameras:
            _stop(camera)
        LOGGER.info("All cameras stopped.")

    if counts and all(count >= CAPTURE_LIMIT for count in counts.values()):
        LOGGER.info("Captured %s frames for each camera. Results saved in %s", CAPTURE_LIMIT, output_dir)
    else:
        LOGGER.info("Captured frames per camera: %s (output: %s)", counts, output_dir)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
