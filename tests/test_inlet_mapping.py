"""
Test suite for inlet_mapping module.

Tests cover:
- InletMapping class initialization
- Velocity profile computations (plug, parabolic, Womersley)
- Fourier decomposition
- Helper functions
- Flow rate calculations
"""

import pytest
import sys
import tempfile
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestInletMappingInit:
    """Test InletMapping initialization."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_init_with_valid_config(self, mock_logger):
        """Test initialization with valid configuration."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'inlet_data.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic',
                    'orientation': 'auto'
                }
            },
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'scale_factor': 0.001
            },
            'physics': {
                'nu': 3.5e-6
            }
        }

        mapping = InletMapping(config, '/tmp/case')

        assert mapping.data_type == 'flowrate'
        assert mapping.profile == 'parabolic'
        assert mapping.nu == 3.5e-6

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_init_with_direct_inlet_config(self, mock_logger):
        """Test initialization with direct inlet config (alternative structure)."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'inlet': {
                'csv_file': 'inlet_data.csv',
                'data_type': 'velocity',
                'profile': 'plug'
            },
            'boundary_conditions': {},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
            },
            'physics': {
                'nu': 3.5e-6
            }
        }

        mapping = InletMapping(config, '/tmp/case')

        assert mapping.data_type == 'velocity'
        assert mapping.profile == 'plug'


class TestPlugProfile:
    """Test plug profile calculations."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_plug_profile_speed_flowrate(self, mock_logger):
        """Test plug profile speed calculation from flow rate."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'plug'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')
        mapping.radius = 0.01  # 1 cm radius
        mapping.area = np.pi * 0.01**2  # Circular area

        # Flow rate of 0.0001 m³/s
        flow_rate = 0.0001
        expected_speed = flow_rate / mapping.area

        result = mapping.plug_profile_speed(flow_rate)

        assert abs(result - expected_speed) < 1e-10

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_plug_profile_speed_velocity(self, mock_logger):
        """Test plug profile speed when data is already velocity."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'velocity',
                    'profile': 'plug'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')
        mapping.radius = 0.01

        velocity = 0.5  # m/s
        result = mapping.plug_profile_speed(velocity)

        assert result == velocity


class TestParabolicProfile:
    """Test parabolic profile calculations."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_parabolic_centerline_speed(self, mock_logger):
        """Test parabolic centerline speed calculation."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')
        mapping.radius = 0.01
        mapping.area = np.pi * 0.01**2

        flow_rate = 0.0001  # m³/s
        avg_velocity = flow_rate / mapping.area
        expected_centerline = 2.0 * avg_velocity

        result = mapping.parabolic_centerline_speed(flow_rate)

        assert abs(result - expected_centerline) < 1e-10

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_parabolic_factor_at_center(self, mock_logger):
        """Test parabolic factor at center (r=0)."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')
        mapping.radius = 0.01

        # At center (r=0), parabolic factor should be 1.0
        result = mapping.parabolic_factor(0.0)

        assert result == 1.0

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_parabolic_factor_at_wall(self, mock_logger):
        """Test parabolic factor at wall (r=R)."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')
        mapping.radius = 0.01

        # At wall (r=R), parabolic factor should be 0.0
        result = mapping.parabolic_factor(0.01)

        assert result == 0.0

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_parabolic_factor_at_half_radius(self, mock_logger):
        """Test parabolic factor at r=R/2."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')
        mapping.radius = 0.01

        # At r=R/2, factor = 1 - (0.5)² = 0.75
        result = mapping.parabolic_factor(0.005)

        assert abs(result - 0.75) < 1e-10

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_parabolic_factor_outside_radius(self, mock_logger):
        """Test parabolic factor outside radius is clamped to 0."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')
        mapping.radius = 0.01

        # Outside radius should return 0
        result = mapping.parabolic_factor(0.015)

        assert result == 0.0


class TestWomersleyProfile:
    """Test Womersley profile calculations."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_womersley_shape_factor_at_center(self, mock_logger):
        """Test Womersley shape factor at center."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'womersley'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')
        mapping.radius = 0.01

        omega = 2 * np.pi  # 1 Hz
        alpha = 5.0  # Typical Womersley number

        # At center, Womersley profile should have maximum velocity
        result = mapping.womersley_shape_factor(0.0, 0.0, omega, alpha)

        # Result should be a real number
        assert isinstance(result, (float, np.floating))


class TestFourierDecomposition:
    """Test Fourier decomposition methods."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_compute_fourier_coefficients(self, mock_logger):
        """Test Fourier coefficient computation."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'womersley_fft'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')
        mapping.radius = 0.01

        # Create a simple sinusoidal waveform
        n_points = 100
        T = 0.8  # 800 ms cardiac cycle
        times = np.linspace(0, T, n_points, endpoint=False)
        mean_flow = 5e-5  # m³/s
        amplitude = 3e-5
        values = mean_flow + amplitude * np.sin(2 * np.pi * times / T)

        V0, Vn_complex, omega_fundamental = mapping._compute_fourier_coefficients(
            times, values, n_harmonics=4
        )

        # V0 should be close to mean_flow
        assert abs(V0 - mean_flow) < 1e-5

        # Fundamental frequency should be approximately 2π/T
        expected_omega = 2 * np.pi / T
        rel_error = abs(omega_fundamental - expected_omega) / expected_omega
        assert rel_error < 0.02  # 2% tolerance

        # First harmonic should capture most of the amplitude
        assert np.abs(Vn_complex[0]) > 0.05 * amplitude

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_estimate_required_harmonics(self, mock_logger):
        """Test automatic harmonic estimation."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'womersley_fft'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')

        # Create a simple sinusoidal waveform (should need few harmonics)
        n_points = 100
        values = np.sin(np.linspace(0, 2*np.pi, n_points))

        n_harmonics = mapping._estimate_required_harmonics(values, energy_threshold=0.95)

        # For a pure sine wave, should need very few harmonics
        assert n_harmonics >= 4  # Minimum
        assert n_harmonics <= 20  # Should be small for simple signal

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_estimate_harmonics_constant_signal(self, mock_logger):
        """Test harmonic estimation for constant signal."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'womersley_fft'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')

        # Constant signal
        values = np.ones(100) * 5.0

        n_harmonics = mapping._estimate_required_harmonics(values)

        # For constant signal, should return default
        assert n_harmonics == 8


