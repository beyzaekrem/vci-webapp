# ruff: noqa: T201, INP001
import argparse

from controller.trigger_box_connection import trigger_box, trigger_box_new

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Send a command to the trigger box server")
    parser.add_argument("command", help="commands: single, on, off, set_fps_X", nargs="+")
    args = parser.parse_args()
    for command in args.command:
        print(command, "response:", trigger_box(command))
        print(command, "response:", trigger_box_new(command))
