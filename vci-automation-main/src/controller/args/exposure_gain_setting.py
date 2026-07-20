from dataclasses import dataclass

from pydantic import BaseModel, field_validator

from .util import CLI_GROUP_IMAGE_CONFIGURATION, CliArg, ScriptArgumentField


@dataclass(frozen=True)  # instance is immuntable
class ExposureSettings:
    exposure: int
    gain: int
    illumination: int
    name: str


VERY_SLOW_EXPOSURE = ExposureSettings(exposure=15906, gain=0, illumination=99, name="super_slow")
SLOW_EXPOSURE = ExposureSettings(exposure=8000, gain=6, illumination=99, name="slow")  # previous default
DEFAULT_EXPOSURE = ExposureSettings(exposure=4050, gain=12, illumination=99, name="default")  # previous speedy
SPEEDY_EXPOSURE = ExposureSettings(exposure=2013, gain=18, illumination=99, name="speedy")
SUPER_SPEEDY_EXPOSURE = ExposureSettings(
    exposure=1025,
    gain=24,
    illumination=99,
    name="super_speedy",  # highest gain possible for ximea
)

LOW_LIGHT_EXPOSURE = ExposureSettings(exposure=35312, gain=12, illumination=10, name="low_light")

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


class ExposureArg(BaseModel):
    """adds --exposure argument to parser. Select a predefined exposure profile.
    defaults to "default" when not passed.

    Adds fields to pydantic model:
      - exposure(str)
      - exposure_profile(arguments.ExposureSettings)
    """

    exposure: str = ScriptArgumentField(
        default="default",
        description="Select a predefined exposure profile.",
        json_schema_extra={"enum": list(EXPOSURE_MAP.keys())},
        cli=CliArg(
            group=CLI_GROUP_IMAGE_CONFIGURATION,
        ),
    )

    @field_validator("exposure")
    @classmethod
    def validate_exposure(cls, value: str) -> str:
        if value not in EXPOSURE_MAP:
            valid = ", ".join(EXPOSURE_MAP.keys())
            raise ValueError(f"Invalid exposure setting {value!r}. Must be one of: {valid}")
        return value

    @property
    def exposure_settings(self) -> ExposureSettings:
        return EXPOSURE_MAP[self.exposure]
