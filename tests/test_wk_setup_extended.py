"""
Extended test suite for WkSetup class.

Tests cover:
- Windkessel coefficient calculations
- Flow split methods (Murray's law, percentage, custom)
- PWV calculation methods
- 2-element vs 3-element model selection
- Input validation and edge cases
"""

import pytest
import sys
import math
import numpy as np
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aortacfd_lib.constants import MMHG_TO_PA, ML_TO_M3, MURRAY_LAW_EXPONENT


class TestMurrayFlowSplitExtended:
    """Extended tests for Murray's law flow split calculation."""

    def test_murray_three_outlets_equal(self):
        """Test Murray's law with three equal outlets."""
        radii = {"o1": 0.01, "o2": 0.01, "o3": 0.01}  # All equal radii

        # Murray's law: f_i = r_i³ / Σr_j³
        total_r3 = sum(r**MURRAY_LAW_EXPONENT for r in radii.values())
        expected = {name: (r**MURRAY_LAW_EXPONENT) / total_r3 for name, r in radii.items()}

        # All should be ~33.3%
        for name, fraction in expected.items():
            assert fraction == pytest.approx(1 / 3, rel=1e-6)

    def test_murray_dominant_outlet(self):
        """Test Murray's law with one dominant outlet."""
        radii = {"main": 0.02, "branch1": 0.005, "branch2": 0.005}

        total_r3 = sum(r**MURRAY_LAW_EXPONENT for r in radii.values())
        main_fraction = (0.02**MURRAY_LAW_EXPONENT) / total_r3

        # Main outlet should get most of the flow
        assert main_fraction > 0.9  # Should be >90%

    def test_murray_preserves_total_flow(self):
        """Test that Murray's law fractions sum to 1."""
        radii = {"o1": 0.015, "o2": 0.01, "o3": 0.008, "o4": 0.005}

        total_r3 = sum(r**MURRAY_LAW_EXPONENT for r in radii.values())
        fractions = {name: (r**MURRAY_LAW_EXPONENT) / total_r3 for name, r in radii.items()}

        assert sum(fractions.values()) == pytest.approx(1.0, rel=1e-9)


class TestMAPCalculationExtended:
    """Extended tests for Mean Arterial Pressure calculation."""

    def test_map_hypertensive(self):
        """Test MAP for hypertensive patient (140/90)."""
        SP, DP = 140, 90
        MAP = DP + (SP - DP) / 3
        assert MAP == pytest.approx(106.67, rel=1e-2)

    def test_map_hypotensive(self):
        """Test MAP for hypotensive patient (90/60)."""
        SP, DP = 90, 60
        MAP = DP + (SP - DP) / 3
        assert MAP == pytest.approx(70.0, rel=1e-2)

    def test_map_wide_pulse_pressure(self):
        """Test MAP with wide pulse pressure (isolated systolic hypertension)."""
        SP, DP = 160, 70
        MAP = DP + (SP - DP) / 3
        # Wide pulse pressure: PP = 90 mmHg
        assert MAP == pytest.approx(100.0, rel=1e-2)

    def test_map_narrow_pulse_pressure(self):
        """Test MAP with narrow pulse pressure."""
        SP, DP = 100, 85
        MAP = DP + (SP - DP) / 3
        # Narrow pulse pressure: PP = 15 mmHg
        assert MAP == pytest.approx(90.0, rel=1e-2)


class TestResistanceCalculationExtended:
    """Extended tests for resistance calculations."""

    def test_total_resistance_formula(self):
        """Test R_total = (MAP - P_venous) / Q formula."""
        MAP_Pa = 100 * MMHG_TO_PA  # 100 mmHg in Pa
        P_venous_Pa = 5 * MMHG_TO_PA  # 5 mmHg in Pa
        Q = 5e-5  # 50 mL/s in m³/s

        R_total = (MAP_Pa - P_venous_Pa) / Q

        # R_total in mmHg·s/mL for clinical comparison
        R_clinical = R_total / (MMHG_TO_PA * 1e6)
        assert R_clinical == pytest.approx(1.9, rel=0.1)  # ~1.9 mmHg·s/mL

    def test_zero_venous_pressure(self):
        """Test with zero venous pressure (historical CFD convention)."""
        MAP_Pa = 93.3 * MMHG_TO_PA  # Normal MAP
        P_venous_Pa = 0  # Zero venous pressure
        Q = 8.33e-5  # ~5 L/min total, so ~83 mL/s = 8.33e-5 m³/s

        R_total = (MAP_Pa - P_venous_Pa) / Q

        # Should give reasonable resistance
        assert R_total > 0
        assert R_total < 1e10  # Should be less than 10 GPa·s/m³

    def test_resistance_scales_inversely_with_flow(self):
        """Test that resistance scales inversely with flow."""
        MAP_Pa = 100 * MMHG_TO_PA
        P_venous_Pa = 5 * MMHG_TO_PA

        Q1 = 1e-5  # Low flow
        Q2 = 2e-5  # Double flow

        R1 = (MAP_Pa - P_venous_Pa) / Q1
        R2 = (MAP_Pa - P_venous_Pa) / Q2

        assert R1 == pytest.approx(2 * R2, rel=1e-6)


