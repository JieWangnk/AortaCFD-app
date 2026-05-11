import logging
import sys
import os

# Custom log level for clean console output (between WARNING and ERROR)
CONSOLE_ONLY = 35  # Shows on console in clean mode, but not in file
logging.addLevelName(CONSOLE_ONLY, "CONSOLE")


class CleanConsoleFormatter(logging.Formatter):
    """Formatter for clean console output - no timestamps, just messages."""

    def format(self, record):
        # For CONSOLE level, just return the message
        if record.levelno == CONSOLE_ONLY:
            return record.getMessage()
        # For warnings/errors, add prefix
        if record.levelno >= logging.WARNING:
            return f"⚠️  {record.getMessage()}" if record.levelno == logging.WARNING else f"❌ {record.getMessage()}"
        return record.getMessage()


class Logger:
    _instance = None
    _logger = None
    _verbose = False

    def __new__(cls, module_name="AortaCFD", log_file="AortaCFD.log", level=logging.INFO, verbose=None):
        """Singleton pattern to ensure single logger instance.

        Args:
            module_name: Logger name
            log_file: Path to log file (gets full details always)
            level: Base log level
            verbose: If True, console shows all INFO. If False, console shows only key messages.
                    If None (default), keeps existing setting.
        """
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._verbose = False  # Default to clean mode
            cls._instance.log_file_path = log_file
            cls._setup_logger(log_file, level, cls._verbose)

        # Only update verbose if explicitly set (not None)
        if verbose is not None and verbose != cls._verbose:
            cls._verbose = verbose
            cls._setup_logger(log_file, level, verbose)

        return cls._instance

    @classmethod
    def _setup_logger(cls, log_file, level, verbose):
        """Setup the singleton logger with file and console handlers."""
        # Create directory for log file if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        # Create the log file if it doesn't exist
        if not os.path.exists(log_file):
            with open(log_file, "a"):
                pass

        # Create the main logger
        cls._logger = logging.getLogger("AortaCFD")

        # Clear any existing handlers and close them
        for handler in cls._logger.handlers[:]:
            handler.close()
            cls._logger.removeHandler(handler)

        # Logger accepts all levels, handlers filter
        cls._logger.setLevel(logging.DEBUG)

        # File handler: always gets full details (INFO and above)
        file_handler = logging.FileHandler(log_file, mode="a")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)

        # Console handler: clean by default, verbose shows all
        console_handler = logging.StreamHandler(sys.stdout)
        if verbose:
            # Verbose mode: show all INFO and above
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(file_formatter)
        else:
            # Clean mode: only show CONSOLE level (35) and warnings/errors
            console_handler.setLevel(CONSOLE_ONLY)
            console_handler.setFormatter(CleanConsoleFormatter())

        # Add handlers to the logger
        cls._logger.addHandler(file_handler)
        cls._logger.addHandler(console_handler)

        # Prevent log propagation to the root logger
        cls._logger.propagate = False

    @classmethod
    def set_verbose(cls, verbose: bool):
        """Update verbosity at runtime."""
        if cls._logger:
            cls._verbose = verbose
            for handler in cls._logger.handlers:
                if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                    if verbose:
                        handler.setLevel(logging.INFO)
                        handler.setFormatter(
                            logging.Formatter(
                                "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
                            )
                        )
                    else:
                        handler.setLevel(CONSOLE_ONLY)
                        handler.setFormatter(CleanConsoleFormatter())

    def get_logger(self):
        """Returns the configured singleton logger."""
        return self._logger

    @classmethod
    def console(cls, message: str):
        """Log a message that appears on console in clean mode (and always in file)."""
        if cls._logger:
            cls._logger.log(CONSOLE_ONLY, message)

    @classmethod
    def clear_log_file(cls, log_file="AortaCFD.log"):
        """Clear the log file for a new session."""
        try:
            if os.path.exists(log_file):
                with open(log_file, "w"):
                    pass  # Truncate the file
        except Exception:
            pass  # Ignore errors when clearing log file

    @classmethod
    def reset_singleton(cls):
        """Reset the singleton instance - useful for testing."""
        if cls._logger:
            # Close all handlers
            for handler in cls._logger.handlers[:]:
                handler.close()
                cls._logger.removeHandler(handler)

        # Clear all loggers with our name
        logger = logging.getLogger("AortaCFD")
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

        cls._instance = None
        cls._logger = None
