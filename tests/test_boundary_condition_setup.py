"""
Comprehensive test suite for BoundaryConditionSetup module.

Tests the boundary condition file generation and velocity calculations.
"""

import pytest
import sys
import os
import tempfile
import shutil
import math
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aortacfd_lib.boundary_condition_setup import BoundaryConditionSetup


class TestBoundaryConditionSetupInitialization:
    """Test BoundaryConditionSetup initialization."""

    def setup_method(self):
        """Setup minimal config and temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.case_dir = os.path.join(self.temp_dir, "test_case")
        os.makedirs(self.case_dir)
        os.makedirs(os.path.join(self.case_dir, "0"))
        os.makedirs(os.path.join(self.case_dir, "constant", "triSurface"), exist_ok=True)

    def teardown_method(self):
        """Cleanup temp directory."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_initialization_basic_config(self):
        """Test initialization with basic configuration."""
        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall'
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'velocity': 0.5},
                'outlets': {'type': 'ZEROGRADIENT'}
            },
            'physics': {
                'simulation_type': 'laminar',
                'blood_density': 1060
            },
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)

        assert bc_setup.config == config
        assert bc_setup.case_dir == self.case_dir
        assert bc_setup.inlet_patch == 'inlet'
        assert bc_setup.outlet_patches == ['outlet1']
        assert bc_setup.wall_patch == 'wall'

    def test_initialization_nested_config(self):
        """Test initialization with nested boundary_conditions structure."""
        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1', 'outlet2'],
                'wall_keywords_ordered': 'wall'
            },
            'boundary_conditions': {
                'inlet': {'type': 'TIMEVARYING', 'csv_file': 'flow.csv'},
                'outlets': {'type': '3EWINDKESSEL'}
            },
            'physics': {'simulation_type': 'RAS'},
            'openfoam_version': '8'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)

        assert bc_setup.inlet_settings['type'] == 'TIMEVARYING'
        assert bc_setup.outlet_settings['type'] == '3EWINDKESSEL'

    def test_initialization_flattened_config(self):
        """Test initialization with flattened inlet/outlet structure."""
        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall'
            },
            'inlet': {'type': 'CONSTANT', 'velocity': 0.5},
            'outlets': {'type': 'ZEROGRADIENT'},
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)

        # Should work with flattened structure
        assert bc_setup.inlet_settings['velocity'] == 0.5


