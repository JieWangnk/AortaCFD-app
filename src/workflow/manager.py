"""Workflow manager for orchestrating CFD simulation tasks.

This module provides the WorkflowManager class that coordinates the execution
of simulation tasks based on predefined recipes (command sequences).
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

try:
    from .base_task import logger, AortaCFDError, Task, ExecutionContext
    from .tasks import setup_tasks, execution_tasks
except ImportError:
    from workflow.base_task import logger, AortaCFDError, Task, ExecutionContext
    from workflow.tasks import setup_tasks, execution_tasks

from aortacfd_lib.utils.logger import Logger


class WorkflowManager:
    """
    Orchestrates the execution of a series of tasks based on a user command.

    The manager maintains a registry of available tasks and predefined recipes
    (sequences of tasks) that can be executed by command name.

    Attributes:
        config: Full simulation configuration dictionary.
        context: Typed ExecutionContext for sharing data between tasks.
        available_tasks: Registry mapping task names to task classes.

    Example:
        >>> manager = WorkflowManager(config)
        >>> manager.run_workflow("runAll")  # Full simulation
        >>> manager.run_workflow("run:mesh")  # Mesh only
    """

    config: Dict[str, Any]
    context: ExecutionContext
    available_tasks: Dict[str, Type[Task]]

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initialize the workflow manager.

        Args:
            config: Full simulation configuration dictionary containing
                   geometry, mesh, physics, and boundary condition settings.
        """
        self.config = config
        self.context = ExecutionContext()  # Typed context for task data sharing
        self._register_tasks()
        self._initialize_context()  # Initialize context with config values early

    def _initialize_context(self) -> None:
        """
        Initialize the execution context from config.

        Sets up case directory and patient name from config settings.
        Called during __init__ so context is ready before any workflow runs.
        """
        # Only initialize if geometry config is available
        geom_cfg = self.config.get("geometry")
        if not geom_cfg:
            return

        # Set case directory
        if not self.context.case_directory:
            refinement = geom_cfg.get("refinement_level", "default")
            self.context.case_directory = os.path.join(
                os.getcwd(), "output", "OPENFOAM", f"{geom_cfg['case_name']}_{refinement}"
            )

        # Set patient name for report generation
        if not self.context.patient_name:
            self.context.patient_name = self.config.get("case_info", {}).get(
                "patient_id", geom_cfg.get("case_name", "unknown")
            )

        # Set cardiac cycle if available
        cardiac_cycle = self.config.get("cardiac_cycle")
        if cardiac_cycle and not self.context.cardiac_cycle:
            self.context.cardiac_cycle = cardiac_cycle

    def _handle_workflow_failure(
        self, command: str, failed_task: str, completed_tasks: List[str], error: Optional[Exception] = None
    ) -> None:
        """
        Handle workflow failure by writing a failure marker and logging details.

        Creates a .workflow_failed file in the case directory with details about
        the failure, allowing users to understand what went wrong and potentially
        resume or clean up.

        Args:
            command: The workflow command that was running
            failed_task: Name of the task that failed
            completed_tasks: List of tasks that completed successfully
            error: Optional exception that caused the failure
        """
        case_dir = self.context.case_directory
        if not case_dir:
            logger.warning("No case directory set; cannot write failure marker")
            return

        case_path = Path(case_dir)
        if not case_path.exists():
            logger.warning(f"Case directory does not exist: {case_dir}")
            return

        # Write failure marker with details
        failure_info = {
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "failed_task": failed_task,
            "completed_tasks": completed_tasks,
            "error_message": str(error) if error else "Task returned False",
            "case_directory": str(case_dir),
            "patient_name": self.context.patient_name,
        }

        failure_file = case_path / ".workflow_failed"
        try:
            with open(failure_file, "w") as f:
                json.dump(failure_info, f, indent=2)
            logger.info(f"Failure marker written to: {failure_file}")
        except Exception as e:
            logger.warning(f"Could not write failure marker: {e}")

        # Log recovery instructions
        logger.info(
            f"\n{'='*60}\n"
            f"WORKFLOW FAILED at task: {failed_task}\n"
            f"Completed tasks: {', '.join(completed_tasks) if completed_tasks else 'None'}\n"
            f"\nTo resume, fix the issue and run:\n"
            f"  - Full rerun: python run_case.py <patient> --workflow {command}\n"
            f"  - Or continue from failed step if applicable\n"
            f"\nFailure details saved to: {failure_file}\n"
            f"{'='*60}"
        )

    def clear_failure_marker(self) -> bool:
        """
        Remove the failure marker file if it exists.

        Call this after a successful workflow run or manual cleanup.

        Returns:
            True if marker was removed, False otherwise
        """
        case_dir = self.context.case_directory
        if not case_dir:
            return False

        failure_file = Path(case_dir) / ".workflow_failed"
        if failure_file.exists():
            try:
                failure_file.unlink()
                logger.info("Cleared previous workflow failure marker")
                return True
            except Exception as e:
                logger.warning(f"Could not remove failure marker: {e}")
        return False

    def get_previous_failure(self) -> Optional[Dict[str, Any]]:
        """
        Check for and return information about a previous workflow failure.

        Returns:
            Dict with failure info if a previous failure exists, None otherwise
        """
        case_dir = self.context.case_directory
        if not case_dir:
            return None

        failure_file = Path(case_dir) / ".workflow_failed"
        if failure_file.exists():
            try:
                with open(failure_file, "r") as f:
                    return json.load(f)
            except Exception:
                return {"error": "Could not read failure marker"}
        return None

    def _register_tasks(self) -> None:
        """Create a complete library of all available tasks."""
        self.available_tasks = {
            "create_case_structure": setup_tasks.CreateCaseStructureTask,
            "generate_mesh_files": setup_tasks.GenerateMeshFilesTask,
            "generate_physical_properties": setup_tasks.GeneratePhysicalPropertiesTask,
            "generate_numerical_schemes": setup_tasks.GenerateNumericalSchemesTask,
            "generate_solver_settings": setup_tasks.GenerateSolverSettingsTask,
            "generate_decompose_par_dict": setup_tasks.GenerateDecomposeParDictTask,
            "prepare_boundary_data": setup_tasks.PrepareBoundaryDataTask,
            "generate_bc_files": setup_tasks.GenerateBCFilesTask,
            "generate_control_dict": setup_tasks.GenerateControlDictTask,
            "update_control_dict": setup_tasks.GenerateControlDictTask,
            "generate_simulation_report": setup_tasks.GenerateSimulationReportTask,
            "generate_windkessel_report": setup_tasks.GenerateWindkesselReportTask,
            "execute_meshing": execution_tasks.ExecuteMeshingTask,
            "execute_solver": execution_tasks.ExecuteSolverTask,
            "execute_reconstruct": execution_tasks.ExecuteReconstructionTask,
            "execute_post": execution_tasks.ExecutePostProcessingTask,
            "execute_hemodynamics": execution_tasks.ExecuteHemodynamicsTask,
        }

    def run_workflow(self, command: str) -> None:
        """
        Look up the recipe for a command and run the tasks.

        Args:
            command: Workflow command name. Available commands:
                - "runAll": Full end-to-end simulation
                - "createCase": Setup case without running solver
                - "setup:dict": Generate dictionary files only
                - "setup:bc": Generate boundary condition files
                - "run:mesh": Execute meshing only
                - "run:solver": Execute solver only
                - "run:post": Execute post-processing
                - "run:reconstruct": Reconstruct parallel case
                - "run:hemodynamics": Compute hemodynamic metrics (WSS, TAWSS, OSI, RRT)
                - "setup:regenerate-numerics": Regenerate schemes

        Raises:
            AortaCFDError: If command is unknown or a task fails.
        """

        recipes = {
            # COMMAND 1: Generates all non-mesh-dependent dictionary files.
            "setup:dict": [
                "create_case_structure",
                "generate_mesh_files",
                "generate_physical_properties",
                "generate_numerical_schemes",
                "generate_solver_settings",
                "generate_decompose_par_dict",
                "generate_control_dict",  # Writes preliminary controlDict
                "generate_simulation_report",  # Save config manifest for reproducibility
            ],
            # COMMAND 2: Generates BC files and data AFTER a mesh exists.
            # This is the command you will use to update BCs.
            "setup:bc": [
                "prepare_boundary_data",  # Runs writeMeshObj, InletMapping, etc.
                "generate_bc_files",  # Writes the final 0/ files
                "update_control_dict",  # Overwrites controlDict with final endTime
            ],
            # COMMAND 3: Executes the meshing utilities.
            "run:mesh": ["execute_meshing"],
            # COMMAND 4: Executes the solver.
            "run:solver": ["execute_solver"],
            # COMMAND 5: Executes post-processing (ParaView visualization).
            "run:post": ["execute_post"],
            "execute_post": ["execute_post"],  # Alias
            # COMMAND 6: Executes hemodynamics analysis (WSS, TAWSS, OSI, RRT, pressure drop).
            # Can be run after simulation or as standalone post-processing.
            "run:hemodynamics": ["execute_hemodynamics"],
            "execute_hemodynamics": ["execute_hemodynamics"],  # Alias
            # User-friendly: combines QoI extraction + image rendering. This is what
            # `--steps postprocess` maps to, matching what most users expect from
            # the word "post-processing" (numbers AND pictures, not just numbers).
            "run:postprocess": ["execute_hemodynamics", "execute_post"],
            # COMMAND 7: Executes reconstruction.
            "run:reconstruct": ["execute_reconstruct"],
            "execute_reconstruct": ["execute_reconstruct"],  # Alias
            # COMMAND 7: A user-friendly alias to set up a case completely.
            "createCase": [
                "create_case_structure",
                "generate_mesh_files",
                "generate_physical_properties",
                "generate_numerical_schemes",
                "generate_solver_settings",
                "generate_decompose_par_dict",
                "generate_control_dict",
                "execute_meshing",
                "prepare_boundary_data",
                "generate_bc_files",
                "update_control_dict",
                "generate_simulation_report",  # Report after final controlDict + boundary data
            ],
            # COMMAND 9: The full end-to-end run.
            "runAll": [
                "create_case_structure",
                "generate_mesh_files",
                "generate_physical_properties",
                "generate_numerical_schemes",
                "generate_solver_settings",
                "generate_decompose_par_dict",
                "generate_control_dict",
                "execute_meshing",
                "prepare_boundary_data",
                "generate_bc_files",
                "update_control_dict",
                "generate_simulation_report",  # Report after final controlDict + boundary data
                "execute_solver",
                "execute_hemodynamics",  # Compute WSS, TAWSS, OSI, RRT, pressure drop
                "execute_post",  # ParaView visualization
                "generate_windkessel_report",  # Generate WK analysis after simulation
            ],
            # COMMAND 9: Regenerate numerical schemes with mesh-adaptive adjustments.
            # Use AFTER meshing to apply mesh-quality-aware settings based on checkMesh results.
            "setup:regenerate-numerics": ["generate_numerical_schemes", "generate_solver_settings"],
        }

        task_sequence = recipes.get(command)
        if not task_sequence:
            raise AortaCFDError(f"Unknown command '{command}'")

        # Ensure context is initialized (idempotent - safe to call multiple times)
        self._initialize_context()

        # Track completed tasks for failure handling
        completed_tasks: List[str] = []

        logger.info(f"Starting workflow for command: '{command}'")
        Logger.console(f"\n📋 Running workflow: {command}")
        try:
            for task_name in task_sequence:
                task_class = self.available_tasks.get(task_name)
                if not task_class:
                    self._handle_workflow_failure(command, task_name, completed_tasks, Exception("Task not registered"))
                    raise AortaCFDError(f"Task '{task_name}' is not registered in the manager.")

                task_instance = task_class(self.config)
                logger.info(f"--- Executing Task: {task_instance.__class__.__name__} ---")
                # Clean console output: show task name
                task_display_name = task_name.replace("_", " ").title()
                Logger.console(f"  → {task_display_name}...")

                try:
                    success = task_instance.execute(self.context)
                except Exception as task_error:
                    self._handle_workflow_failure(command, task_name, completed_tasks, task_error)
                    logger.error(f"Task '{task_name}' raised exception: {task_error}")
                    raise AortaCFDError(f"Workflow aborted due to exception in task: {task_name}") from task_error

                if not success:
                    self._handle_workflow_failure(command, task_name, completed_tasks)
                    logger.error(f"Task '{task_name}' failed. Aborting workflow.")
                    raise AortaCFDError(f"Workflow aborted due to failure in task: {task_name}")

                completed_tasks.append(task_name)

            # Clear any previous failure marker on success
            self.clear_failure_marker()
            logger.info("Workflow completed successfully.")
            Logger.console(f"\n✅ Workflow '{command}' completed successfully")

        except AortaCFDError:
            # Re-raise workflow errors (already handled)
            raise
        except Exception as e:
            # Handle unexpected errors
            self._handle_workflow_failure(command, "unknown", completed_tasks, e)
            raise AortaCFDError(f"Unexpected error during workflow: {e}") from e
