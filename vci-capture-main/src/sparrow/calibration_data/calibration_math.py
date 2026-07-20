## helper funcitons and default processing steps.
from __future__ import annotations

import numpy as np
import torch  # noqa: TC002

from sparrow.modes.handler_exceptions import InvalidProcessingStepError


def scale_intrincis_matrix(intrinsic_matrix: torch.tensor, image_shape: np.array, resolution: np.array) -> torch.tensor:
    # image shape will be either [C, H, W] or [H, W]
    # depending on how the image is rotated and was calibrated the resolution [H,W] might not fit.
    # to prevent almost imperceptible errors, we find the smaller of the dimenions to scale with.
    img_m = min(image_shape[-2:])
    res_m = min(resolution[-2:])  # the resolution should usually have only 2 dimensions, but just in case
    factor = img_m / res_m
    return intrinsic_matrix * factor


def check_resolution(image_shape: np.array, resolution: np.array, *, allow_scale: bool) -> bool:
    """
    Checks if the image_shape matches the calibrated resolution.
    With allow_scale, a matching form factor is valid: image_shape = resolution * X, X element of real numbers

    raises InvalidProcessingStepError
    """
    # image_shape is torch shape: [C,H,W] or [H,W]
    # image_resolution is the calibrated resolution of the (raw) caputre: [W, H]
    image_s = np.array(image_shape[-2:])  # [C,H,W] | [H,W] -> [H,W]
    resolution: np.array = resolution[:2][::-1]  # [W,H,C] | [W,H] -> [H,W]

    if allow_scale:  # a scale mismatch is allowed. But both images should have the same format: e.g: both are landscape
        scale: np.array = (
            image_s / resolution
        )  # [1000, 2000] / [4000, 2000] = [0.25, 1] -> len(set) == 2 -> mismatching form

        if len(set(scale)) == 1:
            pass  # matching form-factor
        else:
            msg = f"The image_shape {image_s} does not match the form-factor of the calibration data {resolution} * X !"
            step = ""
            raise InvalidProcessingStepError(step, msg)
    elif image_s != resolution:
        msg = f"The image_shape {image_s} does not match the resolution {resolution} of the calibration data! "
        step = ""
        raise InvalidProcessingStepError(step, msg)
    else:
        pass  # the resolution matches perfectly


def check_orthogonality(view_matrix: np.array) -> None:
    rot = view_matrix.reshape([4, 4])[:3, :3]
    idenity_check = np.dot(rot.T, rot)
    error = np.linalg.norm(idenity_check - np.eye(3))
    if error >= 1e-6:  # noqa: PLR2004
        msg = f"view_matrix is not orthogonal. Error: {error}"
        raise ValueError(msg)


def polar_reorthogonalize(view_matrix: np.array, error: float = 1e-6) -> None:
    check_orthogonality(view_matrix)
    pos_beginning = get_world_pos(view_matrix)
    m = view_matrix.reshape(4, 4)
    rot = m[:3, :3]
    trans = m[:3, 3]  # This is NOT the world position

    # SVD decomposition
    u, _, vh = np.linalg.svd(rot)

    # The closest orthogonal matrix is U * V^H
    rot_corrected = np.dot(u, vh)

    # Ensure it's a right-handed system (det = 1, not -1)
    if np.linalg.det(rot_corrected) < 0:
        u[:, -1] *= -1
        rot_corrected = np.dot(u, vh)

    res = np.eye(4)
    res[:3, :3] = rot_corrected
    res[:3, 3] = trans
    pos_end = get_world_pos(res)

    if not np.allclose(pos_beginning, pos_end, error):
        msg = f"Position before: {pos_beginning}, after: {pos_end}. "
        "view_matrix world position shifted to much when applying re-orthogonalization. "
        raise ValueError(msg)

    return res


def get_world_pos(view_matrix: np.array) -> np.array:
    extrinsic_matrix = view_matrix.reshape((4, 4))
    rot = extrinsic_matrix[:3, :3]
    t = extrinsic_matrix[:3, 3].reshape(3, 1)
    world_pos = -rot.T @ t
    return world_pos.flatten()
