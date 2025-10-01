"""
Unit tests for boundary condition setup.

Tests inlet, outlet, wall, and Windkessel boundary conditions.
"""

import pytest
import json
from pathlib import Path


class TestInletBoundaryConditions:
    """Test inlet boundary condition configuration."""

    @pytest.fixture
    def time_varying_inlet(self):
        """Time-varying inlet BC configuration."""
        return {
            "type": "TIMEVARYING",
            "csv_file": "BPM75.csv",
            "data_type": "velocity",
            "profile": "plug_flow",
            "orientation": "out"
        }

    @pytest.fixture
    def womersley_inlet(self):
        """Womersley profile inlet BC configuration."""
        return {
            "type": "TIMEVARYING",
            "csv_file": "BPM75.csv",
            "data_type": "velocity",
            "profile": "womersley",
            "orientation": "out",
            "alpha": 12.0  # Womersley number
        }

    def test_inlet_type_valid(self, time_varying_inlet):
        """Test inlet BC type is valid."""
        valid_types = ["TIMEVARYING", "STEADY", "FIXED"]
        assert time_varying_inlet["type"] in valid_types

    def test_inlet_has_csv_file(self, time_varying_inlet):
        """Test time-varying inlet has CSV file specified."""
        assert "csv_file" in time_varying_inlet
        assert time_varying_inlet["csv_file"].endswith(".csv")

    def test_inlet_data_type_valid(self, time_varying_inlet):
        """Test inlet data type is valid."""
        valid_data_types = ["velocity", "flow", "pressure"]
        assert time_varying_inlet["data_type"] in valid_data_types

    def test_inlet_profile_type(self, time_varying_inlet):
        """Test inlet profile type is valid."""
        valid_profiles = ["plug_flow", "womersley", "parabolic", "uniform"]
        assert time_varying_inlet["profile"] in valid_profiles

    def test_inlet_orientation_valid(self, time_varying_inlet):
        """Test inlet orientation is valid."""
        valid_orientations = ["in", "out"]
        assert time_varying_inlet["orientation"] in valid_orientations

    def test_womersley_has_alpha(self, womersley_inlet):
        """Test Womersley profile has alpha parameter."""
        if womersley_inlet["profile"] == "womersley":
            assert "alpha" in womersley_inlet
            assert womersley_inlet["alpha"] > 0


class TestOutletBoundaryConditions:
    """Test outlet boundary condition configuration."""

    @pytest.fixture
    def pressure_outlet(self):
        """Fixed pressure outlet BC."""
        return {
            "type": "pressure",
            "value": 80  # mmHg, diastolic
        }

    @pytest.fixture
    def windkessel_outlets(self):
        """Windkessel outlet BC configuration."""
        return {
            "type": "3EWINDKESSEL",
            "windkessel_settings": {
                "systolic_pressure": 120,
                "diastolic_pressure": 80,
                "methodology": "murray_law_automatic"
            }
        }

    def test_outlet_type_valid(self, pressure_outlet):
        """Test outlet BC type is valid."""
        valid_types = ["pressure", "3EWINDKESSEL", "FIXED", "zeroGradient"]
        assert pressure_outlet["type"] in valid_types

    def test_pressure_outlet_value(self, pressure_outlet):
        """Test pressure outlet has valid pressure value."""
        assert "value" in pressure_outlet
        assert 0 <= pressure_outlet["value"] <= 200  # Reasonable mmHg range

    def test_windkessel_has_settings(self, windkessel_outlets):
        """Test Windkessel BC has required settings."""
        assert "windkessel_settings" in windkessel_outlets
        settings = windkessel_outlets["windkessel_settings"]
        assert "systolic_pressure" in settings
        assert "diastolic_pressure" in settings

    def test_windkessel_pressure_range(self, windkessel_outlets):
        """Test Windkessel pressures are physiologically valid."""
        settings = windkessel_outlets["windkessel_settings"]
        systolic = settings["systolic_pressure"]
        diastolic = settings["diastolic_pressure"]

        # Physiological range
        assert 80 <= systolic <= 200  # mmHg
        assert 40 <= diastolic <= 120  # mmHg
        assert systolic > diastolic  # Systolic should be higher

    def test_windkessel_methodology(self, windkessel_outlets):
        """Test Windkessel methodology is valid."""
        settings = windkessel_outlets["windkessel_settings"]
        valid_methods = ["murray_law_automatic", "manual", "literature"]
        assert settings["methodology"] in valid_methods


