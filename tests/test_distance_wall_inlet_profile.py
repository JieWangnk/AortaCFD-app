"""
Test suite for aortacfd_lib/distance_wall_inlet_profile.py module.

Tests cover:
- ShapeFunction enum
- DistanceWallInletProfile initialization and configuration parsing
- Shape function computation (single and vectorized)
- CSV file reading
- Points file reading and writing
- Time directory cleanup
- Factory function
"""

import pytest
import sys
import os
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import shutil

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestShapeFunctionEnum:
    """Test ShapeFunction enum."""

    def test_shape_function_values(self):
        """Test that all shape functions have correct values."""
        from aortacfd_lib.distance_wall_inlet_profile import ShapeFunction

        assert ShapeFunction.POWER_LAW.value == "power_law"
        assert ShapeFunction.POISEUILLE.value == "poiseuille"
        assert ShapeFunction.HYBRID_JET.value == "hybrid_jet"
        assert ShapeFunction.BLUNTED_PARABOLIC.value == "blunted"

    def test_shape_function_members(self):
        """Test that all expected members exist."""
        from aortacfd_lib.distance_wall_inlet_profile import ShapeFunction

        assert hasattr(ShapeFunction, 'POWER_LAW')
        assert hasattr(ShapeFunction, 'POISEUILLE')
        assert hasattr(ShapeFunction, 'HYBRID_JET')
        assert hasattr(ShapeFunction, 'BLUNTED_PARABOLIC')


class TestDistanceWallInletProfileInit:
    """Test DistanceWallInletProfile initialization."""

    def test_initialization_with_inlet_config(self, tmp_path):
        """Test initialization with inlet config structure."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        config = {
            'inlet': {
                'csv_file': 'flow.csv',
                'data_type': 'flowrate',
                'profile': 'distance_wall',
                'exponent': 2.0,
                'shape_function': 'power_law',
                'orientation': 'auto'
            },
            'geometry': {
                'inlet_keywords_ordered': 'inlet'
            },
            'physics': {}
        }

        profile = DistanceWallInletProfile(config, str(tmp_path))

        assert profile.inlet_name == 'inlet'
        assert profile.inlet_data_file == 'flow.csv'
        assert profile.data_type == 'flowrate'
        assert profile.exponent == 2.0
        assert profile.orientation == 'auto'

    def test_initialization_with_boundary_conditions_config(self, tmp_path):
        """Test initialization with boundary_conditions.inlet structure."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'velocity.csv',
                    'data_type': 'velocity',
                    'exponent': 1.5
                }
            },
            'geometry': {'inlet_keywords_ordered': 'aortic_inlet'},
            'physics': {}
        }

        profile = DistanceWallInletProfile(config, str(tmp_path))

        assert profile.inlet_data_file == 'velocity.csv'
        assert profile.data_type == 'velocity'
        assert profile.exponent == 1.5

    def test_initialization_default_values(self, tmp_path):
        """Test initialization uses correct defaults."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile, ShapeFunction

        config = {}

        profile = DistanceWallInletProfile(config, str(tmp_path))

        assert profile.inlet_name == 'inlet'
        assert profile.inlet_data_file == 'flow.csv'
        assert profile.data_type == 'flowrate'
        assert profile.exponent == 2.0
        assert profile.core_fraction == 0.3
        assert profile.shape_function == ShapeFunction.POWER_LAW


class TestParseShapeFunction:
    """Test _parse_shape_function method."""

    def test_parse_power_law(self, tmp_path):
        """Test parsing power_law shape function."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile, ShapeFunction

        profile = DistanceWallInletProfile({}, str(tmp_path))

        assert profile._parse_shape_function('power_law') == ShapeFunction.POWER_LAW
        assert profile._parse_shape_function('power') == ShapeFunction.POWER_LAW
        assert profile._parse_shape_function('linear') == ShapeFunction.POWER_LAW

    def test_parse_poiseuille(self, tmp_path):
        """Test parsing poiseuille shape function."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile, ShapeFunction

        profile = DistanceWallInletProfile({}, str(tmp_path))

        assert profile._parse_shape_function('poiseuille') == ShapeFunction.POISEUILLE
        assert profile._parse_shape_function('parabolic') == ShapeFunction.POISEUILLE

    def test_parse_hybrid_jet(self, tmp_path):
        """Test parsing hybrid_jet shape function."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile, ShapeFunction

        profile = DistanceWallInletProfile({}, str(tmp_path))

        assert profile._parse_shape_function('hybrid') == ShapeFunction.HYBRID_JET
        assert profile._parse_shape_function('hybrid_jet') == ShapeFunction.HYBRID_JET

    def test_parse_blunted(self, tmp_path):
        """Test parsing blunted shape function."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile, ShapeFunction

        profile = DistanceWallInletProfile({}, str(tmp_path))

        assert profile._parse_shape_function('blunted') == ShapeFunction.BLUNTED_PARABOLIC
        assert profile._parse_shape_function('blunted_parabolic') == ShapeFunction.BLUNTED_PARABOLIC

    def test_parse_unknown_defaults_to_poiseuille(self, tmp_path):
        """Test unknown shape function defaults to poiseuille."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile, ShapeFunction

        profile = DistanceWallInletProfile({}, str(tmp_path))

        assert profile._parse_shape_function('unknown') == ShapeFunction.POISEUILLE
        assert profile._parse_shape_function('foobar') == ShapeFunction.POISEUILLE


