#!/usr/bin/env python3
"""
Comprehensive Mesh Parameter Study for Cardiovascular CFD
==========================================================

This script runs systematic parameter sweeps covering ALL key snappyHexMesh
parameters, including span refinement. Use this to validate and optimize
mesh presets for different geometry types.

Test Categories:
================
1. CASTELLATED MESH CONTROLS
   - nCellsBetweenLevels: refinement transition smoothness
   - surfaceRefinementLevels: min/max refinement levels
   - resolveFeatureAngle: feature detection threshold

2. SNAP CONTROLS
   - snapTolerance: attraction distance multiplier
   - nSolveIter: mesh displacement iterations
   - nFeatureSnapIter: feature edge snapping iterations
   - nSmoothPatch: pre-snap surface smoothing

3. ADD LAYERS CONTROLS
   - num_layers: boundary layer count
   - expansionRatio: layer growth rate
   - nSmoothSurfaceNormals: patch normal smoothing (CRITICAL)
   - nSmoothThickness: thickness distribution smoothing
   - nLayerIter: layer addition iterations
   - featureAngle: layer termination angle
   - maxFaceThicknessRatio: layer coverage in tight regions

4. MESH QUALITY CONTROLS
   - maxNonOrtho: non-orthogonality threshold
   - maxInternalSkewness: skewness threshold

5. SPAN REFINEMENT (NEW)
   - span_refinement_enabled: enable/disable
   - cells_across_span: span resolution
   - span_refinement_level: refinement level in span region

Usage:
======
    # Run all tests (comprehensive - takes hours)
    python scripts/run_mesh_parameter_study_comprehensive.py

    # Run quick validation (5 key tests)
    python scripts/run_mesh_parameter_study_comprehensive.py --quick

    # Run specific category
    python scripts/run_mesh_parameter_study_comprehensive.py --category castellated
    python scripts/run_mesh_parameter_study_comprehensive.py --category snap
    python scripts/run_mesh_parameter_study_comprehensive.py --category layers
    python scripts/run_mesh_parameter_study_comprehensive.py --category quality
    python scripts/run_mesh_parameter_study_comprehensive.py --category span

    # Run specific test by name
    python scripts/run_mesh_parameter_study_comprehensive.py --test nSmoothNormals_30

    # Dry run (list tests without running)
    python scripts/run_mesh_parameter_study_comprehensive.py --dry-run

    # Use span-enabled base config
    python scripts/run_mesh_parameter_study_comprehensive.py --with-span
"""

import os
import sys
import json
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
import re
import argparse
from typing import Dict, List, Any, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Configuration paths
BASE_CONFIG_NO_SPAN = PROJECT_ROOT / "cases_input/0014_H_AO_COA/config_mesh_test.json"
BASE_CONFIG_WITH_SPAN = PROJECT_ROOT / "cases_input/0014_H_AO_COA/config_mesh_span15.json"
OUTPUT_BASE = PROJECT_ROOT / "output/0014_H_AO_COA/mesh_study_comprehensive"


# =============================================================================
# TEST MATRIX DEFINITIONS
# =============================================================================

def get_castellated_tests() -> List[Dict[str, Any]]:
    """Castellated mesh control parameter tests."""
    tests = []

    # nCellsBetweenLevels: refinement transition smoothness
    # Lower = faster but less smooth, Higher = smoother but more cells
    for n in [2, 3, 4, 5]:
        tests.append({
            "name": f"cast_nCellsBetween_{n}",
            "category": "castellated",
            "description": f"Refinement transition: {n} cells between levels",
            "overrides": {"nCellsBetweenLevels": n}
        })

    # surfaceRefinementLevels: [min, max] refinement on surfaces
    for levels in [[1, 1], [1, 2], [2, 2], [2, 3], [1, 3]]:
        name = f"cast_surfRef_{levels[0]}_{levels[1]}"
        tests.append({
            "name": name,
            "category": "castellated",
            "description": f"Surface refinement levels: {levels}",
            "overrides": {"surfaceRefinementLevels": levels}
        })

    # resolveFeatureAngle: threshold for feature detection
    for angle in [20, 30, 45, 60]:
        tests.append({
            "name": f"cast_featureAngle_{angle}",
            "category": "castellated",
            "description": f"Feature detection angle: {angle}°",
            "overrides": {"resolveFeatureAngle": angle}
        })

    return tests


