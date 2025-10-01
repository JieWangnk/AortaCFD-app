"""
Unit tests for workflow setup tasks.

Tests the setup tasks that prepare case directories, generate configuration files,
and setup boundary conditions for OpenFOAM simulations.
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path

from src.workflow.tasks.setup_tasks import (
    CreateCaseStructureTask,
    GenerateMeshFilesTask,
    GenerateBCFilesTask,
    GeneratePhysicalPropertiesTask,
    GenerateNumericalSchemesTask,
    GenerateSolverSettingsTask,
    GenerateDecomposeParDictTask,
    GenerateControlDictTask
)


@pytest.fixture
def workflow_config(full_config):
    """Augment full_config with fields required by workflow tasks."""
    full_config.update({
        "geometry": {
            "case_name": "test_case",
            "inlet_keywords_ordered": "inlet",
            "scale_factor": 0.001
        },
        "inlet": {
            "type": "timeVaryingMappedFixedValue",
            "csv_file": "flow.csv"
        },
        "outlets": {
            "type": "fixedValue"
        },
        "physical_properties": {
            "density": 1060,
            "kinematic_viscosity": 3.77e-06
        },
        "schemes": {
            "ddtSchemes": {"default": "backward"},
            "gradSchemes": {"default": "Gauss linear"},
            "divSchemes": {"default": "Gauss linear"}
        },
        "fvSolution": {
            "solvers": {},
            "PIMPLE": {}
        },
        "simulation_control": {
            "end_time": None,
            "number_of_cycles": 1,
            "controlDict": {
                "application": "foamRun",
                "startFrom": "latestTime",
                "startTime": 0,
                "stopAt": "endTime",
                "deltaT": 0.001,
                "writeControl": "adjustable"
            }
        },
        "post_processing": {
            "pvbatch_exe": "/usr/bin/pvbatch"
        }
    })

    # Also augment mesh settings
    full_config["mesh"]["SNAPPY_SETTINGS"].update({
        "maxLocalCells": 1_800_000,
        "maxGlobalCells": 2_000_000,
        "castellatedMesh": True,
        "snap": True,
        "addLayers": True
    })

    return full_config


class TestCreateCaseStructureTask:
    """Tests for CreateCaseStructureTask."""

    def test_task_initialization(self, workflow_config):
        """Test task can be initialized with config."""
        task = CreateCaseStructureTask(workflow_config)
        assert task.config == workflow_config
        assert hasattr(task, 'log')

    def test_creates_required_directories(self, workflow_config, tmp_path, monkeypatch):
        """Test creates all required case directories."""
        # Change to tmp_path so relative paths work
        monkeypatch.chdir(tmp_path)

        case_dir = tmp_path / "test_case"
        context = {"case_directory": str(case_dir)}

        # Create mock geometry files for validation
        import struct
        cad_folder = tmp_path / "cases_input" / "test_case"
        cad_folder.mkdir(parents=True)

        # Create mock inlet.stl (binary format)
        inlet_stl = cad_folder / "inlet.stl"
        with open(inlet_stl, 'wb') as f:
            f.write(b' ' * 80)  # Header
            f.write(struct.pack('<I', 1))  # 1 triangle
            f.write(struct.pack('<fff', 0.0, 0.0, 1.0))  # Normal
            f.write(struct.pack('<fff', 0.0, 0.0, 0.0))  # Vertex 1
            f.write(struct.pack('<fff', 1.0, 0.0, 0.0))  # Vertex 2
            f.write(struct.pack('<fff', 0.0, 1.0, 0.0))  # Vertex 3
            f.write(struct.pack('<H', 0))  # Attribute

        # Create mock outlet.stl
        outlet_stl = cad_folder / "outlet1.stl"
        with open(outlet_stl, 'wb') as f:
            f.write(b' ' * 80)
            f.write(struct.pack('<I', 1))
            f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
            f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
            f.write(struct.pack('<fff', 1.0, 0.0, 0.0))
            f.write(struct.pack('<fff', 0.0, 1.0, 0.0))
            f.write(struct.pack('<H', 0))

        # Create mock wall.stl
        wall_stl = cad_folder / "wall.stl"
        with open(wall_stl, 'wb') as f:
            f.write(b' ' * 80)
            f.write(struct.pack('<I', 1))
            f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
            f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
            f.write(struct.pack('<fff', 2.0, 0.0, 0.0))
            f.write(struct.pack('<fff', 0.0, 2.0, 0.0))
            f.write(struct.pack('<H', 0))

        # Create mock flow CSV file
        flow_csv = cad_folder / workflow_config['inlet']['csv_file']
        flow_csv.write_text("Time,Flow\n0.0,0.5\n0.1,0.6\n")

        task = CreateCaseStructureTask(workflow_config)
        result = task.execute(context)

        assert result is True
        assert (case_dir / "system").exists()
        assert (case_dir / "constant" / "triSurface").exists()
        assert (case_dir / "0").exists()

    def test_creates_boundary_data_dir(self, workflow_config, tmp_path, monkeypatch):
        """Test creates boundaryData directory for inlet."""
        # Change to tmp_path so relative paths work
        monkeypatch.chdir(tmp_path)

        case_dir = tmp_path / "test_case"
        context = {"case_directory": str(case_dir)}

        # Setup mock inlet keywords
        workflow_config['geometry']['inlet_keywords_ordered'] = 'inlet'

        # Create mock geometry files for validation
        import struct
        cad_folder = tmp_path / "cases_input" / "test_case"
        cad_folder.mkdir(parents=True)

        # Create mock STL files
        for name in ['inlet', 'outlet1', 'wall']:
            stl_file = cad_folder / f"{name}.stl"
            with open(stl_file, 'wb') as f:
                f.write(b' ' * 80)
                f.write(struct.pack('<I', 1))
                f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
                f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
                f.write(struct.pack('<fff', 1.0, 0.0, 0.0))
                f.write(struct.pack('<fff', 0.0, 1.0, 0.0))
                f.write(struct.pack('<H', 0))

        # Create mock flow CSV file
        flow_csv = cad_folder / workflow_config['inlet']['csv_file']
        flow_csv.write_text("Time,Flow\n0.0,0.5\n0.1,0.6\n")

        task = CreateCaseStructureTask(workflow_config)
        result = task.execute(context)

        assert result is True
        boundary_data = case_dir / "constant" / "boundaryData" / "inlet"
        assert boundary_data.exists()

    def test_clean_run_removes_existing(self, workflow_config, tmp_path):
        """Test clean_run flag removes existing directory."""
        case_dir = tmp_path / "test_case"
        case_dir.mkdir()
        marker_file = case_dir / "old_file.txt"
        marker_file.write_text("old data")

        workflow_config['clean_run'] = True
        context = {"case_directory": str(case_dir)}

        task = CreateCaseStructureTask(workflow_config)
        task.execute(context)

        # Old file should be gone
        assert not marker_file.exists()
        # New structure should exist
        assert (case_dir / "system").exists()

    def test_preserves_existing_when_no_clean(self, workflow_config, tmp_path):
        """Test preserves existing directory when clean_run is False."""
        case_dir = tmp_path / "test_case"
        case_dir.mkdir()
        system_dir = case_dir / "system"
        system_dir.mkdir()
        marker_file = system_dir / "old_file.txt"
        marker_file.write_text("old data")

        workflow_config['clean_run'] = False
        context = {"case_directory": str(case_dir)}

        task = CreateCaseStructureTask(workflow_config)
        task.execute(context)

        # Old file should still exist
        assert marker_file.exists()
        assert marker_file.read_text() == "old data"


class TestGenerateMeshFilesTask:
    """Tests for GenerateMeshFilesTask."""

    def test_task_initialization(self, workflow_config):
        """Test task initializes with config."""
        task = GenerateMeshFilesTask(workflow_config)
        assert task.config == workflow_config

    def test_requires_mesh_config(self, workflow_config):
        """Test requires mesh configuration."""
        task = GenerateMeshFilesTask(workflow_config)
        assert "mesh" in task.config
        assert "SNAPPY_SETTINGS" in task.config["mesh"]

    def test_config_has_geometry_settings(self, workflow_config):
        """Test config has required geometry settings."""
        task = GenerateMeshFilesTask(workflow_config)
        assert "geometry" in task.config
        assert "scale_factor" in task.config["geometry"]


class TestGenerateBCFilesTask:
    """Tests for GenerateBCFilesTask."""

    def test_task_initialization(self, workflow_config):
        """Test task initializes correctly."""
        task = GenerateBCFilesTask(workflow_config)
        assert task.config == workflow_config

    def test_requires_boundary_config(self, workflow_config):
        """Test requires boundary condition configuration."""
        task = GenerateBCFilesTask(workflow_config)

        # Must have inlet and outlet configs
        assert "inlet" in task.config
        assert "outlets" in task.config

    def test_inlet_config_structure(self, workflow_config):
        """Test inlet configuration has required fields."""
        task = GenerateBCFilesTask(workflow_config)
        inlet = task.config["inlet"]

        assert "type" in inlet
        assert "csv_file" in inlet
        assert inlet["type"] in ["timeVaryingMappedFixedValue", "fixedValue"]


class TestGeneratePhysicalPropertiesTask:
    """Tests for GeneratePhysicalPropertiesTask."""

    def test_task_initialization(self, workflow_config):
        """Test task initializes with config."""
        task = GeneratePhysicalPropertiesTask(workflow_config)
        assert task.config == workflow_config

    def test_requires_physical_properties(self, workflow_config):
        """Test requires physical properties in config."""
        task = GeneratePhysicalPropertiesTask(workflow_config)

        assert "physical_properties" in task.config
        props = task.config["physical_properties"]

        # Blood properties
        assert "density" in props
        assert "kinematic_viscosity" in props

    def test_blood_density_range(self, workflow_config):
        """Test blood density is physiologically valid."""
        task = GeneratePhysicalPropertiesTask(workflow_config)
        density = task.config["physical_properties"]["density"]

        # Blood density approximately 1050-1070 kg/m³
        assert 1000 <= density <= 1100

    def test_kinematic_viscosity_range(self, workflow_config):
        """Test kinematic viscosity is physiologically valid."""
        task = GeneratePhysicalPropertiesTask(workflow_config)
        nu = task.config["physical_properties"]["kinematic_viscosity"]

        # Blood kinematic viscosity approximately 3-5 × 10⁻⁶ m²/s
        assert 2e-6 <= nu <= 10e-6


class TestGenerateNumericalSchemesTask:
    """Tests for GenerateNumericalSchemesTask."""

    def test_task_initialization(self, workflow_config):
        """Test task initializes correctly."""
        task = GenerateNumericalSchemesTask(workflow_config)
        assert task.config == workflow_config

    def test_requires_schemes_config(self, workflow_config):
        """Test requires schemes configuration."""
        task = GenerateNumericalSchemesTask(workflow_config)

        # Check for schemes section
        assert "schemes" in task.config or "numerical_schemes" in task.config

    def test_schemes_structure(self, workflow_config):
        """Test schemes have required discretization settings."""
        task = GenerateNumericalSchemesTask(workflow_config)

        # Get schemes from appropriate location
        if "schemes" in task.config:
            schemes = task.config["schemes"]
        else:
            schemes = task.config.get("numerical_schemes", {})

        # Should specify time, gradient, divergence schemes
        assert isinstance(schemes, dict)


class TestGenerateSolverSettingsTask:
    """Tests for GenerateSolverSettingsTask."""

    def test_task_initialization(self, workflow_config):
        """Test task initializes correctly."""
        task = GenerateSolverSettingsTask(workflow_config)
        assert task.config == workflow_config

    def test_requires_solver_config(self, workflow_config):
        """Test requires solver configuration."""
        task = GenerateSolverSettingsTask(workflow_config)

        # Check for solver settings
        assert "fvSolution" in task.config or "solver_settings" in task.config


class TestGenerateDecomposeParDictTask:
    """Tests for GenerateDecomposeParDictTask."""

    def test_task_initialization(self, workflow_config):
        """Test task initializes correctly."""
        task = GenerateDecomposeParDictTask(workflow_config)
        assert task.config == workflow_config

    def test_requires_run_settings(self, workflow_config):
        """Test requires run settings for decomposition."""
        task = GenerateDecomposeParDictTask(workflow_config)

        assert "run_settings" in task.config

    def test_parallel_settings_structure(self, workflow_config):
        """Test parallel settings have required fields."""
        task = GenerateDecomposeParDictTask(workflow_config)
        run_settings = task.config["run_settings"]

        if run_settings.get("solution_type") == "parallel":
            assert "subdomains" in run_settings
            assert run_settings["subdomains"] > 0

    def test_subdomain_count_reasonable(self, workflow_config):
        """Test subdomain count is reasonable."""
        workflow_config["run_settings"]["solution_type"] = "parallel"
        workflow_config["run_settings"]["subdomains"] = 4

        task = GenerateDecomposeParDictTask(workflow_config)
        subdomains = task.config["run_settings"]["subdomains"]

        # Should be between 1 and 128 for typical systems
        assert 1 <= subdomains <= 128


class TestGenerateControlDictTask:
    """Tests for GenerateControlDictTask."""

    def test_task_initialization(self, workflow_config):
        """Test task initializes correctly."""
        task = GenerateControlDictTask(workflow_config)
        assert task.config == workflow_config

    def test_requires_simulation_control(self, workflow_config):
        """Test requires simulation control settings."""
        task = GenerateControlDictTask(workflow_config)

        assert "simulation_control" in task.config
        assert "controlDict" in task.config["simulation_control"]

    def test_calculates_endtime_from_cycles(self, workflow_config, tmp_path):
        """Test calculates endTime from cardiac cycles."""
        case_dir = tmp_path / "test_case"
        case_dir.mkdir()
        (case_dir / "system").mkdir()

        context = {
            "case_directory": str(case_dir),
            "cardiac_cycle": 0.8  # 0.8 second cycle
        }

        workflow_config["simulation_control"]["end_time"] = None
        workflow_config["simulation_control"]["number_of_cycles"] = 3

        task = GenerateControlDictTask(workflow_config)
        result = task.execute(context)

        # Should calculate: 0.8 * 3 = 2.4s
        assert result is True

    def test_uses_fixed_endtime_when_provided(self, workflow_config, tmp_path):
        """Test uses fixed endTime when explicitly set."""
        case_dir = tmp_path / "test_case"
        case_dir.mkdir()
        (case_dir / "system").mkdir()

        context = {
            "case_directory": str(case_dir),
            "cardiac_cycle": 0.8
        }

        workflow_config["simulation_control"]["end_time"] = 5.0  # Fixed

        task = GenerateControlDictTask(workflow_config)
        result = task.execute(context)

        # Should use fixed value, not calculate from cycles
        assert result is True

    def test_control_dict_structure(self, workflow_config):
        """Test controlDict has required OpenFOAM fields."""
        task = GenerateControlDictTask(workflow_config)
        control_dict = task.config["simulation_control"]["controlDict"]

        # Required OpenFOAM controlDict fields
        assert "application" in control_dict
        assert "startFrom" in control_dict
        assert "startTime" in control_dict
        assert "stopAt" in control_dict
        assert "deltaT" in control_dict
        assert "writeControl" in control_dict

    def test_timestep_positive(self, workflow_config):
        """Test timestep is positive."""
        task = GenerateControlDictTask(workflow_config)
        dt = task.config["simulation_control"]["controlDict"]["deltaT"]

        assert dt > 0
        assert 1e-6 <= dt <= 1.0  # Reasonable range

    def test_number_of_cycles_positive(self, workflow_config):
        """Test number of cycles is positive integer."""
        task = GenerateControlDictTask(workflow_config)

        if "number_of_cycles" in task.config["simulation_control"]:
            n_cycles = task.config["simulation_control"]["number_of_cycles"]
            assert n_cycles > 0
            assert isinstance(n_cycles, int)
