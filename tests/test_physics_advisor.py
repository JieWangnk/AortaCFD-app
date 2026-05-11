"""
Test suite for physics_advisor module.

Tests cover:
- Reynolds number estimation
- Mesh-turbulence compatibility checks
- Physics model recommendation
- LES stabilisation override in boundary_condition_setup
"""

import pytest
import sys
import math
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aortacfd_lib.physics_advisor import (
    estimate_reynolds_number,
    check_mesh_turbulence_compatibility,
    recommend_physics_model,
    log_physics_advice,
    PhysicsAdvice,
    RE_LAMINAR_SAFE,
    RE_TRANSITIONAL_UPPER,
    RANS_MAX_NON_ORTHO,
    LES_MAX_NON_ORTHO,
    LES_MAX_SKEWNESS,
)


# =============================================================================
# Reynolds Number Estimation
# =============================================================================


class TestReynoldsEstimation:
    """Test Reynolds number estimation from config."""

    def test_re_from_cardiac_output(self):
        """Test Re estimation from cardiac output."""
        config = {
            "physics": {"transport_properties": {"nu": 3.7736e-6, "rho": 1060}},
            "boundary_conditions": {"inlet": {"type": "CONSTANT", "cardiac_output": 5.0}},
        }
        Re = estimate_reynolds_number(config)
        assert Re is not None
        # 5 L/min through default 25mm aorta should give Re ~2000-3000
        assert 1000 < Re < 5000

    def test_re_from_velocity(self):
        """Test Re estimation from direct velocity."""
        config = {
            "physics": {"transport_properties": {"nu": 3.7736e-6}},
            "boundary_conditions": {"inlet": {"type": "CONSTANT", "velocity": 0.5}},
        }
        Re = estimate_reynolds_number(config)
        assert Re is not None
        # 0.5 m/s * 0.025 m / 3.77e-6 ~ 3300
        assert 3000 < Re < 4000

    def test_re_pulsatile_doubles_peak(self):
        """Test that pulsatile inlet doubles mean velocity for peak Re estimate."""
        config_steady = {
            "physics": {"transport_properties": {"nu": 3.7736e-6}},
            "boundary_conditions": {"inlet": {"type": "CONSTANT", "velocity": 0.5}},
        }
        config_pulsatile = {
            "physics": {"transport_properties": {"nu": 3.7736e-6}},
            "boundary_conditions": {"inlet": {"type": "TIMEVARYING", "velocity": 0.5}},
        }

        Re_steady = estimate_reynolds_number(config_steady)
        Re_pulsatile = estimate_reynolds_number(config_pulsatile)

        assert Re_pulsatile == pytest.approx(Re_steady * 2, rel=1e-6)

    def test_re_returns_none_without_velocity(self):
        """Test that Re returns None when no velocity info in config."""
        config = {
            "physics": {"transport_properties": {"nu": 3.7736e-6}},
            "boundary_conditions": {"inlet": {"type": "TIMEVARYING"}},
        }
        Re = estimate_reynolds_number(config)
        assert Re is None

    def test_re_with_custom_inlet_radius(self):
        """Test Re estimation with custom inlet radius."""
        config = {
            "physics": {"transport_properties": {"nu": 3.7736e-6}},
            "boundary_conditions": {"inlet": {"type": "CONSTANT", "cardiac_output": 5.0}},
        }
        # Small inlet radius -> higher velocity -> higher Re
        Re_small = estimate_reynolds_number(config, inlet_radius_m=0.005)
        Re_large = estimate_reynolds_number(config, inlet_radius_m=0.015)
        assert Re_small > Re_large

    def test_re_old_physics_format(self):
        """Test Re estimation with old physics config format."""
        config = {
            "physics": {
                "default_viscosity": 0.004,
                "default_density": 1060,
            },
            "boundary_conditions": {"inlet": {"type": "CONSTANT", "velocity": 0.5}},
        }
        Re = estimate_reynolds_number(config)
        assert Re is not None
        assert Re > 0

    def test_re_flowrate_alias(self):
        """Test that flowrate is treated as cardiac_output alias."""
        config = {
            "physics": {"transport_properties": {"nu": 3.7736e-6}},
            "boundary_conditions": {"inlet": {"type": "CONSTANT", "flowrate": 5.0}},
        }
        Re = estimate_reynolds_number(config)
        assert Re is not None