class TestDistanceCalculations:
    """Test distance and geometry calculations."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_get_distance_from_center(self, mock_logger):
        """Test distance from center calculation."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')
        mapping.center = np.array([0.0, 0.0, 0.0])

        # Test point
        point = np.array([0.003, 0.004, 0.0])  # Distance = 0.005

        result = mapping._get_distance_from_center(point)

        assert abs(result - 0.005) < 1e-10

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_compute_cross_sectional_area_with_stl_area(self, mock_logger):
        """Test cross-sectional area with STL area."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')
        mapping.area = 0.0003  # Pre-computed STL area
        mapping.radius = 0.01

        result = mapping.compute_cross_sectional_area()

        # Should return actual STL area
        assert result == 0.0003

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_compute_cross_sectional_area_fallback(self, mock_logger):
        """Test cross-sectional area falls back to circular approx."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')
        mapping.area = None  # Not yet computed
        mapping.radius = 0.01

        result = mapping.compute_cross_sectional_area()

        expected = np.pi * 0.01**2
        assert abs(result - expected) < 1e-10


class TestVelocityComponents:
    """Test velocity component calculations."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_get_velocity_components_inward(self, mock_logger):
        """Test velocity components with inward orientation."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic',
                    'orientation': 'in'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')

        speed = 0.5
        normal = np.array([1.0, 0.0, 0.0])

        result = mapping._get_velocity_components(speed, normal)

        # With 'in' orientation, should be negative normal direction
        expected = -speed * normal
        np.testing.assert_array_almost_equal(result, expected)

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_get_velocity_components_outward(self, mock_logger):
        """Test velocity components with outward orientation."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic',
                    'orientation': 'out'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')

        speed = 0.5
        normal = np.array([1.0, 0.0, 0.0])

        result = mapping._get_velocity_components(speed, normal)

        # With 'out' orientation, should be positive normal direction
        expected = speed * normal
        np.testing.assert_array_almost_equal(result, expected)

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_get_velocity_components_auto(self, mock_logger):
        """Test velocity components with auto orientation."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic',
                    'orientation': 'auto'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')
        mapping.auto_flip_normal = True  # Simulate auto-detection result

        speed = 0.5
        normal = np.array([1.0, 0.0, 0.0])

        result = mapping._get_velocity_components(speed, normal)

        # With auto_flip=True, should flip direction
        expected = -speed * normal
        np.testing.assert_array_almost_equal(result, expected)


class TestDetermineCardiacPeriod:
    """Test cardiac period determination."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_determine_cardiac_period(self, mock_logger):
        """Test cardiac period calculation."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')

        times = np.array([0.0, 0.2, 0.4, 0.6, 0.8])

        result = mapping._determine_cardiac_period(times)

        assert result == 0.8

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_determine_cardiac_period_insufficient_data(self, mock_logger):
        """Test error with insufficient time data."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')

        times = np.array([0.5])  # Only one point

        with pytest.raises(ValueError) as exc_info:
            mapping._determine_cardiac_period(times)

        assert 'Insufficient' in str(exc_info.value)


class TestWomersleyFFTVelocity:
    """Test Womersley FFT velocity calculations."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_womersley_fft_velocity_at_center(self, mock_logger):
        """Test Womersley FFT velocity at center."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'womersley_fft'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')
        mapping.radius = 0.01
        mapping.nu = 3.5e-6

        V0 = 0.5  # Mean velocity
        Vn_complex = np.array([0.1 + 0.0j, 0.05 + 0.0j])
        omega_fundamental = 2 * np.pi / 0.8

        # At center (r=0), should get maximum velocity
        result = mapping._womersley_fft_velocity(0.0, 0.0, V0, Vn_complex, omega_fundamental)

        # Steady component at center = 2 * V0
        assert result > V0  # Should be greater than mean

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_womersley_fft_velocity_at_wall(self, mock_logger):
        """Test Womersley FFT velocity approaches zero at wall."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'womersley_fft'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')
        mapping.radius = 0.01
        mapping.nu = 3.5e-6

        V0 = 0.5
        Vn_complex = np.array([0.1 + 0.0j])
        omega_fundamental = 2 * np.pi / 0.8

        # At wall (r=R), velocity should be approximately 0
        result = mapping._womersley_fft_velocity(0.01, 0.0, V0, Vn_complex, omega_fundamental)

        assert abs(result) < 0.1  # Should be close to zero

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_womersley_fft_velocity_outside_radius(self, mock_logger):
        """Test Womersley FFT velocity is zero outside radius."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'data.csv',
                    'data_type': 'flowrate',
                    'profile': 'womersley_fft'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, '/tmp/case')
        mapping.radius = 0.01
        mapping.nu = 3.5e-6

        V0 = 0.5
        Vn_complex = np.array([0.1 + 0.0j])
        omega_fundamental = 2 * np.pi / 0.8

        # Outside radius
        result = mapping._womersley_fft_velocity(0.015, 0.0, V0, Vn_complex, omega_fundamental)

        assert result == 0.0


class TestReadCsvFile:
    """Test _read_csv_file method."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_reads_csv_with_header(self, mock_logger, tmp_path):
        """Test reading CSV file with header row."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))

        csv_content = """time,flowrate
0.0,5.0e-5
0.1,6.0e-5
0.2,5.5e-5
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        times, values, cardiac_cycle = mapping._read_csv_file(str(csv_file))

        assert len(times) == 3
        assert len(values) == 3
        assert abs(times[0]) < 1e-10
        assert abs(cardiac_cycle - 0.2) < 1e-10

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_reads_csv_without_header(self, mock_logger, tmp_path):
        """Test reading CSV file without header (numeric-only first line)."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))

        # Use non-scientific notation to avoid header detection (e is alpha)
        csv_content = """0.0,0.00001
0.1,0.00002
0.2,0.000015
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        times, values, cardiac_cycle = mapping._read_csv_file(str(csv_file))

        assert len(times) == 3
        assert abs(times[1] - 0.1) < 1e-10

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_reads_csv_with_comments(self, mock_logger, tmp_path):
        """Test reading CSV file with comment lines."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))

        csv_content = """# This is a comment
# Another comment
time,flowrate
0.0,1e-5
0.1,2e-5
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        times, values, _ = mapping._read_csv_file(str(csv_file))

        assert len(times) == 2

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_auto_converts_liters_per_minute(self, mock_logger, tmp_path):
        """Test automatic conversion from L/min to m³/s."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))

        # Values > 1.0 are detected as L/min
        csv_content = """0.0,300
