# ruff: noqa: T201
import json
import shutil
import time
from pathlib import Path

from sparrow.image_processing.codecs import encode_images
from sparrow.mode_shared.camera_manager import CAMERA_MANAGER

RUNTIME_SECONDS = 10
SAVE_DIR = Path("images")


def stability_test():
    if SAVE_DIR.exists():
        shutil.rmtree(SAVE_DIR)
    SAVE_DIR.mkdir(parents=True)

    ignore_path = Path("camera_ignore.json")
    all_ids, _ = CAMERA_MANAGER.get_camera_ids_without_opening_cameras()

    requested_ids = all_ids
    if ignore_path.exists():
        with open(ignore_path) as f:
            data = json.load(f)
            ignored = data.get("ignored_cameras", [])
            requested_ids = [cid for cid in all_ids if cid not in ignored]
            print(f"Loaded ignore file from {ignore_path}")
            print(f"Active cameras: {requested_ids}")
    else:
        print(f"CRITICAL: Ignore file NOT found at {ignore_path}")

    CAMERA_MANAGER.setup_cameras(requested_ids)
    CAMERA_MANAGER.set_depth_mode("COLOR")

    for camera in CAMERA_MANAGER.cameras:
        mfr = camera.manufacturer.lower()
        camera.set_exposure(200)
        if "orbbec" in mfr:
            camera.set_secondary()
            camera.set_exposure(200)

    CAMERA_MANAGER.start_cameras()

    if not CAMERA_MANAGER.camera_ids:
        print("No cameras were opened. Ending test.")
        return

    print("Waiting 2s for stabilization...")
    time.sleep(2)

    first_hw_nos = {}
    counts = dict.fromkeys(CAMERA_MANAGER.camera_ids, 0)
    initial_gaps = {}
    max_drifts = dict.fromkeys(CAMERA_MANAGER.camera_ids, 0.0)

    loop_idx = 0
    print("Flushing buffer...")
    for _ in range(50):
        CAMERA_MANAGER.capture_images()
    print("Buffer clear. Starting test.")

    start_time = time.time()
    try:
        print(f"Capturing for {RUNTIME_SECONDS} seconds...")
        while (time.time() - start_time) < RUNTIME_SECONDS:
            raw_images, image_infos = CAMERA_MANAGER.capture_images()

            if not image_infos:
                continue

            ref_ts = image_infos[0].get("timestamp_us")

            for idx, info in enumerate(image_infos):
                cam_id = CAMERA_MANAGER.camera_ids[idx]

                if CAMERA_MANAGER.cameras[idx].manufacturer.lower() == "orbbec":
                    ts = info.get("timestamp_us")  #  * 1000.0
                else:
                    ts = info.get("timestamp_us")

                hw_no = info.get("frame_number")

                if cam_id not in first_hw_nos:
                    first_hw_nos[cam_id] = hw_no
                    initial_gaps[cam_id] = ts - ref_ts

                current_gap = ts - ref_ts
                drift = (current_gap - initial_gaps[cam_id]) / 1000.0

                if abs(drift) > abs(max_drifts[cam_id]):
                    max_drifts[cam_id] = drift

                counts[cam_id] += 1
                hwf = hw_no - first_hw_nos[cam_id]

                file_name = f"frame_{loop_idx:04d}_{cam_id}.jpg"
                encoded_data = encode_images(raw_images[idx], "jpg", quality=95)
                with open(SAVE_DIR / file_name, "wb") as f:
                    f.write(encoded_data.cpu().numpy())

                print(f"[{loop_idx:03d}] {cam_id} | HWf: {hwf} | Drift: {drift:.3f}ms | TS: {ts}")

            loop_idx += 1

    finally:
        CAMERA_MANAGER.stop_cameras()

        for cam_id in CAMERA_MANAGER.camera_ids:
            total = counts[cam_id]
            m_drift = max_drifts[cam_id]
            print(f"Cam {cam_id}: {total} frames | Max Deviation: {m_drift:.3f}ms")
        print("=" * 40)


if __name__ == "__main__":
    stability_test()
