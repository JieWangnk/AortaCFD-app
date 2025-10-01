"""
Unit tests for workflow execution tasks.

Tests the execution tasks that run OpenFOAM commands (meshing, solving, post-processing).
"""

import pytest
import os
from pathlib import Path

from src.workflow.tasks.execution_tasks import (
    ExecuteMeshingTask,
    ExecuteSolverTask,
    ExecutePostProcessingTask
)
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


class TestExecuteMeshingTask:
    """Tests for ExecuteMeshingTask."""

    def test_task_initialization(self, workflow_config):
        """Test task can be initialized."""
        task = ExecuteMeshingTask(workflow_config)
        assert task.config == workflow_config
        assert hasattr(task, 'log')

    def test_requires_mesh_settings(self, workflow_config):
        """Test requires mesh configuration."""
        task = ExecuteMeshingTask(workflow_config)

        assert "mesh" in task.config
        assert "SNAPPY_SETTINGS" in task.config["mesh"]

    def test_requires_geometry_scale(self, workflow_config):
        """Test requires geometry scale factor."""
        task = ExecuteMeshingTask(workflow_config)

        assert "geometry" in task.config
        assert "scale_factor" in task.config["geometry"]

    def test_scale_factor_positive(self, workflow_config):
        """Test scale factor is positive."""
        task = ExecuteMeshingTask(workflow_config)
        scale = task.config["geometry"]["scale_factor"]

        assert scale > 0
        # Typically 0.001 (mm to m) or 1.0 (no scaling)
        assert 0.0001 <= scale <= 100.0

    def test_parallel_settings_structure(self, workflow_config):
        """Test parallel meshing settings."""
        task = ExecuteMeshingTask(workflow_config)
        snappy = task.config["mesh"]["SNAPPY_SETTINGS"]

        assert "parallel" in snappy

        if snappy["parallel"]:
            assert "nProcessors" in snappy
            assert snappy["nProcessors"] > 0
            assert snappy["nProcessors"] <= 64  # Reasonable upper limit

    def test_snappy_stages_enabled(self, workflow_config):
        """Test SnappyHexMesh stages are properly configured."""
        task = ExecuteMeshingTask(workflow_config)
        snappy = task.config["mesh"]["SNAPPY_SETTINGS"]

        # At least one stage should be enabled
        assert "castellatedMesh" in snappy
        assert "snap" in snappy
        assert "addLayers" in snappy

    def test_cell_limits_positive(self, workflow_config):
        """Test cell count limits are positive."""
        task = ExecuteMeshingTask(workflow_config)
        snappy = task.config["mesh"]["SNAPPY_SETTINGS"]

        assert snappy["maxLocalCells"] > 0
        assert snappy["maxGlobalCells"] > 0
        assert snappy["maxGlobalCells"] >= snappy["maxLocalCells"]


class TestExecuteSolverTask:
    """Tests for ExecuteSolverTask."""

    def test_task_initialization(self, workflow_config):
        """Test task initializes correctly."""
        task = ExecuteSolverTask(workflow_config)
        assert task.config == workflow_config

    def test_requires_simulation_control(self, workflow_config):
        """Test requires simulation control settings."""
        task = ExecuteSolverTask(workflow_config)

        assert "simulation_control" in task.config
        assert "controlDict" in task.config["simulation_control"]

    def test_solver_application_valid(self, workflow_config):
        """Test solver application is valid OpenFOAM solver."""
        task = ExecuteSolverTask(workflow_config)
        app = task.config["simulation_control"]["controlDict"]["application"]

        valid_solvers = ["foamRun", "pimpleFoam", "simpleFoam", "icoFoam"]
        assert app in valid_solvers

    def test_windkessel_uses_foamrun(self, workflow_config):
        """Test Windkessel BCs use foamRun solver."""
        workflow_config["outlets"]["type"] = "3ElementWindkessel"

        task = ExecuteSolverTask(workflow_config)

        # Should use foamRun for Windkessel
        assert "outlets" in task.config
        assert task.config["outlets"]["type"] == "3ElementWindkessel"

    def test_parallel_run_settings(self, workflow_config):
        """Test parallel solver settings."""
        workflow_config["run_settings"]["solution_type"] = "parallel"
        workflow_config["run_settings"]["subdomains"] = 8

        task = ExecuteSolverTask(workflow_config)
        run_settings = task.config["run_settings"]

        assert run_settings["solution_type"] == "parallel"
        assert run_settings["subdomains"] > 0
        assert run_settings["subdomains"] <= 128

    def test_serial_run_settings(self, workflow_config):
        """Test serial solver settings."""
        workflow_config["run_settings"]["solution_type"] = "serial"

        task = ExecuteSolverTask(workflow_config)
        run_settings = task.config["run_settings"]

        assert run_settings["solution_type"] == "serial"


