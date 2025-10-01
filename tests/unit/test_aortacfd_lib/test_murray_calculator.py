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


class TestVesselTypeDetection:
    """Test automatic vessel type detection and exponent selection."""

    def test_large_vessel_detection(self, temp_case_dir):
        """Test detection of large vessels (>25mm) → exponent 2.0."""
        # Mock config without explicit exponent
        config = {
            "geometry": {
                "inlet_keywords_ordered": "inlet"
            }
        }

        # Create mock STL file and patch area calculation
        from unittest.mock import patch
        from pathlib import Path
        tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)
        (tri_surface / "inlet.stl").write_text("dummy")
        
        with patch.object(MurrayCalculator, '_calculate_stl_area', return_value=math.pi * (0.015)**2):
            calculator = MurrayCalculator(str(temp_case_dir), config)
            # Inlet diameter = 30mm → large vessel
            assert calculator.murray_exponent == 2.0

    def test_medium_large_vessel_detection(self, temp_case_dir):
        """Test detection of medium-large vessels (15-25mm) → exponent 2.2."""
        config = {
            "geometry": {
                "inlet_keywords_ordered": "inlet"
            }
        }

        from unittest.mock import patch
        from pathlib import Path
        tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)
        (tri_surface / "inlet.stl").write_text("dummy")
        
        with patch.object(MurrayCalculator, '_calculate_stl_area', return_value=math.pi * (0.010)**2):
            calculator = MurrayCalculator(str(temp_case_dir), config)
            # Inlet diameter = 20mm → medium-large vessel
            assert calculator.murray_exponent == 2.2

    def test_medium_vessel_detection(self, temp_case_dir):
        """Test detection of medium vessels (8-15mm) → exponent 2.39."""
        config = {
            "geometry": {
                "inlet_keywords_ordered": "inlet"
            }
        }

        from unittest.mock import patch
        with patch.object(MurrayCalculator, '_calculate_stl_area', return_value=math.pi * (0.005)**2):
            calculator = MurrayCalculator(str(temp_case_dir), config)
            # Inlet diameter = 10mm → medium vessel
            assert calculator.murray_exponent == 2.39

    def test_coronary_vessel_detection(self, temp_case_dir):
        """Test detection of coronary-sized vessels (4-8mm) → exponent 2.5."""
        config = {
            "geometry": {
                "inlet_keywords_ordered": "inlet"
            }
        }

        from unittest.mock import patch
        from pathlib import Path
        tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)
        (tri_surface / "inlet.stl").write_text("dummy")
        
        with patch.object(MurrayCalculator, '_calculate_stl_area', return_value=math.pi * (0.003)**2):
            calculator = MurrayCalculator(str(temp_case_dir), config)
            # Inlet diameter = 6mm → coronary vessel
            assert calculator.murray_exponent == 2.5

    def test_small_vessel_detection(self, temp_case_dir):
        """Test detection of small vessels (<4mm) → exponent 2.7."""
        config = {
            "geometry": {
                "inlet_keywords_ordered": "inlet"
            }
        }

        from unittest.mock import patch
        from pathlib import Path
        tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)
        (tri_surface / "inlet.stl").write_text("dummy")
        
        with patch.object(MurrayCalculator, '_calculate_stl_area', return_value=math.pi * (0.0015)**2):
            calculator = MurrayCalculator(str(temp_case_dir), config)
            # Inlet diameter = 3mm → small vessel
            assert calculator.murray_exponent == 2.7


class TestAreaExtraction:
    """Test outlet area extraction methods."""

    def test_extract_areas_from_config(self, temp_case_dir):
        """Test extracting outlet patches from config."""
        config = {
            "geometry": {
                "outlet_keywords_ordered": ["outlet1", "outlet2", "outlet3"]
            }
        }

        calculator = MurrayCalculator(str(temp_case_dir), config)

        # Patch the extraction methods to return known values
        from unittest.mock import patch
        with patch.object(calculator, '_extract_areas_from_checkmesh', return_value={}):
            with patch.object(calculator, '_estimate_outlet_area', side_effect=lambda x: 1e-4):
                areas = calculator.extract_outlet_areas_from_stl()

        # Should have 3 outlets from config
        assert len(areas) == 3
        assert "outlet1" in areas
        assert "outlet2" in areas
        assert "outlet3" in areas

    def test_fallback_to_default_outlets(self, temp_case_dir):
        """Test fallback to default outlet naming when config missing."""
        config = {}  # No geometry config

        calculator = MurrayCalculator(str(temp_case_dir), config)

        from unittest.mock import patch
        with patch.object(calculator, '_extract_areas_from_checkmesh', return_value={}):
            with patch.object(calculator, '_estimate_outlet_area', side_effect=lambda x: 1e-4):
                areas = calculator.extract_outlet_areas_from_stl()

        # Should use default outlet1, outlet2, outlet3, outlet4
        assert len(areas) == 4


