# ruff: noqa: T201, INP001

import argparse
from pathlib import Path

from controller import (
    Controller,
    ImageEntry,
    PreviewWriter,
    ProcessingSteps,
    argmods,
    input_modules,
    trigger_box,
)
from pathlib import Path
from typing import Literal

import controller.args as arguments
from controller import (
    Controller,
    PreviewWriter,
    ProcessingSteps,
    ServerDesyncError,
    TriggerBoxError,
    trigger_box,
    trigger_single,
)
from controller.args.util import (
    CLI_GROUP_IMAGE_CONFIGURATION,
    CLI_GROUP_OUTPUT_CONTROL,
    ArgMode,
    CliArg,
    ScriptArgumentField,
)
from web_app_integration.script_runner import ScriptRunner


class TakeBackgroundImagesArgs(arguments.server_list_arg(default=None), arguments.ExposureArg):
    pass


class TakeBackgroundImages(ScriptRunner):

    desciption = "Take background images"

    def _get_args_pydantic_model(self) -> type:
        return TakeBackgroundImagesArgs

    def main(self, args: TakeBackgroundImagesArgs) -> None:
        exposure_profile: arguments.ExposureSettings = args.exposure_settings

        with Controller(args.server, mode="single", user_interface=self.ui) as c:
            c.set_depth_active("COLOR")
            c.set_exposure_and_gain(exposure_profile.exposure, exposure_profile.gain)
            self.ui.log(f"Selected {exposure_profile}")

            input_modules.ask_for_new_background(c, request=False)

            self.ui.log("grabbing new background images for review...")
            image_entires: list[ImageEntry] = c.grab_background_images(
                steps=ProcessingSteps.TINY, quality=argmods.HIGH_QUALITY_PNG.quality
            )
            p = Path("visuals/Background.jpg")
            image_grid, _ = PreviewWriter.create_image_grid(image_entires, "Background")
            self.ui.write_pil_image(image_grid, p, "new Background", "Backgrounds")

            self.ui.log(f"Combined background image   ------>  {p}")
            self.ui.log("Done")


if __name__ == "__main__":
    TakeBackgroundImages.run_in_cli()