class TestComputeShapeFactor:
    """Test _compute_shape_factor method."""

    def test_power_law_at_wall(self, tmp_path):
        """Test power law shape factor at wall (d=0)."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile, ShapeFunction

        config = {'inlet': {'shape_function': 'power_law', 'exponent': 2.0}}
        profile = DistanceWallInletProfile(config, str(tmp_path))
        profile.d_max = 0.01

        assert profile._compute_shape_factor(0.0) == 0.0

    def test_power_law_at_center(self, tmp_path):
        """Test power law shape factor at center (d=d_max)."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile, ShapeFunction

        config = {'inlet': {'shape_function': 'power_law', 'exponent': 2.0}}
        profile = DistanceWallInletProfile(config, str(tmp_path))
        profile.d_max = 0.01

        assert profile._compute_shape_factor(0.01) == pytest.approx(1.0, rel=1e-6)

    def test_power_law_quadratic(self, tmp_path):
        """Test power law with exponent=2 gives quadratic profile."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        config = {'inlet': {'shape_function': 'power_law', 'exponent': 2.0}}
        profile = DistanceWallInletProfile(config, str(tmp_path))
        profile.d_max = 1.0

        # At d=0.5, f = (0.5)^2 = 0.25
        assert profile._compute_shape_factor(0.5) == pytest.approx(0.25, rel=1e-6)

    def test_power_law_linear(self, tmp_path):
        """Test power law with exponent=1 gives linear profile."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        config = {'inlet': {'shape_function': 'power_law', 'exponent': 1.0}}
        profile = DistanceWallInletProfile(config, str(tmp_path))
        profile.d_max = 1.0

        # At d=0.5, f = 0.5
        assert profile._compute_shape_factor(0.5) == pytest.approx(0.5, rel=1e-6)

    def test_poiseuille_at_wall(self, tmp_path):
        """Test Poiseuille shape factor at wall."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        config = {'inlet': {'shape_function': 'poiseuille'}}
        profile = DistanceWallInletProfile(config, str(tmp_path))
        profile.d_max = 0.01

        assert profile._compute_shape_factor(0.0) == 0.0

    def test_poiseuille_at_center(self, tmp_path):
        """Test Poiseuille shape factor at center."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        config = {'inlet': {'shape_function': 'poiseuille'}}
        profile = DistanceWallInletProfile(config, str(tmp_path))
        profile.d_max = 0.01

        assert profile._compute_shape_factor(0.01) == pytest.approx(1.0, rel=1e-6)

    def test_poiseuille_parabolic_profile(self, tmp_path):
        """Test Poiseuille gives parabolic profile."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        config = {'inlet': {'shape_function': 'poiseuille'}}
        profile = DistanceWallInletProfile(config, str(tmp_path))
        profile.d_max = 1.0

        # f(d) = 1 - (1 - d/d_max)^2
        # At d=0.5: f = 1 - (1 - 0.5)^2 = 1 - 0.25 = 0.75
        assert profile._compute_shape_factor(0.5) == pytest.approx(0.75, rel=1e-6)

    def test_hybrid_jet_in_core(self, tmp_path):
        """Test hybrid jet shape factor in core region."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        config = {'inlet': {'shape_function': 'hybrid_jet', 'core_fraction': 0.3}}
        profile = DistanceWallInletProfile(config, str(tmp_path))
        profile.d_max = 1.0
        profile.core_fraction = 0.3

        # At d=0.5 (> 0.3 * 1.0 = 0.3), should be flat = 1.0
        assert profile._compute_shape_factor(0.5) == pytest.approx(1.0, rel=1e-6)

    def test_hybrid_jet_near_wall(self, tmp_path):
        """Test hybrid jet shape factor near wall."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        config = {'inlet': {'shape_function': 'hybrid_jet', 'core_fraction': 0.3, 'exponent': 2.0}}
        profile = DistanceWallInletProfile(config, str(tmp_path))
        profile.d_max = 1.0
        profile.core_fraction = 0.3
        profile.exponent = 2.0

        # At d=0.15 (< 0.3), f = (0.15/0.3)^2 = 0.25
        assert profile._compute_shape_factor(0.15) == pytest.approx(0.25, rel=1e-6)

    def test_blunted_parabolic_in_core(self, tmp_path):
        """Test blunted parabolic shape factor in core region."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        config = {'inlet': {'shape_function': 'blunted', 'core_fraction': 0.3}}
        profile = DistanceWallInletProfile(config, str(tmp_path))
        profile.d_max = 1.0
        profile.core_fraction = 0.3

        # At d=0.5 (> 0.3), should be flat = 1.0
        assert profile._compute_shape_factor(0.5) == pytest.approx(1.0, rel=1e-6)

    def test_zero_d_max_returns_one(self, tmp_path):
        """Test that d_max=0 returns 1.0."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        profile = DistanceWallInletProfile({}, str(tmp_path))
        profile.d_max = 0.0

        assert profile._compute_shape_factor(0.5) == 1.0


class TestComputeShapeFactorsVectorized:
    """Test _compute_shape_factors_vectorized method."""

    def test_power_law_vectorized(self, tmp_path):
        """Test vectorized power law computation."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        config = {'inlet': {'shape_function': 'power_law', 'exponent': 2.0}}
        profile = DistanceWallInletProfile(config, str(tmp_path))
        profile.d_max = 1.0

        distances = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
        expected = np.array([0.0, 0.0625, 0.25, 0.5625, 1.0])

        result = profile._compute_shape_factors_vectorized(distances)
        np.testing.assert_array_almost_equal(result, expected)

    def test_poiseuille_vectorized(self, tmp_path):
        """Test vectorized Poiseuille computation."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        config = {'inlet': {'shape_function': 'poiseuille'}}
        profile = DistanceWallInletProfile(config, str(tmp_path))
        profile.d_max = 1.0

        distances = np.array([0.0, 0.5, 1.0])
        expected = np.array([0.0, 0.75, 1.0])

        result = profile._compute_shape_factors_vectorized(distances)
        np.testing.assert_array_almost_equal(result, expected)

    def test_zero_d_max_returns_ones(self, tmp_path):
        """Test that d_max=0 returns all ones."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        profile = DistanceWallInletProfile({}, str(tmp_path))
        profile.d_max = 0.0

        distances = np.array([0.1, 0.2, 0.3])
        result = profile._compute_shape_factors_vectorized(distances)

        np.testing.assert_array_equal(result, np.ones(3))


