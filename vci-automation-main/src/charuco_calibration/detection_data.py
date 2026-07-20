import copy
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL.Image import Image
from typing_extensions import Self

from .board import Board
from .display_detected_points import overlay_detected_points

DetectionDict = dict[str, np.ndarray]
"""
A dict containing the ids and corners of a single charuco board detection.

shape:

{
"ids": np.ndarray | None,
"corners: np.ndarray | None
}
"""

AllDetectionsList = list[list[DetectionDict]]
"""
Multiple Charuco Board detections indexed by camera_idx and frame_idx [2D list].

E.g.: single_detection: DetectionDict = detections[camera_idx][frame_idx]. 


Each entry is a DetectionDict.

shape:

{
"ids": np.ndarray | None,
"corners: np.ndarray | None
}

"""


class DetectionData:
    """A dataset of charuco board detections.
    Contains detected points over multiple frames and mutliple cameras.

    The dataset can be saved and loaded to a json file.
    """

    camera_names: list[str] | None = None
    """The names of the cameras corresponding to the detected points, in matching order."""

    detections: AllDetectionsList | None = None
    """Detected ids and corners over frames and cameras"""

    resolutions: list[list[int, int]] | None = None
    """resolution per camera"""

    origin_capture_idx: int = -1
    """index of the detection where board lies on the ground as referece for the coordiante system"""

    processing_steps: dict | list
    """processign steps applied to the images before point detection"""

    filepath: Path | None = None

    def __init__(
        self,
        camera_names: list[str],
        detections: AllDetectionsList,
        camera_resolutions: list[list[int]],
        processing_steps: dict | list,
        origin_capture_idx: int = -1,
    ) -> None:
        # raises RuntimeError if the passed data isnt valid.
        self.camera_names = camera_names
        self.detections = detections
        self.resolutions = camera_resolutions
        self.processing_steps = processing_steps
        self.origin_capture_idx = origin_capture_idx

        self.pose_cnt: dict[str:int] = defaultdict(int)
        """number of frams with a valid detection per camera_name"""
        self.image_points_cnt: dict[str:int] = defaultdict(int)
        """number of total detected image_points per camera_name"""

        if detections is not None and self.camera_names is not None:
            self.check_detections_good(camera_names, detections)

            for camera_idx, camera_name in zip(range(len(detections)), self.camera_names, strict=True):
                for frame_idx in range(len(detections[camera_idx])):
                    cid_cnt = len(detections[camera_idx][frame_idx]["ids"])
                    if cid_cnt > 0:
                        self.pose_cnt[camera_name] += 1
                        self.image_points_cnt[camera_name] += cid_cnt

    def get_camera_data(self, camera_idx: int) -> tuple:
        """returns the detection data of a specified camera by index.

        Args:
            camera_idx (int): _description_

        Returns:
            tuple: camera_name (str), detections (list(DetectionDict)), resolution (list(int))
        """
        return (self.camera_names[camera_idx], self.detections[camera_idx], self.resolutions[camera_idx])

    def get_idx_of(self, camera_id: str) -> int | None:
        if self.camera_names:
            return self.camera_names.index(camera_id)
        return None

    @property
    def points_are_undistoreted(self) -> bool:
        steps_contain(self.processing_steps, "undistort") or steps_contain(self.processing_steps, "superkernel")

    @property
    def frame_cnt(self) -> int:
        if self.detections:
            return len(self.detections[0])
        return -1

    @property
    def camera_cnt(self) -> int:
        if self.camera_names:
            return len(self.camera_names)
        return -1

    @property
    def total_pose_cnt(self) -> int:
        return sum(self.pose_cnt.values())

    def set_resolutions(self, resolution_dict: dict[str, list]) -> None:
        """Set the camera resolutions.

        Args:
            resolution_dict (dict[camera_id (str), size (list)]): dictionary of image resolutions [W, H], keyed by camera-id.

        Raises:
            RuntimeError: given camera_id keys do not match DetectionData's camera_names
        """
        if set(resolution_dict.keys()) != set(self.camera_names):
            msg = "Mismatching camera names"
            raise RuntimeError(msg)
        self.resolutions = [resolution_dict[cam_id] for cam_id in self.camera_names]

    def append_detections(self, new_detection_per_camera: dict[str, dict]) -> None:
        if self.camera_names is None:
            msg = "No camera_names set yet."
            raise RuntimeError(msg)
        if self.detections is None:
            self.detections = [[] for _ in self.camera_names]

        for idx, camera_name in enumerate(self.camera_names):
            if camera_name in new_detection_per_camera:
                self.detections[idx].append(new_detection_per_camera[camera_name])
                self.pose_cnt[camera_name] += 1
                self.image_points_cnt[camera_name] += len(new_detection_per_camera[camera_name].get("ids", []))
            else:
                # add empty detection.
                self.detections[idx].append(
                    {
                        "corners": np.zeros([0, 2]),
                        "ids": np.zeros(0, dtype=int),
                    }
                )

    @classmethod
    def load_from_file(
        cls,
        filename: str | Path,
    ) -> Self:  # json
        """
        Load detections from a JSON file.
        If the file doesnt exist, reutrns an empty DetectionData object.

        Returns:
            camera_names (list[str]): List of camera IDs.

            detections (list[list[dict[str, np.ndarray]]]):
                All detections, indexed as detections[camera_idx][frame_idx].
                Each dict contains:
                    - "ids" (np.ndarray|None)
                    - "corners" (np.ndarray|None)
            resolutions (list[tuple[int,int]]):
                Image sizes (width, height) per camera.
            origin_capture_idx (int):
                Frame index where the board was laid on the ground to indicate
                orientation and height of the ground.
            processing_steps (list[str]):
                The processing steps performed during detection
        """
        try:
            with Path(filename).open("r") as file:
                detection_file = json.load(file)
                camera_names = detection_file.get("camera_names")
                origin_capture_idx = detection_file.get("origin_capture_idx", -1)
                detections = detection_file.get("detections")
                resolutions = detection_file.get("resolutions")
                processing_steps = detection_file.get("processing_steps", [])
                if resolutions is None:  # handle deprecated detection files.
                    print(
                        "!!!!   Detection file is missing resolution info. Assuming [5328, 4608] for each camera.   !!!!!"
                    )
                    resolutions = [[5328, 4608] for _ in camera_names]

                if len(detections[0]) == 0:
                    print("previous detection file is empty")
                    return cls.empty()
                if isinstance(detections[0][0], list):
                    detections = [[frame[0] for frame in per_camera] for per_camera in detections]
                for camera_Idx in range(len(detections)):
                    for detection_idx in range(len(detections[camera_Idx])):
                        detections[camera_Idx][detection_idx]["corners"] = np.array(
                            detections[camera_Idx][detection_idx]["corners"]
                        ).reshape((-1, 2))
                        detections[camera_Idx][detection_idx]["ids"] = np.array(
                            detections[camera_Idx][detection_idx]["ids"], dtype=int
                        )

                ret = cls(
                    camera_names=camera_names,
                    detections=detections,
                    camera_resolutions=resolutions,
                    processing_steps=processing_steps,
                    origin_capture_idx=origin_capture_idx,
                )
                ret.filepath = filename
                return ret
        except FileNotFoundError:
            return cls.empty()

    @classmethod
    def empty(cls) -> Self:
        return cls(
            camera_names=None, detections=None, camera_resolutions=None, processing_steps=[], origin_capture_idx=-1
        )

    @staticmethod
    def check_detections_good(camera_names: list[str], detections: AllDetectionsList) -> None:
        if len(camera_names) != len(detections):
            msg = "Input detections are malformed. Length of camera_names should match detected_points"
            raise RuntimeError(msg)
        if len(detections) == 0:
            msg = "Input detections is empty."
            raise RuntimeError(msg)
        if len({len(detection) for detection in detections}) != 1:
            msg = "Input detections are malformed. The different cameras have a mismatched amount of detections. This suggests a server desync."
            raise RuntimeError(msg)

    @staticmethod
    def detection_is_valid(board: Board, detected_ids: np.ndarray) -> bool:
        w, h = board.size
        dims = np.unravel_index(detected_ids, shape=(h, w))
        has_rows = [np.unique(d).size >= board.min_rows for d in dims]
        return detected_ids.size >= board.min_points and all(has_rows)

    def save_to_file(
        self,
        filename: str | Path,
    ) -> None:
        if self.detections is None:
            print("No detections. Nothing to save")
            return
        if self.frame_cnt == 0:
            print("No detections. Nothing to save")
            return

        Path(filename).parent.mkdir(exist_ok=True, parents=True)
        detections = copy.deepcopy(self.detections)

        # flatten numpy arrays and turn them into lists.
        for camera_idx in range(len(detections)):
            for detection_idx in range(len(detections[camera_idx])):
                detections[camera_idx][detection_idx]["corners"] = (
                    detections[camera_idx][detection_idx]["corners"].flatten().tolist()
                )
                detections[camera_idx][detection_idx]["ids"] = (
                    detections[camera_idx][detection_idx]["ids"].flatten().tolist()
                )

        with Path(filename).open("w") as f:
            json.dump(
                {
                    "camera_cnt": self.camera_cnt,
                    "detection_cnt": self.frame_cnt,
                    "processing_steps": self.processing_steps,
                    "origin_capture_idx": self.origin_capture_idx,
                    "camera_names": self.camera_names,
                    "resolutions": self.resolutions,
                    "detections": detections,
                },
                f,
                indent=2,
            )
        self.filepath = filename

    def display_detected_points(
        self,
        save_path: str,
        base_image: Image,
        grid_size: tuple[int, int],
    ) -> Image:
        img: Image = overlay_detected_points(
            base_image, grid_size, self.camera_names, self.detections, self.resolutions
        )
        print("  Saved Plot - Detected Points per Camera -->", save_path)
        img.save(save_path)
        return img

    def reduce_set(self, requested_frame_cnt: int) -> None:
        if self.frame_cnt <= requested_frame_cnt:
            return

        selected_indeces = []

        orignal_frame_cnt = self.frame_cnt
        if self.origin_capture_idx != -1:
            selected_indeces.append(self.origin_capture_idx)
            self.origin_capture_idx = 0

            requested_frame_cnt -= 1
            orignal_frame_cnt -= 1

        selected_indeces.extend(list(range(0, orignal_frame_cnt, round(orignal_frame_cnt / requested_frame_cnt))))

        for camera_idx in range(self.camera_cnt):
            self.detections[camera_idx] = [self.detections[camera_idx][sample] for sample in selected_indeces]


def steps_contain(steps: dict | list, step_key: str) -> bool:
    """checks if an entire steps dict[camera_id: step_list] contains step_key anywhere
    or, checks is a step_list of a specific camera contains the key.
    """
    if isinstance(steps, dict):  # we got an entire steps dict[camera_id: step_list]
        for step_list in steps.values():
            for step in step_list:
                if step_key in step:
                    return True
        return False
    if isinstance(steps, list):
        return any(step_key in step for step in steps)  # steps is a list
    msg = f"steps is of type {type(steps)} but it should be either dict or list."
    raise TypeError(msg)
