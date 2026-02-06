"""
Test suite for the config schema module.

Tests cover:
- Enumerations
- Pydantic models (if available)
- Fallback dataclass implementations
- Configuration validation
- Default value handling
"""

import pytest
import sys
from pathlib import Path
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.schema import (
    PhysicsModel,
    NumericsProfile,
    InletType,
    OutletType,
    ReferenceRadiusStrategy,
    validate_config,
    is_pydantic_available,
    PYDANTIC_AVAILABLE,
)

# Import conditionally based on pydantic availability
if PYDANTIC_AVAILABLE:
    from config.schema import (
        PhysicsConfig,
        BoundaryLayerConfig,
        SnappySettings,
        MeshConfig,
        GeometryConfig,
        NumericsConfig,
        InletConfig,
        OutletConfig,
        BoundaryConditionsConfig,
        WindkesselConfig,
        SimulationConfig,
    )


class TestEnumerations:
    """Test configuration enumerations."""

    def test_physics_model_values(self):
        """Test PhysicsModel enum values."""
        assert PhysicsModel.LAMINAR.value == "laminar"
        assert PhysicsModel.RANS.value == "rans"
        assert PhysicsModel.LES.value == "les"

    def test_numerics_profile_values(self):
        """Test NumericsProfile enum values."""
        assert NumericsProfile.ROBUST.value == "robust"
        assert NumericsProfile.STANDARD.value == "standard"
        assert NumericsProfile.PRECISE.value == "precise"

    def test_inlet_type_values(self):
        """Test InletType enum values."""
        assert InletType.CONSTANT.value == "CONSTANT"
        assert InletType.TIMEVARYING.value == "TIMEVARYING"
        assert InletType.WOMERSLEY.value == "WOMERSLEY"
        assert InletType.PARABOLIC.value == "PARABOLIC"

    def test_outlet_type_values(self):
        """Test OutletType enum values."""
        assert OutletType.ZEROGRADIENT.value == "zeroGradient"
        assert OutletType.FIXEDVALUE.value == "fixedValue"
        assert OutletType.WINDKESSEL_2E.value == "2EWINDKESSEL"
        assert OutletType.WINDKESSEL_3E.value == "3EWINDKESSEL"

    def test_reference_radius_strategy_values(self):
        """Test ReferenceRadiusStrategy enum values."""
        assert ReferenceRadiusStrategy.INLET.value == "inlet"
        assert ReferenceRadiusStrategy.MINIMUM.value == "minimum"
        assert ReferenceRadiusStrategy.AVERAGE.value == "average"

    def test_enum_string_behavior(self):
        """Test that enums behave as strings."""
        assert str(PhysicsModel.LAMINAR) == "PhysicsModel.LAMINAR"
        # String comparison via value
        assert PhysicsModel.LAMINAR.value == "laminar"