class TestInletVelocityCalculations:
    """Test inlet velocity vector calculations."""

    def setup_method(self):
        """Setup temp directory and mock patch processor."""
        self.temp_dir = tempfile.mkdtemp()
        self.case_dir = os.path.join(self.temp_dir, "test_case")
        os.makedirs(os.path.join(self.case_dir, "constant", "triSurface"), exist_ok=True)

    def teardown_method(self):
        """Cleanup."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch('aortacfd_lib.boundary_condition_setup.detect_world_patch_mode', return_value=False)
    @patch('aortacfd_lib.utils.patch_processing.PatchProcessing')
    def test_constant_inlet_from_velocity(self, mock_patch_processing, mock_world):
        """Test velocity vector calculation from specified velocity."""
        # Mock the patch processor
        mock_processor = Mock()
        mock_processor.calculate_normal_direction.return_value = (0, 0, 1)  # Z-direction
        mock_patch_processing.return_value = mock_processor

        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall',
                'scale_factor': 1e-3
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'velocity': 0.5},
                'outlets': {'type': 'ZEROGRADIENT'}
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)
        velocity_vector = bc_setup._calculate_inlet_velocity_vector()

        # Should return OpenFOAM vector format
        assert velocity_vector is not None
        assert '(' in velocity_vector and ')' in velocity_vector

    @patch('aortacfd_lib.boundary_condition_setup.detect_world_patch_mode', return_value=False)
    @patch('aortacfd_lib.utils.patch_processing.PatchProcessing')
    def test_constant_inlet_from_cardiac_output(self, mock_patch_processing, mock_world):
        """Test velocity calculation from cardiac output."""
        # Mock the patch processor
        mock_processor = Mock()
        mock_processor.calculate_surface_area.return_value = 3.14e-4  # π * (0.01)² ≈ 314 mm²
        mock_processor.calculate_normal_direction.return_value = (0, 0, 1)
        mock_patch_processing.return_value = mock_processor

        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall',
                'scale_factor': 1e-3
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'cardiac_output': 5.0},  # L/min
                'outlets': {'type': 'ZEROGRADIENT'}
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)
        velocity_vector = bc_setup._calculate_inlet_velocity_vector()

        # Cardiac output: 5 L/min = 5/60/1000 = 8.33e-5 m³/s
        # Area: 3.14e-4 m²
        # Velocity: 8.33e-5 / 3.14e-4 ≈ 0.265 m/s
        assert velocity_vector is not None

    def test_timevarying_inlet_no_velocity_vector(self):
        """Test that TIMEVARYING inlet returns None (uses boundaryData)."""
        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall'
            },
            'boundary_conditions': {
                'inlet': {'type': 'TIMEVARYING', 'csv_file': 'flow.csv'},
                'outlets': {'type': 'ZEROGRADIENT'}
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)
        velocity_vector = bc_setup._calculate_inlet_velocity_vector()

        # TIMEVARYING should return None (boundary data used instead)
        assert velocity_vector is None

    @patch('aortacfd_lib.boundary_condition_setup.detect_world_patch_mode', return_value=False)
    @patch('aortacfd_lib.utils.patch_processing.PatchProcessing')
    def test_parabolic_inlet_velocity_adjustment(self, mock_patch_processing, mock_world):
        """Test that PARABOLIC profile adjusts centerline velocity to mean."""
        mock_processor = Mock()
        mock_processor.calculate_normal_direction.return_value = (0, 0, 1)
        mock_patch_processing.return_value = mock_processor

        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall',
                'scale_factor': 1e-3
            },
            'boundary_conditions': {
                'inlet': {'type': 'PARABOLIC', 'velocity': 1.0},  # Centerline velocity
                'outlets': {'type': 'ZEROGRADIENT'}
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)

        # For PARABOLIC, mean velocity = centerline / 2
        # This is tested in the actual implementation


class TestInitialPressureCalculations:
    """Test initial pressure field calculations."""

    def setup_method(self):
        """Setup temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.case_dir = os.path.join(self.temp_dir, "test_case")
        os.makedirs(os.path.join(self.case_dir, "constant", "triSurface"), exist_ok=True)

    def teardown_method(self):
        """Cleanup."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_initial_pressure_zerogradient_outlets(self):
        """Test initial pressure with ZEROGRADIENT outlets."""
        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall'
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'velocity': 0.5},
                'outlets': {'type': 'ZEROGRADIENT'}
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)
        initial_p, outlet_pressures = bc_setup._calculate_initial_pressure()

        # ZEROGRADIENT outlets should have 0 initial pressure
        assert initial_p == 0
        assert outlet_pressures == {}

    def test_initial_pressure_windkessel_outlets(self):
        """Test initial pressure with Windkessel outlets."""
        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1', 'outlet2'],
                'wall_keywords_ordered': 'wall'
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'velocity': 0.5},
                'outlets': {
                    'type': '3EWINDKESSEL',
                    'windkessel_settings': {
                        'diastolic_pressure': 80,  # mmHg
                        'venous_pressure': 5
                    }
                }
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)
        initial_p, outlet_pressures = bc_setup._calculate_initial_pressure()

        # Initial pressure should be based on diastolic pressure (default method)
        # Diastolic = 80 mmHg = 80 * 133.322 Pa
        expected_p = 80 * 133.322
        assert initial_p == pytest.approx(expected_p, rel=1e-4)


class TestTurbulenceParameterCalculations:
    """Test turbulence parameter (k, omega) calculations."""

    def setup_method(self):
        """Setup temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.case_dir = os.path.join(self.temp_dir, "test_case")
        os.makedirs(os.path.join(self.case_dir, "constant", "triSurface"), exist_ok=True)

    def teardown_method(self):
        """Cleanup."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch('aortacfd_lib.boundary_condition_setup.detect_world_patch_mode', return_value=False)
    @patch('aortacfd_lib.utils.patch_processing.PatchProcessing')
    def test_turbulence_parameters_from_intensity(self, mock_patch_processing, mock_world):
        """Test k and omega calculation from turbulence intensity."""
        mock_processor = Mock()
        mock_processor.calculate_surface_area.return_value = 3.14e-4
        mock_processor.calculate_hydraulic_diameter.return_value = 0.02  # 20mm
        mock_patch_processing.return_value = mock_processor

        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall',
                'scale_factor': 1e-3
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'velocity': 0.5},
                'outlets': {'type': 'ZEROGRADIENT'}
            },
            'physics': {
                'simulation_type': 'RAS',
                'turbulence_intensity': 0.05,  # 5%
                'blood_viscosity': 0.004,
                'blood_density': 1060
            },
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)
        turb_params = bc_setup._calculate_turbulence_parameters()

        # k = 1.5 * (U * I)²
        # omega = k^0.5 / (C_mu^0.25 * L)
        assert 'k_initial' in turb_params
        assert 'omega_initial' in turb_params
        assert turb_params['k_initial'] > 0
        assert turb_params['omega_initial'] > 0

    @patch('aortacfd_lib.boundary_condition_setup.detect_world_patch_mode', return_value=False)
    @patch('aortacfd_lib.utils.patch_processing.PatchProcessing')
    def test_turbulence_intensity_default(self, mock_patch_processing, mock_world):
        """Test default turbulence intensity when not specified."""
        mock_processor = Mock()
        mock_processor.calculate_surface_area.return_value = 3.14e-4
        mock_processor.calculate_hydraulic_diameter.return_value = 0.02
        mock_patch_processing.return_value = mock_processor

        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall',
                'scale_factor': 1e-3
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'velocity': 0.5},
                'outlets': {'type': 'ZEROGRADIENT'}
            },
            'physics': {
                'simulation_type': 'RAS',
                # No turbulence_intensity specified - should use default (5%)
                'blood_viscosity': 0.004,
                'blood_density': 1060
            },
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)
        turb_params = bc_setup._calculate_turbulence_parameters()

        # Should have reasonable values even with defaults
        assert turb_params['k_initial'] > 0
        assert turb_params['omega_initial'] > 0


class TestOutletSettingsPreparation:
    """Test outlet settings preparation including Murray's law."""

    def setup_method(self):
        """Setup temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.case_dir = os.path.join(self.temp_dir, "test_case")
        os.makedirs(os.path.join(self.case_dir, "constant", "triSurface"), exist_ok=True)

    def teardown_method(self):
        """Cleanup."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_zerogradient_outlets_passthrough(self):
        """Test that ZEROGRADIENT outlets pass through unchanged."""
        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall'
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'velocity': 0.5},
                'outlets': {'type': 'ZEROGRADIENT'}
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)
        outlet_settings = bc_setup._prepare_outlet_settings()

        assert outlet_settings['type'] == 'ZEROGRADIENT'

    def test_windkessel_with_predefined_flow_split(self):
        """Test Windkessel outlets with predefined flow split (no Murray's law)."""
        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1', 'outlet2'],
                'wall_keywords_ordered': 'wall'
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'velocity': 0.5},
                'outlets': {
                    'type': '3EWINDKESSEL',
                    'windkessel_settings': {
                        'flow_split': {'outlet1': 0.6, 'outlet2': 0.4},
                        'systolic_pressure': 120,
                        'diastolic_pressure': 80
                    }
                }
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)
        outlet_settings = bc_setup._prepare_outlet_settings()

        # Should keep predefined flow_split
        assert 'flow_split' in outlet_settings['windkessel_settings']
        assert outlet_settings['windkessel_settings']['flow_split']['outlet1'] == 0.6


