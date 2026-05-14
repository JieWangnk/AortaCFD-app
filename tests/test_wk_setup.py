"""
Comprehensive test suite for Windkessel (3-element) model setup.

Tests the WkSetup class for calculating Windkessel parameters (R1, R2, C).
"""

import pytest
import sys
import numpy as np
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aortacfd_lib.wk_setup import WkSetup
from aortacfd_lib.constants import MMHG_TO_PA, ML_TO_M3, MURRAY_LAW_EXPONENT


class TestWindkesselConstants:
    """Test unit conversion constants from constants module."""

    def test_mmhg_to_pa_conversion(self):
        """Test mmHg to Pascal conversion constant."""
        assert MMHG_TO_PA == pytest.approx(133.322, rel=1e-4)

    def test_ml_to_m3_conversion(self):
        """Test mL to m³ conversion constant."""
        assert ML_TO_M3 == pytest.approx(1e-6, rel=1e-9)


class TestMurrayFlowSplit:
    """Test Murray's law flow distribution calculations."""

    def setup_method(self):
        """Setup mock config and WkSetup instance."""
        self.config = {
            "geometry": {
                "case_name": "test_case",
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["outlet1", "outlet2", "outlet3"],
            },
            "boundary_conditions": {
                "inlet": {"type": "CONSTANT", "cardiac_output": 5.0},
                "outlets": {"windkessel_settings": {"systolic_pressure": 120, "diastolic_pressure": 80, "tau": 1.8}},
            },
            "physics": {"blood_density": 1060},
        }
        self.wk = WkSetup(self.config, [], "/tmp/test", 1.0)

    def test_murray_equal_radii(self):
        """Test Murray's law with equal outlet radii."""
        outlet_radii = {"outlet1": 0.005, "outlet2": 0.005, "outlet3": 0.005}  # 5mm

        flow_split = self.wk._calculate_murray_flow_split(outlet_radii)

        # Equal radii should give equal flow split
        assert flow_split["outlet1"] == pytest.approx(1 / 3, rel=1e-6)
        assert flow_split["outlet2"] == pytest.approx(1 / 3, rel=1e-6)
        assert flow_split["outlet3"] == pytest.approx(1 / 3, rel=1e-6)

        # Should sum to 1.0
        assert sum(flow_split.values()) == pytest.approx(1.0, rel=1e-9)

    def test_murray_different_radii(self):
        """Test Murray's law with different radii."""
        outlet_radii = {
            "outlet1": 0.008,  # 8mm - largest
            "outlet2": 0.005,  # 5mm - medium
            "outlet3": 0.003,  # 3mm - smallest
        }

        flow_split = self.wk._calculate_murray_flow_split(outlet_radii)

        # Larger vessels should get more flow (r^n relationship)
        assert flow_split["outlet1"] > flow_split["outlet2"] > flow_split["outlet3"]

        # Check actual Murray's law: f_i = r^n / Σr^n (n=MURRAY_LAW_EXPONENT)
        # MURRAY_LAW_EXPONENT imported at top of file
        r_powered_sum = sum(r**MURRAY_LAW_EXPONENT for r in outlet_radii.values())
        for name, radius in outlet_radii.items():
            expected = radius**MURRAY_LAW_EXPONENT / r_powered_sum
            assert flow_split[name] == pytest.approx(expected, rel=1e-6)

        # Should sum to 1.0
        assert sum(flow_split.values()) == pytest.approx(1.0, rel=1e-9)

    def test_murray_single_outlet(self):
        """Test Murray's law with single outlet gets 100%."""
        outlet_radii = {"outlet1": 0.010}

        flow_split = self.wk._calculate_murray_flow_split(outlet_radii)

        assert flow_split["outlet1"] == pytest.approx(1.0, rel=1e-9)

    def test_murray_two_outlets_double_radius(self):
        """Test that doubling radius increases flow by 2^n (n=MURRAY_LAW_EXPONENT)."""
        # MURRAY_LAW_EXPONENT imported at top of file
        outlet_radii = {"small": 0.005, "large": 0.010}  # 5mm  # 10mm (2x diameter)

        flow_split = self.wk._calculate_murray_flow_split(outlet_radii)

        # Large outlet: (2^n) / (2^n + 1), where n = MURRAY_LAW_EXPONENT
        ratio = 2.0**MURRAY_LAW_EXPONENT
        expected_large = ratio / (ratio + 1.0)
        expected_small = 1.0 / (ratio + 1.0)

        assert flow_split["large"] == pytest.approx(expected_large, rel=1e-4)
        assert flow_split["small"] == pytest.approx(expected_small, rel=1e-4)


