import copy
import json
import os
from datetime import datetime
from pathlib import Path

import numpy as np
from camorph.lib.model.Camera import Camera as CamorphCamera
from camorph.lib.model.FileHandler import FileHandler
from camorph.lib.utils import math_utils
from pyquaternion import Quaternion


# make sure to install camorph: pip install git+https://github.com/Fraunhofer-IIS/camorph
def main():

    cams = camorph.read_cameras(
        "dome",
        "/home/ximea/git/vci-automation/Capture/chair_A_pose_test/calibration_dome.json",
        images_half_resolution=False,
    )
    print("cameras", len(cams))
    print("camera_ids:", [cam.name for cam in cams])
    visualize(cams)

    # camorph.write_cameras("fbx", "/home/ximea/git/vci-automation/Capture/chair_A_pose_test/cameras.fbx", cams)
    #
    # camorph.write_cameras("fbx", "reformat_output/calibration.fbx", cams)
    #
    # camorph.write_cameras("colmap", "reformat_output/manual_sparse_model", cams)


# region Dome FileHandler


class Dome(FileHandler):

    def crucial_properties(self) -> list[(str, type)]:
        return []

    def name(self):
        return "dome"

    def file_number(self):
        return 1

    def read_file(self, input_path, **kwargs):  # called on camorph.read_cameras
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"File {input_path} could not be found")

        with open(input_path) as f:
            calibration_data = json.load(f)

        sensor_size_mm = kwargs.get("sensor_size_mm")
        image_half_resolution = kwargs.get("images_half_resolution", False)
        imdir = kwargs.get("imdir")
        absolute_path = kwargs.get("absolute_path", False)

        cameras = self.parse(
            calibration_data,
            sensor_size_mm=sensor_size_mm,
            images_half_resolution=image_half_resolution,
        )
        if imdir is not None:
            cameras = self.set_source_images(cameras, imdir, absolute_path)
        return cameras

    def parse(
        self, calibration_data, sensor_size_mm=None, images_half_resolution=False
    ):
        if sensor_size_mm is None:
            sensor_size_mm = [14, 12]  # Ximea cameras sensor size in mm
        assert calibration_data is not None

        calibration_cameras = calibration_data["cameras"]
        self.last_meta = calibration_data.get("meta")
        ret_camorph_cameras: list[CamorphCamera] = []

        for calib in calibration_cameras:
            c = CamorphCamera()
            c.name = calib.get("camera_id", "Err")

            # keep these attributes if we read from dome and save as dome again. For example if resolution or crop is changed.
            for key in [
                "color_correction_matrix",
                "white_balance_coefficients",
                "distortion_coefficients",
            ]:
                value = calib["intrinsics"].get(key)
                if value is not None:
                    setattr(c, key, value)

            # extrinsic_matrix: |rot 3x3 , t 3x1|
            #                   | 0    ,  1   |
            # opencv convention
            extrinsic_matrix = calib.get("extrinsics", {}).get("view_matrix", None)
            if extrinsic_matrix is None:
                print(f"Camera {c.name} does not have a view_matrix")
                continue
            extrinsic_matrix = np.array(extrinsic_matrix).reshape((4, 4))
            rot = extrinsic_matrix[:3, :3]
            t = extrinsic_matrix[:3, 3].reshape(3, 1)
            world_position = -rot.T @ t

            c.t = world_position
            q = Quaternion(matrix=rot)
            c.r = Quaternion(-q.w, q.x, q.y, q.z)

            c.serialNumber = c.name
            c.projection_type = "perspective"
            c.model = "pinhole"

            c.source_image = f"{c.name}.jpg"  # default image name

            intrinsics = calib.get("intrinsics")
            c.resolution = np.array(intrinsics.get("resolution"))
            intrinsic_matrix = intrinsics.get("camera_matrix")
            if intrinsic_matrix is not None:
                intrinsic_matrix = np.array(intrinsic_matrix).reshape((3, 3))

                c.sensor_size = np.array(sensor_size_mm, dtype=float)
                # ensure sensor_size aspekt ratio matches resolution aspekt ratio
                c.sensor_size[0] = c.sensor_size[1] * c.resolution[0] / c.resolution[1]

                if images_half_resolution:
                    c.resolution = c.resolution // 2
                    intrinsic_matrix = intrinsic_matrix // 2

                c.focal_length_px = np.array(
                    [intrinsic_matrix[0, 0], intrinsic_matrix[1, 1]]
                )
                c.focal_length_mm = (c.focal_length_px * c.sensor_size) / c.resolution

                c.principal_point = np.array(
                    [intrinsic_matrix[0, 2], intrinsic_matrix[1, 2]]
                )

            ret_camorph_cameras.append(c)

        ret_camorph_cameras = self.coordinate_from(ret_camorph_cameras)
        return ret_camorph_cameras

    def set_source_images(self, cameras, imdir, absolute_path=False):
        if imdir is None:
            return

        imdir = Path(imdir)
        if imdir.is_file():
            raise IsADirectoryError(
                f"imdir {imdir} is a file. set_source_images is expecting a folder"
            )
        valid_extensions = (
            ".jpg",
            ".jpeg",
            ".png",
            ".bmp",
            ".tiff",
            ".tif",
            ".webp",
            ".pt",
            ".pth",
        )

        filenames = [
            f.name
            for f in imdir.iterdir()
            if f.is_file() and f.suffix.lower() in valid_extensions
        ]
        if len(filenames) == 0:
            raise FileNotFoundError(
                f"imdir {imdir} does not contain any image files. "
                f"Please input the direct parent folder of the images you want to "
                f"attach to the cameras. E.g.: /capture001/frame_00001/rgb"
                f"Valid image extensions are : {valid_extensions}"
            )

        no_image_found_for = []
        for cam in cameras:
            if cam.name == "origin":
                continue
            # search for image with name of cam in file name
            image_file = [f for f in filenames if cam.name in f]
            if len(image_file) == 0:
                no_image_found_for.append(cam.name)
            else:
                if len(image_file) > 1:
                    print(
                        Warning(
                            f"Found more than one image for camera {cam.name} in imdir {imdir}. Images found {image_file}"
                        )
                    )
                if absolute_path:
                    cam.source_image = str(imdir / image_file[0])
                else:
                    cam.source_image = image_file[0]

        if len(no_image_found_for) > 0:
            print(
                FileNotFoundError(
                    f"Could not find images for cameras: {no_image_found_for} ({len(no_image_found_for)}/{len(cameras)} cameras)"
                )
            )
            cams_with_image = [
                cam for cam in cameras if cam.name not in no_image_found_for
            ]
            print(
                f"Removing cameras from calibration. "
                f"Remaining cameras: {len(cams_with_image)}"
            )
            cameras = cams_with_image
        return cameras

    def write_file(
        self, camera_array, output_path, file_type=None
    ):  # called on camorph.write_cameras
        camera_array: list[CamorphCamera] = self.coordinate_into(camera_array)
        json_entries = []

        for c in camera_array:
            q: Quaternion = c.r
            q = Quaternion(-q.w, q.x, q.y, q.z)
            rot = q.rotation_matrix
            t = -rot @ c.t

            extrinsic_matrix = np.eye(4)
            extrinsic_matrix[:3, :3] = rot
            extrinsic_matrix[:3, 3] = t

            fx, fy = c.focal_length_px
            cx, cy = c.principal_point

            intrinsic_matrix = np.array(
                [
                    [fx, 0, cx],
                    [0, fy, cy],
                    [0, 0, 1],
                ]
            )

            entry = {
                "camera_id": c.name,
                "extrinsics": {"view_matrix": extrinsic_matrix.flatten().tolist()},
                "intrinsics": {
                    "camera_matrix": intrinsic_matrix.flatten().tolist(),  # principal point imported from fbx is wrong
                    "resolution": np.array(c.resolution).flatten().tolist(),
                },
            }

            for key in [
                "color_correction_matrix",
                "distortion_coefficients",
                "white_balance_coefficients",
            ]:
                if hasattr(c, key):
                    entry["intrinsics"][key] = getattr(c, key)
            json_entries.append(entry)

        if hasattr(self, "last_meta") and self.last_meta is not None:
            meta = self.last_meta
        else:
            meta = (
                "Generated with reformat_camorph. "
                + "Extrinsics use OpenCV coordinate system (x right, z forward into the scene, y down)"
            )
        calib_dome = {
            "meta": meta,
            "timestamp": datetime.now().strftime("%Y.%m.%d %H:%M"),
            "cameras": json_entries,
        }
        p = Path(output_path).parent
        p.mkdir(exist_ok=True, parents=True)
        with open(output_path, "w") as f:
            json.dump(calib_dome, f, indent=2)

    def coordinate_from(self, camera_array):
        # Converts cameras rotation and translation from dome coordinate system into camorph coordinate system
        cam_arr = copy.deepcopy(camera_array)
        for cam in cam_arr:
            # conversion opencv board -> camorph
            cam.t, cam.r = math_utils.convert_coordinate_systems(
                ["y", "-z", "-x"], cam.t, cam.r, cdir=[0, 0, 1], cup=[0, -1, 0]
            )
            # [opencv_x = camorph_y, opencv_y = camorph -z, opencv_z = camorph_ -x]
        # opencv:
        #   / z (forward into the scene, away from viewer)
        #  /
        # ______ x (right)
        # |
        # |
        # | y (down)

        # Camorph        |z (up)
        # Coordinate     |
        # S System       |___y (right)
        #               /
        #              x (toward the viewer)
        #
        return cam_arr

    def coordinate_into(self, camera_array):
        cam_arr = copy.deepcopy(camera_array)
        for cam in cam_arr:
            cam.t, cam.r = math_utils.convert_coordinate_systems(
                ["y", "-z", "-x"], cam.t, cam.r, cdir=[0, 0, 1], cup=[0, 1, 0]
            )
        # converts from camorph coordinate system to dome (opencv) coordinate system
        return cam_arr


