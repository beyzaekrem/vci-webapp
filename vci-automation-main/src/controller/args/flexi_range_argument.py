from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from pydantic import BaseModel, create_model, field_validator

from controller.argmods.flexi_range_argument import FlexiRange, _create_flexi_range_from_tokens

from .util import CLI_GROUP_FRAME_SELECTION, CliArg, ScriptArgumentField


def make_description(arg_name: str, extra_description: str = "") -> str:
    description = (
        f"{extra_description} "
        f"Specify individually (e.g. --{arg_name} 0 7 -5 -1) or via python slice "
        f"(e.g. --{arg_name} 5:10 15: 10:50:10). Slice notation is START:INCLUSIVE_END:STEP. "
        f"Request evenly spaced samples with e.g. --{arg_name} ::COUNT=3 or no samples with --{arg_name} ::COUNT=0."
        f"You can mix the styles: e.g. --{arg_name} 0:10 15 -1"
    )
    return description


examples = [
    ["0", "7", "-1"],
    ["5:10", "15:", "10:50:10"],
    ["::COUNT=3"],
    ["0:10", "15", "-1"],
]


def validate_flexi_range(value: list[str] | None) -> list[str] | None:
    """
    Validate the input by attempting to parse it into a FlexiRange object,
    then return the original value for further processing.
    Raises an error if the input is invalid.
    """
    _create_flexi_range_from_tokens(value or [])
    return value


def parse_flexi_range(value: list[str] | None) -> FlexiRange:
    """
    Parse the input list of strings into a FlexiRange object.
    """
    return _create_flexi_range_from_tokens(value or [])


def flexi_range_arg(
    arg_name: str,
    extra_description: str = "",
    default: Sequence[str] | None = None,
    *,
    group: str = CLI_GROUP_FRAME_SELECTION,
) -> type[BaseModel]:
    """
    Dynamically create a pydantic model with a flexi range argument and matching
    ``{arg_name}_selection`` property.
    This creates a pydantic model like below, with the downside of no type hints for the properties.
    """
    validators = {
        f"validate_{arg_name}": field_validator(arg_name, mode="before")(validate_flexi_range),
    }

    DynamicMixin = create_model(
        f"FlexiRangeArgMixin{arg_name.title()}",
        __base__=BaseModel,
        __validators__=validators,
        **cast(Any, {
            arg_name: (
                list[str],
                ScriptArgumentField(
                    default_factory=lambda: list(default or []),
                    description=make_description(arg_name, extra_description),
                    json_schema_extra={
                        "examples": examples,
                    },
                    cli=CliArg(group=group, metavar=arg_name.upper()),
                ),
            )
        }),
    )

    def selection_property(self) -> FlexiRange:
        return parse_flexi_range(getattr(self, arg_name))

    setattr(DynamicMixin, f"{arg_name}_selection", property(selection_property))
    return DynamicMixin


class FlexiRangeArgMixinFrames(BaseModel):
    """
    Example of a manually defined flexi range argument.
    """

    frames: list[str] | None = ScriptArgumentField(
        default=[],  # use default = ["::COUNT=0"] if you want to default to no samples instead of all
        description=make_description("frames", "Select frames to download."),
        json_schema_extra={"examples": examples},
        cli=CliArg(group=CLI_GROUP_FRAME_SELECTION, metavar="FRAME"),
    )

    @field_validator("frames", mode="before")
    @classmethod
    def validate_frames(cls, value: list[str] | None) -> list[str] | None:
        return validate_flexi_range(value)

    @property
    def frames_selection(self) -> FlexiRange:
        return parse_flexi_range(self.frames)
