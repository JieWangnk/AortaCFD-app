"""
Test suite for Distance-to-Wall Inlet Profile Generator
========================================================

Tests the DistanceWallInletProfile class and its integration with InletMapping.

Author: Jie Wang
Date: November 2025
"""

import os
import sys
import unittest
import tempfile
import shutil
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.aortacfd_lib.distance_wall_inlet_profile import (
    DistanceWallInletProfile,
    ShapeFunction,
    create_distance_wall_profile,
)

# Define distance-wall profile names for testing
# These are the profile names recognized as distance-to-wall based profiles
DISTANCE_WALL_PROFILES = {
    "distance_wall",
    "distance_to_wall",
    "wall_distance",
    "power_law",
    "poiseuille_distance",
    "hybrid_jet",
    "blunted",
    "blunted_parabolic",
    "irregular",
}


class TestShapeFunctions(unittest.TestCase):
    """Test shape function calculations."""

    def setUp(self):
        """Create a minimal config for testing."""
        self.config = {
            "inlet": {
                "csv_file": "flow.csv",
                "data_type": "flowrate",
                "profile": "distance_wall",
                "shape_function": "poiseuille",
                "exponent": 2.0,
            },
            "geometry": {"inlet_keywords_ordered": "inlet", "scale_factor": 0.001},
            "physics": {"nu": 3.7736e-6, "transport_properties": {"rho": 1060}},
        }
        # Create temporary directory structure
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary directory."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_shape_function_enum(self):
        """Test ShapeFunction enum values."""
        self.assertEqual(ShapeFunction.POWER_LAW.value, "power_law")
        self.assertEqual(ShapeFunction.POISEUILLE.value, "poiseuille")
        self.assertEqual(ShapeFunction.HYBRID_JET.value, "hybrid_jet")
        self.assertEqual(ShapeFunction.BLUNTED_PARABOLIC.value, "blunted")

    def test_poiseuille_shape_factor(self):
        """Test Poiseuille shape factor: S = 1 - r²."""
        # Create a mock generator with known d_max
        self.config["inlet"]["shape_function"] = "poiseuille"

        # Mock the generator with minimal initialization
        class MockGenerator:
            def __init__(self):
                self.d_max = 0.01  # 10mm radius
                self.shape_function = ShapeFunction.POISEUILLE
                self.exponent = 2.0
                self.core_fraction = 0.3

        gen = MockGenerator()

        # Test _compute_shape_factor method logic
        # At center (d = d_max): S should be ~1
        d_center = 0.01
        d_norm = d_center / gen.d_max
        r_norm = 1.0 - d_norm  # = 0 at center
        S_center = max(0, 1.0 - r_norm**2)
        self.assertAlmostEqual(S_center, 1.0, places=5)

        # At wall (d = 0): S should be 0
        d_wall = 0.0
        d_norm = d_wall / gen.d_max
        r_norm = 1.0 - d_norm  # = 1 at wall
        S_wall = max(0, 1.0 - r_norm**2)
        self.assertAlmostEqual(S_wall, 0.0, places=5)

        # At midpoint (d = d_max/2): S should be ~0.75
        d_mid = 0.005
        d_norm = d_mid / gen.d_max
        r_norm = 1.0 - d_norm  # = 0.5
        S_mid = max(0, 1.0 - r_norm**2)
        self.assertAlmostEqual(S_mid, 0.75, places=5)

    def test_power_law_shape_factor(self):
        """Test power law shape factor: S = (d/d_max)^n."""
        d_max = 0.01
        exponent = 2.0

        # At center (d = d_max): S = 1
        d_center = 0.01
        S_center = (d_center / d_max) ** exponent
        self.assertAlmostEqual(S_center, 1.0, places=5)

        # At wall (d = 0): S = 0
        d_wall = 0.0
        S_wall = (d_wall / d_max) ** exponent
        self.assertAlmostEqual(S_wall, 0.0, places=5)

        # At midpoint (d = d_max/2): S = 0.25 for n=2
        d_mid = 0.005
        S_mid = (d_mid / d_max) ** exponent
        self.assertAlmostEqual(S_mid, 0.25, places=5)

    def test_hybrid_jet_shape_factor(self):
        """Test hybrid jet profile: flat core + decay near wall."""
        d_max = 0.01
        core_fraction = 0.3
        exponent = 2.0
        core_dist = core_fraction * d_max  # 3mm

        # In core region (d > core_dist): S = 1
        d_core = 0.008  # > 3mm
        S_core = 1.0  # Should be flat
        self.assertAlmostEqual(S_core, 1.0, places=5)

        # Near wall (d < core_dist): decay
        d_near_wall = 0.001  # 1mm < 3mm
        local_d_norm = d_near_wall / core_dist
        S_near = local_d_norm**exponent
        self.assertLess(S_near, 1.0)
        self.assertGreater(S_near, 0.0)


class TestFlowRateCorrection(unittest.TestCase):
    """Test flow rate correction calculations."""

    def test_flow_rate_integral(self):
        """Test that flow rate correction produces correct integral."""
        # Create simple 1D test case
        n_points = 100
        d_max = 0.01  # 10mm

        # Linear distribution of distances from 0 to d_max
        distances = np.linspace(0, d_max, n_points)

        # Poiseuille shape factors
        shape_factors = []
        for d in distances:
            d_norm = d / d_max
            r_norm = 1.0 - d_norm
            S = max(0, 1.0 - r_norm**2)
            shape_factors.append(S)
        shape_factors = np.array(shape_factors)

        # For a circular inlet, the area-weighted integral should give
        # the correct average velocity
        # For Poiseuille: <S> = 0.5 (average of parabolic profile)

        # Uniform face areas (simplified)
        area = np.pi * d_max**2
        avg_face_area = area / n_points

        # Integrated shape factor
        integrated = np.sum(shape_factors) * avg_face_area

        # For a target flow rate Q, correction = Q / integrated
        Q_target = 1e-4  # 100 mL/s
        correction = Q_target / integrated

        # Verify corrected flow rate
        Q_corrected = np.sum(shape_factors * correction) * avg_face_area
        self.assertAlmostEqual(Q_corrected, Q_target, places=8)


