from collections import Counter, defaultdict
from contextlib import suppress
from dataclasses import dataclass, field

import cv2
import matplotlib.pyplot as plt
import numpy as np
from natsort import natsorted

from .detection_data import DetectionData
from .exceptions import InvalidDetectionData, MissingCalibrationData
from .intrinsic import Camera


def get_projection_matrices(cameras: list[Camera]) -> list[np.array]:
    proj_matrices = []
    for cam in cameras:
        intrinsic = cam.intrinsic
        extrinsic = cam.extrinsic_matrix

        rotation = extrinsic[:3, :3]
        translation = extrinsic[:3, 3].reshape(3, 1)

        rot_t = np.hstack((rotation, translation))  # shape (3, 4)
        projection_matrix = intrinsic @ rot_t  # projection matrix: shape (3, 4)
        proj_matrices.append(projection_matrix)
    return proj_matrices


def undistort_corners(corners: np.array, camera: Camera) -> np.array:
    """undisotrts the given corners - 2D coordiantes of

    Args:
        corners (np.array):
        camera (Camera): calibrated camera

    Returns:
        np.array: _description_
    """
    return cv2.undistortPoints(
        corners.reshape(-1, 1, 2),
        cameraMatrix=camera.intrinsic,
        distCoeffs=camera.distortion_coeff,
        P=camera.intrinsic,  # reprojects into pixel coords
    ).reshape(-1, 2)


def triangulate_n_views(pixel_coordinates: list[np.array], projection_matrices: list[np.array]) -> np.array:
    """Triangualtes a 3D positon from multiple pixel_coordinates (e.g charuco_corners)
    and corresponding camera_projection_matrices.

    Uses Linear Least Squares Triangulation.

    Args:
        pixel_coordinates (list(np.array)): list of 2D pixel coordiantes
        projection_matrices (list(np.array)): list of projection matrices.

    Returns:
        np.array: 3D position in camera's coordinate frame.
    """
    linear_constraint_matrix = []
    for pixel_coord_2d, projection_matrix in zip(pixel_coordinates, projection_matrices, strict=True):
        x, y = pixel_coord_2d[0], pixel_coord_2d[1]
        # Each view provies two lienar contraints from
        # pixel_coord cross (projection_matrix * world_point) = 0
        linear_constraint_matrix.append(x * projection_matrix[2] - projection_matrix[0])
        linear_constraint_matrix.append(y * projection_matrix[2] - projection_matrix[1])

    linear_constraint_matrix = np.stack(linear_constraint_matrix)
    # SDV finds the best solution for the linear_constraint_matrix.
    # aka, the 3D point that best explains the pixel_coordiantes we "see"
    _, _, v_transpose = np.linalg.svd(linear_constraint_matrix)

    homogeneous_point_3d = v_transpose[-1]  # homogeneous coordinates [X, Y, Z, W]
    world_point_3d = homogeneous_point_3d / homogeneous_point_3d[3]  # Cartesian [x, y, z]
    return world_point_3d[:3]


@dataclass
class TriangulatedFrame:
    image_points_all_cameras: dict[dict[int, np.array]]
    """image_points_all_cameras[cam_name] is {chacruo_id (int): image_point_2d (np.array)}. Image points are undistorted"""
    triangulated_points: dict[int, list[np.array]]
    """3D positions of charuco_ids {charuco_id(int) : 3d_pos}"""
    reproj_error_pixel: defaultdict[str : list[float]] = field(default_factory=lambda: defaultdict(list))
    """reprojection error in pixels per camera. One entry per image_point"""
    reproj_error_mm: defaultdict[str : list[float]] = field(default_factory=lambda: defaultdict(list))
    """reprojection error in mm per camera. One entry per image_point"""


