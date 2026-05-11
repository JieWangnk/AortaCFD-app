"""Physics model advisor for AortaCFD.

Recommends laminar vs RANS vs LES based on flow conditions and mesh quality.

For aortic CFD, laminar is the correct default for most cases because:
- Aortic Reynolds number is typically 500-4000 (transitional, not fully turbulent)
- k-omega SST generates non-zero eddy viscosity even in predominantly laminar flow
- The k equation production term P_k = nut * |S|^2 amplifies mesh-induced velocity
  gradient errors. On snappyHexMesh with polyhedral transition cells, this creates
  instabilities at refinement boundaries and bifurcations.
- Published aortic CFD increasingly uses laminar (or DNS) up to Re ~4000.

References:
    - Fehn et al. (2019) Numerical analysis of the Navier-Stokes equations in the
      context of hemodynamic simulations. J Comp Phys.
    - Bergersen et al. (2019) The FDA benchmark body: A computational round robin
      study. Int J Numer Meth Biomed Eng.
    - Madhavan & Kemmerling (2018) The effect of inlet and outlet boundary conditions
      in image-based CFD modeling of aortic flow. BioMed Eng Online.
"""

import logging
import math
from typing import Dict, List, Optional

from .constants import (
    AORTIC_DIAMETER_DEFAULT,
    L_TO_M3,
    MIN_TO_S,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Reynolds number thresholds for model selection
# =============================================================================

RE_LAMINAR_SAFE = 4000
"""Below this, laminar is scientifically defensible for aortic flows."""

RE_TRANSITIONAL_UPPER = 5000
"""Above this, RANS may be justified if mesh quality supports it."""

# =============================================================================
# Mesh quality thresholds for turbulence models
# =============================================================================

# RANS requires reasonable mesh quality to avoid k production blowup
RANS_MAX_NON_ORTHO = 65.0  # degrees
RANS_MAX_SKEWNESS = 4.0
RANS_MAX_ASPECT_RATIO = 500.0

# LES has stricter requirements
LES_MAX_NON_ORTHO = 55.0
LES_MAX_SKEWNESS = 2.0
LES_MAX_ASPECT_RATIO = 100.0

# Surface refinement level jump creates volume ratio issues
# [1,2] = 8:1 volume jump; [2,3] = 8:1; [1,3] = 64:1
MAX_SAFE_REFINEMENT_JUMP = 1  # Max difference between min and max level


class PhysicsAdvice:
    """Container for physics model recommendation."""

    def __init__(self):
        self.recommended_model: str = "laminar"
        self.reasoning: List[str] = []
        self.warnings: List[str] = []
        self.estimated_re: Optional[float] = None
        self.mesh_compatible: bool = True

    def __repr__(self):
        return (
            f"PhysicsAdvice(model={self.recommended_model}, " f"Re={self.estimated_re}, warnings={len(self.warnings)})"
        )


def estimate_reynolds_number(
    config: dict,
    inlet_radius_m: Optional[float] = None,
) -> Optional[float]:
    """
    Estimate peak Reynolds number from config.

    Uses cardiac output (or velocity) and inlet geometry to compute:
        Re = U * D / nu

    Args:
        config: Full configuration dictionary
        inlet_radius_m: Inlet radius in metres (if known from geometry).
            Falls back to AORTIC_DIAMETER_DEFAULT/2 if not provided.

    Returns:
        Estimated Reynolds number, or None if insufficient data.
    """
    physics = config.get("physics", {})
    inlet_settings = config.get("boundary_conditions", {}).get("inlet") or config.get("inlet", {})

    # Get kinematic viscosity
    transport = physics.get("transport_properties", {})
    if "nu" in transport:
        nu = transport["nu"]
    elif "nu" in physics:
        nu = physics["nu"]
    else:
        mu = physics.get("default_viscosity", 0.004)
        rho = physics.get("default_density", 1060)
        nu = mu / rho

    # Determine characteristic velocity
    velocity = None

    # Try cardiac output first
    cardiac_output = inlet_settings.get("cardiac_output") or inlet_settings.get("flowrate")
    if cardiac_output is not None:
        # cardiac_output is in L/min
        Q = cardiac_output * L_TO_M3 / MIN_TO_S  # m^3/s

        # Get inlet area
        if inlet_radius_m is not None:
            area = math.pi * inlet_radius_m**2
        else:
            area = math.pi * (AORTIC_DIAMETER_DEFAULT / 2) ** 2

        velocity = Q / area
    elif "velocity" in inlet_settings:
        velocity = inlet_settings["velocity"]
    elif "mean_velocity" in inlet_settings:
        velocity = inlet_settings["mean_velocity"]

    if velocity is None:
        return None

    # For pulsatile flow, peak velocity is roughly 2x mean
    inlet_type = inlet_settings.get("type", "CONSTANT").upper()
    if inlet_type in ["TIMEVARYING", "WOMERSLEY", "MRI"]:
        velocity_peak = velocity * 2.0
    else:
        velocity_peak = velocity

    # Characteristic diameter
    if inlet_radius_m is not None:
        D = 2 * inlet_radius_m
    else:
        D = AORTIC_DIAMETER_DEFAULT

    Re = velocity_peak * D / nu
    return Re


def check_mesh_turbulence_compatibility(
    config: dict,
    physics_model: str,
    mesh_metrics: Optional[Dict[str, float]] = None,
) -> List[str]:
    """
    Check if mesh settings are compatible with the requested physics model.

    Args:
        config: Full configuration dictionary
        physics_model: 'laminar', 'rans', or 'les'
        mesh_metrics: Parsed checkMesh metrics (if available post-meshing).
            Keys: max_non_orthogonality, max_skewness, max_aspect_ratio

    Returns:
        List of warning strings. Empty list means mesh is compatible.
    """
    if physics_model == "laminar":
        return []

    warnings = []
    mesh_config = config.get("mesh", {})
    snappy = mesh_config.get("SNAPPY_SETTINGS", {})

    # Check surface refinement level jump
    ref_levels = snappy.get("surfaceRefinementLevels", [])
    if isinstance(ref_levels, list) and len(ref_levels) >= 2:
        level_jump = abs(ref_levels[-1] - ref_levels[0])
        if level_jump > MAX_SAFE_REFINEMENT_JUMP:
            volume_ratio = 8**level_jump
            warnings.append(
                f"surfaceRefinementLevels {ref_levels} creates {volume_ratio}:1 volume "
                f"jumps at refinement boundaries. "
                f"{'k-omega SST' if physics_model == 'rans' else 'LES'} may be unstable "
                f"at these transitions due to velocity gradient discontinuities. "
                f"Consider [{ref_levels[-1]},{ref_levels[-1]}] (uniform) or switch to laminar."
            )

    # Check boundary layers for RANS/LES
    bl_config = mesh_config.get("boundary_layers", {})
    if physics_model == "les":
        # LES needs boundary layers for near-wall resolution
        if not bl_config.get("enabled", True):
            warnings.append(
                "LES selected but boundary layers disabled. "
                "Wall-resolved LES requires y+ < 1 which needs boundary layer cells."
            )
        elif bl_config.get("num_layers", 5) < 3:
            warnings.append(
                f"LES with only {bl_config.get('num_layers', 5)} boundary layers. "
                f"Wall-resolved LES typically needs 5+ layers with y+ < 1."
            )

    # Check post-meshing metrics if available
    if mesh_metrics:
        if physics_model == "rans":
            _check_metrics_rans(mesh_metrics, warnings)
        elif physics_model == "les":
            _check_metrics_les(mesh_metrics, warnings)

    return warnings


def _check_metrics_rans(metrics: Dict[str, float], warnings: List[str]):
    """Check mesh metrics against RANS thresholds."""
    ortho = metrics.get("max_non_orthogonality")
    if ortho is not None and ortho > RANS_MAX_NON_ORTHO:
        warnings.append(
            f"Max non-orthogonality {ortho:.1f} deg exceeds RANS threshold "
            f"({RANS_MAX_NON_ORTHO} deg). k-omega SST turbulence production term "
            f"P_k = nut*|S|^2 amplifies velocity gradient errors on non-orthogonal cells, "
            f"leading to k blowup."
        )

    skew = metrics.get("max_skewness")
    if skew is not None and skew > RANS_MAX_SKEWNESS:
        warnings.append(
            f"Max skewness {skew:.2f} exceeds RANS threshold ({RANS_MAX_SKEWNESS}). "
            f"Skewed cells create artificial velocity gradients that feed the k equation."
        )

    aspect = metrics.get("max_aspect_ratio")
    if aspect is not None and aspect > RANS_MAX_ASPECT_RATIO:
        warnings.append(
            f"Max aspect ratio {aspect:.0f} exceeds RANS threshold ({RANS_MAX_ASPECT_RATIO}). "
            f"Highly elongated cells amplify directional gradient errors in the k equation."
        )


def _check_metrics_les(metrics: Dict[str, float], warnings: List[str]):
    """Check mesh metrics against LES thresholds."""
    ortho = metrics.get("max_non_orthogonality")
    if ortho is not None and ortho > LES_MAX_NON_ORTHO:
        warnings.append(
            f"Max non-orthogonality {ortho:.1f} deg exceeds LES threshold "
            f"({LES_MAX_NON_ORTHO} deg). LES subgrid models (e.g. WALE) compute "
            f"eddy viscosity from velocity gradients — non-orthogonal cells corrupt "
            f"this estimate and cause nut blowup."
        )

    skew = metrics.get("max_skewness")
    if skew is not None and skew > LES_MAX_SKEWNESS:
        warnings.append(
            f"Max skewness {skew:.2f} exceeds LES threshold ({LES_MAX_SKEWNESS}). "
            f"LES requires good cell quality for accurate gradient reconstruction."
        )

    aspect = metrics.get("max_aspect_ratio")
    if aspect is not None and aspect > LES_MAX_ASPECT_RATIO:
        warnings.append(
            f"Max aspect ratio {aspect:.0f} exceeds LES threshold ({LES_MAX_ASPECT_RATIO}). "
            f"LES needs isotropic cells (aspect ratio < 100) for valid subgrid modelling."
        )


def recommend_physics_model(
    config: dict,
    inlet_radius_m: Optional[float] = None,
    mesh_metrics: Optional[Dict[str, float]] = None,
) -> PhysicsAdvice:
    """
    Recommend physics model based on flow conditions and mesh quality.

    This is advisory only — the user's explicit choice always takes precedence.
    The function is called during config build and after meshing to provide
    guidance and warnings.

    Args:
        config: Full configuration dictionary
        inlet_radius_m: Inlet radius in metres (if known from geometry)
        mesh_metrics: Parsed checkMesh metrics (if available post-meshing)

    Returns:
        PhysicsAdvice with recommended model, reasoning, and warnings
    """
    advice = PhysicsAdvice()

    # Estimate Reynolds number
    Re = estimate_reynolds_number(config, inlet_radius_m)
    advice.estimated_re = Re

    # Get user's selected model
    physics = config.get("physics", {})
    selected_model = physics.get("simulation_type", "laminar").lower()
    if selected_model not in ("laminar", "rans", "les"):
        # Normalize OpenFOAM naming
        if selected_model.upper() == "RAS":
            selected_model = "rans"

    # Reynolds number based recommendation
    if Re is not None:
        if Re < RE_LAMINAR_SAFE:
            advice.recommended_model = "laminar"
            advice.reasoning.append(
                f"Estimated Re_peak = {Re:.0f} (< {RE_LAMINAR_SAFE}). "
                f"Laminar is scientifically defensible for aortic flows in this regime."
            )

            if selected_model in ("rans", "les"):
                advice.warnings.append(
                    f"RANS/LES selected but estimated Re_peak = {Re:.0f}. "
                    f"At Re < {RE_LAMINAR_SAFE}, aortic flow is transitional — "
                    f"k-omega SST may over-predict eddy viscosity in predominantly laminar flow, which is inappropriate "
                    f"for most of the cardiac cycle. Consider switching to laminar."
                )
        elif Re < RE_TRANSITIONAL_UPPER:
            advice.recommended_model = "laminar"
            advice.reasoning.append(
                f"Estimated Re_peak = {Re:.0f} ({RE_LAMINAR_SAFE}-{RE_TRANSITIONAL_UPPER}). "
                f"This is the upper transitional regime. Laminar is still recommended "
                f"unless you have specific reasons for turbulence modelling."
            )
        else:
            advice.recommended_model = "rans"
            advice.reasoning.append(
                f"Estimated Re_peak = {Re:.0f} (> {RE_TRANSITIONAL_UPPER}). "
                f"Flow may be turbulent — RANS could be justified if mesh quality allows."
            )
    else:
        advice.reasoning.append(
            "Could not estimate Reynolds number (no velocity/cardiac_output in config). "
            "Laminar is the safe default for aortic flows."
        )

    # Check mesh compatibility with selected model
    mesh_warnings = check_mesh_turbulence_compatibility(config, selected_model, mesh_metrics)
    advice.warnings.extend(mesh_warnings)
    if mesh_warnings:
        advice.mesh_compatible = False

    return advice


def log_physics_advice(advice: PhysicsAdvice, selected_model: str):
    """
    Log physics model advice to the logger.

    Only logs if there are actionable warnings (i.e., the user selected
    a model that the advisor disagrees with or mesh is incompatible).

    Args:
        advice: PhysicsAdvice from recommend_physics_model
        selected_model: User's selected physics model
    """
    if not advice.warnings:
        return

    logger.warning("=" * 65)
    logger.warning("PHYSICS MODEL ADVISORY")
    logger.warning("=" * 65)

    if advice.estimated_re is not None:
        logger.warning(f"  Estimated peak Reynolds number: {advice.estimated_re:.0f}")

    logger.warning(f"  Selected model: {selected_model}")
    logger.warning(f"  Recommended model: {advice.recommended_model}")

    for reason in advice.reasoning:
        logger.warning(f"  {reason}")

    for warning in advice.warnings:
        logger.warning(f"  WARNING: {warning}")

    logger.warning("=" * 65)
