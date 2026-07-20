# ruff: noqa: T201, INP001

import argparse
import json
import re
from pathlib import Path

import cv2
from natsort import natsorted
from PIL import Image
from teague.calibration import Calibration  # from vci-common packages/teague - looking_glass viewer

from charuco_calibration.camera import Camera, load_dome_format
from controller import Controller, argmods

# Tuple format: (start_frame, end_frame_exclusive_or_none, step)
# None is used for the exclusive end when defining a single frame index.


def arugments() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Rectify mono images of an image set")
    parser.add_argument(
        "--folder",
        type=argmods.output_paths_argument.output_folder_type,
        help="path to the image set. Supports presets TEST CAPTURE etc",
        default="TEST/2025_10_28_ir_poses",
    )
    return parser.parse_args()


def main() -> None:
    args = arugments()

    parent_folder = Path(args.folder)
    assert parent_folder.exists, f"Folder {parent_folder} cannot be found"
    # expected:
    fps = 25
    image_format = "avif"
    mask_format = "avif"
    frame_zero_is_background = True

    check_image_file_size = True
    image_min_size = (
        400 * 1000
    )  # 490 KB # image is smaller when no subejct. the background scene is not as high frequency
    image_max_size = 1600 * 1000  # 1.3 MB

    mask_min_size = 500  # masks can be *really* small when noone is in this view
    mask_max_size = 1000 * 1000  # when subject is close to the camera - lots of white space - larger mask file

    image_size = [4608 // 2, 5328 // 2]

    exclude_cameras = ["C0030"]

    check_servers = True

    stage_controller: Controller | None = None
    if check_servers:
        try:
            stage_controller = Controller()
            stage_controller.switch_mode("replay")
        except Exception:
            print(Warning("could not connect to vci capture servers. Cannot run full check."))

    image_sets_paths = natsorted(parent_folder.iterdir())
    print(f"\nrunning check in {parent_folder}")
    for image_set_path in image_sets_paths:
        print(f"\nchecking {image_set_path.name}...")
        if not image_set_path.is_dir():
            continue

        # check calibration
        calib_file = image_set_path / "calibration_dome.json"
        try:
            with calib_file.open() as f:
                calib_json = json.load(f)
        except:
            assert False, f"Missing {calib_file}"

        assert (
            calib_json["meta"]["capture"]["fps"] == fps
        ), f"fps should be {fps}. Older calibs dont contain this meta info"
        recording_name = calib_json["meta"]["name"]
        assert (
            recording_name == image_set_path.name
        ), "the folder is expected to match the name of the recording in the calib"

        # check if camera orientations are correct.
        loaded_calib = Calibration(calibration=calib_json, load_color=True, load_mono=True, load_depth=True)
        assert loaded_calib.import_settings.legacy.c0004_is_origin == False, "Calib origin shoudl bot in in C0004"
        assert (
            loaded_calib.import_settings.legacy.up_is_down == False
        ), "Calib coordinate system should not have flipped vertical axis"

        # check for missing cameras
        frame_folders = natsorted(list(image_set_path.glob("frame_*")))
        assert len(frame_folders) != 0, f"No frame_* folders found in directory {image_set_path}"

        camera_names_first_frame = find_rbg_or_images(
            frame_folders[0]
        ).keys()  # camera names and image paths for first frame
        assert len(camera_names_first_frame) != 0, f"No images found in frame folder {frame_folders[0]}"

        print(
            f"{image_set_path.name} has {len(frame_folders)} frame folders, captured by {len(camera_names_first_frame)} cameras"
        )

        # check if the camera ids from the first folder match what the servers have
        if stage_controller is not None:
            stage_controller.set_recording_name(recording_name, invalid_ok=True)
            server_camera_names = []
            for server_idx in range(len(stage_controller.servernames)):
                s = stage_controller.get_status(server_idx)
                server_rec_name = s.get("recording_name", "")
                if server_rec_name != recording_name:
                    print(
                        Warning(
                            f"sever {stage_controller.servernames[server_idx]} does not have recording {recording_name}"
                        )
                    )
                    continue

                server_camera_names.extend(s["camera_ids"])
                frame_count = s.get("frame_count")
                if frame_zero_is_background:
                    frame_count = frame_count - 1
                assert frame_count == len(
                    frame_folders
                ), f"Server {stage_controller.servernames[server_idx]} has frame count {frame_count} but our download folder contains {len(frame_folders)} frames"

            for cam in exclude_cameras:
                if cam in server_camera_names:
                    server_camera_names.remove(cam)
            assert set(camera_names_first_frame) == set(
                server_camera_names
            ), "the folders should contain the same cameras as the servers have for the recording"

        # check if all other folders share the the same camera_ids
        for frame_folder in frame_folders:
            image_path_dict = find_rbg_or_images(frame_folder, image_format)
            camera_names = image_path_dict.keys()
            assert (
                set(camera_names) == camera_names_first_frame
            ), f"all folders are expected to contain images of the same {len(camera_names_first_frame)} cameras in {image_format} format. Frame {frame_folder.name} does not have the expected images.."

            mask_path_dict = find_image_paths_in_folder(frame_folder / "mask" / f"mask_<camera_id>.{mask_format}")
            mask_cameras = mask_path_dict.keys()
            assert set(camera_names) == set(
                mask_cameras
            ), f"mask folders are expected to contain masks of the same {len(camera_names_first_frame)} cameras in {image_format} format. Frame {frame_folder.name} does not have the expected masks."

            if check_image_file_size:
                check_image_file_sizes(image_path_dict, image_min_size, image_max_size, f"{frame_folder.name}")
                check_image_file_sizes(mask_path_dict, mask_min_size, mask_max_size, f"{frame_folder.name}")
            # check_image_size(image_path_dict, [2304, 5328 // 2])

        # check if calib contains the cameras
        cameras: list[Camera] = load_dome_format(calib_json, camera_names_first_frame)
        cameras_in_calib = [c.name for c in cameras]
        assert set(camera_names_first_frame) == set(cameras_in_calib)

        # check background images
        background_path_dict = find_image_paths_in_folder(
            image_set_path / "background" / f"*_<camera_id>.{image_format}"
        )
        if len(background_path_dict) == 0:
            background_path_dict = find_image_paths_in_folder(
                image_set_path / "background" / f"<camera_id>.{image_format}"
            )
        assert set(background_path_dict.keys()) == set(
            camera_names_first_frame
        ), f"background folder is expected to contain background of the same {len(camera_names_first_frame)} cameras in {image_format} format."

        print("    checked.")

        # check the preview folder
        preview_folder = image_set_path / "preview"
        assert preview_folder.exists(), f"{image_set_path.name} is missing preview folder"
        assert (
            preview_folder / "background.jpg"
        ).exists(), f"{image_set_path.name} is missing combined background in preview folder"
        combined_frames = list(preview_folder.glob("frame_*.jpg"))
        assert (
            len(combined_frames) == 1
        ), f"{recording_name} should have exactly one combined preview frame. Found: {combined_frames}"
        if frame_zero_is_background:
            assert combined_frames[0].name == "frame_00001.jpg"
        else:
            assert combined_frames[0].name == "frame_00000.jpg"

        # check iamge_grid
        image_grid_video_path = preview_folder / "image_grid.mp4"
        assert (image_grid_video_path).exists(), f"{recording_name} is missing {image_grid_video_path}"
        preview_video = cv2.VideoCapture(str(image_grid_video_path))
        frames = int(preview_video.get(cv2.CAP_PROP_FRAME_COUNT))
        assert (
            abs(frames - (frame_count // 6)) <= 1
        ), f"{recording_name} frame count of preview_video is expected to be {frame_count//6}. But it is {frames}"


def check_image_size(image_path_dict: dict, image_size: list[int]) -> None:
    for image_path in image_path_dict.values():
        image = Image.open(image_path)
        actual_size = list(image.size)
        assert (
            actual_size == image_size
        ), f"Image {image_path} is expected to have image size {image_size} but it was {actual_size}"


def check_image_file_sizes(image_path_dict: dict, image_min_size: int, image_max_size: int, frame_desc: str) -> None:
    # check the image sizes
    for image_path in image_path_dict.values():
        image_data_size = image_path.stat().st_size
        if not (image_min_size <= image_data_size <= image_max_size):
            image = Image.open(image_path)
            extrema = image.convert("L").getextrema()
            s = f"{frame_desc} {image_path.name}"
            if extrema == (0, 0):
                print(Warning(f"image {s} is all black"))
            elif extrema == (1, 1) or extrema == (255, 255):
                print(Warning(f"image {s} is all white"))
            elif extrema[0] == extrema[1]:
                print(Warning(f"image is all {extrema}"))
            else:
                msg = f"Unexpected image data size: {image_path} is {image_path.stat().st_size} bytes, out of range [{image_min_size}, {image_max_size}]"
                raise AssertionError(msg)


def find_rbg_or_images(frame_folder: Path, extension: str = "*") -> dict[str, Path]:
    """
    Checks "rgb" or "image" pattern for camera_ids and paths.
    """
    frame_folder = Path(frame_folder)
    image_path_dict = find_image_paths_in_folder(frame_folder / "rgb" / f"<camera_id>.{extension}")
    if len(image_path_dict) == 0:
        image_path_dict = find_image_paths_in_folder(frame_folder / "image" / f"*_<camera_id>.{extension}")
    return image_path_dict


def find_image_paths_in_folder(path_pattern: Path | str) -> dict[str, Path]:
    """
    Finds the camera_ids and image paths that in a folder as specified by the path_pattern.
    Example path pattern: "my/capture_001 / image / *_<camera_id>.avif"

    Returns:
        dict[camera(str) , image_path (Path)]
    """
    path_pattern = Path(path_pattern)
    frame_dir = path_pattern.parent
    filename_template = path_pattern.name
    if "*" in str(frame_dir):
        msg = f"Parent folder cannot contain wildcards: {frame_dir}"
        raise ValueError(msg)
    if "(.*)" in str(path_pattern):
        msg = f"Regex capture groups '(.*)' are not allowed as that would interfere with the <camera_id> search. Pattern: {path_pattern}"
        raise ValueError(msg)
    if "<camera_id>" not in str(filename_template):
        msg = f"The placeholder <camera_id> must be in the filename: {filename_template}."
        raise ValueError(msg)

    # glob for file serach (replace both <camera_id> and .* with *)
    glob_str = path_pattern.name.replace("<camera_id>", "*")

    # Regex:
    # - Escape dots (\.)
    # - Replace '*' with non-greedy '.*?' to prevent it from 'eating' the camera_id
    # - Replace '<camera_id>' with the only capture group '(.*)'
    re_str = filename_template.replace(".", "\\.").replace("*", ".*?").replace("<camera_id>", "(.*)")
    regex = re.compile(f"^{re_str}$")

    camera_to_path: dict[str, Path] = {}

    for img_path in frame_dir.glob(glob_str):
        match = regex.match(img_path.name)
        if match:
            # Because we blocked other (.*), match.group(1) is guaranteed to be <camera_id>
            camera_id = match.group(1)
            camera_to_path[camera_id] = img_path

    return camera_to_path


if __name__ == "__main__":
    main()
