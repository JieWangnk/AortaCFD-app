import logging
import sys
import os

class Logger:
    def __init__(self, log_file, level=logging.INFO):
        """
        Initializes the logger to write logs to both the console and a file.

        Args:
            log_file (str): Path to the log file.
            level (int): Logging level (e.g., logging.INFO, logging.DEBUG).
        """
        self.log_file_path = log_file
        
        # Create directory for log file if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            
        # Remove any existing handlers
        self.logger = logging.getLogger("AortaCFD")
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
            
        self.logger.setLevel(level)

        # Create a file handler
        file_handler = logging.FileHandler(log_file, mode='w')
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
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        # Prevent log propagation to the root logger
        self.logger.propagate = False

    def get_logger(self):
        """Returns the configured logger."""
        return self.logger