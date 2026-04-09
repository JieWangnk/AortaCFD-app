"""
Mesh resolution constants for AortaCFD.

Resolution Philosophy (v2.0 - OpenFOAM 12+):
===========================================

PRIMARY METHOD: cells_across_span (RECOMMENDED)
    Uses OpenFOAM 12's insideSpan mode with closeness data from wall_aorta.stl
    to guarantee minimum cells across vessel diameter at EVERY cross-section.

    Config:
        "mesh": {
            "SNAPPY_SETTINGS": {
                "span_refinement_enabled": true,
                "cells_across_span": 20
            }
        }

    Guidelines:
        - 15-20: Standard simulation (default: 20)
        - 25-30: High resolution, mesh-independent solutions
        - 10-15: Coarse, initial exploration

    Advantages:
        - Geometry-adaptive: automatically handles varying diameters
        - Guaranteed resolution: ensures minimum cells everywhere
        - Robust: works for coarctations, aneurysms, small branches

LEGACY METHODS (deprecated, for backward compatibility):
    - cells_per_diameter: Old method based on reference diameter
    - target_cell_size_mm: Absolute cell size specification

    These methods control blockMesh base cell size but don't guarantee
    resolution in narrow regions. Use cells_across_span instead.
"""

# =============================================================================
# MESH RESOLUTION GUIDELINES (v2.0)
# =============================================================================
# RECOMMENDED: Use cells_across_span for guaranteed resolution
#
# Example config:
#   "mesh": {
#     "SNAPPY_SETTINGS": {
#       "span_refinement_enabled": true,
#       "cells_across_span": 20
#     }
#   }
#
# LEGACY: cells_per_diameter (deprecated)
# Recommended cells_per_diameter values (if not using span refinement):
#   10-12: Initial exploration, fast iteration (coarse)
#   15-20: Standard simulation, balanced accuracy/cost (standard)
#   25-30: High resolution, mesh-independent solutions (fine)

# Minimum cells per diameter (validation threshold)
MIN_CELLS_PER_DIAMETER = 10  # Below this, results may be unreliable

# Default fallback: conservative starting point
# Only used if user provides no resolution specification
DEFAULT_CELLS_PER_DIAMETER = 10  # Conservative: resolves basic flow features

# =============================================================================
# SURFACE REFINEMENT LEVELS
# =============================================================================
# surfaceRefinementLevels: [min, max] snappy refinement levels
# Each level subdivides the base cell size by a factor of 2:
#   [0, 1]: Base cell size at surface
#   [1, 2]: 2× finer at surface (DEFAULT)
#   [2, 3]: 4× finer at surface
#   [1, 3]: Variable refinement (min 2×, max 4× finer)
#
# Cell count scaling at surface:
#   max=1: 1× surface cells
#   max=2: 4× surface cells (2² = 4)
#   max=3: 16× surface cells (4² = 16)
#
# Example config:
#   "SNAPPY_SETTINGS": {
#     "surfaceRefinementLevels": [1, 2]
#   }

# Default surface refinement levels [min, max]
DEFAULT_SURFACE_REFINEMENT_LEVELS = [1, 2]  # Moderate refinement

# =============================================================================
# BOUNDARY LAYER DEFAULTS
# =============================================================================
# Based on cardiovascular CFD best practices (SimVascular, OpenFOAM literature)
# Target: y+ ≈ 1-5 for wall-resolved simulations (accurate WSS prediction)
#
# Reference: For aortic blood flow at typical conditions:
#   - Wall shear stress: 1-3 Pa
#   - First cell height: 1-10 µm recommended
#   - Growth ratio: 1.1-1.3 (lower = smoother transition)
#   - Number of layers: 10-15 (captures boundary layer development)

