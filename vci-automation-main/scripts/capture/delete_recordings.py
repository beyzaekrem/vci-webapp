# ruff: noqa: T201

import argparse
import contextlib
from pathlib import Path

from controller import (
    Controller,
    PreviewWriter,
    ProcessingSteps,
    argmods,
    exceptions,
    recording_helper,
    stop_on_interrupt,
    trigger_box,
)

STEPS = ProcessingSteps.TINY
QUALITY = argmods.HIGH_QUALITY_JPG


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Searches and deletes recordings that contain the --capture-name. "
            "For each recoring a preivew image is downloaded first and you confirm deletion per recording."
        )
    )
    parser = argmods.add_server_list_argument(parser)

    group = parser.add_argument_group("SEARCH & PREVIEW")

    exclusive_actions = group.add_mutually_exclusive_group(required=True)
    exclusive_actions.add_argument("--list", "-l", action="store_true", help="List available recordings and exit.")
    exclusive_actions.add_argument(
        "--capture-name",
        "-n",
        type=str,
        help="Search key for recordings to be deleted from the server handdrives (e.g. 'capture_001').",
    )
    argmods.add_output_folder_argument(group, default="TEST/delete_recordings")

    args = parser.parse_args()
    with Controller(args.server, mode="replay") as c:

        available_recordings = c.get_available_recordings()
        print("\n")
        if args.list:
            print("Available recordings:")
            for rec in available_recordings:
                print(rec)
            return

        search_key = args.capture_name
        if search_key in available_recordings:
            print(f"found recording '{search_key}'")
            delete(search_key, c, args.outputfolder)
        else:
            selected_recordings = [recording for recording in available_recordings if search_key in recording]
            print(f"found {len(selected_recordings)} recordings containing {search_key}: {selected_recordings}")

            for recording_name in selected_recordings:
                delete(recording_name, c, args.outputfolder)


def delete(
    recording_name: str,
    c: Controller,
    outputfolder: Path | str,
) -> None:
    with c.filter_connections(c.get_servers_with_recording(recording_name)):
        c.set_recording_name(recording_name)
        rec_details = recording_helper.RecordingDetails(c, recording_name)
        with contextlib.suppress(exceptions.TriggerBoxError):
            trigger_box("off")

        p = Path(outputfolder) / f"{recording_name}"
        p.mkdir(exist_ok=True, parents=True)
        print(f"\n--- {recording_name} ----")
        rec_details.pretty_print()
        frame_counts = c.check_frame_count(raise_exception=False)
        sequence_length = min(frame_counts)

        if input("Get preview images? [Y,n]").lower() != "n":
            try:
                print(f"Getting preview. Output: {p}")
                print("get frame 0")
                image_entries = c.capture_images(
                    steps=STEPS,
                    frame_idx=0,
                    image_format=QUALITY.format,
                    quality=QUALITY.quality,
                    requested_camera_ids=None,
                    invalid_ok=True,
                )
                PreviewWriter.save_image_grid(image_entries, f"{p!s}/frame_0.jpg", f"{recording_name} frame 0")

                with stop_on_interrupt():
                    for i in range(1, sequence_length, max(sequence_length // 5, 1)):
                        print("get frame", i)
                        image_entries = c.capture_images(
                            steps=STEPS,
                            frame_idx=i,
                            image_format=QUALITY.format,
                            quality=QUALITY.quality,
                            requested_camera_ids=None,
                            invalid_ok=True,
                        )
                        camera_ids = {entry.cam_id for entry in image_entries}
                        PreviewWriter.save_image_grid(
                            image_entries,
                            f"{p!s}/frame_{i}_cameras_{len(camera_ids)}.jpg",
                            f"{recording_name} frame {i} - {len(camera_ids)} cameras",
                        )
            except Exception as e:
                print(e, f"\n----Getting preview images for {recording_name} failed.----")

        print(f"Recording contains {sequence_length} images.")
        delete = input(f"\nDELETE {recording_name}? [y, N]").lower() == "y"
        if delete:
            print("deleting...")
            c.send("DELETE_RECORDING", {"recording_name": recording_name})
            c.send("DELETE_DEPRECATED_BACKGROUND", {"recording_name": recording_name})
        else:
            print("Not deleting")


if __name__ == "__main__":
    main()
