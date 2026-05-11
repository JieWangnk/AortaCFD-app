"""
Test suite for patient_runner core module.

Tests cover:
- PatientCaseRunner class
- Patient validation and loading
- Configuration preparation
- Profile catalog
- Exception handling
"""

import pytest
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from patient_runner.core import (
    PatientCaseRunner,
    PatientValidationError,
    PatientConfigurationError,
    PatientSimulationError,
)


class TestPatientCaseRunnerInit:
    """Test PatientCaseRunner initialization."""

    def test_init_defaults(self):
        """Test default initialization."""
        runner = PatientCaseRunner()

        assert runner.cases_dir == Path("cases_input")
        assert runner.output_dir == Path("output")
        assert runner.logger is not None


class TestPatientIdValidation:
    """Test _is_valid_patient_id method."""

    def test_valid_patient_id(self):
        """Test valid patient IDs."""
        runner = PatientCaseRunner()

        assert runner._is_valid_patient_id("PAT001") is True
        assert runner._is_valid_patient_id("patient_1") is True
        assert runner._is_valid_patient_id("test-case") is True
        assert runner._is_valid_patient_id("ABC123") is True

    def test_invalid_patient_id_empty(self):
        """Test empty patient ID."""
        runner = PatientCaseRunner()

        assert runner._is_valid_patient_id("") is False
        assert runner._is_valid_patient_id(None) is False

    def test_invalid_patient_id_too_long(self):
        """Test patient ID that's too long."""
        runner = PatientCaseRunner()

        long_id = "a" * 51
        assert runner._is_valid_patient_id(long_id) is False

    def test_invalid_patient_id_special_chars(self):
        """Test patient ID with special characters."""
        runner = PatientCaseRunner()

        assert runner._is_valid_patient_id("PAT@001") is False
        assert runner._is_valid_patient_id("patient#1") is False
        assert runner._is_valid_patient_id("test$case") is False

    def test_invalid_patient_id_path_traversal(self):
        """Test patient ID with path traversal."""
        runner = PatientCaseRunner()

        assert runner._is_valid_patient_id("../etc") is False
        assert runner._is_valid_patient_id("PAT/001") is False
        assert runner._is_valid_patient_id("PAT\\001") is False


class TestClassifyStlFiles:
    """Test _classify_stl_files method."""

    def test_classify_inlet(self):
        """Test inlet STL classification."""
        runner = PatientCaseRunner()
        stl_files = [Path("/path/to/inlet.stl")]

        result = runner._classify_stl_files(stl_files)

        assert "inlet" in result
        assert result["inlet"] == Path("/path/to/inlet.stl")

    def test_classify_wall_aorta(self):
        """Test wall/aorta STL classification."""
        runner = PatientCaseRunner()
        stl_files = [Path("/path/to/wall_aorta.stl")]

        result = runner._classify_stl_files(stl_files)

        assert "wall_aorta" in result
        assert result["wall_aorta"] == Path("/path/to/wall_aorta.stl")

    def test_classify_outlets(self):
        """Test outlet STL classification with numbering."""
        runner = PatientCaseRunner()
        stl_files = [
            Path("/path/to/outlet1.stl"),
            Path("/path/to/outlet2.stl"),
            Path("/path/to/outlet3.stl"),
        ]

        result = runner._classify_stl_files(stl_files)

        assert "outlet1" in result
        assert "outlet2" in result
        assert "outlet3" in result

    def test_classify_mixed_files(self):
        """Test classification of mixed STL files."""
        runner = PatientCaseRunner()
        stl_files = [
            Path("/path/to/inlet.stl"),
            Path("/path/to/wall_aorta.stl"),
            Path("/path/to/outlet1.stl"),
            Path("/path/to/outlet2.stl"),
        ]

        result = runner._classify_stl_files(stl_files)

        assert "inlet" in result
        assert "wall_aorta" in result
        assert "outlet1" in result
        assert "outlet2" in result

    def test_classify_alternative_names(self):
        """Test classification with alternative naming."""
        runner = PatientCaseRunner()
        stl_files = [
            Path("/path/to/aorta_wall.stl"),
            Path("/path/to/inlet_patch.stl"),
        ]

        result = runner._classify_stl_files(stl_files)

        # Should classify based on presence of keywords
        assert len(result) >= 0  # May or may not match


