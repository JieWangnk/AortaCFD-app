"""
Global pytest configuration and fixtures for AortaCFD testing.
"""
import os
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Generator

# Test data directory
TEST_DATA_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """Sample configuration for testing."""
    return {
        "geometry": {
            "case_name": "test_case",
            "refinement_level": "coarse",
            "wall_keywords_ordered": "wall_aorta",
            "inlet_keywords_ordered": "inlet",
            "outlet_keywords_ordered": ["outlet1", "outlet2"],
            "scale_factor": 1.0
        },
        "mesh": {
            "base_cell_size": 0.001,
            "refinement_surfaces": {
                "wall_aorta": {"level": "(1 2)"},
                "inlet": {"level": "(1 2)"},
                "outlet1": {"level": "(1 2)"},
                "outlet2": {"level": "(1 2)"}
            },
            "SNAPPY_SETTINGS": {
                "parallel": True,
                "nProcessors": 4
            }
        },
        "physics": {
            "density": 1060.0,
            "dynamic_viscosity": 0.0035,
            "kinematic_viscosity": 3.3e-06
        },
        "solver": {
            "application": "pimpleFoam",
            "start_time": 0.0,
            "end_time": 1.0,
            "delta_t": 0.001,
            "write_interval": 0.1
        },
        "inlet": {
            "csv_file": "inletFlowRate.csv",
            "flow_rate_profile": "laminar"
        },
        "boundary_conditions": {
            "inlet": {
                "type": "flowRateInletVelocity",
                "value": "uniform (0 0 0)",
                "flowRate": "table",
                "flowRateProfile": "laminar"
            },
            "outlet1": {
                "type": "fixedValue",
                "value": "uniform 0"
            },
            "outlet2": {
                "type": "fixedValue", 
                "value": "uniform 0"
            },
            "wall_aorta": {
                "type": "noSlip"
            }
        },
        "numerical": {
            "ddtSchemes": {
                "default": "Euler"
            },
            "gradSchemes": {
                "default": "Gauss linear"
            },
            "divSchemes": {
                "default": "none",
                "div(phi,U)": "Gauss linearUpwind grad(U)",
                "div((nuEff*dev2(T(grad(U)))))": "Gauss linear"
            },
            "laplacianSchemes": {
                "default": "Gauss linear corrected"
            },
            "interpolationSchemes": {
                "default": "linear"
            },
            "snGradSchemes": {
                "default": "corrected"
            }
        },
        "openfoam_version": "8"
    }


@pytest.fixture
def sample_case_directory(temp_dir: Path) -> Path:
    """Create a sample case directory structure."""
    case_dir = temp_dir / "data" / "CAD" / "test_case"
    case_dir.mkdir(parents=True)
    
    # Create sample STL files (empty for testing)
    stl_files = ["inlet.stl", "outlet1.stl", "outlet2.stl", "wall_aorta.stl"]
    for stl_file in stl_files:
        (case_dir / stl_file).write_text("# Empty STL file for testing")
    
    # Create sample CSV file
    csv_content = """Time,FlowRate
0.0,0.0
0.1,1.0
0.2,0.5
0.3,0.0"""
    (case_dir / "inletFlowRate.csv").write_text(csv_content)
    
    # Create sample boundary conditions file
    bc_content = """{
    "boundary_conditions": {
        "inlet": {
            "type": "flowRateInletVelocity",
            "flowRate": "table"
        },
        "outlet1": {
            "type": "fixedValue",
            "value": "uniform 0"
        },
        "outlet2": {
            "type": "fixedValue",
            "value": "uniform 0"
        }
    }
}"""
    (case_dir / "boundary_conditions.json").write_text(bc_content)
    
    return case_dir


@pytest.fixture
def mock_openfoam():
    """Mock OpenFOAM subprocess calls."""
    with patch('subprocess.run') as mock_run, \
         patch('subprocess.Popen') as mock_popen, \
         patch('subprocess.check_output') as mock_check_output:
        
        # Configure successful return values
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        mock_check_output.return_value = "OpenFOAM output"
        
        # Configure Popen for interactive processes
        mock_process = Mock()
        mock_process.communicate.return_value = ("output", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        yield {
            'run': mock_run,
            'popen': mock_popen,
            'check_output': mock_check_output
        }


@pytest.fixture
def mock_paraview():
    """Mock ParaView subprocess calls."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout="ParaView output", stderr="")
        yield mock_run


@pytest.fixture
def mock_logger():
    """Mock logger for testing."""
    with patch('src.aortacfd_lib.utils.logger.Logger') as mock_logger_class:
        mock_logger_instance = Mock()
        mock_logger_class.return_value.get_logger.return_value = mock_logger_instance
        yield mock_logger_instance


@pytest.fixture
def openfoam_case_structure(temp_dir: Path) -> Path:
    """Create a mock OpenFOAM case structure."""
    case_dir = temp_dir / "output" / "OPENFOAM" / "test_case_coarse"
    case_dir.mkdir(parents=True)
    
    # Create basic OpenFOAM directories
    directories = ["0", "constant", "system"]
    for directory in directories:
        (case_dir / directory).mkdir()
    
    # Create some basic files
    (case_dir / "system" / "controlDict").write_text("// Empty controlDict")
    (case_dir / "system" / "fvSchemes").write_text("// Empty fvSchemes")
    (case_dir / "system" / "fvSolution").write_text("// Empty fvSolution")
    (case_dir / "constant" / "transportProperties").write_text("// Empty transportProperties")
    
    return case_dir


@pytest.fixture
def sample_stl_content() -> str:
    """Sample STL file content for testing."""
    return """solid test_geometry
  facet normal 0.0 0.0 1.0
    outer loop
      vertex 0.0 0.0 0.0
      vertex 1.0 0.0 0.0
      vertex 0.0 1.0 0.0
    endloop
  endfacet
endsolid test_geometry"""


@pytest.fixture
def sample_flow_data() -> str:
    """Sample flow rate CSV data."""
    return """Time,FlowRate
0.0,0.0
0.1,100.0
0.2,80.0
0.3,60.0
0.4,40.0
0.5,20.0
0.6,0.0
0.7,0.0
0.8,0.0
0.9,0.0
1.0,0.0"""


# Environment setup
@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("FOAM_RUN", "/tmp/test_foam_run")
    monkeypatch.setenv("FOAM_USER_APPBIN", "/tmp/test_foam_appbin")
    monkeypatch.setenv("WM_PROJECT_VERSION", "8")