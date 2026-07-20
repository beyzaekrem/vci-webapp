import numpy as np
from PIL import Image, ImageDraw, ImageFont


def overlay_detected_points(
    base_image: Image.Image | None,
    gridsize: tuple[int, int],
    camera_names: list[str],
    detections: list[list[dict[str, np.ndarray | str]]],
    resolutions: tuple[int, int],
) -> Image.Image:
    """
    Overlay detected calibration points + detected cam_id onto a multi-view grid image.

    Args:
        base_image: Grid image returned by merge_views_to_grid. Can be None.
        gridsize: (grid_width, grid_height) used in merge_views_to_grid.
        camera_names: List of camera IDs
        detections: All Detections. detections[camera_idx][frame_idx] = {"idx": [], "corners": []}
                    Each dict contains:
                        - "ids": np.ndarray|None
                        - "corners": np.ndarray|None
        resolution: List of (image_width, image_height) per camera
    Returns:
        Image.Image: The grid with overlays drawn.
    """

    grid_w, grid_h = gridsize
    if base_image is None:
        resolution = resolutions[0]
        img = Image.new(
            "RGB", ((resolution[0] // 4) * grid_w, (resolution[1] // 4) * grid_h)
        )
    else:
        img = base_image.copy()  # keep original safe
    draw = ImageDraw.Draw(img)
    target_w = img.size[0] // grid_w  # pixel width of sub_image in base_img
    target_h = img.size[1] // grid_h  # pixel height of sub_image in base_img

    try:
        font = ImageFont.truetype("arial.ttf", size=30)
    except IOError:
        font = ImageFont.load_default()

    num_frames = len(detections[0])
    # draw detections for all frames
    for cam_idx, cam_id in enumerate(camera_names):
        for frame in range(num_frames):
            det = detections[cam_idx][frame]
            resolution = resolutions[cam_idx]
            if det is None:
                continue

            corners = det.get("corners")

            # Offset for this camera’s image in the grid
            offset_x = (cam_idx % grid_w) * target_w
            offset_y = (cam_idx // grid_w) * target_h

            # Scale factor from original resolution to resized grid cell
            scale_x = target_w / resolution[0]
            scale_y = target_h / resolution[1]

            # --- draw points ---
            if corners is not None:
                for px, py in corners.reshape(-1, 2):
                    x = int(px * scale_x) + offset_x
                    y = int(py * scale_y) + offset_y
                    r = 4
                    draw.ellipse(
                        (x - r, y - r, x + r, y + r),
                        fill="red",
                        outline="white",
                        width=1,
                    )

    # draw text once per camera
    try:
        font = ImageFont.truetype("arial.ttf", size=40)  # large font
    except IOError:
        font = ImageFont.load_default(size=40)

    for cam_idx, cam_id in enumerate(camera_names):
        board_poses = 0
        total_points = 0
        for frame in range(num_frames):
            det = detections[cam_idx][frame]
            c = len(det.get("ids"))
            if c > 0:
                board_poses += 1
            total_points += c

        # format text
        text = f"{cam_id} ({board_poses} poses, {total_points} points)"

        text_h = font.getbbox(text)[3]

        # bottom-left of sub-image
        x = (cam_idx % grid_w) * target_w + 20
        y = (cam_idx // grid_w) * target_h + target_h - text_h - 20

        draw.text(
            (x, y),
            text,
            fill="white",
            font=font,
            stroke_width=3,
            stroke_fill="black",
        )

    return img
