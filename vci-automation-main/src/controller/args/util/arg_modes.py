import argparse
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel
from pydantic.fields import FieldInfo

_ARG_MODE_DEFAULT_UNSET = object()


@dataclass(frozen=True)
class ArgMode:
    """
    Metadata for defining how a pydantic model field should be treated in different execution modes.
    """

    default: Any = field(default_factory=lambda: _ARG_MODE_DEFAULT_UNSET)
    fixed: bool = False
    hidden: bool = False

    def __post_init__(self):
        if self.fixed and self.default is _ARG_MODE_DEFAULT_UNSET:
            msg = "ArgMode fixed=True requires an explicit default value."
            raise ValueError(msg)

    @property
    def has_default(self) -> bool:
        return self.default is not _ARG_MODE_DEFAULT_UNSET


class ArgModes(Mapping[str, ArgMode]):
    def __init__(self, modes: Mapping[str, ArgMode]) -> None:
        self._modes = dict(modes)

    def __getitem__(self, key: str) -> ArgMode:
        return self._modes[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._modes)

    def __len__(self) -> int:
        return len(self._modes)

    def __hash__(self):
        return hash(tuple(sorted(self._modes.items())))

    def __eq__(self, other):
        if not isinstance(other, ArgModes):
            return NotImplemented
        return self._modes == other._modes


def _get_arg_modes(field: FieldInfo) -> ArgModes | None:
    """
    Get the ArgMode metadata from a pydantic FieldInfo, if it exists.
    """
    for meta in field.metadata:
        if isinstance(meta, ArgModes):
            return meta
    return None


def _get_arg_mode(field: FieldInfo, mode: str) -> ArgMode | None:
    """
    Get the ArgMode metadata for a specific execution mode, if it exists.
    """
    arg_modes = _get_arg_modes(field)
    if arg_modes is None:
        return None
    return arg_modes.get(mode)


def apply_arg_modes_to_args(
    args: dict,
    args_type: type[BaseModel],
    mode: str,
) -> dict:
    """
    Apply mode-specific defaults and fixed values before validating args.

    Defaults are only used when the incoming args do not contain a value.
    Fixed values always override incoming args.
    """
    resolved_args = dict(args)
    for dest, field in args_type.model_fields.items():
        arg_mode = _get_arg_mode(field, mode)
        if arg_mode is None or not arg_mode.has_default:
            continue

        if arg_mode.fixed or dest not in resolved_args:
            resolved_args[dest] = arg_mode.default

    return resolved_args


def apply_arg_modes_to_schema(
    schema: dict,
    args_type: type[BaseModel],
    mode: str,
) -> dict:
    """
    Apply mode-specific defaults, fixed values, and UI hints to a JSON schema.
    """
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    for dest, field in args_type.model_fields.items():
        arg_mode = _get_arg_mode(field, mode)
        if arg_mode is None:
            continue

        property_schema = properties.get(dest)
        if property_schema is None:
            continue

        if arg_mode.has_default:
            property_schema["default"] = arg_mode.default

        if arg_mode.fixed:
            property_schema["const"] = arg_mode.default
            property_schema["readOnly"] = True
            property_schema["ui:readonly"] = True
            property_schema["x-fixed-value"] = arg_mode.default
            if dest in required:
                required.remove(dest)

        if arg_mode.hidden:
            property_schema["ui:widget"] = "hidden"
            property_schema["x-hidden"] = True
            if dest in required:
                required.remove(dest)

    return schema


# ----------------------
# ArgMode integration with ArgumentParser for CLI execution
# TODO check if this behaves as we want it to, e.g. with fixed and/or hidden args
# ----------------------


def _append_help_note(action: argparse.Action, note: str) -> None:
    if action.help in (None, argparse.SUPPRESS):
        action.help = note
        return
    action.help = f"{action.help} {note}"


def _apply_arg_mode_to_parser_action(
    parser: argparse.ArgumentParser,
    dest: str,
    arg_mode: ArgMode,
    typehint: object | None = None,
) -> argparse.ArgumentParser:
    action = next((action for action in parser._actions if action.dest == dest), None)
    if action is None:
        return parser

    # Fix typehint so Annotation with ArgMode does not show up in the type printed in help text.
    if typehint is not None and hasattr(action, "_typehint"):
        action._typehint = typehint

    if arg_mode.hidden:
        action.help = argparse.SUPPRESS

    if arg_mode.has_default:
        action.default = arg_mode.default
        if hasattr(action, "required"):
            action.required = False

    if arg_mode.fixed:
        if not arg_mode.hidden:
            _append_help_note(action, f"(fixed: {arg_mode.default!r})")
        action.default = arg_mode.default
        if hasattr(action, "required"):
            action.required = False

    return parser


def apply_arg_modes_to_parser(
    parser: argparse.ArgumentParser,
    args_type: type[BaseModel],
    mode: str = "cli",
) -> argparse.ArgumentParser:
    """
    Apply the different ArgModes defined in the model
    to the corresponding arguments in the ArgumentParser.
    Returns an updated ArgumentParser (Only used for CLI execution)
    """
    for dest, field in args_type.model_fields.items():
        arg_mode = _get_arg_mode(field, mode)
        if arg_mode is None:
            if _get_arg_modes(field) is not None:
                action = next((action for action in parser._actions if action.dest == dest), None)
                if action is not None and hasattr(action, "_typehint"):
                    action._typehint = field.annotation
            continue
        _apply_arg_mode_to_parser_action(parser, dest, arg_mode, field.annotation)
    return parser
