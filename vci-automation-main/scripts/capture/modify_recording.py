import argparse

from controller import Controller, argmods, input_modules, recording_helper


def main() -> None:
    parser = argparse.ArgumentParser("Rename a recording")
    parser = argmods.add_server_list_argument(parser)
    # Create the subparser handler
    subparsers = parser.add_subparsers(dest="command", required=True, help="Sub-command to run")

    # --- Setup 'rename' command ---
    rename_parser = subparsers.add_parser("rename", help="Rename a recording")
    rename_parser.add_argument("old_name", type=str, help="Previous name of recording")
    rename_parser.add_argument("new_name", type=str, help="New name for recording")

    # --- Setup 'set-fps' command ---
    fps_parser = subparsers.add_parser("set-fps", help="Set the FPS for a recording")
    argmods.add_capture_name_argument(fps_parser, default=None, resolve_date=False, required=True)
    argmods.add_flexi_range_argument(
        fps_parser,
        "Treats the --capture-name as a series (e.g 'capture' -> capture_001, capture_002 ...). --series downloads every recording from the series. Otherwise: ",
        "--series",
        default=None,
    )
    exclusive_group = fps_parser.add_mutually_exclusive_group(required=True)
    exclusive_group.add_argument(
        "--video",
        "-v",
        type=int,
        default=None,
        help="This recording or series contains videos. Set the fps with which the recording(s) were originaly recored (e.g 20 or 30).",
    )
    exclusive_group.add_argument(
        "--single", action="store_true", help="This recording contains disjointed, single images."
    )
    args = parser.parse_args()

    with Controller(args.server, mode="replay") as c:
        if len(c.servernames) != len(c.system_layout.expected_servers()):
            rename_anyway = input_modules.boolean_user_input(
                f"Not connected to all servers! {len(c.servernames)}/{len(c.system_layout.expected_servers())}. {args.command} anyway? ",
                default_choice=False,
            )
            if not rename_anyway:
                print("abort.")
                exit()

        if args.command == "rename":
            old_name = args.old_name
            new_name = args.new_name

            c.send("RENAME_RECORDING", {"old_name": old_name, "new_name": new_name})
            print(f"Renamed {old_name} -> {new_name}")
        elif args.command == "set-fps":
            rec_name = args.capture_name
            fps = args.video
            r = recording_helper.ReplayOMat(c)
            selected_recordings = r.get_recordings_from_series(rec_name, args.series)

            if len(selected_recordings) == 0:
                print("nothing to rename. exit")
                exit()

            print(f"\nSelected {len(selected_recordings)} recordings:")
            for rec in selected_recordings:
                print(f"   {rec}")
            print(f"FPS = {fps}")
            go = input_modules.boolean_user_input("Setting fps?")
            if go:
                for rec in selected_recordings:
                    c.send("SET_FPS", {"recording_name": rec, "fps": fps})
            else:
                print("Abort")


if __name__ == "__main__":
    main()
