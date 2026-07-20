import controller.args as arguments
from controller import Controller
from controller.args.util import CliArg, ScriptArgumentField
from web_app_integration.script_runner import ScriptRunner


class SetActiveCamerasArgs(arguments.server_list_arg(default=None)):
    mono: bool = arguments.ScriptFlagField(
        description="Controls if mono cameras are opened", option_strings=["-m", "--mono"], group="Camera Control"
    )
    exclude: list[str] = ScriptArgumentField(
        description="list of camera ids that should NOT be openend (space-separated list)",
        default=[],
        cli=CliArg(group="Camera Control"),
    )
    disabled_cameras: list[str] = ScriptArgumentField(
        description="cameras that are disabled due hardware issues",
        default=[
            "C0040",
            "M0004",
            "M0020",
        ],
        cli=CliArg(group="Camera Control"),
    )


class SetActiveCameras(ScriptRunner):
    "Set which cameras should be opened by the servers."

    "The servers need to be reset for the change to take effect."

    def _get_args_pydantic_model(self) -> type:
        return SetActiveCamerasArgs

    def main(self, args: SetActiveCamerasArgs) -> None:
        self.ui.log()
        self.ui.log(f"Mono Enabled: {args.mono}")
        self.ui.log(f"Cameras to Exclude: {args.exclude}")

        with Controller(args.server, user_interface=self.ui) as c:
            color_only = not args.mono
            c.set_ignore_cameras(color_only, None)

            # M0020 vci-08 doesn't react to hardware trigger (waits in capture_next).
            # Works with software trigger.
            # Different Power/Trigger cable in same port on the rig did not fix the issue.
            # Switching Power/Trigger cable with a working camera on the rig (also switching port) did not fix the issue.
            # -> camera might be broken

            # C0040 vci-13 No Image Data. Doesn't work in xiCamTool either.
            # xiCamTool outputs:
            # xiApi: GetImage Warning lost frame skipped. PCIeWaitForEvent: Warning frame lost reported, but no buffer was lost (e.g. due to calling AcqAbort))
            # Doesn't work with different data cable either.
            # firmware reset didnt solve the issue
            # -> camera might be broken

            # M0004 vci-10 delivers a few images in xiCamTool then stops (waits in capture_next)
            # xiApi: Get Image warning: timeout - waiting for image 2000ms
            # firmware reset didnt solve the issue
            # Does it work with software trigger?

            # missing:
            # rig of vci-09
            selected = args.exclude + args.disabled_cameras
            c.set_ignore_cameras(color_only, selected)

            reset = self.ui.boolean_user_input("\n Reset servers?", default_choice=False)
            if reset:
                c.hard_reset()
            else:
                self.ui.log("no reset.")


if __name__ == "__main__":
    SetActiveCameras.run_in_cli()
