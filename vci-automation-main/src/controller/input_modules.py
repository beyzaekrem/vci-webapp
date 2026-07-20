import contextlib
import time

import torch
from inputimeout import TimeoutOccurred, inputimeout

from . import path_patterns
from .controller import Controller
from .play_sound import camera_beep
from .processing_steps import ProcessingSteps
from .trigger_box_connection import trigger_box


def timeout_input(
    wait_prompt: str = "Trigger Next image [Y,n]: ",
    timeout_prompt: str = "Auto triggering.... ",
    timeout_return="y",
    auto_trigger_enabled: bool = False,
    timeout_seconds: float = None,
) -> tuple[str, bool]:
    """
    Input prompt with optional timeout feature.
    When calling timeout_input in a loop, the user can choose to enable the timeout feature with the command "a" (autoamtic).
    They can disable the timeout with the command "s" (stop).

    :param str wait_prompt: The prompt to display when timeout is disabled.
    :param str timeout_prompt: The prompt to display when timeout is enabled.
    :param str timeout_return: The command that is returned automatically upon timeout.
    :param bool auto_trigger_enabled: enables/disables timeout feature.
    :param int timeout_seconds: The wait time for the timeout in seconds.

    :returns str command: The user input or the timeout_return
    :returns bool auto_trigger_enabled: The current auto_trigger_enabled flag,
      respecting the user entering/exiting the timeout feature.

    **Example**

    The user enters an input loop where they can perform some action repeatedly.
    They can choose to enter the auto trigger / timeout mode to automatically "press the button" for them.
    In order to stop the input loop, they can to exit the timeout mode first (with "s") and then exit the wait prompt as well.

    ::

        auto_trigger = False
        while True:
            command, auto_trigger = timeout_input("Trigger Image [Y,n]",
                                                "Auto triggering...",
                                                auto_trigger_enabled=auto_trigger)
            # passing and catching the auto_trigger
            # so the user can enter/exit the timeout mode
            if command == "s":
                continue # stop the auto trigger - going back to wait prompt
            if command == "n":
                break # exit the loop
            else:
                # some task triggered either manually or from timeout

    """
    if auto_trigger_enabled:
        try:
            timeout_seconds = 3 if timeout_seconds is None else timeout_seconds
            command = inputimeout(prompt=f"{timeout_prompt} [s] to stop: ", timeout=timeout_seconds).lower()
            if command == "s":  # exit auto_trigger mode
                return timeout_input(wait_prompt, timeout_prompt, timeout_return, False, timeout_seconds)
            return command, True
        except TimeoutOccurred:
            return timeout_return, True
    else:  # waiting mode
        command = input(wait_prompt).lower()
        if command == "a":  # enter auto trigger mode
            return timeout_input(wait_prompt, timeout_prompt, timeout_return, True, timeout_seconds)
        return command, False


@contextlib.contextmanager
def stop_on_interrupt():
    try:
        yield
    except KeyboardInterrupt:
        print("Stopping via Keyboard Interrupt")


@contextlib.contextmanager
def trigger_single(c: Controller, fps=15, *, force_burst: bool = False):
    """Use as context manager.
    Trigger a single image. If depth cameras are connected, triggers via a short burst of pulsed triggers.
    Unused frames are flushed at the end of the context manager.
    """
    if len(c.cameras_of_type("D")) > 0 or force_burst:
        print("depth camera detected")
        trigger_box(f"set_fps_{fps}")
        trigger_box("on")
        camera_beep()
        try:
            yield
        finally:
            trigger_box("off")
            c.send("FLUSH_IMAGE_BUFFER")
            camera_beep("boop")
    else:
        camera_beep()
        trigger_box("single")
        yield


class CudaTimer:
    def __init__(self, name="gpu block", startEvent=None, endEvent=None, enabled=True):
        self.name = name
        self.enabled = enabled
        if enabled:
            self.start = startEvent
            self.end = endEvent
            if self.start is None:
                self.start = torch.cuda.Event(enable_timing=True)
            if self.end is None:
                self.end = torch.cuda.Event(enable_timing=True)

    def __enter__(self):
        if self.enabled:
            self.start.record()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.enabled:
            self.end.record()
            torch.cuda.synchronize()
            elapsed = self.start.elapsed_time(self.end)
            print(f"                   {self.name}: {elapsed:.3f} ms")