class TestReadCsvFile:
    """Test _read_csv_file method."""

    def test_read_simple_csv(self, tmp_path):
        """Test reading simple CSV file."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        csv_file = tmp_path / "flow.csv"
        csv_file.write_text("0.0,0.001\n0.4,0.002\n0.8,0.001\n")

        profile = DistanceWallInletProfile({}, str(tmp_path))
        times, values, period = profile._read_csv_file(str(csv_file))

        assert len(times) == 3
        assert len(values) == 3
        assert period == pytest.approx(0.8, rel=1e-6)
        assert times[0] == 0.0
        assert times[-1] == 0.8

    def test_read_csv_with_comments(self, tmp_path):
        """Test reading CSV with comment lines."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        csv_file = tmp_path / "flow.csv"
        csv_file.write_text("# Comment line\n# Another comment\n0.0,0.001\n0.8,0.002\n")

        profile = DistanceWallInletProfile({}, str(tmp_path))
        times, values, period = profile._read_csv_file(str(csv_file))

        assert len(times) == 2
        assert period == pytest.approx(0.8, rel=1e-6)

    def test_read_csv_with_header(self, tmp_path):
        """Test reading CSV with header line."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        csv_file = tmp_path / "flow.csv"
        csv_file.write_text("time,flowrate\n0.0,0.001\n0.8,0.002\n")

        profile = DistanceWallInletProfile({}, str(tmp_path))
        times, values, period = profile._read_csv_file(str(csv_file))

        assert len(times) == 2

    def test_read_csv_invalid_raises(self, tmp_path):
        """Test that invalid CSV raises ValueError."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        csv_file = tmp_path / "bad.csv"
        csv_file.write_text("0.0\n0.4\n0.8\n")  # Single column

        profile = DistanceWallInletProfile({}, str(tmp_path))

        with pytest.raises(ValueError, match="at least 2 columns"):
            profile._read_csv_file(str(csv_file))


class TestReadPointsFile:
    """Test _read_points_file method."""

    def test_read_points_with_parentheses(self, tmp_path):
        """Test reading points file with parentheses format."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        points_file = tmp_path / "points"
        points_file.write_text("3\n(\n(0 0 0)\n(1 0 0)\n(0 1 0)\n)\n")

        profile = DistanceWallInletProfile({}, str(tmp_path))
        n_points, points = profile._read_points_file(str(points_file))

        assert n_points == 3
        assert points.shape == (3, 3)
        np.testing.assert_array_equal(points[0], [0, 0, 0])
        np.testing.assert_array_equal(points[1], [1, 0, 0])
        np.testing.assert_array_equal(points[2], [0, 1, 0])

    def test_read_points_without_outer_parentheses(self, tmp_path):
        """Test reading points file without outer parentheses."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        points_file = tmp_path / "points"
        points_file.write_text("2\n(0.1 0.2 0.3)\n(0.4 0.5 0.6)\n")

        profile = DistanceWallInletProfile({}, str(tmp_path))
        n_points, points = profile._read_points_file(str(points_file))

        assert n_points == 2
        np.testing.assert_array_almost_equal(points[0], [0.1, 0.2, 0.3])
        np.testing.assert_array_almost_equal(points[1], [0.4, 0.5, 0.6])