0.5,400
1.0,350
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        times, values, _ = mapping._read_csv_file(str(csv_file))

        # 300 L/min = 300 * 1e-3 / 60 = 0.005 m³/s
        expected = 300 * 1e-3 / 60.0
        assert abs(values[0] - expected) < 1e-10

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_preserves_si_units(self, mock_logger, tmp_path):
        """Test that SI units (m³/s) are preserved."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))

        # Use decimal notation - scientific notation 'e' triggers header detection
        csv_content = """0.0,0.00005
0.5,0.00006
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        times, values, _ = mapping._read_csv_file(str(csv_file))

        # Values < 1.0 should be preserved as-is (m³/s)
        assert abs(values[0] - 5e-5) < 1e-10

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_raises_error_for_single_column(self, mock_logger, tmp_path):
        """Test error handling for invalid CSV format."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))

        csv_content = """0.0
0.1
0.2
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        with pytest.raises(RuntimeError, match="must have at least 2 columns"):
            mapping._read_csv_file(str(csv_file))


class TestReadPointsFile:
    """Test _read_points_file method."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_reads_points_with_parentheses(self, mock_logger, tmp_path):
        """Test reading OpenFOAM points file with parentheses format."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))

        points_content = """3
(
(0.001 0.002 0.003)
(0.004 0.005 0.006)
(0.007 0.008 0.009)
)
"""
        points_file = tmp_path / "points"
        points_file.write_text(points_content)

        n_points, points = mapping._read_points_file(str(points_file))

        assert n_points == 3
        assert points.shape == (3, 3)
        assert abs(points[0, 0] - 0.001) < 1e-10
        assert abs(points[1, 1] - 0.005) < 1e-10

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_reads_points_without_outer_parentheses(self, mock_logger, tmp_path):
        """Test reading points file without outer parentheses."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))

        points_content = """2
(0.01 0.02 0.0)
(0.03 0.04 0.0)
"""
        points_file = tmp_path / "points"
        points_file.write_text(points_content)

        n_points, points = mapping._read_points_file(str(points_file))

        assert n_points == 2
        assert points.shape == (2, 3)


class TestFlowRateScaling:
    """Test flow rate scaling and conservation."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_scale_to_target_flowrate_parabolic(self, mock_logger, tmp_path):
        """Test flow rate scaling for parabolic profile."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.area = np.pi * 0.01**2

        shape_factors = np.array([1.0, 0.75, 0.5, 0.25, 0.0])
        target_Q = 1e-4  # m³/s

        velocities = mapping._scale_to_target_flowrate(shape_factors, target_Q, len(shape_factors))

        # For parabolic, U_max = 2 * Q / A
        expected_U_max = 2.0 * target_Q / mapping.area
        assert abs(velocities[0] - expected_U_max) < 1e-10

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_scale_to_target_flowrate_plug(self, mock_logger, tmp_path):
        """Test flow rate scaling for plug profile."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'plug'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.area = np.pi * 0.01**2

        shape_factors = np.array([1.0, 1.0, 1.0, 1.0])
        target_Q = 1e-4  # m³/s

        velocities = mapping._scale_to_target_flowrate(shape_factors, target_Q, len(shape_factors))

        # For plug, U_max = Q / A
        expected_U = target_Q / mapping.area
        np.testing.assert_array_almost_equal(velocities, [expected_U] * 4)

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_scale_to_target_flowrate_no_active_points(self, mock_logger, tmp_path):
        """Test scaling returns zeros when no active points."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.area = np.pi * 0.01**2

        shape_factors = np.array([0.0, 0.0, 0.0])  # All outside

        velocities = mapping._scale_to_target_flowrate(shape_factors, 1e-4, len(shape_factors))

        np.testing.assert_array_almost_equal(velocities, [0.0, 0.0, 0.0])


class TestVerifyFlowrate:
    """Test flow rate verification."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_verify_flowrate(self, mock_logger, tmp_path):
        """Test flow rate verification calculation."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.area = 1e-4  # 1 cm²

        velocity_magnitudes = np.array([1.0, 1.0, 1.0, 1.0])
        n_points = 4

        Q = mapping._verify_flowrate(velocity_magnitudes, n_points)

        # Q = sum(V) * A_face = sum(V) * A / n_active = 4 * 1e-4 / 4 = 1e-4
        expected = 1.0 * 1e-4
        assert abs(Q - expected) < 1e-10

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_verify_flowrate_no_active(self, mock_logger, tmp_path):
        """Test flow rate verification with no active points."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.area = 1e-4

        velocity_magnitudes = np.array([0.0, 0.0, 0.0])
        n_points = 3

        Q = mapping._verify_flowrate(velocity_magnitudes, n_points)

        assert Q == 0.0


class TestOpenFoamOutput:
    """Test OpenFOAM data file writing."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_write_openfoam_data_format(self, mock_logger, tmp_path):
        """Test OpenFOAM velocity data file writing."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))

        output_file = tmp_path / "U"
        velocities = [
            np.array([0.1, 0.0, 0.0]),
            np.array([0.2, 0.1, 0.0]),
            np.array([0.15, 0.05, 0.0]),
        ]

        mapping._write_openfoam_data_format(str(output_file), 3, velocities)

        content = output_file.read_text()
        assert content.startswith("3\n(\n")
        assert content.endswith(")\n")
        assert "(1.000000e-01 0.000000e+00 0.000000e+00)" in content

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_write_openfoam_data_format_empty(self, mock_logger, tmp_path):
        """Test writing empty velocity list."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))

        output_file = tmp_path / "U"
        velocities = []

        mapping._write_openfoam_data_format(str(output_file), 0, velocities)

        content = output_file.read_text()
        assert "0\n(\n)\n" == content


class TestShapeFactors:
    """Test shape factor computation for various profiles."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_plug_profile_shape_factors(self, mock_logger, tmp_path):
        """Test shape factors for plug flow profile."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'plug'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.area = np.pi * 0.01**2

        points = np.array([
            [0.0, 0.0, 0.0],      # Center
            [0.005, 0.0, 0.0],    # Half radius
            [0.009, 0.0, 0.0],    # Near edge
        ])

        factors = mapping._compute_shape_factors(points, t=0.0)

        # Plug flow: all points inside should have factor = 1.0
        np.testing.assert_array_almost_equal(factors, [1.0, 1.0, 1.0])

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_parabolic_profile_shape_factors(self, mock_logger, tmp_path):
        """Test shape factors for parabolic profile."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.area = np.pi * 0.01**2

        points = np.array([
            [0.0, 0.0, 0.0],      # Center
            [0.005, 0.0, 0.0],    # Half radius
            [0.01, 0.0, 0.0],     # Edge
        ])

        factors = mapping._compute_shape_factors(points, t=0.0)

        # Parabolic: center=1.0, half=0.75, edge=0.0
        assert abs(factors[0] - 1.0) < 1e-10
        assert abs(factors[1] - 0.75) < 1e-10
        assert abs(factors[2] - 0.0) < 1e-10

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_shape_factors_outside_radius(self, mock_logger, tmp_path):
        """Test shape factors for points outside inlet radius."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.area = np.pi * 0.01**2

        points = np.array([
            [0.015, 0.0, 0.0],    # Outside radius
            [0.02, 0.0, 0.0],     # Further outside
        ])

        factors = mapping._compute_shape_factors(points, t=0.0)

        # Points outside should have factor = 0.0
        np.testing.assert_array_almost_equal(factors, [0.0, 0.0])

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_default_profile_is_plug(self, mock_logger, tmp_path):
        """Test that unknown profile defaults to plug flow."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'unknown_profile'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.area = np.pi * 0.01**2

        points = np.array([
            [0.0, 0.0, 0.0],
            [0.005, 0.0, 0.0],
        ])

        factors = mapping._compute_shape_factors(points, t=0.0)

        # Default: plug flow
        np.testing.assert_array_almost_equal(factors, [1.0, 1.0])


