import argparse

import sparrow.gibbs_wrapper as gibbs
from sparrow.mode_shared.camera_manager import CAMERA_MANAGER

parser = argparse.ArgumentParser(description="checks which cameras are connected without opening them")
parser.add_argument("--log-level", "-l", choices=["debug", "info", "warn"], default="warn")

args = parser.parse_args()
if args.log_level is not None:
    log_level = getattr(gibbs.interceptor.log_level, args.log_level.lower(), None)
    if log_level is not None:
        gibbs.interceptor.setup_logger(log_level, log_level)
    else:
        print(f"failed to parse '{args.log_level}' to a proper log_level")

cameras: dict[str, any] = CAMERA_MANAGER.get_camera_ids_without_opening_cameras()
gibbs.CameraManager.disable_api_logging()
print(f"Cameras found: {list(cameras.keys())} {len(cameras)}")  # noqa: T201