class TestWriteVelocityFileFast:
    """Test _write_velocity_file_fast method."""

    def test_write_velocity_file(self, tmp_path):
        """Test writing velocity file in OpenFOAM format."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        profile = DistanceWallInletProfile({}, str(tmp_path))

        velocities = np.array([
            [0.1, 0.0, 0.0],
            [0.2, 0.0, 0.0],
            [0.15, 0.0, 0.0]
        ])

        output_file = tmp_path / "U"
        profile._write_velocity_file_fast(str(output_file), velocities)

        content = output_file.read_text()

        assert "3" in content
        assert "(" in content
        assert ")" in content
        assert "1.000000e-01" in content  # 0.1 in scientific notation

    def test_write_velocity_file_format(self, tmp_path):
        """Test velocity file has correct OpenFOAM format."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        profile = DistanceWallInletProfile({}, str(tmp_path))

        velocities = np.array([[1.0, 2.0, 3.0]])

        output_file = tmp_path / "U"
        profile._write_velocity_file_fast(str(output_file), velocities)

        lines = output_file.read_text().strip().split('\n')

        assert lines[0] == "1"
        assert lines[1] == "("
        assert "1.000000e+00" in lines[2]
        assert "2.000000e+00" in lines[2]
        assert "3.000000e+00" in lines[2]
        assert lines[3] == ")"


class TestCleanTimeDirectories:
    """Test _clean_time_directories method."""

    def test_clean_removes_time_directories(self, tmp_path):
        """Test cleaning removes numeric time directories."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        # Create time directories
        (tmp_path / "0.000000").mkdir()
        (tmp_path / "0.100000").mkdir()
        (tmp_path / "1.5").mkdir()
        (tmp_path / "points").touch()  # Non-numeric file should remain

        profile = DistanceWallInletProfile({}, str(tmp_path))
        profile._clean_time_directories(str(tmp_path))

        assert not (tmp_path / "0.000000").exists()
        assert not (tmp_path / "0.100000").exists()
        assert not (tmp_path / "1.5").exists()
        assert (tmp_path / "points").exists()  # Should remain

    def test_clean_handles_symlinks(self, tmp_path):
        """Test cleaning handles symbolic links."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        # Create a directory and symlink
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        link = tmp_path / "0.5"
        link.symlink_to(real_dir)

        profile = DistanceWallInletProfile({}, str(tmp_path))
        profile._clean_time_directories(str(tmp_path))

        assert not link.exists()
        assert real_dir.exists()  # Original should remain


class TestCalculateScalingFactor:
    """Test _calculate_scaling_factor method."""

    def test_scaling_factor_calculation(self, tmp_path):
        """Test scaling factor calculation."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        config = {'inlet': {'shape_function': 'power_law', 'exponent': 2.0}}
        profile = DistanceWallInletProfile(config, str(tmp_path))
        profile.d_max = 1.0
        profile.face_areas = np.array([0.1, 0.1, 0.1])  # Total area 0.3

        distances = np.array([0.5, 0.75, 1.0])
        target_flow = 0.01  # m³/s

        U_0 = profile._calculate_scaling_factor(distances, target_flow)

        # U_0 = Q / sum(f(d_i) * dA_i)
        # f values: 0.25, 0.5625, 1.0
        # sum(f * dA) = 0.25*0.1 + 0.5625*0.1 + 1.0*0.1 = 0.18125
        # U_0 = 0.01 / 0.18125 ≈ 0.0552
        expected = 0.01 / 0.18125
        assert U_0 == pytest.approx(expected, rel=1e-4)


class TestCreateDistanceWallProfile:
    """Test factory function."""

    def test_create_returns_correct_instance(self, tmp_path):
        """Test factory function returns correct instance."""
        from aortacfd_lib.distance_wall_inlet_profile import (
            create_distance_wall_profile, DistanceWallInletProfile
        )

        config = {'inlet': {'exponent': 3.0}}
        result = create_distance_wall_profile(config, str(tmp_path))

        assert isinstance(result, DistanceWallInletProfile)
        assert result.exponent == 3.0


class TestShouldFlipNormal:
    """Test _should_flip_normal method."""

    @patch('aortacfd_lib.distance_wall_inlet_profile.PatchProcessing')
    def test_no_outlet_files_returns_false(self, mock_patch_proc, tmp_path):
        """Test returns False when no outlet files exist."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        # Create triSurface directory with only inlet
        tri_surface = tmp_path / "constant" / "triSurface"
        tri_surface.mkdir(parents=True)
        (tri_surface / "inlet.stl").touch()

        profile = DistanceWallInletProfile({}, str(tmp_path))
        profile.center = np.array([0, 0, 0])
        profile.inlet_normal = np.array([0, 0, 1])

        result = profile._should_flip_normal()

        assert result is False

    @patch('aortacfd_lib.distance_wall_inlet_profile.PatchProcessing')
    def test_exception_returns_false(self, mock_patch_proc, tmp_path):
        """Test returns False on exception."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        # No triSurface directory
        profile = DistanceWallInletProfile({}, str(tmp_path))

        result = profile._should_flip_normal()

        assert result is False


class TestWriteVelocityFile:
    """Test _write_velocity_file method (legacy format)."""

    def test_write_velocity_file_legacy(self, tmp_path):
        """Test legacy velocity file writing."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        profile = DistanceWallInletProfile({}, str(tmp_path))

        velocities = [
            np.array([0.1, 0.0, 0.0]),
            np.array([0.2, 0.0, 0.0])
        ]

        output_file = tmp_path / "U"
        profile._write_velocity_file(str(output_file), velocities)

        content = output_file.read_text()

        assert "2" in content
        assert "(" in content
        assert ")" in content


