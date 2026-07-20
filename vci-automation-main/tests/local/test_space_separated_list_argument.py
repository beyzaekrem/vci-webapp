from jsonargparse import ArgumentParser
from pydantic import BaseModel, Field

from controller.args import (
    CliArg,
    CliField,
    add_additional_arg_names_from_model,
    apply_argparse_utils_from_model,
    use_space_separated_list_argument,
)


class NameArgs(BaseModel):
    names: list[str] = Field(default_factory=list)


def test_space_separated_list_argument_accepts_multiple_values():
    parser = ArgumentParser()
    parser.add_class_arguments(NameArgs)
    use_space_separated_list_argument(parser, "names")

    parsed = parser.parse_args(["--names", "john", "mary"])
    args = NameArgs.model_validate(parsed.__dict__)

    assert args.names == ["john", "mary"]


class AliasArgs(BaseModel):
    quality: str = CliField(
        default="avif_ll",
        cli=CliArg(option_strings=["--quality", "-q"]),
    )


def test_add_additional_arg_names_registers_field_aliases():
    parser = ArgumentParser()
    parser.add_class_arguments(AliasArgs)
    add_additional_arg_names_from_model(parser, AliasArgs)

    parsed = parser.parse_args(["-q", "png"])
    args = AliasArgs.model_validate(parsed.__dict__)

    assert args.quality == "png"


class GroupedArgs(BaseModel):
    exposure: int = CliField(default=1000, cli=CliArg(group="Capture"))
    cameras: list[str] = CliField(default_factory=list, cli=CliArg(group="Selection"))


def test_apply_argparse_utils_from_model_moves_fields_to_argument_groups():
    parser = ArgumentParser()
    parser.add_class_arguments(GroupedArgs)
    apply_argparse_utils_from_model(parser, GroupedArgs)

    groups = {
        group.title: [action.dest for action in group._group_actions]
        for group in parser._action_groups
    }

    assert "exposure" in groups["Capture"]
    assert "cameras" in groups["Selection"]

    parsed = parser.parse_args(["--cameras", "C0001", "C0002"])
    args = GroupedArgs.model_validate(parsed.__dict__)

    assert args.cameras == ["C0001", "C0002"]


class OptionalAliasArgs(BaseModel):
    capture_name: str | None = CliField(default="connection_test", cli=CliArg(option_strings=["--capture-name", "-n"]))


def test_apply_argparse_utils_from_model_hides_cli_metadata_from_help_type():
    parser = ArgumentParser()
    parser.add_class_arguments(OptionalAliasArgs)
    apply_argparse_utils_from_model(parser, OptionalAliasArgs)

    help_text = parser.format_help()

    assert "Annotated" not in help_text
    assert "CliArg object" not in help_text
    assert "type: str | None" in help_text
