#!/usr/bin/env python3
"""
Unit tests for patient_runner CLI argument parsing

Tests the command-line interface for the AortaCFD patient runner.
"""

import pytest
import sys
from pathlib import Path
from io import StringIO
from unittest.mock import patch, MagicMock

# Add src to path
src_path = str(Path(__file__).parent.parent.parent.parent / 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from patient_runner.cli import create_parser, main


class TestCLIArgumentParsing:
    """Test CLI argument parsing functionality"""

    def test_create_parser_returns_parser(self):
        """Parser creation should return ArgumentParser instance"""
        parser = create_parser()
        assert parser is not None
        assert hasattr(parser, 'parse_args')

    def test_parse_basic_patient_id(self):
        """Basic patient ID parsing"""
        parser = create_parser()
        args = parser.parse_args(['patient1'])
        assert args.patient_id == 'patient1'

    def test_parse_with_list_flag(self):
        """--list flag parsing"""
        parser = create_parser()
        args = parser.parse_args(['--list'])
        assert args.list is True
        assert args.patient_id is None

    def test_parse_with_list_short_flag(self):
        """- l flag parsing"""
        parser = create_parser()
        args = parser.parse_args(['-l'])
        assert args.list is True

    def test_parse_with_list_steps_flag(self):
        """--list-steps flag parsing"""
        parser = create_parser()
        args = parser.parse_args(['--list-steps'])
        assert args.list_steps is True

    def test_parse_single_step(self):
        """Single --step argument"""
        parser = create_parser()
        args = parser.parse_args(['patient1', '--step', 'mesh'])
        assert args.step == ['mesh']

    def test_parse_multiple_steps(self):
        """Multiple --step arguments"""
        parser = create_parser()
        args = parser.parse_args(['patient1', '--step', 'case', '--step', 'mesh'])
        assert args.step == ['case', 'mesh']

    def test_parse_all_valid_steps(self):
        """All valid step options"""
        parser = create_parser()
        valid_steps = ['case', 'mesh', 'boundary', 'solver', 'post', 'all']
        for step in valid_steps:
            args = parser.parse_args(['patient1', '--step', step])
            assert args.step == [step]

    def test_parse_invalid_step_raises_error(self):
        """Invalid step should raise error"""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(['patient1', '--step', 'invalid'])

    def test_parse_quick_flag(self):
        """--quick flag parsing"""
        parser = create_parser()
        args = parser.parse_args(['patient1', '--quick'])
        assert args.quick is True

    def test_parse_overwrite_flag(self):
        """--overwrite flag parsing"""
        parser = create_parser()
        args = parser.parse_args(['patient1', '--overwrite'])
        assert args.overwrite is True

    def test_parse_profile_option(self):
        """--profile option parsing"""
        parser = create_parser()
        # Test with a known profile (sim_laminar_medium exists)
        args = parser.parse_args(['patient1', '--profile', 'sim_laminar_medium'])
        assert args.profile == 'sim_laminar_medium'

    def test_parse_custom_config_path(self):
        """--config option parsing"""
        parser = create_parser()
        config_path = '/path/to/custom/config.json'
        args = parser.parse_args(['patient1', '--config', config_path])
        assert args.config == config_path

    def test_parse_combined_flags(self):
        """Multiple flags combined"""
        parser = create_parser()
        args = parser.parse_args([
            'patient1',
            '--step', 'mesh',
            '--quick',
            '--overwrite',
            '--profile', 'sim_laminar_coarse'
        ])
        assert args.patient_id == 'patient1'
        assert args.step == ['mesh']
        assert args.quick is True
        assert args.overwrite is True
        assert args.profile == 'sim_laminar_coarse'

    def test_no_arguments_patient_id_is_none(self):
        """No arguments results in None patient_id"""
        parser = create_parser()
        args = parser.parse_args([])
        assert args.patient_id is None


class TestCLIMain:
    """Test CLI main() function behavior"""

    @patch('patient_runner.cli.PatientCaseRunner')
    def test_main_with_list_flag(self, mock_runner_class):
        """main() with --list should list patients"""
        mock_runner = MagicMock()
        mock_runner.list_available_patients.return_value = ['patient1', 'patient2']
        mock_runner_class.return_value = mock_runner

        with patch('sys.argv', ['run_patient.py', '--list']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                main()
                output = mock_stdout.getvalue()
                assert 'patient1' in output
                assert 'patient2' in output
                assert 'Available Patient Cases' in output

    @patch('patient_runner.cli.PatientCaseRunner')
    def test_main_with_list_no_patients(self, mock_runner_class):
        """main() with --list but no patients found"""
        mock_runner = MagicMock()
        mock_runner.list_available_patients.return_value = []
        mock_runner_class.return_value = mock_runner

        with patch('sys.argv', ['run_patient.py', '--list']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                main()
                output = mock_stdout.getvalue()
                assert 'No patient cases found' in output

    @patch('patient_runner.cli.PatientCaseRunner')
    def test_main_with_list_steps(self, mock_runner_class):
        """main() with --list-steps should list workflow steps"""
        # Mock WorkflowSteps from the steps module where it's imported
        with patch('patient_runner.steps.WorkflowSteps') as mock_steps_class:
            mock_steps = MagicMock()
            mock_steps.get_step_dependencies.return_value = []
            mock_steps_class.return_value = mock_steps

            with patch('sys.argv', ['run_patient.py', '--list-steps']):
                with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                    main()
                    output = mock_stdout.getvalue()
                    assert 'Workflow Steps' in output
                    assert 'case' in output
                    assert 'mesh' in output

    @patch('patient_runner.cli.PatientCaseRunner')
    def test_main_requires_patient_id(self, mock_runner_class):
        """main() without patient_id should show error"""
        with patch('sys.argv', ['run_patient.py']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit):
                    main()

    @patch('patient_runner.cli.PatientCaseRunner')
    def test_main_runs_patient_case(self, mock_runner_class):
        """main() with patient_id should run patient case"""
        mock_runner = MagicMock()
        mock_runner.load_patient_case.return_value = {
            'patient_id': 'patient1',
            'config': {'case_info': {}},
            'config_file': 'cases_input/patient1/config.json'
        }
        mock_runner.prepare_simulation.return_value = {
            'config': {},
            'profile_name': 'sim_laminar_medium',
            'run_dir': '/path/to/run'
        }
        mock_runner.run_workflow_step.return_value = True
        mock_runner.generate_results_summary.return_value = '/path/to/results'
        mock_runner_class.return_value = mock_runner

        with patch('sys.argv', ['run_patient.py', 'patient1']):
            with patch('sys.stdout', new_callable=StringIO):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0  # Success exit
                mock_runner.load_patient_case.assert_called_once_with('patient1', config_path=None)

    @patch('patient_runner.cli.PatientCaseRunner')
    def test_main_with_step_option(self, mock_runner_class):
        """main() with --step should pass steps to runner"""
        mock_runner = MagicMock()
        mock_runner.load_patient_case.return_value = {
            'patient_id': 'patient1',
            'config': {'case_info': {}},
            'config_file': 'cases_input/patient1/config.json'
        }
        mock_runner.prepare_simulation.return_value = {
            'config': {},
            'profile_name': 'sim_laminar_medium',
            'run_dir': '/path/to/run'
        }
        mock_runner.run_workflow_step.return_value = True
        mock_runner.generate_results_summary.return_value = '/path/to/results'
        mock_runner_class.return_value = mock_runner

        with patch('sys.argv', ['run_patient.py', 'patient1', '--step', 'mesh']):
            with patch('sys.stdout', new_callable=StringIO):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0
                # Verify workflow step was called with mesh mapping
                mock_runner.run_workflow_step.assert_called()
                call_args = mock_runner.run_workflow_step.call_args
                assert call_args[0][1] == 'run:mesh'  # workflow command

    @patch('patient_runner.cli.PatientCaseRunner')
    def test_main_with_quick_option(self, mock_runner_class):
        """main() with --quick should pass quick flag"""
        mock_runner = MagicMock()
        mock_runner.load_patient_case.return_value = {
            'patient_id': 'patient1',
            'config': {'case_info': {}},
            'config_file': 'cases_input/patient1/config.json'
        }
        mock_runner.prepare_simulation.return_value = {
            'config': {},
            'profile_name': 'sim_laminar_coarse',
            'run_dir': '/path/to/run'
        }
        mock_runner.run_workflow_step.return_value = True
        mock_runner.generate_results_summary.return_value = '/path/to/results'
        mock_runner_class.return_value = mock_runner

        with patch('sys.argv', ['run_patient.py', 'patient1', '--quick']):
            with patch('sys.stdout', new_callable=StringIO):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0
                # Verify --quick sets profile to sim_laminar_coarse
                call_args = mock_runner.prepare_simulation.call_args
                options = call_args[0][1]
                assert options['profile'] == 'sim_laminar_coarse'

    @patch('patient_runner.cli.PatientCaseRunner')
    def test_main_with_profile_option(self, mock_runner_class):
        """main() with --profile should pass profile to runner"""
        mock_runner = MagicMock()
        mock_runner.get_available_profiles.return_value = {
            'sim_laminar_fine': {'name': 'Laminar Fine'}
        }
        mock_runner.load_patient_case.return_value = {
            'patient_id': 'patient1',
            'config': {'case_info': {}},
            'config_file': 'cases_input/patient1/config.json'
        }
        mock_runner.prepare_simulation.return_value = {
            'config': {},
            'profile_name': 'sim_laminar_fine',
            'run_dir': '/path/to/run'
        }
        mock_runner.run_workflow_step.return_value = True
        mock_runner.generate_results_summary.return_value = '/path/to/results'
        mock_runner_class.return_value = mock_runner

        with patch('sys.argv', ['run_patient.py', 'patient1', '--profile', 'sim_laminar_fine']):
            with patch('sys.stdout', new_callable=StringIO):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0
                call_args = mock_runner.prepare_simulation.call_args
                options = call_args[0][1]
                assert options['profile'] == 'sim_laminar_fine'

    @patch('patient_runner.cli.PatientCaseRunner')
    def test_main_with_custom_config(self, mock_runner_class):
        """main() with --config should pass config path"""
        mock_runner = MagicMock()
        config_path = '/custom/config.json'
        mock_runner.load_patient_case.return_value = {
            'patient_id': 'patient1',
            'config': {'case_info': {}},
            'config_file': config_path
        }
        mock_runner.prepare_simulation.return_value = {
            'config': {},
            'profile_name': 'sim_laminar_medium',
            'run_dir': '/path/to/run'
        }
        mock_runner.run_workflow_step.return_value = True
        mock_runner.generate_results_summary.return_value = '/path/to/results'
        mock_runner_class.return_value = mock_runner

        with patch('sys.argv', ['run_patient.py', 'patient1', '--config', config_path]):
            with patch('sys.stdout', new_callable=StringIO):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0
                # Verify config_path was passed to load_patient_case
                mock_runner.load_patient_case.assert_called_once_with('patient1', config_path=config_path)

    @patch('patient_runner.cli.PatientCaseRunner')
    def test_main_handles_simulation_error(self, mock_runner_class):
        """main() should handle simulation errors gracefully"""
        from patient_runner.core import PatientSimulationError

        mock_runner = MagicMock()
        mock_runner.load_patient_case.side_effect = PatientSimulationError("Mesh generation failed")
        mock_runner_class.return_value = mock_runner

        with patch('sys.argv', ['run_patient.py', 'patient1']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1  # Error exit
                output = mock_stdout.getvalue()
                assert 'Mesh generation failed' in output or 'Error' in output


class TestCLIHelpText:
    """Test CLI help text and documentation"""

    def test_parser_has_description(self):
        """Parser should have description"""
        parser = create_parser()
        assert parser.description is not None
        assert 'AortaCFD' in parser.description

    def test_parser_has_epilog(self):
        """Parser should have usage examples in epilog"""
        parser = create_parser()
        assert parser.epilog is not None
        assert 'WORKFLOW STEPS' in parser.epilog
        assert 'EXAMPLES' in parser.epilog

    def test_help_includes_step_choices(self):
        """Help text should show available step choices"""
        parser = create_parser()
        help_text = parser.format_help()
        assert 'case' in help_text
        assert 'mesh' in help_text
        assert 'boundary' in help_text
        assert 'solver' in help_text
        assert 'post' in help_text

    def test_help_includes_profile_choices(self):
        """Help text should show available profile choices"""
        parser = create_parser()
        help_text = parser.format_help()
        assert '--profile' in help_text