DEFAULT_BOUNDARY_LAYER_SETTINGS = {
    'enabled': True,
    'num_layers': 10,              # Increased from 5-8 to 10 (SimVascular standard)
    'expansion_ratio': 1.2,        # Growth ratio between layers
    'final_layer_thickness': 0.3,  # Relative to undistorted cell
    'min_thickness': 0.1,          # Minimum layer thickness
    'relativeSizes': True,         # Sizes relative to base cell
}

# Quality tiers for boundary layer coverage
# Percentage of wall surface covered by prism layers
BL_COVERAGE_EXCELLENT = 95.0  # Target for publication quality
BL_COVERAGE_GOOD = 90.0       # Acceptable for production
BL_COVERAGE_FAIR = 80.0       # May miss some regions
BL_COVERAGE_POOR = 70.0       # Significant gaps - investigate

# BlockMesh size warning thresholds
# We don't try to "fix" large meshes - just warn the user and let them decide
MAX_BLOCKMESH_CELLS_WARNING = 10_000_000  # 10M cells - inform user it's large
MAX_BLOCKMESH_CELLS_LARGE = 25_000_000    # 25M cells - warn may cause OOM
MAX_BLOCKMESH_CELLS_HUGE = 50_000_000     # 50M cells - strongly warn

import math


# =============================================================================
# MESH GOAL PRESETS
# =============================================================================
# User-facing intent presets that map to existing meshing parameters.
# These simplify config for non-expert users while preserving full override.
#
# Usage in config.json:
#   "mesh": { "goal": "routine_hemodynamics" }
#
# Precedence: explicit user settings override goal defaults.

MESH_GOAL_PRESETS = {
    "pressure_fast": {
        "description": "Quick screening — pressure gradient, flow split, robust turnaround",
        "mesh_strategy": "adaptive_span",
        "cells_across_span": 10,
        "layers_mode": "off",
        "surfaceRefinementLevels": [0, 1],  # no layers → light surface is fine
    },
    "routine_hemodynamics": {
        "description": "Standard patient-specific run — pressure, flow, general hemodynamics",
        "mesh_strategy": "adaptive_span",
        "cells_across_span": 16,
        "layers_mode": "standard",
        "surfaceRefinementLevels": [2, 2],  # required for layer insertion
    },
    "wall_sensitive": {
        "description": "WSS, OSI, near-wall indices — higher resolution + wall layers",
        "mesh_strategy": "adaptive_span",
        "cells_across_span": 22,
        "layers_mode": "standard",
        "surfaceRefinementLevels": [2, 2],  # required for layer insertion
        "throat_uplift": 4,  # reserved — only applies if throat region is supplied
    },
}

# Layer profiles — optimised for vascular coverage (April 2026)
# Strategy C: featureAngle 190 + unlocked ratios + moderate smoothing
# BPM120: 51% coverage with 5 layers (vs 8% with OF defaults, 34% with 2-layer baseline)
LAYER_PROFILES = {
    "off": {
        "addLayers": False,
        "addLayer": 0,
    },
    "standard": {
        "addLayers": True,
        "addLayer": 5,
        "relativeSizes": True,
        "expansionRatio": 1.2,
        "finalLayerThickness": 0.3,
        "minThickness": 0.01,
        "featureAngle": 190,                # >180 forces layers at sharp junctions
        "nGrow": 0,                         # each face gets independent chance
        "nSmoothSurfaceNormals": 10,        # sweet spot for curved vessels
        "nSmoothNormals": 5,
        "nSmoothThickness": 0,             # disabled — lets each face adapt
        "nSmoothDisplacement": 5,
        "maxFaceThicknessRatio": 1.0,       # unlocked (0.5 was the main bottleneck)
        "maxThicknessToMedialRatio": 1.0,   # unlocked (0.3 blocked narrow regions)
        "minMedianAxisAngle": 30,           # allows tighter angles (was 90)
        "nBufferCellsNoExtrude": 0,
        "nLayerIter": 50,
        "nRelaxedIter": 0,
    },
}


