# ruff: noqa: T201
import argparse

from controller import Controller, FolderMode, ProcessingSteps, argmods, path_patterns, recording_helper


def main() -> None:
    args, parser = arguments()
    with Controller(args.server, mode=None) as c:
        available_recordings = c.get_available_recordings()

        if args.list:
            print("Available recordings:")
            for rec in available_recordings:
                print(rec)
            return

        r = recording_helper.ReplayOMat(c, outputfolder=args.outputfolder)
        series_selection: argmods.FlexiRange | None = args.series
        if args.list_info:
            print("Available recordings + info:")
            c.switch_mode("replay")
            if args.capture_name is None:
                selected_recordings = available_recordings
            else:
                selected_recordings = r.get_recordings_from_series(args.capture_name, series_selection)

            total_frames = 0
            for rec in selected_recordings:
                with c.filter_connections(c.get_servers_with_recording(rec)):
                    c.set_recording_name(rec)
                    details = recording_helper.RecordingDetails(c, rec)
                    print(details)

            print(f"{len(selected_recordings)} recordings. Total {total_frames} frames.")
            return

        r.zip_to_path = args.zip_to
        r.get_background = not args.no_background
        r.get_calib_file = not args.no_calib
        r.save_individual_camera_frames = True
        r.foldermode = args.folder_mode

        r.requested_camera_ids = args.cams  # wildcard pattern of selected cameras
        r.processing = args.processing
        if args.no_rotation:
            r.processing = ProcessingSteps.OVERWRITE_NO_ROTATION(r.processing)
        r.quality = args.quality
        r.mattes = not args.no_mattes

        r.ignore_frame_count_mismatch = args.ignore_mismatch
        frame_selection: argmods.FlexiRange = args.frames

        r.combined_preview_images = r.PreviewImageMode[args.preview_images]
        r.preview_fps = args.preview_fps  # int [0=disbaled, 1, ..., 100=all]
        r.preview_video_prefered_cameras = argmods.resolve_cameras(args.video_cams, c.system_layout)
        r.preview_view_cnt = args.view_cnt

        # legacy output structure
        if args.legacy_output:
            r.set_image_path_delegate = old_output_strucutre

        if args.only_calib:  # quick setting only download the calib file
            r.save_individual_camera_frames = False
            r.ignore_frame_count_mismatch = True
            frame_selection = argmods.FlexiRange([])  # no frames selected
            r.get_background = False
            r.get_calib_file = True
            r.foldermode = FolderMode.save
            r.preview_fps = 0  # disabled
            r.combined_preview_images = r.PreviewImageMode.NONE

        if args.no_preview:
            r.preview_fps = 0  # disabled
            r.combined_preview_images = r.PreviewImageMode.NONE
        if args.preview_only or args.flat_video:
            r.save_individual_camera_frames = False
            r.get_background = True
            r.get_calib_file = False

            r.quality = argmods.HIGH_QUALITY_JPG
            if ProcessingSteps.steps_contain(r.processing, "superkernel"):
                r.processing = ProcessingSteps.TINY

            if args.flat_video:
                r.get_background = False
                r.set_image_path_delegate = replay_preview_video_flat_hierarchy
                if args.preview_images == r.PreviewImageMode.EVERY_FRAME:
                    r.combined_preview_images = r.PreviewImageMode.FIRST_FRAME

        elif args.flat:
            r.set_image_path_delegate = image_hierarchy_flat

        if series_selection:
            # capture_name refers to a series
            r.replay_series(args.capture_name, series_selection, frame_selection)
        elif args.capture_name not in available_recordings:
            print(
                f"Recording name '{args.capture_name}' not found in available recordings. Use --list to see available recordings."
            )
            return
        else:
            r.replay(args.capture_name, frame_selection)


