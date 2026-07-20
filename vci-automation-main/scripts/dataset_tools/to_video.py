# ruff: noqa: T201, INP001

import argparse
import glob
import os
import subprocess


def process_cameras(cameras_root, fps):
    if not os.path.isdir(cameras_root):
        print(f"Error: The directory '{cameras_root}' does not exist.")
        return

    # Iterate through all items in the root directory
    for item in os.listdir(cameras_root):
        sub_dir = os.path.join(cameras_root, item)

        # Only process if it's a directory
        if os.path.isdir(sub_dir):
            # Verify it contains our expected PNG files
            avif_files = glob.glob(os.path.join(sub_dir, "frame_*.avif"))
            if not avif_files:
                print(f"Skipping '{item}': No 'frame_*.avif' files found.")
                continue

            # Save inside the specific camera directory
            output_file = os.path.join(sub_dir, f"{item}.mp4")

            # Input pattern: assumes standard sequential naming like frame_00000.avif
            input_pattern = os.path.join(sub_dir, "frame_%05d.avif")

            print(f"\n--- Processing '{item}' into {output_file} ---")

            # Build the FFmpeg command
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",  # Overwrite output file if it exists
                "-framerate",
                str(fps),  # Set input framerate
                "-i",
                input_pattern,  # Input files
                "-c:v",
                "h264_nvenc",  # --- UPDATED: NVIDIA Hardware H.264 Encoder ---
                "-pix_fmt",
                "yuv420p",  # Pixel format for maximum player compatibility
                output_file,
            ]

            try:
                # Execute the FFmpeg command
                subprocess.run(ffmpeg_cmd, check=True)
                print(f"Successfully generated {output_file}")
            except subprocess.CalledProcessError as e:
                print(f"FFmpeg failed while processing '{item}'. Error: {e}")
            except FileNotFoundError:
                print("Error: 'ffmpeg' command not found. Please ensure FFmpeg is installed and in your system PATH.")
                break


def main():
    parser = argparse.ArgumentParser(
        description="Convert directories of PNG frames into MP4 videos using FFmpeg and h264_nvenc."
    )
    parser.add_argument(
        "--cameras-root", required=True, help="Path to the parent directory containing the camera subdirectories."
    )
    parser.add_argument("--fps", type=int, default=30, help="Framerate for the output video (default: 30).")

    args = parser.parse_args()
    process_cameras(args.cameras_root, args.fps)


if __name__ == "__main__":
    main()
