from unittest.mock import patch

import cv2
import numpy as np
from cached_property import cached_property

np.int = int  # noqa: NPY001
np.bool = bool


from multical.board.charuco import CharucoBoard as multicalCharucoBoard  # noqa: E402
from multical.camera import Camera as multicalCamera  # noqa: E402
from multical.tables import initialise_poses as multical_initialise_poses  # noqa: E402
from structs.numpy import struct  # noqa: E402


def initialise_poses(board_poses, camera_poses=None):
    with patch("multical.tables.invalid_pose", struct(poses=np.eye(4), valid=False)):
        pose_init = multical_initialise_poses(board_poses, camera_poses)
    return pose_init


class MulticalBoard(multicalCharucoBoard):

    def __init__(
        self,
        size,
        square_length,
        marker_length,
        min_rows,
        min_points,
        aruco_dict,
        charucoBoard,
    ):
        self.charuco_board = charucoBoard
        super().__init__(
            size,
            square_length,
            marker_length,
            min_rows,
            min_points,
            None,
            None,
            aruco_dict,
            0,
        )

    @cached_property
    def board(self):
        return self.charuco_board

    @property
    def points(self):
        return self.board.getChessboardCorners()


class MulticalCamera(multicalCamera):
    def project(self, points):
        projected, _ = cv2.projectPoints(
            points.reshape(-1, 1, 3),
            np.zeros(3),
            np.zeros(3),
            self.intrinsic,
            self.dist,
        )
        return projected.reshape(*points.shape[:-1], 2)

    def copy(self, **k):
        d = self.__getstate__()
        d.update(k)
        return MulticalCamera(**d)
