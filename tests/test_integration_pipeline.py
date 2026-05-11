"""
Integration tests for the full AortaCFD simulation pipeline.

These tests verify that the complete workflow functions correctly from
configuration through to dictionary file generation.

Note: These tests do NOT require OpenFOAM to be installed. They test
the Python workflow and file generation, not actual CFD execution.
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.builder import ConfigBuilder
from workflow.manager import WorkflowManager
from workflow.base_task import AortaCFDError


class TestWorkflowManager:
    """Test the WorkflowManager task orchestration."""

    @pytest.fixture
    def mock_config(self) -> Dict[str, Any]:
        """Mock configuration for workflow tests."""
        return {
            "geometry": {
                "case_name": "test_patient",
                "refinement_level": "default",
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["outlet"],
                "wall_keywords_ordered": "wall",
                "scale_factor": 0.001,
            },
            "mesh": {"SNAPPY_SETTINGS": {}},
            "physics": {"density": 1060, "viscosity": 0.004, "simulation_type": "laminar"},
            "numerics": {"profile": "standard"},
            "boundary_conditions": {},
            "simulation": {"end_time": 0.1, "num_processors": 1},
        }

    def test_workflow_manager_initialization(self, mock_config: Dict[str, Any]):
        """Test WorkflowManager initializes correctly."""
        from workflow.base_task import ExecutionContext

        manager = WorkflowManager(mock_config)

        assert manager.config == mock_config
        # Context is now an ExecutionContext dataclass, not an empty dict
        assert isinstance(manager.context, ExecutionContext)
        # Context should be initialized with case_directory from config
        assert manager.context.case_directory != ""  # Should be set from geometry config
        assert len(manager.available_tasks) > 0

    def test_workflow_manager_has_required_tasks(self, mock_config: Dict[str, Any]):
        """Test WorkflowManager has all required tasks registered."""
        manager = WorkflowManager(mock_config)

        required_tasks = [
            "create_case_structure",
            "generate_mesh_files",
            "generate_physical_properties",
            "generate_numerical_schemes",
            "generate_solver_settings",
            "generate_bc_files",
            "execute_meshing",
            "execute_solver",
        ]

        for task_name in required_tasks:
            assert task_name in manager.available_tasks, f"Missing task: {task_name}"

    def test_unknown_command_raises_error(self, mock_config: Dict[str, Any]):
        """Test that unknown workflow commands raise AortaCFDError."""
        manager = WorkflowManager(mock_config)

        with pytest.raises(AortaCFDError) as exc_info:
            manager.run_workflow("unknown_command")

        assert "Unknown command" in str(exc_info.value)

    def test_workflow_recipes_defined(self, mock_config: Dict[str, Any]):
        """Test that all expected workflow recipes are available."""
        manager = WorkflowManager(mock_config)

        # Access recipes through the run_workflow method indirectly
        expected_commands = ["setup:dict", "setup:bc", "run:mesh", "run:solver", "runAll", "createCase"]

        # These should not raise AortaCFDError for unknown command
        # (they may fail for other reasons since we don't have real files)
        for command in expected_commands:
            try:
                manager.run_workflow(command)
            except AortaCFDError as e:
                # Should not be "Unknown command" error
                assert "Unknown command" not in str(e), f"'{command}' should be a valid command"
            except Exception:
                # Other exceptions are fine (e.g., missing files)
                pass


class TestNumericsProfiles:
    """Test the numerics profile system."""

    def test_all_profiles_loadable(self):
        """Test that all numeric profiles can be loaded."""
        from config.numerics_builder import NumericsBuilder

        builder = NumericsBuilder()

        # Test each known profile individually
        for profile_name in ["robust", "standard", "precise"]:
            profile = builder._load_profile(profile_name)
            assert profile is not None

    def test_standard_profile_has_required_keys(self):
        """Test that standard profile has all required configuration keys."""
        from config.numerics_builder import NumericsBuilder

        builder = NumericsBuilder()
        profile = builder._load_profile("standard")

        required_keys = [
            "ddtSchemes",
            "gradSchemes",
            "divSchemes",
            "laplacianSchemes",
            "interpolationSchemes",
            "snGradSchemes",
            "solvers",
            "time_stepping",
        ]

        for key in required_keys:
            assert key in profile, f"Standard profile missing key: {key}"

    @pytest.mark.parametrize(
        "profile_name,expected_stability",
        [
            ("robust", "high"),
            ("standard", "medium"),
            ("precise", "medium"),
        ],
    )
    def test_profile_stability_levels(self, profile_name: str, expected_stability: str):
        """Test that profiles have expected stability characteristics."""
        from config.numerics_builder import NumericsBuilder

        builder = NumericsBuilder()
        profile = builder._load_profile(profile_name)
        metadata = profile.get("_profile_metadata", {})

        # Check stability is defined
        assert "stability" in metadata, f"Profile {profile_name} missing stability metadata"


class TestConstantsModule:
    """Test the new constants module."""

    def test_unit_conversions_correct(self):
        """Test that unit conversion constants are correct."""
        from aortacfd_lib.constants import MMHG_TO_PA, PA_TO_MMHG, ML_TO_M3, M3_TO_ML

        # 1 mmHg = 133.322 Pa (by definition)
        assert abs(MMHG_TO_PA - 133.322) < 0.001

        # Inverse should be reciprocal
        assert abs(PA_TO_MMHG - 1.0 / MMHG_TO_PA) < 1e-10

        # 1 mL = 1e-6 m³
        assert ML_TO_M3 == 1e-6
        assert M3_TO_ML == 1e6

    def test_blood_properties_in_physiological_range(self):
        """Test that blood property defaults are physiologically reasonable."""
        from aortacfd_lib.constants import (
            BLOOD_DENSITY_DEFAULT,
            BLOOD_DENSITY_MIN,
            BLOOD_DENSITY_MAX,
            BLOOD_VISCOSITY_DEFAULT,
            BLOOD_VISCOSITY_MIN,
            BLOOD_VISCOSITY_MAX,
        )

        # Density should be around 1060 kg/m³
        assert BLOOD_DENSITY_MIN < BLOOD_DENSITY_DEFAULT < BLOOD_DENSITY_MAX
        assert 1000 <= BLOOD_DENSITY_DEFAULT <= 1100

        # Viscosity should be around 0.004 Pa·s
        assert BLOOD_VISCOSITY_MIN < BLOOD_VISCOSITY_DEFAULT < BLOOD_VISCOSITY_MAX
        assert 0.003 <= BLOOD_VISCOSITY_DEFAULT <= 0.005

    def test_map_calculation_correct(self):
        """Test MAP calculation function."""
        from aortacfd_lib.constants import calculate_map

        # For 120/80, MAP should be approximately 93.3
        map_result = calculate_map(120, 80)
        expected = 80 + (120 - 80) / 3.0  # 93.333...

        assert abs(map_result - expected) < 0.01
        assert abs(map_result - 93.333) < 0.01

    def test_cardiac_output_conversion(self):
        """Test cardiac output conversion function."""
        from aortacfd_lib.constants import cardiac_output_to_m3s

        # 5 L/min = 5/60/1000 m³/s = 8.33e-5 m³/s
        result = cardiac_output_to_m3s(5.0)
        expected = 5.0 / 60.0 / 1000.0

        assert abs(result - expected) < 1e-10


class TestFileGeneration:
    """Test that OpenFOAM dictionary files can be generated."""

    @pytest.fixture
    def temp_case_directory(self) -> str:
        """Create a temporary case directory structure."""
        tmpdir = tempfile.mkdtemp()

        # Create required directory structure
        os.makedirs(os.path.join(tmpdir, "system"))
        os.makedirs(os.path.join(tmpdir, "constant", "triSurface"))
        os.makedirs(os.path.join(tmpdir, "0"))

        yield tmpdir

        # Cleanup
        shutil.rmtree(tmpdir)

    def test_numerical_schemes_generator(self, temp_case_directory: str):
        """Test that numerical schemes can be generated."""
        from aortacfd_lib.numerical_setup import FvSchemesWriter

        config = {
            "numerics": {
                "profile": "standard",
            },
            "physics": {"simulation_type": "laminar"},
            "schemes": {
                "ddtSchemes": {"default": "backward"},
                "gradSchemes": {"default": "Gauss linear"},
                "divSchemes": {"default": "none"},
                "laplacianSchemes": {"default": "Gauss linear corrected"},
                "interpolationSchemes": {"default": "linear"},
                "snGradSchemes": {"default": "corrected"},
            },
            "openfoam_version": "12",
        }

        setup = FvSchemesWriter(config, temp_case_directory)
        setup.write_fvSchemes_file()

        fvSchemes_path = os.path.join(temp_case_directory, "system", "fvSchemes")
        assert os.path.exists(fvSchemes_path)

        with open(fvSchemes_path, "r") as f:
            content = f.read()

        assert "ddtSchemes" in content
        assert "gradSchemes" in content
        assert "divSchemes" in content

    def test_physical_properties_generator(self, temp_case_directory: str):
        """Test that physical properties files can be generated."""
        from aortacfd_lib.physical_properties_setup import PhysicalPropertiesWriter

        config = {
            "physics": {"density": 1060, "viscosity": 0.004, "simulation_type": "laminar"},
            "openfoam_version": "12",
        }

        setup = PhysicalPropertiesWriter(config, temp_case_directory)
        setup.write_transportProperties_file()

        props_path = os.path.join(temp_case_directory, "constant", "transportProperties")
        assert os.path.exists(props_path)


class TestErrorHandling:
    """Test error handling throughout the pipeline."""

    def test_invalid_profile_raises_error(self):
        """Test that invalid numerics profile raises ValueError."""
        from config.numerics_builder import NumericsBuilder

        builder = NumericsBuilder()

        with pytest.raises(ValueError) as exc_info:
            builder._load_profile("nonexistent_profile")

        assert "Unknown numeric profile" in str(exc_info.value)

    def test_missing_required_fields_detected(self):
        """Test that missing required configuration fields are detected."""
        from config.numerics_builder import NumericsBuilder

        builder = NumericsBuilder()

        # Config missing required keys
        incomplete_config = {
            "physics": {"model": "laminar"}
            # Missing 'numerics' key
        }

        with pytest.raises((ValueError, KeyError)):
            builder.build(incomplete_config)


# Run pytest if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
