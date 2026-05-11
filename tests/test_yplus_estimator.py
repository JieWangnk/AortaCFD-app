"""
Comprehensive test suite for Y+ estimator module.

Tests the YPlusEstimator class for boundary layer mesh generation.
"""

import pytest
import math
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aortacfd_lib.yplus_estimator import YPlusEstimator, estimate_from_config


class TestYPlusEstimatorInitialization:
    """Test YPlusEstimator initialization and properties."""

    def test_initialization_with_blood_properties(self):
        """Test initialization with typical blood properties."""
        estimator = YPlusEstimator(density=1060.0, viscosity=0.004, flow_regime="auto")  # kg/m³  # Pa·s

        assert estimator.rho == 1060.0
        assert estimator.mu == 0.004
        assert estimator.nu == pytest.approx(0.004 / 1060.0, rel=1e-6)
        assert estimator.flow_regime == "auto"

    def test_initialization_with_water_properties(self):
        """Test initialization with water properties."""
        estimator = YPlusEstimator(density=1000.0, viscosity=0.001, flow_regime="turbulent")

        assert estimator.rho == 1000.0
        assert estimator.mu == 0.001
        assert estimator.nu == pytest.approx(1e-6, rel=1e-6)

    def test_kinematic_viscosity_calculation(self):
        """Verify kinematic viscosity is calculated correctly."""
        estimator = YPlusEstimator(density=1060.0, viscosity=0.00377)
        expected_nu = 0.00377 / 1060.0
        assert estimator.nu == pytest.approx(expected_nu, rel=1e-9)


