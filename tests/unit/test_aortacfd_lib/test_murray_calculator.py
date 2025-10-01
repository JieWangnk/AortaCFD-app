"""
Unit tests for Murray's Law Calculator.

Tests flow distribution calculation based on vessel geometry.
"""

import pytest
import math
from pathlib import Path
from src.aortacfd_lib.murray_calculator import MurrayCalculator


class TestMurrayExponentDetermination:
    """Test automatic Murray exponent selection."""

    def test_explicit_exponent_from_config(self, temp_case_dir):
        """Test using explicit exponent from config."""
        config = {
            "physics": {
                "murray_exponent": 2.5
            }
        }

        calculator = MurrayCalculator(str(temp_case_dir), config)
        assert calculator.murray_exponent == 2.5

    def test_default_exponent_when_no_geometry(self, temp_case_dir):
        """Test default exponent when geometry unavailable."""
        config = {}

        calculator = MurrayCalculator(str(temp_case_dir), config)
        # Should use default meta-analysis value
        assert calculator.murray_exponent == 2.39


class TestFlowRatioCalculation:
    """Test flow ratio calculation using Murray's Law."""

    @pytest.fixture
    def calculator(self, temp_case_dir):
        """Create calculator with default settings."""
        config = {"physics": {"murray_exponent": 3.0}}  # Classical Murray
        return MurrayCalculator(str(temp_case_dir), config)

    def test_calculate_murray_flow_ratios_equal_outlets(self, calculator):
        """Test flow ratios with equal outlet areas."""
        outlet_areas = {
            "outlet1": 1.0,
            "outlet2": 1.0,
            "outlet3": 1.0
        }

        ratios = calculator.calculate_murray_flow_ratios(outlet_areas)

        # Equal areas should give equal ratios
        assert len(ratios) == 3
        for outlet, ratio in ratios.items():
            assert abs(ratio - 1/3) < 0.01  # Approximately 33.3%

    def test_calculate_murray_flow_ratios_different_outlets(self, calculator):
        """Test flow ratios with different outlet areas."""
        # Murray's law: Q ∝ r^3 ∝ A^(3/2)
        # For areas: 4, 1, 1 (diameters: 2, 1, 1)
        # Flow ratios: 8, 1, 1 → normalized: 0.8, 0.1, 0.1
        outlet_areas = {
            "outlet1": 4.0,  # 2x diameter → 8x flow
            "outlet2": 1.0,
            "outlet3": 1.0
        }

        ratios = calculator.calculate_murray_flow_ratios(outlet_areas)

        # Check ratios sum to 1
        assert abs(sum(ratios.values()) - 1.0) < 0.001

        # Largest outlet should get most flow
        assert ratios["outlet1"] > ratios["outlet2"]
        assert ratios["outlet1"] > ratios["outlet3"]

        # Smaller outlets should be approximately equal
        assert abs(ratios["outlet2"] - ratios["outlet3"]) < 0.01

    def test_calculate_murray_flow_ratios_sum_to_one(self, calculator):
        """Test that flow ratios always sum to 1.0."""
        outlet_areas = {
            "outlet1": 2.5,
            "outlet2": 1.0,
            "outlet3": 0.5,
            "outlet4": 3.2
        }

        ratios = calculator.calculate_murray_flow_ratios(outlet_areas)

        total = sum(ratios.values())
        assert abs(total - 1.0) < 1e-6  # Very close to 1.0

    def test_calculate_murray_flow_ratios_preserves_keys(self, calculator):
        """Test that output keys match input keys."""
        outlet_areas = {
            "left_subclavian": 1.0,
            "right_subclavian": 1.2,
            "descending_aorta": 3.0
        }

        ratios = calculator.calculate_murray_flow_ratios(outlet_areas)

        assert set(ratios.keys()) == set(outlet_areas.keys())

    def test_calculate_murray_flow_ratios_empty_input(self, calculator):
        """Test handling of empty input."""
        outlet_areas = {}

        ratios = calculator.calculate_murray_flow_ratios(outlet_areas)

        assert ratios == {}

    def test_calculate_murray_flow_ratios_single_outlet(self, calculator):
        """Test with single outlet (gets 100% flow)."""
        outlet_areas = {"outlet1": 1.0}

        ratios = calculator.calculate_murray_flow_ratios(outlet_areas)

        assert len(ratios) == 1
        assert ratios["outlet1"] == 1.0


class TestMurrayExponentEffect:
    """Test effect of different Murray exponents."""

    def test_exponent_2_vs_3(self, temp_case_dir):
        """Test difference between exponent 2 and 3."""
        outlet_areas = {
            "outlet1": 4.0,  # 2x diameter
            "outlet2": 1.0
        }

        # Exponent = 2 (Q ∝ d^2)
        calc_2 = MurrayCalculator(str(temp_case_dir), {"physics": {"murray_exponent": 2.0}})
        ratios_2 = calc_2.calculate_murray_flow_ratios(outlet_areas)

        # Exponent = 3 (Q ∝ d^3, classical Murray)
        calc_3 = MurrayCalculator(str(temp_case_dir), {"physics": {"murray_exponent": 3.0}})
        ratios_3 = calc_3.calculate_murray_flow_ratios(outlet_areas)

        # With exponent 3, larger outlet should get more flow than with exponent 2
        assert ratios_3["outlet1"] > ratios_2["outlet1"]
        assert ratios_3["outlet2"] < ratios_2["outlet2"]

    def test_exponent_affects_distribution(self, temp_case_dir):
        """Test that exponent significantly affects distribution."""
        outlet_areas = {
            "large": 9.0,  # 3x diameter
            "small": 1.0
        }

        # Test range of exponents
        exponents = [2.0, 2.5, 3.0]
        ratios_large = []

        for exp in exponents:
            calc = MurrayCalculator(str(temp_case_dir), {"physics": {"murray_exponent": exp}})
            ratios = calc.calculate_murray_flow_ratios(outlet_areas)
            ratios_large.append(ratios["large"])

        # Larger exponent should give more flow to larger outlet
        assert ratios_large[0] < ratios_large[1] < ratios_large[2]


