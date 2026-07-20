from .util import ScriptArgumentField, CliArg, ArgMode, ArgModes
from typing import Any


def ScriptFlagField(
    *,
    description: str | None,
    option_strings: list[str] = None,
    group=None,
    arg_mode: ArgModes | dict[str, ArgMode] | None = None,
) -> Any:
    """
    Creates a ScriptArgumentField for a boolean flag.
    Behaves like store_true: --flag sets it to True,
    but --flag true/false explicit values still work.
    """

    # make store_true CliArg
    cli = CliArg(
        group=group,
        option_strings=option_strings,
        nargs="?",
        const=True,
    )

    return ScriptArgumentField(default=False, description=description, cli=cli, arg_mode=arg_mode)
