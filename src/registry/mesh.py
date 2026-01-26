# src/registry/mesh.py
"""
Centralized mesh quality thresholds and settings.

This module is the SINGLE SOURCE OF TRUTH for mesh quality criteria,
boundary layer defaults, and mesh-adaptive scheme adjustments.

Usage:
    from src.registry.mesh import MESH_QUALITY_TIERS, get_mesh_quality_tier

    tier = get_mesh_quality_tier(max_skewness=0.7, max_non_ortho=50)
    # Returns: 'fair'
"""

from typing import Dict, Any, Optional, Tuple
from copy import deepcopy


# =============================================================================
# MESH QUALITY TIERS
# =============================================================================

MESH_QUALITY_TIERS = {
    'excellent': {
        'maxSkewness': 0.5,
        'maxNonOrtho': 40,
        'maxAspectRatio': 20,
        'minVolume': 1e-18,
        'minArea': 1e-14,
        'minDeterminant': 0.1,
        'description': 'Publication-quality mesh, suitable for precise profile',
    },

    'good': {
        'maxSkewness': 0.7,
        'maxNonOrtho': 60,
        'maxAspectRatio': 50,
        'minVolume': 1e-18,
        'minArea': 1e-14,
        'minDeterminant': 0.05,
        'description': 'Production-quality mesh, suitable for standard profile',
    },

    'fair': {
        'maxSkewness': 0.85,
        'maxNonOrtho': 70,
        'maxAspectRatio': 100,
        'minVolume': 1e-20,
        'minArea': 1e-16,
        'minDeterminant': 0.01,
        'description': 'Acceptable mesh, may need robust profile',
    },

    'poor': {
        'maxSkewness': 0.95,
        'maxNonOrtho': 80,
        'maxAspectRatio': 200,
        'minVolume': 1e-22,
        'minArea': 1e-18,
        'minDeterminant': 0.001,
        'description': 'Poor mesh, requires robust profile, fix if possible',
    },
}


# =============================================================================
# RECOMMENDED PROFILE PER MESH TIER
# =============================================================================

TIER_TO_PROFILE = {
    'excellent': 'precise',
    'good': 'standard',
    'fair': 'robust',
    'poor': 'robust',
}


# =============================================================================
# BOUNDARY LAYER DEFAULTS
# =============================================================================

BOUNDARY_LAYER_DEFAULTS = {
    # General defaults
    'nLayers': 5,
    'expansionRatio': 1.2,
    'finalLayerThickness': 0.3,
    'minThickness': 0.001,

    # For hemodynamic simulations (wall shear stress accuracy)
    'hemodynamic': {
        'nLayers': 10,
        'expansionRatio': 1.15,
        'finalLayerThickness': 0.2,
        'minThickness': 0.0001,
        'target_yplus': 1.0,
    },

    # For coarse/fast simulations
    'coarse': {
        'nLayers': 3,
        'expansionRatio': 1.3,
        'finalLayerThickness': 0.4,
        'minThickness': 0.01,
        'target_yplus': 30.0,
    },

    # Quality controls
    'featureAngle': 130,
    'slipFeatureAngle': 30,
    'nGrow': 0,
    'nBufferCellsNoExtrude': 0,
    'nLayerIter': 50,
    'nRelaxedIter': 20,
}


# =============================================================================
# SNAPPYHEXMESH QUALITY DEFAULTS
# =============================================================================

SNAPPY_QUALITY_DEFAULTS = {
    # Mesh quality controls
    'maxNonOrtho': 65,
    'maxBoundarySkewness': 20,
    'maxInternalSkewness': 4,
    'maxConcave': 80,
    'minVol': 1e-18,
    'minTetQuality': 1e-15,
    'minArea': 1e-14,
    'minTwist': 0.02,
    'minDeterminant': 0.001,
    'minFaceWeight': 0.05,
    'minVolRatio': 0.01,
    'minTriangleTwist': -1,

    # Error/warning thresholds
    'errorReduction': 0.75,
    'nSmoothScale': 4,
}


# =============================================================================
# MESH-ADAPTIVE SCHEME ADJUSTMENTS
# =============================================================================

MESH_ADAPTIVE_ADJUSTMENTS = {
    # For poor mesh quality, use more stable schemes
    'poor': {
        'schemes': {
            'ddt': 'Euler',
            'div_phi_U': 'Gauss upwind',
            'grad_U': 'cellLimited Gauss linear 1.0',
        },
        'relaxation': {
            'p': 0.15,
            'U': 0.4,
        },
        'pimple': {
            'nNonOrthogonalCorrectors': 3,
        },
    },

    'fair': {
        'schemes': {
            'grad_U': 'cellLimited Gauss linear 0.8',
        },
        'relaxation': {
            'p': 0.2,
            'U': 0.5,
        },
        'pimple': {
            'nNonOrthogonalCorrectors': 2,
        },
    },

    'good': {
        # No adjustments needed
    },

    'excellent': {
        # Can use more aggressive settings
        'relaxation': {
            'p': 0.4,
            'U': 0.8,
        },
        'pimple': {
            'nNonOrthogonalCorrectors': 1,
        },
    },
}


