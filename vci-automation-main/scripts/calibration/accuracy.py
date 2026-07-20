# ruff: noqa: T201, INP001

import argparse
import json
from pathlib import Path

from charuco_calibration.charuco_calibrator import CharucoCalibrator
from controller import (
    Controller,
    ProcessingSteps,
    argmods,
    exceptions,
    stop_on_interrupt,
    timeout_input,
)
from controller.charuco_detection_omat import CaptureDetectionOMat

visuals_path = Path("visuals/calibration")


def capture_and_check(
    detection_file: str | Path,
    calib: dict,
    server_list: list[int] | None = None,
    *,
    exposure_settings: argmods.ExposureSettings | None = None,
    undistort: bool = False,
) -> None:

    global auto_trigger

    c = Controller(server_list)
    capture_o_mat = CaptureDetectionOMat(c)
    if exposure_settings:
        capture_o_mat.settings.exposure_profile = exposure_settings

    capture_o_mat.check_and_prepare_system()
    capture_o_mat.handle_previous_detections(detection_file)
    capture_o_mat.settings.detection_processing_steps = (
        ProcessingSteps.PROCESSED if undistort else ProcessingSteps.CHARUCO
    )

    c.start()

    with stop_on_interrupt():
        while True:
            command, auto_trigger = timeout_input(
                "Choose an option:\n"
                "  [Enter] Capture next image \n"
                "  [a] Auto-trigger next capture\n"
                "  [camera_id] Enter a specific camera ID to request an image\n"
                "  [x] Stop capturing - starts accuracy test\n"
                "> ",
                auto_trigger_enabled=auto_trigger,
                timeout_seconds=1,
            )
            if command.lower() == "x":
                break
            if command.lower() == "y" or command == "":
                capture_o_mat.capture_detection()
            elif command.upper()[0] in ["C", "M"]:
                if command.upper() in c.all_camera_ids:
                    capture_o_mat.save_detection_image(command.upper(), "CharucoDetection.jpg")
                else:
                    print(f"unknown camera_id {command}")
    capture_o_mat.stop_and_save_detections(detection_file)

    if calib is None:
        calib = c.get_calibration_file()
        try:
            c.check_calibration_file_sync()
        except exceptions.ServerDesyncError as e:
            print(e)
        print(
            "\nchecking with current server calib. Timestamp",
            calib.get("timestamp"),
        )
    else:
        print("\nchecking with local calib. Timestamp", calib.get("timestamp"))
    calibrator = CharucoCalibrator(detection_data=detection_file)
    calibrator.load_calibration_file(calib)
    calibrator.check_accuracy(
        error_plot_path=visuals_path / "ReprojectionError.png",
        cameras_and_boards_plot_path=visuals_path / "Board_Positions.png",
    )


auto_trigger = False
if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=(
            "Check intrinsic & extrinsics calibration accuracy with a charuco board. "
            "Detections are triggered individually in command line (or via --auto-trigger). "
            "Detections are saved locally and you can append detections with subsequent runs. "
            "You can also skip the detection and simply redo the accuracy check with --redo."
        )
    )
    parser = argmods.add_server_list_argument(parser)
    data_group = parser.add_argument_group("DATA FLOW")
    data_group.add_argument(
        "--redo",
        "-r",
        action="store_true",
        help="rerun accuracy check with previous detections",
    )
    data_group.add_argument(
        "--detection-file",
        default="Calibration/validation_detections.json",
        help="path and filename for detection json file. Default here: Calibration/validation_detections.json",
    )
    data_group.add_argument(
        "--calibration-file",
        default="SERVER",
        help="path to the calibration json to test. Pass SERVER to test the current calibration on the server. \
            Default: SERVER",
    )

    capture_group = parser.add_argument_group("IMAGE CAPTURE & PROCESSING")
    argmods.add_auto_trigger_argument(capture_group, "board detection")
    capture_group.add_argument(
        "--skip-undistortion",
        action="store_true",
        help=(
            "Skips image undistortion in processing. The resulting detection points contain raw lense distortion, "
            "and are therefore independent of the calibration file being tested "
            "(identical to the data used to calibrate in the first place). "
            "This allows you to check the accuracy of multiple different calibrations against the same detection set. "
            "Do NOT use this flag if you want to verify the system's current running state. "
            "Allowing the undistortion step gives you the exact result of how the entire pipeline behaves."
        ),
    )
    argmods.add_exposure_argument(capture_group, default="speedy")

    args = parser.parse_args()
    server_list = args.server
    auto_trigger = args.auto_trigger
    exposure_settings: argmods.ExposureSettings = args.exposure

    calib = None
    if args.calibration_file != "SERVER":
        with Path.open(args.calibration_file) as f:
            calib = json.load(f)

    if args.redo:
        if calib is None:
            c = Controller(server_list, mode="single")
            calib = c.get_calibration_file()
            print(
                "\nchecking with current server calib. Timestamp",
                calib.get("timestamp"),
            )
        else:
            print("\nchecking with local calib. Timestamp", calib.get("timestamp"))

        calibrator = CharucoCalibrator(detection_data=args.detection_file)
        calibrator.load_calibration_file(calib)
        calibrator.check_accuracy(
            error_plot_path=visuals_path / "ReprojectionError.png",
            cameras_and_boards_plot_path=visuals_path / "Board_Positions.png",
        )

    else:
        capture_and_check(
            args.detection_file,
            calib,
            server_list,
            exposure_settings=exposure_settings,
            undistort=not args.skip_undistortion,
        )
