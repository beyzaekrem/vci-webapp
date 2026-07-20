# isort: skip_file
from __future__ import annotations

import argparse

import tests.orbbec.helpers as helpers


NO_ORBBEC_MSG = "No Orbbec cameras found."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture frames from Orbbec cameras.")
    parser.add_argument(
        "--mode",
        default="color",
        choices=helpers.CAPTURE_MODES,
        help="Capture mode to use.",
    )
    parser.add_argument(
        "--exposure",
        type=int,
        help="Manual exposure value (microseconds) for color/mono modes.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the output directory after capture.",
    )
    parser.add_argument(
        "--output-root",
        type=str,
        help="Optional directory where the capture folder should be created.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _, orbbec_cameras, _ = helpers.enumerate_cameras()
    if not orbbec_cameras:
        raise SystemExit(NO_ORBBEC_MSG)
    if args.mode == "depth":
        helpers.set_depth_mode(orbbec_cameras)
    else:
        helpers.set_color_mode(orbbec_cameras)
    helpers.assign_roles(orbbec_cameras)
    helpers.start_orbbec(orbbec_cameras)
    try:
        out_dir = helpers.capture_mode_once(
            orbbec_cameras,
            mode=args.mode,
            exposure=args.exposure,
            output_dir=args.output_root,
            open_dir=args.open,
        )
        helpers.logger.info("Saved captures to %s", out_dir)
    finally:
        helpers.stop_orbbec(orbbec_cameras)


if __name__ == "__main__":
    main()