def get_snap_tests() -> List[Dict[str, Any]]:
    """Snap control parameter tests."""
    tests = []

    # snapTolerance: attraction distance multiplier
    # Higher = more aggressive snapping, but can cause quality issues
    for tol in [0.5, 1.0, 1.5, 2.0, 3.0]:
        tests.append({
            "name": f"snap_tolerance_{tol}",
            "category": "snap",
            "description": f"Snap tolerance: {tol}",
            "overrides": {"snapTolerance": tol}
        })

    # nSolveIter: mesh displacement iterations
    # More iterations = better conformity but slower
    for n in [5, 10, 20, 30, 50]:
        tests.append({
            "name": f"snap_nSolveIter_{n}",
            "category": "snap",
            "description": f"Displacement iterations: {n}",
            "overrides": {"nSolveIter": n}
        })

    # nFeatureSnapIter: feature edge snapping
    for n in [3, 5, 10, 15]:
        tests.append({
            "name": f"snap_nFeatureSnapIter_{n}",
            "category": "snap",
            "description": f"Feature snap iterations: {n}",
            "overrides": {"nFeatureSnapIter": n}
        })

    # nSmoothPatch: pre-snap surface smoothing
    for n in [1, 3, 5, 10]:
        tests.append({
            "name": f"snap_nSmoothPatch_{n}",
            "category": "snap",
            "description": f"Pre-snap smoothing: {n}",
            "overrides": {"nSmoothPatch": n}
        })

    # nRelaxIter: relaxation iterations
    for n in [3, 5, 8, 10]:
        tests.append({
            "name": f"snap_nRelaxIter_{n}",
            "category": "snap",
            "description": f"Snap relaxation iterations: {n}",
            "overrides": {"nRelaxIter": n}
        })

    return tests


def get_layer_tests() -> List[Dict[str, Any]]:
    """Boundary layer parameter tests."""
    tests = []

    # num_layers: boundary layer count (critical for y+)
    for n in [3, 5, 7, 10, 12, 15]:
        tests.append({
            "name": f"layer_numLayers_{n}",
            "category": "layers",
            "description": f"Boundary layers: {n}",
            "overrides": {"num_layers": n}
        })

    # expansionRatio: layer growth rate
    # Lower = more uniform, Higher = faster growth
    for ratio in [1.05, 1.1, 1.15, 1.2, 1.25, 1.3]:
        tests.append({
            "name": f"layer_expansion_{ratio}",
            "category": "layers",
            "description": f"Expansion ratio: {ratio}",
            "overrides": {"expansionRatio": ratio}
        })

    # nSmoothSurfaceNormals: MOST CRITICAL for curved geometry
    for n in [5, 10, 15, 20, 30, 50, 75, 100]:
        tests.append({
            "name": f"layer_nSmoothNormals_{n}",
            "category": "layers",
            "description": f"Surface normal smoothing: {n}",
            "overrides": {"nSmoothSurfaceNormals": n}
        })

    # nSmoothThickness: thickness distribution smoothing
    for n in [5, 10, 15, 20, 30]:
        tests.append({
            "name": f"layer_nSmoothThickness_{n}",
            "category": "layers",
            "description": f"Thickness smoothing: {n}",
            "overrides": {"nSmoothThickness": n}
        })

    # nLayerIter: layer addition iterations
    for n in [30, 50, 75, 100, 150]:
        tests.append({
            "name": f"layer_nLayerIter_{n}",
            "category": "layers",
            "description": f"Layer iterations: {n}",
            "overrides": {"nLayerIter": n}
        })

    # featureAngle: layer termination angle
    for angle in [100, 130, 150, 160, 170, 180]:
        tests.append({
            "name": f"layer_featureAngle_{angle}",
            "category": "layers",
            "description": f"Layer feature angle: {angle}°",
            "overrides": {"featureAngle": angle}
        })

    # nRelaxedIter: when to switch to relaxed thresholds
    for n in [10, 20, 30, 40, 50]:
        tests.append({
            "name": f"layer_nRelaxedIter_{n}",
            "category": "layers",
            "description": f"Relaxed iterations: {n}",
            "overrides": {"nRelaxedIter": n}
        })

    # maxFaceThicknessRatio: layer coverage in tight regions
    for ratio in [0.3, 0.5, 0.6, 0.7, 0.8]:
        tests.append({
            "name": f"layer_maxFaceThickRatio_{ratio}",
            "category": "layers",
            "description": f"Max face thickness ratio: {ratio}",
            "overrides": {"maxFaceThicknessRatio": ratio}
        })

    # finalLayerThickness: last layer as fraction of cell size
    for thick in [0.2, 0.3, 0.4, 0.5]:
        tests.append({
            "name": f"layer_finalThickness_{thick}",
            "category": "layers",
            "description": f"Final layer thickness: {thick}",
            "overrides": {"finalLayerThickness": thick}
        })

    return tests


