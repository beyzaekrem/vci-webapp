# ruff: noqa: T201

import argparse
import json
from pathlib import Path

from charuco_calibration import CharucoCalibrator, DetectionData
from controller import Controller, PreviewWriter, ProcessingSteps, argmods
from controller.charuco_detection_omat import CaptureDetectionOMat

visuals_path = Path("visuals/calibration")


def plot_detections(calibration_file: str | Path, detections_file: str | Path) -> None:
    with Path(calibration_file).open() as f:
        calib = json.load(f)

    if detections_file is not None and detections_file != "None":
        if not Path(detections_file).exists():
            msg = f"Detections file {detections_file} could not be found"
            raise FileNotFoundError(msg)
        detections = DetectionData.load_from_file(detections_file)

        print("\nplotting calib from", calib.get("timestamp"))
        with Controller() as c:
            if all(camera_id in c.all_camera_ids for camera_id in detections.camera_names):
                print("Capturing real images for detection grid.")
                image_grid, grid_size = CaptureDetectionOMat.capture_image_grid(
                    c, visuals_path / "CharucoDetectionGrid.jpg", detections.camera_names
                )
            else:
                print(f"Not capturing real images for detection grid. \
                        {[camera_id for camera_id in detections.camera_names if camera_id not in c.all_camera_ids]} \
                            are in calibration but currently not active.")
                print()
                image_grid = None
                grid_size = PreviewWriter.calcualte_grid_size(detections.camera_names)
        detections.display_detected_points(visuals_path / "CharucoDetectionGrid.jpg", image_grid, grid_size)

        calibrator = CharucoCalibrator(detection_data=detections)
        calibrator.load_calibration_file(calib)
        calibrator.check_accuracy(
            error_plot_path=visuals_path / "ReprojectionError.png",
            cameras_and_boards_plot_path=visuals_path / "Board_Positions.png",
        )
        print("\n")


def plot_camera_positions(calibration_file: str | Path, *, interactive: bool = False) -> None:
    if not Path(calibration_file).exists():
        raise FileNotFoundError
    # displays camera positions
    from reformat_camorph.reformat import (  # from vci-common submodule  # noqa: PLC0415
        camorph,
        visualize,
    )

    cams = camorph.read_cameras(
        "dome",
        calibration_file,
        images_half_resolution=False,
    )
    path = None if interactive else visuals_path / "camera_positions_plt.png"
    visualize(cams, path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=("Plot calibration parameters."),
    )
    parser = argmods.add_server_list_argument(parser)

    input_group = parser.add_argument_group("INPUT")
    input_group.add_argument(
        "--live",
        action="store_true",
        help="Pull calibration from servers. Processing applied to data as per --processing.",
    )
    argmods.add_processing_steps_argument(input_group)
    input_group.add_argument(
        "--no-rotation",
        action="store_true",
        default=False,
        help="Disables autoamtic rotation that compensates for hardware setup.",
    )
    input_group.add_argument(
        "--calibration_file",
        "-c",
        type=str,
        default="Calibration/calibration_dome.json",
        help="Path to the calibration file to visualize",
    )
    input_group.add_argument(
        "--detections-file",
        "-d",
        type=str,
        default=None,
        help="optional: The path to a detections.json file to show the detected charuco points in the camera views \
            and in projected 3D space",
    )
    input_group.add_argument("-i", "--interactive", action="store_true", default=False)
    args = parser.parse_args()

    if args.live:
        print("get calibration from live servers")
        with Controller(args.server) as c:
            c.switch_mode("single")
            processing = args.processing
            if args.no_rotation:
                processing = ProcessingSteps.OVERWRITE_NO_ROTATION(processing)
            data = c.get_calibration_file(processing_steps=processing)
            calibration_file = "/tmp/calib_plot.json"

            with Path(calibration_file).open("w") as f:
                json.dump(data, f, indent=2)
    else:
        calibration_file = Path(args.calibration_file)
        print(f"open local calibration file from {calibration_file}")
        if calibration_file.is_dir():
            calibration_file = calibration_file / "calibration_dome.json"
        if not calibration_file.exists():
            msg = f"{calibration_file} does not exist."
            raise FileNotFoundError(msg)

    plot_detections(calibration_file, args.detections_file)
    plot_camera_positions(calibration_file, interactive=args.interactive)
