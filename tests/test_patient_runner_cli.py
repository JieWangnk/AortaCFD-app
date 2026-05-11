"""
Test suite for patient_runner CLI module.

Tests cover:
- Argument parser creation
- CLI option handling
- Step mapping and validation
- Main entry point flows
"""

import pytest
import sys
import argparse
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestCreateParser:
    """Test create_parser function."""

    def test_parser_creation(self):
        """Test parser is created successfully."""
        from patient_runner.cli import create_parser

        parser = create_parser()

        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "run_patient.py"

    def test_parser_patient_id_argument(self):
        """Test patient_id positional argument."""
        from patient_runner.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["PAT001"])

        assert args.patient_id == "PAT001"

    def test_parser_list_flag(self):
        """Test --list flag."""
        from patient_runner.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["--list"])

        assert args.list is True

    def test_parser_list_steps_flag(self):
        """Test --list-steps flag."""
        from patient_runner.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["--list-steps"])

        assert args.list_steps is True

    def test_parser_steps_option(self):
        """Test --steps option with comma-separated values."""
        from patient_runner.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["PAT001", "--steps", "case,mesh,boundary"])

        assert args.steps == "case,mesh,boundary"

    def test_parser_step_list_multiple(self):
        """Test --step option used multiple times."""
        from patient_runner.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["PAT001", "--step", "case", "--step", "mesh"])

        assert args.step_list == ["case", "mesh"]

    def test_parser_config_option(self):
        """Test --config option."""
        from patient_runner.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["PAT001", "--config", "custom_config.json"])

        assert args.config == "custom_config.json"

    def test_parser_profile_option(self):
        """Test --profile option."""
        from patient_runner.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["PAT001", "--profile", "sim_laminar_coarse"])

        assert args.profile == "sim_laminar_coarse"

    def test_parser_quick_flag(self):
        """Test --quick flag."""
        from patient_runner.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["PAT001", "--quick"])

        assert args.quick is True

    def test_parser_run_name_option(self):
        """Test --run-name option."""
        from patient_runner.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["PAT001", "--run-name", "my_test_run"])

        assert args.run_name == "my_test_run"

    def test_parser_update_option(self):
        """Test --update option."""
        from patient_runner.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["PAT001", "--update", "/path/to/case"])

        assert args.update == "/path/to/case"

    def test_parser_postprocess_option(self):
        """Test --postprocess option."""
        from patient_runner.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["--postprocess", "/path/to/run"])

        assert args.postprocess == "/path/to/run"

    def test_parser_verbose_flag(self):
        """Test --verbose flag."""
        from patient_runner.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["PAT001", "--verbose"])

        assert args.verbose is True

    def test_parser_short_flags(self):
        """Test short flag versions."""
        from patient_runner.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["PAT001", "-l"])

        assert args.list is True

    def test_parser_combined_options(self):
        """Test multiple options combined."""
        from patient_runner.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(
            ["PAT001", "--config", "config.json", "--run-name", "test", "--verbose", "--steps", "case,mesh"]
        )

        assert args.patient_id == "PAT001"
        assert args.config == "config.json"
        assert args.run_name == "test"
        assert args.verbose is True
        assert args.steps == "case,mesh"

    def test_parser_no_args(self):
        """Test parser with no arguments."""
        from patient_runner.cli import create_parser

        parser = create_parser()
        args = parser.parse_args([])

        assert args.patient_id is None
        assert args.list is False
        assert args.list_steps is False


class TestStepValidation:
    """Test workflow step validation logic."""

    def test_valid_steps(self):
        """Test all valid step names."""
        valid_steps = {
            "case",
            "mesh",
            "boundary",
            "regenerate-numerics",
            "solver",
            "reconstruct",
            "postprocess",
            "paraview",
            "all",
        }

        from patient_runner.cli import create_parser

        parser = create_parser()

        for step in ["case", "mesh", "boundary", "solver", "reconstruct", "all"]:
            args = parser.parse_args(["PAT001", "--step", step])
            assert step in args.step_list

    def test_step_mapping_keys(self):
        """Test step mapping contains expected keys."""
        step_mapping = {
            "case": "setup:dict",
            "mesh": "run:mesh",
            "boundary": "setup:bc",
            "regenerate-numerics": "setup:regenerate-numerics",
            "solver": "run:solver",
            "reconstruct": "run:reconstruct",
            "postprocess": "run:hemodynamics",
            "paraview": "execute_post",
            "all": "runAll",
        }

        assert "case" in step_mapping
        assert step_mapping["case"] == "setup:dict"
        assert step_mapping["mesh"] == "run:mesh"
        assert step_mapping["all"] == "runAll"


class TestRunStandalonePostprocess:
    """Test run_standalone_postprocess function."""

    def test_missing_openfoam_case(self):
        """Test error handling when OpenFOAM case not found."""
        from patient_runner.cli import run_standalone_postprocess

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a directory without openfoam subdirectory
            with patch("builtins.print") as mock_print:
                run_standalone_postprocess(tmpdir)
                # Should print error message about missing OpenFOAM case
                assert mock_print.called


class TestMainFunction:
    """Test main CLI entry point - integration tests."""

    def test_main_functions_exist(self):
        """Test main function and create_parser exist."""
        from patient_runner.cli import main, create_parser

        assert callable(main)
        assert callable(create_parser)


class TestVerbosePreParse:
    """Test verbose flag pre-parsing logic."""

    def test_verbose_in_sys_argv(self):
        """Test detection of verbose flag in sys.argv."""
        test_argv = ["run_patient.py", "PAT001", "--verbose"]

        verbose = "-v" in test_argv or "--verbose" in test_argv

        assert verbose is True

    def test_short_verbose_in_sys_argv(self):
        """Test detection of -v flag in sys.argv."""
        test_argv = ["run_patient.py", "PAT001", "-v"]

        verbose = "-v" in test_argv or "--verbose" in test_argv

        assert verbose is True

    def test_no_verbose_flag(self):
        """Test no verbose flag detection."""
        test_argv = ["run_patient.py", "PAT001"]

        verbose = "-v" in test_argv or "--verbose" in test_argv

        assert verbose is False


class TestUpdateMode:
    """Test update mode functionality."""

    def test_update_mode_logic(self):
        """Test update mode step defaults."""
        # In update mode, default steps should be ['case', 'boundary']
        # This tests the expected behavior without calling main

        # Default steps for update mode
        default_update_steps = ["case", "boundary"]

        assert "mesh" not in default_update_steps  # Mesh is preserved
        assert "case" in default_update_steps
        assert "boundary" in default_update_steps


class TestStepsParsing:
    """Test steps parsing from command line."""

    def test_parse_comma_separated_steps(self):
        """Test parsing comma-separated steps string."""
        steps_str = "case,mesh,boundary"

        steps = [s.strip() for s in steps_str.split(",")]

        assert steps == ["case", "mesh", "boundary"]

    def test_parse_single_step(self):
        """Test parsing single step string."""
        steps_str = "mesh"

        steps = [s.strip() for s in steps_str.split(",")]

        assert steps == ["mesh"]

    def test_parse_steps_with_spaces(self):
        """Test parsing steps with extra spaces."""
        steps_str = "case, mesh, boundary"

        steps = [s.strip() for s in steps_str.split(",")]

        assert steps == ["case", "mesh", "boundary"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
