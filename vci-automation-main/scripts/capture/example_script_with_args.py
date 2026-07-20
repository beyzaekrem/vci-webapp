import controller.args as arguments
from web_app_integration.script_runner import ScriptRunner


class CaptureArgs(
    arguments.ExposureArg,
    arguments.max_recording_time_arg(7),
    arguments.fps_arg(25),
    arguments.quality_arg("avif_ll", required=True),
    arguments.processing_steps_arg("processed"),
    arguments.cameras_arg("ALL", short_name="-c"),
    arguments.capture_name_arg(),
    arguments.series_flag_arg(),
    arguments.output_folder_arg("TEST"),
    arguments.folder_mode_arg("append"),
    arguments.FlexiRangeArgMixinFrames,
):
    pass


class CaptureArgsExampleScript(ScriptRunner):
    def _get_args_pydantic_model(self) -> type:
        return CaptureArgs

    def main(self, args: CaptureArgs) -> None:
        self.ui.log(str(args))
        self.ui.log(str(args.exposure))  # exposure string key, e.g. "default", "fast"
        self.ui.log(str(args.exposure_settings))  # ExposureSettings object with exposure, gain, illumination, name

        self.ui.log(str(args.time))
        self.ui.log(str(args.fps))

        # example on how to deal with flexi range arguments:
        self.ui.log(str(args.frames))  # e.g. "1:5"
        self.ui.log(str(args.frames_selection))  # format (start, end, step), e.g. (1, 5, 1) or multiple selections
        self.ui.log(str(list(args.frames_selection.resolve_indices(10))))

        # other arguments
        self.ui.log(str(args.quality))
        self.ui.log(str(args.quality_settings))
        self.ui.log(str(args.processing))
        self.ui.log(str(args.processing_steps))
        self.ui.log(str(args.cams))
        self.ui.log(str(args.capture_name))
        self.ui.log(str(args.series))
        self.ui.log(str(args.outputfolder))
        self.ui.log(str(args.output_folder_path))
        self.ui.log(str(args.folder_mode))
        self.ui.log(str(args.folder_mode_setting))

        # we get the json schema for free
        schema = CaptureArgs.model_json_schema()
        self.ui.log(f"JSON schema fields: {', '.join(schema.get('properties', {}).keys())}")


if __name__ == "__main__":
    CaptureArgsExampleScript.run_in_cli()
