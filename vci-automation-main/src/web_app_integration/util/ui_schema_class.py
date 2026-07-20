from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any, ClassVar


def _merge_ui_schema(target: dict[str, Any], source: dict[str, Any]) -> None:
    """
    Recursively merge two ui schema dictionaries,
    with the source taking precedence over the target.
    """
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge_ui_schema(target[key], value)
        else:
            target[key] = copy.deepcopy(value)


class UISchemaGeneratingClass:
    output_ui_schema: ClassVar[dict[str, Any]] = {}

    def get_ui_schema(self) -> dict[str, Any]:
        """
        Return the RJSF uiSchema fragment for this class.
        You can override this in the child class
        if the ui schema needs to be dynamic based on the instance parameters,
        otherwise it will use the default static ui schema defined in the class variable `output_ui_schema`.
        It will also merge ui schemas from parent classes with child classes.
        """
        ui_schema = {}
        for cls in reversed(type(self).mro()):
            class_ui_schema = cls.__dict__.get("output_ui_schema")
            if class_ui_schema is None:
                continue
            _merge_ui_schema(ui_schema, class_ui_schema)
        return ui_schema

    @classmethod
    def dict_to_ui_schema(cls, data: Mapping[str, UISchemaGeneratingClass]) -> dict[str, dict[str, Any]]:
        return {key: value.get_ui_schema() for key, value in data.items()}
