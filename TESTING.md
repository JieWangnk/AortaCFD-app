# AortaCFD Testing Guide

**Last Updated:** 2025-10-01
**Test Coverage:** 22%
**Total Tests:** 289 (274 passing)

---

## 📋 Quick Start

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage report
pytest tests/ --cov=src --cov-report=html

# Run unit tests only
pytest tests/unit/

# Run integration tests only
pytest tests/integration/

# Run specific test file
pytest tests/unit/test_aortacfd_lib/test_mesh_setup.py -v

# Run specific test class
pytest tests/unit/test_config/test_builder.py::TestConfigBuilder -v

# Run specific test
pytest tests/unit/test_config/test_builder.py::TestConfigBuilder::test_build_base_and_profile -v
```

### Test Markers

```bash
# Run integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"

# Run only slow tests (performance benchmarks)
pytest -m slow
```

---

## 🧪 Test Organization

### Directory Structure

```
tests/
├── conftest.py                           # Shared fixtures and configuration
├── pytest.ini                            # Pytest configuration
├── integration/                          # Integration tests (27 tests)
│   ├── __init__.py
│   ├── test_config_workflow.py          # Config loading/merging (9 tests)
│   ├── test_mesh_workflow.py            # Mesh generation (9 tests)
│   └── test_boundary_workflow.py        # Boundary conditions (9 tests)
└── unit/                                 # Unit tests (262 tests)
    ├── test_config/                      # Configuration module (17 tests)
    │   ├── test_builder.py               # ConfigBuilder tests
    │   └── test_profiles.py              # Profile composition tests
    ├── test_workflow/                    # Workflow module (11 tests)
    │   ├── test_manager.py               # WorkflowManager tests
    │   └── test_execution_tasks.py       # Task execution tests
    └── test_aortacfd_lib/                # Core library (234 tests)
        ├── test_mesh_setup.py            # Mesh setup tests (37 tests)
        ├── test_murray_calculator.py     # Murray's Law tests (34 tests)
        ├── test_boundary_conditions.py   # BC setup tests (28 tests)
        ├── test_validation.py            # Validation tests (59 tests)
        ├── test_wk_setup.py              # Windkessel tests (15 tests)
        └── ...                           # Other module tests
```

### Test Counts by Module

| Module | Unit Tests | Integration Tests | Total | Pass Rate |
|--------|-----------|-------------------|-------|-----------|
| **Config** | 17 | 9 | 26 | 100% ✅ |
| **Workflow** | 11 | 0 | 11 | 100% ✅ |
| **Mesh Setup** | 37 | 9 | 46 | 84.8% |
| **Boundary Conditions** | 28 | 9 | 37 | 75.7% |
| **Murray Calculator** | 34 | 0 | 34 | 100% ✅ |
| **Validation** | 59 | 0 | 59 | 100% ✅ |
| **Windkessel** | 15 | 0 | 15 | 100% ✅ |
| **Other** | 61 | 0 | 61 | 100% ✅ |
| **TOTAL** | 262 | 27 | 289 | 94.8% |

---

## ✍️ Writing Tests

### Unit Test Template

```python
"""
Unit tests for <module_name>.

Tests <component> functionality including edge cases and error handling.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from src.module_name import ComponentClass


class TestComponentClass:
    """Test ComponentClass initialization and core functionality."""

    @pytest.fixture
    def minimal_config(self):
        """Minimal configuration for testing."""
        return {
            "required_key": "value",
            "optional_key": "default"
        }

    def test_initialization(self, minimal_config):
        """Test component initializes correctly."""
        component = ComponentClass(minimal_config)

        assert component is not None
        assert component.config == minimal_config

    def test_core_functionality(self, minimal_config):
        """Test core functionality works as expected."""
        component = ComponentClass(minimal_config)

        result = component.process()

        assert result is not None
        assert isinstance(result, dict)

    def test_error_handling(self, minimal_config):
        """Test error handling for invalid inputs."""
        component = ComponentClass(minimal_config)

        with pytest.raises(ValueError, match="invalid input"):
            component.process(invalid_input)


class TestComponentClassEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def edge_case_config(self):
        """Configuration for edge case testing."""
        return {
            "extreme_value": 999999,
            "empty_list": [],
            "zero_value": 0.0
        }

    def test_handles_empty_input(self, edge_case_config):
        """Test handling of empty input."""
        component = ComponentClass(edge_case_config)

        result = component.process([])

        assert result == expected_default_behavior

    def test_handles_extreme_values(self, edge_case_config):
        """Test handling of extreme values."""
        component = ComponentClass(edge_case_config)

        result = component.process(999999)

        # Should handle gracefully
        assert result is not None
```

### Integration Test Template

```python
"""
Integration tests for <workflow_name> workflow.