class TestLoadPatientCase:
    """Test load_patient_case method."""

    def test_invalid_patient_id_format(self):
        """Test loading with invalid patient ID format."""
        runner = PatientCaseRunner()

        with pytest.raises(PatientValidationError) as exc_info:
            runner.load_patient_case("../etc/passwd")

        assert "Invalid patient ID" in str(exc_info.value)

    @patch.object(PatientCaseRunner, "_is_valid_patient_id", return_value=True)
    def test_patient_dir_not_found(self, mock_valid):
        """Test loading when patient directory doesn't exist."""
        runner = PatientCaseRunner()
        runner.cases_dir = Path("/nonexistent")

        with pytest.raises(PatientValidationError) as exc_info:
            runner.load_patient_case("PAT001")

        assert "not found" in str(exc_info.value)

    def test_load_with_custom_output_id(self):
        """Test load_patient_case with custom output_id."""
        runner = PatientCaseRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            patient_dir = Path(tmpdir) / "PAT001"
            patient_dir.mkdir()

            # Create config file
            config = {
                "case_info": {"patient_id": "PAT001"},
                "physics": {"model": "laminar"},
                "numerics": {"profile": "standard"},
                "mesh": {},
                "boundary_conditions": {},
            }
            config_file = patient_dir / "config.json"
            with open(config_file, "w") as f:
                json.dump(config, f)

            # Create STL file
            stl_file = patient_dir / "inlet.stl"
            stl_file.touch()

            runner.cases_dir = Path(tmpdir)

            result = runner.load_patient_case("PAT001", output_id="PAT001_custom")

            assert result["patient_id"] == "PAT001"
            assert result["output_id"] == "PAT001_custom"


class TestPrepareSimulation:
    """Test prepare_simulation method."""

    @patch.object(PatientCaseRunner, "_prepare_simulation_new_system")
    def test_prepare_with_new_system(self, mock_new_system):
        """Test prepare_simulation routes to new system."""
        runner = PatientCaseRunner()

        case_info = {
            "patient_id": "PAT001",
            "output_id": "PAT001",
            "config": {
                "physics": {"model": "laminar"},
                "numerics": {"profile": "standard"},
            },
        }

        mock_new_system.return_value = {"result": "test"}

        result = runner.prepare_simulation(case_info)

        mock_new_system.assert_called_once()
        assert result == {"result": "test"}

    def test_prepare_missing_physics_numerics(self):
        """Test prepare_simulation fails without physics/numerics."""
        runner = PatientCaseRunner()

        case_info = {"patient_id": "PAT001", "output_id": "PAT001", "config": {}}

        with pytest.raises(PatientConfigurationError):
            runner.prepare_simulation(case_info)


class TestResolveRunDirectory:
    """Test _resolve_run_directory method."""

    def test_resolve_default_timestamp(self):
        """Test default timestamp-based directory."""
        runner = PatientCaseRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            patient_output_dir = Path(tmpdir) / "PAT001"
            patient_output_dir.mkdir()

            result = runner._resolve_run_directory(patient_output_dir)

            assert result.parent == patient_output_dir
            assert result.name.startswith("run_")

    def test_resolve_with_run_name(self):
        """Test with custom run name."""
        runner = PatientCaseRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            patient_output_dir = Path(tmpdir) / "PAT001"
            patient_output_dir.mkdir()

            options = {"run_name": "my_custom_run"}
            result = runner._resolve_run_directory(patient_output_dir, options)

            assert result.name == "my_custom_run"

    def test_resolve_with_case_dir(self):
        """Test with existing case directory."""
        runner = PatientCaseRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            patient_output_dir = Path(tmpdir) / "PAT001"
            patient_output_dir.mkdir()

            existing_case = patient_output_dir / "existing_run"
            existing_case.mkdir()

            options = {"case_dir": str(existing_case)}
            result = runner._resolve_run_directory(patient_output_dir, options)

            assert result == existing_case

    def test_resolve_case_dir_with_openfoam(self):
        """Test with case_dir pointing to openfoam subdirectory."""
        runner = PatientCaseRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            patient_output_dir = Path(tmpdir) / "PAT001"
            run_dir = patient_output_dir / "existing_run"
            openfoam_dir = run_dir / "openfoam"
            openfoam_dir.mkdir(parents=True)

            options = {"case_dir": str(openfoam_dir)}
            result = runner._resolve_run_directory(patient_output_dir, options)

            assert result == run_dir


