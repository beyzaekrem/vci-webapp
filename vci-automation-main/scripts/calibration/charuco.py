# ruff: noqa: T201, INP001
import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from charuco_calibration import CharucoCalibrator, InvalidDetectionData, MissingCalibrationData, load_dome_format
from controller import (
    Controller,
    argmods,
    boolean_user_input,
    camera_beep,
    merge_calib_jsons,
    remove_key_from_calib,
    stop_on_interrupt,
    timeout_input,
)
from controller.charuco_detection_omat import CaptureDetectionOMat
from controller.components.connection_manager import AggregatedRequestError


@dataclass
class Settings:
    """The CLI args in object form."""

    auto_trigger: bool
    board_path: str
    extrinsics_only: bool
    intrinsic_only: bool
    output_folder: str | Path
    redo: bool
    selected_cameras: list[str] | None
    detections_file: str | Path | None = None
    servers: list[int] | None = None

    @property
    def both(self) -> bool:
        return not self.extrinsics_only and not self.intrinsic_only

    @property
    def intrinsics_enabled(self) -> bool:
        return self.intrinsic_only or self.both

    @property
    def extrinsics_enabled(self) -> bool:
        return self.extrinsics_only or self.both

    @property
    def bundle_adjust(self) -> bool:
        return self.extrinsics_enabled and self.selected_cameras is None


class CharucoAppRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings: Settings = settings
        self.calibrator = None

    def run(self) -> None:
        if not self.settings.redo:
            self._capture_detections()
        self._run_calibration()

    def _capture_detections(self) -> None:
        """Interactive detection capture, detections saved to output_folder"""

        with Controller(self.settings.servers, mode=None) as c:
            capture_o_mat = CaptureDetectionOMat(c, target_camera_ids=self.settings.selected_cameras)

            if self.settings.extrinsics_only:  # we need previous intrincis to exist (for selected cameras).
                calib: dict = c.get_raw_calibration()
                need_to_exist = self.settings.selected_cameras or c.all_camera_ids
                cameras = load_dome_format(calib, need_to_exist)

                missing_completely = len([cam for cam in cameras if cam is None])
                no_intrinsics = len([cam for cam in cameras if cam is not None and cam.intrinsic is None])

                if missing_completely + no_intrinsics != 0:
                    msg = f"Unable to perform extrinic_only calibration. \
                        Calibration file from servers is missing intriic camera infomration for \
                            {missing_completely+no_intrinsics} camera(s)"
                    raise MissingCalibrationData(msg)

            capture_o_mat.check_and_prepare_system(ask_user_confirmation=True)
            capture_o_mat.handle_previous_detections(self.settings.detections_file)

            # capture charuco detections

            try:
                c.set_depth_active("COLOR")
            except AggregatedRequestError as e:
                print(f"Could not disable depth cameras: {e}")
                input("Press [Enter] to continue...")
            c.start()
            print("\nCapture Charuco Boards.")
            with stop_on_interrupt():
                while True:
                    origin_capture_hint = "[o] Capture origin image - place board on the floor"
                    if self.settings.intrinsic_only:
                        origin_capture_hint = f"({origin_capture_hint}) not needed for intrinsic only"

                    elif (
                        capture_o_mat.detection_data is not None
                        and capture_o_mat.detection_data.origin_capture_idx != -1
                    ):
                        origin_capture_hint = f"({origin_capture_hint}) Done. \
                            origin_capture_idx = {capture_o_mat.detection_data.origin_capture_idx}"

                    command, self.settings.auto_trigger = timeout_input(
                        "Choose an option:\n"
                        "  [Enter] Capture next image \n"
                        "  [a] Auto-trigger next capture\n"
                        f"  {origin_capture_hint}\n"
                        "  [camera_id] Enter a specific camera ID to request an image\n"
                        "  [x] Stop capturing - starts calibration\n"
                        "> ",
                        auto_trigger_enabled=self.settings.auto_trigger,
                        timeout_seconds=2 if self.settings.selected_cameras is None else 3,
                    )
                    if command == "x":  # stop detections
                        if capture_o_mat.detection_data.origin_capture_idx == -1 and self.settings.extrinsics_enabled:
                            q = boolean_user_input(
                                "Error: You are missing an origin capture. Quit Anyway?",
                                default_choice=False,
                            )
                            if q:
                                break
                            continue
                        print("Stopping.")
                        break
                    if command.lower() in ["y", "", "o"]:
                        last_void_detections, capture_idx = capture_o_mat.capture_detection()

                        if command == "o":
                            # check if camera 0 has a valid detection for board
                            if c.all_camera_ids[0] in last_void_detections:
                                capture_o_mat.detection_data.origin_capture_idx = capture_idx
                                print("Success!!!   Origin capture done.")
                                camera_beep("boop")
                            else:
                                print(
                                    f"Failed!!!   Origin capture failed. Please try again. "
                                    f"{c.all_camera_ids[0]} has to detect the board. "
                                    f"Lay the board flat on the ground, to capture the rotation and "
                                    f"height of the floor relative to {c.all_camera_ids[0]}"
                                )
                    # get test image of requested camera id
                    elif command.upper() in c.all_camera_ids:
                        # to save bandwidth we are only requesting this one image.
                        # This means that this detection cannot be used for the extrinsic calibration as
                        # we lack the matching detection data of the other cameras
                        requested_camera_id = command.upper()
                        capture_o_mat.save_detection_image(requested_camera_id, "CharucoDetection.jpg")
                    else:
                        print(f"Unknown command or camera_id {command}")
                        continue

            capture_o_mat.stop_and_save_detections(self.settings.detections_file)
            print(f"detections saved to {self.settings.detections_file}")

    def _save_and_send_calibration(self) -> None:
        """writes claibration result to calibration_dome.json format. Sends to servers if permitted."""
        save_path = Path(self.settings.output_folder)
        print("\nSaving calibration result:")
        if self.settings.bundle_adjust:
            # extrinsics are newly created via bundle adjust over all cameras.
            try:
                self.calibrator.bundle_adjust_system.dump_calib_pkl(save_path / "debug_calibration.pkl")
            except Exception as e:  # noqa: BLE001
                print("failed to save debug file.", e)
                print(" Continuing ....")

            # set board as origin if board idx has been captured
            orig = self.calibrator.detection_data.origin_capture_idx
            if orig != -1:
                calib_json = self.calibrator.set_origin_board(orig, center_of_cameras_bb=True)

        calib_json = self.calibrator.save_json(f"{save_path}/calibration_geometry.json")

        if calib_json is None or len(calib_json) == 0:  # calibration failed
            return

        # merge with previous calibration
        print("\nmerge with server calibration...")
        with Controller(self.settings.servers, mode="observer") as c:
            original = c.get_raw_calibration()

            # on  intrisnics only, we trash the view-matrix of all selected cameras. all or partial
            # on extrisnics only. partial, we copy overwrite the extrisnics of the selected cameras. - no trash
            # extricy only, bundle adjust, we trash all extrisnics of cameras that were not calibrated.

            # both, partial, overwrite selected cmaeras. no trash
            # both, bundle adjust, trash all extrisnocs of cmaeras that were not calibrated. - trashhh

            # extrinsic only and both is actually same.

            if len(original) != 0:
                effected_cameras = self.settings.selected_cameras or self.calibrator.detection_data.camera_names
                if self.settings.intrinsic_only:
                    print(
                        "Intrinsic_only calibration: Removing outdated view_matrices (extrinsic) "
                        f"from {len(effected_cameras)} cameras"
                    )
                    remove_key_from_calib(original, "extrinsics/view_matrix", effected_cameras)
                elif self.settings.bundle_adjust:
                    print(
                        "Extrinsics of all Cameras adjusted: Removing outdated view_matrices of cameras that"
                        " were not in this run."
                    )
                    remove_key_from_calib(
                        original,
                        "extrinsics/view_matrix",
                    )

            calib_json = merge_calib_jsons(original, calib_json)

        if self.settings.extrinsics_enabled:
            # check reprojection accuracy
            self.calibrator.load_calibration_file(calib_json)
            try:
                self.calibrator.check_accuracy()
            except (MissingCalibrationData, InvalidDetectionData) as e:
                print(e)

        # save final, merged calibration locally
        with Path.open(save_path / "calibration_dome.json", "w") as f:
            json.dump(calib_json, f, indent=2)
            print(f"Saved merged calibration file to  --> {save_path!s}/calibration_dome.json")

        # Send calibration to server is user allows it
        send = boolean_user_input("\nSend calibration file to server? ")
        if not send:
            print("Not sending")
            return
        with Controller(self.settings.servers, mode="obersver") as c:
            try:
                c.set_raw_calibration(calib_json)  # this can fail due to ControlTakenError
                print("Calibration file sent")
            except AggregatedRequestError:
                print("Sending calibration failed: {e}.")
                print(
                    f" Attempt to send again with \n\
                      python scripts/calibration/send_calib_file.py --file {save_path!s}/calibration_dome.json"
                )

        print("\n\nCalibration is done")

    def _run_calibration(self) -> None:
        self.calibrator = CharucoCalibrator(detection_data=self.settings.detections_file, board=settings.board_path)
        detection_data = self.calibrator.detection_data
        print("Detection Data:")
        print(f"    file: {detection_data.filepath}")
        print(f"    cameras: {detection_data.camera_cnt}")
        print(f"    frame_cnt: {detection_data.frame_cnt}")
        print(f"    total_poses: {detection_data.total_pose_cnt}")
        print()
        print("Calibration Settings:")
        print(f"    extrinsic: {self.settings.extrinsics_enabled}")
        print(f"    intrinsic: {self.settings.intrinsics_enabled}")
        print(f"    selected_cameras: {self.settings.selected_cameras or f'all ({detection_data.camera_cnt})'}")
        print(f"    board: {self.settings.board_path}")
        print(f"    local output: {self.settings.output_folder!s}")

        if detection_data.total_pose_cnt == 0:
            print("No valid detections found. Exiting.")
            sys.exit()

        if self.settings.intrinsic_only:  # all or selected cameras.
            self.calibrator.intrinsic_calibration(self.settings.selected_cameras)
            # no accuracy check possible - changig the intrinsics, trashes the extrinsics.

        elif self.settings.extrinsics_only:
            self._load_calibration_from_servers()
            if self.settings.selected_cameras is None:
                # all cameras. use bundle adjust via multical library.
                self.calibrator.extrinsic_calibration_bundle_adjust()
            else:
                # up to 5(?) selected cameras
                print(f"\ntriangulating image_points and fitting {self.settings.selected_cameras} ....")
                self.calibrator.targeted_extrinsic_recalibration(self.settings.selected_cameras)
                print("done.")

        elif self.settings.both:
            if self.settings.selected_cameras is None:
                # all cameras. use bundle adjust via multical library.
                # no loading previous calib.
                self.calibrator.calibrate()
            else:
                # first updates the intrinsics independantly, based on image points only
                self.calibrator.intrinsic_calibration(self.settings.selected_cameras)
                # then trinagualtes 3d positions via the "fixed" cameras and fitts new position for the selected cameras
                self.calibrator.targeted_extrinsic_recalibration(self.settings.selected_cameras)
        else:
            msg = "Waaaait a minute. How did we get here?"
            raise RuntimeError(msg)
        self._save_and_send_calibration()

    def _load_calibration_from_servers(self) -> None:
        with Controller(self.settings.servers, mode="observer") as c:
            calib = c.get_raw_calibration()
            self.calibrator.load_calibration_file(calib)


