"""
Unit tests for inlet_mapping.py module.
Tests velocity profile mapping, CSV parsing, and boundary condition generation.
"""
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import tempfile
import shutil
import os

from src.aortacfd_lib.inlet_mapping import InletMapping


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def basic_inlet_config():
    """Basic configuration for InletMapping."""
    return {
        "inlet": {
            "type": "TIMEVARYING",
            "csv_file": "flow.csv",
            "data_type": "velocity",
            "profile": "plug",
            "orientation": "in"
        },
        "geometry": {
            "inlet_keywords_ordered": "inlet",
            "scale_factor": 1e-3
        },
        "physics": {
            "nu": 3.5e-6,
            "blood_density": 1060,
            "blood_viscosity": 0.004
        }
    }


@pytest.fixture
def auto_orientation_config(basic_inlet_config):
    """Config with automatic orientation detection."""
    config = basic_inlet_config.copy()
    config["inlet"]["orientation"] = "auto"
    return config


@pytest.fixture
def parabolic_profile_config(basic_inlet_config):
    """Config with parabolic velocity profile."""
    config = basic_inlet_config.copy()
    config["inlet"]["profile"] = "parabolic"
    return config


@pytest.fixture
def womersley_profile_config(basic_inlet_config):
    """Config with Womersley velocity profile."""
    config = basic_inlet_config.copy()
    config["inlet"]["profile"] = "womersley"
    return config


@pytest.fixture
def temp_case_dir():
    """Temporary case directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def case_dir_with_structure(temp_case_dir):
    """Case directory with basic OpenFOAM structure."""
    # Create directory structure
    tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
    tri_surface.mkdir(parents=True, exist_ok=True)

    boundary_data = Path(temp_case_dir) / "constant" / "boundaryData" / "inlet"
    boundary_data.mkdir(parents=True, exist_ok=True)

    return temp_case_dir


# ============================================================================
# Test Class: Initialization and Configuration
# ============================================================================

class TestInletMappingInitialization:
    """Test InletMapping initialization and configuration."""

    def test_initialization_with_valid_config(self, basic_inlet_config, temp_case_dir):
        """Test that InletMapping initializes correctly with valid config."""
        inlet_mapper = InletMapping(basic_inlet_config, temp_case_dir)

        assert inlet_mapper.config == basic_inlet_config
        assert inlet_mapper.case_directory == temp_case_dir
        assert inlet_mapper.inlet_name == "inlet"
        assert inlet_mapper.inlet_data_file == "flow.csv"
        assert inlet_mapper.data_type == "velocity"
        assert inlet_mapper.profile == "plug"
        assert inlet_mapper.orientation == "in"
        assert inlet_mapper.nu == 3.5e-6

    def test_initialization_with_auto_orientation(self, auto_orientation_config, temp_case_dir):
        """Test initialization with automatic orientation detection."""
        inlet_mapper = InletMapping(auto_orientation_config, temp_case_dir)

        assert inlet_mapper.orientation == "auto"
        assert inlet_mapper.auto_flip_normal == False  # Default before run()

    def test_initialization_sets_none_for_calculated_properties(self, basic_inlet_config, temp_case_dir):
        """Test that calculated properties start as None."""
        inlet_mapper = InletMapping(basic_inlet_config, temp_case_dir)

        assert inlet_mapper.center is None
        assert inlet_mapper.radius is None
        assert inlet_mapper.cardiac_cycle is None


# ============================================================================
# Test Class: CSV File Reading
# ============================================================================

class TestCSVFileReading:
    """Test CSV file reading and parsing."""

    def test_read_csv_with_header(self, basic_inlet_config, temp_case_dir):
        """Test reading CSV file with header row."""
        csv_content = "time,velocity\n0.0,0.5\n0.1,0.6\n0.2,0.7\n"

        inlet_mapper = InletMapping(basic_inlet_config, temp_case_dir)

        with patch("builtins.open", mock_open(read_data=csv_content)):
            with patch("numpy.genfromtxt") as mock_genfromtxt:
                mock_genfromtxt.return_value = np.array([[0.0, 0.5], [0.1, 0.6], [0.2, 0.7]])

                times, yval, cardiac_cycle = inlet_mapper._read_csv_file("flow.csv")

                assert len(times) == 3
                assert len(yval) == 3
                assert cardiac_cycle == 0.2  # 0.2 - 0.0

    def test_read_csv_without_header(self, basic_inlet_config, temp_case_dir):
        """Test reading CSV file without header row."""
        csv_content = "0.0,0.5\n0.1,0.6\n0.2,0.7\n"

        inlet_mapper = InletMapping(basic_inlet_config, temp_case_dir)

        with patch("builtins.open", mock_open(read_data=csv_content)):
            with patch("numpy.genfromtxt") as mock_genfromtxt:
                mock_genfromtxt.return_value = np.array([[0.0, 0.5], [0.1, 0.6], [0.2, 0.7]])

                times, yval, cardiac_cycle = inlet_mapper._read_csv_file("flow.csv")

                assert len(times) == 3
                assert len(yval) == 3

    def test_read_csv_insufficient_columns(self, basic_inlet_config, temp_case_dir):
        """Test error handling when CSV has insufficient columns."""
        inlet_mapper = InletMapping(basic_inlet_config, temp_case_dir)

        with patch("builtins.open", mock_open(read_data="0.0\n0.1\n")):
            with patch("numpy.genfromtxt") as mock_genfromtxt:
                mock_genfromtxt.return_value = np.array([[0.0], [0.1]])

                with pytest.raises(RuntimeError, match="Error reading CSV file"):
                    inlet_mapper._read_csv_file("flow.csv")

    def test_read_csv_file_not_found(self, basic_inlet_config, temp_case_dir):
        """Test error handling when CSV file doesn't exist."""
        inlet_mapper = InletMapping(basic_inlet_config, temp_case_dir)

        with patch("builtins.open", side_effect=FileNotFoundError("File not found")):
            with pytest.raises(RuntimeError, match="Error reading CSV file"):
                inlet_mapper._read_csv_file("nonexistent.csv")