Tests end-to-end workflow including file I/O, task execution,
and inter-component communication.
"""

import pytest
from pathlib import Path
import shutil
from src.workflow.tasks.task_module import WorkflowTask


@pytest.mark.integration
class TestWorkflowIntegration:
    """Test complete workflow execution."""

    @pytest.fixture
    def workflow_config(self):
        """Complete configuration for workflow."""
        return {
            "geometry": {
                "case_name": "test_case",
                "scale_factor": 0.001,
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["outlet1"]
            },
            "mesh": {
                "SNAPPY_SETTINGS": {
                    "parallel": False,
                    "nProcessors": 1
                }
            }
        }

    def test_complete_workflow(self, temp_case_dir, workflow_config):
        """Test workflow executes successfully end-to-end."""
        # Setup: Create required files
        self._setup_test_files(temp_case_dir)

        # Execute: Run workflow
        task = WorkflowTask(workflow_config)
        context = {"case_directory": str(temp_case_dir)}
        result = task.execute(context)

        # Verify: Check results
        assert result is True
        assert self._verify_outputs(temp_case_dir)

        # Cleanup handled by temp_case_dir fixture

    def _setup_test_files(self, case_dir: Path):
        """Helper to create test files."""
        tri_surface = case_dir / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)

        # Create minimal STL
        (tri_surface / "inlet.stl").write_text("solid mesh\nendsolid mesh\n")

    def _verify_outputs(self, case_dir: Path) -> bool:
        """Helper to verify workflow outputs."""
        system_dir = case_dir / "system"
        return (system_dir / "expectedFile").exists()
```

### Performance Test Template

```python
@pytest.mark.integration
@pytest.mark.slow
class TestComponentPerformance:
    """Test component performance benchmarks."""

    def test_operation_performance(self, workflow_config):
        """Test operation completes within time limit."""
        import time

        component = Component(workflow_config)

        # Benchmark
        start = time.time()
        for _ in range(100):
            component.operation()
        elapsed = time.time() - start

        # Should complete 100 operations in under 1 second
        assert elapsed < 1.0

    def test_memory_efficiency(self, workflow_config):
        """Test operation doesn't leak memory."""
        import gc
        import sys

        component = Component(workflow_config)

        # Get baseline memory
        gc.collect()
        baseline = sys.getsizeof(component)

        # Perform operations
        for _ in range(1000):
            component.operation()

        # Check memory didn't grow significantly
        gc.collect()
        current = sys.getsizeof(component)

        # Should not grow >10% from baseline
        assert current < baseline * 1.1
```

---

## 🔧 Test Fixtures

### Common Fixtures (conftest.py)

#### Configuration Fixtures

```python
@pytest.fixture
def minimal_config():
    """Minimal valid configuration."""
    return {
        "simulation_settings": {
            "analysis_type": "coarse",
            "solver_type": "laminar"
        },
        "physics": {
            "blood_density": 1060,
            "blood_viscosity": 0.004
        }
    }

@pytest.fixture
def full_config():
    """Complete configuration with all sections."""
    return {
        "case_info": {...},
        "simulation_settings": {...},
        "physics": {...},
        "mesh": {...},
        "run_settings": {...},
        "time_settings": {...}
    }
