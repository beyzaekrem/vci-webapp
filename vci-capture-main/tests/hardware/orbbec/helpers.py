"""Utility helpers for working with Orbbec/Ximea cameras via the sparrow SDK.

This module provides a thin wrapper around the Gibbs camera manager for
enumerating devices, configuring capture parameters, and persisting frames to
disk. Functions are intentionally lightweight so that higher level scripts can
combine them as needed.
"""

# ruff: noqa: ANN001, ANN201, BLE001, PERF203

from __future__ import annotations

import logging
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import cv2
import numpy as np
from tests.orbbec.orbbec_capture_utils import _ensure_channel_last

import sparrow.gibbs_wrapper as g
from sparrow.mode_shared import CAMERA_MANAGER, LOG  # noqa: F401

logger = logging.getLogger(__name__)

DEFAULT_COLOR_EXPOSURE = 120
_COLOR_TIMEOUT_MS = 1500
_DEPTH_TIMEOUT_MS = 2000
_COLOR_SETTLE_FRAMES = 10
_COLOR_AUTO_EXPOSURE = "OB_PROP_COLOR_AUTO_EXPOSURE_BOOL"
_COLOR_EXPOSURE = "OB_PROP_COLOR_EXPOSURE_INT"
_COLOR_GAIN = "OB_PROP_COLOR_GAIN_INT"
_CHANNEL_DIMS = 3
_NV12_CHANNELS = 2
_RGB_MIN_CHANNELS = 3
_DEFAULT_ROOTS = {
    "color": "color_captures",
    "mono": "mono_captures",
    "depth": "depth_captures",
}


def enumerate_cameras():
    """Locate connected cameras and bucket them by type.

    Returns
    -------
    tuple[list[Any], list[Any], list[Any]]
        A tuple containing the complete camera list, the subset of depth
        cameras (Orbbec), and the subset of color cameras (Ximea).

    Notes
    -----
    The Gibbs API occasionally raises if a device index is unused. We probe up
    to 64 indices to remain tolerant of sparse ID assignments.
    """

    cams = []
    n = 64
    with suppress(Exception):
        n = g.CameraManager.num_cameras()
    for i in range(n):
        c = None
        with suppress(Exception):
            c = g.CameraManager.get_camera_by_id(i)
        if c:
            cams.append(c)
    orbbec = []
    ximea = []
    for c in cams:
        logger.info(
            "%s %s %s %s %s",
            c.camera_id,
            c.info().device_name,
            c.info().manufacturer,
            c.info().serialnumber,
            c.camera_type,
        )
        if c.camera_type == g.ImageType.Depth:
            orbbec.append(c)
        elif c.camera_type == g.ImageType.Color:
            ximea.append(c)
    logger.info("Found %s orbbec cameras and %s ximea camera", len(orbbec), len(ximea))
    return cams, orbbec, ximea


def list_orbbec():
    """Return a list of all detected Orbbec (depth) cameras."""

    out = []
    for i in range(64):
        with suppress(Exception):
            c = g.CameraManager.get_camera_by_id(i)
            if c and str(c.camera_type) == "ImageType.Depth":
                out.append(c)
    return out


def set_depth_mode(cams):
    """Configure all provided cameras to use the Orbbec depth capture mode."""

    for c in cams:
        g.set_orbbec_mode(c, g.OrbbecMode.DEPTH)


def set_color_mode(cams):
    """Configure all provided cameras to use the Orbbec color capture mode."""

    for c in cams:
        camera_id = c.camera_id if hasattr(c, "camera_id") else "?"
        try:
            g.set_orbbec_mode(c, g.OrbbecMode.COLOR)
        except RuntimeError as err:
            logger.warning("failed to switch %s to COLOR mode: %s", camera_id, err)


def assign_roles(cams):
    """Mark the first camera as primary and the rest as secondary if possible."""

    if not cams:
        return
    with suppress(Exception):
        cams[0].set_primary()
    for c in cams[1:]:
        with suppress(Exception):
            c.set_secondary()