class TestYPlusEstimation:
    """Test Y+ estimation for different flow conditions."""

    def setup_method(self):
        """Setup common estimator for blood properties."""
        self.estimator = YPlusEstimator(density=1060.0, viscosity=0.004, flow_regime="auto")

    def test_laminar_flow_estimation(self):
        """Test estimation for laminar flow (low Re)."""
        results = self.estimator.estimate_first_layer_thickness(
            target_yplus=1.0,
            mean_velocity=0.1,  # Low velocity
            characteristic_length=0.02,  # 20mm diameter
            n_layers=5,
            expansion_ratio=1.2,
        )

        # Verify all required keys present
        assert "firstLayerThickness" in results
        assert "estimated_yplus" in results
        assert "reynolds_number" in results
        assert "friction_velocity" in results
        assert "total_layer_thickness" in results
        assert "flow_regime" in results
        assert "friction_factor" in results

        # Verify flow regime detected as laminar
        assert results["flow_regime"] == "laminar"
        assert results["reynolds_number"] < 2300

        # Verify y+ is approximately target
        assert results["estimated_yplus"] == pytest.approx(1.0, rel=1e-3)

        # Verify reasonable first layer thickness
        assert results["firstLayerThickness"] > 0
        assert results["firstLayerThickness"] < 0.01  # Less than 10mm

    def test_turbulent_flow_estimation(self):
        """Test estimation for turbulent flow (high Re)."""
        results = self.estimator.estimate_first_layer_thickness(
            target_yplus=1.0,
            mean_velocity=1.0,  # Higher velocity
            characteristic_length=0.025,  # 25mm diameter
            n_layers=5,
            expansion_ratio=1.2,
        )

        # Verify flow regime detected as turbulent
        assert results["flow_regime"] == "turbulent"
        assert results["reynolds_number"] > 4000

        # Verify y+ target met
        assert results["estimated_yplus"] == pytest.approx(1.0, rel=1e-3)

        # Turbulent flow should have smaller first layer for same y+
        assert results["firstLayerThickness"] > 0

    def test_wall_function_yplus_target(self):
        """Test estimation with y+ ~ 30 for wall functions."""
        results = self.estimator.estimate_first_layer_thickness(
            target_yplus=30.0, mean_velocity=0.5, characteristic_length=0.025, n_layers=3, expansion_ratio=1.2
        )

        # y+ = 30 should give much larger first layer
        assert results["estimated_yplus"] == pytest.approx(30.0, rel=1e-3)
        assert results["firstLayerThickness"] > 1e-5  # > 0.01mm

    def test_les_yplus_target(self):
        """Test estimation with y+ < 1 for LES."""
        results = self.estimator.estimate_first_layer_thickness(
            target_yplus=0.5, mean_velocity=0.5, characteristic_length=0.025, n_layers=6, expansion_ratio=1.15
        )

        # Very small y+ should give very small first layer
        assert results["estimated_yplus"] == pytest.approx(0.5, rel=1e-3)
        assert results["firstLayerThickness"] < 1e-4  # < 0.1mm

    def test_reynolds_number_calculation(self):
        """Verify Reynolds number is calculated correctly."""
        velocity = 0.5  # m/s
        diameter = 0.025  # m

        results = self.estimator.estimate_first_layer_thickness(
            target_yplus=1.0, mean_velocity=velocity, characteristic_length=diameter, n_layers=5, expansion_ratio=1.2
        )

        expected_Re = self.estimator.rho * velocity * diameter / self.estimator.mu
        assert results["reynolds_number"] == pytest.approx(expected_Re, rel=1e-6)

    def test_friction_factor_laminar(self):
        """Test friction factor calculation for laminar flow."""
        results = self.estimator.estimate_first_layer_thickness(
            target_yplus=1.0, mean_velocity=0.1, characteristic_length=0.02, n_layers=5, expansion_ratio=1.2
        )

        # Laminar: f = 64/Re
        expected_f = 64.0 / results["reynolds_number"]
        assert results["friction_factor"] == pytest.approx(expected_f, rel=1e-6)

    def test_friction_factor_turbulent(self):
        """Test friction factor for turbulent flow (Blasius correlation)."""
        results = self.estimator.estimate_first_layer_thickness(
            target_yplus=1.0, mean_velocity=1.0, characteristic_length=0.025, n_layers=5, expansion_ratio=1.2
        )

        Re = results["reynolds_number"]
        assert Re > 4000  # Ensure turbulent

        # Blasius: f = 0.316 / Re^0.25
        if Re < 100000:
            expected_f = 0.316 / (Re**0.25)
            assert results["friction_factor"] == pytest.approx(expected_f, rel=1e-4)

    def test_total_boundary_layer_thickness(self):
        """Test total BL thickness calculation with expansion ratio."""
        n_layers = 5
        expansion_ratio = 1.2

        results = self.estimator.estimate_first_layer_thickness(
            target_yplus=1.0,
            mean_velocity=0.5,
            characteristic_length=0.025,
            n_layers=n_layers,
            expansion_ratio=expansion_ratio,
        )

        delta_y1 = results["firstLayerThickness"]
        # Total = Δy₁ × (r^n - 1) / (r - 1)
        expected_total = delta_y1 * (expansion_ratio**n_layers - 1) / (expansion_ratio - 1)

        assert results["total_layer_thickness"] == pytest.approx(expected_total, rel=1e-6)

    def test_uniform_layers_no_expansion(self):
        """Test with expansion ratio = 1.0 (uniform layers)."""
        n_layers = 5

        results = self.estimator.estimate_first_layer_thickness(
            target_yplus=1.0, mean_velocity=0.5, characteristic_length=0.025, n_layers=n_layers, expansion_ratio=1.0
        )

        # With r=1, total = n × Δy₁
        expected_total = results["firstLayerThickness"] * n_layers
        assert results["total_layer_thickness"] == pytest.approx(expected_total, rel=1e-6)