# add Dome FileHandler to camorph
import camorph

dome_handler = Dome()
camorph.imported_instances[dome_handler.name().lower()] = dome_handler

from camorph import camorph


def visualize(cams: list[CamorphCamera], save=True):
    import matplotlib.pyplot as plt

    """
    Copy of camorphs visualize with tweaks to show more info (like camera names, axis descriptions and origin)
    This function takes a list of camorph cameras and visualizes them with matplotlib

    :param cams: A list of camorph Cameras
    :type cams: list[Camera]
    :return: None
    """

    x, y, z = zip(*[x.t for x in cams])
    dir = np.array([0, 0, -1])
    up = np.array([0, 1, 0])

    # dir = np.array([1, 0, 0])
    # up = np.array([0, 0, 1])

    maxdist = max([np.linalg.norm(x.t) for x in cams])
    dir = dir * maxdist * 0.1
    up = up * maxdist * 0.1

    dirx, diry, dirz = zip(*[x.r.rotate(dir) for x in cams])
    upx, upy, upz = zip(*[x.r.rotate(up) for x in cams])
    fig = plt.figure(figsize=(20, 20))
    ax = fig.add_subplot(111, projection="3d")
    ax.quiver(x, y, z, dirx, diry, dirz, color="r", label="Camera Front")
    ax.quiver(x, y, z, upx, upy, upz, color="g", label="Camera Up")

    ax.set_xlim([-maxdist, maxdist])
    ax.set_ylim([-maxdist, maxdist])
    ax.set_zlim([-maxdist, maxdist])

    ax.scatter(x, y, z)

    # show origin
    ax.scatter(0, 0, 0, color="black", linewidths=3)
    ax.text(0, 0, 0, "origin", color="black")
    ax.quiver(0, 0, 0, 1, 0, 0, color="red", label="x front")
    ax.quiver(0, 0, 0, 0, 1, 0, color="blue", label="y right")
    ax.quiver(0, 0, 0, 0, 0, 1, color="green", label="z up")

    for cam, xpos, ypos, zpos in zip(cams, x, y, z):
        color = "gray"
        if cam.name in ["C0031", "C0039"]:
            color = "cyan"
        elif cam.name in ["C0018", "C0004", "C0034"]:
            color = "magenta"
        elif cam.name in ["C1002", "C0020"]:
            color = "black"
        ax.text(xpos, ypos, zpos, cam.name, color=color)
    ax.set_xlabel("X (front)", color="red")
    ax.set_ylabel("Y (right)", color="blue")
    ax.set_zlabel("Z (up)", color="green")

    ax.legend()
    ax.view_init(elev=15, azim=15, roll=0)

    if save:
        print("saved camera position figure  ----> plt.png")
        plt.savefig("plt.png")
    else:
        plt.show()
    return fig


# endregion

if __name__ == "__main__":
    main()
