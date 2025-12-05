"""Tests for logging configuration utilities."""

import logging
import os
from io import StringIO
from unittest.mock import patch

from dotenvmodel.logging_config import configure_logging, disable_logging


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def setup_method(self) -> None:
        """Reset logger state before each test."""
        logger = logging.getLogger("dotenvmodel")
        logger.handlers.clear()
        logger.setLevel(logging.WARNING)
        logger.propagate = True

    def teardown_method(self) -> None:
        """Clean up logger after each test."""
        logger = logging.getLogger("dotenvmodel")
        logger.handlers.clear()
        logger.setLevel(logging.WARNING)
        logger.propagate = True

    def test_configure_logging_with_string_level(self) -> None:
        """Test configuring logging with string level."""
        configure_logging("DEBUG")

        logger = logging.getLogger("dotenvmodel")
        assert logger.level == logging.DEBUG
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.StreamHandler)
        assert logger.propagate is False

    def test_configure_logging_with_int_level(self) -> None:
        """Test configuring logging with integer level."""
        configure_logging(logging.INFO)

        logger = logging.getLogger("dotenvmodel")
        assert logger.level == logging.INFO
        assert len(logger.handlers) == 1
        assert logger.propagate is False

    def test_configure_logging_case_insensitive(self) -> None:
        """Test that string levels are case-insensitive."""
        configure_logging("debug")  # lowercase

        logger = logging.getLogger("dotenvmodel")
        assert logger.level == logging.DEBUG

    def test_configure_logging_with_env_var(self) -> None:
        """Test configuring logging from environment variable."""
        with patch.dict(os.environ, {"DOTENVMODEL_LOG_LEVEL": "INFO"}):
            configure_logging(None)

            logger = logging.getLogger("dotenvmodel")
            assert logger.level == logging.INFO

    def test_configure_logging_default_level(self) -> None:
        """Test default logging level when no level or env var provided."""
        with patch.dict(os.environ, {}, clear=True):
            configure_logging(None)

            logger = logging.getLogger("dotenvmodel")
            assert logger.level == logging.WARNING

    def test_configure_logging_custom_format(self) -> None:
        """Test configuring logging with custom format string."""
        custom_format = "[%(levelname)s] %(message)s"
        configure_logging("INFO", format_string=custom_format)

        logger = logging.getLogger("dotenvmodel")
        handler = logger.handlers[0]
        assert handler.formatter is not None
        assert handler.formatter._fmt == custom_format

    def test_configure_logging_custom_handler(self) -> None:
        """Test configuring logging with custom handler."""
        custom_handler = logging.StreamHandler(StringIO())
        configure_logging("INFO", handler=custom_handler)

        logger = logging.getLogger("dotenvmodel")
        assert len(logger.handlers) == 1
        assert logger.handlers[0] is custom_handler

    def test_configure_logging_clears_existing_handlers(self) -> None:
        """Test that configure_logging removes existing handlers."""
        logger = logging.getLogger("dotenvmodel")

        # Add a handler
        configure_logging("INFO")
        assert len(logger.handlers) == 1
        first_handler = logger.handlers[0]

        # Configure again - should clear and add new handler
        configure_logging("DEBUG")
        assert len(logger.handlers) == 1
        assert logger.handlers[0] is not first_handler

    def test_configure_logging_invalid_level_string(self) -> None:
        """Test that invalid level string falls back to WARNING."""
        configure_logging("INVALID")

        logger = logging.getLogger("dotenvmodel")
        assert logger.level == logging.WARNING

    def test_configure_logging_all_standard_levels(self) -> None:
        """Test all standard logging levels."""
        levels = [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
        ]

        for level_str, level_int in levels:
            configure_logging(level_str)
            logger = logging.getLogger("dotenvmodel")
            assert logger.level == level_int

    def test_configure_logging_propagate_false(self) -> None:
        """Test that propagate is set to False to avoid duplicate logs."""
        configure_logging("INFO")

        logger = logging.getLogger("dotenvmodel")
        assert logger.propagate is False

    def test_configure_logging_actual_output(self) -> None:
        """Test that logging actually produces output."""
        output = StringIO()
        handler = logging.StreamHandler(output)
        configure_logging("INFO", handler=handler)

        logger = logging.getLogger("dotenvmodel")
        logger.info("Test message")

        log_output = output.getvalue()
        assert "Test message" in log_output
        assert "INFO" in log_output


