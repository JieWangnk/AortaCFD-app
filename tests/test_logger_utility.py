"""
Test suite for the Logger utility class.

Tests cover:
- Singleton pattern behavior
- Logger initialization
- Verbose vs clean mode
- Console output
- File logging
- Log file operations
"""

import pytest
import sys
import os
import logging
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aortacfd_lib.utils.logger import Logger, CONSOLE_ONLY, CleanConsoleFormatter


class TestLoggerSingleton:
    """Test Logger singleton pattern."""

    def setup_method(self):
        """Reset singleton before each test."""
        Logger.reset_singleton()

    def teardown_method(self):
        """Clean up after each test."""
        Logger.reset_singleton()

    def test_singleton_returns_same_instance(self):
        """Test that Logger returns same instance."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_file = f.name

        try:
            logger1 = Logger("test1", log_file)
            logger2 = Logger("test2", log_file)

            # Should be same instance
            assert logger1 is logger2
        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)

    def test_reset_singleton(self):
        """Test singleton reset creates new instance."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_file = f.name

        try:
            logger1 = Logger("test", log_file)
            Logger.reset_singleton()
            logger2 = Logger("test", log_file)

            # Should be different instances
            assert logger1 is not logger2
        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)


class TestLoggerInitialization:
    """Test Logger initialization."""

    def setup_method(self):
        """Reset singleton before each test."""
        Logger.reset_singleton()

    def teardown_method(self):
        """Clean up after each test."""
        Logger.reset_singleton()

    def test_creates_log_file(self):
        """Test that Logger creates log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            Logger("test", log_file)

            assert os.path.exists(log_file)

    def test_creates_log_directory(self):
        """Test that Logger creates log directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'subdir', 'test.log')
            Logger("test", log_file)

            assert os.path.exists(os.path.dirname(log_file))
            assert os.path.exists(log_file)

    def test_get_logger_returns_logger(self):
        """Test get_logger returns a logging.Logger instance."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_file = f.name

        try:
            instance = Logger("test", log_file)
            logger = instance.get_logger()

            assert logger is not None
            assert isinstance(logger, logging.Logger)
        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)


class TestLoggerVerboseMode:
    """Test verbose vs clean logging modes."""

    def setup_method(self):
        """Reset singleton before each test."""
        Logger.reset_singleton()

    def teardown_method(self):
        """Clean up after each test."""
        Logger.reset_singleton()

    def test_default_is_clean_mode(self):
        """Test that default mode is clean (not verbose)."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_file = f.name

        try:
            Logger("test", log_file)
            assert Logger._verbose is False
        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)

    def test_verbose_mode_set_on_init(self):
        """Test verbose mode can be set on init."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_file = f.name

        try:
            Logger("test", log_file, verbose=True)
            assert Logger._verbose is True
        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)

    def test_set_verbose_at_runtime(self):
        """Test set_verbose method."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_file = f.name

        try:
            Logger("test", log_file, verbose=False)
            assert Logger._verbose is False

            Logger.set_verbose(True)
            assert Logger._verbose is True

            Logger.set_verbose(False)
            assert Logger._verbose is False
        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)


class TestLoggerConsoleOutput:
    """Test console logging methods."""

    def setup_method(self):
        """Reset singleton before each test."""
        Logger.reset_singleton()

    def teardown_method(self):
        """Clean up after each test."""
        Logger.reset_singleton()

    def test_console_method_logs_message(self):
        """Test Logger.console method."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_file = f.name

        try:
            Logger("test", log_file)
            Logger.console("Test console message")

            # Message should be in log file
            with open(log_file, 'r') as f:
                content = f.read()
            assert "Test console message" in content
        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)

    def test_console_level_value(self):
        """Test CONSOLE_ONLY level is between WARNING and ERROR."""
        assert logging.WARNING < CONSOLE_ONLY < logging.ERROR


class TestCleanConsoleFormatter:
    """Test CleanConsoleFormatter class."""

    def test_console_level_no_prefix(self):
        """Test CONSOLE level messages have no prefix."""
        formatter = CleanConsoleFormatter()
        record = logging.LogRecord(
            name='test', level=CONSOLE_ONLY, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        formatted = formatter.format(record)
        assert formatted == 'Test message'

    def test_warning_has_prefix(self):
        """Test WARNING level messages have prefix."""
        formatter = CleanConsoleFormatter()
        record = logging.LogRecord(
            name='test', level=logging.WARNING, pathname='', lineno=0,
            msg='Warning message', args=(), exc_info=None
        )
        formatted = formatter.format(record)
        assert '⚠️' in formatted
        assert 'Warning message' in formatted

    def test_error_has_prefix(self):
        """Test ERROR level messages have prefix."""
        formatter = CleanConsoleFormatter()
        record = logging.LogRecord(
            name='test', level=logging.ERROR, pathname='', lineno=0,
            msg='Error message', args=(), exc_info=None
        )
        formatted = formatter.format(record)
        assert '❌' in formatted
        assert 'Error message' in formatted

    def test_info_no_prefix(self):
        """Test INFO level messages have no prefix."""
        formatter = CleanConsoleFormatter()
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Info message', args=(), exc_info=None
        )
        formatted = formatter.format(record)
        # In clean mode, INFO just returns message
        assert formatted == 'Info message'


class TestLoggerFileOperations:
    """Test log file operations."""

    def setup_method(self):
        """Reset singleton before each test."""
        Logger.reset_singleton()

    def teardown_method(self):
        """Clean up after each test."""
        Logger.reset_singleton()

    def test_clear_log_file(self):
        """Test clear_log_file clears existing log."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False, mode='w') as f:
            f.write("Some existing content\n")
            log_file = f.name

        try:
            # File has content
            with open(log_file, 'r') as f:
                assert f.read() != ""

            Logger.clear_log_file(log_file)

            # File should be empty
            with open(log_file, 'r') as f:
                assert f.read() == ""
        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)

    def test_clear_nonexistent_file(self):
        """Test clear_log_file handles missing file gracefully."""
        # Should not raise
        Logger.clear_log_file('/nonexistent/path/to/file.log')

    def test_logging_writes_to_file(self):
        """Test that log messages are written to file."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_file = f.name

        try:
            instance = Logger("test", log_file)
            logger = instance.get_logger()

            logger.info("Test info message")
            logger.warning("Test warning message")
            logger.error("Test error message")

            with open(log_file, 'r') as f:
                content = f.read()

            assert "Test info message" in content
            assert "Test warning message" in content
            assert "Test error message" in content
        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)


class TestLoggerIntegration:
    """Integration tests for Logger."""

    def setup_method(self):
        """Reset singleton before each test."""
        Logger.reset_singleton()

    def teardown_method(self):
        """Clean up after each test."""
        Logger.reset_singleton()

    def test_multiple_log_calls(self):
        """Test multiple logging calls."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_file = f.name

        try:
            instance = Logger("test", log_file)
            logger = instance.get_logger()

            for i in range(10):
                logger.info(f"Message {i}")

            with open(log_file, 'r') as f:
                content = f.read()

            for i in range(10):
                assert f"Message {i}" in content
        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)

    def test_logging_after_verbose_toggle(self):
        """Test logging works after toggling verbose mode."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_file = f.name

        try:
            instance = Logger("test", log_file, verbose=False)
            logger = instance.get_logger()

            logger.info("Before toggle")
            Logger.set_verbose(True)
            logger.info("After verbose on")
            Logger.set_verbose(False)
            logger.info("After verbose off")

            with open(log_file, 'r') as f:
                content = f.read()

            assert "Before toggle" in content
            assert "After verbose on" in content
            assert "After verbose off" in content
        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
