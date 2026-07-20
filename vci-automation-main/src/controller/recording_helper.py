# ruff: noqa: T201
import contextlib
import re
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from natsort import natsorted
from tqdm import tqdm

from controller import (
    Controller,
    FolderMode,
    PreviewWriter,
    ProcessingSteps,
    ServersEncounteredError,
    argmods,
    exceptions,
    input_modules,
    stop_on_interrupt,
    zip_folder,
)

from .trigger_box_connection import trigger_box


@dataclass
class RecordingDetails:
    rec: str
    camera_ids: list[str]
    frame_counts: list[int]
    capture_fps: list[int | None]
    server_statuses: list[dict]

    @property
    def camera_type_counts(self) -> dict:
        counts: dict = {}
        for cam_id in self.camera_ids:
            camera_type = f"{cam_id[0]}*"
            counts[camera_type] = counts.get(camera_type, 0) + 1
        return counts

    @property
    def pretty_length(self) -> int | str:
        min_f = min(self.frame_counts)
        max_f = max(self.frame_counts)
        return min_f if min_f == max_f else f"[{min_f}, {max_f}]"

    @property
    def server_cnt(self) -> int:
        return len(self.server_statuses)

    @property
    def capture_timestamp(self) -> str:
        return self.server_statuses[0].get("capture_timestamp")

    @property
    def pretty_fps(self) -> str:
        normed = [fps or -1 for fps in self.capture_fps]
        min_fps = min(normed)
        max_f = max(normed)
        if min_fps == max_f:
            if min_fps == -1:
                return None
            return min_fps
        return f"[{None if min_fps == -1 else min_fps}, {max_f}]"

    def __init__(self, c: Controller, rec: str) -> None:
        sever_statuses = c.get_status()
        sever_statuses = [s for s in sever_statuses if s["mode"] == "replay" and s["recording_name"] == rec]
        if len(sever_statuses) == 0:
            return
        frame_counts = [s["frame_count"] for s in sever_statuses]
        fps = [s.get("fps") or -1 for s in sever_statuses]

        camera_ids = []
        for st in sever_statuses:
            camera_ids.extend(st["camera_ids"])
        self.rec = rec
        self.camera_ids = camera_ids
        self.frame_counts = frame_counts
        self.server_statuses = sever_statuses
        self.capture_fps = fps

    def _format_fields(self, binding: str = ", ") -> str:
        fields = {
            "length": f"{self.pretty_length} frames",
            "servers": self.server_cnt,
            "cameras": self.camera_type_counts,
            "capture_timestamp": self.capture_timestamp,
            "fps": self.pretty_fps,
        }
        return binding.join(f"{k}: {v}" for k, v in fields.items())

    def __str__(self) -> str:
        return f"{self.rec} - {self._format_fields(binding=', ')}"

    def pretty_print(self) -> None:
        b = "\n    "
        print(f"    {self._format_fields(b)}")