class TestPydanticAvailability:
    """Test pydantic availability detection."""

    def test_is_pydantic_available(self):
        """Test pydantic availability function."""
        result = is_pydantic_available()
        assert isinstance(result, bool)
        assert result == PYDANTIC_AVAILABLE


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestPhysicsConfig:
    """Test PhysicsConfig model."""

    def test_default_values(self):
        """Test default physics configuration."""
        config = PhysicsConfig()

        assert config.model == PhysicsModel.LAMINAR
        assert config.simulation_type == "laminar"
        assert config.blood_density == 1060.0
        assert config.blood_viscosity == 0.004

    def test_custom_values(self):
        """Test physics configuration with custom values."""
        config = PhysicsConfig(
            model=PhysicsModel.LES,
            blood_density=1050.0,
            blood_viscosity=0.0035
        )

        assert config.model == PhysicsModel.LES
        assert config.blood_density == 1050.0
        assert config.blood_viscosity == 0.0035

    def test_validation_blood_density_positive(self):
        """Test that blood density must be positive."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PhysicsConfig(blood_density=-1.0)

    def test_validation_blood_viscosity_positive(self):
        """Test that blood viscosity must be positive."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PhysicsConfig(blood_viscosity=0.0)


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestBoundaryLayerConfig:
    """Test BoundaryLayerConfig model."""

    def test_default_values(self):
        """Test default boundary layer configuration."""
        config = BoundaryLayerConfig()

        assert config.enabled is True
        assert config.num_layers == 5
        assert config.expansion_ratio == 1.15
        assert config.final_layer_thickness == 0.4
        assert config.min_thickness == 0.1

    def test_validation_num_layers(self):
        """Test num_layers bounds validation."""
        from pydantic import ValidationError

        # Valid range
        config = BoundaryLayerConfig(num_layers=10)
        assert config.num_layers == 10

        # Invalid - negative
        with pytest.raises(ValidationError):
            BoundaryLayerConfig(num_layers=-1)

        # Invalid - too large
        with pytest.raises(ValidationError):
            BoundaryLayerConfig(num_layers=25)

    def test_validation_expansion_ratio(self):
        """Test expansion_ratio bounds validation."""
        from pydantic import ValidationError

        # Valid
        config = BoundaryLayerConfig(expansion_ratio=1.5)
        assert config.expansion_ratio == 1.5

        # Invalid - must be > 1.0
        with pytest.raises(ValidationError):
            BoundaryLayerConfig(expansion_ratio=0.9)


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestSnappySettings:
    """Test SnappySettings model."""

    def test_default_values(self):
        """Test default snappy settings."""
        config = SnappySettings()

        assert config.maxLocalCells == 10000000
        assert config.maxGlobalCells == 20000000
        assert config.span_refinement_enabled is True
        assert config.cells_across_span == 36
        assert config.parallel is True
        assert config.nProcessors == 4

    def test_custom_processor_count(self):
        """Test custom processor count."""
        config = SnappySettings(nProcessors=8)
        assert config.nProcessors == 8

    def test_validation_cells_across_span(self):
        """Test cells_across_span bounds."""
        from pydantic import ValidationError

        # Valid
        config = SnappySettings(cells_across_span=50)
        assert config.cells_across_span == 50

        # Invalid - too low
        with pytest.raises(ValidationError):
            SnappySettings(cells_across_span=5)


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestMeshConfig:
    """Test MeshConfig model."""

    def test_default_initialization(self):
        """Test that MeshConfig creates defaults."""
        config = MeshConfig()

        # Should auto-create nested configs
        assert config.boundary_layers is not None
        assert config.SNAPPY_SETTINGS is not None

    def test_custom_boundary_layers(self):
        """Test MeshConfig with custom boundary layers."""
        bl_config = BoundaryLayerConfig(num_layers=8)
        config = MeshConfig(boundary_layers=bl_config)

        assert config.boundary_layers.num_layers == 8


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestGeometryConfig:
    """Test GeometryConfig model."""

    def test_default_values(self):
        """Test default geometry configuration."""
        config = GeometryConfig()

        assert config.inlet_keywords_ordered == "inlet"
        assert config.wall_keywords_ordered == "wall"
        assert config.scale_factor == 0.001
        assert config.reference_radius_strategy == ReferenceRadiusStrategy.INLET

    def test_outlet_list(self):
        """Test outlet keywords as list."""
        config = GeometryConfig(outlet_keywords_ordered=["outlet1", "outlet2", "outlet3"])

        assert len(config.outlet_keywords_ordered) == 3

    def test_validation_scale_factor_positive(self):
        """Test that scale factor must be positive."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            GeometryConfig(scale_factor=-0.001)


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestNumericsConfig:
    """Test NumericsConfig model."""

    def test_default_values(self):
        """Test default numerics configuration."""
        config = NumericsConfig()

        assert config.profile == NumericsProfile.STANDARD
        assert config.max_co == 1.0
        assert config.max_delta_t == 0.001

    def test_custom_profile(self):
        """Test custom numerics profile."""
        config = NumericsConfig(profile=NumericsProfile.PRECISE)
        assert config.profile == NumericsProfile.PRECISE

    def test_validation_max_co(self):
        """Test max_co bounds validation."""
        from pydantic import ValidationError

        # Valid
        config = NumericsConfig(max_co=2.0)
        assert config.max_co == 2.0

        # Invalid - too high
        with pytest.raises(ValidationError):
            NumericsConfig(max_co=10.0)


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestInletConfig:
    """Test InletConfig model."""

    def test_default_values(self):
        """Test default inlet configuration."""
        config = InletConfig()

        assert config.type == InletType.CONSTANT
        assert config.profile_type == "plug"

    def test_timevarying_inlet(self):
        """Test time-varying inlet configuration."""
        config = InletConfig(
            type=InletType.TIMEVARYING,
            csv_file="inlet_flow.csv"
        )

        assert config.type == InletType.TIMEVARYING
        assert config.csv_file == "inlet_flow.csv"


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestWindkesselConfig:
    """Test WindkesselConfig model."""

    def test_default_values(self):
        """Test default Windkessel configuration."""
        config = WindkesselConfig()

        assert config.enabled is True
        assert config.estimation_method == "auto"
        assert config.murray_exponent == 2.6
        assert config.time_constant == 1.0

    def test_validation_murray_exponent(self):
        """Test Murray exponent bounds."""
        from pydantic import ValidationError

        # Valid
        config = WindkesselConfig(murray_exponent=2.7)
        assert config.murray_exponent == 2.7

        # Invalid - too low
        with pytest.raises(ValidationError):
            WindkesselConfig(murray_exponent=1.5)


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestSimulationConfig:
    """Test SimulationConfig model."""

    def test_minimal_config(self):
        """Test simulation config with minimal input."""
        config = SimulationConfig()

        # Should auto-create defaults
        assert config.geometry is not None
        assert config.physics is not None
        assert config.mesh is not None
        assert config.numerics is not None

    def test_full_config(self):
        """Test simulation config with full specification."""
        config = SimulationConfig(
            patient={"id": "PAT001", "age": 65},
            geometry=GeometryConfig(scale_factor=0.001),
            physics=PhysicsConfig(model=PhysicsModel.LAMINAR),
            run_settings={"solution_type": "parallel", "subdomains": 8}
        )

        assert config.patient["id"] == "PAT001"
        assert config.geometry.scale_factor == 0.001
        assert config.run_settings["subdomains"] == 8

    def test_extra_fields_allowed(self):
        """Test that extra fields are allowed."""
        config = SimulationConfig(
            custom_field="custom_value"
        )

        # Extra fields should be allowed
        assert hasattr(config, 'custom_field') or 'custom_field' in config.__dict__


class TestValidateConfig:
    """Test the validate_config helper function."""

    def test_validate_empty_config(self):
        """Test validation of empty config."""
        config_dict: Dict[str, Any] = {}
        result = validate_config(config_dict)

        assert result is not None

    def test_validate_minimal_config(self):
        """Test validation of minimal config."""
        config_dict = {
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1']
            }
        }

        result = validate_config(config_dict)
        assert result is not None

    def test_validate_complete_config(self):
        """Test validation of complete config."""
        config_dict = {
            'patient': {'id': 'PAT001'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1', 'outlet2'],
                'wall_keywords_ordered': 'wall_aorta',
                'scale_factor': 0.001
            },
            'physics': {
                'simulation_type': 'laminar',
                'blood_density': 1060.0,
                'blood_viscosity': 0.004
            },
            'mesh': {
                'SNAPPY_SETTINGS': {
                    'parallel': True,
                    'nProcessors': 4
                }
            },
            'run_settings': {
                'solution_type': 'parallel',
                'subdomains': 4
            }
        }

        result = validate_config(config_dict)
        assert result is not None


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestValidationErrors:
    """Test validation error handling."""

    def test_invalid_blood_density(self):
        """Test that invalid blood density raises error."""
        from pydantic import ValidationError

        config_dict = {
            'physics': {
                'blood_density': -1000.0  # Invalid
            }
        }

        with pytest.raises(ValidationError):
            validate_config(config_dict)

    def test_invalid_scale_factor(self):
        """Test that invalid scale factor raises error."""
        from pydantic import ValidationError

        config_dict = {
            'geometry': {
                'scale_factor': 0.0  # Invalid - must be positive
            }
        }

        with pytest.raises(ValidationError):
            validate_config(config_dict)


class TestFallbackBehavior:
    """Test fallback behavior when pydantic not available."""

    def test_dataclass_fallback_geometry(self):
        """Test GeometryConfig dataclass fallback."""
        # Force using the dataclass version directly
        from dataclasses import is_dataclass

        if not PYDANTIC_AVAILABLE:
            from config.schema import GeometryConfig
            assert is_dataclass(GeometryConfig)

    def test_validate_config_fallback(self):
        """Test validate_config with fallback path."""
        config_dict = {
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'scale_factor': 0.001
            }
        }

        result = validate_config(config_dict)
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