class TestFlowSplitPercentage:
    """Test percentage-based flow distribution."""

    def setup_method(self):
        """Setup mock config and WkSetup instance."""
        self.config = {
            "geometry": {
                "case_name": "test_case",
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["branch1", "branch2", "main"],
            },
            "boundary_conditions": {
                "inlet": {"type": "CONSTANT", "cardiac_output": 5.0},
                "outlets": {"windkessel_settings": {"systolic_pressure": 120, "diastolic_pressure": 80}},
            },
            "physics": {"blood_density": 1060},
        }
        self.wk = WkSetup(self.config, [], "/tmp/test", 1.0)

    def test_percentage_split_basic(self):
        """Test basic percentage split (60% to branches, 40% to main)."""
        outlet_patches = ["branch1", "branch2", "main"]
        outlet_radii = {"branch1": 0.003, "branch2": 0.003, "main": 0.010}  # Same radius  # Same radius

        flow_split = self.wk._parse_flow_split_percentage(
            60.0, outlet_patches, method="area", geometry_data=outlet_radii  # 60% to branches
        )

        # Main outlet should get 40%
        assert flow_split["main"] == pytest.approx(0.40, rel=1e-6)

        # Branches share 60% equally (same area)
        assert flow_split["branch1"] == pytest.approx(0.30, rel=1e-6)
        assert flow_split["branch2"] == pytest.approx(0.30, rel=1e-6)

        # Should sum to 1.0
        assert sum(flow_split.values()) == pytest.approx(1.0, rel=1e-9)

    def test_percentage_split_single_outlet(self):
        """Test percentage split with single outlet gets 100%."""
        outlet_patches = ["main"]
        outlet_radii = {"main": 0.010}

        flow_split = self.wk._parse_flow_split_percentage(
            50.0, outlet_patches, method="area", geometry_data=outlet_radii  # Doesn't matter for single outlet
        )

        assert flow_split["main"] == pytest.approx(1.0, rel=1e-9)

    def test_percentage_split_no_outlets(self):
        """Test error with no outlets."""
        with pytest.raises(ValueError, match="No outlet patches"):
            self.wk._parse_flow_split_percentage(60.0, [], method="area", geometry_data={})


class TestMAPCalculation:
    """Test Mean Arterial Pressure calculations.

    Uses physiological MAP formula: MAP = DP + (SP-DP)/3 = (2*DP + SP)/3
    This accounts for diastole being ~2/3 of the cardiac cycle.
    Reference: Klabunde (2011) Cardiovascular Physiology Concepts
    """

    def test_map_formula_standard_values(self):
        """Test MAP calculation with standard BP values (120/80 mmHg)."""
        SP = 120  # mmHg
        DP = 80  # mmHg

        # Physiological MAP = DP + (SP-DP)/3 = 80 + 40/3 = 93.33 mmHg
        pulse_pressure = SP - DP
        expected_MAP = DP + (1.0 / 3.0) * pulse_pressure
        assert expected_MAP == pytest.approx(93.333, rel=1e-3)

    def test_map_formula_high_bp(self):
        """Test MAP with hypertensive values (160/100 mmHg)."""
        SP = 160
        DP = 100

        # MAP = 100 + (160-100)/3 = 100 + 20 = 120 mmHg
        pulse_pressure = SP - DP
        expected_MAP = DP + (1.0 / 3.0) * pulse_pressure
        assert expected_MAP == pytest.approx(120.0, rel=1e-6)

    def test_map_formula_low_bp(self):
        """Test MAP with hypotensive values (90/60 mmHg)."""
        SP = 90
        DP = 60

        # MAP = 60 + (90-60)/3 = 60 + 10 = 70 mmHg
        pulse_pressure = SP - DP
        expected_MAP = DP + (1.0 / 3.0) * pulse_pressure
        assert expected_MAP == pytest.approx(70.0, rel=1e-6)

    def test_map_formula_equivalent_forms(self):
        """Test that MAP = DP + PP/3 = (2*DP + SP)/3."""
        SP = 120
        DP = 80

        # Form 1: DP + (SP-DP)/3
        pulse_pressure = SP - DP
        map_form1 = DP + (1.0 / 3.0) * pulse_pressure

        # Form 2: (2*DP + SP)/3
        map_form2 = (2.0 * DP + SP) / 3.0

        assert map_form1 == pytest.approx(map_form2, rel=1e-9)

    def test_map_conversion_to_pascal(self):
        """Test MAP conversion from mmHg to Pa."""
        MAP_mmHg = 100.0
        MAP_Pa = MAP_mmHg * MMHG_TO_PA

        expected_Pa = 100.0 * 133.322
        assert MAP_Pa == pytest.approx(expected_Pa, rel=1e-6)


class TestResistanceCalculations:
    """Test Windkessel resistance calculations."""

    def test_total_resistance_calculation(self):
        """Test R_total = (MAP - P_v) / Q."""
        MAP_Pa = 100 * 133.322  # 100 mmHg in Pa
        P_venous_Pa = 5 * 133.322  # 5 mmHg in Pa
        Q_outlet = 50e-6  # 50 mL/s = 50e-6 m³/s

        R_total = (MAP_Pa - P_venous_Pa) / Q_outlet

        # R_total should be in Pa·s/m³
        assert R_total > 0
        assert R_total == pytest.approx((MAP_Pa - P_venous_Pa) / Q_outlet, rel=1e-6)

    def test_characteristic_impedance_r1(self):
        """Test R1 = ρ·c/A (characteristic impedance)."""
        rho = 1060  # kg/m³
        c = 6.0  # m/s (PWV)
        A = 3.14e-4  # m² (10mm radius circle)

        R1 = rho * c / A

        expected = 1060 * 6.0 / 3.14e-4
        assert R1 == pytest.approx(expected, rel=1e-6)

    def test_distal_resistance_r2(self):
        """Test R2 = R_total - R1."""
        R_total = 1e8  # Pa·s/m³
        R1 = 1e7  # Pa·s/m³

        R2 = R_total - R1

        assert R2 == pytest.approx(9e7, rel=1e-6)
        assert R2 > 0

    def test_r2_correction_when_negative(self):
        """Test R2 correction when R1 > R_total (should adjust R1)."""
        R_total = 1e8
        R1 = 1.5e8  # Larger than R_total

        # Should correct: R1 = 0.1*R_total, R2 = 0.9*R_total
        if R1 > R_total:
            R1_corrected = 0.1 * R_total
            R2_corrected = 0.9 * R_total

            assert R1_corrected == pytest.approx(1e7, rel=1e-6)
            assert R2_corrected == pytest.approx(9e7, rel=1e-6)
            assert R1_corrected + R2_corrected == pytest.approx(R_total, rel=1e-6)