def start_orbbec(cams, warmup=2, delay=0.1):
    """Start capture on each camera and perform a warmup sequence.

    Parameters
    ----------
    cams : Iterable
        Collection of camera objects to start.
    warmup : int, default=2
        Number of dummy frames to pull per camera to stabilize exposure.
    delay : float, default=0.1
        Sleep duration between kicking off individual camera streams.
    """

    for c in cams:
        with suppress(Exception):
            c.start()
        time.sleep(delay)
    for c in cams:
        for _ in range(warmup):
            try:
                b = c.capture_next(200)
            except Exception:
                break
            if b:
                with suppress(Exception):
                    b.unlock()


def stop_orbbec(cams):
    """Stop and close each camera, swallowing any device-level errors."""

    for c in cams:
        with suppress(Exception):
            c.stop()
    time.sleep(0.05)
    for c in cams:
        with suppress(Exception):
            c.close()


def save_depth(be, raw_path, viz_path):
    """Persist a depth buffer to disk along with a colored visualization."""

    info = be.info()
    b = be.to_bytes()
    h, w = info.height, info.width
    arr = np.frombuffer(b, np.uint16).reshape(h, w)
    cv2.imwrite(str(raw_path), arr)
    mx = int(arr.max()) or 1
    viz = cv2.applyColorMap((arr * (255.0 / mx)).astype(np.uint8), cv2.COLORMAP_JET)
    cv2.imwrite(str(viz_path), viz)


def capture_once(cams, timeout_ms=2000):
    """Capture a single frame from each camera, tolerating timeouts."""

    outs = []
    for c in cams:
        try:
            b = c.capture_next(timeout_ms)
        except Exception:
            b = None
        outs.append(b)
    return outs


def capture_loop(cams, n=50, outdir="orbbec_out", prefix=None, timeout_ms=2000):
    """Capture a burst of depth frames and write raw/viz images to disk."""

    p = Path(outdir)
    p.mkdir(exist_ok=True)
    for i in range(n):
        bufs = capture_once(cams, timeout_ms)
        try:
            for idx, be in enumerate(bufs):
                if not be:
                    continue
                tag = prefix[idx] if prefix and idx < len(prefix) else f"C{idx}"
                rp = p / f"{tag}_raw_{i:04d}.png"
                vp = p / f"{tag}_viz_{i:04d}.png"
                save_depth(be, rp, vp)
            ok = [bool(b) for b in bufs]
            logger.info("capture iteration %s ok=%s", i, ok)
        finally:
            for b in bufs:
                if b:
                    with suppress(Exception):
                        b.unlock()


def save_color(be, raw_path):
    """Persist a color buffer to disk as a PNG image."""

    info = be.info()
    b = be.to_bytes()
    h, w = info.height, info.width
    arr = np.frombuffer(b, np.uint8).reshape(h, w, 3)
    cv2.imwrite(str(raw_path), arr)


def next_color_output_dir(root: str = "exposure_image_tests") -> Path:
    """Return a timestamped directory under *root* for color captures."""

    timestamp = datetime.now(tz=ZoneInfo("Europe/Berlin")).strftime("%Y%m%d_%H%M%S")
    return Path(root) / timestamp


def _color_entry_to_bgr(entry) -> np.ndarray:
    tensor = g.ConvertBufferEntryToTorchTensor(entry)
    array = tensor.detach().cpu().numpy()
    array = _ensure_channel_last(array)
    array = array.astype(np.uint8, copy=False)
    if array.ndim == _CHANNEL_DIMS and array.shape[2] == _NV12_CHANNELS:
        return cv2.cvtColor(array, cv2.COLOR_YUV2BGR_YUY2)
    if array.ndim == _CHANNEL_DIMS and array.shape[2] >= _RGB_MIN_CHANNELS:
        return array[..., :3]
    return cv2.cvtColor(array, cv2.COLOR_GRAY2BGR)


def _prepare_color_camera(cam) -> None:
    for key, value in ((_COLOR_AUTO_EXPOSURE, 0), (_COLOR_GAIN, 0)):
        with suppress(Exception):
            cam.set_parameter_int(key, value)


def color_entry_to_bgr(entry) -> np.ndarray:
    """Convert a color buffer entry to a BGR ndarray."""

    return _color_entry_to_bgr(entry)


_CAPTURE_MODES = {"color", "mono", "depth"}
CAPTURE_MODES = tuple(sorted(_CAPTURE_MODES))


