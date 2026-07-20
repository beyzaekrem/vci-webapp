import io
from abc import ABC as AbstractBaseClass
from abc import abstractmethod
from pathlib import Path
from typing import Any, Literal

import interceptor
from inputimeout import TimeoutOccurred, inputimeout
from PIL import Image

from controller.boolean_user_input import boolean_user_input
from controller.logging_config import logger

from .script_events import (
    AutomaticUserInputEvent,
    AutomaticUserInputEventWithResponse,
    DisplayImageEvent,
    InputEvent,
    LogEvent,
    ManualUserInputEvent,
    ManualUserInputEventWithResponse,
    ScriptEvent,
    UserBooleanInputEvent,
    UserBooleanInputEventWithResponse,
    UserInputEvent,
    UserInputEventWithResponse,
)
from .script_output import ScriptOutput
from .util.response_waiter import ResponseWaiter


def _default_choice_from_command(command: Any) -> bool:
    if isinstance(command, bool):
        return command
    return str(command).lower() not in {"n", "no", "false", "0"}


def _response_to_command(response: Any) -> str:
    if response is None:
        return ""
    if isinstance(response, bool):
        return "y" if response else "n"
    return str(response).lower()


InputType = Literal["boolean", "text"]


def _create_user_input_event(
    prompt: str | None,
    input_type: InputType,
    default_value: Any,
    runner_id: str | None,
    event_slot: str | None,
) -> InputEvent:
    if input_type == "boolean":
        return UserBooleanInputEvent(
            prompt or "",
            _default_choice_from_command(default_value),
            runner_id,
            event_slot,
        )
    if input_type == "text":
        return UserInputEvent(
            prompt,
            "" if default_value is None else str(default_value),
            runner_id,
            event_slot,
        )
    msg = f"Unsupported timeout input type: {input_type}"
    raise ValueError(msg)


