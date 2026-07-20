# Image quailty pre-sets
import argparse
from dataclasses import dataclass


@dataclass()
class ImageQualitySettings:
    format: str
    quality: int
    mattes_format: str
    mattes_quality: int
    name: str


HIGH_QUALITY_PNG = ImageQualitySettings(format="png", quality=98, mattes_format="png", mattes_quality=98, name="png")

HIGH_QUALITY_JPG = ImageQualitySettings(format="jpg", quality=98, mattes_format="binary", mattes_quality=98, name="jpg")

LOW_QUALITY_JPG = ImageQualitySettings(
    format="jpg", quality=70, mattes_format="binary", mattes_quality=70, name="jpg_low"
)

ENC_QUALITY_AVIF = ImageQualitySettings(
    format="avif",
    quality=87,  # 87 looks solid. barely any different from png. ~4 MiB for full size rgb image. 85 noticably worse.
    # 100 is exactly the same as png and jpg (98) ~13 MiB per image.
    mattes_format="avif",
    mattes_quality=87,
    name="avif",
)

LOSSLESS_QUALITY_AVIF = ImageQualitySettings(
    format="avif_ll",
    quality=100,
    mattes_format="avif_ll",
    mattes_quality=100,
    name="avif_ll",
)

LOW_QUALITY_JPG = ImageQualitySettings(
    format="jpg", quality=70, mattes_format="binary", mattes_quality=70, name="jpg_low"
)

QUALITY_EXR = ImageQualitySettings(format="exr", quality=100, mattes_format="exr", mattes_quality=100, name="exr")

QUALITY_TORCH = ImageQualitySettings(
    format="torch:float32", quality=100, mattes_format="torch:float32", mattes_quality=100, name="torch:32"
)

QUALITY_PRESETS = {
    p.name: p
    for p in [
        HIGH_QUALITY_PNG,
        HIGH_QUALITY_JPG,
        LOW_QUALITY_JPG,
        ENC_QUALITY_AVIF,
        LOSSLESS_QUALITY_AVIF,
        QUALITY_EXR,
        QUALITY_TORCH,
    ]
}


def _image_quality_type(value: str) -> ImageQualitySettings:
    """
    Custom argparse type function to look up ImageQualitySettings by name.
    """
    if value in QUALITY_PRESETS:
        return QUALITY_PRESETS[value]

    valid_choices = ", ".join(QUALITY_PRESETS.keys())
    msg = f"Invalid image quality preset name: '{value}'. Must be one of: {valid_choices}"
    raise argparse.ArgumentTypeError(msg)


def add_quality_argument(
    parser: argparse.ArgumentParser,
    default: str = "avif_ll",
    required: bool = False,
) -> argparse.ArgumentParser:
    """
    Adds the --quality [-q] argument to the given argparse.ArgumentParser.

    Args:
        parser: The ArgumentParser object to modify.
        default_key: The key to use as the default value.
        is_required: If True, the argument must be supplied by the user.
    """
    choices = list(QUALITY_PRESETS.keys())

    # Logic to adjust required status if a default is provided
    if default is not None:
        required = False

    help_msg = (
        f"Select an image quality preset (Image and Mattes Format and Quality). "
        f"Available options: **{', '.join(choices)}**."
    )
    if default is not None:
        help_msg += f" Default here:'{default}'."

    parser.add_argument(
        "--quality",
        "-q",
        type=_image_quality_type,  # Custom conversion/validation function
        default=default,  # Stores the string key as default
        required=required,
        help=help_msg,
        # We omit 'choices' here to prevent conflict with the custom type conversion.
    )
    return parser
