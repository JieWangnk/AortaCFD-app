# workflow/base_task.py
from abc import ABC, abstractmethod
from ..aortacfd_lib.utils.logger import Logger

# Initialize a global logger for all tasks to use
log_file_path = "AortaCFD.log"
logger = Logger(log_file_path).get_logger()

# --- ADD THIS CLASS DEFINITION ---
class AortaCFDError(Exception):
    """Custom exception for all workflow-related errors."""
    pass
# -----------------------------------

class Task(ABC):
    """
    Abstract Base Class for all workflow tasks.
    It defines the basic structure, ensuring every task has an execute method.
    """
    def __init__(self, config: dict):
        self.config = config
        self.log = logger

    @abstractmethod
    def execute(self, context: dict) -> bool:
        """
        Executes the main logic of the task.

        Args:
            context (dict): A dictionary for sharing data between tasks
                            (e.g., case_directory, cardiac_cycle).

        Returns:
            bool: True if the task completed successfully, False otherwise.
        """
        pass