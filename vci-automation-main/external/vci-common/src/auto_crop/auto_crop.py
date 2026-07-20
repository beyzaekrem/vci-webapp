from pathlib import Path

import cv2
import numpy as np
import json
from natsort import natsorted
import shutil


# crops the rgb images and masks to the foreground region.
# Creates cropped_camera_matrix.json with cropped camera_matrices
def main():
    capture_dir = Path("Capture/Tests/bonn_tele_bench_004")
    output_dir = Path("Capture/Tests/bonn_tele_bench_004_cropped")
    calibration_file_path = capture_dir / "calibration_dome.json"

    # check if calibration file exists
    if not Path(calibration_file_path).exists():
        raise Exception(f"calibration file does not exist {calibration_file_path}")

    # CalibrationCropper writes new crop_calib.json for us.
    calibration_cropper = CalibrationCropper(calibration_file_path, output_dir / "cropped_camera_matrix.json")

    # loop though all frame folders and crop the images
    frame_names = natsorted([f.name for f in capture_dir.iterdir() if f.suffix == ""])
    for idx, frame in enumerate(frame_names, start=1):  # frame_00001, frame_00002, frame_00003 ...
        print(f"auto crop {idx}/{len(frame_names)}    -    {capture_dir / frame}")
        crop_frame(frame,
                   capture_dir,
                   output_dir,
                   calibration_cropper)
    print("\nDone. Results saved to", output_dir)


def crop_frame(frame_name: str, input_dir, output_dir, calibration_cropper, padding=10):
    rgb_folder = input_dir / frame_name / "rgb"
    mask_folder = input_dir / frame_name / "mask"

    rgb_output = output_dir / frame_name / "rbg"
    mask_output = output_dir / frame_name / "mask"

    # check if rgb folder and mask folder exist
    if not rgb_folder.exists():
        raise FileNotFoundError(f"rgb_folder {rgb_folder} does not exist")
    if not mask_folder.exists():
        raise FileNotFoundError(f"mask_folder {mask_folder} does not exist")

    image_names = natsorted([f.name for f in rgb_folder.iterdir()])
    mask_names = [f.name for f in mask_folder.iterdir()]

    # crop the images, masks and camera_matrices
    for image_name in image_names:
        camera_id = Path(image_name).stem
        mask_name = [mask_name for mask_name in mask_names if Path(image_name).stem in mask_name]
        if len(mask_name) == 0:
            print(Warning(f"Couldn't find a mask for camera {camera_id} in mask_folder {mask_folder}."
                          f"\nSkipping this image."))
            continue
        else:
            mask_name = mask_name[0]

        # crop image
        rgb = cv2.imread(str(rgb_folder / image_name), cv2.IMREAD_COLOR)
        mask = cv2.imread(str(mask_folder / mask_name), cv2.IMREAD_COLOR)

        rgb_cropped, mask_cropped, crop_region = crop_to_mask_bbox(rgb, mask, padding)

        rgb_output.mkdir(exist_ok=True, parents=True)
        mask_output.mkdir(exist_ok=True, parents=True)
        cv2.imwrite(str(rgb_output / image_name), rgb_cropped)
        cv2.imwrite(str(mask_output / image_name), mask_cropped)

        # crop camera_matrix
        calibration_cropper.crop_camera_matrix(frame_name, camera_id, crop_region)
    calibration_cropper.write()


def crop_to_mask_bbox(rgb: np.array, mask: np.array, padding: int = 10):
    if rgb is None or mask is None:
        raise ValueError("rgb or mask image could not be read")

    if mask.shape[2] == 3:
        mask = mask[:, :, 0]
    ys, xs = np.where(mask > 0)
    if len(xs) == 0 or len(ys) == 0:
        raise ValueError("Mask has no non-zero values")

    # Compute bounding box with padding
    x_min = int(max(xs.min() - padding, 0))
    x_max = int(min(xs.max() + padding, rgb.shape[1] - 1))
    y_min = int(max(ys.min() - padding, 0))
    y_max = int(min(ys.max() + padding, rgb.shape[0] - 1))

    # Crop RGB and mask
    rgb_cropped = rgb[y_min:y_max + 1, x_min:x_max + 1]
    mask_cropped = mask[y_min:y_max + 1, x_min:x_max + 1]
    crop_region = [[x_min, y_min], [x_max, y_max]]

    return rgb_cropped, mask_cropped, crop_region


class CalibrationCropper:
    def __init__(self, input_path: Path, output_path: Path):

        shutil.copy(input_path, output_path.parent / input_path.name)
        self.original_camera_matrices, self.original_timestamp = self._read_original_calib_data(input_path)
        self.output_path = output_path
        self.frame_entries = {}

    @staticmethod
    def _read_original_calib_data(input_path: Path):
        with open(input_path) as f:
            calib_data = json.load(f)
        camera_entries = calib_data["cameras"]

        original_camera_matrices = {}
        for cam_entry in camera_entries:
            cam_id = cam_entry["camera_id"]
            camera_matrix = cam_entry["intrinsics"]["camera_matrix"]
            camera_matrix = np.array(camera_matrix).reshape((3, 3))
            original_camera_matrices[cam_id] = camera_matrix
        return original_camera_matrices, calib_data.get("timestamp")

    def crop_camera_matrix(self, frame_name: str, camera_id: str, crop_region):
        original = self.original_camera_matrices[camera_id]
        cropped_matrix = self._crop_matrix(original, crop_region)
        resolution = [crop_region[1][0] - crop_region[0][0], crop_region[1][1] - crop_region[0][1]]

        if frame_name not in self.frame_entries:
            self.frame_entries[frame_name] = {}
        self.frame_entries[frame_name].update({camera_id: {"crop_region": crop_region,
                                                           "camera_matrix": cropped_matrix.flatten().tolist(),
                                                           "resolution": resolution}})

    @staticmethod
    def _crop_matrix(camera_matrix: np.array, crop_region):
        # principal point (optical center)
        cx, cy = camera_matrix[0, 2], camera_matrix[1, 2]
        # focal length in pixels
        fx, fy = camera_matrix[0, 0], camera_matrix[1, 1]

        # crop
        cx = cx - crop_region[0][0]
        cy = cy - crop_region[0][1]
        # focal lengths stay the same. Cropping does not change the scaling of the pixels

        cropped_camera_matrix = np.array([
            [fx, 0, cx],
            [0, fy, cy],
            [0, 0, 1],
        ])
        return cropped_camera_matrix

    def write(self):
        cropped_calib_data = {"meta": "intrinsic camera_matrices of cropped images",
                              "timestamp_original_calib": self.original_timestamp,
                              "frames": self.frame_entries}
        with open(self.output_path, "w") as f:
            json.dump(cropped_calib_data, f, indent=2)


if __name__ == "__main__":
    main()
