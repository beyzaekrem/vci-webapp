"""teague package

Provides a package-level logger and a helper to configure logging for the package.
"""

from __future__ import annotations

import logging

# Package logger: use a named logger so users can configure it as 'teague' or more granularly
logger = logging.getLogger("teague")
# Avoid configuring handlers at import time in libraries
logger.addHandler(logging.NullHandler())


def setup_logging(level: str | int = "INFO", fmt: str | None = None) -> None:
    """Configure package-wide logging.

    Args:
            level: logging level as string ("DEBUG", "INFO", ...) or an int.
            fmt: optional format string passed to logging.basicConfig
    """
    if fmt is None:
        fmt = "% (asctime)s - % (name)s - % (levelname)s - % (message)s".replace(" ", "")
        # the above replace avoids accidental leading spaces when using percent formatting in raw string
        fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Resolve string level names to logging constants
    if isinstance(level, str):
        level_upper = level.upper()
        if level_upper.isdigit():
            level = int(level_upper)
        else:
            level = getattr(logging, level_upper, None)
            if level is None:
                raise ValueError(f"Unknown log level: {level}")

    logging.basicConfig(level=level, format=fmt)
    logger.setLevel(level)
