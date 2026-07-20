import argparse

from pydantic import BaseModel

from .arg_modes import apply_arg_modes_to_parser
from .parser_metadata import apply_cli_arg_metadata_from_model
from .space_separated_lists import use_space_separated_list_arguments_from_model


def apply_argparse_utils_from_model(
    parser: argparse.ArgumentParser,
    args_type: type[BaseModel],
) -> argparse.ArgumentParser:
    """
    Applies all argparse utils to the parser based on the model fields.
    Currently applies CLI metadata, space-separated list arguments, and additional argument names from model fields.
    Call this before parser.parse_args()
    """
    apply_cli_arg_metadata_from_model(parser, args_type)
    apply_arg_modes_to_parser(parser, args_type)
    use_space_separated_list_arguments_from_model(parser, args_type)
    return parser