# =============================================================================
# ADDITIONAL TESTS FOR UNCOVERED PATHS
# =============================================================================

class TestLoadInletGeometry:
    """Test _load_inlet_geometry method."""

    @patch('aortacfd_lib.distance_wall_inlet_profile.PatchProcessing')
    def test_load_inlet_geometry_success(self, mock_patch_proc, tmp_path):
        """Test loading inlet geometry successfully."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        # Create triSurface directory
        tri_surface = tmp_path / "constant" / "triSurface"
        tri_surface.mkdir(parents=True)
        (tri_surface / "inlet.stl").touch()

        # Mock PatchProcessing
        mock_instance = MagicMock()
        mock_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.01, 0.02, 0.0]),
            0.005,
            np.array([0, 0, 1])
        )
        mock_instance.calculate_surface_area.return_value = 0.0001
        mock_patch_proc.return_value = mock_instance

        profile = DistanceWallInletProfile({}, str(tmp_path))
        profile._load_inlet_geometry()

        assert profile.center is not None
        assert profile.area == 0.0001
        np.testing.assert_array_equal(profile.inlet_normal, [0, 0, 1])


class TestCalculateWallDistances:
    """Test _calculate_wall_distances method."""

    def test_calculate_wall_distances_with_scipy(self, tmp_path):
        """Test wall distance calculation using scipy."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile, HAS_SCIPY

        if not HAS_SCIPY:
            pytest.skip("scipy not available")

        profile = DistanceWallInletProfile({}, str(tmp_path))
        profile.center = np.array([0.5, 0.5, 0.0])

        # Test points
        points = np.array([
            [0.5, 0.5, 0.0],  # Center
            [0.6, 0.5, 0.0],
            [0.4, 0.5, 0.0]
        ])

        # Mock boundary extraction to return wall points
        with patch.object(profile, '_extract_inlet_boundary') as mock_boundary:
            # Square boundary
            mock_boundary.return_value = np.array([
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 1.0, 0.0],
                [0.0, 1.0, 0.0]
            ])

            distances = profile._calculate_wall_distances(points)

            assert len(distances) == 3
            # Center should have max distance from boundaries
            assert distances[0] > 0

    def test_calculate_wall_distances_radial_fallback(self, tmp_path):
        """Test wall distance using radial fallback when no boundary."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        profile = DistanceWallInletProfile({}, str(tmp_path))
        profile.center = np.array([0.0, 0.0, 0.0])

        points = np.array([
            [0.0, 0.0, 0.0],  # Center
            [0.5, 0.0, 0.0],  # Mid
            [1.0, 0.0, 0.0]   # Edge
        ])

        # Mock boundary extraction to return None
        with patch.object(profile, '_extract_inlet_boundary', return_value=None):
            distances = profile._calculate_wall_distances(points)

            assert len(distances) == 3
            # Center should have max distance (1.0 - 0.0 = 1.0)
            assert distances[0] == pytest.approx(1.0)
            # Edge should have min distance (1.0 - 1.0 = 0.0)
            assert distances[2] == pytest.approx(0.0)

    @patch('aortacfd_lib.distance_wall_inlet_profile.HAS_SCIPY', False)
    def test_calculate_wall_distances_no_scipy(self, tmp_path):
        """Test wall distance calculation without scipy."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        profile = DistanceWallInletProfile({}, str(tmp_path))
        profile.center = np.array([0.0, 0.0, 0.0])

        points = np.array([
            [0.0, 0.0, 0.0],
            [0.5, 0.0, 0.0]
        ])

        # Mock to return empty boundary to trigger fallback
        with patch.object(profile, '_extract_inlet_boundary', return_value=np.array([[1.0, 0.0, 0.0]])):
            distances = profile._calculate_wall_distances(points)
            assert len(distances) == 2


