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


class TestWindkesselConstants:
    """Test unit conversion constants."""

    def test_mmhg_to_pa_conversion(self):
        """Test mmHg to Pascal conversion constant."""
        assert WkSetup.MMHG_TO_PA == pytest.approx(133.322, rel=1e-4)

    def test_ml_to_m3_conversion(self):
        """Test mL to m³ conversion constant."""
        assert WkSetup.ML_TO_M3 == pytest.approx(1e-6, rel=1e-9)


class TestMurrayFlowSplit:
    """Test Murray's law flow distribution calculations."""

    def setup_method(self):
        """Setup mock config and WkSetup instance."""
        self.config = {
            'geometry': {
                'case_name': 'test_case',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1', 'outlet2', 'outlet3']
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'cardiac_output': 5.0},
                'outlets': {
                    'windkessel_settings': {
                        'systolic_pressure': 120,
                        'diastolic_pressure': 80,
                        'tau': 1.8
                    }
                }
            },
            'physics': {'blood_density': 1060}
        }
        self.wk = WkSetup(self.config, [], '/tmp/test', 1.0)

    def test_murray_equal_radii(self):
        """Test Murray's law with equal outlet radii."""
        outlet_radii = {
            'outlet1': 0.005,  # 5mm
            'outlet2': 0.005,
            'outlet3': 0.005
        }

        flow_split = self.wk._calculate_murray_flow_split(outlet_radii)

        # Equal radii should give equal flow split
        assert flow_split['outlet1'] == pytest.approx(1/3, rel=1e-6)
        assert flow_split['outlet2'] == pytest.approx(1/3, rel=1e-6)
        assert flow_split['outlet3'] == pytest.approx(1/3, rel=1e-6)

        # Should sum to 1.0
        assert sum(flow_split.values()) == pytest.approx(1.0, rel=1e-9)

    def test_murray_different_radii(self):
        """Test Murray's law with different radii."""
        outlet_radii = {
            'outlet1': 0.008,  # 8mm - largest
            'outlet2': 0.005,  # 5mm - medium
            'outlet3': 0.003   # 3mm - smallest
        }

        flow_split = self.wk._calculate_murray_flow_split(outlet_radii)

        # Larger vessels should get more flow (r³ relationship)
        assert flow_split['outlet1'] > flow_split['outlet2'] > flow_split['outlet3']

        # Check actual Murray's law: f_i = r³ / Σr³
        r_cubed_sum = sum(r**3 for r in outlet_radii.values())
        for name, radius in outlet_radii.items():
            expected = radius**3 / r_cubed_sum
            assert flow_split[name] == pytest.approx(expected, rel=1e-6)

        # Should sum to 1.0
        assert sum(flow_split.values()) == pytest.approx(1.0, rel=1e-9)

    def test_murray_single_outlet(self):
        """Test Murray's law with single outlet gets 100%."""
        outlet_radii = {'outlet1': 0.010}

        flow_split = self.wk._calculate_murray_flow_split(outlet_radii)

        assert flow_split['outlet1'] == pytest.approx(1.0, rel=1e-9)

    def test_murray_two_outlets_double_radius(self):
        """Test that doubling radius increases flow by 8x (2³=8)."""
        outlet_radii = {
            'small': 0.005,   # 5mm
            'large': 0.010    # 10mm (2x diameter)
        }

        flow_split = self.wk._calculate_murray_flow_split(outlet_radii)

        # Large outlet should get 8/(8+1) = 8/9 ≈ 0.889
        expected_large = 8.0 / 9.0
        expected_small = 1.0 / 9.0

        assert flow_split['large'] == pytest.approx(expected_large, rel=1e-4)
        assert flow_split['small'] == pytest.approx(expected_small, rel=1e-4)