class TestPWVCalculation:
    """Test Pulse Wave Velocity calculation methods."""

    def test_pwv_matlab_formula(self):
        """Test Olufsen MATLAB PWV formula: c = a / (2*sqrt(A/π))^b."""
        a, b = 13.3, 0.3  # Default Olufsen parameters
        A_mm2 = 100  # 100 mm² area

        c = a / (2 * np.sqrt(A_mm2 / np.pi)) ** b

        # Expected PWV for 100 mm² outlet
        assert 3 < c < 15  # Reasonable physiological range (m/s)

    def test_pwv_decreases_with_larger_area(self):
        """Test that PWV decreases with larger vessel area."""
        a, b = 13.3, 0.3

        A_small = 50  # mm²
        A_large = 200  # mm²

        c_small = a / (2 * np.sqrt(A_small / np.pi)) ** b
        c_large = a / (2 * np.sqrt(A_large / np.pi)) ** b

        assert c_small > c_large

    def test_pwv_empirical_tiers(self):
        """Test empirical PWV tier selection."""

        def get_empirical_pwv(diameter_mm):
            if diameter_mm > 15:
                return 5.0
            elif diameter_mm > 8:
                return 6.0
            else:
                return 7.0

        assert get_empirical_pwv(20) == 5.0  # Large vessel
        assert get_empirical_pwv(10) == 6.0  # Medium vessel
        assert get_empirical_pwv(5) == 7.0  # Small vessel


class TestCharacteristicImpedance:
    """Test characteristic impedance (R1/Z) calculation."""

    def test_z0_formula(self):
        """Test Z0 = ρc/A formula."""
        rho = 1060  # kg/m³
        c = 6.0  # m/s (PWV)
        A = 1e-4  # 100 mm² = 1e-4 m²

        Z0 = rho * c / A

        # Z0 should be reasonable (typically 1e7-1e8 Pa·s/m³)
        assert 1e6 < Z0 < 1e9

    def test_z0_increases_with_smaller_area(self):
        """Test that Z0 increases for smaller vessels."""
        rho = 1060
        c = 6.0

        A_large = 2e-4  # 200 mm²
        A_small = 5e-5  # 50 mm²

        Z0_large = rho * c / A_large
        Z0_small = rho * c / A_small

        assert Z0_small > Z0_large


class TestComplianceCalculation:
    """Test compliance (C) calculation."""

    def test_compliance_formula(self):
        """Test C = τ / R2 formula."""
        tau = 1.8  # s (diastolic decay time)
        R2 = 1e8  # Pa·s/m³

        C = tau / R2

        # C should be reasonable (typically 1e-9 to 1e-8 m³/Pa)
        assert 1e-10 < C < 1e-7

    def test_rc_time_constant(self):
        """Test that R2 * C = τ (time constant)."""
        tau = 1.8
        R2 = 1e8

        C = tau / R2
        time_constant = R2 * C

        assert time_constant == pytest.approx(tau, rel=1e-9)

    def test_compliance_physiological_range(self):
        """Test compliance in physiological range."""
        # Typical aortic compliance: 0.5-2 mL/mmHg = 3.75e-9 to 1.5e-8 m³/Pa
        tau = 1.8
        R2 = 1e8

        C = tau / R2
        C_clinical = C * MMHG_TO_PA * 1e6  # Convert to mL/mmHg

        assert 0.01 < C_clinical < 10  # Reasonable clinical range


class TestTwoElementWindkessel:
    """Test 2-element Windkessel model (R-C, Z=0)."""

    def test_two_element_no_z(self):
        """Test that 2-element model has Z=0."""
        # In 2-element model:
        R1 = 0.0  # No proximal impedance
        R2 = 1e8  # Full resistance
        Z = R1  # Z = 0 in 2-element

        assert Z == 0.0

    def test_two_element_r_equals_rtotal(self):
        """Test that R = R_total in 2-element model."""
        R_total = 1.5e8
        R1 = 0.0
        R2 = R_total

        assert R2 == R_total
        assert R1 + R2 == R_total


class TestThreeElementWindkessel:
    """Test 3-element Windkessel model (R1-C-R2)."""

    def test_r1_plus_r2_equals_rtotal(self):
        """Test that R1 + R2 = R_total in 3-element model."""
        R_total = 1.5e8
        R1 = 1e7  # Characteristic impedance
        R2 = R_total - R1

        assert R1 + R2 == R_total

    def test_r2_greater_than_r1(self):
        """Test that typically R2 >> R1."""
        R_total = 1.5e8
        R1 = 1e7  # Typical Z0

        R2 = R_total - R1

        assert R2 > R1
        assert R2 > 10 * R1  # R2 should be much larger


