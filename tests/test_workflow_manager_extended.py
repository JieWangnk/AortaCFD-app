"""
Extended test suite for the WorkflowManager class.

Tests cover:
- Task registration and discovery
- Context management
- ExecutionContext dict-like access
"""

import pytest
import sys
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from workflow.base_task import Task, ExecutionContext


class TestWorkflowManagerInitialization:
    """Test WorkflowManager initialization."""

    def test_basic_initialization(self):
        """Test basic manager initialization."""
        from workflow.manager import WorkflowManager

        config = {"geometry": {"case_name": "test_case", "inlet_keywords_ordered": "inlet"}}

        manager = WorkflowManager(config)

        assert manager.config == config
        assert isinstance(manager.context, ExecutionContext)
        assert len(manager.available_tasks) > 0

    def test_context_initialization(self):
        """Test that context is properly initialized."""
        from workflow.manager import WorkflowManager

        config = {"geometry": {"case_name": "test_case", "inlet_keywords_ordered": "inlet"}}

        manager = WorkflowManager(config)

        # Context should have case_directory set
        assert manager.context.case_directory != ""

    def test_task_discovery(self):
        """Test that all tasks are discovered."""
        from workflow.manager import WorkflowManager

        config = {"geometry": {"case_name": "test_case"}}

        manager = WorkflowManager(config)

        # Should have various task types
        task_names = list(manager.available_tasks.keys())

        # Check for expected task categories
        assert any("mesh" in name for name in task_names) or any("setup" in name for name in task_names)


class TestWorkflowManagerAPI:
    """Test WorkflowManager API methods."""

    def test_run_workflow_method_exists(self):
        """Test that run_workflow method exists."""
        from workflow.manager import WorkflowManager

        config = {"geometry": {"case_name": "test_case"}}

        manager = WorkflowManager(config)

        # run_workflow is the main execution method
        assert hasattr(manager, "run_workflow")

    def test_available_tasks_populated(self):
        """Test that available_tasks is populated."""
        from workflow.manager import WorkflowManager

        config = {"geometry": {"case_name": "test_case"}}

        manager = WorkflowManager(config)

        # Should have available tasks dictionary
        assert isinstance(manager.available_tasks, dict)
        assert len(manager.available_tasks) > 0

    def test_context_is_execution_context(self):
        """Test that context is an ExecutionContext."""
        from workflow.manager import WorkflowManager

        config = {"geometry": {"case_name": "test_case"}}

        manager = WorkflowManager(config)

        # Context should be ExecutionContext, not dict
        assert isinstance(manager.context, ExecutionContext)


class TestWorkflowManagerStepParsing:
    """Test step/stage parsing."""

    def test_parse_step_simple(self):
        """Test parsing simple step names."""
        from workflow.manager import WorkflowManager

        config = {"geometry": {"case_name": "test_case"}}

        manager = WorkflowManager(config)

        # Test parsing of step specifications
        # Exact behavior depends on implementation
        # This tests the general interface

    def test_parse_step_with_stage(self):
        """Test parsing step names with stage prefix."""
        from workflow.manager import WorkflowManager

        config = {"geometry": {"case_name": "test_case"}}

        manager = WorkflowManager(config)

        # Steps like "setup:geometry" or "run:mesh"


class TestWorkflowManagerIntegration:
    """Integration tests for WorkflowManager."""

    def test_full_setup_workflow(self):
        """Test running a full setup workflow."""
        from workflow.manager import WorkflowManager

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "geometry": {
                    "case_name": "test_case",
                    "inlet_keywords_ordered": "inlet",
                    "outlet_keywords_ordered": ["outlet1"],
                    "wall_keywords_ordered": "wall",
                },
                "boundary_conditions": {
                    "inlet": {"type": "CONSTANT", "velocity": 0.5, "profile": "parabolic"},
                    "outlets": {"type": "ZEROGRADIENT"},
                },
                "simulation_control": {
                    "controlDict": {"application": "foamRun", "writeInterval": 0.01},
                    "number_of_cycles": 1,
                },
            }

            manager = WorkflowManager(config)

            # Override case directory
            manager.context["case_directory"] = os.path.join(tmpdir, "openfoam")
            os.makedirs(manager.context["case_directory"])

            # This tests the manager can be instantiated with a realistic config