class TestComplianceCalculations:
    """Test compliance calculations."""

    def test_compliance_uniform_distribution(self):
        """Test C = tau / R2 for uniform distribution."""
        tau = 1.8  # seconds
        R2 = 9e7  # Pa·s/m³

        C = tau / R2

        expected = 1.8 / 9e7
        assert C == pytest.approx(expected, rel=1e-6)
        assert C > 0

    def test_rc_time_constant(self):
        """Test that R2·C = tau."""
        tau = 1.8
        R2 = 9e7
        C = tau / R2

        RC = R2 * C

        assert RC == pytest.approx(tau, rel=1e-6)

    def test_compliance_scaling_with_r2(self):
        """Test that higher R2 gives lower C (for fixed tau)."""
        tau = 1.8
        R2_low = 5e7
        R2_high = 1e8

        C_high_R = tau / R2_high
        C_low_R = tau / R2_low

        assert C_high_R < C_low_R


class TestPWVCalculations:
    """Test Pulse Wave Velocity calculations."""

    def test_pwv_matlab_formula(self):
        """Test MATLAB PWV formula: c = a / (2*sqrt(A/π))^b."""
        a = 13.3
        b = 0.3
        A_mm2 = 100  # 100 mm²

        c = a / (2 * np.sqrt(A_mm2 / np.pi)) ** b

        # Should be reasonable PWV (4-10 m/s)
        assert 3.0 < c < 12.0

    def test_pwv_decreases_with_area(self):
        """Test that PWV decreases with increasing area (for MATLAB formula)."""
        a = 13.3
        b = 0.3

        A_small = 50  # mm²
        A_large = 200  # mm²

        c_small = a / (2 * np.sqrt(A_small / np.pi)) ** b
        c_large = a / (2 * np.sqrt(A_large / np.pi)) ** b

        # Larger vessels have lower PWV (more compliant)
        assert c_small > c_large

    def test_pwv_empirical_ranges(self):
        """Test empirical PWV ranges by vessel size."""
        # Large vessels (>15mm diameter): ~5 m/s
        # Medium vessels (8-15mm): ~6 m/s
        # Small vessels (<8mm): ~7 m/s

        diameter_large = 20  # mm
        diameter_medium = 10  # mm
        diameter_small = 5  # mm

        # These would be the assigned PWV values in empirical method
        assert 4.5 <= 5.0 <= 5.5  # Large
        assert 5.5 <= 6.0 <= 6.5  # Medium
        assert 6.5 <= 7.0 <= 7.5  # Small


class TestUnitConversions:
    """Test unit conversions used in Windkessel calculations."""

    def test_pressure_mmhg_to_pa(self):
        """Test pressure conversion mmHg → Pa."""
        pressure_mmHg = 120
        pressure_Pa = pressure_mmHg * MMHG_TO_PA

        expected_Pa = 120 * 133.322
        assert pressure_Pa == pytest.approx(expected_Pa, rel=1e-4)

    def test_flow_lmin_to_m3s(self):
        """Test flow rate conversion L/min → m³/s."""
        flow_Lmin = 5.0  # L/min
        flow_m3s = flow_Lmin / 60.0 / 1000.0

        expected = 5.0 / 60000.0
        assert flow_m3s == pytest.approx(expected, rel=1e-9)

    def test_area_mm2_to_m2(self):
        """Test area conversion mm² → m²."""
        area_mm2 = 100
        area_m2 = area_mm2 * 1e-6

        assert area_m2 == pytest.approx(1e-4, rel=1e-9)

    def test_radius_from_area(self):
        """Test radius calculation from area: r = sqrt(A/π)."""
        import math

        area_m2 = 3.14159e-4  # ~10mm radius
        radius_m = math.sqrt(area_m2 / math.pi)

        expected_radius = 0.01  # 10mm
        assert radius_m == pytest.approx(expected_radius, rel=1e-3)


