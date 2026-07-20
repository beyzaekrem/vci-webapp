from __future__ import annotations

import asyncio
import traceback
from collections import defaultdict
from dataclasses import dataclass

import interceptor


@dataclass
class Connection:
    """Wraps an interceptor Client
    Adds meta info: pretty servername, ip_adress
    """

    servername: str
    ip_address: str
    client: interceptor.Client

    def __init__(self, servername: str, ip_address: str, port: int) -> None:
        """connects to an interceptor server on the given ip_adress and port.

        Args:
            servername (str): name for server. Can be freely choosen.
            ip_address (str): ip v4 address of the server.
            port (int): port where interceptor server is running.
        Raises:
            interceptor.NotConnectedError
        """
        client = interceptor.Client(host=ip_address, port=int(port))
        client.run(blocking=False)
        client.wait_for_connection(1000)  # throws NotConnectedError

        self.client = client
        self.servername = servername
        self.ip_address = ip_address

    def send_message(self, message: interceptor.MessageOut, timeout_seconds: int = 60) -> interceptor.MessageIn:
        """Send a message and blocks while we wait for the response.
        This function may be used when you want to send a message only to one connection.
        When targeting mutliple Connections, use send_message_async.

        Args:
            message (interceptor.MessageOut): Message to be send to server.

        Raises:
            RequestError: something happened on the server. Wraps possible Network erros:
                * interceptor.PathHandlerFailedError: Server encountered an error
                * interceptor.NotConnectedError: The Server is not connected (anymore)
                * RuntimeError: other error
                * TimeoutError: the server took to long to respond.


        Returns:
            interceptor.MessageIn: response
        """
        try:
            promise = self.client.async_send(message)
            response = promise.wait_for(timeout_seconds)
        except Exception as e:
            raise RequestError(original_error=e, connection=self, path=message.path, source="Server") from e
        return response

    async def send_message_async(
        self, message: interceptor.MessageOut, timeout_seconds: int = 60
    ) -> interceptor.MessageIn:
        """Sends a message asynconiously. When sending a message to mutliple connections, this function should be used.

        Args:
            message (interceptor.MessageOut): Message to be send. (path + optional payload)

        Raises:
            RequestError: something happened on the server. Wraps possible Network erros:
                * interceptor.PathHandlerFailedError: Server encountered an error
                * interceptor.NotConnectedError: The Server is not connected (anymore)
                * RuntimeError: other error
                * TimeoutError: the server took to long to respond.

        Returns:
            interceptor.MessageIn: response
        """
        promise = self.client.async_send(message)
        # sleep so the message may be sent to other servers (when multiple connetions are open) before we check for response
        await asyncio.sleep(0.001)

        for _ in range(timeout_seconds):  # max wait time.
            try:
                # Blocks for 1 seconds while it waits. Throws TimeoutError if the response isn't ready in that time
                response = promise.wait_for(1)
                if response is not None:
                    return response
            # we let the timeout error pass and just try again. We make our own timeout error after 60 tries
            except interceptor.TimeoutError:  # noqa: PERF203
                await asyncio.sleep(0.001)

            # warp Errors thrown through Network with RequestError to add the path and connection info
            except Exception as e:
                raise RequestError(original_error=e, connection=self, path=message.path, source="Server") from e

        msg = f"Timed out after {timeout_seconds}s"
        raise RequestError(TimeoutError(msg), self, message.path, source="Server")


class RequestError(Exception):
    """Wraps an error thrown by a Connection"""

    def __init__(self, original_error: Exception, connection: Connection, path: str, source: str = "Server") -> None:
        self.original_error = original_error
        self.connection = connection
        self.path = path
        self.source = source
        super().__init__(f"[{source}] {connection.servername} ({path}): {original_error}")


class AggregatedRequestError(RuntimeError):
    """
    Warps a list of RequestErrors, minimizing output to reflect when the same error is thrown by different servers.

    Raised when one or more RequestErrors occur during a message request.
    The Errors may occur on the Server side (via Network) or during the (local) callback function.

    Attributes:
        errors (list[RequestError]): The raw list of individual Erros.
        path (str): The request path that triggered the failures.
    """

    def __init__(self, errors: list[RequestError], total_response_count: int) -> None:
        self.errors = errors

        unique_paths = {err.path for err in errors}
        if len(unique_paths) > 1:
            self.path = "MISMATCHED_PATHS"
            path_context = f"paths {', '.join(unique_paths)}"
        else:
            self.path = next(iter(unique_paths)) if unique_paths else "unknown"
            path_context = f"path {self.path}"
        # we shoudln't get mismatched paths with how send() dispatches messages but you never know

        # Build the signature-based summary internally
        signatures = defaultdict(list)
        for err in errors:
            if err.source == "Server":
                full_traceback = ""
            else:
                # adds full(local) traceback when the error was caused by callback/non Server
                full_traceback = "\n" + "".join(traceback.format_exception(type(err), err, err.__traceback__))
            sig = f"[{err.source}] {type(err.original_error).__name__}: {err.original_error} {full_traceback}"
            signatures[sig].append(err.connection.servername)

        summary = [f"Request failed for {path_context}:"]
        for sig, servers in signatures.items():
            if len(servers) == total_response_count:
                loc = "ALL Servers"
            else:
                loc = f"{len(servers)} Servers ({', '.join(servers)})"
            summary.append(f"  - {loc} raised {sig}")

        super().__init__("\n".join(summary))

    def __repr__(self) -> str:
        return f"<AggregatedRequestError: {len(self.errors)} failures on {self.path}>"
