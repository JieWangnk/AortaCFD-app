# src/registry/__init__.py
"""
Centralized registry for simulation parameters.

This module provides single-source-of-truth definitions for:
- Numerical schemes and solver settings (by profile)
- Physical constants (blood properties, etc.)
- Mesh quality thresholds

Usage:
    from src.registry import get_numerics, BLOOD_PROPERTIES, MESH_QUALITY_TIERS

    # Get numerical settings for a profile
    settings = get_numerics('standard')

    # Access physical constants
    nu = BLOOD_PROPERTIES['kinematic_viscosity']

    # Check mesh quality thresholds
    max_skewness = MESH_QUALITY_TIERS['good']['maxSkewness']
"""

from .numerics import (
    NUMERICS_PRESETS,
    get_numerics,
    get_schemes,
    get_solver_settings,
    get_relaxation_factors,
    get_pimple_settings,
    list_profiles,
)

from .physics import (
    BLOOD_PROPERTIES,
    PHYSICAL_CONSTANTS,
    get_blood_properties,
    calculate_reynolds,
    calculate_womersley,
)

from .mesh import (
    MESH_QUALITY_TIERS,
    BOUNDARY_LAYER_DEFAULTS,
    get_mesh_quality_tier,
    get_boundary_layer_settings,
)

__all__ = [
    # Numerics
    'NUMERICS_PRESETS',
    'get_numerics',
    'get_schemes',
    'get_solver_settings',
    'get_relaxation_factors',
    'get_pimple_settings',
    'list_profiles',
    # Physics
    'BLOOD_PROPERTIES',
    'PHYSICAL_CONSTANTS',
    'get_blood_properties',
    'calculate_reynolds',
    'calculate_womersley',
    # Mesh
    'MESH_QUALITY_TIERS',
    'BOUNDARY_LAYER_DEFAULTS',
    'get_mesh_quality_tier',
    'get_boundary_layer_settings',
]
