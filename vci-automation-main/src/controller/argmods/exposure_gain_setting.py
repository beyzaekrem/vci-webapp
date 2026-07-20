import argparse
from dataclasses import dataclass


@dataclass(frozen=True)  # instance is immuntable
class ExposureSettings:
    exposure: int
    gain: int
    illumination: int
    name: str


VERY_SLOW_EXPOSURE = ExposureSettings(
    exposure=15906, gain=0, illumination=99, name="super_slow"
)
SLOW_EXPOSURE = ExposureSettings(
    exposure=8000, gain=6, illumination=99, name="slow"  # previous default
)
DEFAULT_EXPOSURE = ExposureSettings(
    exposure=4050, gain=12, illumination=99, name="default"  # previous speedy
)
SPEEDY_EXPOSURE = ExposureSettings(
    exposure=2013, gain=18, illumination=99, name="speedy"
)
SUPER_SPEEDY_EXPOSURE = ExposureSettings(
    exposure=1025,
    gain=24,
    illumination=99,
    name="super_speedy",  # highest gain possible for ximea
)

LOW_LIGHT_EXPOSURE = ExposureSettings(
    exposure=35312, gain=12, illumination=10, name="low_light"
)

EXPOSURE_MAP = {
    p.name: p
    for p in [
        DEFAULT_EXPOSURE,
        SPEEDY_EXPOSURE,
        LOW_LIGHT_EXPOSURE,
        SLOW_EXPOSURE,
        VERY_SLOW_EXPOSURE,
    ]
}


def _exposure_setting_type(value: str) -> ExposureSettings:
    if value in EXPOSURE_MAP:
        return EXPOSURE_MAP[value]

    valid_choices = ", ".join(EXPOSURE_MAP.keys())
    raise argparse.ArgumentTypeError(
        f"Invalid exposure setting name: '{value}'. Must be one of: {valid_choices}"
    )


def add_exposure_argument(
    parser: argparse.ArgumentParser, default: str = "default", *, required=False
):
    """
    Adds the --exposure [-e] argument to the given argparse.ArgumentParser.

    The resulting exposure variable is of type ExposureSettings
    Args:
        parser: The ArgumentParser object to modify.
        default: The key from EXPOSURE_MAP to use as the default value.
    """
    choices = list(EXPOSURE_MAP.keys())

    parser.add_argument(
        "--exposure",
        "-e",
        type=_exposure_setting_type,  # The custom type function
        default=default,  # Use the default key provided
        required=required,
        choices=choices,
        help=(
            f"Select a predefined exposure profile (Exposure, Gain, Illumination). "
            f"Available options: **{', '.join(choices)}**. "
            f"Default here: '{default}'."
        ),
    )
    return parser