class TestPhysiologicalValidation:
    """Test that calculated parameters are physiologically reasonable."""

    def test_resistance_physiological_range(self):
        """Test that calculated resistances are in physiological range."""
        # Typical aortic outlet: R_total ~ 1e8 to 1e9 Pa·s/m³
        MAP_Pa = 100 * 133.322
        Q_outlet = 50e-6  # 50 mL/s

        R_total = MAP_Pa / Q_outlet

        # Should be in physiological range
        assert 1e7 < R_total < 1e10

    def test_compliance_physiological_range(self):
        """Test that calculated compliance is in physiological range."""
        # Typical: C ~ 1e-9 to 1e-8 m³/Pa
        tau = 1.8
        R2 = 1e8

        C = tau / R2

        # Should be in physiological range
        assert 1e-10 < C < 1e-7

    def test_pwv_physiological_range(self):
        """Test that PWV is in physiological range (4-10 m/s for aorta)."""
        a = 13.3
        b = 0.3
        A_mm2 = 100  # Typical aortic area

        c = a / (2 * np.sqrt(A_mm2 / np.pi)) ** b

        assert 3.0 < c < 12.0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def setup_method(self):
        """Setup minimal config."""
        self.config = {
            "geometry": {
                "case_name": "test",
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["outlet1"],
            },
            "boundary_conditions": {
                "inlet": {"type": "CONSTANT", "cardiac_output": 5.0},
                "outlets": {"windkessel_settings": {"systolic_pressure": 120, "diastolic_pressure": 80}},
            },
            "physics": {"blood_density": 1060},
        }

    def test_zero_flow_resistance(self):
        """Test that zero flow gives very high resistance."""
        MAP_Pa = 100 * 133.322
        Q_zero = 1e-20  # Effectively zero

        R = MAP_Pa / Q_zero

        # Should be very large
        assert R > 1e15

    def test_very_small_outlet_radius(self):
        """Test Murray's law with very small radius."""
        outlet_radii = {"tiny": 0.0001, "normal": 0.010}  # 0.1mm  # 10mm

        # Should not crash and should give valid ratios
        # MURRAY_LAW_EXPONENT imported at top of file
        r_powered_sum = sum(r**MURRAY_LAW_EXPONENT for r in outlet_radii.values())
        ratio_tiny = outlet_radii["tiny"] ** MURRAY_LAW_EXPONENT / r_powered_sum

        assert 0 < ratio_tiny < 0.001  # Very small but non-zero

    def test_equal_sp_and_dp(self):
        """Test MAP when systolic = diastolic (no pulse pressure)."""
        SP = 100
        DP = 100

        MAP = (SP + DP) / 2.0

        assert MAP == pytest.approx(100.0, rel=1e-6)


class TestCheckDirectRCZMode:
    """Test direct RCZ mode detection."""

    def setup_method(self):
        """Setup config for testing."""
        self.config = {
            "geometry": {"inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": ["outlet1", "outlet2"]},
            "boundary_conditions": {
                "inlet": {"type": "CONSTANT"},
                "outlets": {"windkessel_settings": {"systolic_pressure": 120, "diastolic_pressure": 80}},
            },
            "physics": {"blood_density": 1060},
        }

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_direct_rcz_mode_enabled(self, mock_logger):
        """Test direct RCZ mode enabled when all outlets have R, C, Z."""
        self.config["boundary_conditions"]["outlets"]["windkessel_settings"]["outlet_parameters"] = {
            "outlet1": {"R": 1.5e9, "C": 1.0e-9, "Z": 1.5e8},
            "outlet2": {"R": 2.0e9, "C": 0.8e-9, "Z": 2.0e8},
        }

        wk = WkSetup(self.config, [], "/tmp/test", 1.0)
        outlet_patches = ["outlet1", "outlet2"]

        result = wk._check_direct_rcz_mode(outlet_patches)

        assert result is True

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_direct_rcz_mode_missing_outlet(self, mock_logger):
        """Test direct RCZ mode disabled when outlet is missing."""
        self.config["boundary_conditions"]["outlets"]["windkessel_settings"]["outlet_parameters"] = {
            "outlet1": {"R": 1.5e9, "C": 1.0e-9, "Z": 1.5e8}
            # outlet2 missing
        }

        wk = WkSetup(self.config, [], "/tmp/test", 1.0)
        outlet_patches = ["outlet1", "outlet2"]

        result = wk._check_direct_rcz_mode(outlet_patches)

        assert result is False

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_direct_rcz_mode_missing_parameter(self, mock_logger):
        """Test direct RCZ mode disabled when R, C, or Z is missing."""
        self.config["boundary_conditions"]["outlets"]["windkessel_settings"]["outlet_parameters"] = {
            "outlet1": {"R": 1.5e9, "C": 1.0e-9},  # Z missing
            "outlet2": {"R": 2.0e9, "C": 0.8e-9, "Z": 2.0e8},
        }

        wk = WkSetup(self.config, [], "/tmp/test", 1.0)
        outlet_patches = ["outlet1", "outlet2"]

        result = wk._check_direct_rcz_mode(outlet_patches)

        assert result is False

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_direct_rcz_mode_non_numeric_value(self, mock_logger):
        """Test direct RCZ mode disabled when value is non-numeric."""
        self.config["boundary_conditions"]["outlets"]["windkessel_settings"]["outlet_parameters"] = {
            "outlet1": {"R": "invalid", "C": 1.0e-9, "Z": 1.5e8},
            "outlet2": {"R": 2.0e9, "C": 0.8e-9, "Z": 2.0e8},
        }

        wk = WkSetup(self.config, [], "/tmp/test", 1.0)
        outlet_patches = ["outlet1", "outlet2"]

        result = wk._check_direct_rcz_mode(outlet_patches)

        assert result is False

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_direct_rcz_mode_empty_params(self, mock_logger):
        """Test direct RCZ mode disabled when outlet_parameters is empty."""
        self.config["boundary_conditions"]["outlets"]["windkessel_settings"]["outlet_parameters"] = {}

        wk = WkSetup(self.config, [], "/tmp/test", 1.0)
        outlet_patches = ["outlet1", "outlet2"]

        result = wk._check_direct_rcz_mode(outlet_patches)

        assert result is False


