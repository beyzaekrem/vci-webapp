# ruff: noqa: T201, SLF001
import time  # noqa: I001

## checks which cameras are connected without opening them

import sparrow.gibbs_wrapper as gibbs


from sparrow.mode_shared.camera_manager import CAMERA_MANAGER
from sparrow.mode_shared.persistent_record import PERSISTENT_RECORD

# PERSISTENT_RECORD._capture_folder = Path("/tmp/sparrow_test_dump")
PERSISTENT_RECORD._ssd_cnt = 8
PERSISTENT_RECORD._recording_name = "test_recording"

runtime_seconds = 10
runtime_ms = 1000 * runtime_seconds


# pretty, non-calibrated images
steps_map = {}


def main():
    CAMERA_MANAGER.setup_cameras()
    for camera in CAMERA_MANAGER.cameras:
        camera.set_parameter_int("trigger_source", 0)  # Max speed

    PERSISTENT_RECORD.delete_recording(PERSISTENT_RECORD._recording_name)

    cache_writer = gibbs.io.CacheWriter(
        str(PERSISTENT_RECORD.cache_location),
        [str(d) for d in PERSISTENT_RECORD.dump_locations],
        CAMERA_MANAGER.camera_ids,
    )
    recorder = gibbs.tasks.RecordCapture(CAMERA_MANAGER.cameras, cache_writer, -1)

    CAMERA_MANAGER.start_cameras()

    recorder.Run()
    start = time.time()
    for _ in range(0, runtime_seconds, 5):
        time.sleep(5)
        print(f"Time elapsed: {time.time() - start}. Frames: {recorder.SquenceLength()}")
    recorder.Stop()

    frame_count = recorder.SquenceLength()
    print()
    print(f"Frames written: {frame_count}")
    print(f"fps: {[frame_count / runtime_seconds]}")

    print("Camera manager stop cameras")
    CAMERA_MANAGER.stop_cameras()


if __name__ == "__main__":
    main()
