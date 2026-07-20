## checks which cameras are connected without opening them


import argparse
from pathlib import Path

import sparrow.gibbs_wrapper as gibbs
from sparrow.gibbs_wrapper import ImageType
from sparrow.image_processing.codecs import encode_images
from sparrow.image_processing.process_images import process_images
from sparrow.image_processing.processing_steps import StepDefaults
from sparrow.mode_shared.camera_manager import CAMERA_MANAGER, ExposureSetting
from sparrow.mode_shared.persistent import PERSISTENT_DATA

outpath = Path("data/camera_peek")
outpath.mkdir(exist_ok=True, parents=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="test collection of basic capturing and writing to disk")
    parser.add_argument(
        "-c", "--cams", nargs="+", type=str, default=None, help="specific camera ids to request. Default: all"
    )
    parser.add_argument(
        "--processing",
        type=str,
        help="Select a predefined list of image processing steps.",
        choices=StepDefaults.get_all().keys(),
        default="UNCALIBRATED",
    )
    args = parser.parse_args()
    steps = StepDefaults.get_all()[args.processing.upper()]

    cameras = CAMERA_MANAGER.get_camera_ids_without_opening_cameras()
    print(f"Cameras found: {list(cameras.keys())} {len(cameras)}")

    CAMERA_MANAGER.exposure_settings[ImageType.Color] = ExposureSetting(exposure_ms=35312, gain=12)
    CAMERA_MANAGER.setup_cameras(args.cams)
    PERSISTENT_DATA.load(CAMERA_MANAGER.camera_ids)
    for cam_param in PERSISTENT_DATA.calibration_data.camera_parameters.values():
        cam_param.rotation = 0

    print(CAMERA_MANAGER.get_camera_info())
    print(PERSISTENT_DATA.calibration_data.camera_ids)

    print("starting cameras...")
    CAMERA_MANAGER.set_trigger_source("Software")
    CAMERA_MANAGER.start_cameras()

    print("-------------- READY --------------------")

    print(f"\n   processing: {args.processing} {steps}\n")

    i: int = 0
    while True:
        i += 1
        timers = None
        print(f"get image {i}...")
        images: list[gibbs.GibbsImage] = CAMERA_MANAGER.capture_images(timeout_ms=1000, execute_software_trigger=True)
        process_images(images, PERSISTENT_DATA.calibration_data, steps)
        print(f"processed: {process_images}")

        encoded: list[gibbs.EncodedImage] = encode_images(images, "png", quality=89)
        for enc_img in encoded:
            with (outpath / f"{enc_img.camera_id}_frame.png").open("wb") as f:
                f.write(enc_img.data.numpy().tobytes())
        print(f"Images saved to {outpath}")
        g = input("\ntrigger another image [Y,n]").lower() != "n"
        if not g:
            break

    print("Buh bey!")


if __name__ == "__main__":
    main()