def resolve_mesh_config(mesh_config: dict) -> dict:
    """
    Resolve public mesh API into SNAPPY_SETTINGS overrides.

    Public API keys (app language):
        mesh.goal              — preset name (pressure_fast, routine_hemodynamics, wall_sensitive)
        mesh.span_target       — cells across lumen (integer)
        mesh.mode              — "legacy" for old cells_per_diameter approach
        mesh.layers.mode       — "off", "standard"
        mesh.layers.enabled    — bool
        mesh.layers.num_layers — integer
        mesh.layers.expansion_ratio, final_layer_thickness, min_thickness

    Expert keys (pass-through):
        mesh.SNAPPY_SETTINGS.* — raw snappyHexMesh parameters

    Precedence: explicit user keys > public API > goal preset > base defaults.

    Args:
        mesh_config: The mesh section of the config dict.

    Returns:
        Dict of resolved SNAPPY_SETTINGS overrides to apply.
    """
    import logging
    logger = logging.getLogger("mesh_config")

    resolved = {}
    snappy = mesh_config.get("SNAPPY_SETTINGS", {})
    user_keys = snappy.get("_user_provided_keys", [])
    goal_name = mesh_config.get("goal")
    span_target = mesh_config.get("span_target")
    is_legacy = mesh_config.get("mode") == "legacy"

    # Conflict warnings
    if is_legacy and goal_name:
        logger.warning(f"Both mode='legacy' and goal='{goal_name}' set. Using legacy mode (goal ignored).")
    if goal_name and span_target is not None:
        logger.info(f"Both goal='{goal_name}' and span_target={span_target} set. span_target overrides goal's resolution.")

    # --- Legacy mode ---
    if is_legacy:
        resolved["mesh_strategy"] = "legacy_surface"
        return resolved

    # --- Goal preset ---
    if goal_name and goal_name in MESH_GOAL_PRESETS:
        preset = MESH_GOAL_PRESETS[goal_name]

        if "mesh_strategy" not in user_keys:
            resolved["mesh_strategy"] = preset["mesh_strategy"]

        if "cells_across_span" not in user_keys and "span_refinement_enabled" not in user_keys:
            resolved["span_refinement_enabled"] = True
            resolved["cells_across_span"] = preset["cells_across_span"]

        if "surfaceRefinementLevels" not in user_keys:
            resolved["surfaceRefinementLevels"] = preset["surfaceRefinementLevels"]

        # throat_uplift: store but don't auto-apply
        if "throat_uplift" in preset:
            resolved["_throat_uplift_reserved"] = preset["throat_uplift"]

        # Layers from preset (can be overridden by mesh.layers below)
        layers_mode = preset.get("layers_mode", "off")
        layer_user_keys = {"addLayers", "addLayer", "nSurfaceLayers"} & set(user_keys)
        if not layer_user_keys and layers_mode in LAYER_PROFILES:
            resolved.update(LAYER_PROFILES[layers_mode])

    # --- Public API: span_target ---
    if span_target is not None:
        resolved["span_refinement_enabled"] = True
        resolved["cells_across_span"] = int(span_target)
        if "mesh_strategy" not in resolved:
            resolved["mesh_strategy"] = "adaptive_span"

    # --- Public API: layers ---
    layers_config = mesh_config.get("layers", {})
    if layers_config:
        # layers.mode
        lmode = layers_config.get("mode")
        if lmode and lmode in LAYER_PROFILES:
            resolved.update(LAYER_PROFILES[lmode])
        # layers.enabled
        if "enabled" in layers_config:
            resolved["addLayers"] = layers_config["enabled"]
            if not layers_config["enabled"]:
                resolved["addLayer"] = 0
        # layers.num_layers
        if "num_layers" in layers_config:
            resolved["addLayer"] = layers_config["num_layers"]
            resolved["addLayers"] = True
        # layers.expansion_ratio, final_layer_thickness, min_thickness
        for key_map in [("expansion_ratio", "expansionRatio"),
                        ("final_layer_thickness", "finalLayerThickness"),
                        ("min_thickness", "minThickness")]:
            if key_map[0] in layers_config:
                resolved[key_map[1]] = layers_config[key_map[0]]

    return resolved