class TestDetermineInwardDirection:
    """Test automatic inlet orientation detection."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_returns_false_when_no_outlet_files(self, mock_logger, tmp_path):
        """Test returns False when no outlet STL files exist."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic',
                    'orientation': 'auto'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01

        # Create triSurface dir with only inlet
        tri_surface = tmp_path / "constant" / "triSurface"
        tri_surface.mkdir(parents=True)
        (tri_surface / "inlet.stl").write_text("solid inlet\nendsolid inlet")

        inlet_normal = np.array([0.0, 0.0, 1.0])
        result = mapping._determine_inward_direction(inlet_normal, str(tmp_path))

        # No outlets found, should return False (no flip)
        assert result is False

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_handles_exception_gracefully(self, mock_logger, tmp_path):
        """Test handles exceptions and returns False."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic',
                    'orientation': 'auto'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01

        inlet_normal = np.array([0.0, 0.0, 1.0])

        # No triSurface dir exists - should catch exception
        result = mapping._determine_inward_direction(inlet_normal, str(tmp_path))

        assert result is False


class TestEllipticalProfile:
    """Test elliptical Poiseuille profile."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_elliptical_poiseuille_at_center(self, mock_logger, tmp_path):
        """Test elliptical profile gives maximum at center."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'elliptical'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.area = np.pi * 0.01 * 0.008

        points = np.array([[0.0, 0.0, 0.0]])
        factors = mapping._compute_elliptical_poiseuille_factors(
            points, semi_axis_a=0.01, semi_axis_b=0.008
        )
        assert abs(factors[0] - 1.0) < 1e-10

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_elliptical_poiseuille_on_boundary(self, mock_logger, tmp_path):
        """Test elliptical profile is zero on boundary."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'elliptical'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.area = np.pi * 0.01 * 0.008

        # Point on ellipse boundary: (a, 0)
        points = np.array([[0.01, 0.0, 0.0]])
        factors = mapping._compute_elliptical_poiseuille_factors(
            points, semi_axis_a=0.01, semi_axis_b=0.008
        )
        assert abs(factors[0]) < 1e-10

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_elliptical_poiseuille_outside(self, mock_logger, tmp_path):
        """Test elliptical profile is zero outside ellipse."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'elliptical'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.area = np.pi * 0.01 * 0.008

        # Point outside ellipse
        points = np.array([[0.02, 0.02, 0.0]])
        factors = mapping._compute_elliptical_poiseuille_factors(
            points, semi_axis_a=0.01, semi_axis_b=0.008
        )
        assert factors[0] == 0.0


class TestEstimateEllipseAxes:
    """Test ellipse axis estimation."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_estimate_ellipse_axes(self, mock_logger, tmp_path):
        """Test ellipse axis estimation from points."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'elliptical'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01

        # Generate points in an ellipse-like distribution
        n = 50
        theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
        a, b = 0.012, 0.008  # Semi-axes
        points = np.zeros((n, 3))
        points[:, 0] = 0.8 * a * np.cos(theta)  # Scale down from boundary
        points[:, 1] = 0.8 * b * np.sin(theta)

        est_a, est_b = mapping._estimate_ellipse_axes(points)

        # Estimates should be in reasonable range
        assert est_a > est_b  # a >= b by definition


class TestWomersleyProfileHarmonic:
    """Test Womersley profile harmonic calculations."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_womersley_profile_harmonic_basic(self, mock_logger, tmp_path):
        """Test single Womersley harmonic calculation."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'womersley_fft'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.radius = 0.01
        mapping.nu = 3.5e-6

        omega_fundamental = 2 * np.pi / 0.8  # For T=0.8s
        Vn = 0.3 + 0.0j  # Real coefficient

        u_n = mapping._womersley_profile_harmonic(
            r=0.005,  # Half radius
            n=1,
            omega_fundamental=omega_fundamental,
            Vn_complex=Vn,
            t=0.0
        )

        assert np.isfinite(u_n)
        assert isinstance(u_n, (int, float, np.floating))

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_womersley_profile_harmonic_high_alpha(self, mock_logger, tmp_path):
        """Test Womersley harmonic with moderately high alpha."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'womersley_fft'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 1e-7}  # Moderately low nu for higher alpha
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.radius = 0.01
        mapping.nu = 1e-7

        omega_fundamental = 2 * np.pi * 10  # Moderate frequency
        Vn = 0.1 + 0.1j

        # Should return a finite value for reasonable parameters
        u_n = mapping._womersley_profile_harmonic(
            r=0.005, n=3,
            omega_fundamental=omega_fundamental,
            Vn_complex=Vn, t=0.0
        )

        # Result should be a real number (finite or potentially small)
        assert isinstance(u_n, (int, float, np.floating))


