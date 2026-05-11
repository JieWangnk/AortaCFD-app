"""
Test suite for config_helper module.

Tests cover:
- BoundaryConditionsHelper class
- Configuration analysis
- Auto-completion logic
- Key parameter extraction
- Template generation
"""

import pytest
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestBoundaryConditionsHelperInit:
    """Test BoundaryConditionsHelper initialization."""

    @patch("aortacfd_lib.config_helper.Logger")
    def test_init(self, mock_logger):
        """Test initialization creates helper with defaults."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        assert helper.key_parameters is not None
        assert helper.intelligent_defaults is not None
        assert "geometry.refinement_level" in helper.key_parameters
        assert "inlet.profile" in helper.key_parameters

    @patch("aortacfd_lib.config_helper.Logger")
    def test_init_key_parameters_structure(self, mock_logger):
        """Test key parameters contain expected options."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        # Check refinement levels
        assert "coarse" in helper.key_parameters["geometry.refinement_level"]
        assert "medium" in helper.key_parameters["geometry.refinement_level"]
        assert "fine" in helper.key_parameters["geometry.refinement_level"]

        # Check inlet profiles
        assert "plug" in helper.key_parameters["inlet.profile"]
        assert "parabolic" in helper.key_parameters["inlet.profile"]
        assert "womersley" in helper.key_parameters["inlet.profile"]

    @patch("aortacfd_lib.config_helper.Logger")
    def test_init_intelligent_defaults(self, mock_logger):
        """Test intelligent defaults structure."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        assert "geometry" in helper.intelligent_defaults
        assert "inlet" in helper.intelligent_defaults
        assert "outlets" in helper.intelligent_defaults
        assert "simulation_control" in helper.intelligent_defaults


class TestAnalyzeBoundaryConditions:
    """Test analyze_boundary_conditions method."""

    @patch("aortacfd_lib.config_helper.Logger")
    def test_analyze_valid_config(self, mock_logger):
        """Test analysis of valid configuration file."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "geometry": {"refinement_level": "medium", "scale_factor": 0.001},
                "inlet": {"csv_file": "flow_data.csv", "profile": "womersley"},
                "outlets": {"type": "ZEROGRADIENT"},
                "simulation_control": {"number_of_cycles": 2},
            }

            config_file = Path(tmpdir) / "boundary_conditions.json"
            with open(config_file, "w") as f:
                json.dump(config, f)

            analysis = helper.analyze_boundary_conditions(str(config_file))

            assert "key_parameters" in analysis
            assert "missing_parameters" in analysis
            assert "suggestions" in analysis
            assert "completeness" in analysis
            assert "error" not in analysis

    @patch("aortacfd_lib.config_helper.Logger")
    def test_analyze_missing_file(self, mock_logger):
        """Test analysis with missing file."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        analysis = helper.analyze_boundary_conditions("/nonexistent/file.json")

        assert "error" in analysis

    @patch("aortacfd_lib.config_helper.Logger")
    def test_analyze_invalid_json(self, mock_logger):
        """Test analysis with invalid JSON file."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "invalid.json"
            with open(config_file, "w") as f:
                f.write("not valid json {{{")

            analysis = helper.analyze_boundary_conditions(str(config_file))

            assert "error" in analysis


class TestExtractKeyParameters:
    """Test _extract_key_parameters method."""

    @patch("aortacfd_lib.config_helper.Logger")
    def test_extract_all_parameters(self, mock_logger):
        """Test extraction of all key parameters."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        config = {
            "geometry": {"refinement_level": "fine", "scale_factor": 0.001},
            "inlet": {"profile": "womersley", "data_type": "velocity"},
            "outlets": {"type": "3EWINDKESSEL"},
            "simulation_control": {"number_of_cycles": 3},
        }

        params = helper._extract_key_parameters(config)

        assert params["refinement_level"] == "fine"
        assert params["scale_factor"] == 0.001
        assert params["inlet_profile"] == "womersley"
        assert params["inlet_data_type"] == "velocity"
        assert params["outlet_type"] == "3EWINDKESSEL"
        assert params["number_of_cycles"] == 3

    @patch("aortacfd_lib.config_helper.Logger")
    def test_extract_missing_parameters(self, mock_logger):
        """Test extraction handles missing parameters."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        config = {}

        params = helper._extract_key_parameters(config)

        assert params["refinement_level"] == "unknown"
        assert params["scale_factor"] == "missing"