class DatasetTriangulation:

    @property
    def camera_errors_pixel(self) -> list[str : list[float]]:
        ret = defaultdict(list)
        for t_frame in self.triangualted_frames:
            for cam_namae, errors in t_frame.reproj_error_mm.items():
                ret[cam_namae].extend(errors)
        return ret

    @property
    def camera_errors_mm(self) -> list[str : list[float]]:
        ret = defaultdict(list)
        for t_frame in self.triangualted_frames:
            for cam_namae, errors in t_frame.reproj_error_mm.items():
                ret[cam_namae].extend(errors)
        return ret

    def __init__(self, detection_data: DetectionData, calibrated_cameras: list[Camera], anchor_cnt: int = 2) -> None:
        if detection_data is None:
            msg = "Detection is None"
            raise InvalidDetectionData(msg)
        if detection_data.frame_cnt == 0:
            msg = "Detection is Empty"
            raise InvalidDetectionData(msg)
        self.detection_data = detection_data
        self.cameras_by_name: dict[str, Camera] = {c.name: c for c in calibrated_cameras if c}
        self.anchor_cnt = max(
            anchor_cnt, 2
        )  # minimum amount of cameras that need to "see" one image point for triangulation.
        # higher count is more accurate. Mathmatical minimum is 2.

        input_is_undistorted = self.detection_data.points_are_undistoreted

        # ensure the calibrated cameras we are given are actually, calibrated
        for c in self.cameras_by_name.values():
            if c.intrinsic is None:
                msg = f"Intrinsic matrices is None for camera {c.name}."
                raise MissingCalibrationData(msg)
            if not input_is_undistorted and c.distortion_coeff is None:
                msg = f"Missing distortion coefficients for camera {c.name}"
                raise MissingCalibrationData(msg)

        self.triangualted_frames: list[TriangulatedFrame] = self._perform_triangulation()

    def _get_image_points(self, frame_idx: int) -> dict[dict[int, np.array]]:
        image_points_all_cameras: dict[dict[int, np.array]] = {}
        for cam_idx in range(self.detection_data.camera_cnt):
            camera_name, detections, _ = self.detection_data.get_camera_data(cam_idx)
            correspoding_camera = self.cameras_by_name.get(camera_name)
            detection = detections[frame_idx]
            charuco_ids = detection["ids"]
            charuco_corners = detection["corners"]

            if correspoding_camera is None or charuco_ids is None or charuco_corners is None or len(charuco_ids) == 0:
                # this camera isnt the the calibrated Cameras list. or doesnt have detections.
                image_points_all_cameras[camera_name] = {}
                continue

            charuco_ids = charuco_ids.flatten()
            charuco_corners = np.array(charuco_corners, dtype=np.float32).reshape(-1, 2)

            # undistort if needed
            if not self.detection_data.points_are_undistoreted:
                charuco_corners = undistort_corners(charuco_corners, correspoding_camera)

            point_map = {int(id_): charuco_corners[i] for i, id_ in enumerate(charuco_ids)}
            image_points_all_cameras[camera_name] = point_map
        return image_points_all_cameras

    def _perform_triangulation(self) -> list:
        triangualted_frames: list[TriangulatedFrame] = []
        for frame_idx in range(self.detection_data.frame_cnt):

            # -- get common image points --
            image_points_all_cameras = self._get_image_points(frame_idx)
            all_detected_ids = [set(image_points.keys()) for image_points in image_points_all_cameras.values()]
            id_counts = Counter(id_ for ids in all_detected_ids for id_ in ids)
            common_charuco_ids = {id_ for id_, count in id_counts.items() if count >= self.anchor_cnt}

            triangulated_points: dict[int, list[np.array]] = {}

            # -- triangualte points (when point is seen by at least 2 (anchor_cnt) fully calibrated cameras) --
            for charuco_id in common_charuco_ids:
                views: list = []  # 2D (pixel) position of the given point_id per camera.
                projection_matices: list = []  # proejection matrix per camera

                for cam_name, image_pts in image_points_all_cameras.items():
                    # filtering out not fully calibrated cameras.
                    with suppress(Camera.NotCalibratedError):
                        cam = self.cameras_by_name.get(cam_name)
                        if cam is None:
                            continue
                        projection_matrix = cam.projection_matrix

                        if charuco_id in image_pts:
                            views.append(image_pts[charuco_id])
                            projection_matices.append(projection_matrix)

                if len(views) >= self.anchor_cnt:
                    # we have at least two fully calibrated cameras viewing the same charuco_corner
                    triangulated_points[charuco_id] = triangulate_n_views(views, projection_matices)

            if not triangulated_points:

                # this frame didnt couldn't triangualte anything.
                continue

            #  -- Create frame and calculate errors for existing calibrated cameras ---
            tf = TriangulatedFrame(
                image_points_all_cameras=image_points_all_cameras, triangulated_points=triangulated_points
            )
            for cam_name in image_points_all_cameras:
                self._compute_reprojeciton_error_for_frame(tf, cam_name)

            triangualted_frames.append(tf)

        return triangualted_frames

    def _compute_reprojeciton_error_for_frame(self, frame: TriangulatedFrame, cam_name: str) -> None:
        """Calculates px and mm error for a specific camera in a specific frame."""
        cam = self.cameras_by_name.get(cam_name)
        if cam is None:
            return
        with suppress(Camera.NotCalibratedError):
            # Trigger the property to ensure it's ready
            _ = cam.projection_matrix

            for c_id, pt_3d in frame.triangulated_points.items():
                if c_id in frame.image_points_all_cameras[cam_name]:
                    obs = frame.image_points_all_cameras[cam_name][c_id]

                    # Pixel Error
                    reproj = cam.reproject(pt_3d)
                    err_px = np.linalg.norm(reproj - obs)

                    # MM Error
                    pt_cam = cam.extrinsic_matrix[:3, :3] @ pt_3d + cam.extrinsic_matrix[:3, 3]
                    depth_mm = pt_cam[2] * 1000.0
                    err_mm = (err_px * depth_mm) / cam.intrinsic[0, 0]

                    frame.reproj_error_pixel[cam_name].append(err_px)
                    frame.reproj_error_mm[cam_name].append(err_mm)

    def fit_camera(self, camera: Camera) -> None:
        all_3d = []
        all_2d = []

        for frame in self.triangualted_frames:
            # Get 2D hits for this specific camera
            cam_image_points = frame.image_points_all_cameras.get(camera.name, {})

            # Match based on ID
            for charuco_id, img_pt in cam_image_points.items():
                if charuco_id in frame.triangulated_points:
                    all_3d.append(frame.triangulated_points[charuco_id])
                    all_2d.append(img_pt)

        if len(all_3d) < 6:
            msg = f"To few points to fit {camera.name} to triangualted points: only {len(all_3d)} points found.\
                  Must have at least 6 points."
            raise RuntimeError(msg)

        success, rvec, tvec = cv2.solvePnP(
            np.array(all_3d, dtype=np.float32),
            np.array(all_2d, dtype=np.float32),
            camera.intrinsic,
            np.zeros(5, dtype=np.float32),  # zero distortion
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if not success:
            msg = f"Fitting {camera.name} to triangualted points failed."
            raise RuntimeError(msg)

        rot, _ = cv2.Rodrigues(rvec)
        new_extrinsic = np.eye(4)
        new_extrinsic[:3, :3] = rot
        new_extrinsic[:3, 3] = tvec.flatten()
        camera.extrinsic_matrix = new_extrinsic
        # computes reprojection errors with the new extrinsic
        self.re_compute_errors(camera.name)

    def re_compute_errors(self, camera_id: str | None = None) -> None:
        c_list = self.camera_errors_pixel.keys() if camera_id is None else [camera_id]
        for frame in self.triangualted_frames:
            for cam_id in c_list:
                self._compute_reprojeciton_error_for_frame(frame, cam_id)

    def print_errors(self, camera_filter: list[str] | None = None) -> None:
        # Print per-camera reprojection error statistics in mm
        if isinstance(camera_filter, str):
            camera_filter = [camera_filter]
        c_list = camera_filter or self.cameras_by_name.keys()
        print("Reprojection Errors:")
        for cam_id in natsorted(c_list):
            errors_mm = self.camera_errors_mm.get(cam_id, [])
            errors_pixel = self.camera_errors_pixel.get(cam_id, [])
            if errors_mm:
                print(
                    f"{cam_id:<15} | Mean: {np.mean(errors_pixel):.2f} pixels ({np.mean(errors_mm):.2f} mm)  "
                    f"| Std: {np.std(errors_pixel):.2f} pixels | Max: {np.max(errors_pixel):.2f} pixels "
                    f"  | Points: {len(errors_pixel)}"
                )
            else:
                print(f"{cam_id:<15} | No image points or calibration data")

    def plot_camera_errors(
        self,
        output_path: str = "ReprojectionErrors.png",
        errors_dict: dict[str, list[float]] | None = None,
        unit: str = "pixels",
    ) -> None:
        """Creates a boxplot reprojection errors per camera.

        Args:
            output_path (str, optional): output path for plot. Defaults to "ReprojectionErrors.png".
            errors_dict (dict[camera_id (str), erros:(list[float]]) | None, optional): Errors to be plotted per
            camera_id. Defaults to None - plotting camera_erros_pixel.
            unit (str, optional): Error unit (pixels, mm, etc) to plot label. Defaults to "pixels".
        """
        error_dict: dict[str, list[float]] = self.camera_errors_pixel if errors_dict is None else errors_dict
        if len(error_dict) == 0:
            print("Cannot plot reprojection errors.")
            return

        plt.figure(figsize=(18, 6))
        plt.boxplot(error_dict.values(), labels=error_dict.keys(), showmeans=True, showfliers=True)

        plt.xticks(rotation=90)
        plt.ylabel(f"Reprojection Error ({unit})")
        plt.title("Per-Camera Reprojection Error Distribution")
        plt.grid(True, linestyle="--", alpha=0.4)
        plt.tight_layout()
        plt.savefig(output_path)
        print(f"Error plot saved to ----> {output_path}")
        # plt.show()

    def plot_3d_camera_errors(self, cam_name: str, interactive: bool = True) -> None:

        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection="3d")
        for frame_idx, frame in enumerate(self.triangualted_frames):
            if cam_name not in frame.reproj_error_pixel:
                # this camera didnt/cant reproject
                continue
            errs = frame.reproj_error_pixel[cam_name]
            if np.max(errs) < 10:
                continue

            points = []
            for c_id, pt_3d in frame.triangulated_points.items():
                if c_id in frame.image_points_all_cameras[cam_name]:
                    # this point should be in the reprojection_error_mm
                    points.append(pt_3d)
            assert len(errs) == len(points)

            for error, pt_3d in zip(errs, points):
                color = "gray"
                if error > 2:
                    color = "yellow"
                if error > 10:
                    color = "red"
                ax.scatter(pt_3d[0], pt_3d[1], pt_3d[2], color=color)

                # Plot camera centers
        for cam in self.cameras_by_name.values():
            cam_pos = cam.world_pos
            color = "gray"
            if cam.name in ["C0031", "C0039"]:
                color = "cyan"
            elif cam.name in ["C0018", "C0004", "C0034"]:
                color = "magenta"
            elif cam.name in ["C1002", "C0020"]:
                color = "black"
            ax.scatter(
                cam_pos[0],
                cam_pos[1],
                cam_pos[2],
                c="red",
                marker="^",
                s=50,
            )
            ax.text(cam_pos[0], cam_pos[1], cam_pos[2], cam.name, color=color)

        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.set_zlabel("Z (m)")
        ax.set_title("3D Triangulated Points and Cameras")
        ax.legend()
        if interactive:
            plt.show()

    def plot_3d_points_and_cameras(
        self,
        origin_capture_idx: int | None = None,
        *,
        save_path: str = "BoardsAndCameras.png",
        interactive: bool = False,
    ) -> None:
        # trianglualted points are a list[3dpoints per frame]

        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection="3d")

        # Plot triangulated points
        for frame_idx, t_frame in enumerate(self.triangualted_frames):
            pts = np.array(list(t_frame.triangulated_points.values()))
            if len(pts) > 0:
                ax.scatter(
                    pts[:, 0],
                    pts[:, 1],
                    pts[:, 2],
                    c="gray",
                    marker="o",
                    s=4,
                )
                ax.text(
                    pts[0, 0],
                    pts[0, 1],
                    pts[0, 2],
                    frame_idx,
                    color="gray",
                )

        if (
            origin_capture_idx is not None
            and origin_capture_idx != -1
            and origin_capture_idx in range(len(self.triangualted_frames))
        ):
            origin_pts = np.array(self.triangualted_frames[origin_capture_idx].triangulated_points.values())
            ax.scatter(
                origin_pts[:, 0],
                origin_pts[:, 1],
                origin_pts[:, 2],
                c="red",
                s=4,
                label=f"Origin Board (frame idx: {origin_capture_idx})",
            )
            ax.text(
                origin_pts[0, 0],
                origin_pts[0, 1],
                origin_pts[0, 2],
                origin_capture_idx,
                color="red",
            )

        # Plot camera centers
        for cam in self.cameras_by_name.values():
            cam_pos = cam.world_pos
            if cam_pos is not None:
                color = "gray"
                if cam.name in ["C0031", "C0039"]:
                    color = "cyan"
                elif cam.name in ["C0018", "C0004", "C0034"]:
                    color = "magenta"
                elif cam.name in ["C1002", "C0020"]:
                    color = "black"
                ax.scatter(
                    cam_pos[0],
                    cam_pos[1],
                    cam_pos[2],
                    c="red",
                    marker="^",
                    s=50,
                )
                ax.text(cam_pos[0], cam_pos[1], cam_pos[2], cam.name, color=color)
            else:
                print(f"{cam.name} is missing pose - cannot be plotted.")

        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.set_zlabel("Z (m)")
        ax.set_title("3D Triangulated Points and Cameras")
        ax.legend()
        if interactive:
            plt.show()
        print("Saved Plot - Boards and Cameras  --->", save_path)
        plt.savefig(save_path)
