from pathlib import Path
from typing import Any

from .script_events import ScriptEvent
from .util.helper_classes import ClientSafeClass, PydanticModelGeneratingClass
from .util.ui_schema_class import UISchemaGeneratingClass


class OutputUpdate:
    output: dict[str, Any]
    output_json_schema: dict
    output_ui_schema: dict[str, Any]

    def __init__(
        self,
        output: dict[str, Any],
        output_json_schema: dict,
        output_ui_schema: dict[str, Any],
        full_event_history: list[dict[str, Any]]
    ) -> None:
        self.output = output
        self.output_json_schema = output_json_schema
        self.output_ui_schema = output_ui_schema
        self.full_event_history = full_event_history

class ScriptOutput:
    def __init__(self) -> None:
        self._event_history: list[ScriptEvent] = []
        self._events_in_slots: dict[str, ScriptEvent] = {}

    def add_event(self, event: ScriptEvent) -> None:
        self._event_history.append(event)

        if event.event_slot is not None:
            # if the event has a slot, we update the current output state for this slot
            self._events_in_slots[event.event_slot] = event

        # write output and output schema to file for debugging
        # self._write_debug_files()

    def get_output_update(self) -> OutputUpdate:
        return OutputUpdate(
            output=ClientSafeClass.dict_to_client_safe(self._events_in_slots),
            output_json_schema=PydanticModelGeneratingClass.dict_to_json_schema(self._events_in_slots),
            output_ui_schema=UISchemaGeneratingClass.dict_to_ui_schema(self._events_in_slots),
            full_event_history=ClientSafeClass.list_to_client_safe(self._event_history)
        )


    def _write_debug_files(self) -> None:
        outputs = self.get_output_update().__dict__
        # iterate over dict
        for key, value in outputs.items():
            output_path = Path(f"./{key}.json")
            import json
            with open(output_path, "w") as f:
                f.write(json.dumps(value, indent=4))
