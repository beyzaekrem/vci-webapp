import argparse


def add_auto_trigger_argument(
    parser: argparse.ArgumentParser, action_description="image capture"
):
    """
    Adds the --auto-trigger -a argument flag to the us know if we should start with auto-trigger enabled.
    """
    help_msg = (
        f"Automatically triggers {action_description}, "
        "otherwise triggered via manual console prompt. "
        "You can enable/disable this later."
    )
    parser.add_argument("--auto-trigger", "-a", action="store_true", help=help_msg)


def add_auto_trigger_delay_argument(
    parser: argparse.ArgumentParser, default: int = None, const: int = 5
):
    """
    Adds the --auto-trigger-delay -d argument to specify delay in seconds before auto-triggering.
    The default value is used if the argument is not set, and the const value is used if the argument is provided without a value.
    """
    parser.add_argument(
        "--auto-trigger-delay",
        nargs="?",
        type=int,
        metavar="SECONDS",
        default=default,
        const=const,
        help=f"Enable automatic trigger and set delay between triggers (in seconds). e.g: --auto-trigger-delay (default: {const}) or --auto-trigger-delay 10.",
    )


def add_maximal_trigger_count_argument(
    parser: argparse.ArgumentParser, default: int = None
):
    """
    Adds the --maxcount -m argument to specify the maximal number of automatic triggers.
    """
    parser.add_argument(
        "--maxcount",
        type=int,
        default=default,
        metavar="COUNT",
        help=f"Defines the maximal number of triggers (default: {default}). ",
    )
