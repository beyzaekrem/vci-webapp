# ruff: noqa: T201, INP001
import argparse
from pathlib import Path

from controller import (
    Controller,
    PreviewWriter,
    argmods,
    ask_for_new_background,
    stop_on_interrupt,
    timeout_input,
    trigger_box,
    trigger_single,
)


def main():
    # parse input
    parser = argparse.ArgumentParser(
        description=(
            "Capture, processes and download single frames from all cameras. "
            "The images are triggered individually via command line input. "
            "You can use --auto_trigger flag to automatically trigger images. "
            "This mode does not support video capture."
        )
    )
    parser = argmods.add_server_list_argument(parser)

    trigger_group = parser.add_argument_group("IMAGE TRIGGEER")
    argmods.add_auto_trigger_argument(trigger_group, "image capture")
    trigger_group.add_argument(
        "-t",
        "--time",
        type=float,
        default=None,
        help="specify a timeout after which the next image is automatically triggered",
    )
    output_group = parser.add_argument_group("OUTPUT CONTROL")
    argmods.add_output_folder_argument(output_group, default="CAPTURE")
    argmods.add_capture_name_argument(output_group, default="DATE_single")
    argmods.add_folder_mode_argument(output_group, default="clear")

    image_group = parser.add_argument_group("IMAGE CONFIGURATION")
    argmods.add_exposure_argument(image_group)
    image_group.add_argument("--no-mattes", action="store_true", help="disables mattes capture")
    image_group.add_argument(
        "--no-depth",
        action="store_true",
        help="for depth cameras: flag to request mono images instead of depth",
    )
    image_group.add_argument("--no-calib", action="store_true", help="skip calibration file download")
    image_group.add_argument("--no-backgrounds", action="store_true", help="skip background download")
    argmods.add_processing_steps_argument(image_group, default="processed")
    argmods.add_quality_argument(image_group, default="avif_ll")
    args = parser.parse_args()

    # get arguments
    timeout_seconds = args.time
    auto_trigger = args.auto_trigger or timeout_seconds is not None
    exposure_profile: argmods.ExposureSettings = args.exposure
    quality: argmods.ImageQualitySettings = args.quality
    mattes = not args.no_mattes
    processing_steps: list[str] = args.processing
    image_path = str(args.outputfolder / args.capture_name)
    folder_mode = args.folder_mode

    # capture images
    with Controller(args.server) as c:
        c.check_calibration_file_sync()

        c.set_image_path(
            output_folder=image_path,
            folder_mode=folder_mode,
        )

        try:
            mode = "COLOR" if args.no_depth else "DEPTH"
            c.set_depth_active(mode)
        except Exception as e:
            print(e, "Setting depth mode failed for some servers.")
        c.switch_mode("single")
        trigger_box("off")
        c.set_exposure_and_gain(exposure_profile.exposure, exposure_profile.gain)
        c.set_exposure_and_gain(1, 0, "depth")
        print(f"Selected {exposure_profile}")
        if not args.no_calib:
            c.grab_calibration_file(processing_steps=processing_steps)

        ask_for_new_background(c)

        image_grid_path = Path(c.path_structure.get_preview_path()).parent
        c.start()
        # debayer_malvar, debayer_interpolate, debayer_subsample
        trigger_cnt = 0
        print(f"\nOutput folder: {c.get_output_folder()}")
        with stop_on_interrupt():
            while True:
                command, auto_trigger = timeout_input(
                    auto_trigger_enabled=auto_trigger, timeout_seconds=timeout_seconds
                )
                if command != "n":
                    print()
                    with trigger_single(c):
                        print("Trigger sent. Waiting for images...")
                        image_entires = c.capture_images(
                            steps=processing_steps,
                            mattes=mattes,
                            image_format=quality.format,
                            quality=quality.quality,
                            mattes_format=quality.mattes_format,
                            mattes_quality=quality.mattes_quality,
                        )
                    print("Images recieved")
                    PreviewWriter.save_image_grid(
                        image_entires,
                        f"{image_grid_path}/frame_{str(trigger_cnt).zfill(5)}.jpg",
                        f"frame {trigger_cnt}",
                    )
                    trigger_cnt += 1
                else:
                    break
        if not args.no_calib:
            print("downloading background images...")
            c.grab_background_images(steps=processing_steps)
        print(f"Images saved to {c.get_output_folder()}")


if __name__ == "__main__":
    main()