# ============================================================================
# Test Class: Cardiac Cycle Calculation
# ============================================================================

class TestCardiacCycleCalculation:
    """Test cardiac cycle period determination."""

    def test_determine_cardiac_period_valid_data(self, basic_inlet_config, temp_case_dir):
        """Test cardiac period calculation with valid time series."""
        inlet_mapper = InletMapping(basic_inlet_config, temp_case_dir)

        times = np.array([0.0, 0.1, 0.2, 0.3, 0.8])
        period = inlet_mapper._determine_cardiac_period(times)

        assert period == 0.8

    def test_determine_cardiac_period_insufficient_data(self, basic_inlet_config, temp_case_dir):
        """Test error when insufficient time points provided."""
        inlet_mapper = InletMapping(basic_inlet_config, temp_case_dir)

        times = np.array([0.0])

        with pytest.raises(ValueError, match="Insufficient time data"):
            inlet_mapper._determine_cardiac_period(times)

    def test_determine_cardiac_period_invalid_range(self, basic_inlet_config, temp_case_dir):
        """Test error when time range is invalid (negative or zero)."""
        inlet_mapper = InletMapping(basic_inlet_config, temp_case_dir)

        times = np.array([0.5, 0.5])  # Same time values

        with pytest.raises(ValueError, match="Invalid time range"):
            inlet_mapper._determine_cardiac_period(times)


# ============================================================================
# Test Class: Points File Reading
# ============================================================================

class TestPointsFileReading:
    """Test OpenFOAM points file reading."""

    def test_read_points_file_with_parentheses(self, basic_inlet_config, temp_case_dir):
        """Test reading points file with parentheses in header."""
        points_content = "3\n(\n(0.0 0.0 0.0)\n(1.0 0.0 0.0)\n(0.0 1.0 0.0)\n"

        inlet_mapper = InletMapping(basic_inlet_config, temp_case_dir)

        with patch("builtins.open", mock_open(read_data=points_content)):
            n_points, points = inlet_mapper._read_points_file("points")

            assert n_points == 3
            assert points.shape == (3, 3)
            assert np.allclose(points[0], [0.0, 0.0, 0.0])
            assert np.allclose(points[1], [1.0, 0.0, 0.0])
            assert np.allclose(points[2], [0.0, 1.0, 0.0])

    def test_read_points_file_without_parentheses(self, basic_inlet_config, temp_case_dir):
        """Test reading points file without parentheses in header."""
        points_content = "3\n(0.0 0.0 0.0)\n(1.0 0.0 0.0)\n(0.0 1.0 0.0)\n"

        inlet_mapper = InletMapping(basic_inlet_config, temp_case_dir)

        with patch("builtins.open", mock_open(read_data=points_content)):
            n_points, points = inlet_mapper._read_points_file("points")

            assert n_points == 3
            assert points.shape == (3, 3)


