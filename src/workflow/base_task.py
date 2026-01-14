# workflow/base_task.py
"""Base task classes and exceptions for the AortaCFD workflow system."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type

try:
    from ..aortacfd_lib.utils.logger import Logger
except ImportError:
    from aortacfd_lib.utils.logger import Logger

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

    Attributes:
        config: Full configuration dictionary for the simulation.
        log: Logger instance for task-specific logging.
    """

    config: Dict[str, Any]

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initialize the task with configuration.

        Args:
            config: Full configuration dictionary containing geometry, mesh,
                   physics, and boundary condition settings.
        """
        self.config = config
        self.log = logger

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> bool:
        """
        Execute the main logic of the task.

        Args:
            context: A dictionary for sharing data between tasks.
                    Common keys include:
                    - case_directory: Path to OpenFOAM case
                    - cardiac_cycle: Duration of cardiac cycle in seconds
                    - patient_name: Patient identifier

        Returns:
            True if the task completed successfully, False otherwise.
        """
        pass