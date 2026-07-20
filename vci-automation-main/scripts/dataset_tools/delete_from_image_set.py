# ruff: noqa: T201, INP001
import argparse
import shutil
from pathlib import Path

from natsort import natsorted

from controller import argmods

# Tuple format: (start_frame, end_frame_exclusive_or_none, step)
# None is used for the exclusive end when defining a single frame index.


def arugments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Searches for files and folders with the given glob pattern. The results are deleted after user confirmation."
    )
    parser.add_argument(
        "--folder",
        type=argmods.output_paths_argument.output_folder_type,
        help="path to the image set. Supports presets TEST CAPTURE etc",
        default="TEST/2025_10_28_ir_poses",
    )
    parser.add_argument(
        "--glob",
        "-g",
        type=str,
        help='glob pattern to seach and delete folders or files from the image set(s). E.g: "**/color_C0030*" or "**/frame_00000*"',
    )
    return parser.parse_args()


def main() -> None:
    args = arugments()

    parent_folder = Path(args.folder)
    if not parent_folder.exists():
        raise FileNotFoundError(f"Folder {parent_folder} cannot be found")
    print(parent_folder)

    print(args.glob)  # bonn_tele_bench*
    print(f"searching for {args.glob} in {parent_folder}")
    delete_list = natsorted(parent_folder.glob(args.glob))
    if len(delete_list) == 0:
        print("found nothing.")
        exit()
    print(f"------- found {len(delete_list)}-------")
    for entry in delete_list:
        print(str(entry))
    print(f"------- found {len(delete_list)} files or folders matching {args.glob} -------")

    delete = input("\nAre you sure you want to delete these files/folders? Type [yes] to confirm. ")
    delete = delete.lower() == "yes"

    if not delete:
        print("\nnot deleting. Buh bye!")
    else:
        print("\n deleting...")
        for entry in delete_list:
            try:
                if entry.is_dir():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
                print(f"deleted {entry}")
            except Exception as e:
                print(f"failed to delete {entry}: {e}")
        print("\nDone")


if __name__ == "__main__":
    main()
