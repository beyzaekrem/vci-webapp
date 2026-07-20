from typing import Any

from pydantic import Field
from pydantic.fields import FieldInfo

from .arg_modes import ArgMode, ArgModes

CLI_GROUP_CONNECTION = "Connection"
CLI_GROUP_CAPTURE_SELECTION = "Capture Selection"
CLI_GROUP_FRAME_SELECTION = "Frame Selection"
CLI_GROUP_IMAGE_CONFIGURATION = "Image Configuration"
CLI_GROUP_IMAGE_TRIGGER = "Image Trigger"
CLI_GROUP_OUTPUT_CONTROL = "Output Control"


class CliArg:
    """
    Metadata for defining how a pydantic model field should be parsed
    from the command line using argparse.
    """

    def __init__(
        self,
        option_strings: list[str] | None = None,
        group: str | None = None,
        nargs: str | None = None,
        metavar: str | None = None,
        const: Any | None = None,
    ):
        self.option_strings = option_strings
        self.group = group
        self.nargs = nargs
        self.metavar = metavar
        self.const = const


def ScriptArgumentField(
    default: Any = ...,
    *,
    cli: CliArg | None = None,
    arg_mode: ArgModes | dict[str, ArgMode] | None = None,
    **field_kwargs: Any,
) -> Any:
    """
    Define a pydantic Field with additional metadata for our scripting system,
    including custom CLI parsing and arg modes.
    """
    field: FieldInfo = Field(default, **field_kwargs)

    if cli is not None:
        field.metadata.append(cli)
    if arg_mode is not None:
        field.metadata.append(ArgModes(arg_mode))
    return field


def get_cli_arg(field: FieldInfo) -> CliArg | None:
    """
    Get the CliArg metadata from a pydantic FieldInfo, if it exists.
    """
    cli_arg = None
    for meta in field.metadata:
        if isinstance(meta, CliArg):
            cli_arg = meta
            break
    return cli_arg