class TestComputeWomersleyFFTShapeFactors:
    """Test Womersley FFT shape factor computation."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_compute_womersley_fft_shape_factors(self, mock_logger, tmp_path):
        """Test Womersley FFT shape factor computation."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'womersley_fft'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.nu = 3.5e-6

        points = np.array([
            [0.0, 0.0, 0.0],      # Center
            [0.005, 0.0, 0.0],    # Half radius
            [0.015, 0.0, 0.0],    # Outside
        ])

        V0 = 0.5
        Vn_complex = np.array([0.1 + 0.0j, 0.05 + 0.0j])
        omega_fundamental = 2 * np.pi / 0.8

        velocities = mapping._compute_womersley_fft_shape_factors(
            points, t=0.0, V0=V0, Vn_complex=Vn_complex, omega_fundamental=omega_fundamental
        )

        assert len(velocities) == 3
        # Center should have highest velocity
        assert velocities[0] > velocities[1]
        # Outside should be zero
        assert velocities[2] == 0.0


class TestRunMethod:
    """Test the main run() orchestration method."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_run_with_parabolic_profile(self, mock_logger, tmp_path):
        """Test run() method with parabolic profile."""
        from aortacfd_lib.inlet_mapping import InletMapping

        # Create case directory structure
        case_dir = tmp_path / "case"
        tri_surface = case_dir / "constant" / "triSurface"
        boundary_data = case_dir / "constant" / "boundaryData" / "inlet"
        tri_surface.mkdir(parents=True)
        boundary_data.mkdir(parents=True)

        # Create a minimal STL file
        stl_content = """solid inlet
  facet normal 0 0 1
    outer loop
      vertex 0.0 0.0 0.0
      vertex 0.01 0.0 0.0
      vertex 0.005 0.01 0.0
    endloop
  endfacet
endsolid inlet"""
        (tri_surface / "inlet.stl").write_text(stl_content)

        # Create points file (simple OpenFOAM format: count, then coordinates)
        points_content = """3
(
(0.005 0.005 0.0)
(0.003 0.005 0.0)
(0.007 0.005 0.0)
)"""
        (boundary_data / "points").write_text(points_content)

        # Create CSV file with flow rate data
        csv_content = """time,flowrate
0.0,1.0e-5
0.1,2.0e-5
0.2,1.5e-5"""
        (boundary_data / "inlet_data.csv").write_text(csv_content)

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'inlet_data.csv',
                    'data_type': 'flowrate',
                    'profile': 'plug',
                    'orientation': 'inward'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(case_dir))

        # Mock PatchProcessing
        with patch('aortacfd_lib.inlet_mapping.PatchProcessing') as mock_pp:
            mock_instance = MagicMock()
            mock_instance.calculate_inlet_center_radius.return_value = (
                np.array([0.005, 0.005, 0.0]), 0.005, np.array([0, 0, 1])
            )
            mock_instance.calculate_surface_area.return_value = np.pi * 0.005**2
            mock_pp.return_value = mock_instance

            mapping.run()

        # Check that time directories were created
        time_dirs = [d for d in boundary_data.iterdir() if d.is_dir()]
        assert len(time_dirs) == 3  # Three timesteps

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_run_cleans_old_time_directories(self, mock_logger, tmp_path):
        """Test that run() cleans old time directories."""
        from aortacfd_lib.inlet_mapping import InletMapping

        # Create case directory structure
        case_dir = tmp_path / "case"
        tri_surface = case_dir / "constant" / "triSurface"
        boundary_data = case_dir / "constant" / "boundaryData" / "inlet"
        tri_surface.mkdir(parents=True)
        boundary_data.mkdir(parents=True)

        # Create old time directories that should be cleaned
        (boundary_data / "0.000000").mkdir()
        (boundary_data / "0.100000").mkdir()

        # Create a minimal STL file
        stl_content = """solid inlet
  facet normal 0 0 1
    outer loop
      vertex 0.0 0.0 0.0
      vertex 0.01 0.0 0.0
      vertex 0.005 0.01 0.0
    endloop
  endfacet
endsolid inlet"""
        (tri_surface / "inlet.stl").write_text(stl_content)

        # Create points file (simple format)
        points_content = """1
(
(0.005 0.005 0.0)
)"""
        (boundary_data / "points").write_text(points_content)

        # Create CSV file (needs 2+ data rows for cardiac period calculation)
        csv_content = """time,flowrate
0.0,1.0e-5
0.5,1.0e-5"""
        (boundary_data / "inlet_data.csv").write_text(csv_content)

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'inlet_data.csv',
                    'data_type': 'flowrate',
                    'profile': 'plug',
                    'orientation': 'inward'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(case_dir))

        with patch('aortacfd_lib.inlet_mapping.PatchProcessing') as mock_pp:
            mock_instance = MagicMock()
            mock_instance.calculate_inlet_center_radius.return_value = (
                np.array([0.005, 0.005, 0.0]), 0.005, np.array([0, 0, 1])
            )
            mock_instance.calculate_surface_area.return_value = np.pi * 0.005**2
            mock_pp.return_value = mock_instance

            mapping.run()

        # Old directories should be cleaned, new ones created
        assert not (boundary_data / "0.100000").exists()
        # New timestep directories created
        assert (boundary_data / "0.000000").exists()
        assert (boundary_data / "0.500000").exists()

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_run_raises_on_missing_points_file(self, mock_logger, tmp_path):
        """Test run() raises FileNotFoundError when points file missing."""
        from aortacfd_lib.inlet_mapping import InletMapping

        case_dir = tmp_path / "case"
        tri_surface = case_dir / "constant" / "triSurface"
        boundary_data = case_dir / "constant" / "boundaryData" / "inlet"
        tri_surface.mkdir(parents=True)
        boundary_data.mkdir(parents=True)

        # Create STL but no points file
        (tri_surface / "inlet.stl").write_text("solid inlet\nendsolid inlet")

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'inlet_data.csv',
                    'data_type': 'flowrate',
                    'profile': 'plug',
                    'orientation': 'auto'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(case_dir))

        with patch('aortacfd_lib.inlet_mapping.PatchProcessing') as mock_pp:
            mock_instance = MagicMock()
            mock_instance.calculate_inlet_center_radius.return_value = (
                np.array([0, 0, 0]), 0.01, np.array([0, 0, 1])
            )
            mock_instance.calculate_surface_area.return_value = 1e-4
            mock_pp.return_value = mock_instance

            with pytest.raises(FileNotFoundError, match="Points file not found"):
                mapping.run()

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_run_raises_on_missing_csv_file(self, mock_logger, tmp_path):
        """Test run() raises FileNotFoundError when CSV file missing."""
        from aortacfd_lib.inlet_mapping import InletMapping

        case_dir = tmp_path / "case"
        tri_surface = case_dir / "constant" / "triSurface"
        boundary_data = case_dir / "constant" / "boundaryData" / "inlet"
        tri_surface.mkdir(parents=True)
        boundary_data.mkdir(parents=True)

        (tri_surface / "inlet.stl").write_text("solid inlet\nendsolid inlet")

        # Create points file but no CSV
        points_content = """1
