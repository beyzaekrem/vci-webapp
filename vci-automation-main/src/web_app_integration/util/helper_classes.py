from __future__ import annotations

import base64
from collections.abc import Mapping, Sequence
from typing import Any, cast

from pydantic import BaseModel, Field, create_model
from pydantic.fields import FieldInfo


class ClientSafeClass:
    """
    A class that provides a method to convert its attributes to a client-safe format, e.g., by encoding bytes to base64 strings.
    This is useful for preparing data to be sent to the web-app, which may not be able to handle certain data types like bytes.
    """
    def to_client_safe_dict(self) -> dict[str, Any]:
        return {key: self._convert_to_client_safe(value) for key, value in self.__dict__.items()}

    @classmethod
    def _convert_to_client_safe(cls, value: Any) -> Any:
        if isinstance(value, ClientSafeClass):
            return value.to_client_safe_dict()
        if isinstance(value, bytes):
            return base64.b64encode(value).decode("ascii")
        if isinstance(value, dict):
            return {key: cls._convert_to_client_safe(nested_value) for key, nested_value in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._convert_to_client_safe(item) for item in value]
        return value

    @classmethod
    def dict_to_client_safe(cls, data: Mapping[str, ClientSafeClass]) -> dict[str, dict[str, Any]]:
        return {key: value.to_client_safe_dict() for key, value in data.items()}

    @classmethod
    def list_to_client_safe(cls, data: Sequence[ClientSafeClass]) -> list[dict[str, Any]]:
        return [item.to_client_safe_dict() for item in data]


class PydanticModelGeneratingClass(ClientSafeClass):
    """
    A class that can generate a pydantic model based on its attributes and their types.
    Uses the client-safe dict representation of the class for generating the model,
    so that the generated model is compatible with the data that will be sent to the web-app.
    """

    def get_pydantic_field(self) -> tuple[Any, FieldInfo]:
        """
        Return a pydantic field type and field metadata for this event,
        to be used by the web-app for dynamic form generation and validation.
        You very likely do not need to override this,
        override get_output_field_info instead.
        """
        output_model = self._create_pydantic_model_from_output()
        return output_model, self.get_output_field_info()

    def get_output_field_info(self) -> FieldInfo:
        """
        Return the pydantic FieldInfo for this event.
        Override this in child classes if you want to provide
        a custom title, description, or other metadata that should be
        present in the **json schema** for this event's output.
        """
        return Field()


    def _create_pydantic_model_from_output(self) -> type[BaseModel]:
        fields = {
            key: (self._get_pydantic_type(value), Field())
            for key, value in self.to_client_safe_dict().items()
        }
        return create_model(f"{type(self).__name__}Output", **cast(Any, fields))

    @staticmethod
    def _get_pydantic_type(value: Any) -> Any:
        if value is None:
            return Any
        if isinstance(value, bool):
            return bool
        if isinstance(value, int):
            return int
        if isinstance(value, float):
            return float
        if isinstance(value, str):
            return str
        if isinstance(value, list):
            return list[Any]
        if isinstance(value, dict):
            return dict[str, Any]
        return Any

    @staticmethod
    def _dict_to_pydantic_model(data: Mapping[str, PydanticModelGeneratingClass], model_name: str) -> type[BaseModel]:
        fields = {}
        for key, value in data.items():
            model_type, field_info = value.get_pydantic_field()
            fields[key] = (model_type, field_info)
        return create_model(model_name, **cast(Any, fields))

    @staticmethod
    def dict_to_json_schema(
        data: Mapping[str, PydanticModelGeneratingClass],
        title: str = "Script Output",
    ) -> dict:
        model = PydanticModelGeneratingClass._dict_to_pydantic_model(data, "ScriptOutput")
        schema = model.model_json_schema()
        return schema