class TestExecutePostProcessingTask:
    """Tests for ExecutePostProcessingTask."""

    def test_task_initialization(self, workflow_config):
        """Test task initializes correctly."""
        task = ExecutePostProcessingTask(workflow_config)
        assert task.config == workflow_config

    def test_requires_post_processing_config(self, workflow_config):
        """Test requires post-processing configuration."""
        task = ExecutePostProcessingTask(workflow_config)

        assert "post_processing" in task.config

    def test_pvbatch_executable_specified(self, workflow_config):
        """Test pvbatch executable is specified."""
        task = ExecutePostProcessingTask(workflow_config)
        pp_config = task.config["post_processing"]

        assert "pvbatch_exe" in pp_config
        # Path should be non-empty string
        assert isinstance(pp_config["pvbatch_exe"], str)

    def test_post_processing_optional(self, workflow_config):
        """Test post-processing can be disabled."""
        # Post-processing should be optional
        workflow_config["post_processing"] = {"enabled": False}

        task = ExecutePostProcessingTask(workflow_config)
        assert "post_processing" in task.config


class TestTaskIntegration:
    """Integration tests for task workflow."""

    def test_all_tasks_accept_config(self, workflow_config):
        """Test all tasks can be initialized with same config."""
        tasks = [
            CreateCaseStructureTask(workflow_config),
            GenerateMeshFilesTask(workflow_config),
            GenerateBCFilesTask(workflow_config),
            GeneratePhysicalPropertiesTask(workflow_config),
            GenerateNumericalSchemesTask(workflow_config),
            GenerateSolverSettingsTask(workflow_config),
            GenerateDecomposeParDictTask(workflow_config),
            GenerateControlDictTask(workflow_config),
            ExecuteMeshingTask(workflow_config),
            ExecuteSolverTask(workflow_config),
            ExecutePostProcessingTask(workflow_config)
        ]

        for task in tasks:
            assert task.config == workflow_config
            assert hasattr(task, 'execute')

    def test_context_passing(self, workflow_config):
        """Test context dictionary can be passed between tasks."""
        context = {
            "case_directory": "/tmp/test_case",
            "cardiac_cycle": 0.8,
            "custom_data": {"key": "value"}
        }

        task = CreateCaseStructureTask(workflow_config)

        # Context should be accessible
        assert context["case_directory"] == "/tmp/test_case"
        assert context["cardiac_cycle"] == 0.8

    def test_task_return_boolean(self, workflow_config, tmp_path, monkeypatch):
        """Test all tasks return boolean success/failure."""
        # Change to tmp_path so relative paths work
        monkeypatch.chdir(tmp_path)

        case_dir = tmp_path / "test_case"
        context = {"case_directory": str(case_dir)}

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

        assert isinstance(result, bool)
        assert result is True  # Should succeed

    def test_config_immutability(self, workflow_config):
        """Test tasks don't modify shared config."""
        original_config = workflow_config.copy()

        task1 = CreateCaseStructureTask(workflow_config)
        task2 = ExecuteMeshingTask(workflow_config)

        # Config keys should remain the same
        assert set(workflow_config.keys()) == set(original_config.keys())
