import sys
import time

from natsort import natsorted
from pydantic import model_validator

import controller.args as arguments
from controller import (
    Controller,
    ask_for_new_background,
    camera_beep,
    clip_value,
    download_quick_preview,
    stop_on_interrupt,
    system_layout_reader,
    trigger_box,
)
from controller.args.util import (
    CLI_GROUP_CAPTURE_SELECTION,
    CLI_GROUP_IMAGE_CONFIGURATION,
    CLI_GROUP_IMAGE_TRIGGER,
    CliArg,
    ScriptArgumentField,
)
from web_app_integration.script_runner import ScriptRunner


class RecordArgs(
    arguments.server_list_arg(default=None),
    arguments.capture_name_arg(default=None, required=True),
    arguments.ExposureArg,
    arguments.max_recording_time_arg(default=None),
    arguments.auto_trigger_delay_arg(default=None, const=5),
):
    multiple: bool = ScriptArgumentField(
        default=False,
        description="Multiple recordings: After finishing one recording, quickly starts another with the same settings.",
        cli=CliArg(option_strings=["--multiple", "-m"], group=CLI_GROUP_CAPTURE_SELECTION),
    )
    list: bool = ScriptArgumentField(
        default=False,
        description="List available recordings and exit.",
        cli=CliArg(option_strings=["--list", "-l"], group=CLI_GROUP_CAPTURE_SELECTION),
    )
    no_depth: bool = ScriptArgumentField(
        default=False,
        description="Request mono images instead of depth.",
        cli=CliArg(group=CLI_GROUP_IMAGE_CONFIGURATION, option_strings=["--no-depth"]),
    )
    video: int | None = ScriptArgumentField(
        default=None,
        description="Enable video capture and set fps. e.g: --video (default: 25) or --video 30. (If you do not want to specify this beforehand, use --single 0)",
        cli=CliArg(option_strings=["--video", "-v"], group=CLI_GROUP_IMAGE_TRIGGER, nargs="?", const=25),
    )
    single: int | None = ScriptArgumentField(
        default=None,
        description=(
            "Enable single image capture. Trigger manually via commandline or with automatic trigger. "
            "You can specify a maximum image count: e.g --single 10."
        ),
        cli=CliArg(option_strings=["--single"], group=CLI_GROUP_IMAGE_TRIGGER, nargs="?", const=0),
    )

    @model_validator(mode="after")
    def validate_capture_mode(self):
        if (self.video is None) == (self.single is None):
            raise ValueError("Exactly one of --video or --single is required.")
        return self


def print_recording_info_continuous(
    recording_name: str,
    fps: int,
    timeout_seconds: int,
    exposure: float,
    gain: float,
    controller: Controller,
):
    # --- Print all basic recording Information ---
    controller.ui.log("\n")
    controller.ui.log("Recording Info:")
    controller.ui.log(f"    Name of recording:  {recording_name}")
    controller.ui.log("    recording mode:     continuous")
    controller.ui.log(f"        fps:                    {fps}")
    if timeout_seconds:
        controller.ui.log(f"        automatic stop after:   {timeout_seconds} seconds")
    else:
        controller.ui.log("        automatic stop after:   manual stop only")
    controller.ui.log()
    controller.ui.log(f"   Exposure:            {exposure}")
    controller.ui.log(f"   Gain:                {gain}")
    controller.ui.log(f"   Available cameras:   {len(controller._connection.all_camera_ids)}")
    controller.ui.log(f"   Mono_cameras:        {'inactive' if not controller.mono_is_active else 'active'}")
    controller.ui.log(f"   servers:             {len(controller._connection.servernames)}")
    controller.ui.log("\n")


def print_recording_info_single(
    recording_name: str,
    delay_seconds: float,
    max_images: int,
    exposure: float,
    gain: float,
    controller: Controller,
):
    # --- Print all basic recording Information ---
    controller.ui.log("\n")
    controller.ui.log("Recording Info:")
    controller.ui.log(f"    Name of recording:  {recording_name}")
    controller.ui.log("    recording mode:     single")
    if delay_seconds:
        controller.ui.log(f"        delay between images:   {delay_seconds} seconds")
    else:
        controller.ui.log("        delay between images:   manually triggered")
    if max_images > 0:
        controller.ui.log(f"        automatic stop after:   {max_images} images")
    else:
        controller.ui.log("        automatic stop after:   manual stop only")
    controller.ui.log()
    controller.ui.log(f"   Exposure:            {exposure}")
    controller.ui.log(f"   Gain:                {gain}")
    controller.ui.log(f"   Available cameras:   {len(controller._connection.all_camera_ids)}")
    controller.ui.log(f"   Mono_cameras:        {'inactive' if not controller.mono_is_active else 'active'}")
    controller.ui.log(f"   servers:             {len(controller._connection.servernames)}")
    controller.ui.log("\n")