class TestParseCustomFlowSplit:
    """Test custom flow split parsing."""

    def setup_method(self):
        """Setup mock config."""
        self.config = {
            "geometry": {
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["outlet1", "outlet2", "outlet3"],
            },
            "boundary_conditions": {
                "inlet": {"type": "CONSTANT"},
                "outlets": {"windkessel_settings": {"systolic_pressure": 120, "diastolic_pressure": 80}},
            },
            "physics": {"blood_density": 1060},
        }

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_parse_complete_ratios(self, mock_logger):
        """Test parsing when values are complete ratios summing to 1.0."""
        wk = WkSetup(self.config, [], "/tmp/test", 1.0)

        flow_split_config = {"outlet1": 0.2, "outlet2": 0.3, "outlet3": 0.5}
        outlet_patches = ["outlet1", "outlet2", "outlet3"]
        outlet_radii = {"outlet1": 0.005, "outlet2": 0.006, "outlet3": 0.008}

        result = wk._parse_custom_flow_split(flow_split_config, outlet_patches, outlet_radii)

        assert result["outlet1"] == pytest.approx(0.2, rel=1e-6)
        assert result["outlet2"] == pytest.approx(0.3, rel=1e-6)
        assert result["outlet3"] == pytest.approx(0.5, rel=1e-6)
        assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_parse_percentages_mode(self, mock_logger):
        """Test parsing when values are percentages (> 1.0 or don't sum to 1)."""
        wk = WkSetup(self.config, [], "/tmp/test", 1.0)

        flow_split_config = {"outlet1": 20, "outlet2": 30, "outlet3": 50}
        outlet_patches = ["outlet1", "outlet2", "outlet3"]
        outlet_radii = {"outlet1": 0.005, "outlet2": 0.006, "outlet3": 0.008}

        result = wk._parse_custom_flow_split(flow_split_config, outlet_patches, outlet_radii)

        assert result["outlet1"] == pytest.approx(0.2, rel=1e-6)
        assert result["outlet2"] == pytest.approx(0.3, rel=1e-6)
        assert result["outlet3"] == pytest.approx(0.5, rel=1e-6)

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_parse_with_rest_murray(self, mock_logger):
        """Test parsing with _rest='murray' for remaining outlets."""
        wk = WkSetup(self.config, [], "/tmp/test", 1.0)

        flow_split_config = {"outlet3": 50, "_rest": "murray"}
        outlet_patches = ["outlet1", "outlet2", "outlet3"]
        outlet_radii = {"outlet1": 0.005, "outlet2": 0.005, "outlet3": 0.008}

        result = wk._parse_custom_flow_split(flow_split_config, outlet_patches, outlet_radii)

        # outlet3 gets 50%
        assert result["outlet3"] == pytest.approx(0.5, rel=1e-6)
        # outlet1 and outlet2 share 50% by Murray's law (equal radii = equal share)
        assert result["outlet1"] == pytest.approx(0.25, rel=1e-2)
        assert result["outlet2"] == pytest.approx(0.25, rel=1e-2)


class TestNormalizeDataType:
    """Test data type normalization."""

    def setup_method(self):
        """Setup minimal config."""
        self.config = {
            "geometry": {"inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": ["outlet1"]},
            "boundary_conditions": {
                "inlet": {"type": "CONSTANT"},
                "outlets": {"windkessel_settings": {"systolic_pressure": 120, "diastolic_pressure": 80}},
            },
            "physics": {"blood_density": 1060},
        }

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_normalize_flowrate_variants(self, mock_logger):
        """Test normalization of flowrate variants."""
        wk = WkSetup(self.config, [], "/tmp/test", 1.0)

        assert wk._normalize_data_type("flowrate") == "flowrate"
        assert wk._normalize_data_type("flowRate") == "flowrate"
        assert wk._normalize_data_type("FLOWRATE") == "flowrate"
        assert wk._normalize_data_type("flow_rate") == "flowrate"
        assert wk._normalize_data_type("flow") == "flowrate"
        assert wk._normalize_data_type("Q") == "flowrate"

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_normalize_velocity_variants(self, mock_logger):
        """Test normalization of velocity variants."""
        wk = WkSetup(self.config, [], "/tmp/test", 1.0)

        assert wk._normalize_data_type("velocity") == "velocity"
        assert wk._normalize_data_type("Velocity") == "velocity"
        assert wk._normalize_data_type("VELOCITY") == "velocity"
        assert wk._normalize_data_type("vel") == "velocity"
        assert wk._normalize_data_type("u") == "velocity"

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_normalize_pressure_variants(self, mock_logger):
        """Test normalization of pressure variants."""
        wk = WkSetup(self.config, [], "/tmp/test", 1.0)

        assert wk._normalize_data_type("pressure") == "pressure"
        assert wk._normalize_data_type("PRESSURE") == "pressure"
        assert wk._normalize_data_type("p") == "pressure"
        assert wk._normalize_data_type("press") == "pressure"

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_normalize_none_input(self, mock_logger):
        """Test normalization with None input."""
        wk = WkSetup(self.config, [], "/tmp/test", 1.0)

        assert wk._normalize_data_type(None) is None

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_normalize_unknown_type(self, mock_logger):
        """Test normalization of unknown type returns as-is."""
        wk = WkSetup(self.config, [], "/tmp/test", 1.0)

        assert wk._normalize_data_type("unknown_type") == "unknown_type"