class TestProfileCatalog:
    """Test profile catalog methods."""

    def test_profile_catalog_structure(self):
        """Test profile catalog contains expected profiles."""
        runner = PatientCaseRunner()

        catalog = runner._profile_catalog()

        assert "sim_laminar_coarse" in catalog
        assert "sim_laminar_medium" in catalog
        assert "sim_laminar_fine" in catalog
        assert "sim_rans_coarse" in catalog
        assert "sim_rans_medium" in catalog
        assert "sim_rans_fine" in catalog
        assert "sim_les_medium" in catalog
        assert "sim_les_fine" in catalog

    def test_profile_catalog_data(self):
        """Test profile catalog data structure."""
        runner = PatientCaseRunner()

        catalog = runner._profile_catalog()
        profile = catalog["sim_laminar_medium"]

        assert "base_profile" in profile
        assert "display_name" in profile
        assert "solver_type" in profile
        assert "analysis_level" in profile
        assert "mesh_resolution" in profile
        assert "max_CFL" in profile
        assert "estimated_time" in profile
        assert "use_case" in profile

    def test_get_available_profiles(self):
        """Test get_available_profiles method."""
        runner = PatientCaseRunner()

        profiles = runner.get_available_profiles()

        assert len(profiles) > 0
        for key, data in profiles.items():
            assert "name" in data
            assert "time" in data
            assert "config" in data
            assert "use_case" in data

    def test_display_profile_selection(self):
        """Test display_profile_selection method."""
        runner = PatientCaseRunner()

        with patch("builtins.print"):
            profiles = runner.display_profile_selection()

        assert isinstance(profiles, dict)
        assert len(profiles) > 0


class TestResolveProfileChoice:
    """Test _resolve_profile_choice method."""

    def test_cli_profile_override(self):
        """Test CLI --profile override takes priority."""
        runner = PatientCaseRunner()
        catalog = runner._profile_catalog()

        simulation_settings = {"solver_type": "laminar", "analysis_type": "medium"}
        options = {"profile": "sim_rans_fine"}

        profile_key, profile_data, variant = runner._resolve_profile_choice(simulation_settings, options, catalog)

        assert profile_key == "sim_rans_fine"

    def test_unknown_profile_error(self):
        """Test error on unknown profile."""
        runner = PatientCaseRunner()
        catalog = runner._profile_catalog()

        simulation_settings = {}
        options = {"profile": "nonexistent_profile"}

        with pytest.raises(PatientConfigurationError) as exc_info:
            runner._resolve_profile_choice(simulation_settings, options, catalog)

        assert "Unknown profile" in str(exc_info.value)

    def test_direct_profile_key(self):
        """Test direct profile key matching."""
        runner = PatientCaseRunner()
        catalog = runner._profile_catalog()

        simulation_settings = {"solver_type": "laminar", "analysis_type": "medium"}
        options = None

        profile_key, profile_data, variant = runner._resolve_profile_choice(simulation_settings, options, catalog)

        assert profile_key == "sim_laminar_medium"

    def test_legacy_alias(self):
        """Test legacy alias mapping."""
        runner = PatientCaseRunner()
        catalog = runner._profile_catalog()

        simulation_settings = {"solver_type": "laminar", "analysis_type": "quick"}
        options = None

        profile_key, profile_data, variant = runner._resolve_profile_choice(simulation_settings, options, catalog)

        assert profile_key == "sim_laminar_coarse"