def get_quality_tests() -> List[Dict[str, Any]]:
    """Mesh quality threshold tests."""
    tests = []

    # maxNonOrtho: non-orthogonality threshold
    for angle in [55, 60, 65, 70, 75]:
        tests.append({
            "name": f"qual_maxNonOrtho_{angle}",
            "category": "quality",
            "description": f"Max non-orthogonality: {angle}°",
            "overrides": {"maxNonOrtho": angle}
        })

    # maxInternalSkewness: skewness threshold
    for skew in [4, 5, 6, 8, 10]:
        tests.append({
            "name": f"qual_maxSkewness_{skew}",
            "category": "quality",
            "description": f"Max internal skewness: {skew}",
            "overrides": {"maxInternalSkewness": skew}
        })

    # maxBoundarySkewness: boundary skewness threshold
    for skew in [10, 15, 20, 25]:
        tests.append({
            "name": f"qual_maxBoundSkew_{skew}",
            "category": "quality",
            "description": f"Max boundary skewness: {skew}",
            "overrides": {"maxBoundarySkewness": skew}
        })

    return tests


def get_span_tests() -> List[Dict[str, Any]]:
    """Span refinement parameter tests."""
    tests = []

    # Baseline: no span refinement
    tests.append({
        "name": "span_disabled",
        "category": "span",
        "description": "Span refinement disabled",
        "overrides": {"span_refinement_enabled": False}
    })

    # cells_across_span: span resolution
    for cells in [10, 15, 20, 25, 30]:
        tests.append({
            "name": f"span_cells_{cells}",
            "category": "span",
            "description": f"Span: {cells} cells across",
            "overrides": {
                "span_refinement_enabled": True,
                "cells_across_span": cells,
                "span_refinement_level": 3
            }
        })

    # span_refinement_level: refinement level in span region
    for level in [2, 3, 4]:
        tests.append({
            "name": f"span_level_{level}",
            "category": "span",
            "description": f"Span refinement level: {level}",
            "overrides": {
                "span_refinement_enabled": True,
                "cells_across_span": 15,
                "span_refinement_level": level
            }
        })

    # Combined span + smoothing tests (critical interaction)
    for nsmooth in [20, 30, 50]:
        tests.append({
            "name": f"span_smooth_{nsmooth}",
            "category": "span",
            "description": f"Span enabled + nSmoothNormals={nsmooth}",
            "overrides": {
                "span_refinement_enabled": True,
                "cells_across_span": 15,
                "span_refinement_level": 3,
                "nSmoothSurfaceNormals": nsmooth
            }
        })

    return tests


