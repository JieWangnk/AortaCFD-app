#!/usr/bin/env python3
"""
Unit tests for patient_runner core execution logic

Tests the PatientCaseRunner class and its methods.
"""

import pytest
import json
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from datetime import datetime

# Add src to path
import sys
src_path = str(Path(__file__).parent.parent.parent.parent / 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from patient_runner.core import (
    PatientCaseRunner,
    PatientValidationError,
    PatientConfigurationError,
    PatientSimulationError
)


class TestPatientCaseRunnerInit:
    """Test PatientCaseRunner initialization"""

    def test_init_creates_runner(self):
        """Should create runner instance"""
        runner = PatientCaseRunner()
        assert runner is not None

    def test_init_sets_default_directories(self):
        """Should set default cases_dir and output_dir"""
        runner = PatientCaseRunner()
        assert runner.cases_dir == Path('cases_input')
        assert runner.output_dir == Path('output')

    def test_init_creates_logger(self):
        """Should create logger instance"""
        runner = PatientCaseRunner()
        assert runner.logger is not None


class TestLoadPatientCase:
    """Test patient case loading and validation"""

    @pytest.fixture
    def mock_patient_dir(self, tmp_path):
        """Create mock patient directory with files"""
        patient_dir = tmp_path / "cases_input" / "patient1"
        patient_dir.mkdir(parents=True)

        # Create config file
        config = {
            "case_info": {"patient_id": "patient1"},
            "simulation_settings": {"solver_type": "laminar"},
            "boundary_conditions": {
                "inlet": {"type": "fixedValue"},
                "outlets": {"type": "zeroGradient"}
            }
        }
        with open(patient_dir / "config.json", "w") as f:
            json.dump(config, f)

        # Create STL files
        (patient_dir / "inlet.stl").write_text("solid inlet\nendsolid")
        (patient_dir / "outlet1.stl").write_text("solid outlet1\nendsolid")
        (patient_dir / "wall_aorta.stl").write_text("solid wall\nendsolid")

        # Create CSV file
        (patient_dir / "flow.csv").write_text("time,flow\n0,1.0\n0.1,1.5")

        return patient_dir

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_load_patient_case_success(self, mock_patient_dir):
        """Should load valid patient case"""
        runner = PatientCaseRunner()
        runner.cases_dir = mock_patient_dir.parent
        runner.logger = MagicMock()

        case_info = runner.load_patient_case("patient1")

        assert case_info['patient_id'] == 'patient1'
        assert case_info['patient_dir'] == mock_patient_dir
        assert 'config' in case_info
        assert 'stl_files' in case_info
        assert 'flow_data' in case_info

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_load_patient_invalid_id_format(self):
        """Should reject invalid patient ID"""
        runner = PatientCaseRunner()
        runner.cases_dir = Path('cases_input')
        runner.logger = MagicMock()

        with pytest.raises(PatientValidationError, match="Invalid patient ID format"):
            runner.load_patient_case("../etc/passwd")

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_load_patient_directory_not_found(self):
        """Should raise error for missing directory"""
        runner = PatientCaseRunner()
        runner.cases_dir = Path('cases_input')
        runner.logger = MagicMock()

        with pytest.raises(PatientValidationError, match="Patient directory not found"):
            runner.load_patient_case("nonexistent")

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_load_patient_config_not_found(self, mock_patient_dir):
        """Should raise error for missing config"""
        runner = PatientCaseRunner()
        runner.cases_dir = mock_patient_dir.parent
        runner.logger = MagicMock()

        # Remove config file
        (mock_patient_dir / "config.json").unlink()

        with pytest.raises(PatientValidationError, match="Configuration file not found"):
            runner.load_patient_case("patient1")

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_load_patient_invalid_json(self, mock_patient_dir):
        """Should raise error for invalid JSON"""
        runner = PatientCaseRunner()
        runner.cases_dir = mock_patient_dir.parent
        runner.logger = MagicMock()

        # Write invalid JSON
        with open(mock_patient_dir / "config.json", "w") as f:
            f.write("{invalid json")

        with pytest.raises(PatientConfigurationError, match="Invalid JSON"):
            runner.load_patient_case("patient1")

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_load_patient_missing_required_keys(self, mock_patient_dir):
        """Should raise error for missing required config keys"""
        runner = PatientCaseRunner()
        runner.cases_dir = mock_patient_dir.parent
        runner.logger = MagicMock()

        # Write config missing required keys
        with open(mock_patient_dir / "config.json", "w") as f:
            json.dump({"case_info": {}}, f)

        with pytest.raises(PatientConfigurationError, match="missing required keys"):
            runner.load_patient_case("patient1")

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_load_patient_no_stl_files(self, mock_patient_dir):
        """Should raise error when no STL files found"""
        runner = PatientCaseRunner()
        runner.cases_dir = mock_patient_dir.parent
        runner.logger = MagicMock()

        # Remove STL files
        for stl_file in mock_patient_dir.glob("*.stl"):
            stl_file.unlink()

        with pytest.raises(PatientValidationError, match="No STL files found"):
            runner.load_patient_case("patient1")

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_load_patient_custom_config_path(self, mock_patient_dir, tmp_path):
        """Should load custom config file"""
        runner = PatientCaseRunner()
        runner.cases_dir = mock_patient_dir.parent
        runner.logger = MagicMock()

        # Create custom config
        custom_config = tmp_path / "custom.json"
        config = {
            "case_info": {"patient_id": "custom"},
            "simulation_settings": {"solver_type": "rans"},
            "boundary_conditions": {"inlet": {}, "outlets": {}}
        }
        with open(custom_config, "w") as f:
            json.dump(config, f)

        case_info = runner.load_patient_case("patient1", str(custom_config))

        assert case_info['config']['simulation_settings']['solver_type'] == 'rans'


class TestValidationHelpers:
    """Test validation helper methods"""

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_is_valid_patient_id_valid(self):
        """Should accept valid patient IDs"""
        runner = PatientCaseRunner()

        assert runner._is_valid_patient_id("patient1") is True
        assert runner._is_valid_patient_id("patient_123") is True
        assert runner._is_valid_patient_id("test-case-1") is True

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_is_valid_patient_id_invalid(self):
        """Should reject invalid patient IDs"""
        runner = PatientCaseRunner()

        assert runner._is_valid_patient_id("") is False
        assert runner._is_valid_patient_id("a" * 51) is False
        assert runner._is_valid_patient_id("patient/1") is False
        assert runner._is_valid_patient_id("../etc") is False
        assert runner._is_valid_patient_id("patient;rm") is False

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_classify_stl_files(self):
        """Should classify STL files correctly"""
        runner = PatientCaseRunner()

        stl_files = [
            Path("inlet.stl"),
            Path("outlet1.stl"),
            Path("outlet2.stl"),
            Path("wall_aorta.stl")
        ]

        classified = runner._classify_stl_files(stl_files)

        assert classified['inlet'] == Path("inlet.stl")
        assert classified['wall_aorta'] == Path("wall_aorta.stl")
        assert classified['outlet1'] == Path("outlet1.stl")
        assert classified['outlet2'] == Path("outlet2.stl")


class TestPrepareSimulation:
    """Test simulation preparation"""

    @pytest.fixture
    def mock_case_info(self):
        """Create mock case info"""
        return {
            'patient_id': 'patient1',
            'patient_dir': Path('cases_input/patient1'),
            'config': {
                'case_info': {'patient_id': 'patient1'},
                'simulation_settings': {
                    'solver_type': 'laminar',
                    'analysis_type': 'medium'
                },
                'boundary_conditions': {'inlet': {}, 'outlets': {}},
                'physics': {
                    'blood_density': 1060,
                    'blood_viscosity': 0.004
                },
                'computational': {
                    'parallel': True,
                    'max_processors': 4
                }
            },
            'config_file': 'cases_input/patient1/config.json',
            'stl_files': {},
            'flow_data': None
        }

    @patch('patient_runner.core.ConfigBuilder')
    @patch('patient_runner.core.ProfileComposer')
    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_prepare_simulation_basic(self, mock_composer_class, mock_builder_class, mock_case_info, tmp_path):
        """Should prepare simulation config"""
        runner = PatientCaseRunner()
        runner.output_dir = tmp_path / "output"
        runner.logger = MagicMock()

        # Mock ConfigBuilder
        mock_builder = MagicMock()
        base_config = {
            'mesh': {'SNAPPY_SETTINGS': {}},
            'physics': {'default_density': 1060, 'default_viscosity': 0.004},
            'schemes': {}
        }
        mock_builder.build_base_and_profile.return_value = base_config.copy()
        mock_builder._convert_unified_config.return_value = {}
        mock_builder._apply_openfoam_12_settings.return_value = base_config.copy()
        mock_builder._validate_physical_parameters.return_value = None
        mock_builder_class.return_value = mock_builder

        # Mock ProfileComposer
        mock_composer = MagicMock()
        mock_composer.compose.return_value = {}
        mock_composer_class.return_value = mock_composer

        result = runner.prepare_simulation(mock_case_info)

        assert 'config' in result
        assert 'profile_name' in result
        assert 'run_dir' in result
        assert result['run_dir'].exists()

    @patch('patient_runner.core.ConfigBuilder')
    @patch('patient_runner.core.ProfileComposer')
    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_prepare_simulation_with_overwrite(self, mock_composer_class, mock_builder_class, mock_case_info, tmp_path):
        """Should overwrite existing directory when overwrite=True"""
        runner = PatientCaseRunner()
        runner.output_dir = tmp_path / "output"
        runner.logger = MagicMock()

        # Setup mocks
        mock_builder = MagicMock()
        base_config = {
            'mesh': {'SNAPPY_SETTINGS': {}},
            'physics': {'default_density': 1060, 'default_viscosity': 0.004},
            'schemes': {}
        }
        mock_builder.build_base_and_profile.return_value = base_config.copy()
        mock_builder._convert_unified_config.return_value = {}
        mock_builder._apply_openfoam_12_settings.return_value = base_config.copy()
        mock_builder._validate_physical_parameters.return_value = None
        mock_builder_class.return_value = mock_builder

        mock_composer = MagicMock()
        mock_composer.compose.return_value = {}
        mock_composer_class.return_value = mock_composer

        # Create existing directory
        existing_dir = runner.output_dir / "patient1" / "latest"
        existing_dir.mkdir(parents=True)
        (existing_dir / "old_file.txt").write_text("old")

        options = {'overwrite': True}
        result = runner.prepare_simulation(mock_case_info, options)

        assert result['run_dir'] == runner.output_dir / "patient1" / "latest"
        assert not (result['run_dir'] / "old_file.txt").exists()

    @patch('patient_runner.core.ConfigBuilder')
    @patch('patient_runner.core.ProfileComposer')
    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_prepare_simulation_with_profile_override(self, mock_composer_class, mock_builder_class, mock_case_info):
        """Should use profile from options when provided"""
        runner = PatientCaseRunner()
        runner.output_dir = Path("output")
        runner.logger = MagicMock()

        # Setup mocks
        mock_builder = MagicMock()
        base_config = {
            'mesh': {'SNAPPY_SETTINGS': {}},
            'physics': {'default_density': 1060, 'default_viscosity': 0.004},
            'schemes': {}
        }
        mock_builder.build_base_and_profile.return_value = base_config.copy()
        mock_builder._convert_unified_config.return_value = {}
        mock_builder._apply_openfoam_12_settings.return_value = base_config.copy()
        mock_builder._validate_physical_parameters.return_value = None
        mock_builder_class.return_value = mock_builder

        mock_composer = MagicMock()
        mock_composer.compose.return_value = {}
        mock_composer_class.return_value = mock_composer

        options = {'profile': 'sim_laminar_fine'}
        result = runner.prepare_simulation(mock_case_info, options)

        assert result['profile_key'] == 'sim_laminar_fine'


class TestRunWorkflowStep:
    """Test workflow step execution"""

    @patch('patient_runner.core.WorkflowManager')
    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_run_workflow_step_success(self, mock_manager_class, tmp_path):
        """Should run workflow step successfully"""
        runner = PatientCaseRunner()
        runner.logger = MagicMock()

        mock_manager = MagicMock()
        mock_manager.context = {}
        mock_manager.run_workflow.return_value = True
        mock_manager_class.return_value = mock_manager

        sim_config = {
            'config': {},
            'run_dir': tmp_path / "run"
        }

        result = runner.run_workflow_step(sim_config, 'setup')

        assert result is True
        mock_manager.run_workflow.assert_called_once_with('setup')

    @patch('patient_runner.core.WorkflowManager')
    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_run_workflow_step_failure(self, mock_manager_class, tmp_path):
        """Should handle workflow step failure"""
        runner = PatientCaseRunner()
        runner.logger = MagicMock()

        mock_manager = MagicMock()
        mock_manager.context = {}
        mock_manager.run_workflow.side_effect = Exception("Workflow failed")
        mock_manager_class.return_value = mock_manager

        sim_config = {
            'config': {},
            'run_dir': tmp_path / "run"
        }

        result = runner.run_workflow_step(sim_config, 'mesh')

        assert result is False


class TestGenerateResultsSummary:
    """Test results summary generation"""

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_generate_results_summary_basic(self, tmp_path):
        """Should generate basic results summary"""
        runner = PatientCaseRunner()
        runner.logger = MagicMock()

        case_info = {'patient_id': 'patient1'}
        sim_config = {
            'run_dir': tmp_path / "run",
            'output_directory': str(tmp_path / "openfoam")
        }

        sim_config['run_dir'].mkdir(parents=True)

        result_path = runner.generate_results_summary(case_info, sim_config)

        assert Path(result_path).exists()
        assert (Path(result_path) / "summary.json").exists()
        assert (Path(result_path) / "results").exists()
        assert (Path(result_path) / "logs").exists()

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_generate_results_summary_copies_logs(self, tmp_path):
        """Should copy OpenFOAM logs to results"""
        runner = PatientCaseRunner()
        runner.logger = MagicMock()

        openfoam_dir = tmp_path / "openfoam"
        openfoam_logs = openfoam_dir / "logs"
        openfoam_logs.mkdir(parents=True)
        (openfoam_logs / "log.blockMesh").write_text("blockMesh output")

        case_info = {'patient_id': 'patient1'}
        sim_config = {
            'run_dir': tmp_path / "run",
            'output_directory': str(openfoam_dir)
        }
        sim_config['run_dir'].mkdir(parents=True)

        result_path = runner.generate_results_summary(case_info, sim_config)

        assert (Path(result_path) / "logs" / "openfoam" / "log.blockMesh").exists()


class TestListAvailablePatients:
    """Test patient listing functionality"""

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_list_available_patients_found(self, tmp_path):
        """Should list available patients"""
        runner = PatientCaseRunner()
        runner.cases_dir = tmp_path / "cases_input"
        runner.logger = MagicMock()

        # Create patient directories
        for patient_id in ['patient1', 'patient2']:
            patient_dir = runner.cases_dir / patient_id
            patient_dir.mkdir(parents=True)
            (patient_dir / "config.json").write_text("{}")
            (patient_dir / "inlet.stl").write_text("solid")

        patients = runner.list_available_patients()

        assert len(patients) == 2
        assert 'patient1' in patients
        assert 'patient2' in patients

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_list_available_patients_none_found(self, tmp_path):
        """Should return empty list when no patients found"""
        runner = PatientCaseRunner()
        runner.cases_dir = tmp_path / "cases_input"
        runner.logger = MagicMock()

        patients = runner.list_available_patients()

        assert patients == []

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_list_available_patients_filters_invalid(self, tmp_path):
        """Should filter out invalid patient directories"""
        runner = PatientCaseRunner()
        runner.cases_dir = tmp_path / "cases_input"
        runner.cases_dir.mkdir(parents=True)
        runner.logger = MagicMock()

        # Create valid patient
        valid_dir = runner.cases_dir / "patient1"
        valid_dir.mkdir()
        (valid_dir / "config.json").write_text("{}")
        (valid_dir / "inlet.stl").write_text("solid")

        # Create invalid patient (no STL)
        invalid_dir = runner.cases_dir / "patient2"
        invalid_dir.mkdir()
        (invalid_dir / "config.json").write_text("{}")

        patients = runner.list_available_patients()

        assert len(patients) == 1
        assert 'patient1' in patients


class TestRunPatientCase:
    """Test complete patient case execution"""

    @patch.object(PatientCaseRunner, 'load_patient_case')
    @patch.object(PatientCaseRunner, 'prepare_simulation')
    @patch.object(PatientCaseRunner, 'run_workflow_step')
    @patch.object(PatientCaseRunner, 'generate_results_summary')
    def test_run_patient_case_success(self, mock_summary, mock_workflow, mock_prepare, mock_load):
        """Should run complete patient case successfully"""
        runner = PatientCaseRunner()

        mock_load.return_value = {'patient_id': 'patient1', 'config': {}}
        mock_prepare.return_value = {'config': {}, 'run_dir': Path('output/run')}
        mock_workflow.return_value = True
        mock_summary.return_value = '/path/to/results'

        result = runner.run_patient_case('patient1')

        assert result == '/path/to/results'
        mock_load.assert_called_once_with('patient1')
        mock_workflow.assert_called_once()
        mock_summary.assert_called_once()

    @patch.object(PatientCaseRunner, 'load_patient_case')
    @patch.object(PatientCaseRunner, 'prepare_simulation')
    @patch.object(PatientCaseRunner, 'run_workflow_step')
    def test_run_patient_case_workflow_failure(self, mock_workflow, mock_prepare, mock_load):
        """Should raise error when workflow fails"""
        runner = PatientCaseRunner()

        mock_load.return_value = {'patient_id': 'patient1', 'config': {}}
        mock_prepare.return_value = {'config': {}, 'run_dir': Path('output/run')}
        mock_workflow.return_value = False

        with pytest.raises(PatientSimulationError, match="Simulation workflow failed"):
            runner.run_patient_case('patient1')

    @patch.object(PatientCaseRunner, 'load_patient_case')
    @patch.object(PatientCaseRunner, 'prepare_simulation')
    @patch.object(PatientCaseRunner, 'run_workflow_step')
    @patch.object(PatientCaseRunner, 'generate_results_summary')
    def test_run_patient_case_with_workflow_step_option(self, mock_summary, mock_workflow, mock_prepare, mock_load):
        """Should run specific workflow step when provided"""
        runner = PatientCaseRunner()

        mock_load.return_value = {'patient_id': 'patient1', 'config': {}}
        mock_prepare.return_value = {'config': {}, 'run_dir': Path('output/run')}
        mock_workflow.return_value = True
        mock_summary.return_value = '/path/to/results'

        options = {'workflow_step': 'mesh'}
        runner.run_patient_case('patient1', options)

        mock_workflow.assert_called_once()
        call_args = mock_workflow.call_args
        assert call_args[0][1] == 'mesh'


class TestProfileCatalog:
    """Test profile catalog and selection"""

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_profile_catalog_returns_dict(self):
        """Should return profile catalog"""
        runner = PatientCaseRunner()
        runner.logger = MagicMock()

        catalog = runner._profile_catalog()

        assert isinstance(catalog, dict)
        assert len(catalog) > 0

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_profile_catalog_contains_expected_profiles(self):
        """Should contain expected simulation profiles"""
        runner = PatientCaseRunner()
        runner.logger = MagicMock()

        catalog = runner._profile_catalog()

        expected = [
            'sim_laminar_coarse',
            'sim_laminar_medium',
            'sim_laminar_fine',
            'sim_rans_coarse',
            'sim_rans_medium',
            'sim_rans_fine',
            'sim_les_medium',
            'sim_les_fine'
        ]

        for profile in expected:
            assert profile in catalog

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_resolve_profile_choice_cli_override(self):
        """Should prioritize CLI profile override"""
        runner = PatientCaseRunner()
        runner.logger = MagicMock()

        catalog = runner._profile_catalog()
        sim_settings = {'solver_type': 'laminar', 'analysis_type': 'medium'}
        options = {'profile': 'sim_rans_fine'}

        key, data, variant = runner._resolve_profile_choice(sim_settings, options, catalog)

        assert key == 'sim_rans_fine'
        assert data['solver_type'] == 'rans'

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_resolve_profile_choice_config_settings(self):
        """Should use config solver and analysis settings"""
        runner = PatientCaseRunner()
        runner.logger = MagicMock()

        catalog = runner._profile_catalog()
        sim_settings = {'solver_type': 'laminar', 'analysis_type': 'fine'}

        key, data, variant = runner._resolve_profile_choice(sim_settings, None, catalog)

        assert key == 'sim_laminar_fine'

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_resolve_profile_choice_fallback(self):
        """Should fallback to default when profile not found"""
        runner = PatientCaseRunner()
        runner.logger = MagicMock()

        catalog = runner._profile_catalog()
        sim_settings = {'solver_type': 'unknown', 'analysis_type': 'invalid'}

        key, data, variant = runner._resolve_profile_choice(sim_settings, None, catalog)

        assert key in catalog  # Should fallback to valid profile

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_resolve_profile_choice_invalid_override(self):
        """Should raise error for invalid profile override"""
        runner = PatientCaseRunner()
        runner.logger = MagicMock()

        catalog = runner._profile_catalog()
        sim_settings = {}
        options = {'profile': 'invalid_profile'}

        with pytest.raises(PatientConfigurationError, match="Unknown profile override"):
            runner._resolve_profile_choice(sim_settings, options, catalog)


class TestGetAvailableProfiles:
    """Test profile listing and display"""

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_get_available_profiles(self):
        """Should return user-friendly profile list"""
        runner = PatientCaseRunner()
        runner.logger = MagicMock()

        profiles = runner.get_available_profiles()

        assert isinstance(profiles, dict)
        assert 'sim_laminar_medium' in profiles
        assert 'name' in profiles['sim_laminar_medium']
        assert 'time' in profiles['sim_laminar_medium']
        assert 'use_case' in profiles['sim_laminar_medium']

    @patch.object(PatientCaseRunner, '__init__', lambda x: None)
    def test_display_profile_selection(self, capsys):
        """Should display profile selection menu"""
        runner = PatientCaseRunner()
        runner.logger = MagicMock()

        profiles = runner.display_profile_selection()

        captured = capsys.readouterr()
        assert "SIMULATION PROFILE SELECTION" in captured.out
        assert "sim_laminar_medium" in captured.out
        assert isinstance(profiles, dict)