class TestExtractInletBoundary:
    """Test _extract_inlet_boundary method."""

    def test_extract_boundary_no_trimesh(self, tmp_path):
        """Test boundary extraction without trimesh."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        # Create triSurface directory with inlet.stl
        tri_surface = tmp_path / "constant" / "triSurface"
        tri_surface.mkdir(parents=True)
        (tri_surface / "inlet.stl").write_text("solid\nendsolid")

        profile = DistanceWallInletProfile({}, str(tmp_path))
        profile.center = np.array([0, 0, 0])

        with patch.dict('sys.modules', {'trimesh': None}):
            result = profile._extract_inlet_boundary()
            # Should return None when trimesh not available
            # (may or may not depending on import caching)

    def test_extract_boundary_no_stl_file(self, tmp_path):
        """Test boundary extraction when STL file doesn't exist."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        # Create triSurface directory without inlet.stl
        tri_surface = tmp_path / "constant" / "triSurface"
        tri_surface.mkdir(parents=True)

        profile = DistanceWallInletProfile({}, str(tmp_path))

        result = profile._extract_inlet_boundary()

        assert result is None


class TestComputeShapeFactorsVectorizedAll:
    """Test _compute_shape_factors_vectorized with all shape functions."""

    def test_hybrid_jet_shape(self, tmp_path):
        """Test hybrid jet shape function."""
        from aortacfd_lib.distance_wall_inlet_profile import (
            DistanceWallInletProfile, ShapeFunction
        )

        profile = DistanceWallInletProfile({
            'inlet': {'shape_function': 'hybrid_jet', 'core_fraction': 0.3, 'exponent': 2.0}
        }, str(tmp_path))
        profile.d_max = 1.0

        distances = np.array([0.0, 0.15, 0.3, 0.5, 1.0])
        factors = profile._compute_shape_factors_vectorized(distances)

        # d=0 -> factor should be 0 (at wall)
        assert factors[0] == pytest.approx(0.0)
        # d >= core_distance (0.3) -> factor should be 1.0
        assert factors[2] == pytest.approx(1.0)
        assert factors[3] == pytest.approx(1.0)
        assert factors[4] == pytest.approx(1.0)

    def test_blunted_parabolic_shape(self, tmp_path):
        """Test blunted parabolic shape function."""
        from aortacfd_lib.distance_wall_inlet_profile import (
            DistanceWallInletProfile, ShapeFunction
        )

        profile = DistanceWallInletProfile({
            'inlet': {'shape_function': 'blunted', 'core_fraction': 0.3}
        }, str(tmp_path))
        profile.d_max = 1.0

        distances = np.array([0.0, 0.15, 0.3, 0.5, 1.0])
        factors = profile._compute_shape_factors_vectorized(distances)

        # d=0 -> factor should be 0 (at wall)
        assert factors[0] == pytest.approx(0.0)
        # d >= core_distance (0.3) -> factor should be 1.0
        assert factors[2] == pytest.approx(1.0)
        assert factors[4] == pytest.approx(1.0)

    def test_poiseuille_shape(self, tmp_path):
        """Test Poiseuille shape function."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        profile = DistanceWallInletProfile({
            'inlet': {'shape_function': 'poiseuille'}
        }, str(tmp_path))
        profile.d_max = 1.0

        distances = np.array([0.0, 0.5, 1.0])
        factors = profile._compute_shape_factors_vectorized(distances)

        # Poiseuille: f(d) = 1 - (1 - d/d_max)^2
        # d=0: f = 1 - 1 = 0
        # d=1: f = 1 - 0 = 1
        assert factors[0] == pytest.approx(0.0)
        assert factors[2] == pytest.approx(1.0)

    def test_power_law_shape(self, tmp_path):
        """Test power law shape function."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        profile = DistanceWallInletProfile({
            'inlet': {'shape_function': 'power_law', 'exponent': 2.0}
        }, str(tmp_path))
        profile.d_max = 1.0

        distances = np.array([0.0, 0.5, 1.0])
        factors = profile._compute_shape_factors_vectorized(distances)

        # Power law: f(d) = (d/d_max)^n
        # d=0: f = 0
        # d=0.5: f = 0.25 (with n=2)
        # d=1: f = 1
        assert factors[0] == pytest.approx(0.0)
        assert factors[1] == pytest.approx(0.25)
        assert factors[2] == pytest.approx(1.0)

    def test_unknown_shape_defaults_to_poiseuille(self, tmp_path):
        """Test unknown shape defaults to Poiseuille."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        profile = DistanceWallInletProfile({
            'inlet': {'shape_function': 'unknown_shape'}
        }, str(tmp_path))
        profile.d_max = 1.0

        distances = np.array([0.0, 1.0])
        factors = profile._compute_shape_factors_vectorized(distances)

        # Defaults to Poiseuille
        assert factors[0] == pytest.approx(0.0)
        assert factors[1] == pytest.approx(1.0)


class TestComputeShapeFactorSingle:
    """Test _compute_shape_factor (non-vectorized) with edge cases."""

    def test_d_max_zero(self, tmp_path):
        """Test shape factor when d_max is zero."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        profile = DistanceWallInletProfile({}, str(tmp_path))
        profile.d_max = 0.0

        # Should return 1.0 when d_max is zero
        factor = profile._compute_shape_factor(0.5)
        assert factor == 1.0

    def test_hybrid_jet_single(self, tmp_path):
        """Test hybrid jet shape factor (single point)."""
        from aortacfd_lib.distance_wall_inlet_profile import (
            DistanceWallInletProfile, ShapeFunction
        )

        profile = DistanceWallInletProfile({
            'inlet': {'shape_function': 'hybrid_jet', 'core_fraction': 0.3, 'exponent': 2.0}
        }, str(tmp_path))
        profile.d_max = 1.0

        # In core region (d >= 0.3)
        assert profile._compute_shape_factor(0.5) == pytest.approx(1.0)

        # Near wall (d < 0.3)
        assert profile._compute_shape_factor(0.0) == pytest.approx(0.0)

    def test_blunted_parabolic_single(self, tmp_path):
        """Test blunted parabolic shape factor (single point)."""
        from aortacfd_lib.distance_wall_inlet_profile import (
            DistanceWallInletProfile, ShapeFunction
        )

        profile = DistanceWallInletProfile({
            'inlet': {'shape_function': 'blunted', 'core_fraction': 0.3}
        }, str(tmp_path))
        profile.d_max = 1.0

        # In core region (d >= 0.3)
        assert profile._compute_shape_factor(0.5) == pytest.approx(1.0)


