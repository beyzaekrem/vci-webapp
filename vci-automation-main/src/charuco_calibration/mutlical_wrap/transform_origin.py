# ruff: noqa: E402, INP001, S101

import numpy as np

from charuco_calibration.camera import Camera

np.int = int  # noqa: NPY001
np.bool = bool  # patch for multical.


from multical import tables
from multical.camera import Camera as mutliCalCamera
from multical.optimization.calibration import Calibration as multical_Calibration
from structs.struct import struct


def update_extrinsics(calib: multical_Calibration, cameras: list[Camera]) -> None:
    out_cameras_by_name: dict = {cam.name: cam for cam in cameras}

    for name, mutlical_cam, camera_pose, pose_valid in zip(
        calib.cameras.names, calib.cameras, calib.camera_poses.poses, calib.camera_poses.valid, strict=True
    ):
        out_camera: Camera = out_cameras_by_name.get(name, Camera(name))
        # update existing cmaera or create a new one.

        if pose_valid:
            out_camera.extrinsic_matrix = camera_pose  # we mainly want to update the pose.
        assert np.allclose(out_camera.intrinsic, mutlical_cam.intrinsic)
        assert np.allclose(out_camera.image_size, [int(res) for res in mutlical_cam.image_size])
        assert np.allclose(out_camera.distortion_coeff, mutlical_cam.dist)

        # these can be the same as before
        out_camera.intrinsic = mutlical_cam.intrinsic
        out_camera.image_size = [int(res) for res in mutlical_cam.image_size]
        out_camera.distortion_coeff = mutlical_cam.dist

        out_cameras_by_name[name] = out_camera

    return out_cameras_by_name.values()


def set_origin_camera(
    calib: multical_Calibration, master: mutliCalCamera
) -> multical_Calibration:  # transform camera poses
    # master is a camera
    if master is not None:
        calib = calib.with_master(master)
    return calib


def set_origin_board_pose(
    calib: multical_Calibration,
    pose_idx: int = -1,
    height_offset_mm: float = 10.20,
    *,
    center_of_cameras_bb: bool = True,
) -> multical_Calibration:
    """
    Changes the origin of the coordinate system for all cameras to
    the board that is captured at pose_idx (equivalent to image index).
    The origin aligns with the angle and height of the board.

    If you set center_of_cameras_bb = True, the origin position will be
    centered between the cameras (center of bounding box around all cameras).
    If you set center_of_cameras_bb = False, the position of the charoc board
    (specifically the top left corner ) will be the origin.
    """
    # master is a board pose

    calib = calib.copy()

    board_poses = tables.expand_boards(calib.pose_estimates)  # set of board poses for each image pair
    board_pose = struct(
        poses=board_poses.poses[pose_idx], valid=board_poses.valid[pose_idx]
    )  # board poses for first image pair
    board_pose = np.linalg.inv(board_pose.poses[0])  # invert so pose is expressed in "camera_0 to board"
    calib = calib.transform_views(board_pose)  # transform so board pose is origin

    # we want to set the board pose to be the origin. However the board pose is not
    # expressed in the same way a camera is. It is expressed in object frame.
    # For consistency and simplicity, we are fixing this.
    # object-frame (board) (given):
    #    | z (up)
    #    |
    #    |  / y (along the board)
    #    | /
    #     ------ x (right, along the board)
    #
    # adjust the origin, so it's oriented like a camera

    # board pose is different from camera poses.
    # camera-frame (target-world) : right-handed
    #   / z (forward into the scene, away from viewer)
    #  /
    #  _____ x (right)
    # |
    # |
    # | y (down)
    # a transformation may not change the handedness of the coordinate system.

    rotate = np.array(
        [
            [1, 0, 0, 0],  # world_X = board_X
            [0, 0, 1, 0],  # world_Z = board_Y
            [0, -1, 0, 0],  # world_Y = -board_z
            [0, 0, 0, 1],
        ]
    )
    calib = calib.transform_views(rotate)

    # assuming the board is lying on the ground:
    # subtract physical depth of the board from height so origin is on the floor and not on the surface of the board
    origin_pose = np.array(
        [
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ],
        dtype=float,
    )
    origin_pos = get_position(origin_pose)
    origin_pos[1] = 0 + (height_offset_mm * 0.001)  # updates y axis
    subtract_height_offset = update_position(origin_pose, origin_pos)
    calib = calib.transform_views(subtract_height_offset)

    if center_of_cameras_bb:
        # the board_pose is not in the center of the board but in the upper right corner.
        # And the board is not centered on the stage (human error)
        # ->
        # board position gives us height (y) and rotation of the origin.
        # use the center of the cameras for the other two axis (x and z)
        camera_poses = calib.camera_poses.pose_table.poses
        center = compute_camera_center_bbox(camera_poses)
        origin_pose = np.array(
            [
                [1, 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, 1, 0],
                [0, 0, 0, 1],
            ],
            dtype=float,
        )
        centered_origin_pose = update_position(
            origin_pose, center, [True, False, True]
        )  # update x and z from center position
        calib = calib.transform_views(centered_origin_pose)

    return calib


def get_position(extrinsic_matrix: np.array) -> np.array:
    rot = extrinsic_matrix[:3, :3]
    t = extrinsic_matrix[:3, 3]
    return -rot.T @ t  # world_point


def compute_camera_center_bbox(camera_poses: list[np.ndarray]) -> np.ndarray:
    positions = np.array([get_position(pose) for pose in camera_poses])  # Shape: (N, 3)

    min_xyz = np.min(positions, axis=0)
    max_xyz = np.max(positions, axis=0)
    return (min_xyz + max_xyz) / 2


def update_position(
    extrinsic_matrix: np.ndarray,
    new_position: np.ndarray,
    update_mask: list[bool] | None = NotImplemented,
) -> np.ndarray:
    """
    Update the 3D position of the extrinsic_matrix using center_position,
    while keeping the rotation and of extrinsic_matrix.
    The coodinates of the extrinsic_matrix position are selectively replaced
    with values form new_position, according to update_mask.

    Parameters:
    - extrinsic_matrix: (4,4) numpy array representing the target transformation matrix.
    - new_position: (3,) numpy array representing a (x, y, z) position.
    - update_mask: a list (3,) describing which components (x,y,z) of the new_position are being used to
    update the target_matrix.

    Returns:
    - (4,4) numpy array of the updated transformation matrix.
    """

    if update_mask is None:
        update_mask = [True, True, True]

    matrix_world_position = get_position(extrinsic_matrix)
    # replace with values from new_position
    new_world_position = np.array(
        [new_position[i] if update_mask[i] else matrix_world_position[i] for i in range(len(matrix_world_position))]
    )
    # same as: new_world_position = np.array([new_position[0], new_position[1], matrix_world_position[2]])

    # Convert back to extrinsic translation format
    rot = extrinsic_matrix[:3, :3]
    t_new = -rot @ new_world_position

    # Construct new transformation matrix
    new_matrix = extrinsic_matrix.copy()
    new_matrix[:3, 3] = t_new  # Replace translation

    return new_matrix
