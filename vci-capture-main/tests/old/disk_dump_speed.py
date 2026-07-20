# ruff: noqa: T201, SLF001
import time  # noqa: I001
import unittest

## checks which cameras are connected without opening them

import sparrow.gibbs_wrapper as gibbs


from sparrow.mode_shared.camera_manager import CAMERA_MANAGER
from sparrow.image_processing.codecs import encode_images
from sparrow.image_processing.process_images import process_images
from sparrow.calibration_data import CameraParameters
from sparrow.mode_shared.persistent_record import PERSISTENT_RECORD
from sparrow.mode_shared.persistent import PERSISTENT_DATA
from sparrow.image_processing.processing_steps import StepDefaults
from sparrow.modes.ring_buffer_handler import RingBufferHandler
import torch
import argparse
from tests.stress.old.util_for_test.util import check_image_ok
import sys

# PERSISTENT_RECORD._capture_folder = Path("/tmp/sparrow_test_dump")
PERSISTENT_RECORD._ssd_range = range(8)
PERSISTENT_RECORD._recording_name = "test_recording"

runtime_seconds = 10
runtime_ms = 1000 * runtime_seconds

REQUESTED_CAMERA_IDS = None
DEPTH_MODE = "DEPTH"
SOFTWARE_TRIGGER_FPS = -1

# pretty, non-calibrated images
STEPS = {}


def main():
    parser = argparse.ArgumentParser(description="test collection of basic capturing and writing to disk")
    parser.add_argument(
        "-c", "--cams", nargs="+", type=str, default=None, help="specific camera ids to request. Default: all"
    )
    parser.add_argument("--no-depth", action="store_true", default=False)
    parser.add_argument(
        "--fps",
        default=-1,
        type=int,
        help="if set to positive value, use software trigger at the given fps instead of hardware trigger",
    )
    options, args = parser.parse_known_args()
    global REQUESTED_CAMERA_IDS
    REQUESTED_CAMERA_IDS = options.cams
    global DEPTH_MODE
    DEPTH_MODE = "COLOR" if options.no_depth else "DEPTH"
    global SOFTWARE_TRIGGER_FPS
    SOFTWARE_TRIGGER_FPS = options.fps

    unittest.main(argv=sys.argv[:1] + args)


