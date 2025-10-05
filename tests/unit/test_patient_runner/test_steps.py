#!/usr/bin/env python3
"""
Unit tests for patient_runner workflow steps

Tests the WorkflowSteps class and its methods.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
import sys
src_path = str(Path(__file__).parent.parent.parent.parent / 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from patient_runner.steps import WorkflowSteps


class TestWorkflowStepsInit:
    """Test WorkflowSteps initialization"""

    def test_init_creates_workflow_steps(self):
        """Should create WorkflowSteps instance"""
        steps = WorkflowSteps()
        assert steps is not None

    def test_init_creates_runner(self):
        """Should create PatientCaseRunner instance"""
        steps = WorkflowSteps()
        assert steps.runner is not None

    def test_init_has_step_mapping(self):
        """Should have step mapping dictionary"""
        steps = WorkflowSteps()
        assert isinstance(steps._step_mapping, dict)
        assert len(steps._step_mapping) > 0

    def test_init_has_step_descriptions(self):
        """Should have step descriptions dictionary"""
        steps = WorkflowSteps()
        assert isinstance(steps._step_descriptions, dict)
        assert len(steps._step_descriptions) > 0


class TestListAvailableSteps:
    """Test listing available workflow steps"""

    def test_list_available_steps_returns_list(self):
        """Should return list of available steps"""
        steps = WorkflowSteps()
        available = steps.list_available_steps()
        assert isinstance(available, list)

    def test_list_available_steps_contains_expected_steps(self):
        """Should contain expected workflow steps"""
        steps = WorkflowSteps()
        available = steps.list_available_steps()

        expected = ['case', 'mesh', 'boundary', 'solver', 'post']
        for step in expected:
            assert step in available

    def test_list_available_steps_not_empty(self):
        """Should return non-empty list"""
        steps = WorkflowSteps()
        available = steps.list_available_steps()
        assert len(available) > 0


class TestGetStepDescription:
    """Test getting step descriptions"""

    def test_get_step_description_case(self):
        """Should return description for case step"""
        steps = WorkflowSteps()
        desc = steps.get_step_description('case')
        assert 'case structure' in desc.lower()

    def test_get_step_description_mesh(self):
        """Should return description for mesh step"""
        steps = WorkflowSteps()
        desc = steps.get_step_description('mesh')
        assert 'mesh' in desc.lower()

    def test_get_step_description_boundary(self):
        """Should return description for boundary step"""
        steps = WorkflowSteps()
        desc = steps.get_step_description('boundary')
        assert 'boundary' in desc.lower()

    def test_get_step_description_solver(self):
        """Should return description for solver step"""
        steps = WorkflowSteps()
        desc = steps.get_step_description('solver')
        assert 'solver' in desc.lower()

    def test_get_step_description_post(self):
        """Should return description for post step"""
        steps = WorkflowSteps()
        desc = steps.get_step_description('post')
        assert 'post' in desc.lower()

    def test_get_step_description_unknown_step(self):
        """Should return unknown message for invalid step"""
        steps = WorkflowSteps()
        desc = steps.get_step_description('invalid_step')
        assert 'unknown' in desc.lower()


class TestGetStepDependencies:
    """Test step dependency retrieval"""

    def test_get_step_dependencies_case(self):
        """Case step should have no dependencies"""
        steps = WorkflowSteps()
        deps = steps.get_step_dependencies('case')
        assert deps == []

    def test_get_step_dependencies_mesh(self):
        """Mesh step should depend on case"""
        steps = WorkflowSteps()
        deps = steps.get_step_dependencies('mesh')
        assert deps == ['case']

    def test_get_step_dependencies_boundary(self):
        """Boundary step should depend on case and mesh"""
        steps = WorkflowSteps()
        deps = steps.get_step_dependencies('boundary')
        assert 'case' in deps
        assert 'mesh' in deps

    def test_get_step_dependencies_solver(self):
        """Solver step should depend on case, mesh, and boundary"""
        steps = WorkflowSteps()
        deps = steps.get_step_dependencies('solver')
        assert 'case' in deps
        assert 'mesh' in deps
        assert 'boundary' in deps

    def test_get_step_dependencies_post(self):
        """Post step should depend on all previous steps"""
        steps = WorkflowSteps()
        deps = steps.get_step_dependencies('post')
        assert 'case' in deps
        assert 'mesh' in deps
        assert 'boundary' in deps
        assert 'solver' in deps

    def test_get_step_dependencies_unknown_step(self):
        """Unknown step should return empty list"""
        steps = WorkflowSteps()
        deps = steps.get_step_dependencies('invalid_step')
        assert deps == []


class TestRunStep:
    """Test running individual workflow steps"""

    @patch.object(WorkflowSteps, '__init__', lambda x: None)
    def test_run_step_success(self):
        """Should run step successfully"""
        steps = WorkflowSteps()
        steps._step_mapping = {'case': 'setup:dict'}

        mock_runner = MagicMock()
        mock_runner.load_patient_case.return_value = {'patient_id': 'patient1', 'config': {}}
        mock_runner.prepare_simulation.return_value = {'config': {}}
        mock_runner.run_workflow_step.return_value = True
        steps.runner = mock_runner

        result = steps.run_step('patient1', 'case')

        assert result is True
        mock_runner.load_patient_case.assert_called_once_with('patient1')
        mock_runner.run_workflow_step.assert_called_once()

    @patch.object(WorkflowSteps, '__init__', lambda x: None)
    def test_run_step_invalid_step(self):
        """Should raise ValueError for invalid step"""
        steps = WorkflowSteps()
        steps._step_mapping = {'case': 'setup:dict'}
        steps.runner = MagicMock()

        with pytest.raises(ValueError, match="Invalid workflow step"):
            steps.run_step('patient1', 'invalid_step')

    @patch.object(WorkflowSteps, '__init__', lambda x: None)
    def test_run_step_with_options(self):
        """Should pass options to prepare_simulation"""
        steps = WorkflowSteps()
        steps._step_mapping = {'case': 'setup:dict'}

        mock_runner = MagicMock()
        mock_runner.load_patient_case.return_value = {'patient_id': 'patient1', 'config': {}}
        mock_runner.prepare_simulation.return_value = {'config': {}}
        mock_runner.run_workflow_step.return_value = True
        steps.runner = mock_runner

        options = {'profile': 'sim_laminar_fine'}
        steps.run_step('patient1', 'case', options)

        call_args = mock_runner.prepare_simulation.call_args
        assert call_args[0][1] == options

    @patch.object(WorkflowSteps, '__init__', lambda x: None)
    def test_run_step_failure(self):
        """Should return False when step fails"""
        steps = WorkflowSteps()
        steps._step_mapping = {'case': 'setup:dict'}

        mock_runner = MagicMock()
        mock_runner.load_patient_case.return_value = {'patient_id': 'patient1', 'config': {}}
        mock_runner.prepare_simulation.return_value = {'config': {}}
        mock_runner.run_workflow_step.return_value = False
        steps.runner = mock_runner

        result = steps.run_step('patient1', 'case')

        assert result is False


class TestRunMultipleSteps:
    """Test running multiple workflow steps"""

    @patch.object(WorkflowSteps, '__init__', lambda x: None)
    def test_run_multiple_steps_success(self):
        """Should run multiple steps successfully"""
        steps = WorkflowSteps()
        steps._step_mapping = {'case': 'setup:dict', 'mesh': 'run:mesh'}

        mock_runner = MagicMock()
        mock_runner.load_patient_case.return_value = {'patient_id': 'patient1', 'config': {}}
        mock_runner.prepare_simulation.return_value = {'config': {}}
        mock_runner.run_workflow_step.return_value = True
        steps.runner = mock_runner

        result = steps.run_multiple_steps('patient1', ['case', 'mesh'])

        assert result is True
        assert mock_runner.run_workflow_step.call_count == 2

    @patch.object(WorkflowSteps, '__init__', lambda x: None)
    def test_run_multiple_steps_invalid_step(self):
        """Should raise ValueError for invalid steps"""
        steps = WorkflowSteps()
        steps._step_mapping = {'case': 'setup:dict'}
        steps.runner = MagicMock()

        with pytest.raises(ValueError, match="Invalid workflow steps"):
            steps.run_multiple_steps('patient1', ['case', 'invalid'])

    @patch.object(WorkflowSteps, '__init__', lambda x: None)
    def test_run_multiple_steps_stops_on_failure(self):
        """Should stop execution when a step fails"""
        steps = WorkflowSteps()
        steps._step_mapping = {'case': 'setup:dict', 'mesh': 'run:mesh'}

        mock_runner = MagicMock()
        mock_runner.load_patient_case.return_value = {'patient_id': 'patient1', 'config': {}}
        mock_runner.prepare_simulation.return_value = {'config': {}}
        # First step succeeds, second step fails
        mock_runner.run_workflow_step.side_effect = [True, False]
        steps.runner = mock_runner

        result = steps.run_multiple_steps('patient1', ['case', 'mesh'])

        assert result is False
        assert mock_runner.run_workflow_step.call_count == 2

    @patch.object(WorkflowSteps, '__init__', lambda x: None)
    def test_run_multiple_steps_loads_patient_once(self):
        """Should load patient case only once"""
        steps = WorkflowSteps()
        steps._step_mapping = {'case': 'setup:dict', 'mesh': 'run:mesh'}

        mock_runner = MagicMock()
        mock_runner.load_patient_case.return_value = {'patient_id': 'patient1', 'config': {}}
        mock_runner.prepare_simulation.return_value = {'config': {}}
        mock_runner.run_workflow_step.return_value = True
        steps.runner = mock_runner

        steps.run_multiple_steps('patient1', ['case', 'mesh'])

        mock_runner.load_patient_case.assert_called_once()


class TestValidateStepSequence:
    """Test step sequence validation"""

    def test_validate_step_sequence_valid(self):
        """Should validate correct step sequence"""
        steps = WorkflowSteps()
        result = steps.validate_step_sequence(['case', 'mesh'])

        assert result['valid'] is True
        assert len(result['errors']) == 0

    def test_validate_step_sequence_invalid_step(self):
        """Should detect invalid steps"""
        steps = WorkflowSteps()
        result = steps.validate_step_sequence(['case', 'invalid_step'])

        assert result['valid'] is False
        assert len(result['errors']) > 0
        assert any('Invalid steps' in error for error in result['errors'])

    def test_validate_step_sequence_missing_dependency(self):
        """Should detect missing dependencies"""
        steps = WorkflowSteps()
        result = steps.validate_step_sequence(['mesh'])  # Missing 'case'

        assert result['valid'] is False
        assert len(result['errors']) > 0
        assert any('missing dependencies' in error for error in result['errors'])

    def test_validate_step_sequence_correct_order(self):
        """Should validate correct dependency order"""
        steps = WorkflowSteps()
        result = steps.validate_step_sequence(['case', 'mesh', 'boundary'])

        assert result['valid'] is True
        assert len(result['errors']) == 0

    def test_validate_step_sequence_wrong_order(self):
        """Should detect wrong dependency order"""
        steps = WorkflowSteps()
        result = steps.validate_step_sequence(['mesh', 'case'])  # Wrong order

        assert result['valid'] is False
        assert len(result['errors']) > 0

    def test_validate_step_sequence_empty_list(self):
        """Should validate empty list"""
        steps = WorkflowSteps()
        result = steps.validate_step_sequence([])

        assert result['valid'] is True
        assert len(result['errors']) == 0

    def test_validate_step_sequence_solver_without_boundary(self):
        """Should detect solver without boundary"""
        steps = WorkflowSteps()
        result = steps.validate_step_sequence(['case', 'mesh', 'solver'])  # Missing boundary

        assert result['valid'] is False
        assert len(result['errors']) > 0


class TestCreateCompletePatientAnalysis:
    """Test complete patient analysis workflow"""

    @patch.object(WorkflowSteps, '__init__', lambda x: None)
    def test_create_complete_patient_analysis(self):
        """Should run complete patient analysis"""
        steps = WorkflowSteps()

        mock_runner = MagicMock()
        mock_runner.run_patient_case.return_value = '/path/to/results'
        steps.runner = mock_runner

        result = steps.create_complete_patient_analysis('patient1')

        assert result == '/path/to/results'
        mock_runner.run_patient_case.assert_called_once_with('patient1', None)

    @patch.object(WorkflowSteps, '__init__', lambda x: None)
    def test_create_complete_patient_analysis_with_options(self):
        """Should pass options to run_patient_case"""
        steps = WorkflowSteps()

        mock_runner = MagicMock()
        mock_runner.run_patient_case.return_value = '/path/to/results'
        steps.runner = mock_runner

        options = {'profile': 'sim_laminar_fine'}
        steps.create_complete_patient_analysis('patient1', options)

        call_args = mock_runner.run_patient_case.call_args
        assert call_args[0][0] == 'patient1'
        assert call_args[0][1] == options


class TestStepMapping:
    """Test step mapping configuration"""

    def test_step_mapping_has_all_steps(self):
        """Step mapping should contain all expected steps"""
        steps = WorkflowSteps()

        expected_steps = ['case', 'mesh', 'boundary', 'solver', 'post']
        for step in expected_steps:
            assert step in steps._step_mapping

    def test_step_mapping_has_workflow_commands(self):
        """Step mapping should map to valid workflow commands"""
        steps = WorkflowSteps()

        expected_mappings = {
            'case': 'setup:dict',
            'mesh': 'run:mesh',
            'boundary': 'setup:bc',
            'solver': 'run:solver',
            'post': 'execute_post'
        }

        for step, command in expected_mappings.items():
            assert steps._step_mapping[step] == command

    def test_step_descriptions_match_mapping(self):
        """All mapped steps should have descriptions"""
        steps = WorkflowSteps()

        for step in steps._step_mapping.keys():
            assert step in steps._step_descriptions
            assert len(steps._step_descriptions[step]) > 0
