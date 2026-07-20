import argparse
from pathlib import Path

import torch
import torchvision
import torchvision.transforms.functional

from sparrow import gibbs_wrapper as gibbs
from sparrow.calibration_data import CameraParameters
from sparrow.image_processing.codecs import encode_images
from sparrow.image_processing.process_images import process_images
from sparrow.image_processing.processing_steps import StepDefaults
from sparrow.mode_shared.persistent_record import PERSISTENT_RECORD
from sparrow.modes.replay_handler import ReplayHandler
from sparrow.utils import timers


def encode_and_save(raw_image: torch.tensor, file_name: Path):
    encoded = encode_images(raw_image, file_name.suffix[1:], quality=100).cpu()
    with file_name.open("wb") as f:
        f.write(encoded.numpy().tobytes())
    print(f"\n Saved image --> {file_name}")


def main():
    outpath = Path("data")

    parser = argparse.ArgumentParser(
        "porcess a frame of a recording. example call: -n bonn_tele_bench_003 --frame 126 --crop 2880 1666 --camidx -1"
    )
    parser.add_argument("--capture_name", "-n", default="bonn_tele_bench_003")
    parser.add_argument("--frame", default=126)

    parser.add_argument(
        "--crop",
        nargs="+",
        type=int,
        default=None,
        help="specify crop location 'x y' by upper left corner. cropped patch will be [512x512]",
    )
    parser.add_argument("--camidx", "-i", type=int, default=0, help="camera by index.")

    parser.add_argument(
        "--processing",
        type=str,
        help="Select a predefined list of image processing steps.",
        choices=StepDefaults.get_all().keys(),
        default="PROCESSED",
    )
    parser.add_argument("--format", default="jpg", help="specify image format for saving.")

    args = parser.parse_args()
    recording = args.capture_name
    if args.crop:
        left = args.crop[0]
        top = args.crop[1]
        crop = True
    else:
        crop = False
    caemra_idx = args.camidx
    frame_num = args.frame

    # recording = "2026_02_03_orbbec_test_001"
    # caemra_idx = -1
    # frame_num = 54
    # top = 1683
    # left = 1992

    replayhandler: ReplayHandler = ReplayHandler()
    replayhandler.set_recording_name(recording)
    cam_id = replayhandler.recording_camera_ids[caemra_idx]
    raw_images, requested_frame = replayhandler.retrieve_images([cam_id], requested_frame=frame_num)
    raw_image: gibbs.GibbsImage = raw_images[0]

    if crop:
        pixels = torchvision.transforms.functional.crop(raw_image.pixels, top=top, left=left, height=512, width=512)
        raw_image.pixels = pixels.detach().contiguous().cuda()
        camera_calib: CameraParameters = PERSISTENT_RECORD.calib_data.get(cam_id)
        if camera_calib:
            camera_calib.resolution = [512, 512]

    outpath.mkdir(exist_ok=True)

    with timers.CudaTimer("superkernel"):
        c_img = process_images([raw_image.cuda()], PERSISTENT_RECORD.calib_data, StepDefaults.COLOR_PRETTY)[0]

    p = outpath / f"{replayhandler.recording_name}_{cam_id}"
    print("\nSaving image to -->", p)
    encode_and_save(c_img, p + args.format)
    torch.save(c_img.detach().cpu(), p + ".pth")


if __name__ == "__main__":
    main()