class UserInterface(AbstractBaseClass):

    def __init__(self) -> None:
        # todo keep track of the interaction history here
        self.runner_id = None
        self.output = ScriptOutput()

    @abstractmethod
    def get_arg_mode(self) -> str:
        """
        Return the argument mode used for schema generation, parsing, and validation.
        """

    def set_runner_id(self, runner_id: str) -> None:
        """
        Set a unique id for the current execution.
        This is used to match the events the e.g. web app receives to the correct script execution that triggered them.
        TODO maybe move this to ScriptRunner and reference the ScriptRunner instance here so this is more clear
        """
        self.runner_id = runner_id

    def _add_event(self, event: ScriptEvent) -> None:
        self.output.add_event(event)

    def input(self, prompt: str | None = None, *, event_slot: str | None = None) -> str:
        """
        A simple interface for scripts to ask for user input as a string.
        """

        event = UserInputEvent(prompt, "", self.runner_id, event_slot)
        self._add_event(event)

        return_value = self._input(event)

        # add an event in the same slot that contains the user's response
        response_event = UserInputEventWithResponse(event, return_value)
        self._add_event(response_event)
        return return_value

    @abstractmethod
    def _input(self, event: UserInputEvent) -> str:
        """
        A simple interface for scripts to ask for user input as a string.
        """

    def _input_with_timeout(self, event: UserInputEvent, timeout_seconds: float | None) -> tuple[str | None, bool]:
        """
        Ask for user input and return whether the request timed out.
        Interfaces that can cancel pending waits should override this method.
        """
        return self._input(event), False

    @abstractmethod
    def _manual_timeout_input(self, event: ManualUserInputEvent) -> tuple[Any, bool]:
        """
        Ask for manual-mode timeout input.

        Returns the user response and whether the interface requested switching
        to automatic mode.
        """

    @abstractmethod
    def _automatic_timeout_input(self, event: AutomaticUserInputEvent) -> tuple[Any | None, bool, bool]:
        """
        Ask for automatic-mode timeout input.

        Returns the user response, whether the request timed out, and whether
        the interface requested switching to manual mode.
        """

    def timeout_input(
        self,
        wait_prompt: str = "Trigger Next image [Y,n]: ",
        timeout_prompt: str = "Auto triggering.... ",
        timeout_return: Any = "y",
        auto_trigger_enabled: bool = False,
        timeout_seconds: float | None = None,
        event_slot: str | None = None,
        input_type: InputType = "text",
    ) -> tuple[str, bool]:
        """
        Input prompt with optional timeout feature.

        Users can enter "a" at the wait prompt to enable automatic timeout
        responses, and "s" at the timeout prompt to stop automatic mode.
        """
        """
        TODO maybe add an event for switching between auto and manual mode
        So that the web app can display the current mode and have buttons for switching
        while CLI can switch by typing a and s as before
        """
        while True:  # loop to allow switching between auto and manual mode
            if auto_trigger_enabled:
                timeout_seconds = 3 if timeout_seconds is None else timeout_seconds
                input_event = _create_user_input_event(
                    timeout_prompt,
                    input_type,
                    timeout_return,
                    self.runner_id,
                    event_slot,
                )
                event = AutomaticUserInputEvent(
                    input_event,
                    timeout_seconds,
                    timeout_return,
                )
                self._add_event(event)

                response, timed_out, switch_mode = self._automatic_timeout_input(event)
                command = _response_to_command(timeout_return) if timed_out else _response_to_command(response)

                # user can respond with s to switch to manual mode,
                # or with a normal user input to trigger the next action in the script immediately without waiting for the timeout
                response_event = AutomaticUserInputEventWithResponse(event, command, switch_mode, timed_out)
                self._add_event(response_event)

                if switch_mode:
                    auto_trigger_enabled = False
                    continue
                # return because time out exceeded for this input (or user mistyped)
                return command, True

            input_event = _create_user_input_event(
                wait_prompt,
                input_type,
                timeout_return,
                self.runner_id,
                event_slot,
            )
            event = ManualUserInputEvent(input_event)
            self._add_event(event)

            command, switch_mode = self._manual_timeout_input(event)
            command = _response_to_command(command)

            response_event = ManualUserInputEventWithResponse(event, command, switch_mode)
            self._add_event(response_event)

            # user can respond with a to switch to auto mode,
            # or with a normal user input to trigger the next action in the script
            if switch_mode:
                auto_trigger_enabled = True
                continue
            # return because user provided input
            return command, False

    def boolean_user_input(self, prompt: str, default_choice: bool = True, event_slot: str | None = None) -> bool:
        event = UserBooleanInputEvent(prompt, default_choice, self.runner_id, event_slot)
        self._add_event(event)

        return_value = self._boolean_user_input(event)

        # add an event in the same slot that contains the user's response
        response_event = UserBooleanInputEventWithResponse(event, return_value)
        self._add_event(response_event)
        return return_value

    @abstractmethod
    def _boolean_user_input(self, event: UserBooleanInputEvent) -> bool:
        """
        A simple interface for scripts to ask for boolean user input (e.g., yes/no question).
        """
        # todo implement a wrapper function that uses this function and provides a timeout if we are waiting too long

    def log(self, *text: object, log_level: str | None = None, event_slot: str | None = None) -> None:
        """A simple interface for scripts to log text output, e.g. to the console"""
        content = "".join(str(value) for value in text)
        event = LogEvent(content, self.runner_id, log_level, event_slot)
        self._add_event(event)
        self._log(event)

    @abstractmethod
    def _log(self, event: LogEvent) -> None:
        """log something, e.g. to the console or log files"""

    def write_image(self, image_data: bytes, file_path: str, caption: str = "", event_slot: str | None = None) -> None:
        """A simple interface for scripts to write an image with a caption."""
        event = DisplayImageEvent(image_data, file_path, caption, self.runner_id, event_slot)
        self._add_event(event)
        self._write_image(event)

    @abstractmethod
    def _write_image(self, event: DisplayImageEvent) -> None:
        """write an image, e.g. in the web-app or save to disk and log the path."""

    def write_pil_image(
        self,
        image: Image.Image,
        file_path: str,
        caption: str = "",
        event_slot: str | None = None,
    ) -> None:
        """Encode and write a PIL image."""

        def _image_format_from_path(file_path: str) -> str:
            suffix = Path(file_path).suffix.lower()
            if suffix in {".jpg", ".jpeg"}:
                return "JPEG"
            if suffix == ".png":
                return "PNG"
            return suffix.removeprefix(".").upper() or "PNG"

        file_path = str(file_path)
        output_format = _image_format_from_path(file_path)
        image_to_write = image
        if output_format == "JPEG" and image.mode not in ("RGB", "L"):
            image_to_write = image.convert("RGB")

        buf = io.BytesIO()
        image_to_write.save(buf, format=output_format)
        buf.seek(0)
        self.write_image(buf.read(), file_path, caption, event_slot)

    def write_matplotlib_figure(self, fig, file_path: str, caption: str = "", event_slot: str | None = None) -> None:
        """A helper function to write a matplotlib figure."""
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        image_data = buf.read()
        self.write_image(image_data, file_path, caption, event_slot)

    # helper methods for logging:
    def debug(self, *text: object, event_slot: str | None = None) -> None:
        self.log(*text, log_level="debug", event_slot=event_slot)

    def info(self, *text: object, event_slot: str | None = None) -> None:
        self.log(*text, log_level="info", event_slot=event_slot)

    def warning(self, *text: object, event_slot: str | None = None) -> None:
        self.log(*text, log_level="warning", event_slot=event_slot)

    def error(self, *text: object, event_slot: str | None = None) -> None:
        self.log(*text, log_level="error", event_slot=event_slot)