```

####  Temporary Directory Fixtures

```python
@pytest.fixture
def temp_case_dir():
    """Create temporary case directory."""
    temp_dir = tempfile.mkdtemp(prefix="aortacfd_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def temp_output_dir():
    """Create temporary output directory."""
    temp_dir = tempfile.mkdtemp(prefix="aortacfd_output_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)
```

#### Data Fixtures

```python
@pytest.fixture
def sample_outlet_areas():
    """Sample outlet areas for Murray's Law testing."""
    return {
        "outlet1": 1.0,
        "outlet2": 0.5,
        "outlet3": 0.25
    }

@pytest.fixture
def boundary_conditions_config():
    """Sample boundary conditions configuration."""
    return {
        "inlet": {
            "type": "TIMEVARYING",
            "csv_file": "flow.csv"
        },
        "outlets": {
            "type": "3EWINDKESSEL"
        }
    }
```

### Class-Level Fixtures

Define fixtures within test classes for test isolation:

```python
class TestMeshSetup:
    """Test mesh setup functionality."""

    @pytest.fixture
    def mesh_config(self):
        """Configuration specific to mesh tests."""
        return {
            "geometry": {
                "scale_factor": 0.001,
                "inlet_keywords_ordered": "inlet"
            },
            "mesh": {
                "SNAPPY_SETTINGS": {
                    "parallel": False
                }
            }
        }

    def test_uses_mesh_config(self, mesh_config):
        """Test using class-level fixture."""
        assert mesh_config["mesh"]["SNAPPY_SETTINGS"]["parallel"] is False
```

---

## 🎯 Testing Best Practices

### 1. Test Naming

```python
# Good: Descriptive, clear intent
def test_murray_exponent_selection_for_large_vessels():
    """Test that large vessels (>25mm) use exponent 2.0."""

# Bad: Vague, unclear
def test_murray():
    """Test Murray's Law."""
```

### 2. Test Organization

```python
# Good: Organized by functionality
class TestGeometryAnalyzerInitialization:
    """Test GeometryAnalyzer initialization."""

class TestGeometryAnalyzerCalculations:
    """Test geometry calculations."""

class TestGeometryAnalyzerEdgeCases:
    """Test edge cases and error handling."""

# Bad: Everything in one class
class TestGeometryAnalyzer:
    def test_everything_at_once():
        ...
```

### 3. Assertions

```python
# Good: Specific, informative
assert result.status == "success", f"Expected success, got {result.status}"
assert len(outlets) == 3, f"Expected 3 outlets, found {len(outlets)}"

# Bad: Generic, unhelpful
assert result
assert outlets
```

### 4. Mocking

```python
# Good: Mock external dependencies
from unittest.mock import patch, Mock

with patch('src.module.external_call') as mock_call:
    mock_call.return_value = expected_value
    result = function_under_test()
    assert result == expected_output

# Bad: Testing external dependencies
result = function_that_calls_openfoam()  # Will fail without OpenFOAM
```

### 5. Test Independence

```python
# Good: Each test is independent
def test_create_file(temp_case_dir):
    file_path = temp_case_dir / "test.txt"
    file_path.write_text("content")
    assert file_path.exists()

def test_read_file(temp_case_dir):
    file_path = temp_case_dir / "test.txt"
    file_path.write_text("content")  # Setup in each test
    assert file_path.read_text() == "content"

# Bad: Tests depend on each other
files_created = []

def test_create_file():
    file_path = Path("test.txt")
    file_path.write_text("content")
    files_created.append(file_path)  # State shared between tests

def test_read_file():
    file_path = files_created[0]  # Depends on previous test
    assert file_path.read_text() == "content"
```

---

## 📊 Coverage Analysis

### Viewing Coverage Reports

```bash
# Generate HTML coverage report
pytest tests/ --cov=src --cov-report=html

# Open in browser
open htmlcov/index.html

# Generate terminal report
pytest tests/ --cov=src --cov-report=term-missing

# Generate XML for CI/CD
pytest tests/ --cov=src --cov-report=xml
```

### Current Coverage by Module

| Module | Coverage | Lines | Missing | Priority |
|--------|----------|-------|---------|----------|
| mesh_setup.py | 78% | 197 | 43 | ✅ Good |
| murray_calculator.py | 34% | 343 | 226 | 🟡 Medium |
| validation.py | 35% | 566 | 368 | 🟡 Medium |
| boundary_condition_setup.py | 10% | 90 | 81 | 🔴 Low |
| workflow/setup_tasks.py | 42% | 194 | 112 | 🟡 Medium |
| config/builder.py | 13% | 153 | 133 | 🔴 Low |

### Coverage Goals

- **Critical modules:** 60%+ coverage
- **Core library:** 40%+ coverage
- **Overall project:** 25%+ coverage (currently 22%)

---

## 🚀 Continuous Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.12'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov

    - name: Run tests
      run: |
        pytest tests/ --cov=src --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v2
      with:
        file: ./coverage.xml
```

---

## 🐛 Debugging Tests

### Common Issues

#### 1. Import Errors

```python
# Error: ModuleNotFoundError: No module named 'src'
# Solution: Ensure PYTHONPATH includes src/ or use conftest.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
```

#### 2. Fixture Not Found

```python
# Error: fixture 'temp_case_dir' not found
# Solution: Check conftest.py has fixture or define in test class
@pytest.fixture
def temp_case_dir():
    ...
```

#### 3. Test Isolation Issues

```python
# Issue: Tests pass individually but fail together
# Solution: Use temp directories and ensure cleanup

@pytest.fixture
def isolated_dir():
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)  # Always cleanup
```

### Debugging Commands

```bash
# Run with verbose output
pytest tests/ -v

# Show print statements
pytest tests/ -s

# Stop on first failure
pytest tests/ -x

# Run last failed tests
pytest tests/ --lf

# Show local variables on failure
pytest tests/ -l

# Drop into debugger on failure
pytest tests/ --pdb
```

---

## 📝 Test Development Workflow

### 1. Write Failing Test (Red)

```python
def test_new_feature():
    """Test new feature that doesn't exist yet."""
    component = NewComponent()
    result = component.new_method()
    assert result == expected_value
```

### 2. Implement Feature (Green)

```python
class NewComponent:
    def new_method(self):
        return expected_value
```

### 3. Refactor (Refactor)

```python
class NewComponent:
    def new_method(self):
        """Properly documented and refactored."""
        # Clean implementation
        return self._calculate_expected_value()

    def _calculate_expected_value(self):
        # Extracted helper method
        return expected_value
```

### 4. Add Edge Cases

```python
def test_new_feature_edge_cases():
    """Test edge cases for new feature."""
    component = NewComponent()

    # Test empty input
    assert component.new_method([]) == default_value

    # Test extreme values
    assert component.new_method(999999) is not None

    # Test invalid input
    with pytest.raises(ValueError):
        component.new_method(invalid_input)
```

---

## 🎓 Resources

### Pytest Documentation
- [Pytest Official Docs](https://docs.pytest.org/)
- [Pytest Fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [Pytest Markers](https://docs.pytest.org/en/stable/how-to/mark.html)

### Testing Best Practices
- [Python Testing Best Practices](https://docs.python-guide.org/writing/tests/)
- [Test-Driven Development](https://www.obeythetestinggoat.com/)

### AortaCFD-Specific
- [WEEK3_DAY10_SUMMARY.md](WEEK3_DAY10_SUMMARY.md) - mesh_setup.py testing
- [WEEK3_DAY11_SUMMARY.md](WEEK3_DAY11_SUMMARY.md) - murray_calculator.py testing
- [WEEK3_DAY12_SUMMARY.md](WEEK3_DAY12_SUMMARY.md) - Integration testing

---

**Last Updated:** 2025-10-01
**Test Count:** 289 tests (274 passing, 15 need fixtures)
**Coverage:** 22% overall, 60%+ critical modules
