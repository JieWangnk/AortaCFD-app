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