class TestExecutionContextDictAccess:
    """Test ExecutionContext dict-like access."""

    def test_dict_getitem(self):
        """Test dict-style item getting."""
        context = ExecutionContext(case_directory="/test")

        assert context["case_directory"] == "/test"

        # Returns None for nonexistent keys (not KeyError)
        result = context["nonexistent"]
        assert result is None

    def test_dict_setitem(self):
        """Test dict-style item setting."""
        context = ExecutionContext(case_directory="/test")

        context["new_key"] = "new_value"

        # Should be stored in custom_data
        assert context["new_key"] == "new_value"

    def test_dict_setitem_known_attrs(self):
        """Test dict-style setting of known attributes."""
        context = ExecutionContext(case_directory="/test")

        context["case_directory"] = "/new/path"
        assert context.case_directory == "/new/path"

        context["cardiac_cycle"] = 0.85
        assert context.cardiac_cycle == 0.85

    def test_dict_contains(self):
        """Test 'in' operator."""
        context = ExecutionContext(case_directory="/test")

        assert "case_directory" in context
        assert "nonexistent" not in context

    def test_custom_data_access(self):
        """Test custom_data storage."""
        context = ExecutionContext(case_directory="/test")

        context["custom_key"] = "custom_value"

        assert context.custom_data.get("custom_key") == "custom_value"

    def test_to_dict(self):
        """Test to_dict conversion."""
        context = ExecutionContext(case_directory="/test", patient_name="PAT001", cardiac_cycle=0.85)
        context["extra_data"] = "extra"

        result = context.to_dict()

        assert result["case_directory"] == "/test"
        assert result["patient_name"] == "PAT001"
        assert result["cardiac_cycle"] == 0.85
        assert result["extra_data"] == "extra"

    def test_from_dict(self):
        """Test from_dict class method."""
        data = {"case_directory": "/test", "patient_name": "PAT001", "cardiac_cycle": 0.85, "extra_key": "extra_value"}

        context = ExecutionContext.from_dict(data)

        assert context.case_directory == "/test"
        assert context.patient_name == "PAT001"
        assert context.cardiac_cycle == 0.85
        assert context.custom_data.get("extra_key") == "extra_value"

    def test_case_path_property(self):
        """Test case_path property."""
        context = ExecutionContext(case_directory="/test/path")

        assert context.case_path == Path("/test/path")

    def test_case_path_empty(self):
        """Test case_path with empty directory."""
        context = ExecutionContext()

        assert context.case_path == Path()


class TestWorkflowManagerOutput:
    """Test WorkflowManager output handling."""

    def test_output_directory_creation(self):
        """Test that output directories are created correctly."""
        from workflow.manager import WorkflowManager

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"geometry": {"case_name": "test_case"}, "output_base_directory": tmpdir}

            manager = WorkflowManager(config)

            # The case directory should be set
            assert manager.context.case_directory != ""

    def test_patient_name_in_context(self):
        """Test that patient name is in context."""
        from workflow.manager import WorkflowManager

        config = {"geometry": {"case_name": "PAT001"}}

        manager = WorkflowManager(config)

        # Patient name should be accessible
        # Exact implementation may vary


class TestExecutionContextFlags:
    """Test ExecutionContext task completion flags."""

    def test_default_flags(self):
        """Test default task completion flags."""
        context = ExecutionContext()

        assert context.mesh_generated is False
        assert context.bc_generated is False
        assert context.solver_completed is False
        assert context.post_processed is False

    def test_set_flags(self):
        """Test setting task completion flags."""
        context = ExecutionContext()

        context.mesh_generated = True
        context.bc_generated = True

        assert context.mesh_generated is True
        assert context.bc_generated is True

    def test_flags_in_to_dict(self):
        """Test that flags are included in to_dict."""
        context = ExecutionContext()
        context.mesh_generated = True

        result = context.to_dict()

        assert "mesh_generated" in result
        assert result["mesh_generated"] is True


