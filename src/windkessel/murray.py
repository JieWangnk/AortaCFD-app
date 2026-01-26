# src/windkessel/murray.py
"""
Murray's law flow splitting calculations.

Murray's law states that flow rate in a vessel scales with
the cube of its diameter (or area^1.5):

    Q ∝ D³ ∝ A^1.5

This is used to distribute total cardiac output among
outlet branches based on their cross-sectional areas.

Usage:
    from src.windkessel.murray import calculate_murray_flow_split

    areas = [1e-4, 5e-5, 3e-5]  # m²
    fractions = calculate_murray_flow_split(areas)
    # Returns: [0.58, 0.26, 0.16]
"""

import numpy as np
from typing import Dict, List, Tuple, Union
import logging

logger = logging.getLogger(__name__)


def calculate_murray_flow_split(
    areas: Union[List[float], np.ndarray],
    exponent: float = 1.5,
) -> np.ndarray:
    """
    Calculate flow fractions using Murray's law.

    Murray's law: Q ∝ D³ ∝ A^1.5

    Args:
        areas: Cross-sectional areas of outlets (m²)
        exponent: Murray exponent (default 1.5 for A^1.5)
                 Use 3.0 if input is diameter instead of area

    Returns:
        Array of flow fractions (sum = 1.0)
    """
    areas = np.asarray(areas, dtype=float)

    if np.any(areas <= 0):
        raise ValueError("All areas must be positive")

    # Murray's law: Q_i / Q_total = A_i^1.5 / sum(A_j^1.5)
    weighted = areas ** exponent
    fractions = weighted / np.sum(weighted)

    return fractions


def calculate_murray_flow_split_named(
    outlet_areas: Dict[str, float],
    exponent: float = 1.5,
) -> Dict[str, float]:
    """
    Calculate flow fractions for named outlets.

    Args:
        outlet_areas: Dictionary mapping outlet name to area (m²)
        exponent: Murray exponent

    Returns:
        Dictionary mapping outlet name to flow fraction
    """
    names = list(outlet_areas.keys())
    areas = [outlet_areas[name] for name in names]

    fractions = calculate_murray_flow_split(areas, exponent)

    return dict(zip(names, fractions))


def calculate_murray_resistance_split(
    total_resistance: float,
    areas: Union[List[float], np.ndarray],
    exponent: float = 1.5,
) -> np.ndarray:
    """
    Distribute total resistance among parallel outlets using Murray's law.

    For parallel resistances:
    1/R_total = sum(1/R_i)

    And we want flow distribution to follow Murray's law:
    Q_i/Q_total = A_i^1.5 / sum(A^1.5)

    This gives:
    R_i = R_total * sum(A^1.5) / A_i^1.5

    Args:
        total_resistance: Total peripheral resistance (Pa·s/m³)
        areas: Outlet areas (m²)
        exponent: Murray exponent

    Returns:
        Array of individual outlet resistances
    """
    areas = np.asarray(areas, dtype=float)
    fractions = calculate_murray_flow_split(areas, exponent)

    # For parallel flow, R_i = R_total / flow_fraction_i
    # (larger fraction = more flow = lower resistance)
    resistances = total_resistance / fractions

    return resistances


def area_to_diameter(area: float) -> float:
    """
    Convert circular cross-sectional area to diameter.

    D = 2 * sqrt(A / π)

    Args:
        area: Cross-sectional area (m²)

    Returns:
        Diameter (m)
    """
    return 2 * np.sqrt(area / np.pi)


def diameter_to_area(diameter: float) -> float:
    """
    Convert diameter to circular cross-sectional area.

    A = π * (D/2)²

    Args:
        diameter: Diameter (m)

    Returns:
        Cross-sectional area (m²)
    """
    return np.pi * (diameter / 2) ** 2


def calculate_hydraulic_diameter(area: float, perimeter: float) -> float:
    """
    Calculate hydraulic diameter for non-circular cross-sections.

    D_h = 4 * A / P

    Args:
        area: Cross-sectional area (m²)
        perimeter: Wetted perimeter (m)

    Returns:
        Hydraulic diameter (m)
    """
    if perimeter <= 0:
        raise ValueError("Perimeter must be positive")
    return 4 * area / perimeter


def estimate_outlet_areas_from_stl(
    stl_dir: str,
    outlet_names: List[str],
    scale_factor: float = 1.0,
) -> Dict[str, float]:
    """
    Estimate outlet areas from STL files.

    Args:
        stl_dir: Directory containing STL files
        outlet_names: List of outlet patch names
        scale_factor: Scale factor already applied to STLs

    Returns:
        Dictionary mapping outlet name to area (m²)
    """
    import os

    try:
        from stl import mesh as np_stl_mesh
    except ImportError:
        logger.error("numpy-stl required for STL area calculation")
        return {}

    areas = {}

    for name in outlet_names:
        # Find STL file
        stl_file = None
        for f in os.listdir(stl_dir):
            if f.lower().endswith('.stl') and name.lower() in f.lower():
                stl_file = os.path.join(stl_dir, f)
                break

        if stl_file is None:
            logger.warning(f"STL file not found for outlet: {name}")
            continue

        try:
            stl_mesh = np_stl_mesh.Mesh.from_file(stl_file)
            # Calculate surface area (sum of triangle areas)
            # Each triangle: area = 0.5 * |cross product|
            v0 = stl_mesh.vectors[:, 0, :]
            v1 = stl_mesh.vectors[:, 1, :]
            v2 = stl_mesh.vectors[:, 2, :]
            cross = np.cross(v1 - v0, v2 - v0)
            triangle_areas = 0.5 * np.linalg.norm(cross, axis=1)
            total_area = np.sum(triangle_areas)
            areas[name] = total_area
            logger.debug(f"Outlet {name}: area = {total_area:.6e} m²")
        except Exception as e:
            logger.warning(f"Failed to read STL for {name}: {e}")

    return areas


def validate_flow_split(
    fractions: Union[List[float], np.ndarray],
    tolerance: float = 1e-6,
) -> bool:
    """
    Validate that flow fractions sum to 1.0.

    Args:
        fractions: Flow fractions
        tolerance: Acceptable deviation from 1.0

    Returns:
        True if valid
    """
    fractions = np.asarray(fractions)

    if np.any(fractions < 0):
        logger.warning("Negative flow fraction detected")
        return False

    total = np.sum(fractions)
    if abs(total - 1.0) > tolerance:
        logger.warning(f"Flow fractions sum to {total}, not 1.0")
        return False

    return True


def print_flow_distribution(
    outlet_names: List[str],
    areas: List[float],
    fractions: List[float],
) -> str:
    """
    Generate formatted string showing flow distribution.

    Args:
        outlet_names: Outlet names
        areas: Outlet areas (m²)
        fractions: Flow fractions

    Returns:
        Formatted table string
    """
    lines = [
        "Flow Distribution (Murray's Law)",
        "-" * 50,
        f"{'Outlet':<20} {'Area (cm²)':<12} {'Flow %':<10}",
        "-" * 50,
    ]

    for name, area, frac in zip(outlet_names, areas, fractions):
        area_cm2 = area * 1e4  # m² to cm²
        lines.append(f"{name:<20} {area_cm2:<12.4f} {frac*100:<10.1f}")

    lines.append("-" * 50)
    total_area = sum(areas) * 1e4
    lines.append(f"{'Total':<20} {total_area:<12.4f} {100.0:<10.1f}")

    return "\n".join(lines)