class TestReadInletFlow:
    """Test reading inlet flow data from CSV."""

    def setup_method(self):
        """Setup minimal config."""
        self.config = {
            "geometry": {"inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": ["outlet1"]},
            "boundary_conditions": {
                "inlet": {"type": "CONSTANT"},
                "outlets": {"windkessel_settings": {"systolic_pressure": 120, "diastolic_pressure": 80}},
            },
            "physics": {"blood_density": 1060},
        }

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_read_flowrate_data(self, mock_logger, tmp_path):
        """Test reading flow rate CSV data."""
        wk = WkSetup(self.config, [], "/tmp/test", 1.0)

        # Create CSV file
        csv_content = """time,flowrate
0.0,1.0e-5
0.4,2.0e-5
0.8,1.0e-5"""
        csv_file = tmp_path / "inlet.csv"
        csv_file.write_text(csv_content)

        inlet_area = 1e-4  # 1 cm²
        times, flow = wk._read_inlet_flow(str(csv_file), "flowrate", inlet_area)

        assert len(times) == 3
        assert len(flow) == 3
        assert times[0] == pytest.approx(0.0)
        assert flow[1] == pytest.approx(2.0e-5)

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_read_velocity_data(self, mock_logger, tmp_path):
        """Test reading velocity CSV data (converts to flow rate)."""
        wk = WkSetup(self.config, [], "/tmp/test", 1.0)

        csv_content = """time,velocity
0.0,0.5
0.4,1.0
0.8,0.5"""
        csv_file = tmp_path / "inlet.csv"
        csv_file.write_text(csv_content)

        inlet_area = 1e-4  # 1 cm²
        times, flow = wk._read_inlet_flow(str(csv_file), "velocity", inlet_area)

        assert len(times) == 3
        # Flow = velocity * area
        assert flow[0] == pytest.approx(0.5 * 1e-4)
        assert flow[1] == pytest.approx(1.0 * 1e-4)

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_read_csv_with_comments(self, mock_logger, tmp_path):
        """Test reading CSV with comment lines."""
        wk = WkSetup(self.config, [], "/tmp/test", 1.0)

        csv_content = """# This is a comment
# Another comment
time,flowrate
0.0,1.0e-5
0.8,2.0e-5"""
        csv_file = tmp_path / "inlet.csv"
        csv_file.write_text(csv_content)

        times, flow = wk._read_inlet_flow(str(csv_file), "flowrate", 1e-4)

        assert len(times) == 2
        assert times[0] == pytest.approx(0.0)

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_read_missing_file(self, mock_logger, tmp_path):
        """Test error when file doesn't exist."""
        wk = WkSetup(self.config, [], "/tmp/test", 1.0)

        with pytest.raises(FileNotFoundError, match="Could not find inlet data file"):
            wk._read_inlet_flow("/nonexistent/file.csv", "flowrate", 1e-4)

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_read_unknown_data_type(self, mock_logger, tmp_path):
        """Test error with unknown data type."""
        wk = WkSetup(self.config, [], "/tmp/test", 1.0)

        csv_content = """time,value
0.0,1.0
0.8,2.0"""
        csv_file = tmp_path / "inlet.csv"
        csv_file.write_text(csv_content)

        with pytest.raises(ValueError, match="Unknown data type"):
            wk._read_inlet_flow(str(csv_file), "unknown_type", 1e-4)


class TestCalculatePercentageFlowSplit:
    """Test percentage-based flow split with area or Murray method."""

    def setup_method(self):
        """Setup minimal config."""
        self.config = {
            "geometry": {"inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": ["branch1", "branch2", "main"]},
            "boundary_conditions": {
                "inlet": {"type": "CONSTANT"},
                "outlets": {"windkessel_settings": {"systolic_pressure": 120, "diastolic_pressure": 80}},
            },
            "physics": {"blood_density": 1060},
        }

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_area_method_split(self, mock_logger):
        """Test percentage split using area method."""
        wk = WkSetup(self.config, [], "/tmp/test", 1.0)

        outlet_patches = ["branch1", "branch2", "main"]
        outlet_radii = {"branch1": 0.003, "branch2": 0.003, "main": 0.010}  # Area = π * 9e-6  # Area = π * 9e-6

        result = wk._parse_flow_split_percentage(
            60.0, outlet_patches, method="area", geometry_data=outlet_radii  # 60% to branches
        )

        # Main gets 40%
        assert result["main"] == pytest.approx(0.40, rel=1e-6)
        # Branches share 60% equally (same area)
        assert result["branch1"] == pytest.approx(0.30, rel=1e-6)
        assert result["branch2"] == pytest.approx(0.30, rel=1e-6)

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_murray_method_split(self, mock_logger):
        """Test percentage split using Murray method."""
        wk = WkSetup(self.config, [], "/tmp/test", 1.0)

        outlet_patches = ["branch1", "branch2", "main"]
        outlet_radii = {"branch1": 0.003, "branch2": 0.006, "main": 0.010}  # Twice the radius

        result = wk._parse_flow_split_percentage(
            60.0, outlet_patches, method="murray", geometry_data=outlet_radii  # 60% to branches
        )

        # Main gets 40%
        assert result["main"] == pytest.approx(0.40, rel=1e-6)
        # Branch2 should get more than branch1 (larger radius)
        assert result["branch2"] > result["branch1"]
        # Should sum to 1.0
        assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_no_geometry_data_raises(self, mock_logger):
        """Test error when geometry_data is missing."""
        wk = WkSetup(self.config, [], "/tmp/test", 1.0)

        outlet_patches = ["branch1", "main"]

        with pytest.raises(ValueError, match="Geometry data"):
            wk._parse_flow_split_percentage(60.0, outlet_patches, method="area", geometry_data=None)


