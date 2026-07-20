import cv2
import numpy as np
from scipy.spatial.transform import Rotation as R
from structs.numpy import Table

from charuco_calibration.board import Board
from charuco_calibration.camera import Camera
from charuco_calibration.detection_data import AllDetectionsList, DetectionData

from .multical_patches import MulticalBoard, MulticalCamera, initialise_poses

np.int = int  # noqa: NPY001
np.bool = bool  # patch for multical.


from multical.io.logging import MemoryHandler, setup_logging  # noqa: E402
from multical.motion import StaticFrames  # noqa: E402
from multical.optimization.calibration import Calibration as MulticalCalibration  # noqa: E402
from multical.optimization.calibration import (  # noqa: E402
    select_threshold,
)
from multical.optimization.parameters import ParamList  # noqa: E402
from multical.optimization.pose_set import PoseSet  # noqa: E402


def extrinsic_calibration_bundle_adjust(
    detection_data: DetectionData, board: Board, cameras: list[Camera]
) -> MulticalCalibration:
    if {c.name for c in cameras} != set(detection_data.camera_names):
        msg = "Mismatching cameras and DetectionData"
        raise RuntimeError(msg)

    # ensure the order matches
    if [c.name for c in cameras] != detection_data.camera_names:
        cameras_by_id = {c.name for c in cameras}
        cameras = [cameras_by_id[cam_id] for cam_id in detection_data.camera_names]

    # ensure intrinic calibration is done.
    for camera in cameras:
        if camera is None or camera.intrinsic is None:
            msg = "Missing intrinsic camera matrices."
            raise RuntimeError(msg)

    # point table extends detected corners by filling in empty corner positions [0, 0] for each board corner that
    #  was not detected
    point_table = make_point_table(detection_data.detections, len(board.charuco_points))
    #  valid describes which corner positions are real and which ones are empty/fake

    # compute board poses for each detection
    board_poses = make_board_pose_table(detection_data.detections, cameras, board.charuco_points)
    print(
        "found board_poses",
        list(
            zip(
                detection_data.camera_names,
                [len([detection for detection in cam if detection]) for cam in board_poses.valid],
                strict=True,
            )
        ),
    )
    print("\ncompute camera positions:")
    # we let multical library compute camera positions via bundle adjust
    setup_logging("INFO", [MemoryHandler()], log_file="log.txt")

    pose_init = initialise_poses(board_poses)

    mutlicalboard = MulticalBoard(
        board.size,
        board.square_length,
        board.marker_length,
        board.min_rows,
        board.min_points,
        board.dict_name,
        board.charuco_board,
    )
    calib: MulticalCalibration = MulticalCalibration(
        ParamList(
            [MulticalCamera(camera.image_size, camera.intrinsic, camera.distortion_coeff) for camera in cameras],
            detection_data.camera_names,
        ),
        ParamList([mutlicalboard], ["board"]),
        point_table,
        PoseSet(pose_init.camera, detection_data.camera_names),
        PoseSet(pose_init.board, ["board"]),
        StaticFrames.init(
            pose_init.times,
            ["detection" + str(idx) for idx in range(detection_data.frame_cnt)],
        ),
    )

    fix_intrinsic: bool = (
        True  # not now allow intrinics to be updated.
        # since we pre-compute the intrinsics this is set to True.
        # This makes most sense for --extrinsics-only calibration where the user doesnt cover
        # the entire screen with detections
    )
    fix_camera_poses: bool = False  # no not keep exintrics the same. (True for checking accuracy in mutlical)
    fix_board_poses: bool = (
        False  # Constant poses between boards - shoudl be true, when you have multiple
        # calibration boards in the scene, and they are physically stuck to each other,
        # so the baords always have the same relative pose to each other.
        # For us: We only use one board so this property doesn't matter.
    )
    fix_motion: bool = (
        False  # Constant camera motion estimates
        # I think this should be false. The motion of the boards between captures is not constant.
    )
    adjust_board: bool = False  # Enable optimization for board non-planarity, our board should be pretty planar
    calib = calib.enable(
        cameras=not fix_intrinsic,
        boards=adjust_board,  # adjust board
        camera_poses=not fix_camera_poses,  # camera poses not fixed
        motion=not fix_motion,  # motion not fixed
        board_poses=not fix_board_poses,  # board poses not fixed
    )

    return calib.adjust_outliers(
        loss="linear",
        tolerance=1e-4,
        select_outliers=select_threshold(quantile=0.75, factor=5.0),
        select_scale=None,
    )


def make_point_table(detected_points: AllDetectionsList, board_points_cnt) -> Table:
    # point table extends detected corners
    # fills in empty corner positions [0, 0] for each board corner that was not detected
    all_points = []
    all_valid = []
    for detection_of_camera in detected_points:
        points = []
        is_valid = []
        for detection in detection_of_camera:
            corners = detection["corners"]
            ids = detection["ids"]
            extended = np.zeros((board_points_cnt, 2))
            extended[ids] = corners

            valid = np.full(board_points_cnt, False)  # noqa: FBT003
            valid[ids] = True
            points.append([extended])
            is_valid.append([valid])

        all_points.append(points)
        all_valid.append(is_valid)
    return Table.create(points=np.array(all_points), valid=np.array(all_valid))


def make_board_pose_table(detected_points: AllDetectionsList, cameras: list[Camera], charuco_board_points) -> Table:
    all_poses = []
    all_valid = []
    all_num_points = []
    for camera, detections_of_camera in zip(cameras, detected_points, strict=True):
        poses_per_camera = []
        detection_is_valid = []
        num_points = []
        for detection in detections_of_camera:
            if len(detection["ids"]) == 0:
                valid = False
            else:
                undistorted_corners = cv2.undistortPoints(
                    detection["corners"],
                    camera.intrinsic,
                    camera.distortion_coeff,
                    P=camera.intrinsic,
                )
                object_points = np.array([charuco_board_points[charuco_id] for charuco_id in detection["ids"]])
                valid, rvec, tvec = cv2.solvePnP(object_points, undistorted_corners, camera.intrinsic, np.zeros(0))

            if valid:
                # make position matrix
                rotation = R.from_rotvec(rvec.flatten()).as_matrix()
                matrix = np.hstack((rotation, tvec))
                matrix = np.vstack((matrix, [0, 0, 0, 1]))

                poses_per_camera.append([matrix])
                detection_is_valid.append([True])
                num_points.append([len(undistorted_corners)])
            else:
                poses_per_camera.append([np.eye(4)])
                detection_is_valid.append([False])
                num_points.append([0])
        all_poses.append(poses_per_camera)
        all_valid.append(detection_is_valid)
        all_num_points.append(num_points)
    return Table.create(
        poses=np.array(all_poses),
        valid=np.array(all_valid),
        num_points=np.array(all_num_points),
    )
