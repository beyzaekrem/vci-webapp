# ruff: noqa: T201, INP001
import argparse
import time

from controller import (
    Controller,
    argmods,
    stop_on_interrupt,
    trigger_box,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Records mutliple frames and averages them into one mean image")
    parser = argmods.add_server_list_argument(parser)
    trigger_group = parser.add_argument_group("IMAGE TRIGGER")
    trigger_group.add_argument(
        "--single",
        action="store_true",
        help="enable single image mode (as opposed to continuous video)",
    )
    trigger_group.add_argument(
        "-i",
        "--image_cnt",
        type=int,
        default=10,
        help="image cnt to be captured and averaged",
    )
    output_group = parser.add_argument_group("OUTPUT CONTROL")
    argmods.add_output_folder_argument(output_group, default="TEST")
    argmods.add_capture_name_argument(output_group, default="test_mean")
    argmods.add_folder_mode_argument(output_group, "append")

    image_group = parser.add_argument_group("IMAGE CONFIGURATION")
    argmods.add_exposure_argument(image_group)
    argmods.add_processing_steps_argument(image_group)
    argmods.add_quality_argument(image_group, default="avif_ll")

    args = parser.parse_args()
    server_list = args.server
    exposure_profile: argmods.ExposureSettings = args.exposure
    quality: argmods.ImageQualitySettings = args.quality
    image_cnt = args.image_cnt

    # settings:

    recording_name = args.capture_name
    fps = 25

    c = Controller(server_list)
    c.set_image_path(str(args.outputfolder / recording_name))
    c.switch_mode("single")
    c.check_calibration_file_sync()

    trigger_box("off")
    trigger_box(f"set_fps_{fps}")
    c.set_exposure_and_gain(exposure_profile.exposure, exposure_profile.gain)

    c.switch_mode("record")
    c.set_recording_name(recording_name)

    n = [c.get_status(idx).get("recording_name") for idx in range(len(c.servernames))]
    if len(set(n)) != 1 or n[0] != recording_name:
        msg = f"failed to set recording_name in one or more servers {list(zip(c.servernames, n, strict=True))}"
        raise RuntimeError(msg)

    c.start()
    s = c.get_status(0)
    print(f"\nRecorder started for {s.get('recording_name')}")
    if c.mono_is_active:
        # heat up IR projectors
        c.skip_next_frame()
        trigger_box("single")
    # trigger images in manual trigger mode or free capture mode
    with stop_on_interrupt():
        trigger_box("on")
        start = time.time()
        print("recording...")
        time.sleep(image_cnt / fps)
        print("record_time elapsed:", time.time() - start)
    trigger_box("off")
    print("trigger stopped")
    time.sleep(0.2)  # wait for last frame to be captured

    c.stop()
    print("\nChecking result:")
    frame_cnts = c.check_frame_count()
    print()

    c.switch_mode("replay")

    c.set_recording_name(recording_name)

    print("retriving mean image ...")
    c.capture_mean(steps=args.processing, image_format=quality.format, quality=quality.quality)
    print("done")

    frame = min(frame_cnts) - 1
    print(f"retriving single frame {frame}...")

    c.capture_images(
        frame_idx=frame,
        steps=args.processing,
        mattes=True,
        image_format=quality.format,
        quality=quality.quality,
        mattes_format=quality.mattes_format,
        mattes_quality=quality.mattes_quality,
    )
    print("done")
    print(f"output saved to {c.get_output_folder()}")
    c.close()


if __name__ == "__main__":
    main()
