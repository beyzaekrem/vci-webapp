import argparse

from controller import Controller, argmods


def main():
    parser = argparse.ArgumentParser(description="recompile and restart servers")
    parser = argmods.add_server_list_argument(parser)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    c = Controller(args.server, mode="observer")

    c.take_control(force=args.force)
    print("stopping running tasks...")
    # c.stop()
    print("reseting...")
    c.hard_reset()


if __name__ == "__main__":
    main()
