"""
Test suite for workflow base_task module.

Tests cover:
- ExecutionContext dataclass
- TaskMetadata dataclass
- Task base class
- AortaCFDError exception
- Backward compatibility functions
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from workflow.base_task import (
    ExecutionContext,
    TaskMetadata,
    Task,
    AortaCFDError,
    TaskDependencyError,
    TaskExecutionError,
    context_to_dict,
    dict_to_context,
)


class TestExecutionContext:
    """Test ExecutionContext dataclass."""

    def test_default_values(self):
        """Test default initialization values."""
        ctx = ExecutionContext()

        assert ctx.case_directory == ""
        assert ctx.patient_name == ""
        assert ctx.cardiac_cycle == 0.0
        assert ctx.mesh_generated is False
        assert ctx.bc_generated is False
        assert ctx.solver_completed is False
        assert ctx.post_processed is False
        assert ctx.custom_data == {}

    def test_init_with_values(self):
        """Test initialization with custom values."""
        ctx = ExecutionContext(
            case_directory="/path/to/case",
            patient_name="PAT001",
            cardiac_cycle=0.85,
            mesh_generated=True,
            bc_generated=True,
        )

        assert ctx.case_directory == "/path/to/case"
        assert ctx.patient_name == "PAT001"
        assert ctx.cardiac_cycle == 0.85
        assert ctx.mesh_generated is True
        assert ctx.bc_generated is True

    def test_case_path_property(self):
        """Test case_path property returns Path object."""
        ctx = ExecutionContext(case_directory="/path/to/case")

        assert isinstance(ctx.case_path, Path)
        assert str(ctx.case_path) == "/path/to/case"

    def test_case_path_empty(self):
        """Test case_path with empty directory."""
        ctx = ExecutionContext()
        assert ctx.case_path == Path()

    def test_to_dict(self):
        """Test conversion to dictionary."""
        ctx = ExecutionContext(
            case_directory="/path/to/case",
            patient_name="PAT001",
            cardiac_cycle=0.85,
            mesh_generated=True,
        )
        ctx.custom_data['extra_key'] = 'extra_value'

        d = ctx.to_dict()

        assert d['case_directory'] == "/path/to/case"
        assert d['patient_name'] == "PAT001"
        assert d['cardiac_cycle'] == 0.85
        assert d['mesh_generated'] is True
        assert d['extra_key'] == 'extra_value'

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            'case_directory': '/path/to/case',
            'patient_name': 'PAT001',
            'cardiac_cycle': 0.85,
            'mesh_generated': True,
            'custom_key': 'custom_value',
        }

        ctx = ExecutionContext.from_dict(data)

        assert ctx.case_directory == '/path/to/case'
        assert ctx.patient_name == 'PAT001'
        assert ctx.cardiac_cycle == 0.85
        assert ctx.mesh_generated is True
        assert ctx.custom_data['custom_key'] == 'custom_value'


class TestExecutionContextDictLikeAccess:
    """Test dict-like access on ExecutionContext."""

    def test_getitem(self):
        """Test __getitem__ for known attributes."""
        ctx = ExecutionContext(case_directory="/path/to/case")

        assert ctx['case_directory'] == "/path/to/case"

    def test_getitem_custom(self):
        """Test __getitem__ for custom data."""
        ctx = ExecutionContext()
        ctx.custom_data['my_key'] = 'my_value'

        assert ctx['my_key'] == 'my_value'

    def test_setitem_known(self):
        """Test __setitem__ for known attributes."""
        ctx = ExecutionContext()
        ctx['case_directory'] = "/new/path"
        ctx['cardiac_cycle'] = 0.9

        assert ctx.case_directory == "/new/path"
        assert ctx.cardiac_cycle == 0.9

    def test_setitem_custom(self):
        """Test __setitem__ for custom data."""
        ctx = ExecutionContext()
        ctx['custom_key'] = 'custom_value'

        assert ctx.custom_data['custom_key'] == 'custom_value'

    def test_contains_known_attr(self):
        """Test __contains__ for known attributes."""
        ctx = ExecutionContext(case_directory="/path/to/case")

        assert 'case_directory' in ctx
        assert 'mesh_generated' in ctx  # Boolean, always True for 'in'

    def test_contains_empty_string(self):
        """Test __contains__ for empty string attribute."""
        ctx = ExecutionContext(case_directory="")

        # Empty string should return False for 'in'
        assert 'case_directory' not in ctx

    def test_contains_custom(self):
        """Test __contains__ for custom data."""
        ctx = ExecutionContext()
        ctx.custom_data['my_key'] = 'my_value'

        assert 'my_key' in ctx
        assert 'nonexistent' not in ctx

    def test_get_method(self):
        """Test get method."""
        ctx = ExecutionContext(case_directory="/path/to/case")

        assert ctx.get('case_directory') == "/path/to/case"
        assert ctx.get('nonexistent') is None
        assert ctx.get('nonexistent', 'default') == 'default'

    def test_get_empty_returns_default(self):
        """Test get returns default for empty string."""
        ctx = ExecutionContext(case_directory="")

        assert ctx.get('case_directory', '/default/path') == '/default/path'

    def test_get_custom_data(self):
        """Test get for custom data."""
        ctx = ExecutionContext()
        ctx.custom_data['key'] = 'value'

        assert ctx.get('key') == 'value'
        assert ctx.get('missing', 'default') == 'default'


class TestExecutionContextLogger:
    """Test ExecutionContext logger functionality."""

    def test_get_logger(self):
        """Test get_logger returns a logger."""
        ctx = ExecutionContext()
        logger = ctx.get_logger("test")

        assert logger is not None


class TestTaskMetadata:
    """Test TaskMetadata dataclass."""

    def test_default_values(self):
        """Test default initialization values."""
        meta = TaskMetadata(name="TestTask")

        assert meta.name == "TestTask"
        assert meta.dependencies == []
        assert meta.requires_mesh is False
        assert meta.requires_bc is False
        assert meta.produces == []
        assert meta.description == ""

    def test_with_all_values(self):
        """Test initialization with all values."""
        meta = TaskMetadata(
            name="ComplexTask",
            dependencies=["task1", "task2"],
            requires_mesh=True,
            requires_bc=True,
            produces=["output1", "output2"],
            description="A complex task",
        )

        assert meta.name == "ComplexTask"
        assert meta.dependencies == ["task1", "task2"]
        assert meta.requires_mesh is True
        assert meta.requires_bc is True
        assert meta.produces == ["output1", "output2"]
        assert meta.description == "A complex task"


class TestTask:
    """Test Task base class."""

    def test_task_init(self):
        """Test Task initialization."""
        class ConcreteTask(Task):
            metadata = TaskMetadata(name="ConcreteTask")

            def execute(self, context):
                return True

        config = {'key': 'value'}
        task = ConcreteTask(config)

        assert task.config == config
        assert task.log is not None

    def test_task_repr(self):
        """Test Task __repr__."""
        class ConcreteTask(Task):
            metadata = TaskMetadata(name="MyTask")

            def execute(self, context):
                return True

        task = ConcreteTask({})
        repr_str = repr(task)

        assert "ConcreteTask" in repr_str
        assert "MyTask" in repr_str

    def test_validate_dependencies_pass(self):
        """Test validate_dependencies passes when met."""
        class ConcreteTask(Task):
            metadata = TaskMetadata(name="Test", requires_mesh=True)

            def execute(self, context):
                return True

        task = ConcreteTask({})
        ctx = ExecutionContext(mesh_generated=True)

        # Should not raise
        assert task.validate_dependencies(ctx) is True

    def test_validate_dependencies_mesh_fail(self):
        """Test validate_dependencies fails when mesh required but not generated."""
        class ConcreteTask(Task):
            metadata = TaskMetadata(name="Test", requires_mesh=True)

            def execute(self, context):
                return True

        task = ConcreteTask({})
        ctx = ExecutionContext(mesh_generated=False)

        with pytest.raises(TaskDependencyError) as exc_info:
            task.validate_dependencies(ctx)

        assert "requires mesh" in str(exc_info.value)

    def test_validate_dependencies_bc_fail(self):
        """Test validate_dependencies fails when BC required but not generated."""
        class ConcreteTask(Task):
            metadata = TaskMetadata(name="Test", requires_bc=True)

            def execute(self, context):
                return True

        task = ConcreteTask({})
        ctx = ExecutionContext(bc_generated=False)

        with pytest.raises(TaskDependencyError) as exc_info:
            task.validate_dependencies(ctx)

        assert "requires boundary conditions" in str(exc_info.value)

    def test_run_method(self):
        """Test run method validates then executes."""
        class ConcreteTask(Task):
            metadata = TaskMetadata(name="Test", requires_mesh=True)
            executed = False

            def execute(self, context):
                self.executed = True
                return True

        task = ConcreteTask({})
        ctx = ExecutionContext(mesh_generated=True)

        result = task.run(ctx)

        assert result is True
        assert task.executed is True

    def test_run_method_fails_validation(self):
        """Test run method fails if validation fails."""
        class ConcreteTask(Task):
            metadata = TaskMetadata(name="Test", requires_mesh=True)

            def execute(self, context):
                return True

        task = ConcreteTask({})
        ctx = ExecutionContext(mesh_generated=False)

        with pytest.raises(TaskDependencyError):
            task.run(ctx)


class TestExceptions:
    """Test custom exception classes."""

    def test_aortacfd_error(self):
        """Test AortaCFDError can be raised and caught."""
        with pytest.raises(AortaCFDError):
            raise AortaCFDError("Test error")

    def test_task_dependency_error(self):
        """Test TaskDependencyError is subclass of AortaCFDError."""
        assert issubclass(TaskDependencyError, AortaCFDError)

        with pytest.raises(AortaCFDError):
            raise TaskDependencyError("Dependency not met")

    def test_task_execution_error(self):
        """Test TaskExecutionError is subclass of AortaCFDError."""
        assert issubclass(TaskExecutionError, AortaCFDError)

        with pytest.raises(AortaCFDError):
            raise TaskExecutionError("Execution failed")


class TestBackwardCompatibility:
    """Test backward compatibility functions."""

    def test_context_to_dict(self):
        """Test context_to_dict function."""
        ctx = ExecutionContext(
            case_directory="/path/to/case",
            patient_name="PAT001",
        )

        d = context_to_dict(ctx)

        assert d['case_directory'] == "/path/to/case"
        assert d['patient_name'] == "PAT001"

    def test_dict_to_context(self):
        """Test dict_to_context function."""
        data = {
            'case_directory': '/path/to/case',
            'patient_name': 'PAT001',
            'cardiac_cycle': 0.85,
        }

        ctx = dict_to_context(data)

        assert isinstance(ctx, ExecutionContext)
        assert ctx.case_directory == '/path/to/case'
        assert ctx.patient_name == 'PAT001'
        assert ctx.cardiac_cycle == 0.85

    def test_roundtrip(self):
        """Test dict->context->dict roundtrip."""
        original = {
            'case_directory': '/path/to/case',
            'patient_name': 'PAT001',
            'cardiac_cycle': 0.85,
            'mesh_generated': True,
            'bc_generated': False,
            'solver_completed': False,
            'post_processed': False,
        }

        ctx = dict_to_context(original)
        result = context_to_dict(ctx)

        for key in original:
            assert result[key] == original[key]


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
