from __future__ import annotations

from collections import namedtuple

import cv2
import kornia
import numpy as np
import torch

import sparrow.gibbs_wrapper as gibbs
from sparrow.utils import CudaTimer, Timer, logger

NDIM_COLOR = 3
NDIM_MONO = 2


class CharucoDetector:

    def __init__(self) -> None:
        self.set_board()

    def set_board(
        self,
        dict_name: str = "4X4_1000",
        size: tuple = (29, 19),
        square_length: float = 0.040,
        marker_length: float = 0.031,
    ) -> None:
        """
        Sets charuco board parameters
        """
        dict_id = dict_name if isinstance(dict_name, int) else getattr(cv2.aruco, f"DICT_{dict_name}")
        aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
        board = cv2.aruco.CharucoBoard(size, square_length, marker_length, aruco_dict)
        self.cv2_charcuo_detector = cv2.aruco.CharucoDetector(board)

    def detect_board(self, images: list[gibbs.GibbsImage]) -> tuple[list[dict[str, list[int]]], list[bool]]:
        """
        Runs charuco board detection on the given set of tensor images.
        Recomended processing steps: ["debayer_malvar", "non_linear", "hist_scale"]

        The images get processed further for detection. The current version is designed for images of size [4608, 5328]

        Returns:

            detections (list):
                Each detection is a dictionray with the following strcuture: {
                "corners" (list[int]): the detected corners as a flattened list.
                "ids" (list[int]): the detected ids as a flattened list.
                "cnt" (int): number of detected ids.
                }


            detection_success (list[bool]): detection success per camera

        Empty detections also return the same dictionary structure
        """

        detections: list[dict[str, list]] = []
        detection_success: list[bool] = []

        with Timer(f"charuco detection for {len(images)} cameras"):
            for image in images:
                with CudaTimer(f"processing {image.camera_id}", enabled=False):
                    if image.image_type == gibbs.ImageType.Mono:
                        # performs pre-processing for mono images to reduce noise of projected IR pattern
                        image.pixels = preprocess_mono_gpu(image.pixels[None, None])[0, 0]
                    elif image.image_type == gibbs.ImageType.Color:
                        # reduces channels to single green channel and reduces salt and pepper noise
                        image.pixels = preprocess_color_gpu(image.pixels[None])[0, 0]
                    elif image.image_type == gibbs.ImageType.Depth:
                        logger.debug(f"process D image for detection {image.pixels.shape}")
                        # does no processing for depth images
                        # (3, W, H) -> (W, H)
                        image.pixels = image.pixels[1, :, :]  # only green channel
                    else:
                        msg = f"Unknown camera type {image.image_type} for charuco detection"
                        raise ValueError(msg)

                if image.ndim != NDIM_MONO:  # Shape should be (W, H)
                    msg = f"Processed image for charuco detection has invalid shape {image.shape}"
                    raise ValueError(msg)
                # the processed_img is a tensor of shape [W, H] (single channel image)
                corners, ids, cnt = self._run_detection_tensor(image)
                if ids is None:
                    # empty detection
                    detections.append(
                        {
                            "corners": np.zeros([0, 2]).flatten().tolist(),
                            "ids": np.zeros(0, dtype=int).flatten().tolist(),
                            "cnt": cnt,
                        }
                    )
                    detection_success.append(False)
                else:
                    detections.append(
                        {
                            "corners": corners.squeeze(1).flatten().tolist(),
                            "ids": ids.squeeze(1).flatten().tolist(),
                            "cnt": cnt,
                        }
                    )
                    detection_success.append(True)

        return detections, detection_success

    def annotate_images(
        self, images: list[gibbs.GibbsImage], detections: list[dict[str, list]]
    ) -> list[gibbs.GibbsImage]:
        """
        Annotates a given tensor image with the detected points.
        Writes text in the upper left corner <camera_id> <corner cnt>
        """

        for image, detection in zip(images, detections, strict=True):
            # detected corners are drawn into a black image, with text in upper left corner <camera_id> <corner cnt>
            h, w = image.shape[-2:]
            shape = (h, w, 3) if image.ndim == NDIM_COLOR else (h, w)
            annotation_overlay = np.zeros(shape, dtype=np.float32)
            cnt = detection.get("cnt")
            text = f"{image.camera_id} {cnt}"
            if cnt > 0:
                # Load corners and ids and convert back to proper OpenCV arrays

                corners_list = detection.get("corners")
                ids_list = detection.get("ids")

                # corners_list is flat: [x0, y0, x1, y1, ...]
                corners_np = np.array(corners_list, dtype=np.float32).reshape(-1, 1, 2)

                # ids_list is flat: [id0, id1, ...]
                ids_np = np.array(ids_list, dtype=np.int32).reshape(-1, 1)

                annotation_overlay = cv2.aruco.drawDetectedCornersCharuco(
                    annotation_overlay,
                    corners_np,
                    ids_np,
                )
            else:
                text += " No Charuco Board Found"
            cv2.putText(
                annotation_overlay,
                text,
                (10, 100),
                cv2.FONT_HERSHEY_SIMPLEX,
                3,
                (0.8, 0.8, 0.8),
                5,
            )

            # move annotation image to torch gpu to apply overlay to the tensor image
            annotation_torch = torch.from_numpy(annotation_overlay)
            if image.ndim == NDIM_COLOR:
                annotation_torch = annotation_torch.permute(2, 0, 1)  # (H,W,3) -> (3,H,W)
            annotation_torch = annotation_torch.cuda()
            image.pixels = torch.clamp((image.pixels + annotation_torch), 0.0, 1.0)
        return images

    def _run_detection_tensor(self, image: gibbs.GibbsImage) -> tuple[np.array | None, np.array | None, int]:
        """
        runs charuco board detection on tensor image.
        The tensor is converted to numpy and run though cv2 charuco detection.

        Input
            image(GibbsImage) of shape [W, H]

        Returns
            corners (np.array | None) detected corners
            ids (np.array | None) detected ids
            cnt (int) number of detected ids. (0 when nothing was detected)
        """
        if image.ndim == NDIM_COLOR and image.shape[0] == 1:  # mono image with three channels
            image.pixels = image.pixels[0]
        # Move to CPU
        img: torch.tensor = image.pixels.detach().cpu()

        # performing aruco detection with opencv
        img_np: np.array = (img * 255).byte().numpy()
        corners, ids, _, _ = self.cv2_charcuo_detector.detectBoard(img_np)
        cnt = 0 if ids is None else len(ids)
        logger.info(f"Charuco board detection  ----  {image.camera_id}    {cnt}")
        return corners, ids, cnt