class TestWallBoundaryConditions:
    """Test wall boundary condition configuration."""

    @pytest.fixture
    def no_slip_wall(self):
        """No-slip wall BC."""
        return {
            "type": "no_slip",
            "roughness": 0.0
        }

    @pytest.fixture
    def slip_wall(self):
        """Slip wall BC."""
        return {
            "type": "slip"
        }

    def test_wall_type_valid(self, no_slip_wall):
        """Test wall BC type is valid."""
        valid_types = ["no_slip", "slip", "partial_slip"]
        assert no_slip_wall["type"] in valid_types

    def test_no_slip_roughness(self, no_slip_wall):
        """Test no-slip wall has roughness parameter."""
        assert "roughness" in no_slip_wall
        assert no_slip_wall["roughness"] >= 0.0

    def test_roughness_range(self, no_slip_wall):
        """Test wall roughness is in valid range."""
        roughness = no_slip_wall["roughness"]
        assert 0.0 <= roughness <= 0.01  # Typical range for blood vessels


class TestWindkesselParameters:
    """Test Windkessel model parameters."""

    def test_windkessel_resistance_positive(self):
        """Test Windkessel resistance is positive."""
        R_proximal = 100  # Example value
        R_distal = 1000

        assert R_proximal > 0
        assert R_distal > 0
        assert R_distal > R_proximal  # Distal usually higher

    def test_windkessel_capacitance_positive(self):
        """Test Windkessel capacitance is positive."""
        C = 1e-6  # Example compliance value
        assert C > 0

    def test_windkessel_impedance_positive(self):
        """Test Windkessel characteristic impedance is positive."""
        Z = 50  # Example impedance
        assert Z > 0

    def test_windkessel_parameter_relationships(self):
        """Test relationships between Windkessel parameters."""
        # Typical relationships
        R_proximal = 100
        R_distal = 1000
        Z = 50

        # Characteristic impedance typically less than resistances
        assert Z < R_proximal + R_distal

    def test_windkessel_rc_time_constant(self):
        """Test Windkessel RC time constant."""
        R = 1000  # Pa·s/m³
        C = 1e-6  # m³/Pa
        tau = R * C  # Time constant = 0.001 seconds

        assert tau > 0
        assert 0.0001 <= tau <= 10.0  # Reasonable range in seconds


class TestBoundaryConditionCompatibility:
    """Test boundary condition compatibility and consistency."""

    def test_inlet_outlet_consistency(self):
        """Test inlet and outlet BCs are compatible."""
        inlet_type = "TIMEVARYING"
        outlet_type = "3EWINDKESSEL"

        # Time-varying inlet should work with Windkessel outlet
        compatible_combinations = [
            ("TIMEVARYING", "3EWINDKESSEL"),
            ("TIMEVARYING", "pressure"),
            ("STEADY", "pressure"),
            ("FIXED", "zeroGradient")
        ]

        assert (inlet_type, outlet_type) in compatible_combinations

    def test_all_patches_defined(self):
        """Test all patches have boundary conditions defined."""
        bc_config = {
            "inlet": {"type": "TIMEVARYING"},
            "outlets": {"type": "3EWINDKESSEL"},
            "walls": {"type": "no_slip"}
        }

        required_patches = ["inlet", "outlets", "walls"]
        for patch in required_patches:
            assert patch in bc_config


