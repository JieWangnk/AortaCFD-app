# config/schema.py
"""
Pydantic models for configuration validation.

This module provides type-safe configuration schemas that validate
user input before simulation setup, preventing runtime errors from
invalid or missing configuration values.

Usage:
    from config.schema import SimulationConfig
    config = SimulationConfig(**loaded_json)  # Raises ValidationError if invalid
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

try:
    from pydantic import BaseModel, Field, field_validator, model_validator
    PYDANTIC_AVAILABLE = True
except ImportError:
    # Fallback if pydantic not installed - use dataclasses
    PYDANTIC_AVAILABLE = False
    BaseModel = object
    Field = lambda *args, **kwargs: None
    field_validator = lambda *args, **kwargs: lambda f: f
    model_validator = lambda *args, **kwargs: lambda f: f


# =============================================================================
# ENUMERATIONS
# =============================================================================

class PhysicsModel(str, Enum):
    """Supported physics models."""
    LAMINAR = "laminar"
    RANS = "rans"
    LES = "les"


class NumericsProfile(str, Enum):
    """Numerical accuracy profiles (3-profile system)."""
    ROBUST = "robust"      # 1st order, maximum stability
    STANDARD = "standard"  # 2nd order TVD bounded (default)
    PRECISE = "precise"    # 2nd order LUST/CrankNicolson, minimal diffusion


class InletType(str, Enum):
    """Inlet boundary condition types."""
    CONSTANT = "CONSTANT"
    TIMEVARYING = "TIMEVARYING"
    WOMERSLEY = "WOMERSLEY"
    PARABOLIC = "PARABOLIC"


class OutletType(str, Enum):
    """Outlet boundary condition types."""
    ZEROGRADIENT = "zeroGradient"
    FIXEDVALUE = "fixedValue"
    WINDKESSEL_2E = "2EWINDKESSEL"
    WINDKESSEL_3E = "3EWINDKESSEL"


class ReferenceRadiusStrategy(str, Enum):
    """Strategy for determining reference radius for mesh sizing."""
    INLET = "inlet"
    MINIMUM = "minimum"
    AVERAGE = "average"


# =============================================================================
# CONFIGURATION MODELS (Pydantic-based if available)
# =============================================================================

if PYDANTIC_AVAILABLE:

    class PhysicsConfig(BaseModel):
        """Physics configuration with validation."""

        model: PhysicsModel = PhysicsModel.LAMINAR
        simulation_type: str = "laminar"
        blood_density: float = Field(default=1060.0, gt=0, description="Blood density in kg/m³")
        blood_viscosity: float = Field(default=0.004, gt=0, description="Dynamic viscosity in Pa·s")

        @model_validator(mode='after')
        def sync_simulation_type(self) -> 'PhysicsConfig':
            """Ensure simulation_type matches model."""
            if self.simulation_type.lower() != self.model.value:
                self.simulation_type = self.model.value
            return self

        class Config:
            use_enum_values = True


    class BoundaryLayerConfig(BaseModel):
        """Boundary layer mesh configuration."""

        enabled: bool = True
        num_layers: int = Field(default=5, ge=0, le=20)
        expansion_ratio: float = Field(default=1.15, gt=1.0, le=2.0)
        final_layer_thickness: float = Field(default=0.4, gt=0, le=1.0)
        min_thickness: float = Field(default=0.1, gt=0, le=1.0)


    class SnappySettings(BaseModel):
        """snappyHexMesh configuration with defaults."""

        # Castellated mesh
        maxLocalCells: int = Field(default=10000000, gt=0)
        maxGlobalCells: int = Field(default=20000000, gt=0)

        # Span-based refinement
        span_refinement_enabled: bool = True
        cells_across_span: int = Field(default=36, ge=10, le=100)
        span_refinement_level: int = Field(default=2, ge=1, le=4)

        # Surface refinement
        surfaceRefinementLevels: List[int] = Field(default=[2, 2])
        featureLevel: int = Field(default=2, ge=0, le=5)

        # Feature detection
        includedAngle: int = Field(default=170, ge=0, le=180)
        resolveFeatureAngle: int = Field(default=30, ge=0, le=180)

        # Parallelization
        parallel: bool = True
        nProcessors: int = Field(default=4, ge=1)


    class MeshConfig(BaseModel):
        """Mesh generation configuration."""

        boundary_layers: Optional[BoundaryLayerConfig] = None
        SNAPPY_SETTINGS: Optional[SnappySettings] = None

        @model_validator(mode='after')
        def set_defaults(self) -> 'MeshConfig':
            if self.boundary_layers is None:
                self.boundary_layers = BoundaryLayerConfig()
            if self.SNAPPY_SETTINGS is None:
                self.SNAPPY_SETTINGS = SnappySettings()
            return self


    class GeometryConfig(BaseModel):
        """Geometry configuration."""

        inlet_keywords_ordered: Union[str, List[str]] = "inlet"
        outlet_keywords_ordered: Union[str, List[str]] = Field(default_factory=lambda: ["outlet"])
        wall_keywords_ordered: Union[str, List[str]] = "wall"
        scale_factor: float = Field(default=0.001, gt=0, description="STL scale: 0.001 for mm→m")
        reference_radius_strategy: ReferenceRadiusStrategy = ReferenceRadiusStrategy.INLET


    class NumericsConfig(BaseModel):
        """Numerical schemes configuration."""

        profile: NumericsProfile = NumericsProfile.STANDARD
        max_co: float = Field(default=1.0, gt=0, le=5.0)
        max_delta_t: float = Field(default=0.001, gt=0)

        class Config:
            use_enum_values = True


    class InletConfig(BaseModel):
        """Inlet boundary condition configuration."""

        type: InletType = InletType.CONSTANT
        flow_rate: Optional[float] = None
        velocity: Optional[float] = None
        csv_file: Optional[str] = None
        profile_type: str = "plug"


    class OutletConfig(BaseModel):
        """Outlet boundary condition configuration."""

        type: OutletType = OutletType.WINDKESSEL_3E

        class Config:
            use_enum_values = True


    class BoundaryConditionsConfig(BaseModel):
        """Boundary conditions configuration."""

        inlet: Optional[InletConfig] = None
        outlets: Optional[OutletConfig] = None


    class WindkesselConfig(BaseModel):
        """Windkessel parameter configuration."""

        enabled: bool = True
        estimation_method: str = "auto"
        blood_pressure: Optional[Dict[str, float]] = None
        murray_exponent: float = Field(default=2.6, ge=2.0, le=3.0)
        time_constant: float = Field(default=1.0, gt=0)


    class SimulationConfig(BaseModel):
        """
        Complete simulation configuration with validation.

        This is the top-level configuration schema that validates all
        user-provided configuration values before simulation setup.
        """

        # Patient metadata
        patient: Optional[Dict[str, Any]] = None

        # Core configuration sections
        geometry: Optional[GeometryConfig] = None
        physics: Optional[PhysicsConfig] = None
        mesh: Optional[MeshConfig] = None
        numerics: Optional[NumericsConfig] = None
        boundary_conditions: Optional[BoundaryConditionsConfig] = None
        windkessel: Optional[WindkesselConfig] = None

        # Run settings
        run_settings: Optional[Dict[str, Any]] = None

        @model_validator(mode='after')
        def set_defaults(self) -> 'SimulationConfig':
            """Set default values for missing sections."""
            if self.geometry is None:
                self.geometry = GeometryConfig()
            if self.physics is None:
                self.physics = PhysicsConfig()
            if self.mesh is None:
                self.mesh = MeshConfig()
            if self.numerics is None:
                self.numerics = NumericsConfig()
            return self

        class Config:
            extra = "allow"  # Allow additional fields for flexibility

else:
    # Fallback dataclass implementations when pydantic not available

    @dataclass
    class PhysicsConfig:
        model: str = "laminar"
        simulation_type: str = "laminar"
        blood_density: float = 1060.0
        blood_viscosity: float = 0.004

    @dataclass
    class MeshConfig:
        boundary_layers: Optional[Dict] = None
        SNAPPY_SETTINGS: Optional[Dict] = None

    @dataclass
    class GeometryConfig:
        inlet_keywords_ordered: Union[str, List[str]] = "inlet"
        outlet_keywords_ordered: Union[str, List[str]] = field(default_factory=lambda: ["outlet"])
        wall_keywords_ordered: Union[str, List[str]] = "wall"
        scale_factor: float = 0.001
        reference_radius_strategy: str = "inlet"

    @dataclass
    class SimulationConfig:
        patient: Optional[Dict] = None
        geometry: Optional[GeometryConfig] = None
        physics: Optional[PhysicsConfig] = None
        mesh: Optional[MeshConfig] = None
        numerics: Optional[Dict] = None
        boundary_conditions: Optional[Dict] = None
        windkessel: Optional[Dict] = None
        run_settings: Optional[Dict] = None


# =============================================================================
# VALIDATION HELPERS
# =============================================================================

def validate_config(config_dict: Dict[str, Any]) -> SimulationConfig:
    """
    Validate a configuration dictionary against the schema.

    Args:
        config_dict: Raw configuration dictionary loaded from JSON

    Returns:
        Validated SimulationConfig instance

    Raises:
        ValidationError: If configuration is invalid (pydantic)
        ValueError: If configuration is invalid (fallback)
    """
    if PYDANTIC_AVAILABLE:
        return SimulationConfig(**config_dict)
    else:
        # Basic validation without pydantic
        return SimulationConfig(
            patient=config_dict.get('patient'),
            geometry=GeometryConfig(**config_dict.get('geometry', {})) if config_dict.get('geometry') else None,
            physics=PhysicsConfig(**config_dict.get('physics', {})) if config_dict.get('physics') else None,
            mesh=MeshConfig(**config_dict.get('mesh', {})) if config_dict.get('mesh') else None,
            numerics=config_dict.get('numerics'),
            boundary_conditions=config_dict.get('boundary_conditions'),
            windkessel=config_dict.get('windkessel'),
            run_settings=config_dict.get('run_settings'),
        )


def is_pydantic_available() -> bool:
    """Check if pydantic validation is available."""
    return PYDANTIC_AVAILABLE