def preprocess_color_gpu(
    img: torch.tensor,  # (B, 3, W, H)
) -> torch.Tensor:
    """
    processed color image tensors for charuco board detection.
    Reduces the image to the green channel (the brightest one)
    and performs multiple tiny median filters to reduce salt and pepper noise

    Input: img of shape [1, 3, W, H]

    Returns: img of shape [1, 1, W, H]
    """
    img = img[:, 1:2, :, :]  # only green channel. shape (B, 1, W, H)
    # reducing channels before blur saves time

    # remove salt and pepper noise with repeated tiny median blurs
    for _ in range(3):
        img = kornia.filters.median_blur(img, (3, 3))
    return img


def preprocess_mono_gpu(
    img: torch.tensor,  # (B, 1, W, H)
    blur_sigma_full: int = 550,  # strength of normalization. Lower = stronger normalization. Tuned for [4608, 5328]
    clahe_clip: float = 1.0,  # strength of local contrast scaling. Higher = stronger
    *,
    clahe: bool = True,  # enable/disable local contrast scaling
) -> torch.Tensor:
    """
    processes ir image tensors for charuco board detection.
    Evens out image illumination, boosts contrast locally and performs edge perserving blur.

    Input: img (tensor) of shape [1, 1, W, H] - tuned for [1, 1, 4608, 5328]

    Returns: processed_img (tensor) of shape [1, 1, W, H]
    """

    timers_enabled = False
    if timers_enabled:
        start = torch.cuda.Event(enable_timing=True)
        end = torch.cuda.Event(enable_timing=True)
    else:
        start = None
        end = None

    ScaleFactor = namedtuple("ScaleFactor", "normalize guided_blur")
    scaling_factors = {
        "large": ScaleFactor(0.125, 0.375),  # scale factor tune for [4608, 5328]
        "small": ScaleFactor(1, 1),
    }
    image_width = img.shape[2]
    scale_factor = scaling_factors["large"] if image_width > 1000 else scaling_factors["small"]

    with CudaTimer("median blur x 4", start, end, enabled=timers_enabled):
        # remove salt and pepper noise with repeated tiny median blurs
        for _ in range(3):
            img = kornia.filters.median_blur(img, (3, 3))

    with CudaTimer("normalize", start, end, enabled=timers_enabled):
        # normalize illumination to remove soft shadows/gardients
        norm = normalize(img, scale_factor.normalize, blur_sigma_full)

    with CudaTimer("clahe", start, end, enabled=timers_enabled):
        # --- local contrast scaling ---
        if clahe:
            norm = kornia.enhance.equalize_clahe(norm, clip_limit=clahe_clip)

    with CudaTimer("guided blur on downscaled", start, end, enabled=timers_enabled):
        # --- edge perserving blur ---
        # Downscale for speed
        norm_small = kornia.geometry.resize(
            norm,
            (
                int(norm.shape[-2] * scale_factor.guided_blur),
                int(norm.shape[-1] * scale_factor.guided_blur),
            ),
            interpolation="bilinear",
        )

        # --- edge perserving blur on downscaled ---
        norm_guided_small = kornia.filters.guided_blur(
            guidance=norm_small,
            input=norm_small,
            kernel_size=(3, 3),  # kernel size tuned for [4608, 5328] + scale factor 0.375
            eps=1e-2,  # eps controls blur strength. tuned for [4608, 5328] + scale factor 0.375
        )

    with CudaTimer("edge detection on downscaled", start, end, enabled=timers_enabled):
        # edge detection performed on downscaled blured image. Tuned for [4608, 5328] + scale factor 0.375
        edges_hybrid = edge_detection(norm_guided_small)

    with CudaTimer("upscale back", start, end, enabled=timers_enabled):
        # --- Upscale back ---
        norm_guided_blur = kornia.geometry.resize(norm_guided_small, norm.shape[-2:], interpolation="bilinear")
        edges_hybrid = kornia.geometry.resize(edges_hybrid, norm.shape[-2:], interpolation="bilinear")

    with CudaTimer("compose edges", start, end, enabled=timers_enabled):
        # compose edges of none-blurred image onto blurred image
        # essentially 'sharpens' edges
        blurred_squares_sharp_edges = edges_hybrid * norm + (1 - edges_hybrid) * norm_guided_blur
        blurred_squares_sharp_edges = torch.clamp(blurred_squares_sharp_edges, 0, 1)

    return blurred_squares_sharp_edges  # noqa: RET504


