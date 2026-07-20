import time

import matplotlib.pyplot as plt

import controller.args as arguments
from controller.args.util import ArgMode, ScriptArgumentField
from web_app_integration.script_runner import ScriptRunner


class AwesomeTestArgs(arguments.ExposureArg, arguments.max_recording_time_arg(7), arguments.fps_arg(25)):
    flag: bool = ScriptArgumentField(
        default=False,
        description="Example boolean argument without a mixin.",
        arg_mode={
            "web": ArgMode(default=True, fixed=True),
            "cli": ArgMode(default=False, fixed=True),
        },
    )


class AwesomeTestScript(ScriptRunner):
    def _get_args_pydantic_model(self) -> type:
        return AwesomeTestArgs

    def main(self, args: AwesomeTestArgs) -> None:
        self.ui.log(f"Starting execution with exposure: {args.exposure}")
        self.ui.log("log log log")
        self.ui.log(f"Max recording time: {args.time} seconds")
        self.ui.log(f"FPS: {args.fps}")
        self.ui.log(f"Exposure settings: {args.exposure_settings}", event_slot="exposure_logging")

        name, timeout = self.ui.timeout_input(
            "What is your name?",
            "I will choose a name for you soon...",
            timeout_return="Speedy",
            timeout_seconds=5,
            auto_trigger_enabled=True,
        )
        self.ui.log(f"Hello {name}, nice to meet you! Starting capture setup...")

        if args.flag:
            self.ui.log("flag activated.")

        for i in range(3):
            # This blocks until a click in the WebApp OR 'y/n' in Terminal
            go = self.ui.boolean_user_input(
                f"Do you want to trigger a capture? ({i+1}/3)", event_slot="capture_confirmation"
            )

            if go:
                self.ui.log("User Selected YES - Capturing...")
                time.sleep(1)  # simulate capture delay
                # push an image to a pre-defined slot
                # self.display_image("Raw Frame", some_numpy_array)
            else:
                self.ui.log("User Selected NO - Skipping.")

        # example diagram
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3], [1, 4, 9])
        ax.set_title("Example Plot")
        self.ui.write_matplotlib_figure(fig, "./plot.png", caption="This is an example plot.", event_slot="Plot")

        raise ValueError("This is an example error to show error handling in the UI.")


if __name__ == "__main__":
    # Local CLI execution
    AwesomeTestScript.run_in_cli()
