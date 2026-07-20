import argparse
import shutil
import zipfile
from pathlib import Path

from tqdm import tqdm  # You need to install this: pip install tqdm


def zip_folder(src_folder, target_path):
    src_folder = Path(src_folder)
    zip_path = src_folder.with_suffix(".zip")  # next to the folder

    print(f"Zipping {src_folder} to {zip_path} and sending to {target_path} ...")

    # list of all files to be zipped to determine the total count
    all_files = [file for file in src_folder.rglob("*") if file.is_file()]
    total_files = len(all_files)

    # Create zip next to folder
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
    ) as zf:
        with tqdm(total=total_files, unit="file", desc="Zipping files") as pbar:
            for file in all_files:
                zf.write(file, file.relative_to(src_folder))
                pbar.update(1)  # Increment the progress bar

    print("\nZip finished")

    if target_path is not None:
        target_path = Path(target_path)
        # Move to final destination
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(zip_path), str(target_path))

    return target_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zip folder")
    parser.add_argument("folder", type=str, help="The path to the folder to be zipped.")
    parser.add_argument(
        "--move_to",
        "-m",
        type=str,
        default=None,
        help="Optional: A location to move the finished zip to. For example /home/ximea/Sciebo/Capture/",
    )
    args = parser.parse_args()
    zip_folder(args.folder, args.move_to)
