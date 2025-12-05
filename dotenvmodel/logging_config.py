"""Logging configuration utilities for dotenvmodel."""

import logging
import os
import sys


def configure_logging(
    level: str | int | None = None,
    *,
    format_string: str | None = None,
    handler: logging.Handler | None = None,
) -> None:
    """
    Configure logging for dotenvmodel.

    This is a convenience function to quickly enable dotenvmodel logging.
    For more control, configure the 'dotenvmodel' logger directly using
    the standard logging module.

    Args:
        level: Logging level. Can be a string ("DEBUG", "INFO", "WARNING", "ERROR")
            or an int (logging.DEBUG, etc.). If None, reads from DOTENVMODEL_LOG_LEVEL
            environment variable, defaults to WARNING.
        format_string: Custom format string for log messages. If None, uses a
            default format with timestamp, level, and message.
        handler: Custom logging handler. If None, uses StreamHandler (stdout).

    Example:
        ```python
        from dotenvmodel.logging_config import configure_logging

        # Enable INFO level logging
        configure_logging("INFO")

        # Or use DEBUG for more verbose output
        configure_logging("DEBUG")

        # Custom format
        configure_logging(
            "DEBUG",
            format_string="[%(levelname)s] %(message)s"
        )
        ```
    """
    # Determine log level
    if level is None:
        env_level = os.getenv("DOTENVMODEL_LOG_LEVEL", "WARNING").upper()
        level = getattr(logging, env_level, logging.WARNING)
    elif isinstance(level, str):
        level = getattr(logging, level.upper(), logging.WARNING)

    # Get the dotenvmodel logger
    logger = logging.getLogger("dotenvmodel")
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create handler
    if handler is None:
        handler = logging.StreamHandler(sys.stdout)

    # Set format
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    formatter = logging.Formatter(format_string)
    handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(handler)

    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False


def disable_logging() -> None:
    """
    Disable all dotenvmodel logging.

    Example:
        ```python
        from dotenvmodel.logging_config import disable_logging

        disable_logging()
        ```
    """
    logger = logging.getLogger("dotenvmodel")
    logger.setLevel(logging.CRITICAL + 1)  # Above CRITICAL
    logger.handlers.clear()
    logger.propagate = False