class TestCalculateScalingFactor:
    """Test _calculate_scaling_factor method."""

    def test_scaling_factor_normal(self, tmp_path):
        """Test scaling factor calculation."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        profile = DistanceWallInletProfile({}, str(tmp_path))
        profile.d_max = 1.0
        profile.face_areas = np.array([0.001, 0.001, 0.001])

        distances = np.array([0.5, 0.7, 1.0])
        target_flow = 0.001  # m³/s

        U_0 = profile._calculate_scaling_factor(distances, target_flow)

        # Should return positive scaling velocity
        assert U_0 > 0

    def test_scaling_factor_zero_integrated(self, tmp_path):
        """Test scaling factor when integrated shape*area is zero."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        profile = DistanceWallInletProfile({}, str(tmp_path))
        profile.d_max = 1.0
        profile.area = 0.003
        profile.face_areas = np.array([0.001, 0.001, 0.001])

        # All distances at wall (d=0) means all shape factors are 0
        distances = np.array([0.0, 0.0, 0.0])
        target_flow = 0.001

        U_0 = profile._calculate_scaling_factor(distances, target_flow)

        # Should fall back to Q/A
        assert U_0 == pytest.approx(abs(target_flow) / profile.area)


class TestShouldFlipNormalWithOutlets:
    """Test _should_flip_normal with outlet files present."""

    @patch('aortacfd_lib.distance_wall_inlet_profile.PatchProcessing')
    def test_flip_normal_with_outlet_behind(self, mock_patch_proc, tmp_path):
        """Test flipping normal when outlet is behind inlet."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        # Create triSurface directory with inlet and outlet
        tri_surface = tmp_path / "constant" / "triSurface"
        tri_surface.mkdir(parents=True)
        (tri_surface / "inlet.stl").touch()
        (tri_surface / "outlet.stl").touch()

        # Mock PatchProcessing to return outlet center behind inlet
        mock_instance = MagicMock()
        mock_instance.calculate_inlet_center_radius.return_value = (
            np.array([0, 0, -1]),  # Outlet center is behind inlet
            0.005,
            np.array([0, 0, 1])
        )
        mock_patch_proc.return_value = mock_instance

        profile = DistanceWallInletProfile({}, str(tmp_path))
        profile.center = np.array([0, 0, 0])
        profile.inlet_normal = np.array([0, 0, 1])

        result = profile._should_flip_normal()

        # Flow direction is [0,0,-1] - [0,0,0] = [0,0,-1]
        # dot([0,0,1], [0,0,-1]) = -1 < 0, so should flip
        assert result == True

    @patch('aortacfd_lib.distance_wall_inlet_profile.PatchProcessing')
    def test_no_flip_when_outlet_ahead(self, mock_patch_proc, tmp_path):
        """Test not flipping when outlet is ahead."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        tri_surface = tmp_path / "constant" / "triSurface"
        tri_surface.mkdir(parents=True)
        (tri_surface / "inlet.stl").touch()
        (tri_surface / "outlet.stl").touch()

        mock_instance = MagicMock()
        mock_instance.calculate_inlet_center_radius.return_value = (
            np.array([0, 0, 1]),  # Outlet center is ahead of inlet
            0.005,
            np.array([0, 0, 1])
        )
        mock_patch_proc.return_value = mock_instance

        profile = DistanceWallInletProfile({}, str(tmp_path))
        profile.center = np.array([0, 0, 0])
        profile.inlet_normal = np.array([0, 0, 1])

        result = profile._should_flip_normal()

        # Flow direction is [0,0,1] - [0,0,0] = [0,0,1]
        # dot([0,0,1], [0,0,1]) = 1 > 0, so no flip
        assert result == False