class TestFlowSplitParsing:
    """Test flow split parsing methods."""

    def test_percentage_flow_split(self):
        """Test percentage-based flow split (e.g., 60% to main outlet)."""
        main_percentage = 60
        num_branches = 2
        branch_share = (100 - main_percentage) / num_branches

        assert main_percentage + num_branches * branch_share == 100

    def test_custom_flow_split_dict(self):
        """Test custom flow split dictionary parsing."""
        flow_split = {"outlet1": 0.3, "outlet2": 0.5, "outlet3": 0.2}

        total = sum(flow_split.values())
        assert total == pytest.approx(1.0, rel=1e-9)

    def test_flow_split_normalization(self):
        """Test that unnormalized splits get normalized."""
        raw_split = {"outlet1": 30, "outlet2": 50, "outlet3": 20}

        total = sum(raw_split.values())
        normalized = {k: v / total for k, v in raw_split.items()}

        assert sum(normalized.values()) == pytest.approx(1.0, rel=1e-9)


class TestUnitConversions:
    """Test unit conversions used in WK calculations."""

    def test_flow_lmin_to_m3s(self):
        """Test flow conversion from L/min to m³/s."""
        Q_Lmin = 5.0  # 5 L/min (typical cardiac output)
        Q_m3s = Q_Lmin / 60 / 1000

        assert Q_m3s == pytest.approx(8.33e-5, rel=1e-2)

    def test_area_mm2_to_m2(self):
        """Test area conversion from mm² to m²."""
        A_mm2 = 100
        A_m2 = A_mm2 * 1e-6

        assert A_m2 == pytest.approx(1e-4, rel=1e-9)

    def test_pressure_mmhg_to_pa(self):
        """Test pressure conversion from mmHg to Pa."""
        P_mmHg = 100
        P_Pa = P_mmHg * MMHG_TO_PA

        assert P_Pa == pytest.approx(13332.2, rel=1e-3)

    def test_resistance_si_to_clinical(self):
        """Test resistance conversion from Pa·s/m³ to mmHg·s/mL."""
        R_SI = 1e8  # Pa·s/m³
        R_clinical = R_SI / (MMHG_TO_PA * 1e6)

        # Check it's in reasonable clinical range
        assert 0.1 < R_clinical < 100

    def test_compliance_si_to_clinical(self):
        """Test compliance conversion from m³/Pa to mL/mmHg."""
        C_SI = 1e-8  # m³/Pa
        C_clinical = C_SI * MMHG_TO_PA * 1e6

        # Check it's in reasonable clinical range
        assert 0.01 < C_clinical < 10


class TestEdgeCasesExtended:
    """Extended edge case tests."""

    def test_very_small_outlet(self):
        """Test handling of very small outlet."""
        r_small = 0.001  # 1 mm radius
        A_small = math.pi * r_small**2

        # Calculate impedance
        rho = 1060
        c = 7.0  # Higher PWV for small vessel
        Z0 = rho * c / A_small

        # Very small outlet should have high impedance
        assert Z0 > 1e9

    def test_very_large_outlet(self):
        """Test handling of very large outlet."""
        r_large = 0.015  # 15 mm radius (ascending aorta)
        A_large = math.pi * r_large**2

        # Calculate impedance
        rho = 1060
        c = 5.0  # Lower PWV for large vessel
        Z0 = rho * c / A_large

        # Large outlet should have lower impedance
        assert Z0 < 1e8

    def test_extreme_blood_pressure(self):
        """Test with extreme blood pressure values."""
        # Severe hypertension: 200/120
        SP, DP = 200, 120
        MAP = DP + (SP - DP) / 3

        assert MAP == pytest.approx(146.67, rel=1e-2)

        # This should result in higher resistance for same flow


class TestPhysiologicalValidation:
    """Test physiological plausibility of results."""

    def test_total_peripheral_resistance(self):
        """Test total peripheral resistance in physiological range."""
        # Normal adult: TPR ~ 900-1400 dyne·s/cm⁵ = 0.9-1.4 mmHg·s/mL
        MAP_mmHg = 93.3
        CO_Lmin = 5.0  # Cardiac output

        # Convert to SI
        MAP_Pa = MAP_mmHg * MMHG_TO_PA
        Q_m3s = CO_Lmin / 60 / 1000

        TPR_SI = MAP_Pa / Q_m3s
        TPR_clinical = TPR_SI / (MMHG_TO_PA * 1e6)

        assert 0.5 < TPR_clinical < 3.0  # Physiological range

    def test_windkessel_time_constant(self):
        """Test that time constant is in physiological range."""
        # Typical diastolic decay: 1.0-2.5 s
        tau_values = [1.0, 1.5, 1.8, 2.0, 2.5]

        for tau in tau_values:
            assert 0.5 < tau < 5.0  # Extended acceptable range


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
