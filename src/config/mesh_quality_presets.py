"""
Mesh Quality Presets for snappyHexMesh
======================================

Presets provide parameter OVERRIDES for specific use cases.
Base defaults are defined in base.py (single source of truth).

These presets only contain values that DIFFER from base.py defaults.
User config values always take precedence over both preset and base.py.

Configuration merge order (later overrides earlier):
1. base.py SNAPPY_SETTINGS (OpenFOAM defaults for cardiovascular)
2. Preset values (if quality_preset specified)
3. User config.json SNAPPY_SETTINGS

Available presets:
- draft: Fast meshing for initial exploration (~1x time)
- standard: Proven robust for cardiovascular CFD (~2-3x time) [RECOMMENDED]
- high_quality: Maximum quality for complex geometries (~5-10x time)

Usage in config.json::

    "mesh": {
        "quality_preset": "standard"
    }

VALIDATED: DOE study (22 tests) + Span Refinement study (26 tests):
- 20/20 non-span DOE tests PASSED (skewness 3.04-3.74)
- 23/24 span refinement tests PASSED (skewness 2.71-2.76)

Parameter sensitivity analysis (effect on skewness):
- nSmoothThickness: +0.367 ** (LOWER is better!)
- snapTolerance: +0.286 ** (use 1.0, not 2.0)
- maxFaceThicknessRatio: +0.286 ** (LOWER is better - use 0.5)
- expansionRatio: +0.226 ** (use 1.15-1.2)
- nSmoothSurfaceNormals: +0.004 (insensitive - 10-50 all work)

SPAN REFINEMENT: Works with proper configuration!
- Safe: span_refinement_level=1 or 2 with cells_across_span=10-20
- Unsafe: span_refinement_level=3 with cells_across_span>10 (causes skew>4.0)
- Keep surfaceRefinementLevels=[1,2] when using span (NOT [2,3])

Ref: openfoam.com/documentation/guides/latest/doc/guide-meshing-snappyhexmesh
"""

from typing import Dict, Any


# =============================================================================
# MESH QUALITY PRESETS
# =============================================================================
# Only contains OVERRIDES - values that differ from base.py defaults
# Base.py provides OpenFOAM defaults optimized for cardiovascular geometries