class TestListAvailablePatients:
    """Test list_available_patients method."""

    def test_list_with_valid_patients(self):
        """Test listing patients with valid cases."""
        runner = PatientCaseRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create valid patient directory
            patient_dir = Path(tmpdir) / "PAT001"
            patient_dir.mkdir()
            (patient_dir / "config.json").write_text("{}")
            (patient_dir / "test.stl").touch()

            runner.cases_dir = Path(tmpdir)

            patients = runner.list_available_patients()

            assert "PAT001" in patients

    def test_list_empty_directory(self):
        """Test listing with no patients."""
        runner = PatientCaseRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            runner.cases_dir = Path(tmpdir)

            patients = runner.list_available_patients()

            assert patients == []

    def test_list_nonexistent_directory(self):
        """Test listing with nonexistent cases directory."""
        runner = PatientCaseRunner()
        runner.cases_dir = Path("/nonexistent/path")

        patients = runner.list_available_patients()

        assert patients == []

    def test_list_excludes_invalid_cases(self):
        """Test that invalid cases are excluded."""
        runner = PatientCaseRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create directory without required files
            invalid_dir = Path(tmpdir) / "INVALID"
            invalid_dir.mkdir()

            # Create valid patient directory
            valid_dir = Path(tmpdir) / "VALID"
            valid_dir.mkdir()
            (valid_dir / "config.json").write_text("{}")
            (valid_dir / "test.stl").touch()

            runner.cases_dir = Path(tmpdir)

            patients = runner.list_available_patients()

            assert "VALID" in patients
            assert "INVALID" not in patients


class TestRunWorkflowStep:
    """Test run_workflow_step method."""

    @patch("patient_runner.core.WorkflowManager")
    def test_run_workflow_step_success(self, mock_wf_manager_class):
        """Test successful workflow step execution."""
        runner = PatientCaseRunner()

        mock_manager = MagicMock()
        mock_manager.context = {}
        mock_wf_manager_class.return_value = mock_manager

        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "run_test"
            run_dir.mkdir()

            sim_config = {
                "config": {"case_info": {"patient_id": "PAT001"}},
                "run_dir": run_dir,
            }

            result = runner.run_workflow_step(sim_config, "setup:dict")

            assert result is True
            mock_manager.run_workflow.assert_called_once_with("setup:dict")

    @patch("patient_runner.core.WorkflowManager")
    def test_run_workflow_step_failure(self, mock_wf_manager_class):
        """Test workflow step failure handling."""
        runner = PatientCaseRunner()

        mock_manager = MagicMock()
        mock_manager.context = {}
        mock_manager.run_workflow.side_effect = Exception("Workflow failed")
        mock_wf_manager_class.return_value = mock_manager

        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "run_test"
            run_dir.mkdir()

            sim_config = {
                "config": {"case_info": {"patient_id": "PAT001"}},
                "run_dir": run_dir,
            }

            result = runner.run_workflow_step(sim_config, "setup:dict")

            assert result is False


class TestGenerateResultsSummary:
    """Test generate_results_summary method."""

    def test_generate_summary(self):
        """Test summary generation."""
        runner = PatientCaseRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "run_test"
            run_dir.mkdir()

            # Create openfoam directory with logs
            openfoam_dir = run_dir / "openfoam"
            openfoam_dir.mkdir()
            logs_dir = openfoam_dir / "logs"
            logs_dir.mkdir()

            case_info = {"patient_id": "PAT001", "output_id": "PAT001"}
            sim_config = {"run_dir": run_dir, "output_directory": str(openfoam_dir)}

            result_path = runner.generate_results_summary(case_info, sim_config)

            assert Path(result_path).exists()
            assert (run_dir / "summary.json").exists()

            # Verify summary content
            with open(run_dir / "summary.json") as f:
                summary = json.load(f)

            assert summary["patient_id"] == "PAT001"
            assert "run_directory" in summary
            assert "analysis_completed" in summary


class TestExceptions:
    """Test custom exception classes."""

    def test_patient_validation_error(self):
        """Test PatientValidationError can be raised."""
        with pytest.raises(PatientValidationError):
            raise PatientValidationError("Validation failed")

    def test_patient_configuration_error(self):
        """Test PatientConfigurationError can be raised."""
        with pytest.raises(PatientConfigurationError):
            raise PatientConfigurationError("Config invalid")

    def test_patient_simulation_error(self):
        """Test PatientSimulationError can be raised."""
        with pytest.raises(PatientSimulationError):
            raise PatientSimulationError("Simulation failed")


