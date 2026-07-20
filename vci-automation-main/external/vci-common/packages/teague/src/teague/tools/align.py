"""Align coordinate systems between different calibrations."""

import argparse

import torch
from tqdm import tqdm

from teague.calibration import Calibration, ImportSettings, LegacyImportSettings
from teague.util import normalize_quaternion, quaternion_to_matrix


def build_T(R: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
    """Homogeneous transform (column-vector convention): y = R x + t."""
    T = torch.eye(4, device=R.device, dtype=R.dtype)
    T[:3, :3] = R
    T[:3, 3] = t
    return T


def apply_T_points(T: torch.Tensor, X: torch.Tensor) -> torch.Tensor:
    """Apply T to 3D points (N,3), column-vector convention."""
    R = T[:3, :3]
    t = T[:3, 3]
    return (R @ X.T).T + t  # equivalent to (R @ X.T).T + t


def align_once(
    source_positions: torch.Tensor,
    target_positions: torch.Tensor,
    steps: int = 1_000,
    lr: float = 1e-1,
):
    """Align source_positions to target_positions using gradient-based optimization.
    source_positions: (N,3)
    target_positions: (N,3)

    Returns:
        T: (4,4) homogeneous transform as torch.Tensor
        rating: float final mean-squared error after optimization
    """
    device = source_positions.device

    # Initialize translation from mean difference; keep inputs unchanged.
    X = source_positions.detach()
    Y = target_positions.detach()
    src_mean = X.mean(dim=0)
    tgt_mean = Y.mean(dim=0)

    # Initialize
    q = torch.randn(4, device=device, dtype=source_positions.dtype, requires_grad=True)
    with torch.no_grad():
        q.copy_(normalize_quaternion(q))
    t = (tgt_mean - src_mean).clone().detach().requires_grad_(True)

    optimizer = torch.optim.Adam([q, t], lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=steps)
    for _ in range(steps):
        optimizer.zero_grad()

        R = quaternion_to_matrix(q)
        X_aligned = (R @ X.T).T + t
        loss = torch.mean((X_aligned - Y) ** 2)
        loss.backward()
        optimizer.step()
        scheduler.step()

        with torch.no_grad():
            q.copy_(normalize_quaternion(q))
    with torch.no_grad():
        R = quaternion_to_matrix(q)
        X_aligned = (R @ X.T).T + t
        T = build_T(R, t)

    mae = (X_aligned - Y).norm(p=2, dim=1).mean().item()
    return T, mae


def main():
    # Parse arguments
    argparser = argparse.ArgumentParser(description="Align coordinate systems between different calibrations.")
    argparser.add_argument(
        "source_calibration",
        type=str,
        help="Path to the source calibration file.",
    )
    argparser.add_argument(
        "target_calibration",
        type=str,
        help="Path to the target calibration file.",
    )
    argparser.add_argument(
        "--n",
        type=int,
        help="Number of alignment attempts to perform (best result is kept).",
        default=10,
    )
    argparser.add_argument(
        "--threshold_cm",
        type=float,
        help="Per-camera error threshold in cm used to remove bad cameras and re-run alignment.",
        default=0.1,
    )
    argparser.add_argument(
        "--max_iter",
        type=int,
        help="Maximum number of re-alignment iterations when removing bad cameras.",
        default=10,
    )
    args = argparser.parse_args()

    source_calibration = Calibration(args.source_calibration, import_settings=ImportSettings.as_is())
    s = ImportSettings(legacy=LegacyImportSettings(up_is_down=True, c0004_is_origin=False))
    target_calibration = Calibration(args.target_calibration, import_settings=s)

    # Find common cameras
    common_cameras = sorted(set(source_calibration.cameras.keys()).intersection(set(target_calibration.cameras.keys())))
    if len(common_cameras) < 3:
        raise ValueError("not enough common cameras found between source and target calibration. Need at least 3.")
    print(f"Found {len(common_cameras)} common cameras: {', '.join(common_cameras)}")

    # Iteratively align and remove cameras with large per-camera error.
    max_iter = args.max_iter
    current_cameras = list(common_cameras)
    best_overall_T = None
    final_cam_errors = None
    best_T = None

    for i in range(max_iter):
        print("\n" + "--" * 40)
        print(f"Iteration {i+1}: aligning using {len(current_cameras)} cameras: {', '.join(current_cameras)}")

        # Build position tensors for the current camera set
        source_positions = torch.stack([source_calibration.cameras[c].get_position() for c in current_cameras], dim=0)
        target_positions = torch.stack([target_calibration.cameras[c].get_position() for c in current_cameras], dim=0)

        # Align
        best_rating = float("inf")
        all_ratings = []
        for _ in tqdm(range(args.n), desc="Alignment attempts", dynamic_ncols=True):
            T, rating = align_once(source_positions, target_positions)
            all_ratings.append(rating)
            if rating < best_rating:
                best_rating = rating
                best_T = T

        # Print results for this iteration
        print(f"Average MAE over {args.n} attempts: {sum(all_ratings)/len(all_ratings)*100:.6f} [cm]")
        print(f"Best MAE (final): {best_rating*100:.6f} [cm]")

        # Compute per-camera errors (in cm)
        with torch.no_grad():
            X_aligned = apply_T_points(best_T, source_positions)
            errors_m = torch.norm(X_aligned - target_positions, dim=1)
            errors_cm = (errors_m * 100.0).tolist()
        cam_errors = sorted(zip(current_cameras, errors_cm), key=lambda x: x[1], reverse=True)

        # Report worst camera
        worst_cam, worst_err = cam_errors[0]
        print(f"Worst per-camera error: {worst_cam} = {worst_err:.3f} cm")

        # Determine which camera to remove: only remove the single worst camera
        # if its error exceeds the threshold. This prevents overly-aggressive pruning
        # in one iteration and makes the procedure conservative.
        if worst_err <= args.threshold_cm:
            print(f"All camera errors below threshold {args.threshold_cm} cm. Stopping.")
            print("\n" + "--" * 40)
            best_overall_T = best_T
            final_cam_errors = cam_errors
            break

        # Ensure we don't drop below 3 cameras by removing the worst one.
        if len(current_cameras) <= 3:
            print("Removing the worst camera would drop below 3 cameras; accepting current alignment and stopping.")
            best_overall_T = best_T
            final_cam_errors = cam_errors
            break

        print(f"Removing 1 camera with error > {args.threshold_cm} cm: {worst_cam}")
        current_cameras.remove(worst_cam)
    else:
        # Reached max iterations without meeting threshold
        print(f"Reached max iterations ({max_iter}). Using last alignment.")
        best_overall_T = best_T
        final_cam_errors = cam_errors

    # Final output: print transform and per-camera errors
    print("\n" + "--" * 40)
    if best_overall_T is not None:
        print("Homogeneous transform T (4x4):")
        T = best_overall_T.cpu()
        rows = ["[" + ", ".join(f"{' ' if v>=0 else ''}{v:.8f}" for v in row.tolist()) + "]" for row in T]
        print("[\n  " + ",\n  ".join(rows) + "\n]")
        print("Note: to apply T to the (world to camera) calibration matrix M, use: `M @ torch.linalg.inv(T)`")
    else:
        print("No alignment was produced.")

    if final_cam_errors is not None:
        print("Per-camera errors (cm) sorted high->low:")
        print(", ".join(f"  {cam_id}: {err:.3f} cm" for cam_id, err in final_cam_errors))


if __name__ == "__main__":
    main()
