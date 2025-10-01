# AortaCFD Test Suite

## Overview

Comprehensive testing infrastructure for the AortaCFD patient-specific aortic blood flow simulation application.

## Test Structure

```
tests/
├── conftest.py                      # Pytest configuration and fixtures
├── unit/                            # Unit tests (fast, isolated)
│   ├── test_config/                # Configuration system tests
│   │   ├── test_builder.py        # ConfigBuilder tests (23 tests)
│   │   └── test_profile_composer.py # ProfileComposer tests (27 tests)
│   ├── test_aortacfd_lib/         # Core library tests
│   │   └── test_murray_calculator.py # Murray's Law tests (18 tests)
│   └── test_workflow/             # Workflow tests (pending)
├── integration/                    # Integration tests (slower)
│   └── test_config_workflow.py    # End-to-end config tests (9 tests)
└── fixtures/                      # Test data and fixtures
    ├── sample_configs/            # Sample JSON configs
    ├── sample_stl_files/          # Minimal STL geometries
    └── sample_bc_data/            # Boundary condition data
```

## Running Tests

### Run All Tests
```bash
source venv/bin/activate
python -m pytest tests/ -v
```

### Run Specific Test Categories
```bash
# Unit tests only (fast)
python -m pytest tests/unit/ -v

# Integration tests only
python -m pytest tests/integration/ -v

# Specific module
python -m pytest tests/unit/test_config/test_builder.py -v
```

### Run with Coverage
```bash
python -m pytest tests/ --cov=src --cov-report=html
# View coverage report: open htmlcov/index.html
```

### Run with Markers
```bash
# Only slow tests
python -m pytest -m slow

# Skip slow tests
python -m pytest -m "not slow"

# Only unit tests
python -m pytest -m unit
```

## Test Results

### Current Status (2025-10-01)

**✅ 18 of 23 ConfigBuilder tests passing (78%)**
- Deep merge functionality: 5/5 passing
- Profile building: 3/3 passing
- Basic validation: 1/1 passing
- Merge order: 1/1 passing
- Warnings (need logging setup): 5 pending

**⚠️ ProfileComposer tests: 11/27 passing (41%)**
- Basic composition: 11 passing
- Fragment details need adjustment to match actual implementation

**🎯 Murray's Law Calculator: 18 tests created (not yet run)**
- Exponent determination
- Flow ratio calculation
- Physical correctness

**✅ Integration tests: Framework created, 9 tests**
- Full configuration workflow
- Merge order validation
- Performance benchmarks

### Test Coverage

Current coverage: ~8% overall (initial test infrastructure)

**Well-covered modules:**
- `src/config/profiles/fragments/`: 100%
- `src/config/profiles/profile_builder.py`: 72%
- `src/workflow/base_task.py`: 69%

**Needs coverage:**
- `src/aortacfd_lib/` modules: <15%
- `src/patient_runner/`: 0%
- `src/workflow/tasks/`: 11-19%

## Available Test Fixtures

### Configuration Fixtures
- `minimal_config`: Bare minimum valid config
- `full_config`: Complete configuration with all sections
- `invalid_config`: Config with invalid physical parameters
- `boundary_conditions_config`: Sample BC configuration

### Geometry Fixtures
- `sample_outlet_areas`: Outlet cross-sectional areas for Murray's Law
- `expected_murray_ratios`: Expected flow ratios
- `simple_tube_geometry`: Cylindrical tube geometry data

### Directory Fixtures
- `temp_case_dir`: Temporary case directory (auto-cleanup)
- `temp_output_dir`: Temporary output directory (auto-cleanup)
- `sample_configs_dir`: Path to sample config files
- `sample_stl_dir`: Path to sample STL files

### Helper Fixtures
- `write_json_file`: Helper to write JSON test files
- `create_minimal_stl`: Create minimal STL for testing
- `create_flow_csv`: Create sample flow CSV files

## Test Markers

Tests are marked with categories for selective execution:

- `@pytest.mark.unit`: Fast unit tests (<100ms each)
- `@pytest.mark.integration`: Slower integration tests
- `@pytest.mark.slow`: Very slow tests (>1 second)
- `@pytest.mark.requires_openfoam`: Tests requiring OpenFOAM installation

## Writing New Tests

### Unit Test Template

```python
import pytest
from src.module import MyClass

class TestMyClass:
    """Test MyClass functionality."""

    @pytest.fixture
    def my_instance(self):
        """Create test instance."""
        return MyClass()

    def test_basic_functionality(self, my_instance):
        """Test basic operation."""
        result = my_instance.do_something()
        assert result is not None

    @pytest.mark.unit
    def test_edge_case(self, my_instance):
        """Test edge case handling."""
        with pytest.raises(ValueError):
            my_instance.do_something_invalid()
```

### Integration Test Template

```python
import pytest

@pytest.mark.integration
class TestWorkflow:
    """Test complete workflow."""

    def test_full_pipeline(self, temp_case_dir):
        """Test end-to-end pipeline."""
        # Setup
        # Execute
        # Verify
```

## CI/CD Integration

Tests run automatically on:
- Push to main branch
- Pull requests
- Scheduled nightly builds

Configuration: `.github/workflows/ci.yml`

## Test Data

### Sample Configurations

- `minimal_patient.json`: Minimal valid patient config
- `full_patient.json`: Complete patient config with all sections
- `boundary_conditions.json`: Sample BC configuration
- `simple_flow.csv`: Sample inlet flow data (11 time points)

### Expected Test Outcomes

**Deep Merge Tests:**
- Simple dict merging works correctly
- Nested dict merging preserves structure
- Empty dict handling
- None value handling

**Configuration Building:**
- All 9 standard profiles load without errors
- Profile settings correctly applied
- User config overrides profile settings
- Validation catches invalid parameters

**Murray's Law:**
- Equal outlets get equal flow ratios
- Flow ratios sum to 1.0
- Larger outlets get proportionally more flow
- Exponent affects distribution as expected

## Troubleshooting

### Tests Not Found
```bash
# Ensure tests directory is in Python path
export PYTHONPATH=/path/to/AortaCFD-app:$PYTHONPATH
```

### Import Errors
```bash
# Activate virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Coverage Warnings
Some files (e.g., `publication_reporter.py`) may have syntax that coverage can't parse. This doesn't affect test execution.

## Next Steps

1. **Fix logging tests**: Set up proper logging capture for validation warnings
2. **Adjust ProfileComposer tests**: Match actual fragment names ("aggressive" vs "fast", etc.)
3. **Run Murray's Law tests**: Verify all 18 tests pass
4. **Add mesh tests**: Test mesh generation and quality checking
5. **Add workflow tests**: Test complete patient case execution
6. **Increase coverage**: Target 70% overall coverage

## References

- Pytest documentation: https://docs.pytest.org/
- Coverage.py: https://coverage.readthedocs.io/
- Python testing best practices: https://docs.python-guide.org/writing/tests/
