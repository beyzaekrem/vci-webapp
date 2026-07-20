# ruff: noqa: T201, INP001
import argparse
import json
from pathlib import Path

from controller import (
    Controller,
    PreviewWriter,
    ProcessingSteps,
    argmods,
    boolean_user_input,
    stop_on_interrupt,
    trigger_single,
)

grid_path = Path("visuals/calibration")

software_trigger = False

# setting the rotation is the first step in setting up the system
# as such, we intentionally avoid asking for processing steps that would require the camera to be
# calibrated (color correcitons and undistortions)
ROTATED = ProcessingSteps.TINY_UNCALIBRATED
UN_ROTATED = ProcessingSteps.OVERWRITE_NO_ROTATION(ProcessingSteps.TINY_UNCALIBRATED)

QUALITY = argmods.HIGH_QUALITY_JPG  # hight quality jpg pairs nicely with TINY processing


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactively set rotation per camera.")
    parser = argmods.add_server_list_argument(parser)
    image_group = parser.add_argument_group("IMAGE CONFIGURATION")
    argmods.add_exposure_argument(image_group)
    output_group = parser.add_argument_group("OUTPUT")
    output_group.add_argument(
        "--output",
        "-o",
        type=str,
        default="Calibration/camera_rotation.json",
        help="save path for local copy of camera rotations. Default: Calibration/camera_rotations.json",
    )
    args = parser.parse_args()
    exposure_profile: argmods.ExposureSettings = args.exposure
    with Controller(args.server, mode="single") as c:
        c.set_exposure_and_gain(exposure_profile.exposure, exposure_profile.gain)
        c.set_software_trigger(state=software_trigger)
        send_local_file(c, args.output)
        interactive_set_rotation(c)

        # grabs copy of rotation file.
        with Path.open(args.output, "w") as f:
            json.dump(c.get_camera_rotations(), f, indent=2)
            print(f"\nSaved rotation copy locally --> {args.output}")


def send_local_file(c: Controller, output: str | Path) -> None:
    try:
        with Path.open(output) as f:
            d = json.load(f)
            c.set_camera_rotations(d)
        print("Sent local rotation file to servers.")
    except FileNotFoundError:
        print(f"No local file found at {output}.")


def interactive_set_rotation(c: Controller) -> None:
    camera_rotations: dict[str:int] = c.get_camera_rotations()
    camera_ids = c.all_camera_ids

    missing_rotation = [cam_id for cam_id in camera_ids if cam_id not in camera_rotations]

    print(f"\nMissing camera_rotations for {len(missing_rotation)} cameras.")
    with stop_on_interrupt():
        for idx, camera_id in enumerate(missing_rotation):
            print(f"\n{camera_id} {idx}/{len(missing_rotation)}")
            interactive_set_rotation_for_camera(c, camera_id, camera_rotations)

        while True:
            print("\nCapturing all known rotations...")
            _get_image(
                c,
                list(camera_rotations.keys()),
                ROTATED,
            )
            print("Review the image. Check for incorrect rotations.")
            camera_id = input("Input camera_id of camera you want to rotate or [n] to stop: ")
            if camera_id.lower() == "n":
                break
            if camera_id in camera_ids:
                interactive_set_rotation_for_camera(c, camera_id, camera_rotations)
            else:
                print(f"{camera_id} is not a valid camera_id")

    c.stop()


def interactive_set_rotation_for_camera(
    c: Controller,
    camera_id: str,
    camera_rotations: dict,
) -> None:
    done = False
    try:
        while not done:
            _get_image(c, camera_id, UN_ROTATED)
            rot_dir = input(
                f"input desired new rotation for {camera_id}. Rotate to the left, right, or no rotation [l, r, n] "
            ).lower()
            rot_values = {"l": 1, "r": -1, "n": 0}
            rot = rot_values.get(rot_dir)
            if rot is None:
                print(f"{rot_dir} is not a valid input")
                continue

            camera_rotations[camera_id] = rot
            c.set_camera_rotations(camera_rotations)
            _get_image(c, camera_id, ROTATED)
            done = boolean_user_input(
                f"New rotation applied to {camera_id}. Please check the result. Keep this rotation?",
                default_choice=False,
            )
    except Exception as e:
        print(f"{e}\nsetting rotation of {camera_id} failed.")


def _get_image(c: Controller, camera_ids: str, steps: dict) -> None:
    if not isinstance(camera_ids, list):
        camera_ids = [camera_ids]
    c.start()

    with trigger_single(c):
        image_entries = c.capture_images(
            steps=steps,
            requested_camera_ids=camera_ids,
            image_format=QUALITY.format,
            quality=QUALITY.quality,
            mattes=False,
        )
    if len(image_entries) != 0:
        p = grid_path / "RotationCalibration.jpg"
        PreviewWriter.save_image_grid(image_entries, p, "Rotations")
        print(f"\n----->  image saved to {p}")
    else:
        print("no image captured")


if __name__ == "__main__":
    main()
