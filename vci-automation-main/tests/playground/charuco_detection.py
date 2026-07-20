import argparse

from controller import Controller, argmods, stop_on_interrupt
from controller.charuco_detection_omat import CaptureDetectionOMat


def main() -> None:
    parser = argparse.ArgumentParser(description="test charuco detection")
    parser = argmods.add_server_list_argument(parser)
    parser = argmods.add_exposure_argument(parser, default="low_light")
    args = parser.parse_args()
    server_list = args.server
    exposure: argmods.ExposureSettings = args.exposure

    camera_ids = [
        "C0007",
        "C0018",
        "C0038",
        "C0025",
        "C1005",
        "M0005",
        "M0007",
        "C0010",
        "C0016",
        "M0008",
        "M0009",
        "C0000",
        "M0019",
        "M0021",
    ]
    if server_list is not None:
        camera_ids = None

    with Controller(server_list) as c:

        capture_o_mat = CaptureDetectionOMat(c, camera_ids)
        capture_o_mat.settings.exposure_profile = exposure.exposure
        capture_o_mat.settings.medium_percentage = 0.1
        capture_o_mat.settings.target_pose_cnt_per_camera = 1
        capture_o_mat.settings.target_detected_point_cnt_per_camera = 500
        capture_o_mat.settings.image_grid_display_path = "CharucoDetectionTest.jpg"
        capture_o_mat.settings.detection_processing_steps = ["debayer_malvar", "non_linear"]
        capture_o_mat.settings.detection_processing_steps = [
            "debayer_malvar",
            "non_linear",
            "hist_scale",
        ]
        capture_o_mat.check_and_prepare_system(False)

        c.start()

        # capture_o_mat.save_detection_image("C0009", "CharucoDetection.png")

        with stop_on_interrupt():
            for _ in range(6):
                capture_o_mat.capture_detection()
                capture_o_mat.update_image_grid()
                capture_o_mat.clear()


if __name__ == "__main__":
    main()
