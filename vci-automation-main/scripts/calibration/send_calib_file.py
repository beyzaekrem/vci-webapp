# ruff: noqa: T201, INP001

import argparse
import json
import sys
from pathlib import Path

from controller import Controller, argmods, boolean_user_input


def main() -> None:
    parser = argparse.ArgumentParser(
        description="send a calibration dome file to servers or delete the calibration from servers"
    )
    parser = argmods.add_server_list_argument(parser)
    calib_file_group = parser.add_mutually_exclusive_group(required=True)
    calib_file_group.add_argument(
        "--file",
        type=str,
        nargs="?",
        default=None,
        const="output/calibration_dome.json",
        help="path to the calibration file to be send.",
    )
    calib_file_group.add_argument(
        "--origin",
        type=int,
        help="Server ID to pull calibration from",
    )
    calib_file_group.add_argument(
        "--delete",
        action="store_true",
        help="delete the calibration info from the servers",
    )
    args = parser.parse_args()
    server_list = args.server
    calib_path = args.file
    origin_server = args.origin

    with Controller(server_list) as c:

        if args.delete:
            go = boolean_user_input(
                "Are you sure you want to delete calibration_dome from the servers?",
                default_choice=False,
            )
            if go:
                d = {"timestamp": "wiped", "meta": "wiped", "cameras": []}
                c.set_raw_calibration(d)
                c.check_calibration_file_sync()
            else:
                print("aborting")
                sys.exit()
        else:
            if calib_path is not None:
                with Path.open(calib_path) as f:
                    d = json.load(f)
            else:
                d = c.get_raw_calibration(origin_server)
            go = boolean_user_input(f"Send calib file {calib_path} with timestamp {d.get('timestamp')} to servers?")
            if go:
                c.set_raw_calibration(d)
                c.check_calibration_file_sync()


if __name__ == "__main__":
    main()