class TestFindMissingParameters:
    """Test _find_missing_parameters method."""

    @patch("aortacfd_lib.config_helper.Logger")
    def test_find_all_missing(self, mock_logger):
        """Test finding missing parameters in empty config."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        missing = helper._find_missing_parameters({})

        assert "geometry.scale_factor" in missing
        assert "geometry.refinement_level" in missing
        assert "inlet.csv_file" in missing
        assert "inlet.profile" in missing
        assert "outlets.type" in missing

    @patch("aortacfd_lib.config_helper.Logger")
    def test_find_no_missing(self, mock_logger):
        """Test complete config has no missing params."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        config = {
            "geometry": {"scale_factor": 0.001, "refinement_level": "medium"},
            "inlet": {"csv_file": "flow.csv", "profile": "womersley"},
            "outlets": {"type": "ZEROGRADIENT"},
        }

        missing = helper._find_missing_parameters(config)

        assert len(missing) == 0


class TestGenerateSuggestions:
    """Test _generate_suggestions method."""

    @patch("aortacfd_lib.config_helper.Logger")
    def test_coarse_refinement_suggestion(self, mock_logger):
        """Test suggestion for coarse refinement."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        config = {"geometry": {"refinement_level": "coarse"}}

        suggestions = helper._generate_suggestions(config)

        assert any("medium" in s.lower() for s in suggestions)

    @patch("aortacfd_lib.config_helper.Logger")
    def test_plug_profile_suggestion(self, mock_logger):
        """Test suggestion for plug profile."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        config = {"inlet": {"profile": "plug"}}

        suggestions = helper._generate_suggestions(config)

        assert any("womersley" in s.lower() for s in suggestions)

    @patch("aortacfd_lib.config_helper.Logger")
    def test_womersley_profile_suggestion(self, mock_logger):
        """Test suggestion for womersley profile."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        config = {"inlet": {"profile": "womersley"}}

        suggestions = helper._generate_suggestions(config)

        assert any("viscosity" in s.lower() or "nu" in s for s in suggestions)

    @patch("aortacfd_lib.config_helper.Logger")
    def test_zerogradient_outlet_suggestion(self, mock_logger):
        """Test suggestion for zero gradient outlet."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        config = {"outlets": {"type": "ZEROGRADIENT"}}

        suggestions = helper._generate_suggestions(config)

        assert any("windkessel" in s.lower() for s in suggestions)

    @patch("aortacfd_lib.config_helper.Logger")
    def test_few_cycles_suggestion(self, mock_logger):
        """Test suggestion for too few cycles."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        config = {"simulation_control": {"number_of_cycles": 1}}

        suggestions = helper._generate_suggestions(config)

        assert any("2" in s or "cycles" in s.lower() for s in suggestions)


class TestCalculateCompleteness:
    """Test _calculate_completeness method."""

    @patch("aortacfd_lib.config_helper.Logger")
    def test_empty_config_completeness(self, mock_logger):
        """Test completeness of empty config."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        completeness = helper._calculate_completeness({})

        assert completeness == 0.0

    @patch("aortacfd_lib.config_helper.Logger")
    def test_partial_config_completeness(self, mock_logger):
        """Test completeness of partial config."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        config = {
            "geometry": {
                "scale_factor": 0.001,
                "refinement_level": "medium",
                "rotation": True,
                "target_normal": [0, 0, 1],
            }
        }

        completeness = helper._calculate_completeness(config)

        # Should have 4 parameters out of 15
        assert 20 < completeness < 40  # Approximately 26.67%


class TestAutoCompleteConfig:
    """Test auto_complete_config method."""

    @patch("aortacfd_lib.config_helper.Logger")
    def test_auto_complete_minimal(self, mock_logger):
        """Test auto-completion of minimal config."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        partial = {}

        completed = helper.auto_complete_config(partial)

        # Should have intelligent defaults
        assert "geometry" in completed
        assert "inlet" in completed
        assert "outlets" in completed
        assert "simulation_control" in completed

    @patch("aortacfd_lib.config_helper.Logger")
    def test_auto_complete_preserves_existing(self, mock_logger):
        """Test auto-completion preserves existing values."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        partial = {"geometry": {"refinement_level": "fine", "scale_factor": 0.01}}

        completed = helper.auto_complete_config(partial)

        assert completed["geometry"]["refinement_level"] == "fine"
        assert completed["geometry"]["scale_factor"] == 0.01

    @patch("aortacfd_lib.config_helper.Logger")
    def test_auto_complete_windkessel(self, mock_logger):
        """Test auto-completion adds windkessel settings."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        partial = {"outlets": {"type": "3EWINDKESSEL"}}

        completed = helper.auto_complete_config(partial)

        assert "windkessel_settings" in completed["outlets"]
        assert "systolic_pressure" in completed["outlets"]["windkessel_settings"]


