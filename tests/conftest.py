"""
Pytest configuration and shared fixtures for AortaCFD testing.
"""

import pytest
import sys
import os
from pathlib import Path
import json
import tempfile
import shutil

# Add src to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


# ============================================================================
# Path Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def project_root():
    """Project root directory."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def fixtures_dir():
    """Test fixtures directory."""
    return PROJECT_ROOT / "tests" / "fixtures"


@pytest.fixture(scope="session")
def sample_configs_dir(fixtures_dir):
    """Sample configuration files directory."""
    return fixtures_dir / "sample_configs"


@pytest.fixture(scope="session")
def sample_stl_dir(fixtures_dir):
    """Sample STL geometry files directory."""
    return fixtures_dir / "sample_stl_files"


@pytest.fixture(scope="session")
def sample_bc_dir(fixtures_dir):
    """Sample boundary condition data directory."""
    return fixtures_dir / "sample_bc_data"


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def minimal_config():
    """Minimal valid configuration for testing."""
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
    """Full configuration with all sections."""
    return {
        "case_info": {
            "patient_id": "test_patient",
            "description": "Test case for unit testing"
        },
        "simulation_settings": {
            "analysis_type": "medium",
            "solver_type": "rans"
        },
        "physics": {
            "blood_density": 1060,
            "blood_viscosity": 0.004,
            "default_density": 1060,
            "rho": 1060,
            "nu": 3.77e-06
        },
        "mesh": {
            "SNAPPY_SETTINGS": {
                "parallel": True,
                "nProcessors": 4
            }
        },
        "run_settings": {
            "solution_type": "parallel",
            "subdomains": 4,
            "decomposition_method": "scotch"
        },
        "time_settings": {
            "end_time": 1.0,
            "delta_t": 0.001,
            "write_interval": 0.1
        },
        "openfoam_version": "12",
        "openfoam_major_version": 12
    }


@pytest.fixture
def invalid_config():
    """Configuration with invalid physical parameters."""
    return {
        "simulation_settings": {
            "analysis_type": "coarse",
            "solver_type": "laminar"
        },
        "physics": {
            "blood_density": 5000,  # Invalid: too high
            "blood_viscosity": 0.5   # Invalid: too high
        },
        "time_settings": {
            "end_time": -1.0  # Invalid: negative
        }
    }


@pytest.fixture
def boundary_conditions_config():
    """Sample boundary conditions configuration."""
    return {
        "inlet": {
            "type": "TIMEVARYING",
            "csv_file": "BPM75.csv",
            "data_type": "velocity",
            "profile": "plug_flow",
            "orientation": "out"
        },
        "outlets": {
            "type": "3EWINDKESSEL",
            "windkessel_settings": {
                "systolic_pressure": 120,
                "diastolic_pressure": 80,
                "methodology": "murray_law_automatic"
            }
        },
        "walls": {
            "type": "no_slip",
            "roughness": 0.0
        }
    }


# ============================================================================
# Temporary Directory Fixtures
# ============================================================================

@pytest.fixture
def temp_case_dir():
    """Create a temporary case directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="aortacfd_test_")
    yield Path(temp_dir)
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="aortacfd_output_")
    yield Path(temp_dir)
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================================
# Murray's Law Fixtures
# ============================================================================

@pytest.fixture
def sample_outlet_areas():
    """Sample outlet cross-sectional areas for Murray's Law testing."""
    return {
        "outlet1": 1.0,   # Reference outlet (normalized)
        "outlet2": 0.5,
        "outlet3": 0.25,
        "outlet4": 0.125
    }


@pytest.fixture
def expected_murray_ratios():
    """Expected flow ratios based on Murray's Law (d^3 relationship)."""
    # For areas: 1.0, 0.5, 0.25, 0.125
    # Diameters: 1.128, 0.798, 0.564, 0.399
    # Flow ratios (d^3): 1.0, 0.354, 0.125, 0.044
    # Normalized: 0.666, 0.236, 0.083, 0.029 (sum ≈ 1.014, adjust to 1.0)
    return {
        "outlet1": 0.656,
        "outlet2": 0.232,
        "outlet3": 0.082,
        "outlet4": 0.029
    }