# =============================================================================
# Mesh-Turbulence Compatibility
# =============================================================================


class TestMeshTurbulenceCompatibility:
    """Test mesh quality checks for turbulence models."""

    def test_laminar_no_warnings(self):
        """Test that laminar model never generates mesh warnings."""
        config = {
            "mesh": {
                "SNAPPY_SETTINGS": {"surfaceRefinementLevels": [1, 3]},
                "boundary_layers": {"enabled": False},
            }
        }
        warnings = check_mesh_turbulence_compatibility(config, "laminar")
        assert warnings == []

    def test_rans_refinement_level_jump_warning(self):
        """Test warning for refinement level jump with RANS."""
        config = {
            "mesh": {
                "SNAPPY_SETTINGS": {"surfaceRefinementLevels": [1, 3]},
            }
        }
        warnings = check_mesh_turbulence_compatibility(config, "rans")
        assert len(warnings) >= 1
        assert "volume" in warnings[0].lower() or "refinement" in warnings[0].lower()

    def test_rans_uniform_refinement_no_warning(self):
        """Test no warning for uniform refinement levels."""
        config = {
            "mesh": {
                "SNAPPY_SETTINGS": {"surfaceRefinementLevels": [2, 2]},
            }
        }
        warnings = check_mesh_turbulence_compatibility(config, "rans")
        assert warnings == []

    def test_les_disabled_layers_warning(self):
        """Test warning when LES has boundary layers disabled."""
        config = {
            "mesh": {
                "SNAPPY_SETTINGS": {"surfaceRefinementLevels": [2, 2]},
                "boundary_layers": {"enabled": False},
            }
        }
        warnings = check_mesh_turbulence_compatibility(config, "les")
        assert any("boundary layer" in w.lower() for w in warnings)

    def test_les_few_layers_warning(self):
        """Test warning when LES has too few boundary layers."""
        config = {
            "mesh": {
                "SNAPPY_SETTINGS": {"surfaceRefinementLevels": [2, 2]},
                "boundary_layers": {"enabled": True, "num_layers": 2},
            }
        }
        warnings = check_mesh_turbulence_compatibility(config, "les")
        assert any("layer" in w.lower() for w in warnings)

    def test_rans_poor_orthogonality_from_checkmesh(self):
        """Test RANS warning when checkMesh reports poor orthogonality."""
        config = {"mesh": {"SNAPPY_SETTINGS": {"surfaceRefinementLevels": [2, 2]}}}
        metrics = {"max_non_orthogonality": 70.0, "max_skewness": 2.0}
        warnings = check_mesh_turbulence_compatibility(config, "rans", metrics)
        assert any("orthogonality" in w.lower() for w in warnings)

    def test_les_poor_skewness_from_checkmesh(self):
        """Test LES warning when checkMesh reports high skewness."""
        config = {"mesh": {"SNAPPY_SETTINGS": {"surfaceRefinementLevels": [2, 2]}}}
        metrics = {"max_non_orthogonality": 40.0, "max_skewness": 3.0}
        warnings = check_mesh_turbulence_compatibility(config, "les", metrics)
        assert any("skewness" in w.lower() for w in warnings)

    def test_good_mesh_rans_no_warnings(self):
        """Test no warnings for RANS with good mesh quality."""
        config = {"mesh": {"SNAPPY_SETTINGS": {"surfaceRefinementLevels": [2, 2]}}}
        metrics = {
            "max_non_orthogonality": 50.0,
            "max_skewness": 2.0,
            "max_aspect_ratio": 50.0,
        }
        warnings = check_mesh_turbulence_compatibility(config, "rans", metrics)
        assert warnings == []