class Test(unittest.TestCase):

    def test_cameras_connected(self) -> None:
        camera_ids, _ = CAMERA_MANAGER.get_camera_ids_without_opening_cameras()
        gibbs.CameraManager.disable_api_logging()
        print(f"Cameras found: {camera_ids} {len(camera_ids)}")

    def test_single(self) -> None:
        print("-------------test single image----------------")
        CAMERA_MANAGER.setup_cameras(REQUESTED_CAMERA_IDS)
        CAMERA_MANAGER.set_depth_mode(DEPTH_MODE)
        CAMERA_MANAGER.start_cameras()

        raw_images = CAMERA_MANAGER.capture_images()
        for img in raw_images:
            print(f"Image shape: {img.shape} dtype: {img.dtype} min: {img.min()} max: {img.max()}")
        check_raw_images(raw_images, CAMERA_MANAGER.camera_ids)

        CAMERA_MANAGER.stop_cameras()

    def test_pretty(self) -> None:
        print("-------------test pretty image----------------")
        CAMERA_MANAGER.setup_cameras(REQUESTED_CAMERA_IDS)
        CAMERA_MANAGER.set_depth_mode(DEPTH_MODE)
        CAMERA_MANAGER.start_cameras()

        raw_images = CAMERA_MANAGER.capture_images()
        for img in raw_images:
            print(f"Image shape: {img.shape} dtype: {img.dtype} min: {img.min()} max: {img.max()}")
        calibs = {cam_id: CameraParameters({"camera_id": cam_id}, 0, 12) for cam_id in CAMERA_MANAGER.camera_ids}
        processed_images = process_images(raw_images, calibs, StepDefaults.UNCALIBRATED)
        check_raw_images(processed_images, CAMERA_MANAGER.camera_ids)

        CAMERA_MANAGER.stop_cameras()

    @unittest.skip("only for manual performance testing")
    def test_diskdump(self) -> None:
        print("-------------test tasks.capture_to_disk_dump----------------")
        CAMERA_MANAGER.setup_cameras(REQUESTED_CAMERA_IDS)
        CAMERA_MANAGER.set_depth_mode(DEPTH_MODE)
        create_folders()
        PERSISTENT_RECORD.delete_recording(PERSISTENT_RECORD._recording_name)

        cache_writer = gibbs.io.CacheWriter(
            str(PERSISTENT_RECORD.cache_location),
            [str(d) for d in PERSISTENT_RECORD.dump_locations],
            CAMERA_MANAGER.camera_ids,
        )
        print("capture...")

        frame_counter = gibbs.tasks.capture_to_disk_dump(CAMERA_MANAGER.cameras, cache_writer, runtime_ms, None, False)
        fps = [(cnt / (runtime_seconds)) for cnt in frame_counter]
        print()
        print(
            f"Frames written: {list(zip(frame_counter, CAMERA_MANAGER.camera_ids, strict=False))} "
            "- capture time {runtime_seconds} seconds"
        )
        print(f"fps: {list(zip(fps, CAMERA_MANAGER.camera_ids, strict=False))}")
        CAMERA_MANAGER.stop_cameras()
        check_image_from_recording()

    def test_recordcapture(self) -> None:
        print("--------- test tasks.RecordCapture ---------")
        # this is like record mode of sparrow.server
        CAMERA_MANAGER.setup_cameras(REQUESTED_CAMERA_IDS)
        CAMERA_MANAGER.set_depth_mode(DEPTH_MODE)
        create_folders()
        PERSISTENT_RECORD.delete_recording(PERSISTENT_RECORD._recording_name)

        cache_writer = gibbs.io.CacheWriter(
            str(PERSISTENT_RECORD.cache_location),
            [str(d) for d in PERSISTENT_RECORD.dump_locations],
            CAMERA_MANAGER.camera_ids,
        )
        recorder = gibbs.tasks.RecordCapture(CAMERA_MANAGER.cameras, cache_writer, SOFTWARE_TRIGGER_FPS)

        CAMERA_MANAGER.start_cameras()
        print(f"\ncapture time set to {runtime_seconds} seconds. Capturing...")
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
        check_image_from_recording()

    def test_ssdfull(self) -> None:
        print("--------- test full ssd ---------")
        # this is like record mode of sparrow.server
        CAMERA_MANAGER.setup_cameras(REQUESTED_CAMERA_IDS)
        CAMERA_MANAGER.set_depth_mode(DEPTH_MODE)
        create_folders()
        PERSISTENT_RECORD.delete_recording(PERSISTENT_RECORD._recording_name)

        cache_writer = gibbs.io.CacheWriter(
            str(PERSISTENT_RECORD.cache_location),
            [str(d) for d in PERSISTENT_RECORD.dump_locations],
            CAMERA_MANAGER.camera_ids,
        )
        recorder = gibbs.tasks.RecordCapture(CAMERA_MANAGER.cameras, cache_writer, SOFTWARE_TRIGGER_FPS)

        CAMERA_MANAGER.start_cameras()

        recorder.Run()
        start = time.time()
        minutes = 35
        step = 5
        print(f"\ncapture time set to {minutes} minutes. Capturing...")
        try:
            for i in range(0, minutes * 60, step):
                time.sleep(step)
                t = time.time() - start
                print(
                    f"{int(t/60)}:{round(t%60, 4)}. Frames: {recorder.SequenceLength()} - {recorder.SequenceLength()/t} fps"
                )
        except Exception as e:
            print(e)
        except KeyboardInterrupt:
            print("Capture stopped via Keyboard interrupt")
        recorder.Stop()

        frame_count = recorder.SquenceLength()
        print()
        print(f"Frames written: {frame_count}")
        print(f"fps: {[frame_count / runtime_seconds]}")

        print("Camera manager stop cameras")
        CAMERA_MANAGER.stop_cameras()
        check_image_from_recording()

    def test_processing(self) -> None:
        print("-------------- test processing mutliple images-------------")
        cache_reader = gibbs.io.CacheReader(str(PERSISTENT_RECORD.cache_location))
        cam_ids = cache_reader.camera_ids
        print(f"Frames in cache: {cache_reader.frame_count} {cam_ids}")
        frame_count = cache_reader.frame_count
        STEPS = {camera_id: STEPS[camera_id[0]] for camera_id in CAMERA_MANAGER.camera_ids}

        calibs = {cam_id: CameraParameters({"camera_id": cam_id}, 0, 12) for cam_id in cam_ids}
        for i in range(frame_count):
            start = time.time()
            raw_images = [cache_reader.load_frame(cam_idx, i)[0] for cam_idx in range(len(cam_ids))]
            calibs = {cam_id: CameraParameters({"camera_id": cam_id}, 0, 12) for cam_id in cam_ids}
            processed_images = process_images(raw_images, calibs, STEPS)
            check_raw_images(processed_images, CAMERA_MANAGER.camera_ids, save=False)
            end = time.time()
            print(f"{i}/{frame_count} took {end-start} seconds")

    def test_ringbuffer(self) -> None:
        CAMERA_MANAGER.setup_cameras()
        CAMERA_MANAGER.start_cameras()
        PERSISTENT_DATA.load(CAMERA_MANAGER.camera_ids)

        backgrounds_raw, buffer_infos = CAMERA_MANAGER.capture_images()
        PERSISTENT_DATA.save_background_images(backgrounds_raw)
        height = buffer_infos[0]["height"]
        width = buffer_infos[0]["width"]

        PERSISTENT_DATA.calibration_data.fake_calib(height, width)

        ring_buffer = RingBufferHandler.create_ring_buffer()

        ring_buffer.Run()

        minutes = 35

        print("ring buffer running ....")
        start = time.time()
        try:
            for i in range(0, minutes * 60, 5):
                time.sleep(5)
                t = time.time() - start
                cnt = ring_buffer.LastFrame()
                print(f"{int(t/60)}:{round(t%60, 4)} frames: {cnt}, fps:{cnt/t}")
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(e)

        print("stop")
        ring_buffer.Stop()
        CAMERA_MANAGER.stop_cameras()


def create_folders() -> None:
    for ssd in PERSISTENT_RECORD.ssds:
        ssd.mkdir(parents=True, exist_ok=True)


def check_image_from_recording(frame: int = 0) -> None:
    cache_reader = gibbs.io.CacheReader(str(PERSISTENT_RECORD.cache_location))
    print(f"Frames in cache: {cache_reader.frame_count}")
    cam_ids = cache_reader.camera_ids
    print(cam_ids)
    raw_images = [cache_reader.load_frame_as_tensor(cam_idx, frame)[0] for cam_idx in range(len(cam_ids))]
    check_raw_images(raw_images, cam_ids)


def check_raw_images(raw_images: list[torch.tensor], camera_ids: list[str], *, save: bool = True) -> None:
    shapes = [image.shape for image in raw_images]
    images = [encode_images(image, "jpg", quality=89) for image in raw_images]
    images = [image.cpu() for image in images]
    print(f"Image shapes: {shapes}")
    if save:
        check_image_ok(
            images,
            camera_ids,
            "jpg",
            shapes,
            is_matte=False,
        )


if __name__ == "__main__":
    main()