def normalize(img: torch.tesnor, downscale: float, blur_sigma_full: float) -> torch.tensor:
    # --- Downscale for fast illumination estimation ---
    small = torch.nn.functional.interpolate(img, scale_factor=downscale, mode="area")

    # --- Gaussian blur for illumination ---

    sigma_small = blur_sigma_full * downscale
    _, _, h_s, w_s = small.shape  # Dimensions of the downscaled image
    max_sigma = (min(h_s, w_s) - 1) / 8.0  # kernel size (6*sigma +1 must be <= image size)
    sigma_small = min(sigma_small, max_sigma)
    # compute kernel size similar to OpenCV automatic choice
    ksize = max(3, int(2 * round(3 * sigma_small) + 1))  # roughly 3*sigma rule
    blur_small = kornia.filters.gaussian_blur2d(
        small,
        (ksize, ksize),
        (sigma_small, sigma_small),
    )

    # --- Upscale blur back ---
    blur = torch.nn.functional.interpolate(blur_small, size=img.shape[-2:], mode="bicubic")

    # --- Flatten illumination ---
    norm = (img / (blur + 1e-6)) * 0.5
    return torch.clamp(norm, 0, 1)


def edge_detection(img: torch.tensor) -> torch.tensor:
    edges = kornia.filters.canny(img, low_threshold=0.05, high_threshold=0.15)[0]
    edges_soft = kornia.filters.gaussian_blur2d(
        edges, (3, 3), (1.5, 1.5)
    )  # kernel size (3,3) tuned for [4608, 5328] + scale factor 0.375
    local_mean = kornia.filters.box_blur(
        edges_soft, (15, 15)
    )  # kernel size (15, 15) tuned for [4608, 5328] + scale factor 0.375
    edges_binary = (edges_soft > (local_mean + 0.05)).float()

    # --- Hybrid weighting ---
    # mix binary strong edges with softened edges
    return 0.7 * edges_binary + 0.3 * edges_soft
