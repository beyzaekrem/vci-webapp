from collections.abc import Generator
from concurrent.futures import Future
from contextlib import contextmanager

import interceptor

from controller.components.connection_manager import ConnectionManager, ResponseCallback
from controller.output_writers import (
    CalibrationWriter,
    ImageWriter,
    PathStructure,
    PreviewWriter,
)
from controller.system_layout_reader import SystemLayoutReader
from web_app_integration.user_interface import UserInterface


class ControllerComponent:

    image_writer: ImageWriter
    preview_writer: PreviewWriter
    calibration_writer: CalibrationWriter
    system_layout: SystemLayoutReader

    path_structure: PathStructure
    _connection: ConnectionManager
    ui: UserInterface

    @property
    def camera_ids_by_server(self) -> list[list[str]]:
        return self._connection.camera_ids_by_server

    @property
    def all_camera_ids(self) -> list[str]:
        return self._connection.all_camera_ids

    @property
    def mono_is_active(self) -> bool:
        return len(self.cameras_of_type("M")) > 0

    @property
    def servernames(self) -> list[str]:
        return self._connection.servernames

    def cameras_of_type(self, type_prefix: str) -> list:
        return [camid for camid in self._connection.all_camera_ids if camid[0] == type_prefix]

    @staticmethod
    def create_message(path: str, parameters: dict | None = None) -> interceptor.MessageOut:
        if parameters is None:
            message = interceptor.MessageOut(path)
        else:
            parameters = interceptor.Payload.FromDict(parameters)
            message = interceptor.MessageOut(path, [parameters])
        return message

    @staticmethod
    def get_dict_from_responses(responses: list[interceptor.MessageIn], payload_index: int = 0) -> list[dict] | dict:
        if isinstance(responses, list):
            return [response.payload[payload_index].ToDict() for response in responses]
        return responses.payload[payload_index].ToDict()

    def send(
        self, path: str, parameters: dict | None = None, *, callback: ResponseCallback | None = None, wait: bool = True
    ) -> list[any] | Exception | Future:
        message = self.create_message(path, parameters=parameters)
        return self._connection.send_message(message, callback=callback, wait=wait)

    def send_message(
        self, message: interceptor.MessageOut, *, callback: ResponseCallback | None = None, wait: bool = True
    ) -> list[any] | Exception | Future:
        return self._connection.send_message(message, callback=callback, wait=wait)

    def request_dict(self, path: str, parameters: dict | None = None) -> list[dict]:
        """creates message with path and optional parameters.
        Sends the message and returns the first payload element parsed as dict to you.

        Args:
            path (str): API endpoint path
            parameters (dict | None, optional): optional parameters, depending on API endpoint. Defaults to None.

        Returns:
            list[dict]: dict responses per server. Dict strucutre depends on API endpoint and parameters.
        """
        responses = self.send(path, parameters=parameters)
        return self.get_dict_from_responses(responses)

    @contextmanager
    def filter_connections(self, connection_indeces: list[int]) -> Generator:
        """Filters the active connections (by indeces) for the duration of the context.
        Every call within the context, will be passed only to the selected servers."""
        with self._connection.filter_connections(connection_indeces):
            yield
