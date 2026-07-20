import time
import uuid
from abc import ABC
from typing import Any, ClassVar

from pydantic import Field
from pydantic.fields import FieldInfo

from .util.helper_classes import PydanticModelGeneratingClass
from .util.ui_schema_class import UISchemaGeneratingClass


class ScriptEvent(ABC, UISchemaGeneratingClass, PydanticModelGeneratingClass):
    output_ui_schema: ClassVar[dict[str, Any]] = {
        # "ui:readonly": True,
        # do not render metadata fields in the ui by default
        "type": {
            "ui:widget": "hidden",
        },
        "timestamp": {
            "ui:widget": "hidden",
        },
        "runner_id": {
            "ui:widget": "hidden",
        },
        "event_id": {
            "ui:widget": "hidden",
        },
        "event_slot": {
            "ui:widget": "hidden",
        },
        "ui:field": "script_event",  # tells RJSF to use custom fields for rendering ScriptEvents
    }

    def __init__(self, event_type: str, runner_id: str | None, event_slot: str | None) -> None:
        self.type = event_type
        self.timestamp = time.time()
        self.runner_id = runner_id
        self.event_id = f"{runner_id}_{uuid.uuid4().hex}"  # unique event id based on runner_id and timestamp
        self.event_slot = event_slot


class LogEvent(ScriptEvent):
    output_ui_schema: ClassVar[dict[str, Any]] = {
        "content": {
            "ui:widget": "textarea",
        },
        "log_level": {
            "ui:widget": "hidden",
        },
    }
    content: str
    log_level: str | None = None

    def __init__(self, content: str, runner_id: str | None, log_level: str | None, event_slot: str | None) -> None:
        super().__init__("LOG", runner_id, event_slot)
        self.content = content
        self.log_level = log_level


class UserBooleanInputEvent(ScriptEvent):
    def __init__(self, prompt: str, default_choice: bool, runner_id: str | None, event_slot: str | None) -> None:
        super().__init__("USER_BOOLEAN_INPUT", runner_id, event_slot)
        self.prompt = prompt
        self.default_choice = default_choice

    def get_output_field_info(self) -> FieldInfo:
        return Field(
            description="Latest boolean input request for this UI slot.",
        )


class UserBooleanInputEventWithResponse(UserBooleanInputEvent):
    def __init__(self, inputEvent: UserBooleanInputEvent, user_response: bool):
        super().__init__(inputEvent.prompt, inputEvent.default_choice, inputEvent.runner_id, inputEvent.event_slot)
        self.type = "USER_BOOLEAN_INPUT_RESPONSE"
        self.user_response = user_response


class UserInputEvent(ScriptEvent):
    def __init__(self, prompt: str | None, default_value: str, runner_id: str | None, event_slot: str | None) -> None:
        super().__init__("USER_INPUT", runner_id, event_slot)
        self.prompt = prompt
        self.default_value = default_value

    def get_output_field_info(self) -> FieldInfo:
        return Field(
            description="Latest input request for this UI slot.",
        )


class UserInputEventWithResponse(UserInputEvent):
    def __init__(self, inputEvent: UserInputEvent, user_response: str):
        super().__init__(inputEvent.prompt, inputEvent.default_value, inputEvent.runner_id, inputEvent.event_slot)
        self.type = "USER_INPUT_RESPONSE"
        self.user_response = user_response


InputEvent = UserBooleanInputEvent | UserInputEvent


class ManualUserInputEvent(ScriptEvent):
    def __init__(self, input_event: InputEvent) -> None:
        super().__init__("MANUAL_USER_INPUT", input_event.runner_id, input_event.event_slot)
        self.input_event = input_event


class ManualUserInputEventWithResponse(ManualUserInputEvent):
    def __init__(self, event: ManualUserInputEvent, user_response: Any, switch_mode: bool):
        super().__init__(event.input_event)
        self.type = "MANUAL_USER_INPUT_RESPONSE"
        self.user_response = user_response
        self.switch_mode = switch_mode


class AutomaticUserInputEvent(ScriptEvent):
    def __init__(
        self,
        input_event: InputEvent,
        timeout_seconds: float,
        timeout_return: Any,
    ) -> None:
        super().__init__("AUTOMATIC_USER_INPUT", input_event.runner_id, input_event.event_slot)
        self.input_event = input_event
        self.timeout_seconds = timeout_seconds
        self.timeout_return = timeout_return


class AutomaticUserInputEventWithResponse(AutomaticUserInputEvent):

    def __init__(
        self,
        event: AutomaticUserInputEvent,
        user_response: Any,
        switch_mode: bool,
        timed_out: bool,
    ):
        super().__init__(event.input_event, event.timeout_seconds, event.timeout_return)
        self.type = "AUTOMATIC_USER_INPUT_RESPONSE"
        self.user_response = user_response
        self.switch_mode = switch_mode
        self.timed_out = timed_out


class DisplayImageEvent(ScriptEvent):
    output_ui_schema: ClassVar[dict[str, Any]] = {
        "image_data": {
            "ui:widget": "image",
        },
        "caption": {
            "ui:widget": "hidden",
        },
        "file_path": {
            "ui:widget": "hidden",
        },
    }

    def __init__(
        self,
        image_data: bytes,
        file_path: str,
        caption: str,
        runner_id: str | None,
        event_slot: str | None,
    ) -> None:
        super().__init__("DISPLAY_IMAGE", runner_id, event_slot)
        self.image_data = image_data
        self.caption = caption
        self.file_path = file_path

    def get_output_field_info(self) -> FieldInfo:
        return Field(
            description=self.caption,
            title="Image Payload",
        )
