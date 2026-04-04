"""Post-mesh resolution audit for AortaCFD.

Combines mesh quality metrics (from MeshQualityChecker) with achieved
lumen resolution estimates to produce a structured QC report.

The resolution proxy estimates cells-across-lumen at each patch by
computing boundary face areas from the polyMesh data. This is a proxy,
not a geometric truth — validated to ±15% against manual ParaView
measurements on benchmark geometries.
"""

import math
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np

from .mesh_quality_checker import MeshQualityChecker


# ============================================================================
# Quality thresholds (from OpenFOAM meshQualityDict + vascular CFD practice)
# ============================================================================

THRESHOLDS = {
    "pass": {
        "max_non_ortho": 65,
        "max_internal_skewness": 4,
        "max_boundary_skewness": 20,
        "min_determinant": 0.001,
        "min_face_weight": 0.05,
        "min_vol_ratio": 0.01,
    },
    "preferred": {
        "max_non_ortho": 60,
        "max_internal_skewness": 3.5,
        "max_boundary_skewness": 15,
    },
    "hard_fail": {
        "max_non_ortho": 70,
    },
}


def audit_mesh(
    case_dir: str,
    geometry_info: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run post-mesh quality and resolution audit.

    Args:
        case_dir: OpenFOAM case directory (contains constant/polyMesh, logs/)
        geometry_info: Dict with keys:
            inlet_radius_m: float — inlet radius in meters
            outlet_radii_m: list[float] — outlet radii in meters
            outlet_names: list[str] — outlet patch names
            inlet_name: str — inlet patch name
        config: Merged AortaCFD config dict

    Returns:
        Structured audit report dict.
    """
    snappy = config.get("mesh", {}).get("SNAPPY_SETTINGS", {})

    report = {
        "strategy": snappy.get("mesh_strategy", "unknown"),
        "requested_cells_across_span": snappy.get("cells_across_span"),
        "planner": _extract_planner_info(snappy),
        "quality": _run_quality_check(case_dir),
        "resolution_proxy": {},
        "cell_counts": _extract_cell_counts(case_dir),
        "verdict": "pass",
        "warnings": [],
    }

    # Resolution proxy at each patch
    inlet_name = geometry_info.get("inlet_name", "inlet")
    inlet_r = geometry_info.get("inlet_radius_m")
    if inlet_r and inlet_r > 0:
        proxy = estimate_patch_resolution(case_dir, inlet_name, inlet_r * 2)
        if proxy:
            report["resolution_proxy"]["inlet"] = proxy

    outlet_names = geometry_info.get("outlet_names", [])
    outlet_radii = geometry_info.get("outlet_radii_m", [])
    for name, radius in zip(outlet_names, outlet_radii):
        if radius and radius > 0:
            proxy = estimate_patch_resolution(case_dir, name, radius * 2)
            if proxy:
                report["resolution_proxy"][name] = proxy

    # Determine verdict
    report["verdict"], report["warnings"] = _determine_verdict(report)

    return report


def _extract_planner_info(snappy: dict) -> Optional[dict]:
    """Extract span planner settings if available."""
    if not snappy.get("span_refinement_enabled"):
        return None
    from .utils.mesh_constants import plan_span_background

    target = snappy.get("cells_across_span", 0)
    if target <= 0:
        return None
    plan = plan_span_background(target)
    return plan


def _run_quality_check(case_dir: str) -> dict:
    """Run MeshQualityChecker and return its report."""
    checker = MeshQualityChecker()
    return checker.analyze_mesh_quality(case_dir)


def _extract_cell_counts(case_dir: str) -> dict:
    """Extract blockMesh and final cell counts from logs."""
    counts = {}

    # blockMesh cells
    bm_log = Path(case_dir) / "logs" / "log.blockMesh"
    if bm_log.exists():
        text = bm_log.read_text()
        m = re.search(r"nCells:\s*(\d+)", text)
        if m:
            counts["blockmesh_cells"] = int(m.group(1))

    # Final cells from checkMesh
    cm_log = Path(case_dir) / "logs" / "log.checkMesh"
    if cm_log.exists():
        text = cm_log.read_text()
        m = re.search(r"^\s*cells:\s+(\d+)", text, re.MULTILINE)
        if m:
            counts["final_cells"] = int(m.group(1))

    if "blockmesh_cells" in counts and "final_cells" in counts:
        counts["retained_fraction"] = round(
            counts["final_cells"] / counts["blockmesh_cells"], 3
        )

    return counts


def estimate_patch_resolution(
    case_dir: str, patch_name: str, patch_diameter_m: float
) -> Optional[dict]:
    """
    Estimate achieved cells across lumen at a boundary patch.

    Method: compute mean boundary face area from polyMesh/points + faces + boundary,
    then cells_across ≈ diameter / sqrt(mean_face_area).

    This is a PROXY — validated to ±15% against manual measurement.

    Args:
        case_dir: OpenFOAM case directory
        patch_name: Boundary patch name (e.g., 'inlet', 'outlet1')
        patch_diameter_m: Patch diameter in meters

    Returns:
        Dict with proxy estimate, or None if polyMesh data unavailable.
    """
    poly_dir = Path(case_dir) / "constant" / "polyMesh"
    if not poly_dir.exists():
        return None

    try:
        points = _read_openfoam_points(poly_dir / "points")
        faces = _read_openfoam_faces(poly_dir / "faces")
        boundary = _read_openfoam_boundary(poly_dir / "boundary")
    except Exception:
        return None

    if patch_name not in boundary:
        return None

    patch_info = boundary[patch_name]
    start_face = patch_info["startFace"]
    n_faces = patch_info["nFaces"]

    if n_faces == 0:
        return None

    # Compute face areas for this patch
    face_areas = []
    for i in range(start_face, start_face + n_faces):
        if i >= len(faces):
            break
        face_pts = faces[i]
        if len(face_pts) < 3:
            continue
        # Triangle fan area for polygonal face
        area = 0.0
        p0 = points[face_pts[0]]
        for j in range(1, len(face_pts) - 1):
            p1 = points[face_pts[j]]
            p2 = points[face_pts[j + 1]]
            cross = np.cross(p1 - p0, p2 - p0)
            area += 0.5 * np.linalg.norm(cross)
        face_areas.append(area)

    if not face_areas:
        return None

    mean_area = np.mean(face_areas)
    cell_size_m = math.sqrt(mean_area)
    cells_across = patch_diameter_m / cell_size_m if cell_size_m > 0 else 0

    return {
        "patch": patch_name,
        "diameter_mm": round(patch_diameter_m * 1000, 2),
        "n_faces": n_faces,
        "mean_face_area_mm2": round(mean_area * 1e6, 4),
        "cell_size_proxy_mm": round(cell_size_m * 1000, 4),
        "cells_across_proxy": round(cells_across, 1),
        "method": "boundary_face_area",
    }


def _determine_verdict(report: dict) -> tuple:
    """
    Determine pass/warn/fail verdict from quality + resolution.

    Returns:
        (verdict: str, warnings: list[str])
    """
    warnings = []
    verdict = "pass"

    # Quality check
    quality = report.get("quality", {})
    metrics = quality.get("metrics", {})

    max_ortho = metrics.get("max_non_orthogonality", 0)
    max_skew = metrics.get("max_skewness", 0)

    # Hard fail
    if max_ortho > THRESHOLDS["hard_fail"]["max_non_ortho"]:
        verdict = "fail"
        warnings.append(f"maxNonOrtho={max_ortho:.1f} exceeds hard limit ({THRESHOLDS['hard_fail']['max_non_ortho']})")

    if quality.get("status") == "failed":
        verdict = "fail"
        warnings.append("checkMesh reported failed checks")

    # Pass threshold
    if verdict != "fail":
        if max_ortho > THRESHOLDS["pass"]["max_non_ortho"]:
            verdict = "warn"
            warnings.append(f"maxNonOrtho={max_ortho:.1f} above pass threshold ({THRESHOLDS['pass']['max_non_ortho']})")

        if max_skew > THRESHOLDS["pass"]["max_internal_skewness"]:
            verdict = "warn"
            warnings.append(f"maxSkewness={max_skew:.2f} above pass threshold ({THRESHOLDS['pass']['max_internal_skewness']})")

    # Preferred
    if verdict == "pass":
        if max_ortho > THRESHOLDS["preferred"]["max_non_ortho"]:
            warnings.append(f"maxNonOrtho={max_ortho:.1f} above preferred ({THRESHOLDS['preferred']['max_non_ortho']})")
        if max_skew > THRESHOLDS["preferred"]["max_internal_skewness"]:
            warnings.append(f"maxSkewness={max_skew:.2f} above preferred ({THRESHOLDS['preferred']['max_internal_skewness']})")

    # Resolution check
    requested = report.get("requested_cells_across_span")
    if requested:
        for patch_name, proxy in report.get("resolution_proxy", {}).items():
            achieved = proxy.get("cells_across_proxy", 0)
            if achieved < requested * 0.7:
                warnings.append(
                    f"{patch_name}: achieved {achieved:.0f} cells across vs requested {requested} (below 70% threshold)"
                )
                if verdict == "pass":
                    verdict = "warn"

    return verdict, warnings


# ============================================================================
# polyMesh readers (pure Python, no OpenFOAM dependency)
# ============================================================================


def _read_openfoam_points(filepath: Path) -> np.ndarray:
    """Read OpenFOAM points file → (N, 3) float array."""
    text = filepath.read_text()

    # Find the data block between ( and )
    # Skip the FoamFile header, find the count, then the parenthesised block
    lines = text.split("\n")

    n_points = None
    data_start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.isdigit() and n_points is None:
            n_points = int(stripped)
        if stripped == "(":
            data_start = i + 1
            break

    if n_points is None or data_start is None:
        raise ValueError(f"Cannot parse points file: {filepath}")

    points = np.zeros((n_points, 3))
    idx = 0
    for i in range(data_start, len(lines)):
        line = lines[i].strip()
        if line == ")":
            break
        # Format: (x y z)
        line = line.strip("()")
        parts = line.split()
        if len(parts) == 3:
            points[idx] = [float(parts[0]), float(parts[1]), float(parts[2])]
            idx += 1

    return points[:idx]


def _read_openfoam_faces(filepath: Path) -> list:
    """Read OpenFOAM faces file → list of lists of point indices."""
    text = filepath.read_text()
    lines = text.split("\n")

    n_faces = None
    data_start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.isdigit() and n_faces is None:
            n_faces = int(stripped)
        if stripped == "(":
            data_start = i + 1
            break

    if n_faces is None or data_start is None:
        raise ValueError(f"Cannot parse faces file: {filepath}")

    faces = []
    for i in range(data_start, len(lines)):
        line = lines[i].strip()
        if line == ")":
            break
        # Format: N(i0 i1 i2 ... iN-1)
        m = re.match(r"(\d+)\(([^)]*)\)", line)
        if m:
            indices = [int(x) for x in m.group(2).split()]
            faces.append(indices)

    return faces


def _read_openfoam_boundary(filepath: Path) -> dict:
    """
    Read OpenFOAM boundary file → {patchName: {type, nFaces, startFace}}.
    """
    text = filepath.read_text()

    patches = {}
    # Find patch blocks: patchName { type ...; nFaces N; startFace N; }
    pattern = re.compile(
        r"(\w+)\s*\{[^}]*?"
        r"type\s+(\w+)\s*;"
        r"[^}]*?nFaces\s+(\d+)\s*;"
        r"[^}]*?startFace\s+(\d+)\s*;"
        r"[^}]*?\}",
        re.DOTALL,
    )

    for m in pattern.finditer(text):
        name = m.group(1)
        patches[name] = {
            "type": m.group(2),
            "nFaces": int(m.group(3)),
            "startFace": int(m.group(4)),
        }

    return patches