def get_combined_candidate_tests() -> List[Dict[str, Any]]:
    """Combined candidate configurations based on study insights."""
    tests = []

    # Candidate 1: Conservative (fast, robust)
    tests.append({
        "name": "candidate_conservative",
        "category": "combined",
        "description": "Conservative: fast, robust baseline",
        "overrides": {
            "nSmoothSurfaceNormals": 15,
            "nSmoothThickness": 10,
            "nLayerIter": 50,
            "featureAngle": 160,
            "snapTolerance": 1.0,
            "nSolveIter": 10
        }
    })

    # Candidate 2: Standard (validated 31/31 pass)
    tests.append({
        "name": "candidate_standard",
        "category": "combined",
        "description": "Standard: validated 31/31 pass",
        "overrides": {
            "nSmoothSurfaceNormals": 20,
            "nSmoothThickness": 15,
            "nLayerIter": 50,
            "featureAngle": 170,
            "snapTolerance": 1.0,
            "nSolveIter": 10,
            "maxFaceThicknessRatio": 0.6
        }
    })

    # Candidate 3: High quality (best skewness from study)
    tests.append({
        "name": "candidate_high_quality",
        "category": "combined",
        "description": "High quality: best skewness",
        "overrides": {
            "nSmoothSurfaceNormals": 50,
            "nSmoothThickness": 30,
            "nLayerIter": 100,
            "featureAngle": 180,
            "nRelaxedIter": 40,
            "snapTolerance": 1.0,
            "nSolveIter": 10,
            "maxFaceThicknessRatio": 0.8
        }
    })

    # Candidate 4: Publication (strictest thresholds)
    tests.append({
        "name": "candidate_publication",
        "category": "combined",
        "description": "Publication: strict thresholds",
        "overrides": {
            "nSmoothSurfaceNormals": 50,
            "nSmoothThickness": 30,
            "nLayerIter": 100,
            "featureAngle": 180,
            "nRelaxedIter": 40,
            "nCellsBetweenLevels": 4,
            "maxNonOrtho": 60,
            "maxInternalSkewness": 5,
            "snapTolerance": 1.0,
            "nSolveIter": 10
        }
    })

    # Candidate 5: Span-optimized (for span refinement cases)
    tests.append({
        "name": "candidate_span_optimized",
        "category": "combined",
        "description": "Span-optimized: for span refinement",
        "overrides": {
            "span_refinement_enabled": True,
            "cells_across_span": 20,
            "span_refinement_level": 3,
            "nSmoothSurfaceNormals": 50,
            "nSmoothThickness": 30,
            "nLayerIter": 100,
            "featureAngle": 180,
            "snapTolerance": 1.0,
            "nSolveIter": 10,
            "nCellsBetweenLevels": 4
        }
    })

    return tests


def get_quick_tests() -> List[Dict[str, Any]]:
    """Quick validation tests - 5 key tests covering each category."""
    return [
        {
            "name": "quick_baseline",
            "category": "quick",
            "description": "Baseline (no changes)",
            "overrides": {}
        },
        {
            "name": "quick_smooth_low",
            "category": "quick",
            "description": "Low smoothing (fast)",
            "overrides": {"nSmoothSurfaceNormals": 10}
        },
        {
            "name": "quick_smooth_high",
            "category": "quick",
            "description": "High smoothing (quality)",
            "overrides": {"nSmoothSurfaceNormals": 50}
        },
        {
            "name": "quick_span_enabled",
            "category": "quick",
            "description": "Span refinement enabled",
            "overrides": {
                "span_refinement_enabled": True,
                "cells_across_span": 15,
                "span_refinement_level": 3
            }
        },
        {
            "name": "quick_standard_preset",
            "category": "quick",
            "description": "Standard preset parameters",
            "overrides": {
                "nSmoothSurfaceNormals": 20,
                "nSmoothThickness": 15,
                "featureAngle": 170,
                "snapTolerance": 1.0,
                "nSolveIter": 10
            }
        }
    ]


def get_all_tests() -> List[Dict[str, Any]]:
    """Get all test configurations."""
    all_tests = []
    all_tests.extend(get_castellated_tests())
    all_tests.extend(get_snap_tests())
    all_tests.extend(get_layer_tests())
    all_tests.extend(get_quality_tests())
    all_tests.extend(get_span_tests())
    all_tests.extend(get_combined_candidate_tests())
    return all_tests


# =============================================================================
# TEST EXECUTION
# =============================================================================

def load_base_config(with_span: bool = False) -> dict:
    """Load the base configuration."""
    config_path = BASE_CONFIG_WITH_SPAN if with_span else BASE_CONFIG_NO_SPAN
    if not config_path.exists():
        raise FileNotFoundError(f"Base config not found: {config_path}")
    with open(config_path) as f:
        return json.load(f)