# Backward compatibility alias
def resolve_mesh_goal(mesh_config: dict) -> dict:
    """Backward-compatible alias for resolve_mesh_config."""
    return resolve_mesh_config(mesh_config)


# =============================================================================
# SPAN REFINEMENT PLANNER
# =============================================================================
# Determines coarse blockMesh background and span refinement level to achieve
# a target cells-across-span. Used by both production (mesh_setup.py) and
# benchmark (generate_case.py) to ensure identical planning logic.

# Background blockMesh limits (cells per reference diameter)
MIN_BLOCKMESH_CPD = 4   # Below this, snappy struggles with castellated mesh quality
MAX_BLOCKMESH_CPD = 20  # Upper search bound — raised from 12 to support fine meshes on large geometries

# Candidate scoring weights
_W_LEVEL = 3.0      # heavily penalise deep refinement (transition cost)
_W_BG = 1.0         # prefer moderate background (not too coarse or fine)
_W_OVERSHOOT = 0.5  # prefer not overshooting the target
_BG_IDEAL = 6       # ideal background cpd for scoring


def plan_span_background(
    cells_across_span: int,
    diameter_ratio: float = 1.0,
    min_blockmesh: int = MIN_BLOCKMESH_CPD,
    max_blockmesh: int = MAX_BLOCKMESH_CPD,
    max_span_level: int = 5,
) -> dict:
    """
    Geometry-adaptive planner: search feasible (bg_cpd, level) candidates
    and select the least aggressive pair that can satisfy the span target
    at both the reference vessel and the smallest relevant branch.

    The planner accounts for the vessel diameter range: geometries with
    large diameter ratios (e.g., aorta with small branches) need deeper
    refinement or denser backgrounds to resolve the smallest lumen.

    Args:
        cells_across_span: Target cells across vessel lumen
        diameter_ratio: D_ref / D_min (1.0 = uniform diameter, >1 = multi-scale)
        min_blockmesh: Minimum background cells/D (quality floor)
        max_blockmesh: Maximum background cells/D (search ceiling)
        max_span_level: Maximum span refinement level to search

    Returns:
        dict with keys:
            background_cpd: int
            span_level: int
            theoretical_cells_across: int — bg_cpd * 2^span_level (at reference diameter)
            achievable_at_min_branch: float — estimated cells across smallest branch
            warning: str or None
    """
    T = cells_across_span
    R = max(1.0, diameter_ratio)

    # Generate and score all feasible candidates
    candidates = []
    for level in range(1, max_span_level + 1):
        mult = 2 ** level
        for bg in range(min_blockmesh, max_blockmesh + 1):
            theoretical = bg * mult
            if theoretical < T:
                continue  # can't achieve target at reference diameter

            # Estimate cells across the smallest branch
            # bg is cells/D at reference diameter; at smallest branch it's bg/R
            bg_at_min = bg / R
            achievable_min = bg_at_min * mult

            # Score: prefer lowest level, moderate bg, minimal overshoot
            score = (
                _W_LEVEL * level
                + _W_BG * abs(bg - _BG_IDEAL)
                + _W_OVERSHOOT * (theoretical / T - 1.0)
            )

            passes_branch = achievable_min >= T * 0.7

            candidates.append({
                "bg": bg,
                "level": level,
                "theoretical": theoretical,
                "achievable_min": round(achievable_min, 1),
                "passes_branch": passes_branch,
                "score": round(score, 2),
            })

    # Pick best: first try candidates that pass the branch threshold
    passing = [c for c in candidates if c["passes_branch"]]

    if passing:
        best = min(passing, key=lambda c: c["score"])
        warning = None
    elif candidates:
        # No candidate fully satisfies branches — pick best coverage
        best = max(candidates, key=lambda c: c["achievable_min"])
        warning = (
            f"No (bg_cpd, level) combination fully resolves smallest branch "
            f"(diameter_ratio={R:.1f}). Best achievable: {best['achievable_min']:.1f} "
            f"cells across (target {T}). Consider reducing span target or "
            f"accepting lower resolution at small branches."
        )
    else:
        # Absolute fallback
        best = {"bg": min_blockmesh, "level": max_span_level,
                "theoretical": min_blockmesh * (2 ** max_span_level),
                "achievable_min": 0, "score": 999}
        warning = f"cells_across_span={T} with diameter_ratio={R:.1f} exceeds planner range."

    return {
        "background_cpd": best["bg"],
        "span_level": best["level"],
        "theoretical_cells_across": best["theoretical"],
        "achievable_at_min_branch": best.get("achievable_min", 0),
        "warning": warning,
    }


