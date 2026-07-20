import argparse
from collections.abc import MutableSequence
from typing import cast

from pydantic import BaseModel

from .cli_arg import CliArg, get_cli_arg


def _get_action(parser: argparse.ArgumentParser, dest: str) -> argparse.Action | None:
    return next((action for action in parser._actions if action.dest == dest), None)


def _get_or_create_argument_group(parser: argparse.ArgumentParser, title: str) -> argparse._ArgumentGroup:
    group = next((group for group in parser._action_groups if group.title == title), None)
    return group if group is not None else parser.add_argument_group(title)


def _move_action_to_group(
    parser: argparse.ArgumentParser,
    action: argparse.Action,
    group_title: str,
) -> argparse.ArgumentParser:
    """
    Move an argparse Action to a different argument group in the parser.
    If the group does not exist, it will be created.
    """
    group = _get_or_create_argument_group(parser, group_title)
    if action in group._group_actions:
        return parser

    current_group = getattr(action, "container", None)
    group_actions = getattr(current_group, "_group_actions", None)
    if group_actions is not None and action in group_actions:
        group_actions.remove(action)
    else:
        for action_group in parser._action_groups:
            if action in action_group._group_actions:
                action_group._group_actions.remove(action)

    group._group_actions.append(action)
    setattr(action, "container", group)
    return parser


def apply_cli_arg_metadata(
    parser: argparse.ArgumentParser,
    dest: str,
    cli_arg: CliArg,
    typehint: object | None = None,
) -> argparse.ArgumentParser:
    """
    Apply the CLI metadata from a CliArg to the corresponding argument in the ArgumentParser.
    This includes adding additional option strings,
    moving the argument to a different group,
    and setting nargs, metavar, and const.
    Returns an updated ArgumentParser (Only used for CLI execution)
    """
    action = _get_action(parser, dest)
    if action is None:
        return parser

    # Fix typehint so Annotation with CliArg does not show up in the type printed in help text
    if typehint is not None and hasattr(action, "_typehint"):
        setattr(action, "_typehint", typehint)

    if cli_arg.group is not None:
        _move_action_to_group(parser, action, cli_arg.group)

    if cli_arg.option_strings:
        additional_names = [name for name in cli_arg.option_strings if name not in action.option_strings]
        if additional_names:
            add_additional_arg_names(parser, dest, additional_names)

    for attr in ("nargs", "metavar", "const"):
        value = getattr(cli_arg, attr)
        if value is not None:
            setattr(action, attr, value)

    return parser


def apply_cli_arg_metadata_from_model(
    parser: argparse.ArgumentParser,
    args_type: type[BaseModel],
) -> argparse.ArgumentParser:
    for dest, field in args_type.model_fields.items():
        cli_arg = get_cli_arg(field)
        if cli_arg is None:
            continue
        apply_cli_arg_metadata(parser, dest, cli_arg, field.annotation)
    return parser


def add_additional_arg_names(
    parser: argparse.ArgumentParser,
    dest: str,
    additional_names: list[str],
) -> argparse.ArgumentParser:
    """
    Add additional option strings to an existing argument in the parser.
    E.g. add -f as an additional name for --frames.
    """
    action = _get_action(parser, dest)
    if action is None:
        msg = f"No parser argument with destination {dest!r} exists."
        raise ValueError(msg)

    cast(MutableSequence[str], action.option_strings).extend(additional_names)
    for option_string in additional_names:
        parser._option_string_actions[option_string] = action

    return parser


def add_additional_arg_names_from_model(
    parser: argparse.ArgumentParser,
    args_type: type[BaseModel],
) -> argparse.ArgumentParser:
    """
    Adds additional argument names to the parser based on the model fields.
    E.g. adds both --frames and -f for a field named "frames"
    if the CliArg metadata of the field contains option_strings ["--frames", "-f"].
    """

    for dest, field in args_type.model_fields.items():
        cli_arg = get_cli_arg(field)
        if not cli_arg or not cli_arg.option_strings:
            continue

        action = _get_action(parser, dest)
        if action is None:
            continue

        additional_names = [name for name in cli_arg.option_strings if name not in action.option_strings]
        if additional_names:
            add_additional_arg_names(parser, dest, additional_names)

    return parser