def arguments() -> tuple[argparse.Namespace, argparse.ArgumentParser]:
    parser = argparse.ArgumentParser(
        description=(
            "Downloads a previously captured recording from server harddrives. "
            "The recording is saved in raw, so you can freely select the porcessing steps, quality and frame range. "
            "The output path is constucted like this: outputfolder/capture_name/. "
            "In addition to the individual frames, preview vidoes and images will be downloaded. "
            "These are placed into ouptutfolder/capture_name/preview. "
            "To delete a recording from the server harddrives use delete_recording.py"
        )
    )
    parser = argmods.add_server_list_argument(parser)

    recording_group = parser.add_argument_group("SELECT RECORDING")
    recording_group.add_argument("--list", "-l", action="store_true", help="List available recordings and exit.")
    recording_group.add_argument("--list-info", action="store_true", help="List available recordings + info.")
    argmods.add_capture_name_argument(recording_group, default=None, resolve_date=False)
    argmods.add_flexi_range_argument(
        recording_group,
        "Treats the --capture-name as a series (e.g 'capture' -> capture_001, capture_002 ...). --series downloads every recording from the series. Otherwise: ",
        "--series",
        default=None,
    )

    frame_group = parser.add_argument_group("FRAME SELECTION")
    argmods.add_flexi_range_argument(frame_group, "Select frame(s) for download.", "--frames", "-f")

    output_group = parser.add_argument_group("OUTPUT CONTROL")
    argmods.add_output_folder_argument(output_group, default="CAPTURE")
    argmods.add_folder_mode_argument(output_group, default="save")
    output_group.add_argument(
        "--flat",
        action="store_true",
        help="outputs a flattened image hierarchy: <outputfolder>/rgb/<camera>_F<frame_idx>",
    )
    output_group.add_argument(
        "--legacy-output",
        action="store_true",
        help="outputs legacy output structure: rgb and mask folders. New output structure: image and mask folders",
    )
    output_group.add_argument(
        "--zip-to",
        default=None,
        type=argmods.output_paths_argument.output_folder_type,
        help="After image download, the image directory can be zipped and moved to a secified path. e.g. a Scibo folder. Input options are identical to --outputfolder. Default: None - no zipping",
    )

    image_group = parser.add_argument_group("IMAGE CONFIGURATION")
    argmods.add_cameras_argument(image_group, default="ALL", description="Select cameras for download. ")
    argmods.add_processing_steps_argument(image_group, default="processed")
    image_group.add_argument("--no-rotation", action="store_true", help="skips image rotation")

    argmods.add_quality_argument(image_group, default="avif_ll")
    image_group.add_argument("--no-mattes", action="store_true", help="disables mattes download")
    image_group.add_argument("--no-background", action="store_true", help="disables background download")
    image_group.add_argument("--no-calib", action="store_true", help="disables calibration file download")

    image_group.add_argument(
        "--only-calib",
        action="store_true",
        help="quick setting: only download the calib file(s)",
    )

    image_group.add_argument("--ignore-mismatch", action="store_true", help="ignores frame count mismatch")

    preview_group = parser.add_argument_group(
        "PREVIEW SETTINGS",
    )
    image_mode_choices = [mode.name for mode in recording_helper.ReplayOMat.PreviewImageMode]
    preview_group.add_argument(
        "--preview-images",
        type=str.upper,
        choices=image_mode_choices,
        default=recording_helper.ReplayOMat.PreviewImageMode.AUTO.name,
        help="This options creates a combined preview image of all downloaded cameras. FIRST_FRAME - only a preview image for the first downloaded frame and the background, EVERY_FRAME - creates a preview image for every downloaded frame, NONE - no preview images. Default: FIRST_FRAME.",
    )
    preview_group.add_argument(
        "--preview-fps",
        type=int,
        default=5,
        help="Set target fps for the preview video. Set to 100 for all frames, 0=Disabeld. If recording contains disjointed frames the preview-fps is capped at 1 fps.",
    )
    preview_group.add_argument(
        "--view-cnt",
        type=int,
        default=6,
        help="The number of views shown in the preview video. Default: 6 views.",
    )
    argmods.add_cameras_argument(
        preview_group,
        default="CENTER",
        description="Select prefered cameras for preview video. Views will be removed/added to reach the --view-cnt.",
        name="--video-cams",
        short_name=None,
    )

    preview_only_group = parser.add_argument_group("PREVIEW ONLY")
    preview_only_features = preview_only_group.add_mutually_exclusive_group()
    preview_only_features.add_argument(
        "--flat-video",
        action="store_true",
        help=(
            "Quickly downloads only a preview video into a **flattend hierarchy**: outputfolder/_previews/<recording_name>.mp4 "
            "for a convenient overview over lots of different captures. "
            "Overwrites the --frames selection to ::6 - every 6th frame. "
            "Overwrites processing and quality to tiny jpg images for speed. "
            "Valid preview-image modes: NONE, FIRST (output to _previews as well). "
            "Skipps invidial camera frames, calibration and background download. "
        ),
    )
    preview_only_features.add_argument(
        "--preview-only",
        action="store_true",
        help=(
            "Creates only **the preview folder** content using the selected preview and frame settings. "
            "Output: outputfolder/<recording_name>/previews/. "
            "Overwrites processing and quality to tiny jpg images for speed. "
            "Skips individual camera frames, calibration and background download. "
        ),
    )
    preview_only_features.add_argument("--no-preview", action="store_true", help="disabels preview creation")

    return parser.parse_args(), parser


def replay_preview_video_flat_hierarchy(c: Controller, output_folder: str, recording_name: str) -> str:
    """
    saves _previews location, like quick replay from capture_record
    example:
     - preview_images in output_folder/ _previews / <recording_name>.mp4
    """
    save_path = f"{output_folder}"
    path_patterns.joint_preview_folder(c, recording_name, folder_name="_previews")
    return save_path


def old_output_strucutre(c: Controller, output_folder: str, recording_name: str) -> str:
    save_path = f"{output_folder}/{recording_name}"
    path_patterns.old_path_patterns(c)
    return save_path


def image_hierarchy_flat(c: Controller, output_folder: str, recording_name: str) -> str:
    save_path = f"{output_folder}/{recording_name}"
    path_patterns.vci_course_path_pattern(c)
    return save_path


if __name__ == "__main__":
    main()
