import argparse
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from controller import (  # noqa: E402
    Controller,
    ProcessingSteps,
    argmods,
    stop_on_interrupt,
    trigger_box,
)

EXPOSURE = argmods.DEFAULT_EXPOSURE.exposure
GAIN = argmods.DEFAULT_EXPOSURE.gain


def main():
    # parse input
    parser = argparse.ArgumentParser(description="capture in single mode")
    parser.add_argument("-s", "--server", nargs="+", type=int, default=-1)
    args = parser.parse_args()
    if args.server != -1:
        server_list = args.server
    else:
        server_list = list(range(1, 16))

    c = Controller(server_list)
    c.set_exposure_and_gain(EXPOSURE, GAIN)
    camera_id = [id for id in c.all_camera_ids if id[0] == "M"][0]

    image_set = "test_"
    processing_steps = ProcessingSteps.PROCESSED  # Processing_Steps.PROCESSED
    c.set_image_path(f"Capture/Tests/{image_set}")
    c.path_structure.path_patterns[c.path_structure.IMAGE_TYPE.image] = "<output_path>/frames/rgb/<cam_id>_<frame>"
    c.path_structure.path_patterns[c.path_structure.IMAGE_TYPE.matte] = "<output_path>/frames/mask/<cam_id>_<frame>"

    wait_time = 3 * 60

    c.switch_mode("single")
    trigger_box("off")

    # take a warm background image

    trigger_box("single")
    time.sleep(0.5)
    c.start()
    trigger_box("single")
    c.take_background_image()
    c.grab_background_images(steps=processing_steps, requested_camera_ids=[camera_id])

    # c.set_parameter("trigger_source", 2)  # Falling edge
    # c.start()
    # with stop_on_interrupt():
    #     for i in range(3):

    #         print(f"trigger background {i}")
    #         trigger_box("single")
    #         # time.sleep(0.2)
    #         c.take_background_image()
    #         c.writer_context.path_structure.suffix = f"_{i}"
    #         c.grab_background_images(
    #             steps=processing_steps, requested_camera_ids=[camera_id]
    #         )
    #         c.stop()
    #         time.sleep(2)
    #         c.start()

    trigger_box("single")
    time.sleep(0.5)
    c.start()
    # debayer_malvar, debayer_interpolate, debayer_subsample
    with stop_on_interrupt():
        for i in range(5):
            print(f"trigger image {i}")
            trigger_box("single")
            print("trigger sent")
            c.capture_images(
                image_format="jpg",
                steps=processing_steps,
                requested_camera_ids=[camera_id],
                mattes="png",
            )

    time.sleep(0.2)  # wait for last frame to be captured
    c.wait_images_transferred()
    c.stop()

    time.sleep(wait_time)
    c = Controller(server_list)
    c.set_image_path(f"Capture/Tests/{image_set}", Controller.FOLDER_MODE.save)
    c.path_structure.path_patterns[c.path_structure.IMAGE_TYPE.image] = "<output_path>/frames_cold/rgb/<cam_id>_<frame>"
    c.path_structure.path_patterns[c.path_structure.IMAGE_TYPE.matte] = (
        "<output_path>/frames_cold/mask/<cam_id>_<frame>"
    )
    c.start()
    with stop_on_interrupt():
        for i in range(5):
            print(f"trigger image {i}")
            trigger_box("single")
            print("trigger sent")
            c.capture_images(
                image_format="jpg",
                steps=processing_steps,
                requested_camera_ids=[camera_id],
                mattes="png",
            )

    time.sleep(0.2)  # wait for last frame to be captured
    c.wait_images_transferred()
    c.stop()

    time.sleep(wait_time)

    c = Controller(server_list)
    c.set_image_path(f"Capture/Tests/{image_set}", Controller.FOLDER_MODE.save)
    c.path_structure.path_patterns[c.path_structure.IMAGE_TYPE.image] = "<output_path>/frames_warm/rgb/<cam_id>_<frame>"
    c.path_structure.path_patterns[c.path_structure.IMAGE_TYPE.matte] = (
        "<output_path>/frames_warm/mask/<cam_id>_<frame>"
    )
    trigger_box("single")
    time.sleep(0.5)
    c.start()
    with stop_on_interrupt():
        for i in range(5):
            print(f"trigger image {i}")
            trigger_box("single")
            print("trigger sent")
            c.capture_images(
                image_format="jpg",
                steps=processing_steps,
                requested_camera_ids=[camera_id],
                mattes="png",
            )

    time.sleep(0.2)  # wait for last frame to be captured
    c.wait_images_transferred()
    c.stop()


if __name__ == "__main__":
    main()