# ============================================================================
# Test Class: Geometry Calculations
# ============================================================================

class TestGeometryCalculations:
    """Test geometric calculations (distance, area, etc.)."""

    def test_get_distance_from_center(self, basic_inlet_config, temp_case_dir):
        """Test distance calculation from inlet center."""
        inlet_mapper = InletMapping(basic_inlet_config, temp_case_dir)
        inlet_mapper.center = np.array([0.0, 0.0, 0.0])

        point = np.array([3.0, 4.0, 0.0])
        distance = inlet_mapper._get_distance_from_center(point)

        assert distance == 5.0  # 3-4-5 triangle

    def test_compute_cross_sectional_area(self, basic_inlet_config, temp_case_dir):
        """Test cross-sectional area calculation."""
        inlet_mapper = InletMapping(basic_inlet_config, temp_case_dir)
        inlet_mapper.radius = 10.0  # mm

        area = inlet_mapper.compute_cross_sectional_area()

        expected_area = np.pi * 100.0  # π * r²
        assert np.isclose(area, expected_area)


# ============================================================================
# Test Class: Velocity Components
# ============================================================================

class TestVelocityComponents:
    """Test velocity component calculations with different orientations."""

    def test_velocity_components_orientation_in(self, basic_inlet_config, temp_case_dir):
        """Test velocity components with 'in' orientation (negative normal)."""
        inlet_mapper = InletMapping(basic_inlet_config, temp_case_dir)
        inlet_mapper.orientation = "in"

        speed = 1.0
        normal = np.array([1.0, 0.0, 0.0])

        velocity = inlet_mapper._get_velocity_components(speed, normal)

        assert np.allclose(velocity, [-1.0, 0.0, 0.0])  # Flipped

    def test_velocity_components_orientation_out(self, basic_inlet_config, temp_case_dir):
        """Test velocity components with 'out' orientation (positive normal)."""
        inlet_mapper = InletMapping(basic_inlet_config, temp_case_dir)
        inlet_mapper.orientation = "out"

        speed = 1.0
        normal = np.array([1.0, 0.0, 0.0])

        velocity = inlet_mapper._get_velocity_components(speed, normal)

        assert np.allclose(velocity, [1.0, 0.0, 0.0])  # Not flipped

    def test_velocity_components_auto_flip(self, auto_orientation_config, temp_case_dir):
        """Test velocity components with auto orientation (flipped)."""
        inlet_mapper = InletMapping(auto_orientation_config, temp_case_dir)
        inlet_mapper.auto_flip_normal = True

        speed = 1.0
        normal = np.array([0.0, 1.0, 0.0])

        velocity = inlet_mapper._get_velocity_components(speed, normal)

        assert np.allclose(velocity, [0.0, -1.0, 0.0])  # Flipped

    def test_velocity_components_auto_no_flip(self, auto_orientation_config, temp_case_dir):
        """Test velocity components with auto orientation (not flipped)."""
        inlet_mapper = InletMapping(auto_orientation_config, temp_case_dir)
        inlet_mapper.auto_flip_normal = False

        speed = 1.0
        normal = np.array([0.0, 0.0, 1.0])

        velocity = inlet_mapper._get_velocity_components(speed, normal)

        assert np.allclose(velocity, [0.0, 0.0, 1.0])  # Not flipped


# ============================================================================
# Test Class: Automatic Orientation Detection
# ============================================================================

