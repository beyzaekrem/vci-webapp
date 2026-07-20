# utils.py or config.py
import argparse
from datetime import datetime

# Define the keyword to be used for date substitution
DATE_KEYWORD = "DATE"


def get_current_date_string():
    """Returns the date string in the desired format for subfolders."""
    return datetime.now().strftime("%Y_%m_%d")


def _capture_name_type(value: str) -> str:
    # substitues DATE with the current date
    if DATE_KEYWORD in value:
        date_str = get_current_date_string()
        value = value.replace(DATE_KEYWORD, date_str)
    return value


def add_capture_name_argument(
    parser: argparse.ArgumentParser,
    default: str = DATE_KEYWORD + "_capture",
    *,
    resolve_date: bool = True,
    required: bool = False,
):
    """
    Adds the --capture-name [-n] argument for the final subfolder name.

    Args:
        parser: The ArgumentParser object.
        default_name: The default name to use if none is provided. Can contain DATE.
    """

    help_msg = (
        f"The name of the capture (e.g., 'DATE_capture_001'). "
        f"When saving images, a subfolder of this name will be created in the outputfolder. "
        f"The optional keyword {DATE_KEYWORD} will be substituded with the current date ({get_current_date_string()})."
    )

    if default and not required:
        help_msg += f" Default here: '{default}'"

    parser.add_argument(
        "--capture-name",
        "-n",
        type=_capture_name_type if resolve_date else str,
        default=default,
        help=help_msg,
        required=required,
    )
    return parser


def add_series_flag_arugment(parser: argparse.ArgumentParser):
    """
    Adds the --series argument flag to let us know if the capture_name refers to a series or a single capture.
    """
    parser.add_argument(
        "--series",
        action="store_true",
        help="The given capture-name refers to an image series and should be treated as such.",
    )
    return parser
