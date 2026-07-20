import torch


def rotation_to_quaternion(R: torch.Tensor) -> torch.Tensor:
    """Convert a rotation matrix to a quaternion.

    Args:
        rotation (torch.Tensor): A rotation matrix of shape (3, 3).

    Returns:
        torch.Tensor: A quaternion of shape (4,) in (w, x, y, z) format.
    """
    # Numerical safety: clamp values inside sqrt to >= 0
    a = torch.clamp(1 + R[0, 0] + R[1, 1] + R[2, 2], min=0.0)
    b = torch.clamp(1 + R[0, 0] - R[1, 1] - R[2, 2], min=0.0)
    c = torch.clamp(1 - R[0, 0] + R[1, 1] - R[2, 2], min=0.0)
    d = torch.clamp(1 - R[0, 0] - R[1, 1] + R[2, 2], min=0.0)

    qw = torch.sqrt(a) / 2
    qx = torch.sqrt(b) / 2 * torch.sign(R[2, 1] - R[1, 2])
    qy = torch.sqrt(c) / 2 * torch.sign(R[0, 2] - R[2, 0])
    qz = torch.sqrt(d) / 2 * torch.sign(R[1, 0] - R[0, 1])
    return torch.stack([qw, qx, qy, qz])


def normalize_quaternion(quaternion: torch.Tensor) -> torch.Tensor:
    """Normalize a quaternion.

    Args:
        quaternion: (4,) quaternion in (w, x, y, z) format

    Returns:
        torch.Tensor: normalized quaternion: (4,)
    """
    return quaternion / (quaternion.norm(p=2) + 1e-8)


def quaternion_to_matrix(quaternion: torch.Tensor) -> torch.Tensor:
    """Convert a quaternion to a rotation matrix.

    Args:
        quaternion: (4,) quaternion in (w, x, y, z) format

    Returns:
        torch.Tensor: rotation matrix of shape (3, 3)
    """
    q = normalize_quaternion(quaternion)
    w, x, y, z = q

    return torch.stack(
        [
            torch.stack([1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)]),
            torch.stack([2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)]),
            torch.stack([2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]),
        ]
    )
