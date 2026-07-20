from pydantic import BaseModel, field_validator

from .util import CLI_GROUP_IMAGE_CONFIGURATION, CliArg, ScriptArgumentField
from controller.processing_steps import PROCESSING_STEPS_MAP


def processing_steps_type(value: str) -> dict:
    """
    Look up a predefined list of image processing steps by preset name.
    """
    key = value.lower()
    if key in PROCESSING_STEPS_MAP:
        return PROCESSING_STEPS_MAP[key]

    valid_choices = ", ".join(PROCESSING_STEPS_MAP.keys())
    raise ValueError(f"Invalid processing step preset: {value!r}. Must be one of: {valid_choices}")


def processing_steps_arg(
    default: str | None = "processed",
    *,
    required: bool = False,
    group: str = CLI_GROUP_IMAGE_CONFIGURATION,
):
    choices = list(PROCESSING_STEPS_MAP.keys())
    default_value = default.lower() if default is not None else None
    enum_choices = choices if required else [None, *choices]

    if default_value is not None and default_value not in choices:
        raise ValueError(
            f"Default value {default_value} is not a valid image processing preset. Valid presets: {choices}"
        )

    help_msg = f"Select a predefined list of image processing steps. Available options: {', '.join(choices)}."

    class ProcessingStepsArgMixin(BaseModel):
        processing: str | None = ScriptArgumentField(
            default=... if required else default_value,
            description=help_msg,
            json_schema_extra={
                "enum": enum_choices,
            },
            cli=CliArg(option_strings=["--processing"], group=group),
        )

        @field_validator("processing", mode="before")
        @classmethod
        def validate_processing(cls, value: str | dict | None) -> str | None:
            if value is None:
                if required:
                    raise ValueError("Processing step preset is required.")
                return value
            if isinstance(value, dict):
                for key, steps in PROCESSING_STEPS_MAP.items():
                    if value == steps:
                        return key
                raise ValueError("Processing steps dict does not match any preset.")

            key = value.lower()
            processing_steps_type(key)
            return key

        @property
        def processing_steps(self) -> dict | None:
            if self.processing is None:
                return None
            return PROCESSING_STEPS_MAP[self.processing]

    return ProcessingStepsArgMixin
