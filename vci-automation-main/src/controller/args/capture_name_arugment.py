from datetime import datetime

from pydantic import BaseModel, field_validator

from .util import CLI_GROUP_CAPTURE_SELECTION, ArgMode, CliArg, ScriptArgumentField

DATE_KEYWORD = "DATE"


def get_current_date_string() -> str:
    """Returns the date string used for capture subfolders."""
    return datetime.now().strftime("%Y_%m_%d")


def resolve_capture_name(value: str) -> str:
    if DATE_KEYWORD in value:
        return value.replace(DATE_KEYWORD, get_current_date_string())
    return value


def capture_name_arg(
    default: str | None = DATE_KEYWORD + "_capture",
    *,
    required: bool = False,
    group: str = CLI_GROUP_CAPTURE_SELECTION,
    arg_mode: dict[str, ArgMode] | None = None,
):
    default_value = resolve_capture_name(default) if default is not None else None
    help_msg = (
        "The name of the capture (e.g., 'DATE_capture_001'). "
        "When saving images, a subfolder of this name will be created in the outputfolder. "
        f"The optional keyword {DATE_KEYWORD} will be substituded with the current date ({get_current_date_string()})."
    )

    class CaptureNameArgMixin(BaseModel):
        capture_name: str | None = ScriptArgumentField(
            default=... if required else default_value,
            description=help_msg,
            cli=CliArg(option_strings=["--capture-name", "-n"], group=group, metavar="NAME"),
            arg_mode=arg_mode,
        )

        @field_validator("capture_name", mode="before")
        @classmethod
        def validate_capture_name(cls, value: str | None) -> str | None:
            if value is None:
                if required:
                    raise ValueError("Capture name is required.")
                return value
            return resolve_capture_name(value)

    return CaptureNameArgMixin


def series_flag_arg(default: bool = False, *, group: str = CLI_GROUP_CAPTURE_SELECTION):
    class SeriesFlagArgMixin(BaseModel):
        series: bool = ScriptArgumentField(
            default=default,
            description="The given capture-name refers to an image series and should be treated as such.",
            cli=CliArg(option_strings=["--series"], group=group),
        )

    return SeriesFlagArgMixin
