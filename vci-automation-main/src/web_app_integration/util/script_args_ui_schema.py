from pydantic import BaseModel

from controller.args.util import get_cli_arg


class ScriptArgsUISchema:
    @staticmethod
    def from_model(args_model: type[BaseModel], schema: dict | None = None) -> dict:
        """Generate an RJSF uiSchema for script arguments."""
        groups: dict[str, list[str]] = {}
        ungrouped_fields = []
        field_ui_schema = {}
        schema_properties = (schema or {}).get("properties", {})

        for field_name, field in args_model.model_fields.items():
            property_schema = schema_properties.get(field_name, {})
            field_ui_schema[field_name] = ScriptArgsUISchema._ui_hints_from_property_schema(property_schema)

            cli_arg = get_cli_arg(field)
            group = cli_arg.group if cli_arg is not None else None
            if group is None:
                ungrouped_fields.append(field_name)
                continue

            groups.setdefault(group, []).append(field_name)

        return ScriptArgsUISchema._build_ui_schema(groups, ungrouped_fields, field_ui_schema)

    @staticmethod
    def _ui_hints_from_property_schema(property_schema: dict) -> dict:
        return {key: value for key, value in property_schema.items() if key.startswith("ui:")}

    @staticmethod
    def _build_ui_schema(
        groups: dict[str, list[str]],
        ungrouped_fields: list[str],
        field_ui_schema: dict[str, dict],
    ) -> dict:
        grouped_fields = [field_name for fields in groups.values() for field_name in fields]
        ui_schema = {
            **{field_name: ui for field_name, ui in field_ui_schema.items() if ui},
            "ui:order": [*grouped_fields, *ungrouped_fields],
        }

        if groups:
            ui_schema["ui:groups"] = [
                {
                    "title": group,
                    "fields": fields,
                }
                for group, fields in groups.items()
            ]

        return ui_schema