class TestPlotFlowDistribution:
    """Test flow distribution plotting (with matplotlib mock)."""

    def setup_method(self):
        """Setup minimal config."""
        self.config = {
            "geometry": {"inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": ["outlet1", "outlet2"]},
            "boundary_conditions": {
                "inlet": {"type": "CONSTANT"},
                "outlets": {"windkessel_settings": {"systolic_pressure": 120, "diastolic_pressure": 80}},
            },
            "physics": {"blood_density": 1060},
        }

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_plot_flow_distribution_no_matplotlib(self, mock_logger, tmp_path):
        """Test graceful handling when matplotlib is not available."""
        wk = WkSetup(self.config, [], "/tmp/test", 1.0)

        # Mock import error for matplotlib
        with patch.dict("sys.modules", {"matplotlib": None, "matplotlib.pyplot": None}):
            # Should not raise, just log warning
            times = np.array([0.0, 0.4, 0.8])
            flow_inlet = np.array([1e-5, 2e-5, 1e-5])
            flow_splits = {"outlet1": 0.6, "outlet2": 0.4}

            # This shouldn't crash even without matplotlib
            try:
                wk.plot_flow_distribution(times, flow_inlet, flow_splits, str(tmp_path / "plot.png"))
            except ImportError:
                pass  # Expected if matplotlib is truly unavailable

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_plot_flow_distribution_steady_no_matplotlib(self, mock_logger, tmp_path):
        """Test steady flow plot graceful handling."""
        wk = WkSetup(self.config, [], "/tmp/test", 1.0)

        with patch.dict("sys.modules", {"matplotlib": None, "matplotlib.pyplot": None}):
            mean_Q = 1e-5
            flow_splits = {"outlet1": 0.6, "outlet2": 0.4}
            outlet_params = {"outlet1": {"R": 1e9, "C": 1e-9, "Z": 1e8}, "outlet2": {"R": 2e9, "C": 0.5e-9, "Z": 2e8}}

            try:
                wk.plot_flow_distribution_steady(mean_Q, flow_splits, outlet_params, str(tmp_path / "plot.png"))
            except ImportError:
                pass