class TestDisableLogging:
    """Tests for disable_logging function."""

    def setup_method(self) -> None:
        """Setup logger before each test."""
        configure_logging("DEBUG")

    def teardown_method(self) -> None:
        """Clean up logger after each test."""
        logger = logging.getLogger("dotenvmodel")
        logger.handlers.clear()
        logger.setLevel(logging.WARNING)
        logger.propagate = True

    def test_disable_logging_level(self) -> None:
        """Test that disable_logging sets level above CRITICAL."""
        disable_logging()

        logger = logging.getLogger("dotenvmodel")
        assert logger.level > logging.CRITICAL

    def test_disable_logging_clears_handlers(self) -> None:
        """Test that disable_logging removes all handlers."""
        logger = logging.getLogger("dotenvmodel")
        assert len(logger.handlers) > 0  # Should have handlers from setup

        disable_logging()
        assert len(logger.handlers) == 0

    def test_disable_logging_propagate_false(self) -> None:
        """Test that propagate is set to False."""
        disable_logging()

        logger = logging.getLogger("dotenvmodel")
        assert logger.propagate is False

    def test_disable_logging_no_output(self) -> None:
        """Test that disabled logger produces no output."""
        output = StringIO()
        handler = logging.StreamHandler(output)

        # Configure with handler
        configure_logging("DEBUG", handler=handler)
        logger = logging.getLogger("dotenvmodel")

        # Disable logging
        disable_logging()

        # Add handler back to verify level is high enough to suppress logs
        logger.addHandler(handler)
        logger.critical("This should not appear")

        log_output = output.getvalue()
        assert log_output == ""

    def test_disable_logging_can_reconfigure(self) -> None:
        """Test that logging can be re-enabled after disabling."""
        disable_logging()

        logger = logging.getLogger("dotenvmodel")
        assert logger.level > logging.CRITICAL

        # Re-enable
        configure_logging("INFO")
        assert logger.level == logging.INFO
        assert len(logger.handlers) == 1


class TestLoggingIntegration:
    """Integration tests for logging configuration."""

    def setup_method(self) -> None:
        """Reset logger state before each test."""
        logger = logging.getLogger("dotenvmodel")
        logger.handlers.clear()
        logger.setLevel(logging.WARNING)
        logger.propagate = True

    def teardown_method(self) -> None:
        """Clean up logger after each test."""
        logger = logging.getLogger("dotenvmodel")
        logger.handlers.clear()
        logger.setLevel(logging.WARNING)
        logger.propagate = True

    def test_logging_hierarchy(self) -> None:
        """Test that dotenvmodel logger is properly namespaced."""
        configure_logging("INFO")

        child_logger = logging.getLogger("dotenvmodel.config")

        # Child logger should inherit level from parent
        assert child_logger.getEffectiveLevel() == logging.INFO

    def test_multiple_configure_calls(self) -> None:
        """Test that multiple configure calls don't accumulate handlers."""
        for _ in range(5):
            configure_logging("INFO")

        logger = logging.getLogger("dotenvmodel")
        assert len(logger.handlers) == 1

    def test_env_var_priority(self) -> None:
        """Test that explicit level takes priority over environment variable."""
        with patch.dict(os.environ, {"DOTENVMODEL_LOG_LEVEL": "ERROR"}):
            configure_logging("DEBUG")

            logger = logging.getLogger("dotenvmodel")
            assert logger.level == logging.DEBUG  # Explicit level wins