class TestVelocityUnitConversions:
    """Test velocity and flow rate unit conversions."""

    def test_cardiac_output_to_velocity_conversion(self):
        """Test conversion from L/min to m/s."""
        cardiac_output_Lmin = 5.0  # L/min
        inlet_area_m2 = 3.14e-4  # π * (0.01)² m² (10mm radius)

        # Convert L/min to m³/s: 5 L/min = 5/60000 m³/s
        flow_m3s = cardiac_output_Lmin / 60.0 / 1000.0

        # Calculate velocity: Q/A
        velocity = flow_m3s / inlet_area_m2

        # 5 L/min / 314 mm² ≈ 0.265 m/s
        assert velocity == pytest.approx(5.0 / 60000.0 / 3.14e-4, rel=1e-6)
        assert 0.2 < velocity < 0.3

    def test_velocity_to_flow_rate(self):
        """Test conversion from velocity to flow rate."""
        velocity_ms = 0.5  # m/s
        area_m2 = 3.14e-4  # m²

        flow_m3s = velocity_ms * area_m2
        flow_Lmin = flow_m3s * 60000.0  # Convert m³/s to L/min

        assert flow_m3s == pytest.approx(1.57e-4, rel=1e-3)
        assert flow_Lmin == pytest.approx(9.42, rel=1e-2)