class ReplayOMat:

    class PreviewImageMode(Enum):
        NONE = 0  # no image grid preview
        FIRST_FRAME = 1  # creates combined preview image only for first frame requested per recording
        EVERY_FRAME = 2  # creates preview image grid for every frame.
        AUTO = 3  # FIRST_FRAME / EVERY_FRAME is inferred from capture_fps

    # output_options:
    outputfolder = (
        "Capture/Tests"  # image save folder. Will be extended to: <outputfolder>/<recording_name> by default.
    )
    zip_to_path = None  # e.g: SCIBO, If not None: zips the save_folder (outputfolder/<recording_name>) after replay and copies to give location
    get_background = True
    get_calib_file = True
    save_individual_camera_frames = True
    foldermode: FolderMode = FolderMode.clear

    # image options:
    requested_camera_ids = None  # None is all
    processing = ProcessingSteps.PROCESSED
    quality: argmods.ImageQualitySettings = argmods.HIGH_QUALITY_PNG
    rgb_images = True  ### TODO
    mattes = False

    ignore_frame_count_mismatch = False
    invalid_ok = True

    # preview options:
    preview_video_prefered_cameras = None
    preview_fps: int = 5
    preview_view_cnt = 6  # determines how many image views the preview video shows
    combined_preview_images: PreviewImageMode = PreviewImageMode.FIRST_FRAME

    def __init__(self, c: Controller, outputfolder: str | Path | None = None) -> None:
        self.c: Controller = c
        self.c.switch_mode("replay")
        self.available_recordings = self.c.get_available_recordings()
        if outputfolder is not None:
            if isinstance(outputfolder, str):
                self.outputfolder = outputfolder if outputfolder.endswith("/") else outputfolder + "/"
            else:
                self.outputfolder = outputfolder
        self.set_image_path_delegate = self.default_save_path

    def get_recordings_from_series(
        self, series_name: str, series_selection: argmods.FlexiRange = argmods.FLEXI_RANGE_FULL
    ) -> list[str]:
        date_regex = r"\d{4}_\d{2}_\d{2}_+"  # DATE pattern YYYY_MM_DD_

        series_name = series_name.rstrip("_")
        if series_name.startswith("DATE_"):
            # user reqeusted any DATE prefix: DATE_my_recording
            pattern_str = rf"^{date_regex}{re.escape(series_name[5:])}"
        elif re.match(rf"^{date_regex}", series_name):
            # user passed a concrete Date within the series_name: e.g 2026_05_13_my_recording
            pattern_str = rf"^{re.escape(series_name)}"
        else:
            # Flexible Default: Match with OR without a date prefix
            pattern_str = rf"^(?:{date_regex})?{re.escape(series_name)}"

        # allow wildcared
        pattern_str = pattern_str.replace(r"\*", ".*")
        # add series index "_001"
        pattern = re.compile(f"{pattern_str}(?:_+(\\d+))?$")

        # Collect all matching recordings
        matches: list[tuple[int, str]] = []  # list of (series_index, recording_name)
        for recording_name in self.available_recordings:
            if m := pattern.match(recording_name):
                series_index = int(m.group(1)) if m.group(1) else 0
                matches.append((series_index, recording_name))

        if not matches:
            print(f"Could not find series {series_name}")
            return []

        # Handle no series_selection: (Return all matches for that series/date pattern)
        if series_selection is None:
            matched = [name for _, name in natsorted(matches, key=lambda x: x[1])]
            if len(matched) > 1:
                return matched[:1]
            return matched

        # Filter by selection
        matches = natsorted(matches, key=lambda x: x[1])
        max_idx = max(idx for idx, _ in matches)
        valid_indices = set(series_selection.resolve_indices(max_idx + 1))

        return [name for idx, name in matches if idx in valid_indices]

    def replay_series(
        self,
        series_name: str,
        series_selection: argmods.FlexiRange = argmods.FLEXI_RANGE_FULL,
        frame_selection: argmods.FlexiRange = argmods.FLEXI_RANGE_FULL,
    ) -> None:

        recordings = self.get_recordings_from_series(series_name, series_selection)
        if recordings is None:
            print("stopping")
            sys.exit(0)
        if len(recordings) == 0:
            return
        print(f"\nselected {len(recordings)} recordings from series '{series_name}':")
        for rec in recordings:
            print(f"   {rec}")
        print(f"output folder:   {self.outputfolder}")
        print(f"frame selection: {frame_selection}")
        print(f"processing:      {self.processing}")
        print(f"image format:    {self.quality}")
        go = input("\nbegin download? [Y,n]").lower() != "n"
        if not go:
            print("abort")
            exit()

        error_log = ""
        for cnt, name in enumerate(recordings):
            try:
                print(f"\n replay series {cnt}/{len(recordings)}")
                self.replay(name, frame_selection)
            except ServersEncounteredError as e:
                error_log += f"Error on recording {name} ({cnt}/{len(recordings)}):\n{e}\n\n\n"
            except RuntimeError as e:
                error_log += f"Error on recording {name} ({cnt}/{len(recordings)}):\n{e}\n\n\n"

            if error_log != "":
                print(error_log)

    def replay(self, recording_name: str, frame_selection: argmods.FlexiRange = argmods.FlexiRange) -> None:
        start_replay = time.time()

        # get output path. Usually its output_folder/recording_name
        save_path = self.set_image_path_delegate(self.c, self.outputfolder, recording_name)

        self.c.set_image_path(
            save_path,
            folder_mode=self.foldermode,  # clear, save, append
            save_images=self.save_individual_camera_frames,  # controls if invidual camera frames should be saved. Disabled for preview only
        )

        # handles image path for combined preview images when flat preview hierarchy is used
        combined_preview_image_path = Path(self.c.path_structure.get_preview_path()).parent
        if recording_name in Path(self.c.path_structure.get_preview_path()).name:
            combined_preview_image_path = f"{combined_preview_image_path}/{recording_name}_"
        else:
            combined_preview_image_path = f"{combined_preview_image_path}/"

        # Check if recording exists.
        with contextlib.suppress(exceptions.TriggerBoxError):
            trigger_box("off")
        if recording_name not in self.available_recordings:
            msg = (
                f"Error: No Server has recording {recording_name}.\n\navailable_recordings: {self.available_recordings}"
            )
            raise ValueError(msg)

        with self.c.filter_connections(self.c.get_servers_with_recording(recording_name)):
            print(f"\n--- Replay {recording_name} ---- \n")
            self.c.set_recording_name(recording_name)

            details = RecordingDetails(self.c, recording_name)
            details.pretty_print()
            print(f"  output ---> {save_path}\n")

            recording_cameras = self.c.get_cameras_in_recording(recording_name=recording_name)
            requested_camera_ids = argmods.resolve_cameras(
                self.requested_camera_ids, self.c.system_layout, recording_cameras
            )
            capture_fps = details.capture_fps[0]

            # checks if calibration file is valid
            if self.get_calib_file:
                self.c.grab_calibration_file(
                    processing_steps=self.processing, camera_ids=requested_camera_ids, capture_fps=capture_fps
                )

            # checks if frame count is valid
            frame_counts = self.c.check_frame_count(raise_exception=not self.ignore_frame_count_mismatch)
            sequence_length = min(frame_counts)
            resolved_frames: list[int] = list(frame_selection.resolve_indices(sequence_length))

            # initializes video preview
            if self.preview_fps > 0:
                # cap preview_fps at max capture_fps. If disjointed frames: capture_fps is None, set preview_fps to 1
                normed_capture_fps = capture_fps or 1  # None = 1
                valid_fps = min(self.preview_fps, normed_capture_fps)
                preview_step = normed_capture_fps // valid_fps
                self.c.set_preview(
                    preview_step,
                    capture_fps,
                    output_path=save_path,
                    view_cnt=self.preview_view_cnt,
                    prefered_camera_ids=self.preview_video_prefered_cameras,
                )

            preview_image_setting = self.combined_preview_images
            # resolve to EVERY_FRAME or FIRST_FRAME
            if preview_image_setting is self.PreviewImageMode.AUTO:
                if capture_fps is None:  # disjointed frames
                    preview_image_setting = self.PreviewImageMode.EVERY_FRAME
                else:  # contionus video
                    preview_image_setting = self.PreviewImageMode.FIRST_FRAME

            # donwloading only preview-video:
            preview_video_only: bool = (
                not self.save_individual_camera_frames
                and preview_image_setting != self.PreviewImageMode.EVERY_FRAME
                and self.preview_fps > 0
            )

            if preview_video_only:
                resolved_frames = list(
                    range(min(resolved_frames), max(resolved_frames), self.c.preview_writer.frame_step)
                )
                print(
                    f"preview-video-only download. Mimizing frame retrieval to every {self.c.preview_writer.frame_step}-th frame."
                )

            mattes = self.mattes
            with stop_on_interrupt():
                # download backgrounds
                if self.get_background:
                    print("Grabbing Background Images...")
                    image_entries = self.c.grab_background_images(
                        steps=self.processing,
                        requested_camera_ids=requested_camera_ids,
                        image_format=self.quality.format,
                        quality=self.quality.quality,
                        invalid_ok=self.invalid_ok,
                    )
                    if self.combined_preview_images != self.PreviewImageMode.NONE:
                        PreviewWriter.save_image_grid(
                            image_entries,
                            f"{combined_preview_image_path}background.jpg",
                            "background",
                        )
                    print("Done")
                # download frames
                print(
                    f"\n{recording_name} replaying {len(resolved_frames)} frames {min(resolved_frames), max(resolved_frames)}"
                )
                for i in tqdm(resolved_frames):
                    image_entries = self.c.capture_images(
                        frame_idx=i,
                        steps=self.processing,
                        requested_camera_ids=requested_camera_ids,
                        images=self.rgb_images,
                        mattes=mattes,
                        image_format=self.quality.format,
                        quality=self.quality.quality,
                        mattes_format=self.quality.mattes_format,
                        mattes_quality=self.quality.mattes_quality,
                        invalid_ok=self.invalid_ok,
                    )

                    # user asked for only preview video and we've already grabbed the first frame.
                    if preview_video_only and self.c.preview_writer.selected_view_ids is not None:
                        # print("minimizing requested_cameras for preview only.")
                        requested_camera_ids = self.c.preview_writer.selected_view_ids
                        mattes = False

                    # creates combined preview images if requested.
                    if preview_image_setting in (self.PreviewImageMode.EVERY_FRAME, self.PreviewImageMode.FIRST_FRAME):
                        PreviewWriter.save_image_grid(
                            image_entries,
                            f"{combined_preview_image_path}frame_{str(i).zfill(5)}.jpg",
                            f"{recording_name}   frame {i}",
                        )
                    # stop us from downloading the next preview image when FIRST_FRAME is requested
                    if preview_image_setting == self.PreviewImageMode.FIRST_FRAME:
                        preview_image_setting = self.PreviewImageMode.NONE

            self.c.wait_images_transferred()
            end_replay = time.time()
            # waits until the preview video writer is done
            if self.preview_fps > 0:
                self.c.preview_writer.close_writer()
            print(f"{recording_name} replay done. Took {end_replay - start_replay}s")
            print(f"\noutput ---> {save_path}\n")

            # zips the folder and copies to the target_path
            if self.zip_to_path is not None:
                zip_folder(f"{save_path}", f"{self.zip_to_path}/{recording_name}.zip")

    @staticmethod
    def default_save_path(
        c: Controller,
        outputfolder: str,
        recording_name: str,
    ) -> str:
        """
        replace this with your own delegate to create your own save_path logic.
        For example if you don't want the replays grouped by recording_name
        """
        return f"{outputfolder}/{recording_name}"
