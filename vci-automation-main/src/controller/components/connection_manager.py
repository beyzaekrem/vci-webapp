from __future__ import annotations

import asyncio
import threading
from collections import Counter
from collections.abc import Callable, Generator
from concurrent.futures import Future
from contextlib import contextmanager
from typing import TypeVar

import interceptor

from controller.components.connection import AggregatedRequestError, Connection, RequestError
from controller.exceptions import NoServersRunning
from controller.system_layout_reader import SystemLayoutReader  # noqa: TC001
from web_app_integration.user_interface import UserInterface

# Define T as the Return Type of the callback
T = TypeVar("T")


ResponseCallback = Callable[[interceptor.MessageIn, Connection], T]


class CaptureServerConnection(Connection):
    camera_ids: list[str] | None = None


# Connection Manager is part of the shared context that all modules can use
class ConnectionManager:
    """Handles the connection to multiple capture servers"""

    def __init__(self, user_interface: UserInterface) -> None:
        self.connections: list[CaptureServerConnection] = []
        self.all_camera_ids = []
        self.ui = user_interface

    @property
    def servernames(self) -> list[str]:
        return [conn.servername for conn in self.connections]

    @property
    def camera_ids_by_server(self) -> list[list[str]]:
        return [conn.camera_ids for conn in self.connections]

    @contextmanager
    def filter_connections(self, connection_indeces: list[int]) -> Generator:
        """Filters the active connections (by indeces) for the duration of the context.
        Every call within the context, will be passed only to the selected servers."""
        original_connections = self.connections
        if connection_indeces is None:
            msg = "connection_indeces cannot be None"
            raise TypeError(msg)
        try:
            self.connections = [
                original_connections[i] for i in connection_indeces if 0 <= i < len(original_connections)
            ]
            self._update_all_camera_ids()  # sets all_camera_ids from selected connections.
            yield  # run user calls in context.
        finally:
            # always restore orignal state even if some error happens during the context.
            self.connections = original_connections
            self._update_all_camera_ids()  # restores all_camera_ids

    def connect(self, server_list: list[int], system_layout: SystemLayoutReader) -> None:
        self.connections: list[CaptureServerConnection] = []

        self.ui.debug(f"Connecting to servers: {server_list}")
        if isinstance(server_list, int):
            server_list = [server_list]
        for server_id in server_list:
            try:
                address = system_layout.get_server_address(server_id)
                servername = system_layout.get_server_name(server_id)
                self.ui.debug(f"Trying {servername} {address}")

                attempt_connection = CaptureServerConnection(servername, *address)
                self.connections.append(attempt_connection)

                self.ui.debug(f"{servername} connected")
            except interceptor.NotConnectedError as e:  # noqa: PERF203
                self.ui.warning(f"{servername}: {e}")
        self.ui.info(f"connected servers: {self.servernames} ({len(self.connections)})")
        if len(self.connections) == 0:
            msg = "no servers running!!!"
            raise NoServersRunning(msg)

        self.get_camera_ids()

    def get_camera_ids(self) -> list[str]:
        def get_camera_ids_from_responses(
            response: interceptor.MessageOut, connection: CaptureServerConnection
        ) -> None:
            camera_info: dict = response.payload[0].ToDict()
            camera_ids = camera_info["camera_ids"]
            self.ui.debug(f"{connection.servername} Cameras found: {camera_ids}")

            connection.camera_ids = camera_ids
            if len(camera_ids) == 0:
                self.ui.warning(f"{connection.servername} has no connected cameras")

        message = interceptor.MessageOut("GET_CAMERA_INFO")
        self.send_message(message, callback=get_camera_ids_from_responses)

        self._update_all_camera_ids()

        cnt = Counter([cam_id[0] for cam_id in self.all_camera_ids])
        self.ui.info(f"{len(self.all_camera_ids)} cameras connected: {cnt}")
        return self.all_camera_ids

    def _update_all_camera_ids(self) -> None:
        self.all_camera_ids = []
        for conn in self.connections:
            self.all_camera_ids.extend(conn.camera_ids or [])

    def disconnect(self) -> None:
        for connection in self.connections:
            connection.client.stop()

    def send_message(
        self, message: interceptor.MessageOut, *, callback: ResponseCallback | None = None, wait: bool = True
    ) -> list[interceptor.MessageIn] | Future | list[any]:
        """Sends a message to all connected clients.

        If a callback function is provided, it is executed as soon as each individual response arrives.
        The return value of the callbacks are collected and returned.

        When no callback is provided, a list of the respones (interceptor.MessageIn) is returned instead.

        In blocking mode (wait=True): blocks until all polls (and callbacks) are done.
        In none-blocking (wait=False): returns a concurrent.futures.Future, containing the function result.

        Args:
            message (interceptor.MessageOut): The message to send. Has a path and optional parameters.
            callback (Callable[[MessageIn, Connection], T] | None, optional): A function to process each response as it arrives.
            Must accept exactly two arguments:
                - response (interceptor.MessageIn): The reponse from one server
                - connection (Connection): The connection object of the responding server.
                The return value of this callback will be collected in the final list.
            wait (bool, optional): If True, blocks until all repsonses are processed. Defaults to True.

        Returns:
            list[interceptor.MessageIn] | Future | list[any]: _description_

        Raises:
            AggregatedRequestError: An error occured in one or more servers on in the local callback function run.
        """

        async def send_all() -> list[interceptor.MessageOut | Exception] | list[any | Exception]:
            async def _single_request(connection: Connection) -> any:
                response = await connection.send_message_async(message)
                # callback is automatically skipped when response was an Error
                if callback:
                    try:
                        return callback(response, connection)
                    # warp local Errors to add info.
                    except Exception as e:
                        raise RequestError(
                            original_error=e, connection=connection, path=message.path, source="Callback"
                        ) from e
                return response

            tasks = [_single_request(connection) for connection in self.connections]
            return await asyncio.gather(*tasks, return_exceptions=True)
            # asyncio.gather catches exception (from network or from callback) and puts in it respones list.

        if wait:
            results = asyncio.run(send_all())
            self.error_check(results)
            return results
        # non-blocking, return a concurrent.futures.Future
        outer_future: Future = Future()

        def runner() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(send_all())
                outer_future.set_result(result)
            except Exception as e:
                outer_future.set_exception(e)
            finally:
                loop.close()

        threading.Thread(target=runner, daemon=True).start()
        return outer_future

    def error_check(self, results: list[any]) -> None:
        errors: list[RequestError] = [r for r in results if isinstance(r, RequestError)]
        if not errors:
            return
        raise AggregatedRequestError(errors, len(results))