def compute_cell_size(cells_per_diameter: float, reference_diameter_mm: float) -> float:
    """
    Compute actual cell size in mm from cells/diameter specification.

    Args:
        cells_per_diameter: Target number of cells across diameter
        reference_diameter_mm: Reference vessel diameter in millimeters

    Returns:
        Cell size in millimeters

    Examples:
        >>> compute_cell_size(12, 18.5)
        1.542
        >>> compute_cell_size(20, 6.4)
        0.32
    """
    if cells_per_diameter <= 0 or reference_diameter_mm <= 0:
        raise ValueError("cells_per_diameter and reference_diameter_mm must be positive")

    return reference_diameter_mm / cells_per_diameter


def check_blockmesh_size(target_cell_size_mm: float, bbox_volume_mm3: float) -> dict:
    """
    Check if blockMesh will be large and return warning info.

    Simple approach: just calculate size and warn if large.
    NO automatic changes - user gets what they asked for.

    Args:
        target_cell_size_mm: User's requested cell size
        bbox_volume_mm3: Volume of bounding box in mm³

    Returns:
        dict with 'estimated_cells', 'warning_level', 'message'
    """
    estimated_cells = bbox_volume_mm3 / (target_cell_size_mm ** 3)
    estimated_memory_gb = estimated_cells / 1e6 * 0.3

    if estimated_cells < MAX_BLOCKMESH_CELLS_WARNING:
        return {
            'estimated_cells': estimated_cells,
            'warning_level': 'ok',
            'message': None
        }
    elif estimated_cells < MAX_BLOCKMESH_CELLS_LARGE:
        return {
            'estimated_cells': estimated_cells,
            'warning_level': 'large',
            'message': (
                f"Large blockMesh: {estimated_cells/1e6:.1f}M cells (~{estimated_memory_gb:.1f}GB RAM). "
                f"Feasible with 16GB+ RAM and parallel meshing. "
                f"If OOM occurs, reduce cells_per_diameter."
            )
        }
    elif estimated_cells < MAX_BLOCKMESH_CELLS_HUGE:
        return {
            'estimated_cells': estimated_cells,
            'warning_level': 'very_large',
            'message': (
                f"Very large blockMesh: {estimated_cells/1e6:.1f}M cells (~{estimated_memory_gb:.1f}GB RAM). "
                f"May cause OOM. Recommendations: (1) Reduce cells_per_diameter, "
                f"(2) Use cluster/HPC, (3) Enable parallel meshing."
            )
        }
    else:
        return {
            'estimated_cells': estimated_cells,
            'warning_level': 'huge',
            'message': (
                f"Extremely large blockMesh: {estimated_cells/1e6:.1f}M cells (~{estimated_memory_gb:.1f}GB RAM). "
                f"Will likely cause OOM. Strongly recommend: (1) Reduce cells_per_diameter significantly, "
                f"(2) Use HPC cluster with 64GB+ RAM."
            )
        }