# =============================================================================
# ACCESS FUNCTIONS
# =============================================================================

def get_mesh_quality_tier(
    max_skewness: float,
    max_non_ortho: float,
    max_aspect_ratio: Optional[float] = None,
) -> str:
    """
    Determine mesh quality tier based on quality metrics.

    Args:
        max_skewness: Maximum cell skewness (0-1)
        max_non_ortho: Maximum non-orthogonality angle (degrees)
        max_aspect_ratio: Maximum aspect ratio (optional)

    Returns:
        Tier name: 'excellent', 'good', 'fair', or 'poor'
    """
    # Check each tier from best to worst
    for tier in ['excellent', 'good', 'fair', 'poor']:
        thresholds = MESH_QUALITY_TIERS[tier]

        # Must pass all criteria to be in this tier
        passes_skewness = max_skewness <= thresholds['maxSkewness']
        passes_non_ortho = max_non_ortho <= thresholds['maxNonOrtho']
        passes_aspect = (
            max_aspect_ratio is None or
            max_aspect_ratio <= thresholds['maxAspectRatio']
        )

        if passes_skewness and passes_non_ortho and passes_aspect:
            return tier

    # If nothing matches, it's poor
    return 'poor'


def get_recommended_profile(
    max_skewness: float,
    max_non_ortho: float,
) -> str:
    """
    Get recommended numerical profile for mesh quality.

    Args:
        max_skewness: Maximum cell skewness
        max_non_ortho: Maximum non-orthogonality angle

    Returns:
        Recommended profile name: 'robust', 'standard', or 'precise'
    """
    tier = get_mesh_quality_tier(max_skewness, max_non_ortho)
    return TIER_TO_PROFILE[tier]


def get_boundary_layer_settings(
    preset: str = 'hemodynamic',
    target_yplus: Optional[float] = None,
    n_layers: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Get boundary layer settings with optional overrides.

    Args:
        preset: Preset name ('hemodynamic', 'coarse', or 'default')
        target_yplus: Override target y+
        n_layers: Override number of layers

    Returns:
        Dictionary of boundary layer settings
    """
    if preset in BOUNDARY_LAYER_DEFAULTS:
        settings = deepcopy(BOUNDARY_LAYER_DEFAULTS[preset])
    else:
        settings = deepcopy(BOUNDARY_LAYER_DEFAULTS)
        # Remove nested presets
        settings.pop('hemodynamic', None)
        settings.pop('coarse', None)

    # Apply overrides
    if target_yplus is not None:
        settings['target_yplus'] = target_yplus
    if n_layers is not None:
        settings['nLayers'] = n_layers

    return settings


def get_mesh_adaptive_adjustments(tier: str) -> Dict[str, Any]:
    """
    Get scheme/solver adjustments for mesh quality tier.

    Args:
        tier: Mesh quality tier

    Returns:
        Dictionary of adjustments to apply
    """
    return deepcopy(MESH_ADAPTIVE_ADJUSTMENTS.get(tier, {}))


def get_snappy_quality_settings(
    quality_level: str = 'standard',
) -> Dict[str, Any]:
    """
    Get snappyHexMesh quality control settings.

    Args:
        quality_level: 'strict', 'standard', or 'relaxed'

    Returns:
        Dictionary of meshQualityControls settings
    """
    settings = deepcopy(SNAPPY_QUALITY_DEFAULTS)

    if quality_level == 'strict':
        settings['maxNonOrtho'] = 55
        settings['maxBoundarySkewness'] = 10
        settings['maxInternalSkewness'] = 2
        settings['minDeterminant'] = 0.01

    elif quality_level == 'relaxed':
        settings['maxNonOrtho'] = 75
        settings['maxBoundarySkewness'] = 40
        settings['maxInternalSkewness'] = 6
        settings['minDeterminant'] = 0.0001

    return settings


def estimate_first_layer_height(
    target_yplus: float,
    velocity: float,
    length: float,
    nu: float,
) -> float:
    """
    Estimate first boundary layer cell height for target y+.

    Uses flat plate approximation: Cf = 0.058 * Re^(-0.2)
    tau_w = 0.5 * Cf * rho * U^2
    u_tau = sqrt(tau_w / rho)
    y = y+ * nu / u_tau

    Args:
        target_yplus: Target y+ value (typically 1 for resolved BL)
        velocity: Reference velocity (m/s)
        length: Reference length (m)
        nu: Kinematic viscosity (m²/s)

    Returns:
        First layer height in meters
    """
    import math

    # Reynolds number
    Re = velocity * length / nu

    # Skin friction coefficient (flat plate, turbulent)
    if Re > 0:
        Cf = 0.058 * (Re ** -0.2)
    else:
        Cf = 0.01  # Fallback

    # Wall shear stress (normalized)
    # tau_w / rho = 0.5 * Cf * U^2
    tau_w_over_rho = 0.5 * Cf * velocity ** 2

    # Friction velocity
    u_tau = math.sqrt(tau_w_over_rho)

    # First layer height
    if u_tau > 0:
        y = target_yplus * nu / u_tau
    else:
        y = 1e-5  # Fallback

    return y