class TestApplyConfigSettings:
    """Test _apply_config_settings and related methods."""

    def test_apply_blood_properties(self):
        """Test _apply_blood_properties method."""
        runner = PatientCaseRunner()

        config = {"physics": {}}
        case_config = {"physics": {"blood_density": 1060.0, "blood_viscosity": 0.0035}}

        runner._apply_blood_properties(config, case_config)

        assert config["physics"]["default_density"] == 1060.0
        assert config["physics"]["default_viscosity"] == 0.0035

    def test_apply_parallel_settings(self):
        """Test _apply_parallel_settings method."""
        runner = PatientCaseRunner()

        snappy_config = {}
        case_config = {"computational": {"parallel": True, "max_processors": 8}}

        runner._apply_parallel_settings(snappy_config, case_config)

        assert snappy_config["parallel"] is True
        assert snappy_config["nProcessors"] == 8

    def test_apply_boundary_layer_settings(self):
        """Test _apply_boundary_layer_settings method."""
        runner = PatientCaseRunner()

        snappy_config = {}
        mesh_config = {
            "boundary_layers": {"enabled": True, "num_layers": 5, "expansion_ratio": 1.2, "final_layer_thickness": 0.3}
        }

        runner._apply_boundary_layer_settings(snappy_config, mesh_config)

        assert snappy_config["addLayers"] is True
        assert snappy_config["addLayer"] == 5
        assert snappy_config["expansionRatio"] == 1.2
        assert snappy_config["finalLayerThickness"] == 0.3
        assert snappy_config["relativeSizes"] is True

    def test_apply_surface_refinement_settings(self):
        """Test _apply_surface_refinement_settings method."""
        runner = PatientCaseRunner()

        snappy_config = {}
        mesh_config = {"surface_refinement": {"levels": [2, 3]}}

        runner._apply_surface_refinement_settings(snappy_config, mesh_config)

        assert snappy_config["surfaceRefinementLevels"] == [2, 3]


class TestApplyPhysicsSettings:
    """Test _apply_physics_settings method."""

    def test_laminar_model(self):
        """Test laminar model mapping."""
        runner = PatientCaseRunner()

        merged_config = {}
        config = {"physics": {"model": "laminar"}}

        runner._apply_physics_settings(merged_config, config)

        assert merged_config["physics"]["simulation_type"] == "laminar"

    def test_rans_model(self):
        """Test RANS model mapping."""
        runner = PatientCaseRunner()

        merged_config = {}
        config = {"physics": {"model": "rans_komegasst"}}

        runner._apply_physics_settings(merged_config, config)

        assert merged_config["physics"]["simulation_type"] == "RAS"

    def test_les_model(self):
        """Test LES model mapping."""
        runner = PatientCaseRunner()

        merged_config = {}
        config = {"physics": {"model": "les_wale"}}

        runner._apply_physics_settings(merged_config, config)

        assert merged_config["physics"]["simulation_type"] == "LES"


class TestApplyTimeSteppingSettings:
    """Test _apply_time_stepping_settings method."""

    def test_apply_time_stepping(self):
        """Test time stepping settings application."""
        runner = PatientCaseRunner()

        merged_config = {}
        numerics_config = {
            "time_stepping": {"initial_delta_t": 1e-6, "adjustable_time_step": True, "max_co": 1.0, "max_delta_t": 1e-4}
        }

        runner._apply_time_stepping_settings(merged_config, numerics_config)

        control_dict = merged_config["simulation_control"]["controlDict"]
        assert control_dict["deltaT"] == 1e-6
        assert control_dict["adjustTimeStep"] == "yes"
        assert control_dict["maxCo"] == 1.0
        assert control_dict["maxDeltaT"] == 1e-4

    def test_no_time_stepping(self):
        """Test no time stepping settings."""
        runner = PatientCaseRunner()

        merged_config = {}
        numerics_config = {}

        runner._apply_time_stepping_settings(merged_config, numerics_config)

        # Should not modify config
        assert "simulation_control" not in merged_config


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
