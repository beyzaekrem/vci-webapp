import controller.args as arguments
from controller import Controller
from controller.args.util import (
    CLI_GROUP_IMAGE_CONFIGURATION,
)
from web_app_integration.script_runner import ScriptRunner


class SetExposureArgs(arguments.server_list_arg(default=None), arguments.ExposureArg):
    force: bool = arguments.ScriptFlagField(
        description="!caution! Ignore ControlTakenError to force exposure/gain change. Only use this setting if you are sure.",
        group=CLI_GROUP_IMAGE_CONFIGURATION,
    )


class SetExposureAndGain(ScriptRunner):
    def _get_args_pydantic_model(self) -> type:
        return SetExposureArgs

    def main(self, args: SetExposureArgs) -> None:
        c = Controller(args.server, mode="observer")
        c.take_control(force=args.force)

        exposure_profile: arguments.ExposureSettings = args.exposure_settings
        c.set_exposure_and_gain(exposure_profile.exposure, exposure_profile.gain)
        self.ui.log(f"\nApplied: {exposure_profile}\n\n")


if __name__ == "__main__":
    SetExposureAndGain.run_in_cli()