class TestAutomaticOrientationDetection:
    """Test automatic orientation detection based on geometry."""

    def test_determine_inward_direction_should_flip(self, auto_orientation_config, temp_case_dir):
        """Test auto-detection when normal should be flipped."""
        inlet_mapper = InletMapping(auto_orientation_config, temp_case_dir)
        inlet_mapper.center = np.array([0.0, 0.0, 0.0])
        inlet_mapper.geom_settings = {"scale_factor": 1e-3}

        # Inlet normal pointing opposite to outlet direction
        inlet_normal = np.array([-1.0, 0.0, 0.0])

        # Mock outlet processing
        with patch.object(inlet_mapper.log, 'info'):
            with patch.object(inlet_mapper.log, 'warning'):
                with patch('os.listdir', return_value=['outlet1.stl', 'outlet2.stl']):
                    with patch('src.aortacfd_lib.inlet_mapping.PatchProcessing') as MockPatchProc:
                        mock_processor = Mock()
                        # Outlets are in positive x direction
                        mock_processor.calculate_inlet_center_radius.return_value = (
                            np.array([100.0, 0.0, 0.0]),  # Outlet center
                            10.0,  # Radius
                            np.array([1.0, 0.0, 0.0])  # Normal
                        )
                        MockPatchProc.return_value = mock_processor

                        should_flip = inlet_mapper._determine_inward_direction(inlet_normal, temp_case_dir)

                        assert should_flip == True  # Should flip because dot product < 0

    def test_determine_inward_direction_no_flip(self, auto_orientation_config, temp_case_dir):
        """Test auto-detection when normal should not be flipped."""
        inlet_mapper = InletMapping(auto_orientation_config, temp_case_dir)
        inlet_mapper.center = np.array([0.0, 0.0, 0.0])
        inlet_mapper.geom_settings = {"scale_factor": 1e-3}

        # Inlet normal pointing toward outlet direction
        inlet_normal = np.array([1.0, 0.0, 0.0])

        with patch.object(inlet_mapper.log, 'info'):
            with patch.object(inlet_mapper.log, 'warning'):
                with patch('os.listdir', return_value=['outlet1.stl']):
                    with patch('src.aortacfd_lib.inlet_mapping.PatchProcessing') as MockPatchProc:
                        mock_processor = Mock()
                        mock_processor.calculate_inlet_center_radius.return_value = (
                            np.array([100.0, 0.0, 0.0]),
                            10.0,
                            np.array([1.0, 0.0, 0.0])
                        )
                        MockPatchProc.return_value = mock_processor

                        should_flip = inlet_mapper._determine_inward_direction(inlet_normal, temp_case_dir)

                        assert should_flip == False  # Should not flip because dot product > 0

    def test_determine_inward_direction_no_outlets(self, auto_orientation_config, temp_case_dir):
        """Test auto-detection fallback when no outlets found."""
        inlet_mapper = InletMapping(auto_orientation_config, temp_case_dir)
        inlet_mapper.center = np.array([0.0, 0.0, 0.0])
        inlet_mapper.geom_settings = {"scale_factor": 1e-3}

        inlet_normal = np.array([1.0, 0.0, 0.0])

        with patch.object(inlet_mapper.log, 'warning'):
            with patch('os.listdir', return_value=['wall.stl']):  # No outlets
                should_flip = inlet_mapper._determine_inward_direction(inlet_normal, temp_case_dir)

                assert should_flip == False  # Fallback to no flip


# ============================================================================
# Test Class: Velocity Profile Types
# ============================================================================

class TestVelocityProfiles:
    """Test different velocity profile calculations."""

    def test_plug_profile_from_velocity(self, basic_inlet_config, temp_case_dir):
        """Test plug profile speed calculation from velocity data."""
        inlet_mapper = InletMapping(basic_inlet_config, temp_case_dir)
        inlet_mapper.data_type = "velocity"

        velocity = 1.5  # m/s
        speed = inlet_mapper.plug_profile_speed(velocity)

        assert speed == velocity  # Plug profile: uniform velocity

    def test_plug_profile_from_flow_rate(self, basic_inlet_config, temp_case_dir):
        """Test plug profile speed calculation from flow rate."""
        inlet_mapper = InletMapping(basic_inlet_config, temp_case_dir)
        inlet_mapper.data_type = "flowrate"  # Correct data type name
        inlet_mapper.radius = 10.0  # mm

        flow_rate = 100.0  # Assuming same units as area (mm²)
        speed = inlet_mapper.plug_profile_speed(flow_rate)

        area = np.pi * (10.0) ** 2  # Area in mm²
        expected_speed = flow_rate / area

        assert np.isclose(speed, expected_speed, rtol=1e-3)


# ============================================================================
# Summary
# ============================================================================

"""
Test Coverage Summary:
- Initialization: 3 tests
- CSV Reading: 4 tests
- Cardiac Cycle: 3 tests
- Points File: 2 tests
- Geometry: 2 tests
- Velocity Components: 4 tests
- Auto Orientation: 3 tests
- Velocity Profiles: 2 tests

Total: 23 new tests for inlet_mapping.py

Expected coverage improvement: 16% → 60%+ (targeting major methods)
"""
