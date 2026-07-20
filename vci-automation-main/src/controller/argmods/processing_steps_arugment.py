import argparse

from controller.processing_steps import PROCESSING_STEPS_MAP


def _processing_steps_type(value: str) -> list[str]:
    """
    Custom argparse type function to look up a list of processing steps by name
    using a case-insensitive lookup (converts input to lowercase).
    """
    # *** Convert input to lowercase for lookup ***
    key = value.lower()

    if key in PROCESSING_STEPS_MAP:
        return PROCESSING_STEPS_MAP[key]

    # Use the lowercase keys for the error message
    valid_choices = ", ".join(PROCESSING_STEPS_MAP.keys())
    raise argparse.ArgumentTypeError(f"Invalid processing step preset: '{value}'. Must be one of: {valid_choices}")


def add_processing_steps_argument(
    parser: argparse.ArgumentParser,
    default: str = "processed",
    *,
    required: bool = False,
):
    """
    Adds the --processing argument to the given argparse.ArgumentParser.

    The resulting processed variable is of type list[str].

    """
    # Use the lowercase keys from the map for help text
    choices = list(PROCESSING_STEPS_MAP.keys())

    # The default key should also be lowercase for the argparse default
    default_arg_value = default.lower() if default else None

    # Adjust required status
    if default_arg_value is not None:
        if default_arg_value not in choices:
            raise ValueError(
                f"Default value {default_arg_value} is not a valid image processing preset. "
                f"Valid presets: {choices}"
            )
        required = False

    help_msg = f"Select a predefined list of image processing steps. " f"Available options: **{', '.join(choices)}**."
    if default_arg_value is not None:
        help_msg += f" Default here: '{default_arg_value}'."

    parser.add_argument(
        "--processing",
        type=_processing_steps_type,
        default=default_arg_value,  # Set default as lowercase string
        required=required,
        help=help_msg,
    )
    return parser