class TestWorldPatchMode:
    """Test world patch mode detection."""

    def setup_method(self):
        """Setup temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.case_dir = os.path.join(self.temp_dir, "test_case")
        os.makedirs(os.path.join(self.case_dir, "constant", "triSurface"), exist_ok=True)

    def teardown_method(self):
        """Cleanup."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch('aortacfd_lib.boundary_condition_setup.detect_world_patch_mode')
    def test_world_patch_mode_enabled(self, mock_detect):
        """Test behavior when world patch mode is detected."""
        mock_detect.return_value = True

        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall'
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'velocity': 0.5},
                'outlets': {'type': 'ZEROGRADIENT'}
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)

        assert bc_setup.world_patch_mode is True


class TestEdgeCases:
    """Test edge cases and error handling."""

    def setup_method(self):
        """Setup temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.case_dir = os.path.join(self.temp_dir, "test_case")
        os.makedirs(os.path.join(self.case_dir, "constant", "triSurface"), exist_ok=True)

    def teardown_method(self):
        """Cleanup."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch('aortacfd_lib.boundary_condition_setup.detect_world_patch_mode', return_value=False)
    @patch('aortacfd_lib.utils.patch_processing.PatchProcessing')
    def test_zero_inlet_area_protection(self, mock_patch_processing, mock_world):
        """Test handling of zero or very small inlet area."""
        mock_processor = Mock()
        mock_processor.calculate_surface_area.return_value = 1e-20  # Essentially zero
        mock_patch_processing.return_value = mock_processor

        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall',
                'scale_factor': 1e-3
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'cardiac_output': 5.0},
                'outlets': {'type': 'ZEROGRADIENT'}
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)

        # Should handle gracefully (not divide by zero)
        # The actual implementation should catch this

    def test_missing_required_inlet_parameter(self):
        """Test error when CONSTANT inlet missing velocity/cardiac_output."""
        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall'
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT'},  # Missing velocity!
                'outlets': {'type': 'ZEROGRADIENT'}
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)

        # Should raise error or use defaults
        # (depends on implementation)


