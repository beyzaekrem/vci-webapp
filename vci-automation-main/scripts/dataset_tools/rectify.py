# ruff: noqa: T201, INP001
import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from charuco_calibration.camera import Camera, load_dome_format
from charuco_calibration.mutlical_wrap.transform_origin import (
    compute_camera_center_bbox,
)
from controller import argmods

# Tuple format: (start_frame, end_frame_exclusive_or_none, step)
# None is used for the exclusive end when defining a single frame index.


@dataclass
class StereoTripplet:
    mono_left: Camera
    color_center: Camera | None
    mono_right: Camera

    @property
    def cameras(self) -> list[Camera]:
        return [self.mono_left, self.color_center, self.mono_right]


@dataclass
class RectificationCalib:
    rectified_intrinsics: np.array
    baseline: float


def arugments() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Rectify mono images of an image set")
    parser.add_argument(
        "--image-set",
        type=argmods.output_paths_argument.output_folder_type,
        help="path to the image set. Supports presets TEST CAPTURE etc",
        default="TEST/2025_10_28_ir_poses",
    )
    return parser.parse_args()


def main() -> None:
    args = arugments()

    input_path = Path(args.image_set)
    calib_file = input_path / "calibration_dome.json"
    with calib_file.open() as f:
        calib_json = json.load(f)

    frame_folders = list(input_path.glob("frame_*"))
    camera_names = camera_names_in_folder(frame_folders[0])
    print(f"{input_path.name} has {len(frame_folders)} frame folders, captured by {len(camera_names)} cameras")

    cameras: list[Camera] = load_dome_format(calib_json, camera_names)
    cameras: dict[str, Camera] = dict(zip(camera_names, cameras))
    stereo_triplets: list[StereoTripplet] = find_stereo_tripplets(cameras)
    print(f"Found {len(stereo_triplets)} stereo rigs")

    for frame_folder in frame_folders:
        print(frame_folder)
        for idx, tripplet in enumerate(stereo_triplets):
            print(f"rectify stereo rig: {[c.name for c in tripplet.cameras]} -- {idx} / {len(stereo_triplets)}")
            images = [cv2.imread(str(frame_folder / "rgb" / (c.name + ".png"))) for c in tripplet.cameras]
            print("images loaded")
            # Check if any image failed to load
            if any(img is None for img in images):
                print("Error: One or more images failed to load. Check paths.")
                continue

            save_fused_image(images, "FUSED_Input.jpg")

            rectified_images, rect_calib = rectify(tripplet.mono_left, tripplet.mono_right, images[0], images[2])
            rect_calib: RectificationCalib = rect_calib
            save_fused_image(rectified_images, "FUSED_Rectified.jpg")

            output_folder = input_path / frame_folder / "rectified"
            output_folder.mkdir(exist_ok=True)

            for img, pos, camera in zip(
                rectified_images, ["left", "right"], [tripplet.mono_left, tripplet.mono_right], strict=True
            ):
                desc = f"rig{idx}_{pos}_{camera.name}"
                cv2.imwrite(str(output_folder / (desc + ".png")), img)

            with Path(output_folder / (f"rig{idx}.txt")).open("w") as f:
                k_str = " ".join(map(str, rect_calib.rectified_intrinsics.flatten()))
                f.write(f"{k_str}\n")
                f.write(f"{rect_calib.baseline}\n")


def rectify(
    cam_left: Camera, cam_right: Camera, image_left: np.array, image_right: np.array
) -> tuple[np.array, np.array, RectificationCalib]:
    D_ZERO = np.zeros((5, 1))

    current_height, current_width = image_left.shape[:2]
    img_size = (current_width, current_height)  # OpenCV expects (Width, Height)

    calib_width, _ = cam_left.image_size
    scale_factor = current_width / calib_width
    intrisic_left = cam_left.intrinsic.copy() * scale_factor
    intrinsic_right = cam_right.intrinsic.copy() * scale_factor

    # 2. Calculate Relative Extrinsics (R and T)
    extrinsic_left = cam_left.extrinsic_matrix
    extrinsic_right = cam_right.extrinsic_matrix
    # Calculate extrisnic_left_to_right = E_R @ inv(E_L)
    extrisnic_left_to_right = extrinsic_right @ np.linalg.inv(extrinsic_left)
    relative_rotation = extrisnic_left_to_right[:3, :3]  # Relative Rotation (3x3)
    relative_translation = extrisnic_left_to_right[:3, 3]  # Relative Translation (3x1)

    D_ZERO = np.zeros((5, 1))  # distortion

    # --- Compute Rectification Parameters ---
    R_L, R_R, new_projection_left, new_projection_right, Q, roi_L, roi_R = cv2.stereoRectify(
        cameraMatrix1=intrisic_left,
        distCoeffs1=D_ZERO,
        cameraMatrix2=intrinsic_right,
        distCoeffs2=D_ZERO,
        imageSize=img_size,
        R=relative_rotation,
        T=relative_translation,
        flags=cv2.CALIB_ZERO_DISPARITY,
        alpha=-1,  # Crops the images to only show valid pixels
    )
    mapL_x, mapL_y = cv2.initUndistortRectifyMap(
        cameraMatrix=intrisic_left,  # Original Intrinsic (or undistorted)
        distCoeffs=D_ZERO,  # Must be zero!
        R=R_L,  # Rotation matrix for rectification
        newCameraMatrix=new_projection_left,  # New projection matrix
        size=img_size,
        m1type=cv2.CV_32FC1,
    )

    mapR_x, mapR_y = cv2.initUndistortRectifyMap(
        cameraMatrix=intrinsic_right,  # Original Intrinsic
        distCoeffs=D_ZERO,  # Must be zero!
        R=R_R,  # Rotation matrix for rectification
        newCameraMatrix=new_projection_right,  # New projection matrix
        size=img_size,
        m1type=cv2.CV_32FC1,
    )

    # Rectify
    img_rect_L = cv2.remap(image_left, mapL_x, mapL_y, interpolation=cv2.INTER_LINEAR)  # Faster than cubic
    img_rect_R = cv2.remap(image_right, mapR_x, mapR_y, interpolation=cv2.INTER_LINEAR)

    # the recitiifed intrinsic matrix, shapred by both cameras
    rectified_K = new_projection_left[:3, :3]
    fx = new_projection_right[0, 0]
    baseline = abs(new_projection_right[0, 3] / fx)
    return (
        [img_rect_L, img_rect_R],
        RectificationCalib(rectified_intrinsics=rectified_K, baseline=baseline),
    )