# ============================================================================
# Geometry Fixtures
# ============================================================================

@pytest.fixture
def simple_tube_geometry():
    """Simple cylindrical tube geometry data for testing."""
    return {
        "inlet_area": 3.14,  # π * r^2, r=1
        "outlet_area": 3.14,
        "length": 10.0,
        "diameter": 2.0
    }


# ============================================================================
# Profile Fixtures
# ============================================================================

@pytest.fixture
def available_profiles():
    """List of available simulation profiles."""
    return [
        "sim_laminar_coarse",
        "sim_laminar_medium",
        "sim_laminar_fine",
        "sim_rans_coarse",
        "sim_rans_medium",
        "sim_rans_fine",
        "sim_les_medium",
        "sim_les_fine"
    ]


@pytest.fixture
def profile_metadata():
    """Metadata about simulation profiles."""
    return {
        "sim_laminar_coarse": {
            "resolution_fragment": "coarse",
            "solver_recipe_fragment": "fast",
            "turbulence_model": "laminar"
        },
        "sim_rans_medium": {
            "resolution_fragment": "medium",
            "solver_recipe_fragment": "balanced",
            "turbulence_model": "rans_komega_sst"
        },
        "sim_les_fine": {
            "resolution_fragment": "fine",
            "solver_recipe_fragment": "accurate",
            "turbulence_model": "les_wale"
        }
    }


# ============================================================================
# Helper Functions for Tests
# ============================================================================

@pytest.fixture
def write_json_file():
    """Helper function to write JSON files for testing."""
    def _write_json(filepath: Path, data: dict):
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return filepath
    return _write_json


@pytest.fixture
def create_minimal_stl():
    """Helper function to create a minimal STL file for testing."""
    def _create_stl(filepath: Path):
        # Minimal ASCII STL (single triangle)
        stl_content = """solid test
  facet normal 0 0 1
    outer loop
      vertex 0 0 0
      vertex 1 0 0
      vertex 0 1 0
    endloop
  endfacet
endsolid test
"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(stl_content)
        return filepath
    return _create_stl


@pytest.fixture
def create_flow_csv():
    """Helper function to create a sample flow CSV file."""
    def _create_csv(filepath: Path, time_points=10):
        import csv
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Time', 'Flow'])
            for i in range(time_points):
                time = i * 0.1
                flow = 0.5 + 0.3 * (i / time_points)  # Simple ramp
                writer.writerow([time, flow])
        return filepath
    return _create_csv


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_openfoam_installed(monkeypatch):
    """Mock OpenFOAM installation check."""
    def mock_which(cmd):
        if cmd in ['blockMesh', 'snappyHexMesh', 'foamRun']:
            return '/usr/bin/' + cmd
        return None

    import shutil
    monkeypatch.setattr(shutil, 'which', mock_which)


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_openfoam: mark test as requiring OpenFOAM installation"
    )


# ============================================================================
# Helper Functions for Integration Tests
# ============================================================================

def copy_sample_stl_files(dest_dir: Path):
    """Copy sample STL files to destination directory."""
    sample_stl_dir = PROJECT_ROOT / "tests" / "fixtures" / "sample_stl_files"
    tri_surface = dest_dir / "constant" / "triSurface"
    tri_surface.mkdir(parents=True, exist_ok=True)

    for stl_file in ["inlet.stl", "outlet1.stl", "outlet2.stl", "wall.stl"]:
        src = sample_stl_dir / stl_file
        if src.exists():
            shutil.copy(src, tri_surface / stl_file)


def copy_sample_flow_csv(dest_dir: Path, csv_name: str = "flow.csv"):
    """Copy sample flow CSV to destination directory."""
    sample_csv = PROJECT_ROOT / "tests" / "fixtures" / "sample_bc_data" / "flow.csv"
    dest_file = dest_dir / csv_name
    dest_file.parent.mkdir(parents=True, exist_ok=True)

    if sample_csv.exists():
        shutil.copy(sample_csv, dest_file)


@pytest.fixture
def case_dir_with_geometry(temp_case_dir):
    """Temporary case directory with realistic geometry files."""
    copy_sample_stl_files(temp_case_dir)
    copy_sample_flow_csv(temp_case_dir)
    return temp_case_dir