MESH_QUALITY_PRESETS: Dict[str, Dict[str, Any]] = {
    # =========================================================================
    # DRAFT: Fast meshing for initial exploration
    # =========================================================================
    # Use for: Quick geometry checks, workflow testing, coarse mesh studies
    # Meshing time: ~1x baseline
    # Philosophy: Speed over quality - reduce iterations, relax constraints
    "draft": {
        # Reduced iterations for speed
        "nCellsBetweenLevels": 2,  # base.py: 3 → faster but less smooth
        "nSolveIter": 10,  # Proven: 10 works well
        "nFeatureSnapIter": 5,  # Proven: 5 sufficient
        "nLayerIter": 30,  # base.py: 50 → faster layer addition
        "nRelaxedIter": 10,  # Switch to relaxed sooner
        # Relaxed quality thresholds
        "maxNonOrtho": 70,  # base.py: 65 → more permissive
        "maxInternalSkewness": 10,  # More permissive for draft
        # Minimal smoothing for speed
        "nSmoothSurfaceNormals": 10,  # Reduced from standard
        "nSmoothThickness": 10,  # Reduced from standard
        # Proven parameters
        "snapTolerance": 1.0,  # Proven: 1.0 works better than 2.0
        "featureAngle": 160,  # Conservative layer coverage
    },
    # =========================================================================
    # STANDARD: Proven robust for cardiovascular CFD [RECOMMENDED]
    # =========================================================================
    # Use for: Production runs, typical aortic geometries, most CFD studies
    # Updated: 2026-01-07 - Tightened to prevent negative volume cells
    # Meshing time: ~2-3x baseline
    "standard": {
        # Base.py now has tightened defaults, standard preset uses base defaults
        # Only override what differs from the new tightened base.py
        # Layer parameters
        "nSmoothSurfaceNormals": 30,  # Match base.py default
        "nSmoothThickness": 15,  # Match base.py default
        "nLayerIter": 100,  # Match base.py default
        "featureAngle": 150,  # Match base.py default
        "maxFaceThicknessRatio": 0.4,  # Match base.py default
        # Refinement transitions
        "nCellsBetweenLevels": 3,  # DOE: insensitive
    },
    # =========================================================================
    # HIGH_QUALITY: Maximum quality for LES and second-order schemes
    # =========================================================================
    # Use for: LES, second-order CFD (LUST, linearUpwind), publications, validation
    # Target: Skewness < 2.0, Non-orthogonality < 55° (required for LES/accurate)
    # Updated: 2026-01-07 - Even tighter to prevent negative volume cells for LES
    # Meshing time: ~5-10x baseline
    "high_quality": {
        # Snap parameters - maximum iterations for complex geometry
        "snapTolerance": 2.0,  # Higher tolerance for better snapping
        "nSolveIter": 150,  # Maximum iterations for complex geometry
        "nFeatureSnapIter": 15,  # More iterations for feature edges
        # Enhanced smoothing for low skewness and no negative volumes
        "nSmoothSurfaceNormals": 50,  # Maximum for smoother surface
        "nSmoothThickness": 20,  # Increased smoothing
        "nSmoothPatch": 10,  # More pre-snap smoothing
        "nSmoothNormals": 10,  # Additional normal smoothing
        "nSmoothDisplacement": 20,  # More displacement smoothing
        # Relaxation iterations
        "nRelaxIter": 15,  # More relaxation iterations
        # Layer iterations - maximum effort
        "nLayerIter": 150,  # More iterations for complex cases
        "nRelaxedIter": 75,  # More iterations before relaxing
        "featureAngle": 140,  # Conservative for better quality
        # Conservative expansion ratio
        "expansionRatio": 1.08,  # Very gentle growth for LES
        # Transition smoothness
        "nCellsBetweenLevels": 4,  # More cells between levels for smoothness
        # STRICT quality thresholds for LES and second-order schemes
        "maxNonOrtho": 55,  # Strict non-orthogonality for LES
        "maxInternalSkewness": 2.0,  # STRICT: Required for LES/second-order
        "maxBoundarySkewness": 3,  # Very strict boundary skewness for WSS
        # Cell quality - ultra-tight to prevent negative volumes
        "minVol": 1e-20,  # Ultra-tight volume threshold
        "minDeterminant": 0.02,  # Stricter determinant
        "minTwist": 0.005,  # Stricter twist
        # Layer coverage
        "maxFaceThicknessRatio": 0.3,  # Even lower for quality
        "maxThicknessToMedialRatio": 0.2,  # Tighter for narrow regions
        # Mesh quality controls
        "minMedianAxisAngle": 90,  # Better medial axis for layers
        "minThickness": 0.1,  # Conservative minimum thickness
        "nSmoothScale": 8,  # More smoothing iterations
    },
}


def get_mesh_preset(preset_name: str) -> Dict[str, Any]:
    """
    Get mesh quality preset by name.

    Args:
        preset_name: One of 'draft', 'standard', 'high_quality'

    Returns:
        Dictionary of snappyHexMesh parameter overrides

    Raises:
        ValueError: If preset_name is not recognized
    """
    if preset_name not in MESH_QUALITY_PRESETS:
        valid_presets = list(MESH_QUALITY_PRESETS.keys())
        raise ValueError(f"Unknown mesh quality preset: '{preset_name}'. " f"Valid options: {valid_presets}")
    return MESH_QUALITY_PRESETS[preset_name].copy()


def get_available_presets() -> list:
    """Return list of available mesh quality preset names."""
    return list(MESH_QUALITY_PRESETS.keys())