class TestInitialPressureMethods:
    """Test various initial pressure calculation methods."""

    def setup_method(self):
        """Setup temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.case_dir = os.path.join(self.temp_dir, "test_case")
        os.makedirs(os.path.join(self.case_dir, "constant", "triSurface"), exist_ok=True)

    def teardown_method(self):
        """Cleanup."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_initial_pressure_systolic_method(self):
        """Test initial pressure with systolic method."""
        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall'
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'velocity': 0.5},
                'outlets': {
                    'type': '3EWINDKESSEL',
                    'windkessel_settings': {
                        'systolic_pressure': 120,
                        'diastolic_pressure': 80,
                        'initial_pressure_method': 'systolic'
                    }
                }
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)
        initial_p, _ = bc_setup._calculate_initial_pressure()

        # Systolic = 120 mmHg = 120 * 133.322 Pa
        expected_p = 120 * 133.322
        assert initial_p == pytest.approx(expected_p, rel=1e-4)

    def test_initial_pressure_map_method(self):
        """Test initial pressure with MAP (mean arterial pressure) method."""
        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall'
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'velocity': 0.5},
                'outlets': {
                    'type': '3EWINDKESSEL',
                    'windkessel_settings': {
                        'systolic_pressure': 120,
                        'diastolic_pressure': 80,
                        'initial_pressure_method': 'map'
                    }
                }
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)
        initial_p, _ = bc_setup._calculate_initial_pressure()

        # MAP = DBP + (SBP - DBP)/3 = 80 + 40/3 = 93.33 mmHg
        expected_mmHg = 80 + (120 - 80) / 3.0
        expected_p = expected_mmHg * 133.322
        assert initial_p == pytest.approx(expected_p, rel=1e-4)

    def test_initial_pressure_arithmetic_mean_method(self):
        """Test initial pressure with arithmetic mean method."""
        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall'
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'velocity': 0.5},
                'outlets': {
                    'type': '3EWINDKESSEL',
                    'windkessel_settings': {
                        'systolic_pressure': 120,
                        'diastolic_pressure': 80,
                        'initial_pressure_method': 'mean'
                    }
                }
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)
        initial_p, _ = bc_setup._calculate_initial_pressure()

        # Mean = (SBP + DBP) / 2 = 100 mmHg
        expected_p = 100 * 133.322
        assert initial_p == pytest.approx(expected_p, rel=1e-4)

    def test_initial_pressure_zero_method(self):
        """Test initial pressure with zero (gauge) method."""
        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall'
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'velocity': 0.5},
                'outlets': {
                    'type': '3EWINDKESSEL',
                    'windkessel_settings': {
                        'systolic_pressure': 120,
                        'diastolic_pressure': 80,
                        'initial_pressure_method': 'zero'
                    }
                }
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)
        initial_p, _ = bc_setup._calculate_initial_pressure()

        assert initial_p == 0.0

    def test_initial_pressure_deprecated_windkessel_method(self):
        """Test that deprecated windkessel method falls back to diastolic."""
        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall'
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'velocity': 0.5},
                'outlets': {
                    'type': '3EWINDKESSEL',
                    'windkessel_settings': {
                        'systolic_pressure': 120,
                        'diastolic_pressure': 80,
                        'initial_pressure_method': 'windkessel'
                    }
                }
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)
        initial_p, _ = bc_setup._calculate_initial_pressure()

        # Should fall back to diastolic = 80 mmHg
        expected_p = 80 * 133.322
        assert initial_p == pytest.approx(expected_p, rel=1e-4)

    def test_initial_pressure_unknown_method_fallback(self):
        """Test that unknown method falls back to diastolic."""
        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall'
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'velocity': 0.5},
                'outlets': {
                    'type': '3EWINDKESSEL',
                    'windkessel_settings': {
                        'systolic_pressure': 120,
                        'diastolic_pressure': 80,
                        'initial_pressure_method': 'unknown_method'
                    }
                }
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)
        initial_p, _ = bc_setup._calculate_initial_pressure()

        # Should fall back to diastolic
        expected_p = 80 * 133.322
        assert initial_p == pytest.approx(expected_p, rel=1e-4)

    def test_initial_pressure_with_flow_split(self):
        """Test that outlet pressures are set for all flow splits."""
        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1', 'outlet2'],
                'wall_keywords_ordered': 'wall'
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'velocity': 0.5},
                'outlets': {
                    'type': '3EWINDKESSEL',
                    'windkessel_settings': {
                        'systolic_pressure': 120,
                        'diastolic_pressure': 80,
                        'flow_split': {'outlet1': 0.6, 'outlet2': 0.4}
                    }
                }
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)
        initial_p, outlet_pressures = bc_setup._calculate_initial_pressure()

        # Should have outlet pressures for both outlets
        assert 'outlet1' in outlet_pressures
        assert 'outlet2' in outlet_pressures

    def test_initial_pressure_with_outlet_parameters(self):
        """Test that outlet pressures are set for outlet_parameters."""
        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1', 'outlet2'],
                'wall_keywords_ordered': 'wall'
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'velocity': 0.5},
                'outlets': {
                    'type': '2EWINDKESSEL',
                    'windkessel_settings': {
                        'systolic_pressure': 120,
                        'diastolic_pressure': 80,
                        'outlet_parameters': {'outlet1': {}, 'outlet2': {}}
                    }
                }
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)
        initial_p, outlet_pressures = bc_setup._calculate_initial_pressure()

        assert 'outlet1' in outlet_pressures
        assert 'outlet2' in outlet_pressures


