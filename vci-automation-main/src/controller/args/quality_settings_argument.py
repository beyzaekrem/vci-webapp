# Image quailty pre-sets
import argparse
from dataclasses import dataclass

from pydantic import BaseModel, field_validator

from .util import CLI_GROUP_IMAGE_CONFIGURATION, CliArg, ScriptArgumentField


@dataclass(frozen=True)
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


def quality_arg(
    default: str | None = "avif_ll",
    required: bool = False,
    *,
    group: str = CLI_GROUP_IMAGE_CONFIGURATION,
):
    if default is not None and default not in QUALITY_PRESETS:
        valid = ", ".join(QUALITY_PRESETS.keys())
        raise ValueError(f"Invalid default quality setting {default!r}. Must be one of: {valid}")

    class QualityArgMixin(BaseModel):
        quality: str | None = ScriptArgumentField(
            default=... if required else default,
            description="Select a predefined image quality preset.",
            json_schema_extra={
                "enum": list(QUALITY_PRESETS.keys()),
            },
            cli=CliArg(option_strings=["--quality", "-q"], group=group),
        )

        @field_validator("quality", mode="before")
        @classmethod
        def validate_quality(cls, value: str | ImageQualitySettings | None) -> str | None:
            if value is None:
                if required:
                    raise ValueError("Quality setting is required.")
                return value
            if isinstance(value, ImageQualitySettings):
                return value.name
            if value not in QUALITY_PRESETS:
                valid = ", ".join(QUALITY_PRESETS.keys())
                raise ValueError(f"Invalid quality setting {value!r}. Must be one of: {valid}")
            return value

        @property
        def quality_settings(self) -> ImageQualitySettings | None:
            if self.quality is None:
                return None
            return QUALITY_PRESETS[self.quality]

    return QualityArgMixin