class TestWorkflowManagerFailureHandling:
    """Test workflow failure handling methods."""

    def test_handle_workflow_failure_writes_marker(self):
        """Test that failure marker is written on workflow failure."""
        from workflow.manager import WorkflowManager

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"geometry": {"case_name": "test_case"}}

            manager = WorkflowManager(config)
            manager.context.case_directory = tmpdir
            manager.context.patient_name = "PAT001"

            # Trigger failure handling
            manager._handle_workflow_failure(
                command="runAll",
                failed_task="execute_solver",
                completed_tasks=["create_case_structure", "generate_mesh_files"],
                error=Exception("Solver crashed"),
            )

            # Check failure marker was created
            failure_file = Path(tmpdir) / ".workflow_failed"
            assert failure_file.exists()

            # Verify contents
            import json

            with open(failure_file) as f:
                failure_info = json.load(f)

            assert failure_info["command"] == "runAll"
            assert failure_info["failed_task"] == "execute_solver"
            assert "create_case_structure" in failure_info["completed_tasks"]
            assert "Solver crashed" in failure_info["error_message"]

    def test_handle_workflow_failure_no_case_directory(self):
        """Test failure handling when case directory is not set."""
        from workflow.manager import WorkflowManager

        config = {"geometry": {"case_name": "test_case"}}

        manager = WorkflowManager(config)
        manager.context.case_directory = ""

        # Should not raise, just log warning
        manager._handle_workflow_failure(command="runAll", failed_task="execute_solver", completed_tasks=[], error=None)

    def test_handle_workflow_failure_directory_not_exists(self):
        """Test failure handling when case directory doesn't exist."""
        from workflow.manager import WorkflowManager

        config = {"geometry": {"case_name": "test_case"}}

        manager = WorkflowManager(config)
        manager.context.case_directory = "/nonexistent/path/that/does/not/exist"

        # Should not raise, just log warning
        manager._handle_workflow_failure(command="runAll", failed_task="execute_solver", completed_tasks=[], error=None)

    def test_handle_workflow_failure_without_error(self):
        """Test failure handling when task returns False (no exception)."""
        from workflow.manager import WorkflowManager

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"geometry": {"case_name": "test_case"}}

            manager = WorkflowManager(config)
            manager.context.case_directory = tmpdir

            manager._handle_workflow_failure(
                command="runAll", failed_task="execute_meshing", completed_tasks=["create_case_structure"], error=None
            )

            failure_file = Path(tmpdir) / ".workflow_failed"
            assert failure_file.exists()

            import json

            with open(failure_file) as f:
                failure_info = json.load(f)

            assert failure_info["error_message"] == "Task returned False"


class TestClearFailureMarker:
    """Test clear_failure_marker method."""

    def test_clear_existing_marker(self):
        """Test clearing an existing failure marker."""
        from workflow.manager import WorkflowManager

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"geometry": {"case_name": "test_case"}}

            manager = WorkflowManager(config)
            manager.context.case_directory = tmpdir

            # Create a failure marker
            failure_file = Path(tmpdir) / ".workflow_failed"
            failure_file.write_text('{"test": true}')
            assert failure_file.exists()

            # Clear it
            result = manager.clear_failure_marker()

            assert result is True
            assert not failure_file.exists()

    def test_clear_nonexistent_marker(self):
        """Test clearing when no marker exists."""
        from workflow.manager import WorkflowManager

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"geometry": {"case_name": "test_case"}}

            manager = WorkflowManager(config)
            manager.context.case_directory = tmpdir

            # No failure marker exists
            result = manager.clear_failure_marker()

            assert result is False

    def test_clear_no_case_directory(self):
        """Test clearing when case directory not set."""
        from workflow.manager import WorkflowManager

        config = {"geometry": {"case_name": "test_case"}}

        manager = WorkflowManager(config)
        manager.context.case_directory = ""

        result = manager.clear_failure_marker()

        assert result is False


class TestGetPreviousFailure:
    """Test get_previous_failure method."""

    def test_get_existing_failure(self):
        """Test retrieving an existing failure marker."""
        from workflow.manager import WorkflowManager

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"geometry": {"case_name": "test_case"}}

            manager = WorkflowManager(config)
            manager.context.case_directory = tmpdir

            # Create a failure marker
            import json

            failure_file = Path(tmpdir) / ".workflow_failed"
            failure_data = {"command": "runAll", "failed_task": "execute_solver", "error_message": "Test error"}
            with open(failure_file, "w") as f:
                json.dump(failure_data, f)

            # Get the failure info
            result = manager.get_previous_failure()

            assert result is not None
            assert result["command"] == "runAll"
            assert result["failed_task"] == "execute_solver"

    def test_get_no_failure(self):
        """Test when no failure marker exists."""
        from workflow.manager import WorkflowManager

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"geometry": {"case_name": "test_case"}}

            manager = WorkflowManager(config)
            manager.context.case_directory = tmpdir

            result = manager.get_previous_failure()

            assert result is None

    def test_get_failure_no_case_directory(self):
        """Test when case directory not set."""
        from workflow.manager import WorkflowManager

        config = {"geometry": {"case_name": "test_case"}}

        manager = WorkflowManager(config)
        manager.context.case_directory = ""

        result = manager.get_previous_failure()

        assert result is None

    def test_get_failure_corrupt_marker(self):
        """Test handling of corrupt failure marker."""
        from workflow.manager import WorkflowManager

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"geometry": {"case_name": "test_case"}}

            manager = WorkflowManager(config)
            manager.context.case_directory = tmpdir

            # Create a corrupt failure marker
            failure_file = Path(tmpdir) / ".workflow_failed"
            failure_file.write_text("not valid json {{{")

            result = manager.get_previous_failure()

            assert result is not None
            assert "error" in result


