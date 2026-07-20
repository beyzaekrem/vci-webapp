import time

import cv2
import kornia
import numpy as np
import torch

from controller.input_modules import CudaTimer
from controller.output_writers import PathStructure

PATH = "Capture/charuco"

IS_MONO_DIM = 2
IS_COLOR_DIM = 3


class LOG:
    def log(str):
        print(str)


class Calibration_Thing:

    allow_detection = True

    @classmethod
    def mode_name(cls) -> str:
        return "calibration"

    # record sequence to storage
    def __init__(self) -> None:

        board = self.create_charuco_board()
        self.charuco_detector = cv2.aruco.CharucoDetector(board)

    def create_charuco_board(
        self,
        dict_name: str = "4X4_1000",
        size: tuple = (29, 19),
        square_length: float = 0.040,
        marker_length: float = 0.031,
    ) -> cv2.aruco.CharucoBoard:
        dict_id = (
            dict_name
            if isinstance(dict_name, int)
            else getattr(cv2.aruco, f"DICT_{dict_name}")
        )
        aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
        return cv2.aruco.CharucoBoard(size, square_length, marker_length, aruco_dict)

    def charuco_detection(self, frame):
        images, requested_camera_ids = load_images(frame)
        print(f"loaded {len(images)} images\n")

        for image, cam_id in zip(images, requested_camera_ids):
            reset_cnt()
            print()

            start = time.time()
            print("    ", cam_id)
            if cam_id[0] == "M":
                image = self.preprocess_mono_gpu(image[None, None], cam_id, frame)[0, 0]
            else:
                image = self.preprocess_color_gpu(image[None, None], cam_id, frame)[
                    0, 0
                ]
            end = time.time()
            print(f"processing took {round(end-start, 4)} seconds")

            start = time.time()
            cnt = self.run_detection_tensor(
                image, cam_id, "processed", overwrite_run_detection=True
            )  # moves to cpu
            remember_result(frame, cam_id, cnt)
            print_detetion_result(frame, cam_id)
            end = time.time()
            print(f"cv2 aruco detection took {round(end-start, 4)} seconds")

        print_all_detection_results()

    def run_detection_tensor(self, tensor, cam_id, name, overwrite_run_detection=False):
        if self.allow_detection or overwrite_run_detection:
            if tensor.ndim == 3 and tensor.shape[0] == 1:
                tensor = tensor[0]

            # Move to CPU
            img = tensor.detach().cpu()

            img = np.array(img * 255).astype(np.uint8)
            cnt = self.run_detection(img, cam_id, "gpu", name)
            return cnt
        return 0

    detection_cnt: dict[str, list] = {}

    def run_detection(self, img, cam_id, device, name="detection"):
        corners, ids, marker_corners, marker_ids = self.charuco_detector.detectBoard(
            img
        )
        identifier = f"{device} {name}"
        if ids is None:
            LOG.log(f"{identifier} {cam_id}     ------")
            cnt = 0
        else:
            LOG.log(f"{identifier} {cam_id}     {len(ids)}")
            cnt = len(ids)

        if identifier not in self.detection_cnt:
            self.detection_cnt[identifier] = []
        self.detection_cnt[identifier].append(cnt)

        annotation_overlay = img.copy()
        # draw detected charuco board on overlay
        cv2.putText(
            annotation_overlay,
            f"{identifier} {cam_id} {cnt}",
            (10, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            3,
            (0.8, 0.8, 0.8),
            5,
        )
        if ids is not None:
            annotation_overlay = cv2.aruco.drawDetectedCornersCharuco(
                annotation_overlay, corners, ids
            )
        save_image(cam_id, device, f"{name}_detection", annotation_overlay)
        return cnt

    def preprocess_color_gpu(
        self,
        img_batch: torch.tensor,  # (B, x, W, H)
    ) -> torch.Tensor:
        for _ in range(4):
            img_batch = kornia.filters.median_blur(img_batch, (3, 3))
        return img_batch

    def preprocess_mono_gpu(
        self,
        img_batch: torch.tensor,  # (B, 1, W, H)
        cam_id,
        frame,
        blur_sigma_full=550,
        clahe=True,
        clahe_clip=1.0,
    ) -> torch.Tensor:

        start = torch.cuda.Event(enable_timing=True)
        end = torch.cuda.Event(enable_timing=True)
        # img: torch.float on GPU, shape (H,W)

        timers_enabled = False

        with CudaTimer("median blur x 4", start, end, timers_enabled):
            for _ in range(3):  # 4
                img_batch = kornia.filters.median_blur(img_batch, (3, 3))

        _save_tensor(img_batch, cam_id, "input")
        cnt = self.run_detection_tensor(
            img_batch[0, 0], cam_id, "input", overwrite_run_detection=True
        )
        remember_input_result(frame, cam_id, cnt)

        with CudaTimer("normalize", start, end, timers_enabled):
            norm = normalize(img_batch, 0.125, cam_id, blur_sigma_full)
        # _save_tensor(norm, cam_id, "norm")

        # self.run_detection_tensor(norm, cam_id, "norm")

        with CudaTimer("clahe", start, end, timers_enabled):

            # --- local contrast scaling ---
            if clahe:
                norm = kornia.enhance.equalize_clahe(norm, clip_limit=clahe_clip)

        _save_tensor(norm, cam_id, "clahe")
        # self.run_detection_tensor(norm, cam_id, "clahe")

        # edge perserving blur after clahe

        with CudaTimer("guided blur on downscaled", start, end, timers_enabled):
            # --- Guided blur ---
            # Downscale factor
            scale_factor = 0.375

            # --- Downscale ---
            norm_small = kornia.geometry.resize(
                norm,
                (
                    int(norm.shape[-2] * scale_factor),
                    int(norm.shape[-1] * scale_factor),
                ),
                interpolation="bilinear",
            )

            # --- Guided blur on downscaled ---
            norm_guided_small = kornia.filters.guided_blur(
                guidance=norm_small,
                input=norm_small,
                kernel_size=(3, 3),
                eps=1e-2,
            )

        with CudaTimer("edge detection on downscaled", start, end, timers_enabled):
            edges_hybrid = edge_detection(norm_guided_small, cam_id, dialate=False)

        with CudaTimer("upscale back", start, end, timers_enabled):
            # --- Upscale back ---
            norm_guided_blur = kornia.geometry.resize(
                norm_guided_small, norm.shape[-2:], interpolation="bilinear"
            )
            edges_hybrid = kornia.geometry.resize(
                edges_hybrid, norm.shape[-2:], interpolation="bilinear"
            )

        _save_tensor(norm_guided_blur, cam_id, "downscaled_norm_guided")
        _save_tensor(norm * edges_hybrid, cam_id, "edges_upscaled_norm")
        _save_tensor(edges_hybrid, cam_id, "edges_upscaled")

        with CudaTimer("compose edges", start, end, timers_enabled):
            new_best_maybe = edges_hybrid * norm + (1 - edges_hybrid) * norm_guided_blur
            new_best_maybe = torch.clamp(new_best_maybe, 0, 1)

        # _save_tensor(target, cam_id, "target")
        _save_tensor(new_best_maybe, cam_id, "new_best_maybe_downscale")
        self.run_detection_tensor(new_best_maybe, cam_id, "new_best_maybe_downscale")

        return new_best_maybe


def normalize(img, downscale, cam_id, blur_sigma_full):
    # --- Downscale for fast illumination estimation ---
    small = torch.nn.functional.interpolate(img, scale_factor=downscale, mode="area")

    # --- Gaussian blur for illumination ---
    sigma_small = blur_sigma_full * downscale
    # compute kernel size similar to OpenCV automatic choice
    ksize = max(3, int(2 * round(3 * sigma_small) + 1))  # roughly 3*sigma rule
    # print("blurring with ksize", ksize)
    blur_small = kornia.filters.gaussian_blur2d(
        small,
        (ksize, ksize),
        (sigma_small, sigma_small),
    )

    _save_tensor(blur_small, cam_id, "blur")

    # --- Upscale blur back ---
    blur = torch.nn.functional.interpolate(
        blur_small, size=img.shape[-2:], mode="bicubic"
    )

    # --- Flatten illumination ---
    norm = (img / (blur + 1e-6)) * 0.5
    # norm = (norm - norm.min()) / (norm.max() - norm.min() + 1e-6)
    norm = torch.clamp(norm, 0, 1)
    return norm


def edge_detection(
    img, cam_id, dialate=True
):  # todo: speed up. maybe peform edge detection on downscaled image
    # get edges in [0,1]
    edges = kornia.filters.canny(img, low_threshold=0.05, high_threshold=0.15)[0]
    _save_tensor(edges, cam_id, "edges")

    edges_soft = kornia.filters.gaussian_blur2d(edges, (3, 3), (1.5, 1.5))

    _save_tensor(edges_soft, cam_id, "edges_soft")

    local_mean = kornia.filters.box_blur(edges_soft, (15, 15))
    edges_binary = (edges_soft > (local_mean + 0.05)).float()
    _save_tensor(edges_binary, cam_id, "edges_local")

    # --- Hybrid weighting ---
    # thr = 0.3 * edges_soft.max()  # dynamic threshold
    # edges_binary = (edges_soft > thr).float()  # strong edges = 1, else 0

    # mix binary strong edges with softened edges
    edges_hybrid = 0.7 * edges_binary + 0.3 * edges_soft
    _save_tensor(edges_hybrid, cam_id, "edges_hybrid")

    if dialate:
        # Create a kernel (structuring element) for dilation
        kernel = torch.ones((3, 3), device=edges_hybrid.device)  # 2D kernel
        # Apply dilation
        edges_hybrid = kornia.morphology.dilation(edges_hybrid, kernel)
    # _save_tensor(edges_hybrid, cam_id, "edges_dilated")
    return edges_hybrid


def _save_tensor(tensor: torch.Tensor, cam_id: str, name: str):
    """
    Save a 2D tensor (H, W) or single-channel 3D tensor (1, H, W) as an image for debugging.
    Normalizes to 0-255 if needed.
    """
    if SAVE:
        if tensor.ndim == 4:
            tensor = tensor[0]
        if tensor.ndim == 3 and tensor.shape[0] == 1:
            tensor = tensor[0]

        # Move to CPU
        img = tensor.detach().cpu()

        img = np.array(img * 255).astype(np.uint8)

        # Save with OpenCV
        save_image(cam_id, "gpu", name, img)


device_cnt = {}


def reset_cnt():
    global device_cnt
    device_cnt = {}


def save_image(cam_id, device, name, image):
    if device not in device_cnt:
        device_cnt[device] = 0
    cv2.imwrite(
        f"{PATH}/detection/{cam_id}_{device}_{device_cnt[device]}_{name}.png", image
    )
    device_cnt[device] += 1


def load_images(frame):
    images = []

    for cameraid in camera_ids:
        image = cv2.imread(f"{PATH}/input/{frame}/rgb/{cameraid}.png", cv2.IMREAD_COLOR)
        green = image[..., 1]  # take green channel only
        t_image = torch.from_numpy(green).float() / 255.0
        t_image = t_image.cuda()
        images.append(t_image)
    return images, camera_ids


all_mono = [
    "M0001",
    "M0003",
    "M0005",
    "M0006",
    "M0007",
    "M0008",
    "M0009",
    "M0010",
    "M0011",
    "M0013",
    "M0014",
    "M0015",
    "M0016",
    "M0017",
    "M0018",
    "M0019",
    "M0021",
    "M0022",
    "M0023",
    "M0024",
]

camera_ids = [
    "M0005",
    "M0007",
    "M0008",
    "M0009",
    "M0010",
    "M0011",
    "M0024",
    "M0019",
    "M0021",
]

# camera_ids = all_mono
# camera_ids = camera_ids[:1]
# camera_ids = ["M0019"]
# camera_ids = ["M0005"]
# camera_ids = ["M0010", "M0011"]
camera_ids = ["M0015", "M0016"]

frames = range(6, 45)
frames = [1, 6, 7, 12]
# frames = [1]
# frames = [12]
frames = [14, 15]
SAVE = False
if len(frames) == 1:
    SAVE = True
if SAVE:
    PathStructure.clear_folder(f"{PATH}/detection")


def main():
    c = Calibration_Thing()
    c.allow_detection = False

    for idx in frames:
        frame = f"frame_{str(idx).zfill(5)}"
        print("\n", frame)
        c.charuco_detection(frame)
        # input("Enter")


# region PrintResult

detection_results = {}
input_results = {}


def remember_result(frame, cam_id, cnt):
    global detection_results

    if frame not in detection_results:
        detection_results[frame] = {}
    detection_results[frame][cam_id] = cnt


def remember_input_result(frame, cam_id, cnt):
    global input_results
    if frame not in input_results:
        input_results[frame] = {}
    input_results[frame][cam_id] = cnt


def print_all_detection_results(tolerance=5):
    """
    Compare new detection results against reference targets.

    Args:
        new_results (dict): same structure as `targets`
        targets (dict): reference detection counts
        tolerance (int): allowed difference before marking as ❌
    """
    for frame, cams in detection_results.items():
        print()
        print(f"\n📷 {frame}")
        if frame not in detection_results:
            print("   ⚠️  Frame missing in new results")
            continue

        for cam, target_val in cams.items():
            print_detetion_result(frame, cam, tolerance)


def print_detetion_result(frame, cam, tolerance=5):
    target_val = TARGETS.get(frame, {}).get(cam, 0)
    new_val = detection_results[frame].get(cam, 0)
    input_val = input_results.get(frame, {}).get(cam, 0)
    if target_val == 0 and new_val == 0:
        status = ""
    elif new_val == 0 and target_val != 0:
        status = "❌ (missed)"
    else:
        diff = new_val - target_val
        status = f"✅ (Δ={diff})" if diff >= -tolerance else f"❌ (Δ={diff})"
    result = f"   {cam}: input={input_val}, target={target_val}, new={new_val} {status}"
    print(result)


TARGETS = {
    "frame_00001": {
        "M0005": 502,
        "M0007": 496,
        "M0008": 445,
        "M0009": 422,
        "M0010": 233,
        "M0011": 443,
        "M0024": 8,
        "M0019": 137,
        "M0021": 270,
    },
    "frame_00006": {
        "M0005": 496,
        "M0007": 492,
        "M0008": 443,
        "M0009": 478,
        "M0010": 0,
        "M0011": 34,
        "M0024": 0,
        "M0019": 432,
        "M0021": 489,
    },
    "frame_00007": {
        "M0005": 348,
        "M0007": 340,
        "M0008": 0,
        "M0009": 103,
        "M0010": 0,
        "M0011": 0,
        "M0024": 0,
        "M0019": 0,
        "M0021": 86,
    },
    "frame_00012": {
        "M0005": 419,
        "M0007": 251,
        "M0008": 158,
        "M0009": 321,
        "M0010": 0,
        "M0011": 0,
        "M0024": 0,
        "M0019": 0,
        "M0021": 0,
    },
}

# endregion
if __name__ == "__main__":
    main()