def save_fused_image(images, output="Fused.jpg") -> None:
    # Handle different image channels (Convert mono/grayscale to 3-channel for stacking)
    processed_images = []
    for img in images:
        if len(img.shape) == 2 or img.shape[2] == 1:
            # If grayscale/mono (2D or 1-channel), convert to 3-channel BGR for display
            # This is necessary for horizontal concatenation (hconcat) with the 3-channel RGB image
            processed_images.append(cv2.cvtColor(img, cv2.COLOR_GRAY2BGR))
        else:
            processed_images.append(img)

    # 4. Resize images to a common height for clean concatenation
    # We will use the height of the central RGB image as the reference.
    rgb_height = processed_images[1].shape[0]
    resized_images = []

    for img in processed_images:
        current_height = img.shape[0] // 8
        current_width = img.shape[1] // 8

        if current_height != rgb_height:
            # Calculate new width to maintain aspect ratio
            new_width = int(current_width * (rgb_height / current_height))
            resized_img = cv2.resize(img, (new_width, rgb_height), interpolation=cv2.INTER_LINEAR)
            resized_images.append(resized_img)
        else:
            resized_images.append(img)

    # 5. Concatenate the three images horizontally
    fused_image = cv2.hconcat(resized_images)
    # 6. Display the fused image
    cv2.imwrite(output, fused_image)


def find_stereo_tripplets(
    cameras: dict[str, Camera],
    distance_threshold: float = 0.4,  # 40 cm
    up_vector=np.array([0.0, 1.0, 0.0]),
) -> list[StereoTripplet]:
    """
    Finds stereo tripplets (mono_left, rgb_cam, mono_right).
    The mono_left corresponds to the left eye if you were looking at the scene the same way as the stereo rig.
    """

    stereo_triplets = []
    assigned_cameras = []
    # Iterate through every camera to find the center of a rig
    for center_name, center_cam in cameras.items():
        if center_name in assigned_cameras:
            continue

        center_pos = center_cam.world_pos
        current_rig_members = {center_name: center_cam}
        # Find all cameras close (less than 40 cm) to the potential rig center
        for other_name, other_cam in cameras.items():
            if other_name == center_name or other_name in assigned_cameras:
                continue

            other_pos = other_cam.world_pos
            distance = np.linalg.norm(center_pos - other_pos)
            if distance < distance_threshold:
                current_rig_members[other_name] = other_cam

        # A valid rig must contain at least 2 cameras (2 Mono, 1 RGB)
        if len(current_rig_members) >= 2:
            # sort into mono/color
            mono_candidates = [cam for id, cam in current_rig_members.items() if id.startswith("M")]
            rgb_candidate = [cam for id, cam in current_rig_members.items() if not id.startswith("M")]

            # sort mono1 and 2 into left and right
            if len(mono_candidates) == 2 and len(rgb_candidate) == 1:
                # Found a valid rig of 2 Mono and 1 RGB
                mono_cam1 = mono_candidates.pop()
                mono_cam2 = mono_candidates.pop()
                rgb_cam = rgb_candidate.pop()

                center = compute_camera_center_bbox([cam.extrinsic_matrix for cam in current_rig_members.values()])
                V_center_to_origin = np.array([0, 0, 0]) - center
                V_center_to_1 = mono_cam1.world_pos - center

                R_Dir = np.cross(V_center_to_origin, up_vector)  # points to the right of the rig center
                R_Dir = R_Dir / np.linalg.norm(R_Dir)

                dot_product = np.dot(V_center_to_1, R_Dir)
                if dot_product > 0:
                    # Camera 1 is on the RIGHT side of the V_Ref line
                    mono_right = mono_cam1
                    mono_left = mono_cam2
                else:
                    # Camera 1 is on the LEFT side of the V_Ref line
                    mono_right = mono_cam2
                    mono_left = mono_cam1

                # --- Store Triplet and Mark as assinged ---
                stereo_triplets.append(StereoTripplet(mono_left=mono_left, color_center=rgb_cam, mono_right=mono_right))
                assigned_cameras.extend([mono_cam1, mono_cam2, rgb_cam])
    return stereo_triplets


def camera_names_in_folder(frame_folder) -> list[str]:
    camera_names = (frame_folder / "rgb").glob("*.png")
    return [p.stem for p in camera_names]


if __name__ == "__main__":
    main()