def _resolve_output_dir(mode: str, output_dir: str | Path | None) -> Path:
    root = Path(output_dir) if output_dir else Path(_DEFAULT_ROOTS.get(mode, mode))
    root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(tz=ZoneInfo("Europe/Berlin")).strftime("%Y%m%d_%H%M%S")
    path = root / timestamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def capture_mode_once(
    cams,
    *,
    mode: str = "color",
    exposure: int | None = None,
    output_dir: str | Path | None = None,
    open_dir: bool = False,
) -> Path:
    """Capture a single frame from each camera in *mode* concurrently.

    Parameters
    ----------
    cams
        Iterable of camera objects to sample.
    mode
        Capture mode to use. Supported values: ``"color"``, ``"mono"``,
        ``"depth"``.
    exposure
        Manual exposure in microseconds for color/mono captures. When omitted
        the default exposure is applied.
    output_dir
        Optional directory where the timestamped capture folder will be
        created. Defaults to a mode-specific root directory.
    open_dir
        When ``True`` the resulting directory is opened with ``xdg-open``.
    """

    if mode not in _CAPTURE_MODES:
        msg = f"Unsupported mode '{mode}'. Expected one of {_CAPTURE_MODES}."
        raise ValueError(msg)
    if not cams:
        msg = "No cameras provided for capture."
        raise ValueError(msg)

    if mode == "depth":
        set_depth_mode(cams)
    else:
        set_color_mode(cams)

    if mode in {"color", "mono"}:
        for cam in cams:
            _prepare_color_camera(cam)

    output_path = _resolve_output_dir(mode, output_dir)
    timestamp = datetime.now(tz=ZoneInfo("Europe/Berlin")).strftime("%Y%m%d_%H%M%S_%f")
    exposure_value = exposure if exposure is not None else DEFAULT_COLOR_EXPOSURE

    def _capture_color(cam) -> Path | None:
        cam_dir = output_path / cam.camera_id
        cam_dir.mkdir(parents=True, exist_ok=True)
        with suppress(Exception):
            cam.set_parameter_int(_COLOR_EXPOSURE, exposure_value)
        for _ in range(_COLOR_SETTLE_FRAMES):
            entry = cam.capture_next(_COLOR_TIMEOUT_MS)
            if entry:
                entry.unlock()
        entry = cam.capture_next(_COLOR_TIMEOUT_MS)
        if not entry:
            return None
        try:
            image = _color_entry_to_bgr(entry)
        finally:
            entry.unlock()
        if mode == "mono":
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        filename = cam_dir / f"{mode}_{exposure_value}_{timestamp}.png"
        cv2.imwrite(str(filename), image)
        return filename

    def _capture_depth(cam) -> Path | None:
        cam_dir = output_path / cam.camera_id
        cam_dir.mkdir(parents=True, exist_ok=True)
        entry = cam.capture_next(_DEPTH_TIMEOUT_MS)
        if not entry:
            return None
        raw_path = cam_dir / f"{mode}_{timestamp}_raw.png"
        viz_path = cam_dir / f"{mode}_{timestamp}_viz.png"
        try:
            save_depth(entry, raw_path, viz_path)
        finally:
            entry.unlock()
        return viz_path

    worker = _capture_depth if mode == "depth" else _capture_color
    results: list[Path] = []
    with ThreadPoolExecutor(max_workers=max(len(cams), 1)) as executor:
        futures = {executor.submit(worker, cam): cam for cam in cams}
        for future, cam in futures.items():
            try:
                result = future.result()
            except Exception:
                logger.exception("Failed to capture from %s", cam.camera_id)
            else:
                if result:
                    results.append(result)
                else:
                    logger.warning("No frame captured from %s", cam.camera_id)

    if open_dir:
        with suppress(Exception):
            webbrowser.open(output_path.resolve().as_uri(), new=0, autoraise=True)

    return output_path


def capture_color_exposures(cams, exposures=None, output_dir=None) -> Path:
    """Backward compatible wrapper around :func:`capture_mode_once`."""

    if exposures and isinstance(exposures, (list, tuple)):
        exposure_value = exposures[0]
    elif isinstance(exposures, int):
        exposure_value = exposures
    else:
        exposure_value = None
    return capture_mode_once(cams, mode="color", exposure=exposure_value, output_dir=output_dir)