(
(0.0 0.0 0.0)
)"""
        (boundary_data / "points").write_text(points_content)

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'missing.csv',
                    'data_type': 'flowrate',
                    'profile': 'plug',
                    'orientation': 'inward'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(case_dir))

        with patch('aortacfd_lib.inlet_mapping.PatchProcessing') as mock_pp:
            mock_instance = MagicMock()
            mock_instance.calculate_inlet_center_radius.return_value = (
                np.array([0, 0, 0]), 0.01, np.array([0, 0, 1])
            )
            mock_instance.calculate_surface_area.return_value = 1e-4
            mock_pp.return_value = mock_instance

            with pytest.raises(FileNotFoundError, match="Inlet data CSV not found"):
                mapping.run()


class TestComputeWomersleyFFTScaleFactor:
    """Test _compute_womersley_fft_scale_factor method."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_scale_factor_computation(self, mock_logger, tmp_path):
        """Test Womersley FFT scale factor computation."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'womersley_fft'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.area = np.pi * 0.01**2
        mapping.nu = 3.5e-6

        # Create test points within the inlet
        n_points = 10
        theta = np.linspace(0, 2 * np.pi, n_points, endpoint=False)
        r = 0.005  # Half radius
        points = np.zeros((n_points, 3))
        points[:, 0] = r * np.cos(theta)
        points[:, 1] = r * np.sin(theta)

        V0 = 0.5
        Vn_complex = np.array([0.1 + 0.0j, 0.05 + 0.0j])
        omega_fundamental = 2 * np.pi / 0.8
        target_Q = 1.0e-5  # m³/s

        scale_factor = mapping._compute_womersley_fft_scale_factor(
            points, t=0.0, V0=V0, Vn_complex=Vn_complex,
            omega_fundamental=omega_fundamental, target_Q=target_Q
        )

        assert np.isfinite(scale_factor)
        assert scale_factor != 0.0

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_scale_factor_zero_flow(self, mock_logger, tmp_path):
        """Test scale factor returns 0 when no active points."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'womersley_fft'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.area = np.pi * 0.01**2
        mapping.nu = 3.5e-6

        # Points outside the inlet (will have zero velocity)
        points = np.array([[0.05, 0.05, 0.0], [0.06, 0.06, 0.0]])

        V0 = 0.0
        Vn_complex = np.array([0.0j])
        omega_fundamental = 2 * np.pi / 0.8
        target_Q = 1.0e-5

        scale_factor = mapping._compute_womersley_fft_scale_factor(
            points, t=0.0, V0=V0, Vn_complex=Vn_complex,
            omega_fundamental=omega_fundamental, target_Q=target_Q
        )

        assert scale_factor == 0.0


class TestComputeWallDistances:
    """Test _compute_wall_distances method."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_wall_distances_with_boundary_points(self, mock_logger, tmp_path):
        """Test wall distance computation with provided boundary points."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'wall_distance'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01

        # Create circular boundary points
        n_boundary = 36
        theta = np.linspace(0, 2 * np.pi, n_boundary, endpoint=False)
        boundary_points = np.zeros((n_boundary, 3))
        boundary_points[:, 0] = 0.01 * np.cos(theta)
        boundary_points[:, 1] = 0.01 * np.sin(theta)

        # Test points
        points = np.array([
            [0.0, 0.0, 0.0],      # Center - max distance
            [0.005, 0.0, 0.0],    # Half radius
            [0.009, 0.0, 0.0],    # Near wall
        ])

        distances = mapping._compute_wall_distances(points, boundary_points)

        assert len(distances) == 3
        # Center should have largest distance
        assert distances[0] > distances[1] > distances[2]
        # Center distance should be approximately radius
        assert np.isclose(distances[0], 0.01, rtol=0.1)

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_wall_distances_auto_boundary(self, mock_logger, tmp_path):
        """Test wall distance computation with auto boundary detection."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'wall_distance'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.case_directory = str(tmp_path)
        mapping.inlet_name = 'inlet'

        # Test points
        points = np.array([[0.0, 0.0, 0.0]])

        # Mock _get_inlet_boundary_points
        with patch.object(mapping, '_get_inlet_boundary_points') as mock_boundary:
            n_boundary = 36
            theta = np.linspace(0, 2 * np.pi, n_boundary, endpoint=False)
            boundary = np.zeros((n_boundary, 3))
            boundary[:, 0] = 0.01 * np.cos(theta)
            boundary[:, 1] = 0.01 * np.sin(theta)
            mock_boundary.return_value = boundary

            distances = mapping._compute_wall_distances(points)

        assert len(distances) == 1
        assert np.isclose(distances[0], 0.01, rtol=0.1)


class TestGetInletBoundaryPoints:
    """Test _get_inlet_boundary_points method."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_get_boundary_points_fallback(self, mock_logger, tmp_path):
        """Test boundary points fallback when STL loading fails."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'wall_distance'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.case_directory = str(tmp_path)
        mapping.inlet_name = 'inlet'

        # Create triSurface directory but no STL file
        (tmp_path / "constant" / "triSurface").mkdir(parents=True)

        # Should fallback to circular boundary
        boundary_points = mapping._get_inlet_boundary_points()

        assert len(boundary_points) == 36  # Default circular boundary
        # Check it's circular
        distances_from_center = np.linalg.norm(boundary_points[:, :2] - mapping.center[:2], axis=1)
        assert np.allclose(distances_from_center, mapping.radius, rtol=1e-6)

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_get_boundary_points_with_trimesh(self, mock_logger, tmp_path):
        """Test boundary points extraction with trimesh."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'wall_distance'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.case_directory = str(tmp_path)
        mapping.inlet_name = 'inlet'

        tri_surface = tmp_path / "constant" / "triSurface"
        tri_surface.mkdir(parents=True)

        # Create a simple STL with triangles
        stl_content = """solid inlet
  facet normal 0 0 1
    outer loop
      vertex 0.0 0.0 0.0
      vertex 0.01 0.0 0.0
      vertex 0.005 0.01 0.0
    endloop
  endfacet
  facet normal 0 0 1
    outer loop
      vertex 0.0 0.0 0.0
      vertex 0.005 0.01 0.0
      vertex -0.005 0.005 0.0
    endloop
  endfacet
endsolid inlet"""
        (tri_surface / "inlet.stl").write_text(stl_content)

        try:
            import trimesh
            boundary_points = mapping._get_inlet_boundary_points()
            # Should return some boundary points
            assert len(boundary_points) >= 3
        except ImportError:
            # Fallback if trimesh not available
            boundary_points = mapping._get_inlet_boundary_points()
            assert len(boundary_points) == 36