class Timer:
    """
    Measures how cpu operations take.

    Example:
        with Timer("my awesome operations"):
            time.sleep(4)
            ...
    """

    def __init__(self, name: str = "cpu", *, enabled: bool = True) -> None:
        self.name = name
        self.enabled = enabled
        self.elapsed = 0

    def __enter__(self) -> None:
        if self.enabled:
            self.start = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        if self.enabled:
            self.end = time.time()
            self.elapsed = self.end - self.start
            print(self.__str__())

    def __str__(self) -> str:
        return f"Timer -- {self.name} took {round(self.elapsed, 4)} seconds"


def ask_for_new_background(c: Controller, *, request: bool = True) -> None:
    # background capture
    mode = [c.get_status(idx).get("mode") for idx in range(len(c._connection.servernames))]
    if len(set(mode)) != 1 or mode[0] != "single":
        c.switch_mode("single")

    with stop_on_interrupt():
        trigger_box("off")

        go = (
            c.ui.boolean_user_input("\nBackground capture? (skip if not possible) ", default_choice=False)
            if request
            else True
        )

        if go:
            c.start()
            with trigger_single(c):
                c.take_background_image()
            print()
        else:
            c.ui.log("Skipped\n")


def download_quick_preview(
    c: Controller,
    recording_name,
    output_path,
    frame_step: int,
    capture_fps: int,
    requested_camera_ids=None,
    view_cnt=8,
):

    start = time.time()

    path_patterns.joint_preview_folder(c, recording_name, "_previews")
    steps = ProcessingSteps.TINY_UNCALIBRATED
    c.switch_mode("replay")
    trigger_box("off")

    available_recordings = c.get_status(0, verbose=True).get("available_recordings")
    if recording_name not in available_recordings:
        raise ValueError(
            f"Error: Server does not have recording {recording_name}.\n\navailable_recordings: {available_recordings}"
        )
    print("\nPreview ", recording_name, "\n")
    c.set_recording_name(recording_name)

    if requested_camera_ids is None:
        requested_camera_ids = c.system_layout.get_center_cameras() if len(c.servernames) > 10 else None
    else:
        view_cnt = max(len(requested_camera_ids), view_cnt)

    c.set_preview(frame_step, capture_fps, view_cnt=view_cnt, output_path=output_path)

    frame_counts = c.check_frame_count()
    sequence_length = min(frame_counts)
    for i in range(0, sequence_length, frame_step):
        print("\n", recording_name, i, "/", sequence_length)
        c.capture_images(
            frame_idx=i,
            images=True,
            steps=steps,
            requested_camera_ids=requested_camera_ids,
            mattes=False,
        )
    end = time.time()
    print(f"preview {c.preview_writer.preview_path} created. Took {end - start}s")
    c.preview_writer.close_writer()

    c.path_structure.use_default_path_patterns()


def clip_value(value: float, min_value: float = None, max_value: float = None):
    """
    Clamp a numeric value to optional minimum and maximum bounds.

    Parameters:
        value (float):
            The numeric value to validate and clamp.

        min_value (float, optional):
            The lower bound. If provided, any value below this
            limit will be replaced with min_value.
            Defaults to None meaning no lower bound.

        max_value (float, optional):
            The upper bound. If provided, any value above this
            limit will be replaced with max_value.
            Defaults to None meaning no upper bound.

    Returns:
        float or None:
            The clamped value if input is valid or None if the
            provided value is None.
    """

    # If value itself is None, return None directly
    if value is None:
        return None

    # Apply minimum bound if defined
    if min_value is not None and value < min_value:
        return min_value

    # Apply maximum bound if defined
    if max_value is not None and value > max_value:
        return max_value

    # Value is already within bounds
    return value