def create_test_config(base_config: dict, test_name: str, overrides: dict) -> dict:
    """Create a test configuration with specific overrides."""
    config = json.loads(json.dumps(base_config))  # Deep copy

    # Update mesh study label
    config["_mesh_study"] = test_name

    # Special keys that map to boundary_layers section
    boundary_layer_keys = {
        "addLayers": "enabled",
        "num_layers": "num_layers",
        "addLayer": "num_layers",
        "expansionRatio": "expansion_ratio",
        "finalLayerThickness": "final_layer_thickness",
        "minThickness": "min_thickness",
    }

    # Special keys that map to mesh_resolution section
    mesh_resolution_keys = {
        "target_cell_size_mm": "target_cell_size_mm",
        "cells_across_span": "cells_across_span",
    }

    for key, value in overrides.items():
        if key == "quality_preset":
            config["mesh"]["quality_preset"] = value
        elif key in boundary_layer_keys:
            bl_key = boundary_layer_keys[key]
            if "boundary_layers" not in config["mesh"]:
                config["mesh"]["boundary_layers"] = {}
            config["mesh"]["boundary_layers"][bl_key] = value
        elif key in mesh_resolution_keys:
            res_key = mesh_resolution_keys[key]
            if "mesh_resolution" not in config["mesh"]:
                config["mesh"]["mesh_resolution"] = {}
            config["mesh"]["mesh_resolution"][res_key] = value
        else:
            # Apply to SNAPPY_SETTINGS
            if "SNAPPY_SETTINGS" not in config["mesh"]:
                config["mesh"]["SNAPPY_SETTINGS"] = {}
            config["mesh"]["SNAPPY_SETTINGS"][key] = value

    return config


def run_mesh_only(config: dict, test_name: str, output_dir: Path) -> dict:
    """Run meshing only (no simulation) and return results."""
    test_output = output_dir / test_name
    test_output.mkdir(parents=True, exist_ok=True)

    # Write config
    config_path = test_output / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    patient_id = config.get("case_info", {}).get("patient_id", "0014_H_AO_COA")

    cmd = [
        sys.executable, "-m", "patient_runner.cli",
        patient_id,
        "--config", str(config_path),
        "--steps", "case,mesh"
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")

    print(f"\n{'='*70}")
    print(f"Running test: {test_name}")
    print(f"{'='*70}")

    start_time = datetime.now()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=2400,  # 40 min timeout for complex meshes
            env=env,
            cwd=str(PROJECT_ROOT)
        )

        elapsed = (datetime.now() - start_time).total_seconds()
        check_mesh_result = parse_checkmesh_output(test_output, patient_id)

        return {
            "test_name": test_name,
            "success": result.returncode == 0,
            "elapsed_seconds": elapsed,
            "returncode": result.returncode,
            "checkmesh": check_mesh_result,
            "stdout_tail": result.stdout[-2000:] if result.stdout else "",
            "stderr_tail": result.stderr[-1000:] if result.stderr else ""
        }

    except subprocess.TimeoutExpired:
        return {
            "test_name": test_name,
            "success": False,
            "elapsed_seconds": 2400,
            "error": "Timeout after 40 minutes"
        }
    except Exception as e:
        return {
            "test_name": test_name,
            "success": False,
            "error": str(e)
        }


