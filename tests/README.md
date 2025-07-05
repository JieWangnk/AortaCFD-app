# AortaCFD Testing Framework

This directory contains comprehensive tests for the AortaCFD application.

## Test Structure

```
tests/
├── unit/                           # Unit tests for individual components
│   ├── test_config/               # Configuration system tests
│   ├── test_workflow/             # Workflow management tests
│   ├── test_aortacfd_lib/         # Core library tests
│   └── test_web_interface/        # Web interface tests
├── integration/                   # Integration tests
│   ├── test_full_workflow.py      # End-to-end workflow tests
│   └── test_openfoam_integration.py # OpenFOAM integration tests
├── fixtures/                      # Test data files
│   ├── sample_stl.stl            # Sample STL geometry
│   ├── sample_flow.csv           # Sample flow rate data
│   └── sample_boundary_conditions.json # Sample BC configuration
├── conftest.py                    # Global test configuration
└── README.md                      # This file
```

## Running Tests

### Install Test Dependencies

```bash
pip install -r requirement.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Tests with coverage
pytest --cov=aortacfd_lib --cov=config --cov=workflow --cov-report=html

# Run tests in parallel
pytest -n auto

# Run specific test file
pytest tests/unit/test_config/test_builder.py -v
```

### Run Tests with Specific Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"

# Run only OpenFOAM-related tests
pytest -m requires_openfoam
```

## Test Categories

### Unit Tests

- **Configuration Tests**: Test configuration loading, merging, and validation
- **Workflow Tests**: Test task execution, error handling, and workflow management
- **Library Tests**: Test core CFD functionality, mesh processing, and utilities
- **Web Interface Tests**: Test Flask routes, file uploads, and user interactions

### Integration Tests

- **Full Workflow Tests**: End-to-end simulation pipeline testing
- **OpenFOAM Integration**: Test interaction with OpenFOAM utilities
- **File System Tests**: Test file I/O operations and case management

### Test Fixtures

- **Sample Geometry**: Simplified STL files for testing
- **Flow Data**: Realistic cardiac flow rate profiles
- **Configurations**: Test configuration files and profiles
- **Mock Data**: Synthetic data for various test scenarios

## Test Configuration

Tests are configured via `pytest.ini` and `conftest.py`:

- **Coverage**: Automatically generates coverage reports
- **Markers**: Categorize tests by type and requirements
- **Fixtures**: Provide reusable test data and environments
- **Mocking**: Mock external dependencies (OpenFOAM, ParaView)

## Continuous Integration

Tests run automatically on:
- Push to main branches
- Pull requests
- Multiple Python versions (3.8, 3.9, 3.10)

CI includes:
- Unit and integration tests
- Code coverage reporting
- Linting and formatting checks
- Security vulnerability scanning

## Mock Strategy

External dependencies are mocked to enable testing without:
- OpenFOAM installation
- ParaView installation
- Large computational resources
- Network dependencies

## Test Data

- **Fixtures**: Located in `tests/fixtures/`
- **Generated**: Created dynamically during tests
- **Realistic**: Based on actual medical CFD scenarios
- **Minimal**: Optimized for fast test execution

## Best Practices

1. **Test Isolation**: Each test is independent and can run in any order
2. **Descriptive Names**: Test names clearly describe what is being tested
3. **Mock External Dependencies**: Avoid requiring actual OpenFOAM/ParaView
4. **Fast Execution**: Tests should complete quickly for rapid feedback
5. **Comprehensive Coverage**: Aim for >80% code coverage

## Adding New Tests

1. Create test files following the naming convention `test_*.py`
2. Use appropriate fixtures from `conftest.py`
3. Add markers for categorization
4. Mock external dependencies
5. Include both positive and negative test cases
6. Update this README if adding new test categories

## Debugging Tests

```bash
# Run with verbose output
pytest -vv

# Run with detailed output on failures
pytest --tb=long

# Run specific test with debugging
pytest tests/unit/test_config/test_builder.py::TestConfigBuilder::test_build_success -vv -s

# Run with pdb on failures
pytest --pdb

# Generate HTML coverage report
pytest --cov=aortacfd_lib --cov-report=html
```

## Test Environments

Tests support multiple environments:
- **Local Development**: Run individual tests during development
- **CI/CD**: Automated testing on push/PR
- **Docker**: Containerized testing environment
- **Multiple Python Versions**: Cross-version compatibility testing

## Performance Testing

For performance-critical components:
- Use `pytest-benchmark` for timing tests
- Mock heavy operations in unit tests
- Use smaller datasets for integration tests
- Separate performance tests with markers