class TestAreaToFlowConversion:
    """Test conversion from areas to flow ratios."""

    @pytest.fixture
    def calculator(self, temp_case_dir):
        """Create calculator with exponent 3.0."""
        config = {"physics": {"murray_exponent": 3.0}}
        return MurrayCalculator(str(temp_case_dir), config)

    def test_area_to_diameter_relationship(self, calculator):
        """Test implicit area to diameter conversion in Murray's law."""
        # Area = π*r^2, so d = 2*sqrt(A/π)
        # For A = π, d should be 2
        area_pi = math.pi
        expected_diameter = 2.0

        # Verify this relationship through flow ratios
        outlet_areas = {
            "outlet1": area_pi,
            "outlet2": area_pi / 4  # 1/4 area → 1/2 diameter
        }

        ratios = calculator.calculate_murray_flow_ratios(outlet_areas)

        # With exponent 3: Q1/Q2 = (d1/d2)^3 = (2/1)^3 = 8
        # So ratio should be 8:1 → normalized to 8/9 and 1/9
        expected_ratio_1 = 8.0 / 9.0
        expected_ratio_2 = 1.0 / 9.0

        assert abs(ratios["outlet1"] - expected_ratio_1) < 0.01
        assert abs(ratios["outlet2"] - expected_ratio_2) < 0.01


class TestRobustness:
    """Test robustness and edge cases."""

    def test_handles_zero_area(self, temp_case_dir):
        """Test handling of zero area outlets."""
        config = {"physics": {"murray_exponent": 3.0}}
        calculator = MurrayCalculator(str(temp_case_dir), config)

        outlet_areas = {
            "outlet1": 1.0,
            "outlet2": 0.0  # Zero area
        }

        # Should handle gracefully (zero area gets zero flow)
        ratios = calculator.calculate_murray_flow_ratios(outlet_areas)

        assert ratios["outlet1"] == 1.0  # All flow to non-zero outlet
        assert ratios["outlet2"] == 0.0

    def test_handles_very_small_areas(self, temp_case_dir):
        """Test handling of very small areas."""
        config = {"physics": {"murray_exponent": 3.0}}
        calculator = MurrayCalculator(str(temp_case_dir), config)

        outlet_areas = {
            "outlet1": 1.0,
            "outlet2": 1e-10  # Very small area
        }

        ratios = calculator.calculate_murray_flow_ratios(outlet_areas)

        # Should still sum to 1
        assert abs(sum(ratios.values()) - 1.0) < 1e-6

        # Large outlet should get almost all flow
        assert ratios["outlet1"] > 0.999

    def test_handles_negative_area(self, temp_case_dir):
        """Test handling of negative areas (invalid input)."""
        config = {"physics": {"murray_exponent": 3.0}}
        calculator = MurrayCalculator(str(temp_case_dir), config)

        outlet_areas = {
            "outlet1": 1.0,
            "outlet2": -0.5  # Invalid negative area
        }

        # Should either raise ValueError or treat as zero
        try:
            ratios = calculator.calculate_murray_flow_ratios(outlet_areas)
            # If doesn't raise, negative should be treated as zero
            assert ratios["outlet2"] == 0.0
        except ValueError:
            # Valid to raise error for negative areas
            pass


@pytest.mark.unit
class TestMurrayLawPhysics:
    """Test physical correctness of Murray's law implementation."""

    def test_classical_murray_law(self, temp_case_dir):
        """Test classical Murray's law (n=3) for bifurcation."""
        # Classical Murray: d_parent^3 = d_daughter1^3 + d_daughter2^3
        # For equal daughters: d_parent = 2^(1/3) * d_daughter ≈ 1.26 * d_daughter

        config = {"physics": {"murray_exponent": 3.0}}
        calculator = MurrayCalculator(str(temp_case_dir), config)

        # Parent area = π*r^2, daughters have equal area
        parent_diameter = 1.26
        daughter_diameter = 1.0

        parent_area = math.pi * (parent_diameter / 2) ** 2
        daughter_area = math.pi * (daughter_diameter / 2) ** 2

        outlet_areas = {
            "daughter1": daughter_area,
            "daughter2": daughter_area
        }

        ratios = calculator.calculate_murray_flow_ratios(outlet_areas)

        # Equal daughters should split flow 50/50
        assert abs(ratios["daughter1"] - 0.5) < 0.01
        assert abs(ratios["daughter2"] - 0.5) < 0.01

    def test_physiological_aortic_bifurcation(self, temp_case_dir):
        """Test physiological aortic bifurcation with n=2.0."""
        # Aortic bifurcation typically uses n≈2 due to high pulsatility

        config = {"physics": {"murray_exponent": 2.0}}
        calculator = MurrayCalculator(str(temp_case_dir), config)

        # Typical aortic bifurcation: descending aorta gets more flow than iliacs
        outlet_areas = {
            "descending_aorta": 4.0,  # Larger
            "left_iliac": 1.0,
            "right_iliac": 1.0
        }

        ratios = calculator.calculate_murray_flow_ratios(outlet_areas)

        # Descending should get majority of flow
        assert ratios["descending_aorta"] > 0.5

        # Iliacs should be approximately equal
        assert abs(ratios["left_iliac"] - ratios["right_iliac"]) < 0.05
