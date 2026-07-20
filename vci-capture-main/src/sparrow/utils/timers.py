from __future__ import annotations

import time
from datetime import datetime
from zoneinfo import ZoneInfo

import torch

from sparrow.utils.logging import logger


def current_time_iso() -> str:
    # Get current time for Germany (Berlin)
    # Format: YYYY-MM-DDTHH:MM:SS.mmmmmm+HH:MM
    now_germany = datetime.now(ZoneInfo("Europe/Berlin"))
    # Convert to ISO 8601 string
    return now_germany.replace(microsecond=0).isoformat()
    # Example Output: 2026-02-05T13:57


class CudaTimer:
    """
    Measures how long cuda gpu operations take.

    Example:
        with CudaTimer("my awesome processing"):
            img = torch.clamp(img, 0, 1)
            ...
    """

    def __init__(
        self,
        name: str = "gpu",
        start_event: torch.cuda.Event | None = None,
        end_event: torch.cuda.Event | None = None,
        *,
        enabled: bool = True,
    ) -> None:
        self.name = name
        self.enabled = enabled
        self.elapsed = 0
        if enabled:
            self.start = start_event
            self.end = end_event
            if self.start is None:
                self.start = torch.cuda.Event(enable_timing=True)
            if self.end is None:
                self.end = torch.cuda.Event(enable_timing=True)

    def __enter__(self) -> None:
        if self.enabled:
            self.start.record()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        if self.enabled:
            self.end.record()
            torch.cuda.synchronize()
            self.elapsed = self.start.elapsed_time(self.end)
            logger.info(self.__str__())

    def __str__(self) -> str:
        return f"CudaTimer -- {self.name} took {self.elapsed:.3f} ms"


class Timer:
    """
    Measures how cpu operations take.

    Example:
        with Timer("my awesome operations"):
            time.sleep(4)
            ...
    """

    def __init__(self, name: str = "cpu", *, enabled: bool = True) -> None:
        self.name = name
        self.enabled = enabled
        self.elapsed = 0

    def __enter__(self) -> None:
        if self.enabled:
            self.start = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        if self.enabled:
            self.end = time.time()
            self.elapsed = self.end - self.start
            logger.info(self.__str__())

    def __str__(self) -> str:
        return f"Timer -- {self.name} took {round(self.elapsed, 4)} seconds"
