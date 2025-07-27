import logging
import sys
import os

class Logger:
    _instance = None
    _logger = None
    
    def __new__(cls, module_name="AortaCFD", log_file="AortaCFD.log", level=logging.INFO):
        """Singleton pattern to ensure single logger instance."""
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._setup_logger(log_file, level)
        return cls._instance
    
    @classmethod
    def _setup_logger(cls, log_file, level):
        """Setup the singleton logger with file and console handlers."""
        # Create directory for log file if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            
        # Create the main logger
        cls._logger = logging.getLogger("AortaCFD")
        
        # Clear any existing handlers
        for handler in cls._logger.handlers[:]:
            cls._logger.removeHandler(handler)
            
        cls._logger.setLevel(level)

        # Create a file handler (append mode to preserve logs across modules)
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setLevel(level)

        # Create a console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)

        # Define a consistent log format
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers to the logger
        cls._logger.addHandler(file_handler)
        cls._logger.addHandler(console_handler)

        # Prevent log propagation to the root logger
        cls._logger.propagate = False

    def get_logger(self):
        """Returns the configured singleton logger."""
        return self._logger
        
    @classmethod
    def clear_log_file(cls, log_file="AortaCFD.log"):
        """Clear the log file for a new session."""
        try:
            if os.path.exists(log_file):
                with open(log_file, 'w'):
                    pass  # Truncate the file
        except Exception:
            pass  # Ignore errors when clearing log file