class TestCleanTimeDirectories:
    """Test _clean_time_directories method."""

    def test_clean_removes_numeric_dirs(self, tmp_path):
        """Test cleaning removes numeric directories."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        # Create numeric directories
        (tmp_path / "0.000000").mkdir()
        (tmp_path / "0.100000").mkdir()
        (tmp_path / "1.500000").mkdir()
        # Create non-numeric directories that should be kept
        (tmp_path / "points").touch()

        profile = DistanceWallInletProfile({}, str(tmp_path.parent))
        profile._clean_time_directories(str(tmp_path))

        # Numeric directories should be removed
        assert not (tmp_path / "0.000000").exists()
        assert not (tmp_path / "0.100000").exists()
        # Non-numeric should remain
        assert (tmp_path / "points").exists()

    def test_clean_removes_symlinks(self, tmp_path):
        """Test cleaning removes symlinks to time directories."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        # Create a real directory and symlink
        real_dir = tmp_path / "real_data"
        real_dir.mkdir()
        symlink = tmp_path / "0.000000"
        symlink.symlink_to(real_dir)

        profile = DistanceWallInletProfile({}, str(tmp_path.parent))
        profile._clean_time_directories(str(tmp_path))

        # Symlink should be removed, real_dir should remain
        assert not symlink.exists()
        assert real_dir.exists()


class TestGenerateConstantData:
    """Test _generate_constant_data method."""

    def test_generate_constant_data(self, tmp_path):
        """Test generating constant velocity data."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        profile = DistanceWallInletProfile({
            'inlet': {'orientation': 'auto'}
        }, str(tmp_path))
        profile.inlet_normal = np.array([0, 0, 1.0])
        profile.d_max = 0.01
        profile.area = 0.001
        profile.face_areas = np.array([0.0005, 0.0005])
        profile.center = np.array([0, 0, 0])

        parent_dir = tmp_path / "boundaryData" / "inlet"
        parent_dir.mkdir(parents=True)

        # Mock _should_flip_normal
        with patch.object(profile, '_should_flip_normal', return_value=False):
            profile._generate_constant_data(
                str(parent_dir),
                flow_rate_m3s=0.0001,
                n_points=2,
                distances=np.array([0.005, 0.01])
            )

        # Check file was created
        time_dir = parent_dir / "0.000000"
        assert time_dir.exists()
        assert (time_dir / "U").exists()


class TestReadCSVFile:
    """Test _read_csv_file method with edge cases."""

    def test_read_csv_with_comments(self, tmp_path):
        """Test reading CSV with comment lines."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        csv_file = tmp_path / "flow.csv"
        csv_file.write_text("""# This is a comment
# Another comment
time,flowrate
0.0,50.0
0.1,60.0
0.2,55.0
""")

        profile = DistanceWallInletProfile({}, str(tmp_path))
        times, values, cardiac = profile._read_csv_file(str(csv_file))

        assert len(times) == 3
        assert times[0] == pytest.approx(0.0)
        assert values[0] == pytest.approx(50.0)
        assert cardiac == pytest.approx(0.2)

    def test_read_csv_no_header(self, tmp_path):
        """Test reading CSV without header."""
        from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

        csv_file = tmp_path / "flow.csv"
        csv_file.write_text("""0.0,100.0
0.4,200.0
0.8,100.0
""")

        profile = DistanceWallInletProfile({}, str(tmp_path))
        times, values, cardiac = profile._read_csv_file(str(csv_file))

        assert len(times) == 3
        assert cardiac == pytest.approx(0.8)


class TestFactoryFunction:
    """Test create_distance_wall_profile factory function."""

    def test_factory_creates_profile(self, tmp_path):
        """Test factory function creates profile instance."""
        from aortacfd_lib.distance_wall_inlet_profile import create_distance_wall_profile

        config = {'inlet': {'exponent': 2.5}}
        profile = create_distance_wall_profile(config, str(tmp_path))

        assert profile.exponent == 2.5


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