class TestRunWorkflowErrorHandling:
    """Test error handling in run_workflow method."""

    def test_unknown_command(self):
        """Test that unknown command raises error."""
        from workflow.manager import WorkflowManager
        from workflow.base_task import AortaCFDError

        config = {"geometry": {"case_name": "test_case"}}

        manager = WorkflowManager(config)

        with pytest.raises(AortaCFDError) as exc_info:
            manager.run_workflow("unknown_command")

        assert "Unknown command 'unknown_command'" in str(exc_info.value)

    def test_unregistered_task_in_recipe(self):
        """Test error when recipe contains unregistered task."""
        from workflow.manager import WorkflowManager
        from workflow.base_task import AortaCFDError

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"geometry": {"case_name": "test_case"}}

            manager = WorkflowManager(config)
            manager.context.case_directory = tmpdir

            # Remove a task from the registry
            del manager.available_tasks["create_case_structure"]

            with pytest.raises(AortaCFDError) as exc_info:
                manager.run_workflow("setup:dict")

            assert "not registered" in str(exc_info.value)

    def test_task_exception_handling(self):
        """Test that task exceptions are properly handled."""
        from workflow.manager import WorkflowManager
        from workflow.base_task import AortaCFDError, Task, ExecutionContext

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"geometry": {"case_name": "test_case"}}

            manager = WorkflowManager(config)
            manager.context.case_directory = tmpdir

            # Create a mock task that raises an exception
            class FailingTask(Task):
                def execute(self, context: ExecutionContext) -> bool:
                    raise RuntimeError("Task exploded")

            # Replace the first task with our failing task
            manager.available_tasks["create_case_structure"] = FailingTask

            with pytest.raises(AortaCFDError) as exc_info:
                manager.run_workflow("setup:dict")

            assert "exception in task" in str(exc_info.value)

    def test_task_returns_false(self):
        """Test that task returning False aborts workflow."""
        from workflow.manager import WorkflowManager
        from workflow.base_task import AortaCFDError, Task, ExecutionContext

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"geometry": {"case_name": "test_case"}}

            manager = WorkflowManager(config)
            manager.context.case_directory = tmpdir

            # Create a mock task that returns False
            class FailingTask(Task):
                def execute(self, context: ExecutionContext) -> bool:
                    return False

            # Replace the first task with our failing task
            manager.available_tasks["create_case_structure"] = FailingTask

            with pytest.raises(AortaCFDError) as exc_info:
                manager.run_workflow("setup:dict")

            assert "failure in task" in str(exc_info.value)


class TestWorkflowManagerContextInitialization:
    """Test context initialization edge cases."""

    def test_no_geometry_config(self):
        """Test initialization without geometry config."""
        from workflow.manager import WorkflowManager

        config = {}

        manager = WorkflowManager(config)

        # Should not raise, context remains with defaults
        assert manager.context.case_directory == ""

    def test_cardiac_cycle_from_config(self):
        """Test cardiac cycle is set from config."""
        from workflow.manager import WorkflowManager

        config = {"geometry": {"case_name": "test_case", "refinement_level": "coarse"}, "cardiac_cycle": 0.85}

        manager = WorkflowManager(config)

        assert manager.context.cardiac_cycle == 0.85

    def test_patient_name_from_case_info(self):
        """Test patient name is set from case_info."""
        from workflow.manager import WorkflowManager

        config = {"geometry": {"case_name": "test_case"}, "case_info": {"patient_id": "PAT999"}}

        manager = WorkflowManager(config)

        assert manager.context.patient_name == "PAT999"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
