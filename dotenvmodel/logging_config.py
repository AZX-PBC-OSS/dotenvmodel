"""Logging configuration utilities for dotenvmodel."""

import logging
import os
import sys

from dotenvmodel._constants import LOGGER_NAME


def configure_logging(
    level: str | int | None = None,
    *,
    format_string: str | None = None,
    handler: logging.Handler | None = None,
) -> None:
    """Configure logging for dotenvmodel.

    This is a convenience function to quickly enable dotenvmodel logging.
    For more control, configure the 'dotenvmodel' logger directly using
    the standard logging module.

    When to use:
        - During development to debug config loading issues
        - In production to log which .env files are loaded
        - When troubleshooting missing or invalid config values

    When NOT to use:
        - In production with DEBUG level (too verbose)
        - If your app already configures the root logger comprehensively

    Args:
        level: Logging level. Can be a string ("DEBUG", "INFO", "WARNING", "ERROR")
            or an int (logging.DEBUG, etc.). If None, reads from
            `DOTENVMODEL_LOG_LEVEL` environment variable, defaults to WARNING.
        format_string: Custom format string for log messages. If None, uses
            `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"`.
        handler: Custom logging handler. If None, uses `StreamHandler` (stdout).

    Example:
        ```python
        from dotenvmodel import configure_logging

        # Enable INFO level logging
        configure_logging("INFO")

        # Or use DEBUG for more verbose output
        configure_logging("DEBUG")

        # Custom format
        configure_logging("DEBUG", format_string="[%(levelname)s] %(message)s")

        # Via environment variable (no code change needed)
        # export DOTENVMODEL_LOG_LEVEL=DEBUG
        ```

    See Also:
        - [`disable_logging`][dotenvmodel.logging_config.disable_logging]: Turn off all logging.
    """
    # Determine log level
    resolved_level: int
    if level is None:
        env_level = os.getenv("DOTENVMODEL_LOG_LEVEL", "WARNING").upper()
        resolved_level = getattr(logging, env_level, logging.WARNING)
    elif isinstance(level, str):
        resolved_level = getattr(logging, level.upper(), logging.WARNING)
    else:
        resolved_level = level

    # Get the dotenvmodel logger
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(resolved_level)

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
    """Disable all dotenvmodel logging.

    When to use:
        - When you want to completely silence dotenvmodel log output
        - After temporarily enabling logging for debugging

    Example:
        ```python
        from dotenvmodel import disable_logging

        # Turn off all dotenvmodel logs
        disable_logging()
        ```

    See Also:
        - [`configure_logging`][dotenvmodel.logging_config.configure_logging]: Enable/configure logging.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.CRITICAL + 1)  # Above CRITICAL
    logger.handlers.clear()
    logger.propagate = False
