## checks which cameras are connected without opening them


import argparse
import time
from pathlib import Path

from sparrow.gibbs_wrapper import ImageType
from sparrow.mode_shared.camera_manager import CAMERA_MANAGER, ExposureSetting
from sparrow.mode_shared.persistent import PERSISTENT_DATA
from sparrow.mode_shared.persistent_record import PERSISTENT_RECORD
from sparrow.modes.record_handler import RecordHandle


def main() -> None:
    ### arguments
    parser = argparse.ArgumentParser(description="test collection of basic capturing and writing to disk")
    parser.add_argument(
        "-c", "--cams", nargs="+", type=str, default=None, help="specific camera ids to request. Default: all"
    )
    parser.add_argument(
        "--no-ssds",
        action="store_true",
        help="Disbales storeage on ssd. Stores in local data/recordings instead, using a single dump -> for creating pipeline/stress test data.",
    )
    args = parser.parse_args()

    ### record
    camera_ids, _ = CAMERA_MANAGER.get_camera_ids_without_opening_cameras()
    print(f"Cameras found: {camera_ids} {len(camera_ids)}")

    if args.no_ssds:
        PERSISTENT_RECORD._ssd_range = range(1)
        outpath = Path("data/recordings")
        (outpath / "ssd0").mkdir(exist_ok=True, parents=True)
        PERSISTENT_RECORD._capture_folder = outpath

    CAMERA_MANAGER.exposure_settings[ImageType.Color] = ExposureSetting(exposure_ms=35312, gain=12)
    CAMERA_MANAGER.setup_cameras(args.cams)
    PERSISTENT_DATA.load(CAMERA_MANAGER.camera_ids)

    rh = RecordHandle()
    rh.software_trigger_fps = 10

    print(CAMERA_MANAGER.get_camera_info())
    print(PERSISTENT_DATA.calibration_data.camera_ids)

    print("starting cameras...")

    CAMERA_MANAGER.start_cameras()
    CAMERA_MANAGER.set_trigger_source("Software")

    print("-------------- READY --------------------")

    rh.set_recording_name("_test")

    rh.on_start()

    time.sleep(0.1)

    rh.on_stop()

    print(rh.get_status(verbose=False))


if __name__ == "__main__":
    main()
