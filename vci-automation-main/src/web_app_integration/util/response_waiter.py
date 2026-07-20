import threading
from typing import Any


class ResponseWaiterCancelled(Exception):
    """Raised when pending response waits are cancelled."""


_CANCELLED = object()


class ResponseWaiter:
    """
    Utility class for waiting for responses to events in a thread-safe way.
    Each event is identified by a unique event_id string. When a thread wants to wait for a response,
    it creates a threading.Event and stores it in a dictionary along with the event_id. When another thread
    receives the response, it looks up the event_id in the dictionary, sets the response value, and unblocks
    the waiting thread.
    """

    def __init__(self) -> None:
        self._pending_responses = {}
        self._pending_responses_lock = threading.Lock()

    def create_wait_event(self, event_id: str) -> threading.Event:
        """
        Create a threading.Event for the given event_id and store it in the pending responses dictionary.
        Returns the created Event which can be waited on.
        """
        wait_for_response = threading.Event()
        with self._pending_responses_lock:
            self._pending_responses[event_id] = {"event": wait_for_response, "response": None}
        return wait_for_response

    def wait_for_response(self, event_id: str, timeout: float | None = None) -> tuple[Any, bool]:
        """
        Wait for a response for the given event_id. Returns a tuple of (response, timed_out).
        If the wait times out, response will be None and timed_out will be True.
        """
        wait_for_response = self.create_wait_event(event_id)

        response_received = wait_for_response.wait(timeout)
        if not response_received:
            with self._pending_responses_lock:
                self._pending_responses.pop(event_id, None)
            return None, True

        response = self.get_response(event_id)
        if response is _CANCELLED:
            raise ResponseWaiterCancelled

        return response, False

    def set_response(self, event_id: str, response) -> bool:
        """
        Set the response for the given event_id and unblock the waiting thread.
        Returns True if a waiting thread was unblocked, or False if no pending response was found for the event_id.
        """
        with self._pending_responses_lock:
            pending_response = self._pending_responses.get(event_id)
            if pending_response is None:
                return False
            if pending_response["event"].is_set():
                return False

            pending_response["response"] = response  # set the response value
            pending_response["event"].set()  # unblock the waiting thread
            return True

    def cancel_all(self) -> None:
        """
        Cancel all pending response waits and unblock their waiting threads.
        """
        with self._pending_responses_lock:
            pending_responses = list(self._pending_responses.values())
            for pending_response in pending_responses:
                pending_response["response"] = _CANCELLED
                pending_response["event"].set()

    def get_response(self, event_id: str):
        """
        Get the response for the given event_id. This should only be called after wait_for_response unblocks.
        """
        with self._pending_responses_lock:
            pending_response = self._pending_responses.pop(event_id, None)
            if pending_response is None:
                raise ValueError(f"No pending response found for event_id: {event_id}")
            return pending_response["response"]