def parse_checkmesh_output(test_output: Path, patient_id: str = "0014_H_AO_COA") -> dict:
    """Parse checkMesh log to extract quality metrics."""
    patient_output = PROJECT_ROOT / "output" / patient_id
    run_dirs = list(patient_output.glob("run_*"))
    if not run_dirs:
        run_dirs = list(test_output.glob("run_*"))
    if not run_dirs:
        return {"error": f"No run directory found in {patient_output}"}

    latest_run = max(run_dirs, key=lambda p: p.stat().st_mtime)
    log_path = latest_run / "openfoam/logs/log.checkMesh"

    if not log_path.exists():
        return {"error": f"No checkMesh log found at {log_path}"}

    with open(log_path) as f:
        content = f.read()

    result = {
        "passed": "Mesh OK" in content or "Failed 0 mesh checks" in content,
        "acceptable": False,
        "failed_checks": 0,
        "run_dir": str(latest_run)
    }

    # Extract metrics
    patterns = {
        "cells": r"cells:\s+(\d+)",
        "max_non_ortho": r"Mesh non-orthogonality Max:\s+([\d.]+)",
        "avg_non_ortho": r"average:\s+([\d.]+)",
        "max_skewness": r"Max skewness = ([\d.]+)",
        "skew_faces": r"(\d+) highly skew faces",
        "max_aspect_ratio": r"Max aspect ratio = ([\d.]+)",
        "hexahedra": r"hexahedra:\s+(\d+)",
        "polyhedra": r"polyhedra:\s+(\d+)",
        "prisms": r"prisms:\s+(\d+)",
        "pyramids": r"pyramids:\s+(\d+)"
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, content)
        if match:
            try:
                result[key] = float(match.group(1))
            except ValueError:
                result[key] = match.group(1)

    # Count failed checks
    failed_match = re.search(r"Failed (\d+) mesh checks", content)
    if failed_match:
        result["failed_checks"] = int(failed_match.group(1))

    # Set acceptable based on cardiovascular thresholds
    max_skew = result.get("max_skewness", 999)
    max_ortho = result.get("max_non_ortho", 999)
    if isinstance(max_skew, (int, float)) and isinstance(max_ortho, (int, float)):
        result["acceptable"] = max_skew < 8 and max_ortho < 75

    return result


# =============================================================================
# RESULTS DISPLAY
# =============================================================================

def print_results_table(results: list, category: Optional[str] = None):
    """Print results in a formatted table."""
    if category:
        results = [r for r in results if r.get("category") == category]

    print("\n" + "="*120)
    print("COMPREHENSIVE MESH PARAMETER STUDY RESULTS")
    if category:
        print(f"Category: {category.upper()}")
    print("="*120)

    # Header
    header = f"{'Test Name':<35} {'Pass':<6} {'Cells':<12} {'MaxSkew':<10} {'SkewFaces':<10} {'MaxOrtho':<10} {'Time(s)':<8}"
    print(header)
    print("-"*120)

    for r in results:
        cm = r.get("checkmesh", {})
        passed = "✓" if cm.get("passed", False) else "✗"
        acceptable = "(ok)" if cm.get("acceptable", False) else ""
        cells = cm.get("cells", "N/A")
        max_skew = cm.get("max_skewness", "N/A")
        skew_faces = cm.get("skew_faces", 0)
        max_ortho = cm.get("max_non_ortho", "N/A")
        time_s = r.get("elapsed_seconds", 0)

        if isinstance(cells, float):
            cells = f"{int(cells):,}"
        if isinstance(max_skew, float):
            max_skew = f"{max_skew:.2f}"
        if isinstance(max_ortho, float):
            max_ortho = f"{max_ortho:.1f}°"

        print(f"{r['test_name']:<35} {passed+acceptable:<6} {str(cells):<12} {str(max_skew):<10} {str(int(skew_faces)):<10} {str(max_ortho):<10} {time_s:.0f}")

    print("="*120)

    # Summary
    passed_tests = [r for r in results if r.get("checkmesh", {}).get("passed", False)]
    acceptable_tests = [r for r in results if r.get("checkmesh", {}).get("acceptable", False)]
    print(f"\nPassed checkMesh: {len(passed_tests)}/{len(results)}")
    print(f"Acceptable (skew<8, ortho<75°): {len(acceptable_tests)}/{len(results)}")

    if passed_tests:
        print("\nTop 5 configurations (by lowest max skewness):")
        sorted_passed = sorted(passed_tests,
                              key=lambda r: r.get("checkmesh", {}).get("max_skewness", 999))
        for i, r in enumerate(sorted_passed[:5], 1):
            cm = r.get("checkmesh", {})
            skew = cm.get('max_skewness', 'N/A')
            ortho = cm.get('max_non_ortho', 'N/A')
            skew_str = f"{skew:.3f}" if isinstance(skew, float) else skew
            ortho_str = f"{ortho:.1f}°" if isinstance(ortho, float) else ortho
            print(f"  {i}. {r['test_name']}: skew={skew_str}, ortho={ortho_str}")


