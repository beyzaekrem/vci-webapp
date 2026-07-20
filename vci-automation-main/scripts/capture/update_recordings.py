# ruff: noqa: T201, INP001
import argparse
from pathlib import Path

import interceptor

from controller import Controller, PreviewWriter, ProcessingSteps, argmods, trigger_box


def main():
    parser = argparse.ArgumentParser(description="replay recording")
    parser = argmods.add_server_list_argument(parser)
    args = parser.parse_args()
    c = Controller(args.server, mode="replay")

    available_recordings = c.get_available_recordings()

    series = "bonn_tele_bench_029"
    ignores = ["emotions", "dynamic", "yoga"]

    without_frame0_bg = ["head_avatar", "capture"]

    failed_for = []
    for recording_name in available_recordings:
        if series in recording_name:
            if any([ignore in recording_name for ignore in ignores]):
                print("ignore", recording_name)
                continue
            failed = update(recording_name, c)
            # failed = True
            if failed:
                failed_for.append(recording_name)
    print(f" old recordings: {failed_for}")
    c.wait_images_transferred()


outputfolder = "Capture/Tests/update_background"
fix_missing_backgrounds = True
fix_missing_camera_ids = False
only_check_for_bg = False


def update(
    recording_name,
    c: Controller,
):
    c.set_recording_name(recording_name)
    steps = ProcessingSteps.TINY
    # requested_camera_ids = c.system_layout.get_center_cameras()

    trigger_box("off")

    print("\nCheck raw background ", recording_name, "\n")

    if fix_missing_camera_ids:
        c.send("SET_CAMERA_IDS_AS_CAPTURE")
    # c.set_image_path(f"{outputfolder}/{recording_name}")

    p = Path(f"{outputfolder}/{recording_name}")
    p.mkdir(exist_ok=True, parents=True)
    failed = True
    try:
        image_entries = c.grab_background_images(steps=steps)
        PreviewWriter.save_image_grid(image_entries, f"{p!s}/background.jpg")
        print("background images avaliable")
        failed = False
    except interceptor.PathHandlerFailedError:
        print(f"no raw background images for {recording_name}")
    if fix_missing_backgrounds:
        if failed:
            print("set frame zero as background")
            c.send("FRAME_ZERO_BACKGROUND")
            c.set_recording_name("bonn_tele_bench_003")  # force complete reload of backgrounds
            c.set_recording_name(recording_name)
            failed = True
            try:
                print("try to grab background again")
                image_entries = c.grab_background_images(steps=steps)
                PreviewWriter.save_image_grid(image_entries, f"{p!s}/background.jpg")

                failed = False
            except interceptor.PathHandlerFailedError:
                print(f"still failed to retrieve background :/ {recording_name}")

    if not only_check_for_bg:
        frame_counts = c.check_frame_count(raise_exception=False)
        sequence_length = min(frame_counts)

        if failed:
            print("get frame 0")
            image_entries = c.capture_images(
                frame_idx=0,
                image_format="jpg",
                quality=70,
                steps=steps,
                requested_camera_ids=None,
            )
            PreviewWriter.save_image_grid(image_entries, f"{p!s}/frame_0.jpg")

        image_entries = c.capture_images(
            frame_idx=sequence_length // 2,
            image_format="jpg",
            quality=70,
            steps=steps,
            requested_camera_ids=None,
            mattes=not failed,
        )
        camera_ids = set([entry.cam_id for entry in image_entries])
        PreviewWriter.save_image_grid(
            image_entries,
            f"{p!s}/frame_{sequence_length//2}_cameras_{len(camera_ids)}.jpg",
        )
    return failed


if __name__ == "__main__":
    main()
