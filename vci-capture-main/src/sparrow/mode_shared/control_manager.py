import functools
from collections.abc import Callable

from sparrow.gibbs_wrapper import interceptor
from sparrow.modes.handler_exceptions import (
    ControlTakenError,
)
from sparrow.utils import logger


class ControlManager:
    _control_connection: interceptor.Connection = None

    @property
    def control_is_taken(self) -> bool:
        return self._control_connection is not None

    def protected_path(self) -> Callable:
        """
        A decorator that enforces exclusive control over API paths.

        Since the server manages physical hardware and can perform long tasks like
        capturing to disk, it is stateful. When multiple clients connect, they
        can interfere with each other by aborting tasks or changing modes, which
        leads to unexpected behaviors and errors. To stop this, relevant API paths
        must be protected with this decorator. For example: starting/stopping cameras,
        setting parameters or setting up a task.

        Simply put: If your client-script was running something, which paths should other
        people *not* be able to call to avoid breaking your work?

        **Logic:**
        The first client-connection to call a protected_path is automatically assigned as the
        `control_connection`. Until they disconnect or call RELEASE_CONTROL, they
        are the only connection allowed to call protected_paths.
        Alternatively a connection may explicitly assume control via TAKE_CONTROL.

        **Example:**
        ```python
        @interceptor.path_handler("START")
        @CONTROL_MANAGER.protected_path() # order matters!
        def _path_start(self, message: interceptor.MessageIn) -> None:
            # Only the controller can reach this code
            CAMERA_MANAGER.start_cameras()
            message.Acknowledge()
        ```

        Returns:
            Callable: A decorator that wraps the target API path function.

        Raises:
            ControlTakenError: Request is blocked, another connection has control.
        """

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(instance: any, message: any, *args, **kwargs) -> Callable:  # noqa: ANN002, ANN003
                # Block if someone else is in control
                if self._control_connection is not None and self._control_connection != message.connection():
                    logger.info(f"ControlManager: Request {message.path} blocked. Another Client is in control.")
                    raise ControlTakenError

                # Assign control if it's currently free
                if self._control_connection is None:
                    self._control_connection = message.connection()
                    logger.info(f"ControlManager: Control assigned to: {self._control_connection.endpoint_address} via {message.path}")

                # Execute requested path function
                return func(instance, message, *args, **kwargs)

            return wrapper

        return decorator

    def take_control(self, connection: interceptor.Connection, *, force: bool = False) -> None:
        """
        Gives control to the connection if it's free or if force is True.

        Raises:
             ControlTakenError
        """
        if self.control_is_taken:
            if self._control_connection == connection:
                logger.info("ControlManager: take control called. Connection was already in control.")
            elif force:
                self._control_connection = connection
                logger.info(f"ControlManager: Control assigned to: {self._control_connection} via forced take_control")
            else:
                logger.info("ControlManager: take control blocked. Another connection is in control")
                raise ControlTakenError
        else:
            self._control_connection = connection
            logger.info(f"ControlManager: Control assigned to: {self._control_connection} via take_control")

    def attempt_release_control(self, connection: interceptor.Connection) -> None:
        """Releases control if the passed connection has control."""
        if self._control_connection == connection:
            self._control_connection = None
            logger.info("ControlManager: Control released. Controlling connection disconnected.")

    def release_control(self, connection: interceptor.Connection, *, force: bool = False) -> None:
        """
        Releases control if the connection has it or if force is True

        Raises:
             ControlTakenError
        """
        if self.control_is_taken:
            if self._control_connection == connection:
                self._control_connection = None
                logger.info(f"ControlManager: Control released {self._control_connection} via release_control")
            elif force:
                self._control_connection = None
                logger.info(
                    f"ControlManager: Another connections control was released {self._control_connection} via forced \
                    release_control"
                )
            else:
                logger.info("ControlManager: Control release blocked. Another connection is in control")
                raise ControlTakenError
        else:
            logger.info("ControlManager: Control release called. Nothing happend, no connection was in control.")


CONTROL_MANAGER = ControlManager()
"""Shared ControlManager instance. Manages access to protected API calls
to guard against interference between different client-connections."""