def generate_summary_report(results: list, output_dir: Path):
    """Generate a markdown summary report."""
    report_path = output_dir / "SUMMARY_REPORT.md"

    # Group by category
    categories = {}
    for r in results:
        cat = r.get("category", "unknown")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)

    with open(report_path, "w") as f:
        f.write("# Comprehensive Mesh Parameter Study Report\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Overall summary
        passed = sum(1 for r in results if r.get("checkmesh", {}).get("passed", False))
        acceptable = sum(1 for r in results if r.get("checkmesh", {}).get("acceptable", False))
        f.write(f"## Overall Summary\n\n")
        f.write(f"- **Total tests:** {len(results)}\n")
        f.write(f"- **Passed checkMesh:** {passed}/{len(results)} ({100*passed/len(results):.1f}%)\n")
        f.write(f"- **Acceptable (skew<8):** {acceptable}/{len(results)} ({100*acceptable/len(results):.1f}%)\n\n")

        # Per-category summary
        f.write("## Results by Category\n\n")
        for cat, cat_results in categories.items():
            passed_cat = sum(1 for r in cat_results if r.get("checkmesh", {}).get("passed", False))
            f.write(f"### {cat.upper()}\n\n")
            f.write(f"Passed: {passed_cat}/{len(cat_results)}\n\n")

            f.write("| Test | Pass | Cells | MaxSkew | MaxOrtho | Time(s) |\n")
            f.write("|------|------|-------|---------|----------|--------|\n")

            for r in cat_results:
                cm = r.get("checkmesh", {})
                status = "✓" if cm.get("passed", False) else "✗"
                cells = int(cm.get("cells", 0)) if cm.get("cells") else "N/A"
                skew = cm.get("max_skewness", "N/A")
                ortho = cm.get("max_non_ortho", "N/A")
                time_s = r.get("elapsed_seconds", 0)

                skew_str = f"{skew:.2f}" if isinstance(skew, float) else skew
                ortho_str = f"{ortho:.1f}" if isinstance(ortho, float) else ortho

                f.write(f"| {r['test_name']} | {status} | {cells:,} | {skew_str} | {ortho_str} | {time_s:.0f} |\n")

            f.write("\n")

        # Best configurations
        passed_tests = [r for r in results if r.get("checkmesh", {}).get("passed", False)]
        if passed_tests:
            f.write("## Best Configurations\n\n")
            sorted_passed = sorted(passed_tests,
                                  key=lambda r: r.get("checkmesh", {}).get("max_skewness", 999))
            f.write("### Top 10 by Lowest Skewness\n\n")
            for i, r in enumerate(sorted_passed[:10], 1):
                cm = r.get("checkmesh", {})
                f.write(f"{i}. **{r['test_name']}**: skew={cm.get('max_skewness', 'N/A'):.3f}, "
                       f"ortho={cm.get('max_non_ortho', 'N/A'):.1f}°\n")

    print(f"\nSummary report saved to: {report_path}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Comprehensive mesh parameter study for cardiovascular CFD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Categories:
  castellated  - Castellated mesh controls (nCellsBetweenLevels, refinement)
  snap         - Snap controls (snapTolerance, nSolveIter, etc.)
  layers       - Boundary layer controls (num_layers, smoothing, etc.)
  quality      - Mesh quality thresholds (maxNonOrtho, maxSkewness)
  span         - Span refinement parameters
  combined     - Combined candidate configurations

Examples:
  python run_mesh_parameter_study_comprehensive.py --quick
  python run_mesh_parameter_study_comprehensive.py --category layers
  python run_mesh_parameter_study_comprehensive.py --test nSmoothNormals
  python run_mesh_parameter_study_comprehensive.py --dry-run
        """
    )
    parser.add_argument("--quick", action="store_true",
                       help="Run quick validation (5 tests)")
    parser.add_argument("--category", type=str,
                       choices=["castellated", "snap", "layers", "quality", "span", "combined"],
                       help="Run specific category only")
    parser.add_argument("--test", type=str,
                       help="Run specific test by name (partial match)")
    parser.add_argument("--with-span", action="store_true",
                       help="Use span-enabled base config")
    parser.add_argument("--dry-run", action="store_true",
                       help="List tests without running")
    parser.add_argument("--cores", type=int, default=12,
                       help="Number of cores for meshing (default: 12)")
    args = parser.parse_args()

    # Load base config
    try:
        base_config = load_base_config(with_span=args.with_span)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    # Override processor count
    if "mesh" in base_config and "SNAPPY_SETTINGS" in base_config["mesh"]:
        base_config["mesh"]["SNAPPY_SETTINGS"]["nProcessors"] = args.cores

    # Get test matrix
    if args.quick:
        test_matrix = get_quick_tests()
        study_name = "quick"
    elif args.category:
        category_funcs = {
            "castellated": get_castellated_tests,
            "snap": get_snap_tests,
            "layers": get_layer_tests,
            "quality": get_quality_tests,
            "span": get_span_tests,
            "combined": get_combined_candidate_tests
        }
        test_matrix = category_funcs[args.category]()
        study_name = args.category
    elif args.test:
        all_tests = get_all_tests()
        test_matrix = [t for t in all_tests if args.test.lower() in t["name"].lower()]
        if not test_matrix:
            print(f"No tests matching '{args.test}'")
            print(f"\nAvailable tests ({len(all_tests)}):")
            for t in all_tests[:20]:
                print(f"  - {t['name']}")
            if len(all_tests) > 20:
                print(f"  ... and {len(all_tests) - 20} more")
            return 1
        study_name = f"filter_{args.test}"
    else:
        test_matrix = get_all_tests()
        study_name = "full"

    # Add category to each test for reporting
    for test in test_matrix:
        if "category" not in test:
            test["category"] = "unknown"

    # Dry run - just list tests
    if args.dry_run:
        print(f"\nTest Matrix ({len(test_matrix)} tests):")
        print("-" * 70)
        by_category = {}
        for t in test_matrix:
            cat = t.get("category", "unknown")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(t)

        for cat, tests in sorted(by_category.items()):
            print(f"\n{cat.upper()} ({len(tests)} tests):")
            for t in tests:
                print(f"  - {t['name']}: {t.get('description', '')}")
        return 0

    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_BASE / f"study_{study_name}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nComprehensive Mesh Parameter Study")
    print(f"=" * 70)
    print(f"Study type: {study_name}")
    print(f"Tests to run: {len(test_matrix)}")
    print(f"Output directory: {output_dir}")
    print(f"Base config: {'with span' if args.with_span else 'no span'}")
    print(f"Cores: {args.cores}")

    # Run tests
    results = []
    for i, test in enumerate(test_matrix, 1):
        print(f"\n[{i}/{len(test_matrix)}] {test['name']}")
        print(f"    {test.get('description', '')}")

        config = create_test_config(base_config, test["name"], test["overrides"])
        result = run_mesh_only(config, test["name"], output_dir)
        result["category"] = test.get("category", "unknown")
        result["description"] = test.get("description", "")
        results.append(result)

        # Print immediate feedback
        cm = result.get("checkmesh", {})
        if cm.get("passed"):
            print(f"    ✓ PASSED - Cells: {cm.get('cells', 'N/A'):,.0f}, "
                  f"Skew: {cm.get('max_skewness', 'N/A'):.2f}")
        elif cm.get("acceptable"):
            print(f"    ~ ACCEPTABLE - Cells: {cm.get('cells', 'N/A'):,.0f}, "
                  f"Skew: {cm.get('max_skewness', 'N/A'):.2f}")
        else:
            skew = cm.get('max_skewness', 'N/A')
            skew_str = f"{skew:.2f}" if isinstance(skew, (int, float)) else skew
            print(f"    ✗ FAILED - {cm.get('failed_checks', 0)} checks, Skew: {skew_str}")

    # Save results
    results_path = output_dir / "results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    # Print summary
    print_results_table(results)

    # Generate report
    generate_summary_report(results, output_dir)

    print(f"\nResults saved to: {results_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
