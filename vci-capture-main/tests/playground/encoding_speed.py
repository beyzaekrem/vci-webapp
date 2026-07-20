import argparse
from pathlib import Path

from sparrow import gibbs_wrapper as gibbs
from sparrow.image_processing import codecs, process_images
from sparrow.image_processing.processing_steps import StepDefaults
from sparrow.mode_shared import MATTING
from sparrow.mode_shared.persistent_record import PERSISTENT_RECORD
from sparrow.modes.replay_handler import ReplayHandler
from sparrow.utils import timers


def encode_all_options(images: list[gibbs.GibbsImage], formats: list[str]):
    for f in formats:
        m = {"sequencial": False, "threaded": True, "default": None}
        for name, flag in m.items():
            images_copy = [img.clone() for img in images]
            with timers.CudaTimer(f"Encode {f} {name}"):
                encoded = codecs.encode_images(images_copy, f, force_threadpool=flag, quality=90, threshold=0.5)
                assert isinstance(encoded, list), "should return a list"
                assert all(
                    isinstance(item, gibbs.EncodedImage) for item in encoded
                ), "the returned iamges should be encoded iamges."


def main() -> None:
    outpath = Path("data")

    parser = argparse.ArgumentParser(
        "porcess a frame of a recording. example call: -n bonn_tele_bench_003 --frame 126 --crop 2880 1666 --camidx -1"
    )
    parser.add_argument("--capture_name", "-n", default="bonn_tele_bench_003")
    parser.add_argument("--frame", default=126)
    parser.add_argument("--camidx", "-i", type=int, default=0, help="camera by index.")
    args = parser.parse_args()

    recording = args.capture_name
    caemra_idx = args.camidx
    frame_num = args.frame

    replayhandler: ReplayHandler = ReplayHandler()
    replayhandler.set_recording_name(recording)
    cam_id = replayhandler.recording_camera_ids[caemra_idx]
    raw_images, _ = replayhandler.retrieve_images([cam_id], requested_frame=frame_num)
    raw_image: gibbs.GibbsImage = raw_images[0]

    with timers.CudaTimer("superkernel"):
        base_image = process_images([raw_image.cuda()], PERSISTENT_RECORD.calib_data, StepDefaults.COLOR_PRETTY)[0]
    print(base_image)

    def images() -> list:
        return [base_image.clone() for _ in range(4)]

    encode_all_options(images(), ["jpg", "avif", "avif_ll", "png", "torch:uint8", "torch:float32"])

    background_images: dict[str, gibbs.GibbsImage] = PERSISTENT_RECORD.get_background_images(StepDefaults.COLOR_PRETTY)

    with timers.CudaTimer("Matting"):
        # matting does not benefit from threading, its on gpu
        mattes = MATTING.infer_multiple(images(), background_images, MATTING.VITMATTE_S_RGB_FLOAT16)

    encode_all_options(mattes, ["matte_jpg", "matte_binary", "matte_png"])


if __name__ == "__main__":
    main()
