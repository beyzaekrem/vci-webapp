# noqa: INP001, S101

from typing import Any

from web_app_integration.script_events import ManualUserInputEvent, UserBooleanInputEvent, UserInputEvent
from web_app_integration.script_output import ScriptOutput
from web_app_integration.user_interface import UserInterface


class _TimeoutInputTestInterface(UserInterface):
    def __init__(self, response) -> None:
        super().__init__()
        self.response = response
        self.manual_event = None
        self.automatic_event = None

    def get_arg_mode(self) -> str:
        return "test"

    def _input(self, event: UserInputEvent) -> str:
        return ""

    def _manual_timeout_input(self, event: ManualUserInputEvent) -> tuple[Any, bool]:
        self.manual_event = event
        return self.response, False

    def _automatic_timeout_input(self, event) -> tuple[Any, bool, bool]:
        self.automatic_event = event
        return self.response, False, False

    def _boolean_user_input(self, event: UserBooleanInputEvent) -> bool:
        return True

    def _log(self, event) -> None:
        pass

    def _write_image(self, event) -> None:
        pass


def test_manual_input_event_contains_nested_boolean_input_event():
    input_event = UserBooleanInputEvent("Trigger Next image [Y,n]: ", True, "runner", "slot")
    event = ManualUserInputEvent(input_event)

    assert event.input_event is input_event
    assert event.input_event.type == "USER_BOOLEAN_INPUT"


def test_script_output_serializes_nested_input_event():
    output = ScriptOutput()
    input_event = UserBooleanInputEvent("Trigger Next image [Y,n]: ", True, "runner", "slot")

    output.add_event(ManualUserInputEvent(input_event))
    update = output.get_output_update()

    assert update.output["slot"]["type"] == "MANUAL_USER_INPUT"
    assert update.output["slot"]["input_event"]["type"] == "USER_BOOLEAN_INPUT"
    assert update.output["slot"]["input_event"]["default_choice"] is True


def test_timeout_input_defaults_to_boolean_input_event():
    ui = _TimeoutInputTestInterface(False)
    ui.set_runner_id("runner")

    command, auto_trigger_enabled = ui.timeout_input(event_slot="slot")

    assert command == "n"
    assert auto_trigger_enabled is False
    assert isinstance(ui.manual_event.input_event, UserBooleanInputEvent)


def test_timeout_input_can_use_text_input_event():
    ui = _TimeoutInputTestInterface("custom")
    ui.set_runner_id("runner")

    command, auto_trigger_enabled = ui.timeout_input(event_slot="slot", input_type="text")

    assert command == "custom"
    assert auto_trigger_enabled is False
    assert isinstance(ui.manual_event.input_event, UserInputEvent)
    assert not isinstance(ui.manual_event.input_event, UserBooleanInputEvent)