class TestFlowRegimeDetection:
    """Test automatic flow regime detection."""

    def setup_method(self):
        self.estimator = YPlusEstimator(density=1060.0, viscosity=0.004, flow_regime="auto")

    def test_laminar_regime_detection(self):
        """Test laminar detection for Re < 2300."""
        results = self.estimator.estimate_first_layer_thickness(
            target_yplus=1.0, mean_velocity=0.15, characteristic_length=0.02, n_layers=5, expansion_ratio=1.2
        )

        assert results["reynolds_number"] < 2300
        assert results["flow_regime"] == "laminar"

    def test_turbulent_regime_detection(self):
        """Test turbulent detection for Re > 4000."""
        results = self.estimator.estimate_first_layer_thickness(
            target_yplus=1.0, mean_velocity=1.0, characteristic_length=0.03, n_layers=5, expansion_ratio=1.2
        )

        assert results["reynolds_number"] > 4000
        assert results["flow_regime"] == "turbulent"

    def test_transitional_regime_warning(self):
        """Test that transitional regime (2300 < Re < 4000) triggers warning."""
        # Create conditions for transitional Re
        results = self.estimator.estimate_first_layer_thickness(
            target_yplus=1.0, mean_velocity=0.25, characteristic_length=0.025, n_layers=5, expansion_ratio=1.2
        )

        Re = results["reynolds_number"]
        if 2300 < Re < 4000:
            assert results["flow_regime"] == "transitional"

    def test_forced_laminar_regime(self):
        """Test forcing laminar regime regardless of Re."""
        estimator_forced = YPlusEstimator(density=1060.0, viscosity=0.004, flow_regime="laminar")

        # Use high velocity that would normally be turbulent
        results = estimator_forced.estimate_first_layer_thickness(
            target_yplus=1.0, mean_velocity=2.0, characteristic_length=0.03, n_layers=5, expansion_ratio=1.2
        )

        # Should still be treated as laminar
        assert results["flow_regime"] == "laminar"
        # f = 64/Re for laminar
        expected_f = 64.0 / results["reynolds_number"]
        assert results["friction_factor"] == pytest.approx(expected_f, rel=1e-6)


class TestValidationWarnings:
    """Test validation and warning system."""

    def setup_method(self):
        self.estimator = YPlusEstimator(density=1060.0, viscosity=0.004, flow_regime="auto")

    def test_bl_thickness_too_large_warning(self):
        """Test warning when BL is > 50% of vessel diameter."""
        # Create large BL thickness
        validation = self.estimator.validate_settings(
            first_layer_thickness=0.001,
            total_layer_thickness=0.015,  # 15mm BL
            characteristic_length=0.020,  # 20mm diameter
            solver_type="RANS",
            reynolds_number=5000,
        )

        # BL is 75% of diameter - should warn
        assert len(validation["warnings"]) > 0
        assert any("boundary layer thickness" in w.lower() for w in validation["warnings"])

    def test_laminar_solver_with_turbulent_re_warning(self):
        """Test warning when using laminar solver for turbulent Re."""
        validation = self.estimator.validate_settings(
            first_layer_thickness=1e-4,
            total_layer_thickness=0.001,
            characteristic_length=0.025,
            solver_type="laminar",
            reynolds_number=10000,  # Clearly turbulent
        )

        assert len(validation["warnings"]) > 0
        assert any("laminar solver" in w.lower() and "turbulent" in w.lower() for w in validation["warnings"])

    def test_turbulent_solver_with_laminar_re_warning(self):
        """Test warning when using RANS/LES for laminar Re."""
        validation = self.estimator.validate_settings(
            first_layer_thickness=1e-4,
            total_layer_thickness=0.001,
            characteristic_length=0.025,
            solver_type="RANS",
            reynolds_number=1500,  # Clearly laminar
        )

        assert len(validation["warnings"]) > 0
        assert any("rans" in w.lower() and "laminar" in w.lower() for w in validation["warnings"])

    def test_very_small_first_layer_warning(self):
        """Test warning for first layer < 0.01mm."""
        validation = self.estimator.validate_settings(
            first_layer_thickness=5e-6,  # 5 microns
            total_layer_thickness=0.0001,
            characteristic_length=0.025,
            solver_type="LES",
            reynolds_number=5000,
        )

        assert len(validation["warnings"]) > 0
        assert any("very small" in w.lower() for w in validation["warnings"])
        assert len(validation["recommendations"]) > 0

    def test_large_first_layer_warning(self):
        """Test warning for first layer > 1mm."""
        validation = self.estimator.validate_settings(
            first_layer_thickness=0.002,  # 2mm
            total_layer_thickness=0.02,
            characteristic_length=0.025,
            solver_type="RANS",
            reynolds_number=5000,
        )

        assert len(validation["warnings"]) > 0
        assert any("large" in w.lower() for w in validation["warnings"])

    def test_no_warnings_for_good_settings(self):
        """Test no warnings for reasonable settings."""
        validation = self.estimator.validate_settings(
            first_layer_thickness=1e-4,  # 0.1mm - reasonable
            total_layer_thickness=0.001,  # 1mm - reasonable
            characteristic_length=0.025,  # 25mm diameter
            solver_type="RANS",
            reynolds_number=5000,  # Turbulent
        )

        # Should have minimal or no warnings
        assert len(validation["warnings"]) == 0


