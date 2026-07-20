import threading
from collections.abc import Callable


class Runnable:
    """Run a callable in a managed background thread."""

    def __init__(
        self,
        target: Callable,
        on_error: Callable[[Exception], None] | None = None,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        """Create a runnable around a target callable.
        The fucntion "target" will be started in background thread when start is called.
        stop, attemps to stop the function.

        Args:
            target (Callable): target function to run in a background thread.
            on_error (Callable[[Exception], None] | None, optional): function to call if target crashed. Defaults to None.
            on_finished (Callable[[], None] | None, optional): function to call when target finishes normally. Defaults to None.
        """
        self.target = target
        self.on_error = on_error
        self.on_finished = on_finished
        self.running = False
        self._thread: threading.Thread | None = None
        self._stop_requested = threading.Event()
        self._running_lock = threading.Lock()

    @property
    def stop_requested(self) -> bool:
        """Return whether a cooperative stop has been requested."""
        return self._stop_requested.is_set()

    def start(self, *args, **kwargs) -> None:
        """Start the target in a background thread."""
        with self._running_lock:
            if self.running:
                raise RuntimeError("Runnable is already running")
            self._stop_requested.clear()
            self.running = True

        self._thread = threading.Thread(target=self._run_in_thread, args=args, kwargs=kwargs, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Request cooperative cancellation."""
        self._stop_requested.set()

    def _run_in_thread(self, *args, **kwargs) -> None:
        try:
            self.run(*args, **kwargs)
        except Exception:
            pass

    def run(self, *args, **kwargs) -> None:
        """Run the target synchronously with lifecycle bookkeeping."""
        with self._running_lock:
            if self.running and threading.current_thread() is not self._thread:
                raise RuntimeError("Runnable is already running")
            if not self.running:
                self.running = True
                self._stop_requested.clear()

        try:
            self.target(*args, **kwargs)
        except Exception as e:
            if self.on_error is not None:
                self.on_error(e)
            raise
        finally:
            with self._running_lock:
                self.running = False
            if self.on_finished is not None:
                self.on_finished()