def arguments() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Calibrate intrinsic (lense) and extrinsic (pose) camera parameters using a Charuco board. \n\n"
            "Detections are triggered indivdiually in command line (or via --auto-trigger). "
            "Detections are saved locally and you can append detections with subsequent runs. "
            "You can also skip the deteciton and simply redo the calibration from file with --redo. "
            "You can plot a calibration result with scripts/calibration/plot.py"
        ),
    )

    argmods.add_server_list_argument(parser)

    trigger_group = parser.add_argument_group("DETECTION")
    trigger_group.add_argument(
        "-r",
        "--redo",
        action="store_true",
        help="rerun calibration with previous detections <output_folder>/detections.json",
    )
    argmods.add_auto_trigger_argument(trigger_group, "board detection")

    data_group = parser.add_argument_group("DATA FLOW")
    argmods.add_output_folder_argument(data_group, default="CALIB")
    data_group.add_argument(
        "--board_path",
        type=str,
        default="config/board.json",
        help="path to the board.json file with the charuco baord description. Default: board.json",
    )

    # --- Calibration modes (mutually exclusive) ---
    mode = parser.add_argument_group("CALIBRATION MODE", description="default: calibrates extrinsic & intrinsic")
    x_group = mode.add_mutually_exclusive_group()
    x_group.add_argument(
        "--intrinsics-only",
        action="store_true",
        help="Calibrate only intrinsic parameters. You should run extrinics_only \
            next to update the camera poses.",
    )
    x_group.add_argument(
        "--extrinsics-only",
        action="store_true",
        help="Calibrate only camera poses. Please ensure your intrinsic parameters are up to date.",
    )
    mode.add_argument(
        "--cams",
        nargs="+",
        type=str,
        metavar="CAM_ID",
        help="Target specific cameras by name to calibrate. Default: All cameras.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = arguments()

    settings = Settings(
        auto_trigger=args.auto_trigger,
        board_path=args.board_path,
        extrinsics_only=args.extrinsics_only,
        intrinsic_only=args.intrinsics_only,
        selected_cameras=args.cams,
        output_folder=args.outputfolder,
        redo=args.redo,
        servers=args.server,
        detections_file=f"{args.outputfolder}/detections.json",
    )

    app = CharucoAppRunner(settings)
    app.run()
