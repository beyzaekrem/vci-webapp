# ruff: noqa: T201, INP001, TC002

import argparse
import json
from datetime import datetime
from pathlib import Path

from natsort import natsorted
from PIL import Image

from controller import (
    Controller,
    ServersEncounteredError,
    argmods,
    boolean_user_input,
    camera_beep,
    merge_calib_jsons,
    stop_on_interrupt,
    timeout_input,
    trigger_box,
    trigger_single,
)


class Status:
    no_detection = "\033[31m"  # red
    good = "\033[32m"  # green
    overexposed = "\033[36m"  # cyan
    underexposed = "\033[34m"  # blue


fps = 15


def capture_and_calibrate(args: argparse.Namespace) -> None:
    exposure_profile: argmods.ExposureSettings = args.exposure
    auto_trigger: bool = args.auto_trigger
    output_folder: str = args.outputfolder
    all_types: bool = args.all_types

    underexposure_limit: float = 0.80
    overexposure_limit: float = 0.95

    c = Controller(args.server)

    c.switch_mode("calibration")
    c.set_depth_active("COLOR")
    trigger_box("off")

    if all_types:
        print("seleced: all camera types")
        requested_camera_ids = c.all_camera_ids
    else:
        requested_camera_ids = c.cameras_of_type("C")

    input(
        f"Selected {exposure_profile}. Please turn the lights to {exposure_profile.illumination}%. Continue [Enter]: "
    )
    input(
        f"\n{len(requested_camera_ids)} cameras connected and selected for color calibration. Please confirm [Enter] or abort. "
    )
    try:
        previous_raw_calib = c.get_raw_calibration()
        with Path(f"{output_folder}/previous_calibration_dome.json").open("w") as f:
            json.dump(previous_raw_calib, f, indent=2)
        print(f"previous calibration saved to --> {f'{output_folder}/previous_calibration_dome.json'}")
    except ServersEncounteredError:
        previous_raw_calib = None
        print("failed to get previous calibration from server")
    c.set_exposure_and_gain(exposure_profile.exposure, exposure_profile.gain)
    c.start()
    all_successful_detections = {}
    display_info = {cam_id: ["no detection", Status.no_detection] for cam_id in requested_camera_ids}
    display_info = {cam_id: display_info[cam_id] for cam_id in natsorted(display_info.keys())}
    trigger_cnt = 0
    with stop_on_interrupt():
        while True:
            command, auto_trigger = timeout_input(
                "Capture Next [Y,n] or [a] for auto-trigger. Or enter camera_id to request image ",
                auto_trigger_enabled=auto_trigger,
                timeout_seconds=1,
            )
            trigger_cnt += 1
            detection_results = []
            if command == "n":  # stop detections
                print("stopping.")
                break
            if command.lower in ["y", ""]:
                with trigger_single(c):
                    print("trigger and wait for color checker detections")
                    detection_results = c.color_checker_detection(
                        requested_camera_ids=requested_camera_ids,
                        overexposure_limit=overexposure_limit,
                        underexposure_limit=underexposure_limit,
                        rgb_images=False,
                    )
            elif command.upper() in requested_camera_ids:
                requested_camera_id = command.upper()
                print(f"collecting image for {command}")
                with trigger_single(c):
                    detection_results = c.color_checker_detection(
                        overexposure_limit=overexposure_limit,
                        underexposure_limit=underexposure_limit,
                        rgb_images=True,
                        requested_camera_ids=[requested_camera_id],
                    )
                for _, image_entries in detection_results:
                    for image_entry in image_entries:
                        # should only be one image since we force the input command to accept exactly one camera id
                        i: Image = image_entry.get_image()
                        p = Path("visuals/calibration/ColorCalibration.jpg")
                        p.parent.mkdir(exist_ok=True)
                        i.save(p)
                        print("\n----->  image saved to ColorCalibration.jpg")
            else:
                print(f"unknown command or camera_id {command}")
                continue

            # process detection results

            for detection_info, _ in detection_results:
                frame_idx = detection_info.get("frame_idx")
                camera_ids = detection_info.get("camera_ids")
                detection_success = detection_info.get("detection_success")
                calib_file_entries = detection_info.get("calib_file_entries")
                max_exposures = detection_info.get("max_exposures")
                in_exposure_range = detection_info.get("in_exposure_limit")
                exposure_limit_tests = detection_info.get("exposure_limit_tests")
                exposure_limits = detection_info.get("exposure_limit")
                for idx in range(len(camera_ids)):  # for each camera in this server
                    if detection_success[idx]:
                        if in_exposure_range[idx]:
                            # save successful calibrations
                            all_successful_detections[camera_ids[idx]] = calib_file_entries[idx]

                        # update display info
                        status = Status.good
                        if max_exposures[idx] < exposure_limits[0]:
                            status = Status.underexposed
                        elif max_exposures[idx] > exposure_limits[1]:
                            status = Status.overexposed
                        if camera_ids[idx] not in all_successful_detections or in_exposure_range[idx]:
                            # once we have a successfull detection, only update if we have a newer sucessfull detection.
                            display_info[camera_ids[idx]] = [
                                f"{exposure_limit_tests[idx]} ({max_exposures[idx]}) in frame {frame_idx}",
                                status,
                            ]

            # display which cameras are done/not done. Overexposed/underexposed
            colums = 3
            print()
            for cnt, (cam_id, info) in enumerate(display_info.items()):
                print(
                    f'|   {info[1]}{cam_id:<6}{f"({c.system_layout.camera_position(cam_id)})":<20} {info[0]:<35}\033[0m\
                              ',
                    end="|\n" if (cnt + 1) % colums == 0 else "",
                )
            print(f"\nSuccessful calibrations: {len(all_successful_detections)} / {len(requested_camera_ids)}")
            print()

            if len(all_successful_detections) == len(requested_camera_ids):
                camera_beep("long")
                stop = boolean_user_input("All cameras have a successful calibration. Stop?")
                if stop:
                    break
    c.stop()
    print(f"\n{len(list(all_successful_detections.values()))} successful calibrations\n")

    new_calibration = {
        "meta": "color calibration",
        "timestamp": datetime.now().strftime("%Y.%m.%d %H:%M"),
        "cameras": list(all_successful_detections.values()),
    }
    with Path(f"{output_folder}/calib_color.json").open("w") as f:
        json.dump(new_calibration, f, indent=2)
        print(
            "Saved new color calibration locally to",
            f"{output_folder}/calib_color.json",
        )

    if previous_raw_calib is not None:
        new_calibration["meta"] = previous_raw_calib.get("meta")
        new_calibration = merge_calib_jsons(previous_raw_calib, new_calibration)

    with Path(f"{output_folder}/calibration_dome.json").open("w") as f:
        json.dump(new_calibration, f, indent=2)
        print(
            "Saved merged calibration locally to",
            f"{output_folder}/calibration_dome.json",
        )
    send = boolean_user_input("Send new merged calibration to servers?")
    if send:
        c.set_raw_calibration(new_calibration)

    c.set_software_trigger(False)
    c.close()
    print("Done")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Checks brightness and calibrates color response with xrite color checker board."
            "The images are triggered indivdiually in command line (or via --auto-trigger)."
        )
    )
    parser = argmods.add_server_list_argument(parser)
    capture_group = parser.add_argument_group("IMAGE CAPTURE")
    argmods.add_auto_trigger_argument(capture_group, "board detection")
    argmods.add_exposure_argument(capture_group, default="default")
    capture_group.add_argument(
        "--all-types",
        action="store_true",
        default=False,
        help="run detection on all camera types. Mono and Depth in addition to Color cameras.",
    )
    files_group = parser.add_argument_group("OUTPUT")
    files_group.add_argument(
        "--outputfolder",
        "-o",
        type=str,
        default="Calibration/",
        help="Output folder for calibration_dome.json and calib_color.json. Default here: Calibration/",
    )
    args = parser.parse_args()
    capture_and_calibrate(args)
