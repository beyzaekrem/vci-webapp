import argparse


def add_fps_argument(parser: argparse.ArgumentParser, default: int = 25):
    """
    Adds the --fps -f argument to specify frames per second for video recording.
    """
    parser.add_argument(
        "-f",
        "--fps",
        type=int,
        default=default,
        help=f"Specify the frames per second for video recording (default: {default}).",
    )


def add_max_recording_time_argument(
    parser: argparse.ArgumentParser, default: int = None
):

    parser.add_argument(
        "--time",
        type=int,
        default=None,
        metavar="SECONDS",
        help=f"Defines the maximum recording time in seconds (default: {default}). ",
    )