class TestEstimateFromConfig:
    """Test convenience function for config-based estimation."""

    def test_estimate_from_valid_config(self):
        """Test estimation from properly formatted config."""
        config = {
            "physics": {"blood_density": 1060.0, "blood_viscosity": 0.004},
            "simulation_settings": {"solver_type": "RANS"},
            "estimation_params": {"characteristic_velocity": 0.5, "characteristic_length": 0.025},
            "mesh": {"SNAPPY_SETTINGS": {"addLayer": 5, "expansionRatio": 1.2}},
        }

        results = estimate_from_config(config, target_yplus=1.0)

        assert "firstLayerThickness" in results
        assert "estimated_yplus" in results
        assert results["estimated_yplus"] == pytest.approx(1.0, rel=1e-3)

    def test_estimate_with_minimal_config(self):
        """Test estimation with minimal config (uses defaults)."""
        config = {"physics": {"blood_density": 1060.0, "blood_viscosity": 0.004}}

        # Should use default values
        results = estimate_from_config(config, target_yplus=1.0)

        assert "firstLayerThickness" in results
        assert results["firstLayerThickness"] > 0


class TestPrintReport:
    """Test print_report method."""

    def setup_method(self):
        self.estimator = YPlusEstimator(density=1060.0, viscosity=0.004, flow_regime="auto")

    def test_print_report_without_characteristic_length(self, capsys):
        """Test print_report without characteristic_length (no validation)."""
        results = self.estimator.estimate_first_layer_thickness(
            target_yplus=1.0, mean_velocity=0.5, characteristic_length=0.025, n_layers=5, expansion_ratio=1.2
        )

        self.estimator.print_report(
            results=results,
            target_yplus=1.0,
            n_layers=5,
            expansion_ratio=1.2,
            solver_type="RANS",
            characteristic_length=None,
        )

        captured = capsys.readouterr()
        assert "Y+ ESTIMATOR RESULTS" in captured.out
        assert "Target y+:" in captured.out
        assert "RECOMMENDED MESH SETTINGS" in captured.out
        assert "firstLayerThickness" in captured.out

    def test_print_report_with_characteristic_length(self, capsys):
        """Test print_report with characteristic_length (runs validation)."""
        results = self.estimator.estimate_first_layer_thickness(
            target_yplus=1.0, mean_velocity=0.5, characteristic_length=0.025, n_layers=5, expansion_ratio=1.2
        )

        self.estimator.print_report(
            results=results,
            target_yplus=1.0,
            n_layers=5,
            expansion_ratio=1.2,
            solver_type="RANS",
            characteristic_length=0.025,
        )

        captured = capsys.readouterr()
        assert "Y+ ESTIMATOR RESULTS" in captured.out
        assert "Reynolds number" in captured.out
        # Should have validation output
        assert "Settings appear reasonable" in captured.out or "WARNINGS" in captured.out

    def test_print_report_with_warnings(self, capsys):
        """Test print_report when validation generates warnings."""
        results = self.estimator.estimate_first_layer_thickness(
            target_yplus=30.0,  # Wall functions y+
            mean_velocity=0.5,
            characteristic_length=0.025,
            n_layers=5,
            expansion_ratio=1.2,
        )

        # Use laminar solver with turbulent Re to trigger warning
        self.estimator.print_report(
            results=results,
            target_yplus=30.0,
            n_layers=5,
            expansion_ratio=1.2,
            solver_type="laminar",
            characteristic_length=0.025,
        )

        captured = capsys.readouterr()
        assert "WARNINGS" in captured.out

    def test_print_report_with_recommendations(self, capsys):
        """Test print_report when validation provides recommendations."""
        results = self.estimator.estimate_first_layer_thickness(
            target_yplus=0.1,  # Very small y+ target
            mean_velocity=0.5,
            characteristic_length=0.025,
            n_layers=5,
            expansion_ratio=1.2,
        )

        self.estimator.print_report(
            results=results,
            target_yplus=0.1,
            n_layers=5,
            expansion_ratio=1.2,
            solver_type="LES",
            characteristic_length=0.025,
        )

        captured = capsys.readouterr()
        assert "Y+ ESTIMATOR RESULTS" in captured.out
        # May have recommendations for very small first layer

    def test_print_report_shows_friction_info(self, capsys):
        """Test that print_report shows friction factor and velocity."""
        results = self.estimator.estimate_first_layer_thickness(
            target_yplus=1.0, mean_velocity=0.5, characteristic_length=0.025, n_layers=5, expansion_ratio=1.2
        )

        self.estimator.print_report(
            results=results,
            target_yplus=1.0,
            n_layers=5,
            expansion_ratio=1.2,
            solver_type="RANS",
            characteristic_length=0.025,
        )

        captured = capsys.readouterr()
        assert "Friction factor" in captured.out
        assert "Friction velocity" in captured.out


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def setup_method(self):
        self.estimator = YPlusEstimator(density=1060.0, viscosity=0.004, flow_regime="auto")

    def test_very_high_reynolds_number(self):
        """Test estimation for very high Re (> 100,000)."""
        results = self.estimator.estimate_first_layer_thickness(
            target_yplus=30.0,
            mean_velocity=10.0,  # Very high velocity
            characteristic_length=0.08,  # Larger diameter
            n_layers=3,
            expansion_ratio=1.2,
        )

        assert results["reynolds_number"] > 100000
        # Should use Prandtl-Karman correlation
        Re = results["reynolds_number"]
        expected_f = 0.0032 + 0.221 / (Re**0.237)
        assert results["friction_factor"] == pytest.approx(expected_f, rel=1e-4)

    def test_multiple_layers_different_expansions(self):
        """Test total thickness with various expansion ratios."""
        target_yplus = 1.0
        velocity = 0.5
        diameter = 0.025
        n_layers = 5

        expansions = [1.1, 1.2, 1.3, 1.5]
        total_thicknesses = []

        for exp_ratio in expansions:
            results = self.estimator.estimate_first_layer_thickness(
                target_yplus=target_yplus,
                mean_velocity=velocity,
                characteristic_length=diameter,
                n_layers=n_layers,
                expansion_ratio=exp_ratio,
            )
            total_thicknesses.append(results["total_layer_thickness"])

        # Higher expansion ratio should give larger total thickness
        for i in range(len(total_thicknesses) - 1):
            assert total_thicknesses[i] < total_thicknesses[i + 1]

    def test_consistent_results_for_same_inputs(self):
        """Test that same inputs give same results (deterministic)."""
        params = {
            "target_yplus": 1.0,
            "mean_velocity": 0.5,
            "characteristic_length": 0.025,
            "n_layers": 5,
            "expansion_ratio": 1.2,
        }

        results1 = self.estimator.estimate_first_layer_thickness(**params)
        results2 = self.estimator.estimate_first_layer_thickness(**params)

        assert results1["firstLayerThickness"] == results2["firstLayerThickness"]
        assert results1["estimated_yplus"] == results2["estimated_yplus"]
        assert results1["reynolds_number"] == results2["reynolds_number"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