# =============================================================================
# Physics Model Recommendation
# =============================================================================


class TestPhysicsRecommendation:
    """Test physics model recommendation logic."""

    def test_low_re_recommends_laminar(self):
        """Test that low Re recommends laminar."""
        config = {
            "physics": {
                "simulation_type": "laminar",
                "transport_properties": {"nu": 3.7736e-6},
            },
            "boundary_conditions": {"inlet": {"type": "CONSTANT", "velocity": 0.3}},
        }
        advice = recommend_physics_model(config)
        assert advice.recommended_model == "laminar"
        assert advice.estimated_re is not None
        assert advice.estimated_re < RE_LAMINAR_SAFE

    def test_rans_on_low_re_generates_warning(self):
        """Test that selecting RANS at low Re generates a warning."""
        config = {
            "physics": {
                "simulation_type": "rans",
                "transport_properties": {"nu": 3.7736e-6},
            },
            "boundary_conditions": {"inlet": {"type": "CONSTANT", "velocity": 0.3}},
        }
        advice = recommend_physics_model(config)
        assert advice.recommended_model == "laminar"
        assert len(advice.warnings) > 0
        assert any("rans" in w.lower() or "Re" in w for w in advice.warnings)

    def test_high_re_recommends_rans(self):
        """Test that high Re recommends RANS."""
        config = {
            "physics": {
                "simulation_type": "rans",
                "transport_properties": {"nu": 3.7736e-6},
            },
            "boundary_conditions": {"inlet": {"type": "CONSTANT", "velocity": 2.0}},  # High velocity
        }
        advice = recommend_physics_model(config)
        assert advice.estimated_re is not None
        assert advice.estimated_re > RE_TRANSITIONAL_UPPER
        assert advice.recommended_model == "rans"

    def test_no_velocity_info_defaults_to_laminar(self):
        """Test that missing velocity info defaults to laminar recommendation."""
        config = {
            "physics": {
                "simulation_type": "rans",
                "transport_properties": {"nu": 3.7736e-6},
            },
            "boundary_conditions": {"inlet": {"type": "TIMEVARYING"}},
        }
        advice = recommend_physics_model(config)
        assert advice.estimated_re is None
        assert advice.recommended_model == "laminar"

    def test_mesh_incompatibility_flagged(self):
        """Test that mesh incompatibility is flagged in advice."""
        config = {
            "physics": {
                "simulation_type": "rans",
                "transport_properties": {"nu": 3.7736e-6},
            },
            "boundary_conditions": {"inlet": {"type": "CONSTANT", "velocity": 2.0}},
            "mesh": {
                "SNAPPY_SETTINGS": {"surfaceRefinementLevels": [1, 3]},
            },
        }
        advice = recommend_physics_model(config)
        assert not advice.mesh_compatible
        assert len(advice.warnings) > 0

    def test_advice_repr(self):
        """Test PhysicsAdvice string representation."""
        advice = PhysicsAdvice()
        advice.estimated_re = 2500.0
        advice.warnings = ["test warning"]
        repr_str = repr(advice)
        assert "laminar" in repr_str
        assert "2500" in repr_str


# =============================================================================
# Log Physics Advice
# =============================================================================


class TestLogPhysicsAdvice:
    """Test logging of physics advice."""

    def test_no_warnings_no_log(self):
        """Test that no logging occurs when there are no warnings."""
        advice = PhysicsAdvice()
        advice.warnings = []

        with patch("aortacfd_lib.physics_advisor.logger") as mock_logger:
            log_physics_advice(advice, "laminar")
            mock_logger.warning.assert_not_called()

    def test_warnings_trigger_log(self):
        """Test that warnings are logged."""
        advice = PhysicsAdvice()
        advice.estimated_re = 2000.0
        advice.warnings = ["RANS may be unstable"]
        advice.reasoning = ["Low Re"]

        with patch("aortacfd_lib.physics_advisor.logger") as mock_logger:
            log_physics_advice(advice, "rans")
            assert mock_logger.warning.call_count > 0