def single_image_capture(max_images: int, delay_seconds: float, c: Controller):

    # If delay seconds is set, automatic_trigger is True
    automatic_trigger = bool(delay_seconds)
    trigger_box("off")

    image_count = 0

    # Loop until max_images is reached (if set) or user stops by pressing 'n'
    while True:
        if max_images and image_count >= max_images:
            c.ui.log(f"Reached maximum number of images: {max_images}")
            break
        # Print current status
        c.ui.log()
        status = c.get_status(0)
        c.ui.log(f"{status.get('recording_name')} frame_count: {image_count}")

        command, automatic_trigger = c.ui.timeout_input(
            auto_trigger_enabled=automatic_trigger,
            timeout_seconds=delay_seconds,
            event_slot="single_capture_command",
            input_type="boolean",
        )  # we have to catch and pass the auto_trigger paramter to allow the user to enter/exit automatic mode

        if command != "n":
            camera_beep()
            if c.mono_is_active:
                # trigger twice so mono projectors can heat up
                trigger_box("single")
            trigger_box("single")
            image_count += 1
        else:  # stop capturing if user inputs "n"
            break


def continuous_image_capture(timeout_seconds: int, c: Controller):
    c.ui.log("READY")
    if timeout_seconds:
        c.ui.log(
            f"Maximum recording time set to {timeout_seconds} seconds. "
            "Press cntrl-c to stop the recording early. "
            "Start recording with enter"
        )
        _ = c.ui.input()
    else:
        c.ui.log(
            "No maximum recording time set. "
            "Manually stop recording with ctrl-c. "
            "Press enter to start recording. "
            "Input integer number to set recording-time:"
        )
        timeout_seconds_overwrite = c.ui.input()
        if timeout_seconds_overwrite.isdigit():
            c.ui.log(f"Setting recording-time to {timeout_seconds_overwrite}")
            timeout_seconds = int(timeout_seconds_overwrite)
    camera_beep()
    trigger_box("on")
    c.ui.log("recording...")
    start = time.time()
    # Loop until recording time is reached or user stops recording with ctrl-c
    while True:
        status = c.get_status(0)
        c.ui.log(f"{status.get('recording_name')} frame_count: {status.get('frame_count')}")
        if timeout_seconds is not None and time.time() - start >= timeout_seconds:
            break

        c.ui.log(f"record_time elapsed: {time.time() - start}")
        time.sleep(1)


def check_recording_overwrite(recording_name: str, c: Controller):
    # Check if a recording of the same name already exists
    saved_recordings = c.get_available_recordings()
    if recording_name in saved_recordings:
        overwrite_user_input = c.ui.boolean_user_input(f"\nOverwrite previous recording {recording_name}?")
        if not overwrite_user_input:
            c.ui.log("Not overwriting. Exit")
            sys.exit()
        else:
            c.ui.log("Overwriting previous recording.")


def capture_setup(
    recording_name: str,
    single_image_mode: bool,
    fps: int,
    exposure: float,
    gain: float,
    c: Controller,
    ask_background: bool = True,
):

    # --- Start Setup ---
    c.switch_mode("single")
    c.check_calibration_file_sync()

    c.set_exposure_and_gain(exposure, gain)
    c.set_exposure_and_gain(40, 0, "depth")

    if ask_background:
        ask_for_new_background(c)
    else:
        print("No Background caputre")

    trigger_box("off")
    if not single_image_mode:
        trigger_box(f"set_fps_{fps}")

    c.switch_mode("record")
    c.set_recording_name(recording_name, fps)

    # If mono cameras are active we need to ignore the first frame that's captured in a series because
    # The IR projectors need to heat up (by triggering once) to achieve full illumintation
    if c.mono_is_active:
        if single_image_mode:  # single mode always triggers twice, ignoring the first of the images
            c.ui.log("setting skip frames: 1 (mono cameras active in single mode)")
            c.set_skip_frames(1)
        else:  # contionus mode only ignores the very first image.
            c.ui.log("skip first frame (mono cameras active in continous mode)")
            c.skip_next_frame()

    # Check if right recording name is set at all servers
    n = [c.get_status(idx).get("recording_name") for idx in range(len(c._connection.servernames))]
    assert (
        len(set(n)) == 1 and n[0] == recording_name
    ), f"failed to set recording_name in one or more servers {list(zip(c._connection.servernames, n))}"


