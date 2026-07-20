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

DEFAULT_PROCESSING_STEPS = [
    ProcessingSteps.TINY,
    ProcessingSteps.TINY_UNCALIBRATED,
    ProcessingSteps.OVERWRITE_NO_ROTATION(ProcessingSteps.TINY_UNCALIBRATED),
]

grid_path = Path("visuals/ConnectionTest.jpg")


class ConnectionTestArgs(
    arguments.server_list_arg(default=None),
    arguments.output_folder_arg(default="TEST", arg_mode={"web": ArgMode(default=None, fixed=True, hidden=True)}),
    arguments.capture_name_arg(
        default="connection_test", arg_mode={"web": ArgMode(default=None, fixed=True, hidden=True)}
    ),
    arguments.quality_arg(default="jpg"),
    arguments.processing_steps_arg(default="tiny"),
    arguments.cameras_arg(default=None),
    arguments.ExposureArg,
):
    log_level: Literal["debug", "info", "error"] = ScriptArgumentField(
        default="info",
        description="Logging verbosity.",
        cli=CliArg(
            group="General",
            option_strings=["--log-level"],
        ),
    )
    no_image: bool = arguments.ScriptFlagField(
        description="Skip test image capture.", group=CLI_GROUP_IMAGE_CONFIGURATION, option_strings=["--no-image"]
    )
    no_depth: bool = arguments.ScriptFlagField(
        description="Request mono images instead of depth",
        group=CLI_GROUP_OUTPUT_CONTROL,
        option_strings=["--no-depth"],
    )
    no_mattes: bool = arguments.ScriptFlagField(
        description="Skip mattes.",
        group=CLI_GROUP_IMAGE_CONFIGURATION,
        option_strings=["--no-mattes"],
    )
    no_calib: bool = arguments.ScriptFlagField(
        description="Skip calibration data download.",
        group=CLI_GROUP_OUTPUT_CONTROL,
        option_strings=["--no-calib"],
    )


class ConnectionTest(ScriptRunner):

    def _get_args_pydantic_model(self) -> type:
        return ConnectionTestArgs

    def main(self, args: ConnectionTestArgs) -> None:

        # run test
        exposure_profile = args.exposure_settings
        quality = args.quality_settings
        requested_cameras = args.cams

        processing_steps_options = list(DEFAULT_PROCESSING_STEPS)
        if args.processing is not None:
            processing_steps_options.insert(0, args.processing_steps)
        processing_steps = processing_steps_options[0]

        with Controller(args.server, log_level=args.log_level, mode="single", user_interface=self.ui) as c:
            if args.output_folder_path and args.capture_name:
                image_path = str(args.output_folder_path / args.capture_name)
                c.set_image_path(image_path, folder_mode=c.FOLDER_MODE.clear)

            try:
                mode = "COLOR" if args.no_depth else "DEPTH"
                c.set_depth_active(mode)
            except Exception as e:
                log_msg = f"Failed to set depth mode to {mode} for some servers. Error: {e}"
                self.ui.error(log_msg)
            c.set_exposure_and_gain(exposure_profile.exposure, exposure_profile.gain)
            try:
                trigger_box("off")
                software_trigger = False
            except TriggerBoxError:
                software_trigger = True
                c.set_software_trigger(state=software_trigger)

            if not args.no_image:
                self.ui.log("Capturing test image...")
                c.start()

                mattes = not args.no_mattes
                image_entries = None
                for processing_steps in processing_steps_options:
                    try:
                        if not software_trigger:
                            with trigger_single(c):
                                self.ui.log("trigger sent")
                                image_entries = c.capture_images(
                                    requested_camera_ids=requested_cameras,
                                    mattes=mattes,
                                    steps=processing_steps,
                                    image_format=quality.format,  # quality
                                    quality=quality.quality,
                                    mattes_format=quality.mattes_format,
                                    mattes_quality=quality.mattes_quality,
                                )
                        else:
                            msg = "Depth cameras dont support software trigger"
                            raise NotImplementedError(msg)
                        image_grid, _ = PreviewWriter.create_image_grid(
                            image_entries,
                            f"Connection Test {processing_steps}",
                        )
                        p = Path("visuals/ConnectionTest.jpg")
                        self.ui.write_pil_image(
                            image_grid, p, f"Connection Test {processing_steps}", event_slot="Preview Grid"
                        )
                        break
                    except Exception as e:
                        self.ui.error(f"{e}\n   --- processing steps {processing_steps} failed.\n")
                        if "Missing Background" in str(e):
                            mattes = False
                c.stop()

            self.ui.log("\n\n")
            self.ui.log("----    Results    ----")
            if not args.no_calib:
                try:
                    calib = c.grab_calibration_file(processing_steps=processing_steps)
                    self.ui.log(f"calibrations synced :{calib.get('meta')}")
                except ServerDesyncError as e:
                    # for this one I just want the info if it's synced or not
                    self.ui.log(e)
                except RuntimeError as e:
                    # can happen when not calibrated
                    self.ui.log(e)
            c.check_missing()
            self.ui.log("\n")

            self.ui.log("\n")
            if not args.no_image:
                if image_entries is not None:
                    c.image_writer.print_info(len(c.all_camera_ids), len(image_entries))
                    self.ui.log(
                        f"Individual images saved to {c.image_writer.path_structure.get_output_path()}  ---  {processing_steps}"
                    )
                    self.ui.log(f"Captured with {exposure_profile}")
                    self.ui.log(f"     Combined preview image ---> {grid_path} \n")

                else:
                    self.ui.log("Failed to capture images")
            else:
                self.ui.log("Image capture skipped\n")

            if software_trigger:
                self.ui.log("!!!! trigger box was not reachable !!!\n")

            self.ui.log("----------------------")

        # "excused"
        # doesn't react to hardware trigger ---- vci-08 is missing:  ['M0020']      ---      [('M0020', 'pillar_5, rig_low')]
        # rig is missing ---- vci-09 is missing:  ['C', 'M', 'M']      ---      [('C', 'pillar_6, rig_upper'), ('M', 'pillar_6, rig_upper'), ('M', 'pillar_6, rig_upper')]

        # applied firmware flash but didnt fix the issue.
        # delivers a few images then stops ------ vci-10 is missing:  ['M0004']      ---      [('M0004', 'pillar_7, rig_low')]
        # no image data, doesn't work in xiCamTool ----- vci-13 is missing:  ['C0040']      ---      [('C0040', 'pillar_10, rig_upper')]
        # maybe try on another server again now.


if __name__ == "__main__":
    ConnectionTest.run_in_cli()
