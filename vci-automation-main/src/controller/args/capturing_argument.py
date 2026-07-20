from pydantic import BaseModel

from .util import CLI_GROUP_IMAGE_TRIGGER, CliArg, ScriptArgumentField


def fps_arg(default: int = 25, *, group: str = CLI_GROUP_IMAGE_TRIGGER):
    description = f"Specify the frames per second for video recording (default: {default})."

    class FPSArgMixin(BaseModel):
        fps: int = ScriptArgumentField(
            default=default,
            description=description,
            cli=CliArg(option_strings=["--fps", "-f"], group=group, metavar="FPS"),
        )

    return FPSArgMixin


def max_recording_time_arg(default: int | None = None, *, group: str = CLI_GROUP_IMAGE_TRIGGER):
    description = "Defines the maximum recording time in seconds."

    class MaxRecordingTimeArgMixin(BaseModel):
        time: int | None = ScriptArgumentField(
            default=default,
            description=description,
            cli=CliArg(group=group, metavar="SECONDS"),
        )

    return MaxRecordingTimeArgMixin
