"""
Test suite for patient_runner/steps.py module.

Tests cover:
- WorkflowSteps class initialization
- Step listing and descriptions
- Step dependencies
- Step sequence validation
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestWorkflowStepsInit:
    """Test WorkflowSteps initialization."""

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_init(self, mock_runner_class):
        """Test initialization creates step mappings."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()

        assert steps._step_mapping is not None
        assert steps._step_descriptions is not None
        mock_runner_class.assert_called_once()

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_init_step_mapping_keys(self, mock_runner_class):
        """Test step mapping contains expected keys."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()

        assert 'case' in steps._step_mapping
        assert 'mesh' in steps._step_mapping
        assert 'boundary' in steps._step_mapping
        assert 'solver' in steps._step_mapping
        assert 'reconstruct' in steps._step_mapping
        assert 'post' in steps._step_mapping
        assert 'regenerate-numerics' in steps._step_mapping

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_init_step_mapping_values(self, mock_runner_class):
        """Test step mapping values are correct."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()

        assert steps._step_mapping['case'] == 'setup:dict'
        assert steps._step_mapping['mesh'] == 'run:mesh'
        assert steps._step_mapping['boundary'] == 'setup:bc'
        assert steps._step_mapping['solver'] == 'run:solver'


class TestListAvailableSteps:
    """Test list_available_steps method."""

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_list_steps(self, mock_runner_class):
        """Test listing available steps."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()
        available = steps.list_available_steps()

        assert 'case' in available
        assert 'mesh' in available
        assert 'boundary' in available
        assert 'solver' in available
        assert 'reconstruct' in available
        assert 'post' in available

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_list_steps_count(self, mock_runner_class):
        """Test correct number of available steps."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()
        available = steps.list_available_steps()

        assert len(available) == 7  # case, mesh, boundary, regenerate-numerics, solver, reconstruct, post


class TestGetStepDescription:
    """Test get_step_description method."""

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_case_description(self, mock_runner_class):
        """Test case step description."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()
        desc = steps.get_step_description('case')

        assert 'case' in desc.lower() or 'configuration' in desc.lower()

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_mesh_description(self, mock_runner_class):
        """Test mesh step description."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()
        desc = steps.get_step_description('mesh')

        assert 'mesh' in desc.lower()

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_solver_description(self, mock_runner_class):
        """Test solver step description."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()
        desc = steps.get_step_description('solver')

        assert 'solver' in desc.lower() or 'cfd' in desc.lower()

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_unknown_step_description(self, mock_runner_class):
        """Test unknown step returns error description."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()
        desc = steps.get_step_description('nonexistent')

        assert 'unknown' in desc.lower()


class TestGetStepDependencies:
    """Test get_step_dependencies method."""

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_case_no_dependencies(self, mock_runner_class):
        """Test case step has no dependencies."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()
        deps = steps.get_step_dependencies('case')

        assert deps == []

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_mesh_depends_on_case(self, mock_runner_class):
        """Test mesh step depends on case."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()
        deps = steps.get_step_dependencies('mesh')

        assert 'case' in deps
        assert len(deps) == 1

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_boundary_dependencies(self, mock_runner_class):
        """Test boundary step dependencies."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()
        deps = steps.get_step_dependencies('boundary')

        assert 'case' in deps
        assert 'mesh' in deps

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_solver_dependencies(self, mock_runner_class):
        """Test solver step dependencies."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()
        deps = steps.get_step_dependencies('solver')

        assert 'case' in deps
        assert 'mesh' in deps
        assert 'boundary' in deps

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_post_dependencies(self, mock_runner_class):
        """Test post step dependencies."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()
        deps = steps.get_step_dependencies('post')

        assert 'case' in deps
        assert 'mesh' in deps
        assert 'boundary' in deps
        assert 'solver' in deps

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_unknown_step_dependencies(self, mock_runner_class):
        """Test unknown step returns empty dependencies."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()
        deps = steps.get_step_dependencies('unknown')

        assert deps == []


