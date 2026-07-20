import argparse


def add_server_list_argument(parser: argparse.ArgumentParser):
    """Adds the --server [-s] argument to the given ArgumentParser."""
    parser.add_argument(
        "--server",
        "-s",
        nargs="+",
        type=int,
        default=None,
        help="Specify the server IDs to connect to. Use -1 for all servers (default).",
    )
    return parser
