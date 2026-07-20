import argparse
import json
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from charuco_calibration.camera import Camera, load_dome_format


def quick_hull_check(cameras: dict[str, Camera], masks: dict[str, np.array], voxel_count=64 * 2):
    # 1. Define the 3D Search Space
    # Use camera positions to estimate a bounding box if you don't have one
    all_pos = np.array([c.world_pos for c in cameras.values()])
    # Create a grid around the center (adjust 'scale' based on your scene)
    stage_radius = 2.5
    stage_height = 2.5
    x_range = np.linspace(-stage_radius, stage_radius, voxel_count)
    y_range = np.linspace(-stage_radius, stage_radius, voxel_count)
    z_range = np.linspace(-stage_radius, stage_radius, voxel_count)  # Ground to 3m up
    grid_x, grid_y, grid_z = np.meshgrid(x_range, y_range, z_range)
    voxels = np.stack((grid_x, grid_y, grid_z), axis=-1).reshape(-1, 3)

    voxels_h = np.insert(voxels, 3, 1, axis=1)  # Homogeneous coordinates

    # 2. Iterative Carving
    # We start with all voxels and keep only those that project into EVERY mask
    keep_mask = np.ones(len(voxels), dtype=bool)

    for name, cam in cameras.items():
        if name not in masks:
            continue
        # Project voxels to this camera: [u, v, w] = P @ [X, Y, Z, 1]
        proj = voxels_h @ cam.projection_matrix.T
        u = (proj[:, 0] / proj[:, 2]).astype(int)
        v = (proj[:, 1] / proj[:, 2]).astype(int)

        # Filter points outside the image frame
        h, w = masks[name].shape
        in_frame = (u >= 0) & (u < w) & (v >= 0) & (v < h)

        # Logic: If point is in frame, it MUST be on a white pixel in the mask
        # If it's out of frame, we usually discard it to be safe
        is_foreground = np.zeros(len(voxels), dtype=bool)
        is_foreground[in_frame] = masks[name][v[in_frame], u[in_frame]] > 127

        keep_mask &= is_foreground
    return voxels[keep_mask]


def plot_cameras_with_axes(ax, cameras: dict[str, Camera], scale=0.2):
    for cam in cameras.values():
        # Get the camera center
        pos = cam.world_pos

        # Extract Rotation Matrix from Projection Matrix
        # P = K [R | t], so the first 3x3 is K*R.
        # If you have cam.R, use that. Otherwise:
        # K, R = cv2.decomposeProjectionMatrix(cam.projection_matrix)[:2]
        R = cam.rot  # Assuming your object has the rotation matrix

        # In World Space, the camera's local axes are the columns of R^T
        R_inv = R.T
        forward = R_inv[:, 2]  # Z-axis
        up = -R_inv[:, 1]  # -Y-axis (Up)
        right = R_inv[:, 0]  # X-axis

        # Plot Forward Arrow (Blue)
        ax.quiver(
            pos[0],
            pos[1],
            pos[2],
            forward[0],
            forward[1],
            forward[2],
            length=scale,
            color="blue",
            label="Forward" if cam == list(cameras.values())[0] else "",
        )

        # Plot Up Arrow (Green)
        ax.quiver(
            pos[0],
            pos[1],
            pos[2],
            up[0],
            up[1],
            up[2],
            length=scale * 0.5,
            color="green",
            label="Up" if cam == list(cameras.values())[0] else "",
        )

        # Optional: Label the camera name
        ax.text(pos[0], pos[1], pos[2], cam.name, fontsize=8)


def main():
    parser = argparse.ArgumentParser("Compute visual hull from masks")
    parser.add_argument("frame_path")
    parser.add_argument("--calibration_path", default=None, required=False)
    parser.add_argument("--plot_output", default="visuals/playground/visual_hull")
    parser.add_argument("--cam_cnt", default=None)
    parser.add_argument("--interactive", "-i", action="store_true")
    args = parser.parse_args()

    frame_folder = Path(args.frame_path)
    if args.calibration_path:
        calib_file = Path(args.calibration_path)
    else:
        calib_file = frame_folder.parent / "calibration_dome.json"

    with calib_file.open() as f:
        calib_json = json.load(f)
    camerass: list[Camera] = load_dome_format(calib_json)
    cameras: dict[str, Camera] = {c.name: c for c in camerass}

    mask_path = str(frame_folder / "mask" / "mask_<camera_id>.*")

    masks: dict[str : np.array] = {}
    for camera in cameras.values():
        p = Path(mask_path.replace("<camera_id>", camera.name))
        search_file = list(p.parent.glob(p.name))
        image_path = search_file[0]
        try:
            assert Path(image_path).exists(), f"Image path {image_path} does not exist"
            if image_path.suffix == ".avif":
                with Image.open(str(image_path)) as img:
                    mask = np.array(img.convert("L"))
            else:
                mask = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
            masks[camera.name] = mask
        except Exception as e:
            print(e)

    print(f"loaded {len(masks)} masks")
    if len(masks) == 0:
        print("No images found :(. Existing")
        exit()
    # Run it
    if args.cam_cnt is not None:
        limited_cameras = list(cameras.keys())[: args.cam_cnt]
        limited_cameras = {k: cameras[k] for k in limited_cameras}
        cameras = limited_cameras
    print(cameras.keys())
    hull_points = quick_hull_check(cameras, masks)

    # 3. Fast Plot
    fig = plt.figure(figsize=(20, 20))
    ax = fig.add_subplot(111, projection="3d")
    ax.scatter(hull_points[:, 0], hull_points[:, 1], hull_points[:, 2], s=1)

    # 2. Plot Cameras with Arrows
    plot_cameras_with_axes(ax, cameras, scale=0.2)

    ax.set_xlim(-2, 2)
    ax.set_ylim(-4, 0)
    ax.set_zlim(-2, 2)

    # 3. Aesthetics
    ax.set_xlabel("X (Stage)")
    ax.set_ylabel("Y (Stage)")
    ax.set_zlabel("Z (Height)")
    ax.set_title("Visual Hull & Camera Orientation Check")

    # Equalize aspect ratio (Crucial for checking geometry)
    # Matplotlib 3.3.0+ uses ax.set_box_aspect([1,1,1])
    ax.set_box_aspect([1, 1, 1])

    if args.interactive:
        plt.show()
    else:
        out = Path(args.plot_output)
        out.mkdir(exist_ok=True, parents=True)
        standard_views = [
            (0, -90, "top_down"),
            (-40, 15, "diagonal"),
            (0, 0, "side_1"),
            (90, 0, "side_2"),
            (180, 0, "side_3"),
            (-90, 0, "side_4"),
        ]

        print("Generating standard view gallery...")
        for elev, azim, name in standard_views:
            ax.view_init(elev=elev, azim=azim, roll=-90)
            filename = out / f"view_{name}.png"
            plt.savefig(str(filename))
            print(f"  > Saved {filename}")

    plt.close(fig)  # Clean up memory


if __name__ == "__main__":
    main()