def merge_preset_with_config(preset_name: str, user_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge mesh quality preset with user configuration.

    User-specified values override preset defaults.

    Args:
        preset_name: Name of the preset to use as base
        user_config: User-provided SNAPPY_SETTINGS overrides

    Returns:
        Merged configuration with user values taking precedence
    """
    preset = get_mesh_preset(preset_name)

    # User config overrides preset
    merged = preset.copy()
    merged.update(user_config)

    return merged


# =============================================================================
# PRESET COMPARISON TABLE (Updated from DOE + Span studies 2024-12-22)
# =============================================================================
# Key parameters that differ between presets (all share proven snap params)
#
# Parameter              | Draft | Standard | High Quality | DOE Effect
# -----------------------|-------|----------|--------------|------------
# nSmoothSurfaceNormals  |    10 |       20 |           30 | +0.004 (insensitive)
# nSmoothThickness       |    10 |       10 |           10 | +0.367 ** LOW better!
# maxFaceThicknessRatio  |   0.5 |      0.5 |          0.5 | +0.286 ** LOW better!
# expansionRatio         |  1.2  |      1.2 |         1.15 | +0.226 ** 1.15 best
# nLayerIter             |    30 |       50 |          100 |
# nCellsBetweenLevels    |     2 |        3 |            3 | -0.005 (insensitive)
# featureAngle           |   160 |      170 |          180 | -0.016 (insensitive)
# maxInternalSkewness    |    10 |   8(base)|            5 | Threshold only
#
# All presets share: snapTolerance=1.0, nSolveIter=10, nFeatureSnapIter=5
#
# SPAN REFINEMENT (from follow-up study, 23/24 passed):
# - Safe: span_refinement_level=1 or 2 with cells_across_span=10-20 (skew=2.71-2.76)
# - Unsafe: span_refinement_level=3 with cells_across_span>10 (skew>4.0)
# - Keep surfaceRefinementLevels=[1,2] when using span (NOT [2,3])
#
# =============================================================================
# PRESET DOCUMENTATION
# =============================================================================

PRESET_DESCRIPTIONS = {
    "draft": {
        "description": "Fast meshing for initial exploration",
        "use_cases": ["Quick geometry checks", "Workflow testing", "Coarse mesh studies"],
        "relative_time": "1x",
        "quality_level": "Basic",
        "key_changes": "nLayerIter=30, relaxed thresholds (maxSkew=10)",
    },
    "standard": {
        "description": "Proven robust for cardiovascular CFD [RECOMMENDED]",
        "use_cases": ["Production runs", "Standard aortic geometries", "10-layer boundary mesh"],
        "relative_time": "2-3x",
        "quality_level": "Excellent",
        "key_changes": "DOE validated: 20/20 passed, skew=3.60, nSmoothThick=10, maxFaceThick=0.5",
    },
    "high_quality": {
        "description": "Maximum quality for second-order schemes (LUST, linearUpwind)",
        "use_cases": ["Second-order CFD", "Accurate/publication profiles", "Validation studies"],
        "relative_time": "5-10x",
        "quality_level": "Publication (skew<2, ortho<60°)",
        "key_changes": "maxSkew=2.0, maxOrtho=55, expRatio=1.12, nLayerIter=150, enhanced smoothing",
    },
}


def print_preset_info():
    """Print information about available mesh quality presets."""
    print("\nMesh Quality Presets")
    print("=" * 70)
    print("Presets provide OVERRIDES to base.py defaults (OpenFOAM cardiovascular)")
    print("=" * 70)

    for name, info in PRESET_DESCRIPTIONS.items():
        print(f"\n{name.upper()}")
        print(f"  Description: {info['description']}")
        print(f"  Quality: {info['quality_level']}")
        print(f"  Time: {info['relative_time']} baseline")
        print(f"  Key changes: {info['key_changes']}")
        print("  Use cases:")
        for use_case in info["use_cases"]:
            print(f"    - {use_case}")

        # Show override count
        preset = MESH_QUALITY_PRESETS[name]
        print(f"  Parameters overridden: {len(preset)}")


def print_preset_details(preset_name: str):
    """Print detailed parameter values for a specific preset."""
    if preset_name not in MESH_QUALITY_PRESETS:
        print(f"Unknown preset: {preset_name}")
        return

    print(f"\n{preset_name.upper()} Preset - Parameter Overrides")
    print("=" * 50)
    print("These values override base.py defaults:")
    print("-" * 50)

    preset = MESH_QUALITY_PRESETS[preset_name]
    for key, value in sorted(preset.items()):
        print(f"  {key}: {value}")
