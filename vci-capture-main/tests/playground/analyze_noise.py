import sys

sys.path.append("/srv/vci-capture/src/sparrow")

import cv2
import numpy as np

from sparrow.image_processing.process_images import process_images_old
from sparrow.modes.base_handler import BaseHandler
from sparrow.modes.handler_exceptions import *
from sparrow.modes.mode_util import *
from sparrow.modes.replay_handler import ReplayHandler


def noise(my_handler: BaseHandler = None):
    print("noise anaylsis")

    my_handler.switch_mode("replay")
    replayhandler: ReplayHandler = my_handler.activeHandler

    replayhandler.recording_name = "_test"
    replayhandler.create_CacheReader(["debayer_malvar", "superkernel"])
    num = replayhandler.cache_reader.frame_count
    print("averaged over", num, "images")

    # for cam_idx in range(len(replayhandler.camera_ids)):

    cam_idx = 0

    all_buffers = [
        replayhandler.retrive_images([replayhandler.camera_ids[cam_idx]], requested_frame=f) for f in range(num)
    ]
    all_images = [
        process_images_old(
            buffers, replayhandler.camera_ids, replayhandler.calib_data, ["white_balance_bayer", "non_linear_bayer"]
        )
        for buffers, _, _ in all_buffers
    ]

    frames_of_camera = [single_frame[0] for single_frame in all_images]
    frames_of_camera = [e.cpu() for e in frames_of_camera]

    frames_array = np.array(frames_of_camera, dtype=np.float32)
    _analyze_noise(frames_array, f"{replayhandler.camera_ids[cam_idx]}_12g")

    # rames_array = np.array([(np.array((frame * 4095)).astype(np.uint16) >> 2).astype(np.uint16) / 1023 for frame in frames], dtype=np.float32)
    # _analyze_noise(frames_array,"10_bit")

    # frames_array = np.array([(np.array((frame * 4095)).astype(np.uint16) >> 4).astype(np.uint8) / 255 for frame in frames], dtype=np.float32)
    # _analyze_noise(frames_array, "8_bit")


def _analyze_noise(frames_array, desc):
    print(f"analyze_noise on {len(frames_array)} frames")
    print("\n" + desc)
    print("depth", len(np.unique(frames_array[0])))
    print("max", np.max(frames_array[0]), "min", np.min(frames_array[0]))
    std = np.std(frames_array, axis=0)
    mean = np.mean(frames_array, axis=0)
    snr = np.mean(mean) / np.mean(std)
    noise_image = mean - frames_array[0]
    print("mean noise", np.mean(noise_image))
    print("std noise", np.std(noise_image))
    # print("noise")
    # print("mean", np.mean(mean))
    # print("std", np.mean(std))
    print("snr", snr)
    # print("psnr (frame_0 - gt)", PSNR(mean, frames_array[0]))

    _show_noise_distribution(mean, [mean - frame for frame in frames_array], f"{desc}_all_images")

    for i in range(10):
        _show_noise_distribution(mean, [mean - frames_array[i]], f"{desc}_frame{i}")

    cv2.imwrite(f"{desc}_noise.png", noise_image * 255)
    cv2.imwrite(f"{desc}_noise_x50.png", noise_image * 255 * 50)
    cv2.imwrite(f"{desc}_noisy.png", frames_array[0] * 255)
    cv2.imwrite(f"{desc}_mean.png", mean * 255)
    cv2.imwrite(f"{desc}_std.png", np.abs(std) * 255)
    cv2.imwrite(f"{desc}_std_x50.png", np.abs(std) * 255 * 50)


def _show_noise_distribution(image_values, noise_values, desc):
    from matplotlib import pyplot as plt

    image_values = np.tile(image_values.flatten(), len(noise_values))
    bin_edges = np.linspace(0, 1, 21)
    bin_indeces = np.digitize(image_values, bin_edges)

    noise_values = np.concatenate([n.flatten() for n in noise_values])

    binned_noise = [noise_values[bin_indeces == i] for i in range(1, len(bin_edges))]
    labels = [f"{bin_edges[i-1]:.5f}–{bin_edges[i]:.5f}" for i in range(1, len(bin_edges))]

    print("Bin Range     Mean Noise     Std Dev")
    print("--------------------------------------")

    for label, bin_noise in zip(labels, binned_noise):
        mean = np.mean(bin_noise)
        std = np.std(bin_noise)
        print(f"{label:11}  {mean: .5f}      {std: .5f}")

    plt.figure(figsize=(6, 4))
    plt.boxplot(binned_noise, tick_labels=labels, showfliers=False)

    means = [np.mean(bin_noise) for bin_noise in binned_noise]
    stds = [np.std(bin_noise) for bin_noise in binned_noise]
    x = np.arange(len(labels))

    # plt.plot(x + 1, means, color='red', marker='o', label='Mean')
    plt.fill_between(
        x + 1,
        np.array(means) - np.array(stds),
        np.array(means) + np.array(stds),
        color="red",
        alpha=0.2,
        label="±1 Std Dev",
    )

    plt.title(f"Noise Distribution in Image, {desc}")
    plt.ylabel("Noise Intensity")
    plt.xlabel("Image Intensity")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.savefig(f"{desc}_noise_distribution.png")


def PSNR(gt, image, max_value=1):
    """ "Function to calculate peak signal-to-noise ratio (PSNR) between two images."""
    height, width = gt.shape
    mse = np.mean((gt - image) ** 2)
    if mse == 0:
        return 100
    return 20 * np.log10(max_value / (np.sqrt(mse)))


if __name__ == "__main__":
    bh = BaseHandler()
    noise(bh)
