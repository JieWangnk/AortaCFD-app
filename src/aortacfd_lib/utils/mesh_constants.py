"""
Mesh resolution constants for AortaCFD.

Resolution Philosophy:
    Users specify mesh resolution through ONE of two explicit parameters:

    1. target_cell_size_mm: Absolute cell size in millimeters
       - Direct control for experienced users
       - Specify exact element size regardless of geometry
       - Example: target_cell_size_mm = 0.5

    2. cells_per_diameter: Geometry-adaptive resolution
       - Cell size computed as: diameter / cells_per_diameter
       - Automatically scales to patient anatomy
       - Example: cells_per_diameter = 12

    3. Fallback (if neither specified):
       - Uses 10 cells across reference diameter
       - Conservative default suitable for initial exploration
       - Warning issued to encourage explicit specification

    NO PRESETS (coarse/medium/fine) - These hide actual resolution and
    prevent mesh independence verification. Users must choose values
    appropriate for their specific validation requirements.
"""

# Default fallback: conservative starting point
# Only used if user provides no resolution specification
DEFAULT_CELLS_PER_DIAMETER = 10  # Conservative: resolves basic flow features

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