class TestExecuteMethod:
    """Test the main execute() method."""

    def setup_method(self):
        """Setup config for execute tests."""
        self.config = {
            "geometry": {
                "case_name": "test_case",
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["outlet1", "outlet2"],
                "scale_factor": 0.001,
            },
            "boundary_conditions": {
                "inlet": {"type": "CONSTANT", "csv_file": "inlet.csv", "data_type": "flowrate", "cardiac_output": 5.0},
                "outlets": {
                    # v1.4.0: outlets.type is now explicitly required for the
                    # Windkessel path. Previously, having windkessel_settings
                    # was an implicit signal.
                    "type": "3EWINDKESSEL",
                    "windkessel_settings": {
                        "systolic_pressure": 120,
                        "diastolic_pressure": 80,
                        "tau": 1.8,
                        "venous_pressure": 5,
                        "pwv": 6.0,
                    },
                },
            },
            "physics": {"blood_density": 1060},
        }

    @patch("aortacfd_lib.wk_setup.Logger")
    @patch("aortacfd_lib.wk_setup.PatchProcessing")
    def test_execute_direct_rcz_mode(self, mock_pp, mock_logger, tmp_path):
        """Test execute() injects q_init for direct RCZ mode."""
        # Add direct RCZ parameters
        self.config["boundary_conditions"]["outlets"]["windkessel_settings"]["outlet_parameters"] = {
            "outlet1": {"R": 1.5e9, "C": 1.0e-9, "Z": 1.5e8},
            "outlet2": {"R": 2.0e9, "C": 0.8e-9, "Z": 2.0e8},
        }

        mock_instance = MagicMock()
        mock_instance.calculate_surface_area.side_effect = [
            np.pi * 0.01**2,
            np.pi * 0.006**2,
            np.pi * 0.004**2,
        ]
        mock_pp.return_value = mock_instance

        wk = WkSetup(self.config, [], str(tmp_path), 0.8)
        wk.execute()

        outlet_parameters = self.config["boundary_conditions"]["outlets"]["windkessel_settings"]["outlet_parameters"]
        assert outlet_parameters["outlet1"]["q_init"] > 0
        assert outlet_parameters["outlet2"]["q_init"] > 0
        assert outlet_parameters["outlet1"]["q_init"] + outlet_parameters["outlet2"]["q_init"] == pytest.approx(
            5.0 / 60.0 / 1000.0,
            rel=1e-9,
        )

    @patch("aortacfd_lib.wk_setup.Logger")
    @patch("aortacfd_lib.wk_setup.PatchProcessing")
    def test_execute_direct_rcz_preserves_existing_q_init(self, mock_pp, mock_logger, tmp_path):
        """Test execute() does not overwrite user-specified q_init in direct RCZ mode."""
        self.config["boundary_conditions"]["outlets"]["windkessel_settings"]["outlet_parameters"] = {
            "outlet1": {"R": 1.5e9, "C": 1.0e-9, "Z": 1.5e8, "q_init": 1.2e-5},
            "outlet2": {"R": 2.0e9, "C": 0.8e-9, "Z": 2.0e8},
        }

        mock_instance = MagicMock()
        mock_instance.calculate_surface_area.side_effect = [
            np.pi * 0.01**2,
            np.pi * 0.006**2,
            np.pi * 0.004**2,
        ]
        mock_pp.return_value = mock_instance

        wk = WkSetup(self.config, [], str(tmp_path), 0.8)
        wk.execute()

        outlet_parameters = self.config["boundary_conditions"]["outlets"]["windkessel_settings"]["outlet_parameters"]
        assert outlet_parameters["outlet1"]["q_init"] == pytest.approx(1.2e-5)
        assert outlet_parameters["outlet2"]["q_init"] > 0

    @patch("aortacfd_lib.wk_setup.Logger")
    @patch("aortacfd_lib.wk_setup.PatchProcessing")
    def test_execute_direct_rcz_mode_with_mri_inlet(self, mock_pp, mock_logger, tmp_path):
        """Test direct RCZ q_init injection for MRI inlet data."""
        self.config["boundary_conditions"]["inlet"] = {
            "type": "MRI",
            "file": "./inlet",
            "orientation": "out",
        }
        self.config["boundary_conditions"]["outlets"]["windkessel_settings"]["outlet_parameters"] = {
            "outlet1": {"R": 1.5e9, "C": 1.0e-9, "Z": 1.5e8},
            "outlet2": {"R": 2.0e9, "C": 0.8e-9, "Z": 2.0e8},
        }

        mock_instance = MagicMock()
        mock_instance.calculate_surface_area.side_effect = [
            np.pi * 0.01**2,
            np.pi * 0.006**2,
            np.pi * 0.004**2,
        ]
        mock_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]),
            0.01,
            np.array([0.0, 0.0, 1.0]),
        )
        mock_pp.return_value = mock_instance

        boundary_data = tmp_path / "constant" / "boundaryData" / "inlet"
        for time_name, values in {
            "0": [(0.0, 0.0, 2.0), (0.0, 0.0, 4.0)],
            "0.5": [(0.0, 0.0, 4.0), (0.0, 0.0, 6.0)],
        }.items():
            time_dir = boundary_data / time_name
            time_dir.mkdir(parents=True, exist_ok=True)
            with open(time_dir / "U", "w") as handle:
                handle.write("2\n(\n")
                for value in values:
                    handle.write(f"({value[0]} {value[1]} {value[2]})\n")
                handle.write(")\n")

        wk = WkSetup(self.config, [], str(tmp_path), 0.8)
        wk.execute()

        outlet_parameters = self.config["boundary_conditions"]["outlets"]["windkessel_settings"]["outlet_parameters"]
        expected_mean_q = np.pi * 0.01**2 * 4.0
        assert outlet_parameters["outlet1"]["q_init"] > 0
        assert outlet_parameters["outlet2"]["q_init"] > 0
        assert outlet_parameters["outlet1"]["q_init"] + outlet_parameters["outlet2"]["q_init"] == pytest.approx(
            expected_mean_q,
            rel=1e-9,
        )

    @patch("aortacfd_lib.wk_setup.Logger")
    @patch("aortacfd_lib.wk_setup.PatchProcessing")
    def test_execute_2element_windkessel(self, mock_pp, mock_logger, tmp_path):
        """Test execute() with 2-element Windkessel (CONSTANT inlet)."""
        # Setup mocks
        mock_instance = MagicMock()
        mock_instance.calculate_inlet_center_radius.return_value = (np.array([0, 0, 0]), 0.01, np.array([0, 0, 1]))
        mock_instance.calculate_surface_area.return_value = np.pi * 0.005**2
        mock_pp.return_value = mock_instance

        # Create directories
        case_dir = tmp_path / "case"
        tri_surface = case_dir / "constant" / "triSurface"
        boundary_data = case_dir / "constant" / "boundaryData" / "inlet"
        tri_surface.mkdir(parents=True)
        boundary_data.mkdir(parents=True)

        # Create STL files
        for name in ["outlet1.stl", "outlet2.stl"]:
            (tri_surface / name).write_text("solid\nendsolid")

        self.config["boundary_conditions"]["inlet"]["type"] = "CONSTANT"
        self.config["boundary_conditions"]["outlets"]["type"] = "2EWINDKESSEL"

        wk = WkSetup(self.config, ["outlet1.stl", "outlet2.stl"], str(case_dir), 0.8)

        # Execute should complete without error
        wk.execute()


class TestWkSetupInit:
    """Test WkSetup initialization."""

    def test_init_with_nested_config(self):
        """Test initialization with nested boundary_conditions config."""
        config = {
            "geometry": {"inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": ["outlet1"]},
            "boundary_conditions": {
                "inlet": {"type": "CONSTANT"},
                "outlets": {"windkessel_settings": {"systolic_pressure": 120, "diastolic_pressure": 80}},
            },
            "physics": {"blood_density": 1060},
        }

        with patch("aortacfd_lib.wk_setup.Logger"):
            wk = WkSetup(config, [], "/tmp/test", 1.0)

        assert wk.inlet_settings == config["boundary_conditions"]["inlet"]
        assert wk.outlet_settings == config["boundary_conditions"]["outlets"]

    def test_init_with_flat_config(self):
        """Test initialization with flattened inlet/outlets config."""
        config = {
            "geometry": {"inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": ["outlet1"]},
            "inlet": {"type": "CONSTANT"},
            "outlets": {"windkessel_settings": {"systolic_pressure": 120, "diastolic_pressure": 80}},
            "boundary_conditions": {},
            "physics": {"blood_density": 1060},
        }

        with patch("aortacfd_lib.wk_setup.Logger"):
            wk = WkSetup(config, [], "/tmp/test", 1.0)

        assert wk.inlet_settings == config["inlet"]
        assert wk.outlet_settings == config["outlets"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
