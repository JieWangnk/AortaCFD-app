# workflow/base_task.py
"""
Base task classes and execution context for the AortaCFD workflow system.

This module provides:
- ExecutionContext: Typed context for sharing data between tasks
- TaskMetadata: Dependency and requirement metadata for tasks
- Task: Abstract base class for all workflow tasks
- AortaCFDError: Custom exception for workflow errors
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Set, Type

# Use absolute imports for consistency
from aortacfd_lib.utils.logger import Logger


# =============================================================================
# GLOBAL LOGGER (for backward compatibility)
# =============================================================================

log_file_path = "AortaCFD.log"
logger = Logger(log_file_path).get_logger()


# =============================================================================
# EXCEPTIONS
# =============================================================================

class AortaCFDError(Exception):
    """Base exception for all workflow-related errors."""
    pass


class TaskDependencyError(AortaCFDError):
    """Raised when task dependencies are not satisfied."""
    pass


class TaskExecutionError(AortaCFDError):
    """Raised when task execution fails."""
    pass


# =============================================================================
# EXECUTION CONTEXT
# =============================================================================

@dataclass
class ExecutionContext:
    """
    Typed context for sharing data between workflow tasks.

    This replaces the untyped Dict[str, Any] context with a structured
    dataclass that provides type safety and clear documentation of
    available context values.

    Attributes:
        case_directory: Path to the OpenFOAM case directory
        patient_name: Patient identifier string
        cardiac_cycle: Duration of cardiac cycle in seconds
        mesh_generated: Whether mesh generation has completed
        bc_generated: Whether boundary conditions have been generated
        solver_completed: Whether solver has finished
        custom_data: Dictionary for task-specific data sharing
    """

    case_directory: str = ""
    patient_name: str = ""
    cardiac_cycle: float = 0.0

    # Task completion flags
    mesh_generated: bool = False
    bc_generated: bool = False
    solver_completed: bool = False
    post_processed: bool = False

    # Custom data for extensibility
    custom_data: Dict[str, Any] = field(default_factory=dict)

    # Optional task-specific logger
    _logger: Optional[Any] = field(default=None, repr=False)

    @property
    def case_path(self) -> Path:
        """Return case_directory as a Path object."""
        return Path(self.case_directory) if self.case_directory else Path()

    def get_logger(self, name: str = "task") -> Any:
        """Get a logger, creating one if needed."""
        if self._logger is None:
            self._logger = Logger(log_file_path).get_logger()
        return self._logger

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return {
            "case_directory": self.case_directory,
            "patient_name": self.patient_name,
            "cardiac_cycle": self.cardiac_cycle,
            "mesh_generated": self.mesh_generated,
            "bc_generated": self.bc_generated,
            "solver_completed": self.solver_completed,
            "post_processed": self.post_processed,
            **self.custom_data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionContext":
        """Create ExecutionContext from a dictionary."""
        known_keys = {
            "case_directory", "patient_name", "cardiac_cycle",
            "mesh_generated", "bc_generated", "solver_completed", "post_processed"
        }
        known_data = {k: v for k, v in data.items() if k in known_keys}
        custom_data = {k: v for k, v in data.items() if k not in known_keys}
        return cls(**known_data, custom_data=custom_data)


# =============================================================================
# TASK METADATA
# =============================================================================

@dataclass
class TaskMetadata:
    """
    Metadata describing task dependencies and requirements.

    This enables automatic dependency validation before task execution
    and clear documentation of task requirements.

    Attributes:
        name: Human-readable task name
        dependencies: List of task names that must complete first
        requires_mesh: Whether this task requires mesh to exist
        requires_bc: Whether this task requires BCs to be generated
        produces: List of context keys this task produces/modifies
        description: Brief description of task purpose
    """

    name: str
    dependencies: List[str] = field(default_factory=list)
    requires_mesh: bool = False
    requires_bc: bool = False
    produces: List[str] = field(default_factory=list)
    description: str = ""


# =============================================================================
# TASK BASE CLASS
# =============================================================================

class Task(ABC):
    """
    Abstract Base Class for all workflow tasks.

    Every task in the AortaCFD workflow system inherits from this class.
    Tasks are responsible for a single, well-defined operation in the
    simulation setup or execution process.

    Class Attributes:
        metadata: TaskMetadata describing dependencies and requirements

    Instance Attributes:
        config: Full configuration dictionary for the simulation
        log: Logger instance for task-specific logging

    Example:
        class GenerateMeshTask(Task):
            metadata = TaskMetadata(
                name="Generate Mesh",
                dependencies=["create_case_structure"],
                produces=["mesh_generated"]
            )

            def execute(self, context: ExecutionContext) -> bool:
                # ... mesh generation logic ...
                context.mesh_generated = True
                return True
    """

    # Class-level metadata (override in subclasses)
    metadata: ClassVar[TaskMetadata] = TaskMetadata(name="BaseTask")

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

    def validate_dependencies(self, context: ExecutionContext) -> bool:
        """
        Check if all dependencies are satisfied.

        Args:
            context: Current execution context

        Returns:
            True if all dependencies are met

        Raises:
            TaskDependencyError: If dependencies are not satisfied
        """
        if self.metadata.requires_mesh and not context.mesh_generated:
            raise TaskDependencyError(
                f"Task '{self.metadata.name}' requires mesh, but mesh not generated. "
                f"Run mesh generation first."
            )

        if self.metadata.requires_bc and not context.bc_generated:
            raise TaskDependencyError(
                f"Task '{self.metadata.name}' requires boundary conditions, "
                f"but BCs not generated. Run BC setup first."
            )

        return True

    @abstractmethod
    def execute(self, context: ExecutionContext) -> bool:
        """
        Execute the main logic of the task.

        Args:
            context: ExecutionContext for sharing data between tasks.
                    Can also accept Dict[str, Any] for backward compatibility.

        Returns:
            True if the task completed successfully, False otherwise.

        Raises:
            TaskExecutionError: If execution fails
        """
        pass

    def run(self, context: ExecutionContext) -> bool:
        """
        Validate dependencies and execute the task.

        This is the recommended entry point for running tasks,
        as it ensures dependencies are checked first.

        Args:
            context: ExecutionContext for the workflow

        Returns:
            True if task completed successfully
        """
        self.validate_dependencies(context)
        return self.execute(context)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(metadata={self.metadata.name})"


# =============================================================================
# BACKWARD COMPATIBILITY
# =============================================================================

def context_to_dict(context: ExecutionContext) -> Dict[str, Any]:
    """Convert ExecutionContext to dict for legacy code."""
    return context.to_dict()


def dict_to_context(data: Dict[str, Any]) -> ExecutionContext:
    """Convert dict to ExecutionContext for legacy code."""
    return ExecutionContext.from_dict(data)