class TestValidateStepSequence:
    """Test validate_step_sequence method."""

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_valid_sequence(self, mock_runner_class):
        """Test validating a correct sequence."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()
        result = steps.validate_step_sequence(['case', 'mesh', 'boundary', 'solver'])

        assert result['valid'] is True
        assert len(result['errors']) == 0

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_invalid_step_in_sequence(self, mock_runner_class):
        """Test validating sequence with invalid step."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()
        result = steps.validate_step_sequence(['case', 'invalid_step', 'mesh'])

        assert result['valid'] is False
        assert len(result['errors']) > 0
        assert any('invalid' in e.lower() for e in result['errors'])

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_missing_dependency_in_sequence(self, mock_runner_class):
        """Test validating sequence with missing dependency."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()
        # mesh without case
        result = steps.validate_step_sequence(['mesh'])

        assert result['valid'] is False
        assert len(result['errors']) > 0

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_empty_sequence(self, mock_runner_class):
        """Test validating empty sequence."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()
        result = steps.validate_step_sequence([])

        assert result['valid'] is True
        assert len(result['errors']) == 0

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_single_case_step(self, mock_runner_class):
        """Test validating single case step."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()
        result = steps.validate_step_sequence(['case'])

        assert result['valid'] is True


class TestRunStep:
    """Test run_step method."""

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_run_invalid_step_raises(self, mock_runner_class):
        """Test running invalid step raises ValueError."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()

        with pytest.raises(ValueError) as excinfo:
            steps.run_step('PAT001', 'invalid_step')

        assert 'invalid' in str(excinfo.value).lower()

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_run_step_calls_runner(self, mock_runner_class):
        """Test run_step calls runner methods."""
        from patient_runner.steps import WorkflowSteps

        mock_runner = MagicMock()
        mock_runner.load_patient_case.return_value = {'patient_id': 'PAT001'}
        mock_runner.prepare_simulation.return_value = {'config': 'data'}
        mock_runner.run_workflow_step.return_value = True
        mock_runner_class.return_value = mock_runner

        steps = WorkflowSteps()
        result = steps.run_step('PAT001', 'case')

        mock_runner.load_patient_case.assert_called_once_with('PAT001')
        mock_runner.prepare_simulation.assert_called_once()
        mock_runner.run_workflow_step.assert_called_once()
        assert result is True


class TestRunMultipleSteps:
    """Test run_multiple_steps method."""

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_run_multiple_invalid_steps_raises(self, mock_runner_class):
        """Test running multiple steps with invalid step raises."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()

        with pytest.raises(ValueError):
            steps.run_multiple_steps('PAT001', ['case', 'invalid'])

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_run_multiple_steps_success(self, mock_runner_class):
        """Test running multiple steps successfully."""
        from patient_runner.steps import WorkflowSteps

        mock_runner = MagicMock()
        mock_runner.load_patient_case.return_value = {'patient_id': 'PAT001'}
        mock_runner.prepare_simulation.return_value = {'config': 'data'}
        mock_runner.run_workflow_step.return_value = True
        mock_runner_class.return_value = mock_runner

        steps = WorkflowSteps()
        result = steps.run_multiple_steps('PAT001', ['case', 'mesh'])

        assert result is True
        assert mock_runner.run_workflow_step.call_count == 2

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_run_multiple_steps_failure(self, mock_runner_class):
        """Test running multiple steps stops on failure."""
        from patient_runner.steps import WorkflowSteps

        mock_runner = MagicMock()
        mock_runner.load_patient_case.return_value = {'patient_id': 'PAT001'}
        mock_runner.prepare_simulation.return_value = {'config': 'data'}
        # First step succeeds, second fails
        mock_runner.run_workflow_step.side_effect = [True, False]
        mock_runner_class.return_value = mock_runner

        steps = WorkflowSteps()
        result = steps.run_multiple_steps('PAT001', ['case', 'mesh'])

        assert result is False


class TestCreateCompletePatientAnalysis:
    """Test create_complete_patient_analysis method."""

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_complete_analysis_calls_runner(self, mock_runner_class):
        """Test complete analysis calls runner.run_patient_case."""
        from patient_runner.steps import WorkflowSteps

        mock_runner = MagicMock()
        mock_runner.run_patient_case.return_value = '/path/to/results'
        mock_runner_class.return_value = mock_runner

        steps = WorkflowSteps()
        result = steps.create_complete_patient_analysis('PAT001')

        mock_runner.run_patient_case.assert_called_once_with('PAT001', None)
        assert result == '/path/to/results'

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_complete_analysis_with_options(self, mock_runner_class):
        """Test complete analysis passes options to runner."""
        from patient_runner.steps import WorkflowSteps

        mock_runner = MagicMock()
        mock_runner.run_patient_case.return_value = '/path/to/results'
        mock_runner_class.return_value = mock_runner

        steps = WorkflowSteps()
        options = {'profile': 'fast'}
        steps.create_complete_patient_analysis('PAT001', options)

        mock_runner.run_patient_case.assert_called_once_with('PAT001', options)


class TestStepMappingIntegrity:
    """Test step mapping integrity and consistency."""

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_all_steps_have_descriptions(self, mock_runner_class):
        """Test all mapped steps have descriptions."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()

        for step in steps._step_mapping.keys():
            desc = steps.get_step_description(step)
            assert 'unknown' not in desc.lower(), f"Step '{step}' missing description"

    @patch('patient_runner.steps.PatientCaseRunner')
    def test_all_steps_have_dependencies_defined(self, mock_runner_class):
        """Test all mapped steps have dependencies defined."""
        from patient_runner.steps import WorkflowSteps

        steps = WorkflowSteps()

        for step in steps._step_mapping.keys():
            # Should not raise, even for empty deps
            deps = steps.get_step_dependencies(step)
            assert isinstance(deps, list)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