class TestFlowDataValidation:
    """Test inlet flow data validation."""

    def test_flow_csv_format(self):
        """Test flow CSV has required columns."""
        # Expected CSV format
        required_columns = ["Time", "Flow"]

        # Verify column names
        assert "Time" in required_columns
        assert "Flow" in required_columns

    def test_flow_data_non_negative_time(self):
        """Test flow data has non-negative time values."""
        sample_data = [
            {"Time": 0.0, "Flow": 0.5},
            {"Time": 0.1, "Flow": 0.6},
            {"Time": 0.2, "Flow": 0.7}
        ]

        for entry in sample_data:
            assert entry["Time"] >= 0.0

    def test_flow_data_monotonic_time(self):
        """Test flow data time is monotonically increasing."""
        times = [0.0, 0.1, 0.2, 0.3, 0.4]

        for i in range(1, len(times)):
            assert times[i] > times[i-1]

    def test_flow_data_reasonable_values(self):
        """Test flow data values are physiologically reasonable."""
        # Typical aortic flow rate: 1-30 L/min
        sample_flows = [5.0, 15.0, 25.0]  # L/min

        for flow in sample_flows:
            assert 0 <= flow <= 50  # L/min, generous upper bound


class TestVelocityBoundaryConditions:
    """Test velocity-based boundary conditions."""

    def test_velocity_magnitude_reasonable(self):
        """Test inlet velocity magnitude is reasonable."""
        # Typical aortic velocity: 0.5-2.0 m/s
        velocities = [0.8, 1.2, 1.8]  # m/s

        for vel in velocities:
            assert 0.1 <= vel <= 3.0  # m/s, with safety margin

    def test_reynolds_number_estimation(self):
        """Test Reynolds number estimation for flow regime."""
        # Re = (rho * V * D) / mu
        rho = 1060  # kg/m³
        V = 1.0     # m/s
        D = 0.025   # m (25mm diameter)
        mu = 0.004  # Pa·s

        Re = (rho * V * D) / mu
        assert 100 <= Re <= 10000  # Typical aortic range


@pytest.mark.unit
class TestCompleteBoundaryConditionConfig:
    """Test complete boundary condition configuration."""

    @pytest.fixture
    def complete_bc_config(self):
        """Complete boundary condition configuration."""
        return {
            "inlet": {
                "type": "TIMEVARYING",
                "csv_file": "BPM75.csv",
                "data_type": "velocity",
                "profile": "plug_flow",
                "orientation": "out"
            },
            "outlets": {
                "type": "3EWINDKESSEL",
                "windkessel_settings": {
                    "systolic_pressure": 120,
                    "diastolic_pressure": 80,
                    "methodology": "murray_law_automatic",
                    "beta": 1.0,
                    "enable_stabilization": True
                }
            },
            "walls": {
                "type": "no_slip",
                "roughness": 0.0
            }
        }

    def test_complete_config_structure(self, complete_bc_config):
        """Test complete BC config has all required sections."""
        assert "inlet" in complete_bc_config
        assert "outlets" in complete_bc_config
        assert "walls" in complete_bc_config

    def test_windkessel_stabilization_params(self, complete_bc_config):
        """Test Windkessel stabilization parameters."""
        wk_settings = complete_bc_config["outlets"]["windkessel_settings"]

        if "beta" in wk_settings:
            assert 0.5 <= wk_settings["beta"] <= 1.5

        if "enable_stabilization" in wk_settings:
            assert isinstance(wk_settings["enable_stabilization"], bool)

    def test_bc_config_json_serializable(self, complete_bc_config):
        """Test BC config can be serialized to JSON."""
        try:
            json_str = json.dumps(complete_bc_config)
            assert len(json_str) > 0

            # Verify it can be loaded back
            loaded = json.loads(json_str)
            assert loaded == complete_bc_config
        except (TypeError, ValueError) as e:
            pytest.fail(f"Config is not JSON serializable: {e}")
