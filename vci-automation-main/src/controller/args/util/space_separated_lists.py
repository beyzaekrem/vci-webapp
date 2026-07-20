import argparse
from types import UnionType
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel

from .cli_arg import get_cli_arg


class SpaceSeparatedListAction(argparse.Action):
    """
    An argparse Action that parses space-separated values into a list.
    Necessary so that we can use e.g. --frames 0 7 -5 -1 instead of --frames '["0", "7", "-5", "-1"]'
    """

    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        super().__init__(option_strings, dest, nargs=nargs or "*", **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        values = list(values or [])
        if option_string and option_string.endswith("+"):
            previous = getattr(namespace, self.dest, None)
            if previous:
                values = [*previous, *values]
        setattr(namespace, self.dest, values)


def use_space_separated_list_argument(
    parser: argparse.ArgumentParser,
    name: str,
    *,
    nargs: str | None = None,
    metavar: str | None = None,
    value_type: Any | None = None,
) -> argparse.ArgumentParser:
    """
    When using jsonargparse on e.g. fields of type list[str],
    the default behavior is to expect a JSON array string, e.g. --frames '["0", "7", "-5", "-1"]'.
    This function modifies the parser to instead accept space-separated values, e.g. --frames 0 7 -5 -1.
    """
    dest = name.removeprefix("--").replace("-", "_")
    action = next((action for action in parser._actions if action.dest == dest), None)
    if action is None:
        msg = f"No parser argument with destination {dest!r} exists."
        raise ValueError(msg)

    container = getattr(action, "container", parser)
    for actions in (parser._actions, getattr(container, "_group_actions", [])):
        if action in actions:
            actions.remove(action)
    for option_string in action.option_strings:
        parser._option_string_actions.pop(option_string, None)
        getattr(container, "_option_string_actions", {}).pop(option_string, None)

    argument_kwargs = {
        "action": SpaceSeparatedListAction,
        "default": action.default,
        "dest": action.dest,
        "help": action.help,
        "nargs": nargs or getattr(action, "nargs", None),
        "metavar": metavar or action.metavar,
        "required": getattr(action, "required", False),
    }
    if value_type is not None:
        argument_kwargs["type"] = value_type

    for attr in ("type", "choices"):
        if attr in argument_kwargs:
            continue
        value = getattr(action, attr, None)
        if value is not None:
            argument_kwargs[attr] = value

    container.add_argument(*action.option_strings, **argument_kwargs)
    return parser


def _is_list_annotation(annotation: object) -> bool:
    """
    Returns True if the annotation is a list or an optional list (e.g. list[str] or list[str] | None).
    """
    if annotation is list or get_origin(annotation) is list:
        return True

    if get_origin(annotation) in (Union, UnionType):
        args = get_args(annotation)
        non_none_args = [arg for arg in args if arg is not type(None)]
        return len(non_none_args) == 1 and _is_list_annotation(non_none_args[0])

    return False


def _get_list_item_type(annotation: object) -> Any | None:
    if get_origin(annotation) is list:
        args = get_args(annotation)
        return args[0] if args else None

    if get_origin(annotation) in (Union, UnionType):
        args = get_args(annotation)
        non_none_args = [arg for arg in args if arg is not type(None)]
        if len(non_none_args) == 1:
            return _get_list_item_type(non_none_args[0])

    return None


def _get_argparse_value_type(annotation: object) -> Any | None:
    item_type = _get_list_item_type(annotation)
    if item_type in (str, int, float):
        return item_type
    return None


def use_space_separated_list_arguments_from_model(
    parser: argparse.ArgumentParser,
    args_type: type[BaseModel],
) -> argparse.ArgumentParser:
    """
    Applies use_space_separated_list_argument to all list fields in the model.
    This allows you to type e.g. --frames 0 7 -5 -1 for a field named "frames" of type list[str] | None,
    instead of having to type --frames '["0", "7", "-5", "-1"]' as a JSON array string.
    """
    for dest, field in args_type.model_fields.items():
        if _is_list_annotation(field.annotation):
            name = f"--{dest.replace('_', '-')}"
            cli_arg = get_cli_arg(field)
            option_strings = cli_arg.option_strings if cli_arg else None
            primary_name = option_strings[0] if option_strings else name
            use_space_separated_list_argument(
                parser,
                primary_name,
                nargs=cli_arg.nargs if cli_arg else None,
                metavar=(cli_arg.metavar if cli_arg else None) or dest.upper(),
                value_type=_get_argparse_value_type(field.annotation),
            )
    return parser
