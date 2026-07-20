import time
from pathlib import Path

import controller.args as arguments
from controller import Controller, PreviewWriter, stop_on_interrupt, trigger_box
from controller.args.util import (
    CLI_GROUP_IMAGE_TRIGGER,
    CliArg,
    ScriptArgumentField,
)
from web_app_integration.script_runner import ScriptRunner


class RingBufferArgs(arguments.server_list_arg(default=None), arguments.ExposureArg):
    fps: int | None = ScriptArgumentField(
        default=None,
        description="Set Trigger fps for ring buffer. Default here: 25",
        cli=CliArg(option_strings=["--fps"], group=CLI_GROUP_IMAGE_TRIGGER, nargs="?", const=25),
    )
    # description = "peek into a running ring_buffer mode without interfering with it."


class RingBuffer(ScriptRunner):
    def _get_args_pydantic_model(self) -> type:
        return RingBufferArgs

    def main(self, args: RingBufferArgs) -> None:
        with Controller(args.server, log_level="DEBUG", mode="observer") as c:

            statuus = c.get_status()
            modes = [s.get("mode") for s in statuus]
            if all(m == "ring_buffer" for m in modes):
                self.ui.log("ring_buffer is already running. Grabbing image...")
                frame_counts = [s.get("frame_count") for s in statuus]
                max_f = max(frame_counts)
                min_f = min(frame_counts)
                delta = max_f - min_f
                if max_f == -1:
                    self.ui.log("ring buffer on frame -1")
                    return
                self.ui.log(f"frame_count [{min_f}, {max_f}] delta: {delta}")
                if delta > 2:
                    self.ui.log("frame_count mismatch", list(zip(frame_counts, c.servernames, strict=True)))

                image_entires = c.capture_images(frame_idx=min_f, mattes=True)

                p = Path("visuals/rb/ring_buffer_peek.jpg")
                image_grid, _ = PreviewWriter.save_image_grid(image_entires, p)

                self.ui.write_pil_image(image_grid, "./ring_buffer.jpg", "Ring Buffer Peek", event_slot="Image Grid")
                self.ui.log(f"Saved to  --> {p}")
            else:
                self.ui.log("ring_buffer is not running. Attempting to start...")
                c.switch_mode("ring_buffer")
                try:
                    c.check_calibration_file_sync()
                    exposure_profile = args.exposure_settings
                    c.set_exposure_and_gain(exposure_profile.exposure, exposure_profile.gain)
                    time.sleep(0.5)
                    c.start()
                    self.ui.log(f"Setting fps to {args.fps}")
                    trigger_box(f"set_fps_{args.fps}")
                    trigger_box("on")
                    c.wait_ring_buffer_ready()
                    self.ui.boolean_user_input("Start capture", default_choice=True)
                    self.ui.log("capture...")
                    with stop_on_interrupt():
                        while True:
                            frame_counts = [c.get_status(s).get("frame_count") for s in range(len(c.servernames))]
                            max_f = max(frame_counts)
                            min_f = min(frame_counts)
                            delta = max_f - min_f
                            self.ui.log(f"frame_count [{min_f}, {max_f}] delta: {delta}")
                            if delta > 2:
                                self.ui.log("frame_count mismatch", list(zip(frame_counts, c.servernames, strict=True)))
                            time.sleep(1 / 10)
                    self.ui.log("\ngetting test image...")
                    test = c.capture_images(frame_idx=min(frame_counts), mattes=True)
                    p = "visuals/rb/images.jpg"
                    image_grid, _ = PreviewWriter.save_image_grid(test, p)
                    self.ui.write_pil_image(
                        image_grid, "./ring_buffer.jpg", "Ring Buffer Image", event_slot="Image Grid"
                    )

                finally:
                    c.stop()
                    c.switch_mode("single")


if __name__ == "__main__":
    RingBuffer.run_in_cli()
