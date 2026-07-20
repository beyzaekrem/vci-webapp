import argparse
import json
import os
from pathlib import Path

from controller.output_writers import FolderMode

# --- User Configuration ---
PRESET_FILE_PATH = Path("config/output_presets.json")


def load_output_presets() -> dict[str, str]:
    """Loads presets from the JSON file."""
    if PRESET_FILE_PATH.exists():
        with open(PRESET_FILE_PATH) as f:
            # Preset keys should be upper case
            raw_presets = json.load(f)
            return {k.upper(): v for k, v in raw_presets.items()}
    else:
        # Return a fallback or raise an error if the file is mandatory
        # print("didnt find output_presets.json")
        return {
            "TEST": "Capture/Tests/",
            "CAPTURE": "Capture/",
            "CALIB": "Calibration/",
        }


OUTPUT_PRESETS = load_output_presets()


def output_folder_type(value: str) -> Path:
    """
    argparse type function that converts input to an absolute Path object.
    Accepts an Upper case preset key (defined in output_presets.json) with an optional subpath or a literal path.
    """
    # Split the input value (e.g., "TEST/myfolder" -> ["TEST", "myfolder"])
    if os.sep in value:
        parts = value.split(os.sep, 1)
    elif "/" in value:
        parts = value.split("/", 1)
    else:
        parts = [value]

    preset_candidate = parts[0]  # Keep case as provided by user for initial check
    subpath = parts[1] if len(parts) > 1 else None

    if preset_candidate in OUTPUT_PRESETS:
        preset_path = Path(OUTPUT_PRESETS[preset_candidate])

        if subpath:
            final_path = preset_path / subpath
        else:
            final_path = preset_path
    elif preset_candidate.upper() == preset_candidate and preset_candidate != "":
        # the first part of the path is fully uppercase, however is is not a known preset path.
        raise argparse.ArgumentTypeError(
            f"Unknown path preset '{preset_candidate}'. Please add it to output_presets.json or refrain from using all upper case if you did not intend to call for a preset."
        )
    else:
        # The user wrote "test/myfolder" or "images/test"
        final_path = Path(value)

    # ... (Rest of path finalization logic: is_absolute, trailing separator) ...
    if not final_path.is_absolute():
        final_path = Path.cwd() / final_path
    if not str(final_path).endswith(os.sep):
        final_path = final_path / ""
    return final_path


def add_output_folder_argument(
    parser: argparse.ArgumentParser,
    default: str = "TEST",
    *,
    required: bool = False,
):
    """
    Adds the --outputfolder [-o] argument which accepts a preset key or a custom path.
    """
    # Use the lowercase keys from the map for help text
    preset_choices = OUTPUT_PRESETS.keys()

    help_msg = (
        f"The path to the output directory. Can be an **UPPERCASE predefined preset** "
        f"(e.g., 'TEST') or a **custom path** (e.g., 'home/images'). "
        f"You may append a subdirectory to a preset (e.g., 'TEST/motions'). "
        f"Available presets: **{', '.join(preset_choices)}**."
    )
    if default:
        help_msg += f" Default here: '{default}'."

    parser.add_argument(
        "--outputfolder",
        "-o",
        type=output_folder_type,  # The core logic
        default=default,
        help=help_msg,
        required=required,
    )
    return parser


# The Refined Type Function
def folder_mode_type(value: str) -> FolderMode:
    """
    Custom argparse type function to look up the FolderMode Enum member by name,
    performing a case-insensitive check and returning the Enum member.
    """
    key = value.lower()

    try:
        # finds the matching FolderMode
        return next(member for member in FolderMode if member.name.lower() == key)
    except StopIteration:
        valid_choices = ", ".join([member.name.lower() for member in FolderMode])
        raise argparse.ArgumentTypeError(f"Invalid folder mode: '{value}'. Must be one of: {valid_choices}")


def add_folder_mode_argument(
    parser: argparse.ArgumentParser,
    default: str = "append",
    *,
    required: bool = False,
):
    """
    Adds the --folder-mode argument which controls how the output folder is treated.

    Args:
        parser: The ArgumentParser object.
        default: The default mode name (e.g., 'append', 'clear', 'overwrite').
        required: If True, the argument must be supplied by the user.
    """
    choices = [member.name.lower() for member in FolderMode]

    # Ensure default is valid and lowercase for the help message
    if default not in choices:
        raise ValueError(f"Default key {default} is invalid for folder_mode. Options: {', '.join(choices)}")

    help_msg = (
        f"Controls how the target output folder is handled. "
        f"Options are: **{', '.join(choices)}**."
        f"**clear** (deletes all existing content before saving), "
        f"**append** (avoid overwriting existing images via frame offset for new images), "
        f"**save** (saves blindly; overwrites existing files with the same name)."
    )

    if default:
        help_msg += f" Default here: '{default}'."

    parser.add_argument(
        "--folder-mode",
        type=folder_mode_type,
        default=default,  # Pass the string default
        help=help_msg,
        required=required,
    )
    return parser