class TestApplyRefinementLevelDefaults:
    """Test _apply_refinement_level_defaults method."""

    @patch("aortacfd_lib.config_helper.Logger")
    def test_coarse_refinement_defaults(self, mock_logger):
        """Test coarse refinement time step defaults."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        config = {}
        result = helper._apply_refinement_level_defaults(config, "coarse")

        assert result["simulation_control"]["initial_deltaT"] == 1e-4
        assert result["simulation_control"]["maxDeltaT"] == 5e-3

    @patch("aortacfd_lib.config_helper.Logger")
    def test_fine_refinement_defaults(self, mock_logger):
        """Test fine refinement time step defaults."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        config = {}
        result = helper._apply_refinement_level_defaults(config, "fine")

        assert result["simulation_control"]["initial_deltaT"] == 1e-6
        assert result["simulation_control"]["maxDeltaT"] == 5e-4


class TestApplyInletProfileDefaults:
    """Test _apply_inlet_profile_defaults method."""

    @patch("aortacfd_lib.config_helper.Logger")
    def test_plug_profile_defaults(self, mock_logger):
        """Test plug profile defaults."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        config = {}
        result = helper._apply_inlet_profile_defaults(config, "plug")

        assert result["inlet"]["data_type"] == "velocity"

    @patch("aortacfd_lib.config_helper.Logger")
    def test_womersley_profile_defaults(self, mock_logger):
        """Test womersley profile defaults."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        config = {}
        result = helper._apply_inlet_profile_defaults(config, "womersley")

        assert result["inlet"]["data_type"] == "velocity"


class TestAutoCalculateFlowSplit:
    """Test _auto_calculate_flow_split method."""

    @patch("aortacfd_lib.config_helper.Logger")
    def test_flow_split_calculation(self, mock_logger):
        """Test flow split auto-calculation."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        config = {}
        result = helper._auto_calculate_flow_split(config)

        flow_split = result["outlets"]["windkessel_settings"]["flow_split"]
        assert flow_split["outlet1"] == 0.25
        assert flow_split["outlet2"] == 0.25
        assert flow_split["outlet3"] == 0.25
        assert flow_split["outlet4"] == 0.25


class TestCreateTemplateConfig:
    """Test create_template_config method."""

    @patch("aortacfd_lib.config_helper.Logger")
    def test_template_creation(self, mock_logger):
        """Test template config creation."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        template = helper.create_template_config("PAT001", "flow_data.csv")

        assert template["geometry"]["refinement_level"] == "medium"
        assert template["inlet"]["csv_file"] == "flow_data.csv"
        assert template["inlet"]["profile"] == "womersley"
        assert template["outlets"]["type"] == "ZEROGRADIENT"
        assert template["simulation_control"]["number_of_cycles"] == 2

    @patch("aortacfd_lib.config_helper.Logger")
    def test_template_has_windkessel_settings(self, mock_logger):
        """Test template includes windkessel settings."""
        from aortacfd_lib.config_helper import BoundaryConditionsHelper

        helper = BoundaryConditionsHelper()

        template = helper.create_template_config("PAT001", "flow.csv")

        assert "windkessel_settings" in template["outlets"]
        assert "systolic_pressure" in template["outlets"]["windkessel_settings"]
        assert template["outlets"]["windkessel_settings"]["systolic_pressure"] == 120


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
