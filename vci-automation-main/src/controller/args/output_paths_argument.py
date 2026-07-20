import json
import os
from pathlib import Path

from pydantic import BaseModel, field_validator

from controller.output_writers import FolderMode

from .util import CLI_GROUP_OUTPUT_CONTROL, ArgMode, CliArg, ScriptArgumentField

PRESET_FILE_PATH = Path("config/output_presets.json")


def load_output_presets() -> dict[str, str]:
    """Loads output path presets from the JSON config file."""
    if PRESET_FILE_PATH.exists():
        with open(PRESET_FILE_PATH) as f:
            raw_presets = json.load(f)
            return {key.upper(): value for key, value in raw_presets.items()}
    return {
        "TEST": "Capture/Tests/",
        "CAPTURE": "Capture/",
        "CALIB": "Calibration/",
    }


OUTPUT_PRESETS = load_output_presets()


def output_folder_type(value: str | Path) -> Path:
    """
    Convert a preset key or literal path into an absolute output folder path.
    Uppercase first path segments are treated as preset names.
    """
    value = str(value)
    if os.sep in value:
        parts = value.split(os.sep, 1)
    elif "/" in value:
        parts = value.split("/", 1)
    else:
        parts = [value]

    preset_candidate = parts[0]
    subpath = parts[1] if len(parts) > 1 else None

    if preset_candidate in OUTPUT_PRESETS:
        final_path = Path(OUTPUT_PRESETS[preset_candidate])
        if subpath:
            final_path = final_path / subpath
    elif preset_candidate.upper() == preset_candidate and preset_candidate != "":
        raise ValueError(
            f"Unknown path preset {preset_candidate!r}. Please add it to output_presets.json or refrain from using "
            "all upper case if you did not intend to call for a preset."
        )
    else:
        final_path = Path(value)

    if not final_path.is_absolute():
        final_path = Path.cwd() / final_path
    if not str(final_path).endswith(os.sep):
        final_path = final_path / ""
    return final_path


def folder_mode_type(value: str | FolderMode) -> FolderMode:
    if isinstance(value, FolderMode):
        return value

    key = value.lower()
    try:
        return next(member for member in FolderMode if member.name.lower() == key)
    except StopIteration as exc:
        valid_choices = ", ".join(member.name.lower() for member in FolderMode)
        raise ValueError(f"Invalid folder mode: {value!r}. Must be one of: {valid_choices}") from exc


def output_folder_arg(
    default: str | None = "TEST",
    *,
    required: bool = False,
    group: str = CLI_GROUP_OUTPUT_CONTROL,
    arg_mode: dict[str, ArgMode] | None = None,
):
    if default is not None:
        output_folder_type(default)

    preset_choices = OUTPUT_PRESETS.keys()
    help_msg = (
        "The path to the output directory. Can be an UPPERCASE predefined preset "
        "(e.g., 'TEST') or a custom path (e.g., 'home/images'). "
        "You may append a subdirectory to a preset (e.g., 'TEST/motions'). "
        f"Available presets: {', '.join(preset_choices)}."
    )

    class OutputFolderArgMixin(BaseModel):
        outputfolder: str | None = ScriptArgumentField(
            default=... if required else default,
            description=help_msg,
            cli=CliArg(option_strings=["--outputfolder", "-o"], group=group, metavar="OUTPUT_FOLDER"),
            arg_mode=arg_mode,
        )

        @field_validator("outputfolder", mode="before")
        @classmethod
        def validate_outputfolder(cls, value: str | Path | None) -> str | None:
            if value is None:
                if required:
                    raise ValueError("Output folder is required.")
                return value
            output_folder_type(value)
            return str(value)

        @property
        def output_folder_path(self) -> Path | None:
            if self.outputfolder is None:
                return None
            return output_folder_type(self.outputfolder)

    return OutputFolderArgMixin


def folder_mode_arg(
    default: str | None = "append",
    *,
    required: bool = False,
    group: str = CLI_GROUP_OUTPUT_CONTROL,
):
    choices = [member.name.lower() for member in FolderMode]
    if default is not None and default not in choices:
        raise ValueError(f"Default key {default} is invalid for folder_mode. Options: {', '.join(choices)}")

    help_msg = (
        "Controls how the target output folder is handled. "
        f"Options are: {', '.join(choices)}. "
        "clear deletes all existing content before saving, append avoids overwriting existing images via frame "
        "offset for new images, and save overwrites existing files with the same name."
    )

    class FolderModeArgMixin(BaseModel):
        folder_mode: str | None = ScriptArgumentField(
            default=... if required else default,
            description=help_msg,
            json_schema_extra={
                "enum": choices,
            },
            cli=CliArg(option_strings=["--folder-mode"], group=group),
        )

        @field_validator("folder_mode", mode="before")
        @classmethod
        def validate_folder_mode(cls, value: str | FolderMode | None) -> str | None:
            if value is None:
                if required:
                    raise ValueError("Folder mode is required.")
                return value
            return folder_mode_type(value).name.lower()

        @property
        def folder_mode_setting(self) -> FolderMode | None:
            if self.folder_mode is None:
                return None
            return folder_mode_type(self.folder_mode)

    return FolderModeArgMixin
