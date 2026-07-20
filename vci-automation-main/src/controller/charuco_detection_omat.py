# ruff: noqa: T201
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL.Image import Image

from charuco_calibration import Board, DetectionData
from controller import (
    Controller,
    PreviewWriter,
    ProcessingSteps,
    ServerDesyncError,
    argmods,
    boolean_user_input,
    camera_beep,
    trigger_box,
    trigger_single,
)


@dataclass
class DetectionSettings:
    target_pose_cnt_per_camera = 10
    target_detected_point_cnt_per_camera = 1300
    medium_percentage = 0.8
    target_camera_ids = None

    exposure_profile = argmods.SPEEDY_EXPOSURE
    detection_processing_steps = ProcessingSteps.CHARUCO
    image_grid_display_path = "visuals/calibration/CharucoDetectionGrid.jpg"


class Status:
    no_detection = "\033[31m"  # red
    medium_cnt = "\033[33m"  # yellow
    good_cnt = "\033[32m"  # green
    gray = "\033[0;0m"  # reset

    @classmethod
    def get_status(cls, metric: int, target: int, medium_percent: float = 0.5) -> str:
        if metric >= target:
            return cls.good_cnt
        if metric >= target * medium_percent:
            return cls.medium_cnt
        return cls.no_detection


class CaptureDetectionOMat:
    settings: DetectionSettings = DetectionSettings()

    def __init__(
        self, c: Controller, target_camera_ids: list[str] | None = None, board: Board | Path = "config/board.json"
    ) -> None:
        self.c = c
        self.detection_data: DetectionData | None = None
        self.enough_detections = False
        self.target_camera_ids = target_camera_ids
        if isinstance(board, Board):
            self.board = board
        else:
            self.board = Board(Path(board))

    def check_and_prepare_system(self, *, ask_user_confirmation: bool = True) -> None:
        trigger_box("off")

        if self.target_camera_ids is not None:
            missing = [cam_id for cam_id in self.target_camera_ids if cam_id not in self.c.all_camera_ids]
            if len(missing) > 0:
                print(f"Server is missing camera that was speficically asked for. Missing: {missing}")
                sys.exit()
        else:
            camera_cnt = len(self.c.all_camera_ids)
            print(f"\n{camera_cnt} cameras connected cameras")
            if ask_user_confirmation:
                proceed = boolean_user_input("Please check that the expected amount of cameras is connected. Proceed?")
                if not proceed:
                    sys.exit()

        self.c.set_exposure_and_gain(self.settings.exposure_profile.exposure, self.settings.exposure_profile.gain)
        self.c.set_exposure_and_gain(40, 0, "depth")
        if ask_user_confirmation:
            input(
                f"Selected {self.settings.exposure_profile}. Please turn the lights "
                f"to { self.settings.exposure_profile.illumination}%. "
                "Continue [Enter]"
            )

        # get image grid to display detected points on
        print("Capturing detection image grid backdrop...")
        self.image_grid, self.image_grid_size = self.capture_image_grid(
            self.c,
            self.settings.image_grid_display_path,
            steps=self.settings.detection_processing_steps,
        )
        print(f"Detection image grid image ---->   {self.settings.image_grid_display_path}")
        self.c.stop()

        self.c.switch_mode("calibration")
        self.c.set_charuco_board(
            self.board.dict_name,
            self.board.size,
            self.board.square_length,
            self.board.marker_length,
        )

    @staticmethod
    def capture_image_grid(
        c: Controller,
        path: str,
        camera_ids: list[str] | None = None,
        steps: dict = ProcessingSteps.TINY_UNCALIBRATED,
    ) -> tuple[Image, tuple[int, int]]:
        c.switch_mode("single")
        c.set_depth_active("COLOR")
        c.start()
        with trigger_single(c):
            image_entries = c.capture_images(
                image_format="jpg",
                quality=70,
                steps=steps,
                requested_camera_ids=camera_ids,
            )
        image_grid, image_grid_size = PreviewWriter.save_image_grid(
            image_entries, path, f"Charuco Detections - {len(image_entries)} cameras"
        )
        c.stop()
        return image_grid, image_grid_size

    def handle_previous_detections(self, output_path: str | Path) -> None:
        previous_detection = DetectionData.load_from_file(output_path)

        expected_cameras = self.c.all_camera_ids

        if previous_detection.detections is not None:
            print(f"Previous detections from {output_path}")
            if previous_detection.frame_cnt > 0:
                if (
                    expected_cameras == previous_detection.camera_names
                ):  # check that cameras are the same, and the *order* is the same!
                    print(
                        f"\nPrevious detection found with {previous_detection.frame_cnt} images. "
                        f"For the same {previous_detection.camera_cnt} cameras."
                    )
                    extend_previous_detection = boolean_user_input("Keep and extend previous detection?")

                    if extend_previous_detection:
                        self.detection_data = previous_detection
                    else:
                        print("Clearing previous detections.")
                else:
                    print("\nFound a previous detection with mismatched camera_ids")
                    print(
                        f"previous detection has {previous_detection.camera_cnt} "
                        f"cameras: {previous_detection.camera_names}"
                    )
                    print(f"currently connected with {len(expected_cameras)} cameras: {expected_cameras}")
                    proceed = boolean_user_input("Discard previous detection and continue?")
                    if not proceed:
                        sys.exit()
        else:
            print("No previous detection.json found")

    def clear(self) -> None:
        self.detection_data = None
        self.enough_detections = False

    def capture_detection(self) -> tuple[dict[str, dict], int]:
        """Runs charucoBoard detection via controller.
        The resuting detectiosn are added to the DetectionData.

        Raises:
            ServerDesyncError: The servers returned mismatching frame_indeces.

        Returns:
            tuple containing

            * valid_detections (dict[str, dict]): detections per camera_id from this caputre
            * capture_index (int): index of this detection - matching DetectionData index.
        """
        with trigger_single(self.c):
            print("Trigger and wait for next charuco board detection...")
            detection_results = self.c.charuco_detection(
                detection_processing_steps=self.settings.detection_processing_steps,
                rgb_images=False,
                requested_camera_ids=self.target_camera_ids,
            )

        # process detection results
        frame_indices = [detection_info.get("frame_idx") for detection_info, _ in detection_results]
        if len(set(frame_indices)) > 1:
            msg = "Servers returned different frame_indices. Charuco calibration requires synchronized image capture"
            raise ServerDesyncError(msg)

        # initialize DetectionData - camera_names, processing_steps, resolutions
        if self.detection_data is None:
            self.detection_data = DetectionData(
                camera_names=self.c.all_camera_ids,
                processing_steps=self.settings.detection_processing_steps,
                camera_resolutions=None,
                origin_capture_idx=-1,
                detections=None,
            )

            camera_resolutions = {}
            for detection_info, _ in detection_results:
                camera_ids = detection_info.get("camera_ids")
                shapes = detection_info.get("shapes")  # torch tensor shapes:  [C, H, W] or  [H, W]
                for idx, camera_id in enumerate(camera_ids):
                    camera_resolutions[camera_id] = shapes[idx][-2:][::-1]
                    # camera_resolutions is W, H
            print("DetectionData.camera_names", DetectionData.camera_names)
            print("camera_resoutuions", camera_resolutions.keys())
            self.detection_data.set_resolutions(camera_resolutions)

        # get valid detection results and add to DetectionData
        valid_detections: dict[str:dict] = {}  # dict[camera_id: dict{"corners", "ids"}]
        for detection_info, _ in detection_results:
            # Only detections where enough points and rows are found are good enough for us.

            camera_ids = detection_info.get("camera_ids")
            detections = detection_info.get("detections")  # list[{"corners": ndarray: (x,2), "ids":ndarray: (x)}]
            # save all detections
            for idx, camera_id in enumerate(camera_ids):  # for each camera in this server
                detection: dict = detections[idx]
                if DetectionData.detection_is_valid(self.board, np.array(detection.get("ids"), dtype=int)):
                    # detection is valid
                    detection["corners"] = np.array(detection["corners"]).reshape((-1, 2))
                    detection["ids"] = np.array(detection["ids"], dtype=int)
                    valid_detections[camera_id] = detection

        self.detection_data.append_detections(valid_detections)

        # display detection status (board pose cnt, detected aruco points) of each camera

        self.display_detection_status()
        print(f"Image grid ---> {self.settings.image_grid_display_path}")
        if self.detection_data.frame_cnt % 10 == 0:
            self.update_image_grid()
            print("Image grid updated!")
        else:
            print(f"Next image grid update in {10 - (self.detection_data.frame_cnt% 10)} triggers.")

        self._check_enough_detections(beep_if_enough=True)  # beep once if enough detections

        print(
            f"Frames captures: {self.detection_data.frame_cnt} - "
            "Valid detetions on this trigger: {len(valid_detections)}"
        )
        print()

        return valid_detections, self.detection_data.frame_cnt - 1

    def _check_enough_detections(self, *, beep_if_enough: bool = True) -> bool:
        cam_ids = self.target_camera_ids or self.detection_data.camera_names
        enough_poses = all(
            self.detection_data.pose_cnt[cam_id] >= self.settings.target_pose_cnt_per_camera for cam_id in cam_ids
        )
        enough_image_points = all(
            self.detection_data.image_points_cnt[cam_id] >= self.settings.target_detected_point_cnt_per_camera
            for cam_id in cam_ids
        )
        if enough_poses and enough_image_points and not self.enough_detections:
            if beep_if_enough:
                camera_beep("long")
            self.enough_detections = True
        return self.enough_detections

    def display_detection_status(self, colums: int = 2) -> None:
        if self.detection_data is None:
            print("Detection Data is empty.")
            return
        for idx, cam_id in enumerate(self.detection_data.camera_names):
            pose_cnt = self.detection_data.pose_cnt[cam_id]
            image_points_cnt = self.detection_data.image_points_cnt[cam_id]
            pose_cnt_status = Status.get_status(
                pose_cnt, self.settings.target_pose_cnt_per_camera, self.settings.medium_percentage
            )
            image_points_cnt_status = Status.get_status(
                image_points_cnt, self.settings.target_detected_point_cnt_per_camera, self.settings.medium_percentage
            )
            position_str = f"({self.c.system_layout.camera_position(cam_id)})"
            status_line = (
                f"|   {cam_id:<6}{position_str:<25} {pose_cnt_status} "
                f"board poses: {pose_cnt:<4} {image_points_cnt_status} "
                f"aruco points:{image_points_cnt:<7} \033[0m   "
            )
            print(
                status_line,
                end="|\n" if (idx + 1) % colums == 0 else "",
            )

    def update_image_grid(self) -> None:
        self.detection_data.display_detected_points(
            self.settings.image_grid_display_path, self.image_grid, self.image_grid_size
        )

    def save_detection_image(self, camera_id: str, output_path: str) -> None:
        with trigger_single(self.c):
            print(f"Collecting test image for {camera_id}")
            detection_results = self.c.charuco_detection(
                detection_processing_steps=self.settings.detection_processing_steps,
                rgb_images=True,
                requested_camera_ids=[camera_id],
                format="png",
            )
        for _, image_entries in detection_results:
            for entry in image_entries:
                # should only be one image since we force the input command to accept exactly one camera id
                i: Image = entry.get_image()
                i.save(output_path)
                print(f"\n-------->  image saved to {output_path}")
                break

    def stop_and_save_detections(self, output_path: str) -> None:
        print("Stopped Charuco Board Detection\n")
        self.c.stop()
        # reset gain and exposure to default values
        self.c.set_exposure_and_gain(argmods.DEFAULT_EXPOSURE.exposure, argmods.DEFAULT_EXPOSURE.gain)
        if self.detection_data is not None:
            self.detection_data.save_to_file(output_path)