# =============================================================================
# LES Stabilisation Override (boundary_condition_setup integration)
# =============================================================================


class TestLESStabilisationOverride:
    """Test LES stabilisation auto-disable in BoundaryConditionSetup."""

    def _make_bc_setup(self, sim_type, outlet_type="3EWINDKESSEL", wk_settings=None):
        """Create a minimal BoundaryConditionSetup-like object for testing."""
        from unittest.mock import MagicMock

        setup = MagicMock()
        setup.physics_settings = {"simulation_type": sim_type}
        setup.outlet_settings = {
            "type": outlet_type,
            "windkessel_settings": wk_settings or {},
        }
        setup.log = MagicMock()

        # Bind the actual method
        from aortacfd_lib.boundary_condition_setup import BoundaryConditionSetup

        setup._apply_les_stabilisation_override = BoundaryConditionSetup._apply_les_stabilisation_override.__get__(
            setup
        )
        return setup

    def test_les_disables_stabilisation(self):
        """Test that LES auto-disables stabilisation when not explicitly set."""
        setup = self._make_bc_setup("LES")
        setup._apply_les_stabilisation_override()

        wk = setup.outlet_settings["windkessel_settings"]
        assert wk["enable_stabilization"] is False

    def test_laminar_does_not_change_stabilisation(self):
        """Test that laminar does not touch stabilisation."""
        setup = self._make_bc_setup("laminar")
        setup._apply_les_stabilisation_override()

        wk = setup.outlet_settings["windkessel_settings"]
        assert "enable_stabilization" not in wk

    def test_rans_does_not_change_stabilisation(self):
        """Test that RANS does not touch stabilisation."""
        setup = self._make_bc_setup("RAS")
        setup._apply_les_stabilisation_override()

        wk = setup.outlet_settings["windkessel_settings"]
        assert "enable_stabilization" not in wk

    def test_les_respects_explicit_enable(self):
        """Test that LES does not override explicit enable_stabilization: true."""
        setup = self._make_bc_setup("LES", wk_settings={"enable_stabilization": True})
        setup._apply_les_stabilisation_override()

        wk = setup.outlet_settings["windkessel_settings"]
        # Should still be True since user explicitly set it
        assert wk["enable_stabilization"] is True
        # But should log a warning
        setup.log.warning.assert_called()

    def test_les_non_windkessel_no_change(self):
        """Test that LES with non-Windkessel outlets doesn't trigger override."""
        setup = self._make_bc_setup("LES", outlet_type="zeroGradient")
        setup._apply_les_stabilisation_override()

        wk = setup.outlet_settings["windkessel_settings"]
        assert "enable_stabilization" not in wk


# =============================================================================
# Integration: ConfigBuilder physics validation
# =============================================================================


class TestConfigBuilderPhysicsValidation:
    """Test that ConfigBuilder calls physics validation."""

    def test_validate_physics_model_called_for_rans(self):
        """Test that _validate_physics_model runs for RANS config."""
        from config.builder import ConfigBuilder

        builder = ConfigBuilder()

        # Directly test the method
        config = {
            "physics": {
                "simulation_type": "rans",
                "transport_properties": {"nu": 3.7736e-6},
            },
            "boundary_conditions": {"inlet": {"type": "CONSTANT", "velocity": 0.3}},
            "mesh": {
                "SNAPPY_SETTINGS": {"surfaceRefinementLevels": [1, 3]},
            },
        }

        # Should not raise
        builder._validate_physics_model(config)

    def test_validate_physics_model_skips_laminar(self):
        """Test that _validate_physics_model is a no-op for laminar."""
        from config.builder import ConfigBuilder

        builder = ConfigBuilder()

        config = {"physics": {"simulation_type": "laminar"}}
        # Should return immediately without doing anything
        builder._validate_physics_model(config)
