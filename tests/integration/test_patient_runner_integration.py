#!/usr/bin/env python3
"""
Integration tests for patient runner workflows

Tests the complete patient runner workflow with real data.
"""

import pytest
import json
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
import sys
src_path = str(Path(__file__).parent.parent.parent / 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from patient_runner.core import PatientCaseRunner, PatientValidationError
from patient_runner.steps import WorkflowSteps
from patient_runner.cli import main, create_parser


@pytest.fixture
def integration_patient_dir(tmp_path):
    """Create realistic patient directory for integration testing"""
    patient_dir = tmp_path / "cases_input" / "test_patient"
    patient_dir.mkdir(parents=True)

    # Create realistic config
    config = {
        "case_info": {
            "patient_id": "test_patient",
            "description": "Integration test patient"
        },
        "simulation_settings": {
            "solver_type": "laminar",
            "analysis_type": "coarse",
            "time_step": 0.001,
            "end_time": 0.1
        },
        "boundary_conditions": {
            "inlet": {
                "type": "timeVaryingMappedFixedValue",
                "profile": "parabolic"
            },
            "outlets": {
                "type": "zeroGradient",
                "num_outlets": 2
            }
        },
        "physics": {
            "blood_density": 1060,
            "blood_viscosity": 0.004
        },
        "computational": {
            "parallel": False
        },
        "geometry": {
            "inlet_keywords_ordered": "inlet",
            "outlet_keywords_ordered": ["outlet1", "outlet2"],
            "wall_keywords_ordered": "wall_aorta"
        }
    }

    with open(patient_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    # Create minimal STL files (valid geometry)
    stl_content_inlet = """solid inlet
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 1 0 0
    vertex 0.5 0.866 0
  endloop
endfacet
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 0.5 0.866 0
    vertex -0.5 0.866 0
  endloop
endfacet
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex -0.5 0.866 0
    vertex -1 0 0
  endloop
endfacet
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex -1 0 0
    vertex -0.5 -0.866 0
  endloop
endfacet
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex -0.5 -0.866 0
    vertex 0.5 -0.866 0
  endloop
endfacet
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 0.5 -0.866 0
    vertex 1 0 0
  endloop
endfacet
endsolid
"""

    stl_content_outlet = """solid outlet
facet normal 0 0 1
  outer loop
    vertex 0 0 10
    vertex 0.5 0 10
    vertex 0.25 0.433 10
  endloop
endfacet
facet normal 0 0 1
  outer loop
    vertex 0 0 10
    vertex 0.25 0.433 10
    vertex -0.25 0.433 10
  endloop
endfacet
facet normal 0 0 1
  outer loop
    vertex 0 0 10
    vertex -0.25 0.433 10
    vertex -0.5 0 10
  endloop
endfacet
endsolid
"""

    stl_content_wall = """solid wall_aorta
facet normal 1 0 0
  outer loop
    vertex 1 0 0
    vertex 1 0 10
    vertex 1 1 5
  endloop
endfacet
facet normal 1 0 0
  outer loop
    vertex 1 0 0
    vertex 1 1 5
    vertex 1 0 0
  endloop
endfacet
endsolid
"""

    (patient_dir / "inlet.stl").write_text(stl_content_inlet)
    (patient_dir / "outlet1.stl").write_text(stl_content_outlet)
    (patient_dir / "outlet2.stl").write_text(stl_content_outlet)
    (patient_dir / "wall_aorta.stl").write_text(stl_content_wall)

    # Create CSV file
    csv_content = """time,flow
0.0,1.0
0.1,1.5
0.2,1.3
0.3,1.1
0.4,1.0
"""
    (patient_dir / "flow.csv").write_text(csv_content)

    return patient_dir


class TestPatientRunnerCoreIntegration:
    """Integration tests for PatientCaseRunner"""

    def test_list_available_patients_with_real_directory(self, integration_patient_dir):
        """Should list available patients from real directory"""
        runner = PatientCaseRunner()
        runner.cases_dir = integration_patient_dir.parent

        patients = runner.list_available_patients()

        assert 'test_patient' in patients

    def test_load_patient_case_integration(self, integration_patient_dir):
        """Should load patient case with real files"""
        runner = PatientCaseRunner()
        runner.cases_dir = integration_patient_dir.parent

        case_info = runner.load_patient_case('test_patient')

        assert case_info['patient_id'] == 'test_patient'
        assert 'config' in case_info
        assert 'stl_files' in case_info
        assert 'flow_data' in case_info
        assert case_info['config']['case_info']['patient_id'] == 'test_patient'

    def test_load_patient_case_validates_stl_files(self, integration_patient_dir):
        """Should validate STL files exist"""
        runner = PatientCaseRunner()
        runner.cases_dir = integration_patient_dir.parent

        case_info = runner.load_patient_case('test_patient')

        assert 'inlet' in case_info['stl_files']
        assert 'outlet1' in case_info['stl_files']
        assert 'outlet2' in case_info['stl_files']
        assert 'wall_aorta' in case_info['stl_files']

    @patch('patient_runner.core.ConfigBuilder')
    @patch('patient_runner.core.ProfileComposer')
    def test_prepare_simulation_integration(self, mock_composer, mock_builder, integration_patient_dir):
        """Should prepare simulation with real config"""
        runner = PatientCaseRunner()
        runner.cases_dir = integration_patient_dir.parent

        # Setup mocks
        mock_builder_inst = MagicMock()
        base_config = {
            'mesh': {'SNAPPY_SETTINGS': {}},
            'physics': {'default_density': 1060},
            'schemes': {}
        }
        mock_builder_inst.build_base_and_profile.return_value = base_config.copy()
        mock_builder_inst._convert_unified_config.return_value = {}
        mock_builder_inst._apply_openfoam_12_settings.return_value = base_config.copy()
        mock_builder_inst._validate_physical_parameters.return_value = None
        mock_builder.return_value = mock_builder_inst

        mock_composer_inst = MagicMock()
        mock_composer_inst.compose.return_value = {}
        mock_composer.return_value = mock_composer_inst

        case_info = runner.load_patient_case('test_patient')
        sim_config = runner.prepare_simulation(case_info)

        assert 'config' in sim_config
        assert 'profile_name' in sim_config
        assert 'run_dir' in sim_config

    def test_patient_validation_missing_directory(self, tmp_path):
        """Should raise error for missing patient directory"""
        runner = PatientCaseRunner()
        runner.cases_dir = tmp_path / "empty_cases"

        with pytest.raises(PatientValidationError, match="Patient directory not found"):
            runner.load_patient_case('nonexistent_patient')


class TestWorkflowStepsIntegration:
    """Integration tests for WorkflowSteps"""

    def test_list_available_steps_integration(self):
        """Should list workflow steps"""
        steps = WorkflowSteps()
        available = steps.list_available_steps()

        assert 'case' in available
        assert 'mesh' in available
        assert 'boundary' in available
        assert 'solver' in available
        assert 'post' in available

    def test_get_step_dependencies_chain(self):
        """Should validate dependency chain"""
        steps = WorkflowSteps()

        # Verify dependency chain
        assert steps.get_step_dependencies('case') == []
        assert 'case' in steps.get_step_dependencies('mesh')
        assert 'mesh' in steps.get_step_dependencies('boundary')
        assert 'boundary' in steps.get_step_dependencies('solver')

    def test_validate_step_sequence_complete_workflow(self):
        """Should validate complete workflow sequence"""
        steps = WorkflowSteps()

        result = steps.validate_step_sequence(['case', 'mesh', 'boundary', 'solver', 'post'])

        assert result['valid'] is True
        assert len(result['errors']) == 0

    def test_validate_step_sequence_detects_skip(self):
        """Should detect skipped dependencies"""
        steps = WorkflowSteps()

        # Try to run solver without boundary
        result = steps.validate_step_sequence(['case', 'mesh', 'solver'])

        assert result['valid'] is False
        assert len(result['errors']) > 0

    @patch.object(WorkflowSteps, '__init__', lambda x: None)
    def test_run_step_integration_with_mock_runner(self):
        """Should run individual step with mocked runner"""
        steps = WorkflowSteps()
        steps._step_mapping = {'case': 'setup:dict'}

        mock_runner = MagicMock()
        mock_runner.load_patient_case.return_value = {
            'patient_id': 'test_patient',
            'config': {'case_info': {}}
        }
        mock_runner.prepare_simulation.return_value = {'config': {}}
        mock_runner.run_workflow_step.return_value = True
        steps.runner = mock_runner

        success = steps.run_step('test_patient', 'case')

        assert success is True
        mock_runner.load_patient_case.assert_called_once()
        mock_runner.run_workflow_step.assert_called_once()

    @patch.object(WorkflowSteps, '__init__', lambda x: None)
    def test_run_multiple_steps_integration(self):
        """Should run multiple steps in sequence"""
        steps = WorkflowSteps()
        steps._step_mapping = {'case': 'setup:dict', 'mesh': 'run:mesh'}

        mock_runner = MagicMock()
        mock_runner.load_patient_case.return_value = {
            'patient_id': 'test_patient',
            'config': {'case_info': {}}
        }
        mock_runner.prepare_simulation.return_value = {'config': {}}
        mock_runner.run_workflow_step.return_value = True
        steps.runner = mock_runner

        success = steps.run_multiple_steps('test_patient', ['case', 'mesh'])

        assert success is True
        assert mock_runner.run_workflow_step.call_count == 2


class TestCLIIntegration:
    """Integration tests for CLI"""

    def test_create_parser_integration(self):
        """Should create parser with all expected arguments"""
        parser = create_parser()

        assert parser is not None
        # Test that parser accepts valid arguments
        args = parser.parse_args(['patient1'])
        assert args.patient_id == 'patient1'

    def test_parser_accepts_all_step_combinations(self):
        """Should accept all valid step combinations"""
        parser = create_parser()

        steps = ['case', 'mesh', 'boundary', 'solver', 'post', 'all']
        for step in steps:
            args = parser.parse_args(['patient1', '--step', step])
            assert step in args.step

    def test_parser_accepts_multiple_steps(self):
        """Should accept multiple --step arguments"""
        parser = create_parser()

        args = parser.parse_args(['patient1', '--step', 'case', '--step', 'mesh'])
        assert args.step == ['case', 'mesh']

    @patch('patient_runner.cli.PatientCaseRunner')
    def test_main_with_real_patient_dir(self, mock_runner_class, integration_patient_dir):
        """Should execute main with real patient directory"""
        mock_runner = MagicMock()
        mock_runner.load_patient_case.return_value = {
            'patient_id': 'test_patient',
            'config': {'case_info': {'description': 'Test'}},
            'config_file': str(integration_patient_dir / 'config.json')
        }
        mock_runner.prepare_simulation.return_value = {
            'config': {},
            'profile_name': 'sim_laminar_coarse',
            'run_dir': integration_patient_dir / 'output'
        }
        mock_runner.run_workflow_step.return_value = True
        mock_runner.generate_results_summary.return_value = str(integration_patient_dir / 'results')
        mock_runner_class.return_value = mock_runner

        with patch('sys.argv', ['run_patient.py', 'test_patient']):
            with patch('sys.stdout'):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0


class TestEndToEndWorkflow:
    """End-to-end workflow integration tests"""

    @patch('patient_runner.core.ConfigBuilder')
    @patch('patient_runner.core.ProfileComposer')
    @patch('patient_runner.core.WorkflowManager')
    def test_complete_workflow_patient_loading_to_config(
        self, mock_manager, mock_composer, mock_builder, integration_patient_dir
    ):
        """Should complete workflow from patient loading to configuration"""
        runner = PatientCaseRunner()
        runner.cases_dir = integration_patient_dir.parent

        # Setup mocks
        mock_builder_inst = MagicMock()
        base_config = {
            'mesh': {'SNAPPY_SETTINGS': {}},
            'physics': {'default_density': 1060},
            'schemes': {}
        }
        mock_builder_inst.build_base_and_profile.return_value = base_config.copy()
        mock_builder_inst._convert_unified_config.return_value = {}
        mock_builder_inst._apply_openfoam_12_settings.return_value = base_config.copy()
        mock_builder_inst._validate_physical_parameters.return_value = None
        mock_builder.return_value = mock_builder_inst

        mock_composer_inst = MagicMock()
        mock_composer_inst.compose.return_value = {}
        mock_composer.return_value = mock_composer_inst

        mock_manager_inst = MagicMock()
        mock_manager_inst.context = {}
        mock_manager_inst.run_workflow.return_value = True
        mock_manager.return_value = mock_manager_inst

        # Execute workflow
        case_info = runner.load_patient_case('test_patient')
        assert case_info['patient_id'] == 'test_patient'

        sim_config = runner.prepare_simulation(case_info)
        assert 'config' in sim_config

        success = runner.run_workflow_step(sim_config, 'runAll')
        assert success is True

    @patch('patient_runner.core.ConfigBuilder')
    @patch('patient_runner.core.ProfileComposer')
    def test_workflow_with_different_profiles(
        self, mock_composer, mock_builder, integration_patient_dir
    ):
        """Should handle different simulation profiles"""
        runner = PatientCaseRunner()
        runner.cases_dir = integration_patient_dir.parent

        # Setup mocks
        mock_builder_inst = MagicMock()
        base_config = {
            'mesh': {'SNAPPY_SETTINGS': {}},
            'physics': {'default_density': 1060},
            'schemes': {}
        }
        mock_builder_inst.build_base_and_profile.return_value = base_config.copy()
        mock_builder_inst._convert_unified_config.return_value = {}
        mock_builder_inst._apply_openfoam_12_settings.return_value = base_config.copy()
        mock_builder_inst._validate_physical_parameters.return_value = None
        mock_builder.return_value = mock_builder_inst

        mock_composer_inst = MagicMock()
        mock_composer_inst.compose.return_value = {}
        mock_composer.return_value = mock_composer_inst

        case_info = runner.load_patient_case('test_patient')

        # Test different profiles
        profiles = ['sim_laminar_coarse', 'sim_laminar_medium', 'sim_laminar_fine']
        for profile in profiles:
            options = {'profile': profile}
            sim_config = runner.prepare_simulation(case_info, options)
            assert 'config' in sim_config

    def test_multiple_patients_sequential(self, integration_patient_dir):
        """Should handle multiple patients sequentially"""
        # Create second patient
        patient2_dir = integration_patient_dir.parent / "test_patient2"
        shutil.copytree(integration_patient_dir, patient2_dir)

        runner = PatientCaseRunner()
        runner.cases_dir = integration_patient_dir.parent

        patients = runner.list_available_patients()
        assert len(patients) >= 2
        assert 'test_patient' in patients
        assert 'test_patient2' in patients

        # Load both patients
        case1 = runner.load_patient_case('test_patient')
        case2 = runner.load_patient_case('test_patient2')

        assert case1['patient_id'] == 'test_patient'
        assert case2['patient_id'] == 'test_patient2'