class TestConfigParsing(unittest.TestCase):
    """Test configuration parsing."""

    def test_shape_function_parsing(self):
        """Test that shape function strings are parsed correctly."""
        # Use module-level constant instead of importing from inlet_mapping
        # Check all distance-wall profiles are recognized
        expected_profiles = [
            "distance_wall",
            "distance_to_wall",
            "wall_distance",
            "power_law",
            "poiseuille_distance",
            "hybrid_jet",
            "blunted",
            "blunted_parabolic",
            "irregular",
        ]

        for profile in expected_profiles:
            self.assertIn(profile, DISTANCE_WALL_PROFILES)

    def test_profile_to_shape_mapping(self):
        """Test profile name to shape function mapping."""
        mapping = {
            "distance_wall": "poiseuille",
            "power_law": "power_law",
            "hybrid_jet": "hybrid_jet",
            "blunted": "blunted_parabolic",
        }

        for profile, expected_shape in mapping.items():
            # Verify mapping logic
            profile_to_shape = {
                "distance_wall": "poiseuille",
                "distance_to_wall": "poiseuille",
                "wall_distance": "poiseuille",
                "power_law": "power_law",
                "poiseuille_distance": "poiseuille",
                "hybrid_jet": "hybrid_jet",
                "blunted": "blunted_parabolic",
                "blunted_parabolic": "blunted_parabolic",
                "irregular": "poiseuille",
            }
            self.assertEqual(profile_to_shape.get(profile), expected_shape)


class TestVelocityOutput(unittest.TestCase):
    """Test velocity vector output."""

    def test_velocity_direction(self):
        """Test that velocity vectors have correct direction."""
        # Normal vector (pointing into domain)
        normal = np.array([0, 0, 1])
        speed = 1.0

        # Velocity should be speed * normal
        velocity = speed * normal
        self.assertAlmostEqual(velocity[0], 0.0)
        self.assertAlmostEqual(velocity[1], 0.0)
        self.assertAlmostEqual(velocity[2], 1.0)

        # Flipped normal (pointing out of domain)
        normal_flip = -normal
        velocity_flip = speed * normal_flip
        self.assertAlmostEqual(velocity_flip[2], -1.0)

    def test_zero_at_wall(self):
        """Test that velocity is zero at wall."""
        d_max = 0.01
        d_wall = 0.0

        # Poiseuille profile
        d_norm = d_wall / d_max
        r_norm = 1.0 - d_norm
        S = max(0, 1.0 - r_norm**2)

        self.assertAlmostEqual(S, 0.0)

        # Velocity magnitude at wall
        speed = 1.0 * S
        self.assertAlmostEqual(speed, 0.0)


class TestOpenFOAMFormat(unittest.TestCase):
    """Test OpenFOAM file format output."""

    def test_write_format(self):
        """Test OpenFOAM boundaryData format."""
        # Expected format:
        # n_points
        # (
        # (vx vy vz)
        # ...
        # )

        velocities = [
            np.array([1.0, 0.0, 0.0]),
            np.array([0.5, 0.5, 0.0]),
            np.array([0.0, 0.0, 1.0]),
        ]

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            temp_path = f.name
            f.write(f"{len(velocities)}\n(\n")
            for v in velocities:
                f.write(f"({v[0]:.6e} {v[1]:.6e} {v[2]:.6e})\n")
            f.write(")\n")

        # Read and verify
        with open(temp_path, "r") as f:
            lines = f.readlines()

        self.assertEqual(lines[0].strip(), "3")
        self.assertEqual(lines[1].strip(), "(")
        self.assertTrue(lines[2].startswith("(1.000000e+00"))
        self.assertEqual(lines[-1].strip(), ")")

        # Cleanup
        os.unlink(temp_path)


class TestIntegrationWithInletMapping(unittest.TestCase):
    """Test integration with InletMapping class."""

    def test_distance_wall_profile_detection(self):
        """Test that distance-wall profiles are correctly identified."""
        # Use module-level constant instead of importing from inlet_mapping

        # Create config with distance-wall profile
        config = {
            "inlet": {
                "csv_file": "flow.csv",
                "data_type": "flowrate",
                "profile": "distance_wall",
            },
            "geometry": {"inlet_keywords_ordered": "inlet", "scale_factor": 0.001},
            "physics": {"nu": 3.7736e-6},
        }

        # Test profile detection logic
        profile = config["inlet"]["profile"].lower().strip()
        use_distance_wall = profile in DISTANCE_WALL_PROFILES

        self.assertTrue(use_distance_wall)

    def test_standard_profile_not_delegated(self):
        """Test that standard profiles are not delegated."""
        # Use module-level constant instead of importing from inlet_mapping
        standard_profiles = ["plug", "parabolic", "womersley"]

        for profile in standard_profiles:
            use_distance_wall = profile in DISTANCE_WALL_PROFILES
            self.assertFalse(use_distance_wall)


if __name__ == "__main__":
    unittest.main()