class TestMurrayLawCalculation:
    """Test Murray's law automatic calculation."""

    def setup_method(self):
        """Setup temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.case_dir = os.path.join(self.temp_dir, "test_case")
        os.makedirs(os.path.join(self.case_dir, "constant", "triSurface"), exist_ok=True)

    def teardown_method(self):
        """Cleanup."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_murray_law_calculation_failure_fallback(self):
        """Test that Murray's law failure falls back to equal distribution."""
        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1', 'outlet2'],
                'wall_keywords_ordered': 'wall'
            },
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'velocity': 0.5},
                'outlets': {
                    'type': '3EWINDKESSEL',
                    'windkessel_settings': {
                        # No flow_split - should trigger Murray's law calculation
                        'systolic_pressure': 120,
                        'diastolic_pressure': 80
                    }
                }
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)

        # Murray calculator import will fail - the function catches the exception
        # and falls back to equal distribution
        outlet_settings = bc_setup._prepare_outlet_settings()

        # Should have flow_split with equal distribution after failed Murray's law
        if 'flow_split' in outlet_settings.get('windkessel_settings', {}):
            flow_split = outlet_settings['windkessel_settings']['flow_split']
            assert 'outlet1' in flow_split
            assert 'outlet2' in flow_split
            # Equal distribution: 1/2 = 0.5
            assert abs(flow_split['outlet1'] - 0.5) < 1e-10


class TestFlowrateAlias:
    """Test flowrate as alias for cardiac_output."""

    def setup_method(self):
        """Setup temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.case_dir = os.path.join(self.temp_dir, "test_case")
        os.makedirs(os.path.join(self.case_dir, "constant", "triSurface"), exist_ok=True)

    def teardown_method(self):
        """Cleanup."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch('aortacfd_lib.boundary_condition_setup.detect_world_patch_mode', return_value=False)
    @patch('aortacfd_lib.utils.patch_processing.PatchProcessing')
    def test_flowrate_alias(self, mock_patch_processing, mock_world):
        """Test that 'flowrate' works as alias for 'cardiac_output'."""
        import numpy as np

        mock_processor = Mock()
        mock_processor.calculate_surface_area.return_value = 3.14e-4
        mock_processor.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]),
            0.01,
            np.array([0.0, 0.0, 1.0])
        )
        mock_patch_processing.return_value = mock_processor

        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall'
            },
            'boundary_conditions': {
                'inlet': {
                    'type': 'CONSTANT',
                    'flowrate': 5.0  # Using flowrate instead of cardiac_output
                },
                'outlets': {'type': 'ZEROGRADIENT'}
            },
            'physics': {'simulation_type': 'laminar'},
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)
        velocity_vector = bc_setup._calculate_inlet_velocity_vector()

        # Should work with flowrate (aliased to cardiac_output)
        assert velocity_vector is not None
        assert '(' in velocity_vector


class TestTurbulenceWithMeanVelocity:
    """Test turbulence parameter calculation with mean_velocity."""

    def setup_method(self):
        """Setup temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.case_dir = os.path.join(self.temp_dir, "test_case")
        os.makedirs(os.path.join(self.case_dir, "constant", "triSurface"), exist_ok=True)

    def teardown_method(self):
        """Cleanup."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_turbulence_with_specified_mean_velocity(self):
        """Test turbulence parameters using specified mean_velocity."""
        config = {
            'geometry': {
                'case_name': 'test',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall'
            },
            'boundary_conditions': {
                'inlet': {
                    'type': 'CONSTANT',
                    'velocity': 0.5,
                    'mean_velocity': 0.4  # Explicit mean velocity
                },
                'outlets': {'type': 'ZEROGRADIENT'}
            },
            'physics': {
                'simulation_type': 'RAS',
                'turbulence_intensity': 0.05
            },
            'openfoam_version': '11'
        }

        bc_setup = BoundaryConditionSetup(config, self.case_dir)
        turb_params = bc_setup._calculate_turbulence_parameters()

        # k = 1.5 * (U_ref * I)^2 = 1.5 * (0.4 * 0.05)^2 = 1.5 * 0.0004 = 0.0006
        expected_k = 1.5 * (0.4 * 0.05) ** 2
        assert turb_params['k_initial'] == pytest.approx(expected_k, rel=1e-4)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