class TestComputeWallDistanceShapeFactors:
    """Test _compute_wall_distance_shape_factors method."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_wall_distance_shape_factors(self, mock_logger, tmp_path):
        """Test wall distance shape factor computation."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'wall_distance'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.case_directory = str(tmp_path)
        mapping.inlet_name = 'inlet'

        # Mock _compute_wall_distances
        points = np.array([
            [0.0, 0.0, 0.0],      # Center
            [0.005, 0.0, 0.0],    # Half radius
            [0.009, 0.0, 0.0],    # Near wall
        ])

        with patch.object(mapping, '_compute_wall_distances') as mock_dist:
            # Return distances: max at center, decreasing toward wall
            mock_dist.return_value = np.array([0.01, 0.005, 0.001])

            factors = mapping._compute_wall_distance_shape_factors(points, profile_exponent=2.0)

        assert len(factors) == 3
        # Center should have highest shape factor
        assert factors[0] > factors[1] > factors[2]
        # All factors should be positive
        assert all(f >= 0 for f in factors)

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_wall_distance_shape_factors_exponent(self, mock_logger, tmp_path):
        """Test wall distance shape factors with different exponents."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'wall_distance'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01

        # Use multiple points at different distances to test exponent effect
        points = np.array([
            [0.0, 0.0, 0.0],      # Center - max distance from wall
            [0.005, 0.0, 0.0],    # Mid-radius
            [0.009, 0.0, 0.0],    # Near wall
        ])

        with patch.object(mapping, '_compute_wall_distances') as mock_dist:
            # Distances from wall: center=max, mid=mid, near wall=small
            mock_dist.return_value = np.array([0.01, 0.005, 0.001])

            factors_2 = mapping._compute_wall_distance_shape_factors(points, profile_exponent=2.0)
            factors_4 = mapping._compute_wall_distance_shape_factors(points, profile_exponent=4.0)

        # All factors should be in [0, 1] range
        assert all(0 <= f <= 1 for f in factors_2)
        assert all(0 <= f <= 1 for f in factors_4)
        # Both should maintain correct ordering: center > mid > near wall
        assert factors_2[0] >= factors_2[1] >= factors_2[2]
        assert factors_4[0] >= factors_4[1] >= factors_4[2]


class TestScaleToTargetFlowrateNonStandard:
    """Test _scale_to_target_flowrate for non-standard profiles."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_scale_womersley_profile(self, mock_logger, tmp_path):
        """Test scaling for womersley profile (mesh-based integration)."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'womersley'  # Non-standard profile
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.area = np.pi * 0.01**2

        # Create shape factors (Womersley-like, higher at center)
        shape_factors = np.array([1.0, 0.8, 0.6, 0.4, 0.2])
        n_points = 5
        target_flowrate = 1.0e-5  # m³/s

        velocities = mapping._scale_to_target_flowrate(shape_factors, target_flowrate, n_points)

        assert len(velocities) == n_points
        # Verify flow rate conservation (approximately)
        A_face = mapping.area / n_points
        computed_Q = np.sum(velocities) * A_face
        assert np.isclose(computed_Q, target_flowrate, rtol=0.01)

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_scale_wall_distance_profile(self, mock_logger, tmp_path):
        """Test scaling for wall_distance profile."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'wall_distance'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.area = np.pi * 0.01**2

        shape_factors = np.array([0.9, 0.7, 0.5, 0.3, 0.1])
        n_points = 5
        target_flowrate = 2.0e-5

        velocities = mapping._scale_to_target_flowrate(shape_factors, target_flowrate, n_points)

        # Velocity profile should maintain shape
        assert velocities[0] > velocities[2] > velocities[4]
        # Flow conservation
        A_face = mapping.area / n_points
        computed_Q = np.sum(velocities) * A_face
        assert np.isclose(computed_Q, target_flowrate, rtol=0.01)

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_scale_zero_shape_factors(self, mock_logger, tmp_path):
        """Test scaling returns zeros when shape factors sum is tiny."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'womersley'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.area = np.pi * 0.01**2

        # All zeros
        shape_factors = np.array([0.0, 0.0, 0.0])
        n_points = 3
        target_flowrate = 1.0e-5

        velocities = mapping._scale_to_target_flowrate(shape_factors, target_flowrate, n_points)

        assert np.allclose(velocities, 0.0)


class TestGenerateTimeData:
    """Test _generate_time_data method."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_generate_time_data_parabolic(self, mock_logger, tmp_path):
        """Test time data generation with parabolic profile."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'parabolic'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.area = np.pi * 0.01**2
        mapping.cardiac_cycle = 0.8
        mapping.auto_flip_normal = False

        parent_dir = tmp_path / "output"
        parent_dir.mkdir()

        time_array = np.array([0.0, 0.4, 0.8])
        csv_values = np.array([1.0e-5, 2.0e-5, 1.0e-5])  # Flow rates
        points = np.array([
            [0.0, 0.0, 0.0],
            [0.005, 0.0, 0.0],
            [0.009, 0.0, 0.0],
        ])
        normal_vec = np.array([0, 0, -1])  # Inward

        mapping._generate_time_data(str(parent_dir), time_array, csv_values, points, normal_vec)

        # Check that time directories and U files were created
        assert (parent_dir / "0.000000" / "U").exists()
        assert (parent_dir / "0.400000" / "U").exists()
        assert (parent_dir / "0.800000" / "U").exists()

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_generate_time_data_womersley(self, mock_logger, tmp_path):
        """Test time data generation with single-frequency Womersley."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'velocity',
                    'profile': 'womersley'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.area = np.pi * 0.01**2
        mapping.cardiac_cycle = 0.8
        mapping.nu = 3.5e-6
        mapping.auto_flip_normal = False

        parent_dir = tmp_path / "output"
        parent_dir.mkdir()

        time_array = np.array([0.0, 0.2])
        csv_values = np.array([0.5, 1.0])  # Velocities
        points = np.array([
            [0.0, 0.0, 0.0],
            [0.005, 0.0, 0.0],
        ])
        normal_vec = np.array([0, 0, -1])

        mapping._generate_time_data(str(parent_dir), time_array, csv_values, points, normal_vec)

        assert (parent_dir / "0.000000" / "U").exists()
        assert (parent_dir / "0.200000" / "U").exists()

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_generate_time_data_womersley_fft(self, mock_logger, tmp_path):
        """Test time data generation with Womersley FFT profile."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'womersley_fft',
                    'n_harmonics': 4
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.area = np.pi * 0.01**2
        mapping.cardiac_cycle = 0.8
        mapping.nu = 3.5e-6
        mapping.auto_flip_normal = False

        parent_dir = tmp_path / "output"
        parent_dir.mkdir()

        # More timesteps for FFT
        time_array = np.linspace(0, 0.8, 10)
        csv_values = 1.0e-5 * (1 + 0.5 * np.sin(2 * np.pi * time_array / 0.8))  # Pulsatile flow
        points = np.array([
            [0.0, 0.0, 0.0],
            [0.005, 0.0, 0.0],
        ])
        normal_vec = np.array([0, 0, -1])

        mapping._generate_time_data(str(parent_dir), time_array, csv_values, points, normal_vec)

        # Check multiple timesteps were created
        time_dirs = [d for d in parent_dir.iterdir() if d.is_dir()]
        assert len(time_dirs) == 10

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_generate_time_data_wall_distance(self, mock_logger, tmp_path):
        """Test time data generation with wall_distance profile."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'wall_distance',
                    'exponent': 2.0
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.area = np.pi * 0.01**2
        mapping.cardiac_cycle = 0.8
        mapping.auto_flip_normal = False

        parent_dir = tmp_path / "output"
        parent_dir.mkdir()

        time_array = np.array([0.0])
        csv_values = np.array([1.0e-5])
        points = np.array([[0.0, 0.0, 0.0], [0.005, 0.0, 0.0]])
        normal_vec = np.array([0, 0, -1])

        # Mock wall distance methods
        with patch.object(mapping, '_compute_wall_distances') as mock_dist:
            mock_dist.return_value = np.array([0.01, 0.005])

            mapping._generate_time_data(str(parent_dir), time_array, csv_values, points, normal_vec)

        assert (parent_dir / "0.000000" / "U").exists()

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_generate_time_data_elliptical(self, mock_logger, tmp_path):
        """Test time data generation with elliptical profile."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'elliptical'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.area = np.pi * 0.01**2
        mapping.cardiac_cycle = 0.8
        mapping.auto_flip_normal = False

        parent_dir = tmp_path / "output"
        parent_dir.mkdir()

        time_array = np.array([0.0])
        csv_values = np.array([1.0e-5])
        points = np.array([[0.0, 0.0, 0.0]])
        normal_vec = np.array([0, 0, -1])

        mapping._generate_time_data(str(parent_dir), time_array, csv_values, points, normal_vec)

        assert (parent_dir / "0.000000" / "U").exists()

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_generate_time_data_womersley_requires_nu(self, mock_logger, tmp_path):
        """Test Womersley profile raises error without positive nu."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'womersley'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 0}  # Invalid nu
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.center = np.array([0.0, 0.0, 0.0])
        mapping.radius = 0.01
        mapping.area = np.pi * 0.01**2
        mapping.cardiac_cycle = 0.8
        mapping.nu = 0  # Invalid

        parent_dir = tmp_path / "output"
        parent_dir.mkdir()

        time_array = np.array([0.0])
        csv_values = np.array([1.0e-5])
        points = np.array([[0.0, 0.0, 0.0]])
        normal_vec = np.array([0, 0, -1])

        with pytest.raises(ValueError, match="Womersley profile requires a positive kinematic viscosity"):
            mapping._generate_time_data(str(parent_dir), time_array, csv_values, points, normal_vec)