class TestSTLFaceAreaEstimation:
    """Test STL bytes-per-face to area estimation."""

    def test_very_small_bytes_per_face(self, temp_case_dir):
        """Test estimation for very small bytes/face (<5)."""
        calculator = MurrayCalculator(str(temp_case_dir), {})

        area = calculator._estimate_face_area_from_stl_ratio(3.0)

        assert area == 5e-7  # 0.5 mm²

    def test_moderate_bytes_per_face(self, temp_case_dir):
        """Test estimation for moderate bytes/face (5-10)."""
        calculator = MurrayCalculator(str(temp_case_dir), {})

        area = calculator._estimate_face_area_from_stl_ratio(7.0)

        assert area == 1e-6  # 1 mm²

    def test_higher_bytes_per_face(self, temp_case_dir):
        """Test estimation for higher bytes/face (10-20)."""
        calculator = MurrayCalculator(str(temp_case_dir), {})

        area = calculator._estimate_face_area_from_stl_ratio(15.0)

        assert area == 2e-6  # 2 mm²

    def test_very_high_bytes_per_face(self, temp_case_dir):
        """Test estimation for very high bytes/face (>20)."""
        calculator = MurrayCalculator(str(temp_case_dir), {})

        area = calculator._estimate_face_area_from_stl_ratio(25.0)

        assert area == 5e-6  # 5 mm²


class TestFlowRatioCalculations:
    """Test detailed flow ratio calculations."""

    def test_area_to_radius_conversion(self, temp_case_dir):
        """Test correct conversion from area to radius."""
        config = {"physics": {"murray_exponent": 3.0}}
        calculator = MurrayCalculator(str(temp_case_dir), config)

        # Area = π*r², so for A=π, r should be 1
        outlet_areas = {
            "outlet1": math.pi * (1.0**2),  # r=1
            "outlet2": math.pi * (0.5**2)   # r=0.5
        }

        ratios = calculator.calculate_murray_flow_ratios(outlet_areas)

        # With exponent 3: Q1/Q2 = (r1/r2)^3 = (1/0.5)^3 = 8
        # Normalized: 8/9 and 1/9
        assert abs(ratios["outlet1"] - 8/9) < 0.01
        assert abs(ratios["outlet2"] - 1/9) < 0.01

    def test_extreme_area_ratios(self, temp_case_dir):
        """Test handling of extreme area ratios."""
        config = {"physics": {"murray_exponent": 3.0}}
        calculator = MurrayCalculator(str(temp_case_dir), config)

        outlet_areas = {
            "large": 100.0,  # Very large
            "tiny": 0.01     # Very small
        }

        ratios = calculator.calculate_murray_flow_ratios(outlet_areas)

        # Should still sum to 1
        assert abs(sum(ratios.values()) - 1.0) < 1e-6

        # Large outlet should get almost all flow
        assert ratios["large"] > 0.99

    def test_many_equal_outlets(self, temp_case_dir):
        """Test distribution among many equal outlets."""
        config = {"physics": {"murray_exponent": 3.0}}
        calculator = MurrayCalculator(str(temp_case_dir), config)

        # 10 equal outlets
        outlet_areas = {f"outlet{i}": 1.0 for i in range(10)}

        ratios = calculator.calculate_murray_flow_ratios(outlet_areas)

        # Each should get 10%
        for ratio in ratios.values():
            assert abs(ratio - 0.1) < 0.01


class TestExponentConfiguration:
    """Test Murray exponent configuration and defaults."""

    def test_explicit_config_overrides_auto_detection(self, temp_case_dir):
        """Test explicit exponent config takes precedence."""
        config = {
            "physics": {"murray_exponent": 2.8},
            "geometry": {"inlet_keywords_ordered": "inlet"}
        }

        # Even with STL that would suggest different exponent
        from unittest.mock import patch
        with patch.object(MurrayCalculator, '_calculate_stl_area', return_value=math.pi * (0.015)**2):
            calculator = MurrayCalculator(str(temp_case_dir), config)

            # Should use config value, not auto-detected
            assert calculator.murray_exponent == 2.8

    def test_auto_detection_fallback_on_error(self, temp_case_dir):
        """Test fallback to default when auto-detection fails."""
        config = {
            "geometry": {"inlet_keywords_ordered": "inlet"}
        }

        # Mock STL calculation to raise an error
        from unittest.mock import patch
        with patch.object(MurrayCalculator, '_calculate_stl_area', side_effect=Exception("STL error")):
            calculator = MurrayCalculator(str(temp_case_dir), config)

            # Should fallback to default 2.39
            assert calculator.murray_exponent == 2.39


class TestAreaCalculationHelpers:
    """Test helper methods for area calculation."""

    def test_get_stl_file_sizes(self, temp_case_dir):
        """Test STL file size retrieval."""
        # Create mock STL files
        from pathlib import Path
        tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)

        # Create dummy STL files
        (tri_surface / "outlet1.stl").write_text("dummy content 1")
        (tri_surface / "outlet2.stl").write_text("dummy content 2 longer")

        calculator = MurrayCalculator(str(temp_case_dir), {})
        sizes = calculator._get_stl_file_sizes()

        # Should find the STL files
        assert isinstance(sizes, dict)

    def test_estimate_outlet_area_fallback(self, temp_case_dir):
        """Test fallback outlet area estimation."""
        calculator = MurrayCalculator(str(temp_case_dir), {})

        # Should return reasonable area estimate
        area = calculator._estimate_outlet_area("outlet1")

        # Should be a positive number in reasonable range (mm² to cm²)
        assert area > 0
        assert area < 1.0  # Less than 1 m² (unrealistic for vessels)