class CLIInterface(UserInterface):

    def get_arg_mode(self) -> str:
        return "cli"

    def _input(self, event: UserInputEvent) -> str:
        return input(event.prompt)

    def _input_with_timeout(self, event: UserInputEvent, timeout_seconds: float | None) -> tuple[str | None, bool]:
        try:
            if timeout_seconds is None:
                return inputimeout(prompt=event.prompt or ""), False
            return inputimeout(prompt=event.prompt or "", timeout=timeout_seconds), False
        except TimeoutOccurred:
            return None, True

    def _manual_timeout_input(self, event: ManualUserInputEvent) -> tuple[str, bool]:
        prompt = f"{event.input_event.prompt}"  # TODO do we want "Press [a] to auto-trigger: " here?
        command = input(prompt).lower()
        return command, command == "a"

    def _automatic_timeout_input(self, event: AutomaticUserInputEvent) -> tuple[str | None, bool, bool]:
        try:
            prompt = f"{event.input_event.prompt} Press [s] to stop: "
            command = inputimeout(prompt=prompt, timeout=event.timeout_seconds).lower()
            return command, False, command == "s"
        except TimeoutOccurred:
            return None, True, False

    def _boolean_user_input(self, event: UserBooleanInputEvent) -> bool:
        return boolean_user_input(event.prompt, event.default_choice)

    def _log(self, event: LogEvent) -> None:
        if event.log_level is None:
            print(event.content)
        elif event.log_level.lower() == "debug":
            logger.debug(event.content)
        elif event.log_level.lower() == "info":
            logger.info(event.content)
        elif event.log_level.lower() == "warning":
            logger.warning(event.content)
        elif event.log_level.lower() == "error":
            logger.error(event.content)
        else:
            print(f"Unknown log level {event.log_level} for log message: {event.content}")

    def _write_image(self, event: DisplayImageEvent) -> None:
        """
        Save image to disk and log the path
        """
        filename = Path(event.file_path)
        with open(filename, "wb") as f:
            f.write(event.image_data)
        self.log(f"Image saved to {filename}")


class InterceptorConnectionInterface(UserInterface):
    # this is the interface that the ScriptRunner uses to send messages to the web-app via the interceptor connection.
    def __init__(self) -> None:
        super().__init__()
        self.interceptor_connections: list[interceptor.Connection] = []
        self.response_waiter = ResponseWaiter()

    def add_connection(self, interceptor_connection: interceptor.Connection) -> None:
        """
        Subscribe a client connection to output updates.
        Call this e.g. when a client opens another tab or reconnects.
        """
        if not any(connection is interceptor_connection for connection in self.interceptor_connections):
            self.interceptor_connections.append(interceptor_connection)

    def remove_connection(self, interceptor_connection: interceptor.Connection) -> None:
        """
        Remove a client connection from output updates.
        """
        self.interceptor_connections = [
            connection for connection in self.interceptor_connections if connection is not interceptor_connection
        ]

    def get_arg_mode(self) -> str:
        return "web"

    def receive_event_response(self, event_id: str, response) -> None:
        self.response_waiter.set_response(event_id, response)

    def cancel_pending_inputs(self) -> None:
        self.response_waiter.cancel_all()

    # already covered by _send_event from _add_event
    def _log(self, event: LogEvent) -> None:
        pass

    # already covered by _send_event from _add_event
    def _write_image(self, event: DisplayImageEvent) -> None:
        pass

    def _input(self, event: UserInputEvent) -> str:
        # Web Mode: Trigger UI input field and wait for bridge response
        response, _ = self.response_waiter.wait_for_response(event.event_id)
        return response

    def _input_with_timeout(self, event: UserInputEvent, timeout_seconds: float | None) -> tuple[str | None, bool]:
        # Web Mode: Trigger UI input field and wait for bridge response, with optional timeout
        return self.response_waiter.wait_for_response(event.event_id, timeout_seconds)

    def _manual_timeout_input(self, event: ManualUserInputEvent) -> tuple[str, bool]:
        response, _ = self.response_waiter.wait_for_response(event.event_id)
        command = _response_to_command(response)
        return command, command in {"a", "switch_to_auto"}

    def _automatic_timeout_input(self, event: AutomaticUserInputEvent) -> tuple[str | None, bool, bool]:
        response, timed_out = self.response_waiter.wait_for_response(event.event_id, event.timeout_seconds)
        if timed_out:
            return None, True, False

        command = _response_to_command(response)
        return command, False, command in {"s", "switch_to_manual"}

    def _boolean_user_input(self, event: UserBooleanInputEvent) -> bool:
        # Web Mode: Trigger UI button and wait for bridge response
        response, _ = self.response_waiter.wait_for_response(event.event_id)
        return response

    def _send_output_update(self) -> None:
        output_update = self.output.get_output_update()
        msg = output_update.__dict__
        msg["runner_id"] = self.runner_id
        pl = interceptor.Payload.FromDict(msg)
        for connection in list(self.interceptor_connections):
            connection.async_send(interceptor.MessageOut("OUTPUT_UPDATE", [pl]))

    def _add_event(self, event: ScriptEvent) -> None:
        super()._add_event(event)
        self._send_output_update()

    def trigger_output_update(self) -> None:
        """
        Triggers an output update to be sent to the web-app,
        e.g. call this when a client (re)connects to initially send the current state of the script output.
        """
        self._send_output_update()