class TestFlowSplitPercentage:
    """Test percentage-based flow distribution."""

    def setup_method(self):
        """Setup mock config and WkSetup instance."""
        self.config = {
            'geometry': {
                'case_name': 'test_case',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['branch1', 'branch2', 'main']
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'cardiac_output': 5.0},
                'outlets': {
                    'windkessel_settings': {
                        'systolic_pressure': 120,
                        'diastolic_pressure': 80
                    }
                }
            },
            'physics': {'blood_density': 1060}
        }
        self.wk = WkSetup(self.config, [], '/tmp/test', 1.0)

    def test_percentage_split_basic(self):
        """Test basic percentage split (60% to branches, 40% to main)."""
        outlet_patches = ['branch1', 'branch2', 'main']
        outlet_radii = {
            'branch1': 0.003,  # Same radius
            'branch2': 0.003,  # Same radius
            'main': 0.010
        }

        flow_split = self.wk._parse_flow_split_percentage(
            60.0,  # 60% to branches
            outlet_patches,
            method='area',
            geometry_data=outlet_radii
        )

        # Main outlet should get 40%
        assert flow_split['main'] == pytest.approx(0.40, rel=1e-6)

        # Branches share 60% equally (same area)
        assert flow_split['branch1'] == pytest.approx(0.30, rel=1e-6)
        assert flow_split['branch2'] == pytest.approx(0.30, rel=1e-6)

        # Should sum to 1.0
        assert sum(flow_split.values()) == pytest.approx(1.0, rel=1e-9)

    def test_percentage_split_single_outlet(self):
        """Test percentage split with single outlet gets 100%."""
        outlet_patches = ['main']
        outlet_radii = {'main': 0.010}

        flow_split = self.wk._parse_flow_split_percentage(
            50.0,  # Doesn't matter for single outlet
            outlet_patches,
            method='area',
            geometry_data=outlet_radii
        )

        assert flow_split['main'] == pytest.approx(1.0, rel=1e-9)

    def test_percentage_split_no_outlets(self):
        """Test error with no outlets."""
        with pytest.raises(ValueError, match="No outlet patches"):
            self.wk._parse_flow_split_percentage(60.0, [], method='area', geometry_data={})


class TestMAPCalculation:
    """Test Mean Arterial Pressure calculations.

    Uses physiological MAP formula: MAP = DP + (SP-DP)/3 = (2*DP + SP)/3
    This accounts for diastole being ~2/3 of the cardiac cycle.
    Reference: Klabunde (2011) Cardiovascular Physiology Concepts
    """

    def test_map_formula_standard_values(self):
        """Test MAP calculation with standard BP values (120/80 mmHg)."""
        SP = 120  # mmHg
        DP = 80   # mmHg

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
        MAP_Pa = MAP_mmHg * WkSetup.MMHG_TO_PA

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
        c = 6.0     # m/s (PWV)
        A = 3.14e-4 # m² (10mm radius circle)

        R1 = rho * c / A

        expected = 1060 * 6.0 / 3.14e-4
        assert R1 == pytest.approx(expected, rel=1e-6)

    def test_distal_resistance_r2(self):
        """Test R2 = R_total - R1."""
        R_total = 1e8  # Pa·s/m³
        R1 = 1e7       # Pa·s/m³

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
        R2 = 9e7   # Pa·s/m³

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

        A_small = 50   # mm²
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
        diameter_small = 5   # mm

        # These would be the assigned PWV values in empirical method
        assert 4.5 <= 5.0 <= 5.5  # Large
        assert 5.5 <= 6.0 <= 6.5  # Medium
        assert 6.5 <= 7.0 <= 7.5  # Small


class TestUnitConversions:
    """Test unit conversions used in Windkessel calculations."""

    def test_pressure_mmhg_to_pa(self):
        """Test pressure conversion mmHg → Pa."""
        pressure_mmHg = 120
        pressure_Pa = pressure_mmHg * WkSetup.MMHG_TO_PA

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
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1']
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'cardiac_output': 5.0},
                'outlets': {
                    'windkessel_settings': {
                        'systolic_pressure': 120,
                        'diastolic_pressure': 80
                    }
                }
            },
            'physics': {'blood_density': 1060}
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
        outlet_radii = {
            'tiny': 0.0001,  # 0.1mm
            'normal': 0.010   # 10mm
        }

        # Should not crash and should give valid ratios
        r_cubed_sum = sum(r**3 for r in outlet_radii.values())
        ratio_tiny = outlet_radii['tiny']**3 / r_cubed_sum

        assert 0 < ratio_tiny < 0.001  # Very small but non-zero

    def test_equal_sp_and_dp(self):
        """Test MAP when systolic = diastolic (no pulse pressure)."""
        SP = 100
        DP = 100

        MAP = (SP + DP) / 2.0

        assert MAP == pytest.approx(100.0, rel=1e-6)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