class Record(ScriptRunner):
    def _get_args_pydantic_model(self) -> type:
        return RecordArgs

    def main(self, args: RecordArgs) -> None:

        # --- Define variables ---

        exposure, gain = args.exposure_settings.exposure, args.exposure_settings.gain
        # ToDo: Add expected cameras (mono) to system_layout.json
        slr = system_layout_reader.SystemLayoutReader()
        expected_cameras = slr.get_expected_number_of_cameras()
        server_list = args.server
        single_image_mode = args.single is not None
        multiple_mode = args.multiple

        # --- Recording name ---
        recording_name = args.capture_name

        # Make sure the recording name ends with _pose for single image mode and _video for continuous video
        if (recording_name.endswith("_pose")) and not single_image_mode:
            choice = self.ui.boolean_user_input(
                f"Capture in single image mode instead of continuous video for {recording_name}? This warning is triggered because the recording name ends with '_pose'"
            )
            single_image_mode = choice
        elif (recording_name.endswith("_video")) and single_image_mode:
            choice = self.ui.boolean_user_input(
                f"Capture in coninuous video instead of single image mode for {recording_name}? This warning is triggered because the recording name ends with '_video'"
            )
            single_image_mode = not choice

        # --- Variables for single mode ---

        delay_seconds = args.auto_trigger_delay
        delay_seconds = clip_value(delay_seconds, min_value=0.04)

        max_images = args.single
        if max_images is not None:
            max_images = clip_value(max_images, min_value=0)

        # --- Variables for continuous mode ---

        fps = args.video
        if fps is not None:
            fps = clip_value(fps, min_value=1, max_value=60)

        timeout_seconds = args.time
        timeout_seconds = clip_value(timeout_seconds, min_value=1)

        # --- Start Connecting ---

        with Controller(server_list, user_interface=self.ui) as c:
            if args.list:
                available_recordings = c.get_status(0, verbose=True).get("available_recordings")
                available_recordings = natsorted(available_recordings)
                c.ui.log("Available recordings:")
                for rec in available_recordings:
                    c.ui.log(rec)
                return

            # Check if all expected cameras are available
            if not server_list:
                if len(c.all_camera_ids) < expected_cameras:
                    c.ui.log(f"Warning: Missing cameras! Expected {expected_cameras}, found {len(c.all_camera_ids)}.")
                    choice = c.ui.boolean_user_input("Do you want to continue anyway?", default_choice=False)
                    if not choice:
                        c.ui.log("Aborting due to missing cameras.")
                        raise SystemExit(1)
                    c.ui.log("Continuing despite missing cameras...")

            recording_base_name = recording_name
            sequence_number = 1
            ask_background = True

            try:
                mode = "COLOR" if args.no_depth else "DEPTH"
                c.set_depth_active(mode)
            except Exception as e:
                c.ui.log(e, "Setting depth mode failed for some servers.")

            # While loop for multiple mode. If not in multiple mode, it will be exited after one sequence
            while True:

                if multiple_mode:
                    recording_name = recording_base_name + "_" + str(sequence_number).zfill(3)
                    c.ui.input(
                        f"Press enter to start the next recording sequence (number {sequence_number}), the next recording will be saved as {recording_name}"
                    )

                check_recording_overwrite(recording_name=recording_name, c=c)

                # --- Print Recording Information ---
                if single_image_mode:
                    print_recording_info_single(recording_name, delay_seconds, max_images, exposure, gain, c)
                else:
                    print_recording_info_continuous(recording_name, fps, timeout_seconds, exposure, gain, c)

                capture_setup(
                    recording_name=recording_name,
                    single_image_mode=single_image_mode,
                    fps=fps,
                    exposure=exposure,
                    gain=gain,
                    c=c,
                    ask_background=ask_background,
                )
                ask_background = False

                # --- Start Recording ---
                c.start()
                s = c.get_status(0)
                c.ui.log(f"\nRecorder started for {s.get('recording_name')}")

                # Catch Keyboard interrupt
                with stop_on_interrupt():
                    if single_image_mode:
                        single_image_capture(max_images, delay_seconds, c)
                    else:  # free capture mode
                        continuous_image_capture(timeout_seconds, c)

                # --- Stop Recording ---
                if not single_image_mode:
                    camera_beep("boop")
                trigger_box("off")
                c.ui.log("trigger stopped")
                time.sleep(0.5)  # wait for last frame to be captured

                c.stop()

                # --- Check Recording ---
                c.ui.log("\nChecking result:")
                c.check_frame_count()
                c.ui.log()

                # --- Download Preview ---
                if single_image_mode:
                    frame_step = 1
                else:
                    frame_step = 6

                choice = c.ui.input(f"\nPreview every {frame_step}-th frame? [Y,n] or [Integer Number]")
                if choice.upper() != "N":
                    if choice.upper() != "Y":
                        frame_step = int(choice)

                    download_quick_preview(
                        c,
                        recording_name,
                        "Capture/",
                        frame_step,
                        fps,
                        requested_camera_ids=c.cameras_of_type("D") + c.system_layout.get_center_cameras(),
                    )

                if multiple_mode:
                    choice = c.ui.boolean_user_input(
                        f"Recording squence number {sequence_number} finished, do you want to start another sequence?"
                    )
                    if not choice:
                        c.ui.log("Stopping capture sequence")
                        break
                else:
                    break
                sequence_number += 1


if __name__ == "__main__":
    Record.run_in_cli()
