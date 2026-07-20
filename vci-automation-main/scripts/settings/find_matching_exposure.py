# ruff: noqa: T201, INP001
import argparse

import matplotlib.pyplot as plt

from controller import (
    Controller,
    ProcessingSteps,
    argmods,
    stop_on_interrupt,
    trigger_box,
    trigger_single,
)

# calibrated with:
ref = argmods.DEFAULT_EXPOSURE
image_format = "jpg"
steps = ProcessingSteps.PROCESSED


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Finds exposue time to match the average brightness of a reference image, "
            "when illumination or gain are changed. "
            "Start by passing your pre-change exposure settings (exposure, gain, illumination). "
            "Follow the interactive promps on when to change your gain and illumination."
        )
    )
    parser = argmods.add_server_list_argument(parser)
    image_group = parser.add_argument_group("REFERENCE IMAGE")
    argmods.add_exposure_argument(image_group, default="default")
    argmods.add_processing_steps_argument(image_group, default="processed")

    args = parser.parse_args()

    c = Controller(args.server)
    c.switch_mode("calibration")
    trigger_box("off")
    c.set_exposure_and_gain(ref.exposure, ref.gain)

    # first capture reference brightness
    c.start()
    print(
        f"capturing reference brightness with {ref.exposure} exposure and {ref.gain} gain at {ref.illumination} illumination..."
    )
    c.image_writer.image_name_suffix = "_reference"
    with trigger_single(c):
        statuus = [c.get_status(idx) for idx in range(len(c.servernames))]
        print([s.get("mode") for s in statuus])
        brightness_info = c.calculate_image_brightness(c.all_camera_ids[0], steps)[0][0]
    reference_brightness = brightness_info.get("brightnesses")[0]
    print("reference_brightness captured: ", reference_brightness)

    illumination = ref.illumination
    new_gain = ref.gain
    print()
    with stop_on_interrupt():
        while True:
            illumination_input = input("Input new illumination level if you have adjusted it ")
            if illumination_input.isdigit():
                illumination = int(illumination)
                print("new illumination ", illumination)
            if illumination_input == "n":
                break
            gain_input = input(
                "Input gain to adjust it. Or plot exposure for all gain levels with [all]. [Enter] to leave gain unchanged "
            )
            if gain_input.lower() == "all":
                plot_exposure_and_gain(c, reference_brightness, illumination)
                new_gain = ref.gain
            else:
                if gain_input.isdigit():
                    new_gain = int(gain_input)
                gain, exposure = find_matching_exposure(
                    reference_brightness,
                    ref.exposure,
                    new_gain,
                    c.all_camera_ids[0],
                    c,
                )
    c.stop()
    trigger_box("off")
    c.set_software_trigger(state=False)
    c.set_exposure_and_gain(ref.exposure, ref.gain)
    c.close()


def plot_exposure_and_gain(c: Controller, reference_brightness, illumination):
    exposures = [ref.exposure]
    gains = [ref.gain]
    for gain in range(1, 13):
        c.image_writer.enabled = False
        gain, exposure = find_matching_exposure(
            reference_brightness, exposures[gain - 1], gain, c.all_camera_ids[0], c
        )  # start searching from last exposure
        gains.append(gain)
        exposures.append(exposure)

    print(f"illumination {illumination}")
    print("gain: exposure")
    for e, g in zip(exposures, gains):
        print(f"{str(g).zfill(4)}: {e}")
    plot(gains, exposures, illumination, c.image_writer.output_folder)


def find_matching_exposure(reference_brightness, exposure, gain, camera_ids, c: Controller):
    print("find matching exposure for gain", gain)
    c.stop()
    c.set_exposure_and_gain(exposure, gain)
    c.start()

    with trigger_single(c):
        brightness_info = c.calculate_image_brightness(c.all_camera_ids[0], steps)[0][0]
    b = brightness_info.get("brightnesses")[0]
    print(
        f"find exposure that produces brightness {reference_brightness} at gain {gain}. Starting search with exposure {exposure} producing brightness {b}."
    )
    iterations = 0
    min_exposure, max_exposure = 100, 100000  # Define reasonable exposure bounds
    # adjust exposure till we match the reference brightness
    while abs(b - reference_brightness) > 0.005:  # Smaller tolerance since brightness is 0 to 1
        diff = reference_brightness - b

        # Binary search-like adjustment: increase or decrease by half the current step
        if diff > 0:
            min_exposure = exposure
            exposure = (exposure + max_exposure) // 2  # Increase exposure
        else:
            max_exposure = exposure
            exposure = (exposure + min_exposure) // 2  # Decrease exposure
        c.stop()
        c.set_exposure_and_gain(int(exposure), gain)
        c.start()
        with trigger_single(c):
            brightness_info = c.calculate_image_brightness(c.all_camera_ids[0], steps)[0][0]
        b = brightness_info.get("brightnesses")[0]
        print(f"Adjusted exposure {exposure}, brightness {b}, reference_brightness {reference_brightness}")
        iterations += 1
        if exposure in (min_exposure, max_exposure):  # Avoid infinite loop
            print("Unable to converge further, exiting adjustment loop")
            break
    print(
        f"\n{camera_ids} gain {gain}, matches reference_brightness {reference_brightness} at exposure {exposure} (brightness {b}). Found with {iterations} iterations"
    )
    return gain, exposure


def plot(gain: int, exposure: int, illumination: int, output_folder: str) -> None:
    # Plotting gains vs. exposures
    plt.plot(gain, exposure, marker="o", linestyle="-", color="b")

    # Setting the labels for x and y axes
    plt.xlabel("Gain")
    plt.ylabel("Exposure")

    # Adding grid to the plot
    plt.grid(visible=True)

    # Saving the plot to c.output_folder
    output_path = f"gains_vs_exposures_illumination{illumination}.png"
    plt.savefig(output_path)

    # Displaying the plot
    plt.show()


if __name__ == "__main__":
    main()