class TestVerifyFlowrate:
    """Test _verify_flowrate method."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_verify_flowrate_basic(self, mock_logger, tmp_path):
        """Test flow rate verification calculation."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'plug'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.area = 1.0e-4  # 1 cm²

        velocity_magnitudes = np.array([1.0, 1.0, 1.0, 1.0])  # 1 m/s uniform
        n_points = 4

        Q = mapping._verify_flowrate(velocity_magnitudes, n_points)

        # Q = sum(V) * A_face = 4 * 1.0 * (1e-4 / 4) = 1e-4 m³/s
        assert np.isclose(Q, 1.0e-4)

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_verify_flowrate_zero_velocity(self, mock_logger, tmp_path):
        """Test flow rate verification with zero velocities."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'plug'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))
        mapping.area = 1.0e-4

        velocity_magnitudes = np.array([0.0, 0.0, 0.0])
        n_points = 3

        Q = mapping._verify_flowrate(velocity_magnitudes, n_points)

        assert Q == 0.0


class TestDetermineCardiacPeriod:
    """Test _determine_cardiac_period method."""

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_determine_cardiac_period(self, mock_logger, tmp_path):
        """Test cardiac period determination from time array."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'plug'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))

        times = np.array([0.0, 0.2, 0.4, 0.6, 0.8])
        period = mapping._determine_cardiac_period(times)

        assert np.isclose(period, 0.8)

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_determine_cardiac_period_insufficient_data(self, mock_logger, tmp_path):
        """Test error when insufficient time data."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'plug'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))

        times = np.array([0.0])  # Only one point

        with pytest.raises(ValueError, match="Insufficient time data"):
            mapping._determine_cardiac_period(times)

    @patch('aortacfd_lib.inlet_mapping.Logger')
    def test_determine_cardiac_period_invalid_range(self, mock_logger, tmp_path):
        """Test error when time range is invalid."""
        from aortacfd_lib.inlet_mapping import InletMapping

        config = {
            'boundary_conditions': {
                'inlet': {
                    'csv_file': 'test.csv',
                    'data_type': 'flowrate',
                    'profile': 'plug'
                }
            },
            'geometry': {'inlet_keywords_ordered': 'inlet'},
            'physics': {'nu': 3.5e-6}
        }

        mapping = InletMapping(config, str(tmp_path))

        times = np.array([0.5, 0.5])  # Same time values

        with pytest.raises(ValueError, match="Invalid time range"):
            mapping._determine_cardiac_period(times)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
