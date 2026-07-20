import cv2
import numpy as np

from .board import Board
from .camera import Camera
from .detection_data import DetectionData
from .exceptions import InvalidDetectionData


def calibrate_intrinsics(
    camera: Camera,
    detected_points: list[dict[str : np.array]],
    board: Board,
    resolution: tuple[int, int],
    max_iter=10,
    eps=1e-3,
) -> tuple[Camera, float]:
    """
    Calibrates a Cameras intrinsic parameters from detected charuco points.
    Args:
        detected_points (list[dict[str: np.array|None]]): Detections of the camera, indexed as detections[frame_idx]
            Each dict contains:
                - "ids" (np.ndarray|None)
                - "corners" (np.ndarray|None)
        board (Board): charuco board definition
        camera_id (str): camera Id
        resolution (tuple[int,int]): (width, height) of the camera

    Returns:
        cameras (list[Camera]): Camera objects containing the intrinsic matric, distortion coefficients and resolution

        err (list[float]): RMS Error per camera

    """
    # only non-empty detections. Image sync doesn't matter for intrinsic calibration
    detected_points = [
        detection for detection in detected_points if DetectionData.detection_is_valid(board, detection["ids"])
    ]
    detected_ids = [detection["ids"] for detection in detected_points]
    detected_corners = [np.array(detection["corners"], dtype=np.float32) for detection in detected_points]
    objectPoints = [np.array([board.charuco_points[id] for id in ids], dtype=np.float32) for ids in detected_ids]

    # termination criteria
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, max_iter, eps)
    flags = 0

    if len(detected_corners) == 0:
        msg = "No image points."
        raise InvalidDetectionData(msg)

    err, intrinsic, distortion_coeffs, _, _ = cv2.calibrateCamera(
        objectPoints,
        detected_corners,
        resolution,  # (width, height)
        None,
        None,
        criteria=criteria,
        flags=flags,
    )
    camera.set_intrisics(intrinsic, distortion_coeffs, resolution)
    return camera, err
