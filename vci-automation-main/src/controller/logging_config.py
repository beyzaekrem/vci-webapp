import logging
import sys

logger = logging.getLogger("Controller")
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
logger.addHandler(console_handler)


def set_global_verbosity(level: str):
    """Function to change the visible output level at runtime."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Validate that the result is actually an integer level constant
    if not isinstance(numeric_level, int):
        # Handle the case where the user entered an unrecognized string
        logger.warning(f"Invalid verbosity level: '{level}'. Defaulting to INFO.")
        numeric_level = logging.INFO

    # Apply the numeric level to your logger/handler
    logger.handlers[0].setLevel(numeric_level)
