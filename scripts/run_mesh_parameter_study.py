#!/usr/bin/env python3
"""
Systematic Mesh Parameter Study for Cardiovascular CFD
=======================================================

This script runs multiple mesh configurations to find optimal parameters
for high-quality, robust meshes on cardiovascular geometries.

Test Variables:
1. Quality presets: draft, standard, high_quality
2. maxInternalSkewness: 4, 6, 8, 10
3. nSolveIter: 30, 50, 100
4. nLayerIter: 50, 75, 100
5. featureAngle: 100, 130, 150

Usage:
    python scripts/run_mesh_parameter_study.py
"""

import os
import sys
import json
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
import re

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Configuration
BASE_CONFIG_PATH = PROJECT_ROOT / "cases_input/0014_H_AO_COA/config_mesh_test.json"
OUTPUT_BASE = PROJECT_ROOT / "output/0014_H_AO_COA/mesh_study"
PATIENT_RUNNER = PROJECT_ROOT / "src/patient_runner/cli.py"


def load_base_config():
    """Load the base configuration."""
    with open(BASE_CONFIG_PATH) as f:
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
        "addLayer": "num_layers",  # alias
        "expansionRatio": "expansion_ratio",
        "finalLayerThickness": "final_layer_thickness",
        "minThickness": "min_thickness",
    }

    for key, value in overrides.items():
        if key == "quality_preset":
            config["mesh"]["quality_preset"] = value
        elif key in boundary_layer_keys:
            # Map to boundary_layers section
            bl_key = boundary_layer_keys[key]
            if "boundary_layers" not in config["mesh"]:
                config["mesh"]["boundary_layers"] = {}
            config["mesh"]["boundary_layers"][bl_key] = value
        else:
            # Apply to SNAPPY_SETTINGS
            if "SNAPPY_SETTINGS" not in config["mesh"]:
                config["mesh"]["SNAPPY_SETTINGS"] = {}
            config["mesh"]["SNAPPY_SETTINGS"][key] = value

    return config


def run_mesh_only(config: dict, test_name: str, output_dir: Path) -> dict:
    """Run meshing only (no simulation) and return results."""

    # Create output directory for this test's config
    test_output = output_dir / test_name
    test_output.mkdir(parents=True, exist_ok=True)

    # Write config
    config_path = test_output / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    # Extract patient_id from config
    patient_id = config.get("case_info", {}).get("patient_id", "0014_H_AO_COA")

    # Run patient_runner with case + mesh steps only
    # Use -m to run as module from src directory
    cmd = [
        sys.executable, "-m", "patient_runner.cli",
        patient_id,
        "--config", str(config_path),
        "--steps", "case,mesh"
    ]

    # Set environment
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
            timeout=1800,  # 30 min timeout
            env=env,
            cwd=str(PROJECT_ROOT)
        )

        elapsed = (datetime.now() - start_time).total_seconds()

        # Parse checkMesh results
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
            "elapsed_seconds": 1800,
            "error": "Timeout after 30 minutes"
        }
    except Exception as e:
        return {
            "test_name": test_name,
            "success": False,
            "error": str(e)
        }


def parse_checkmesh_output(test_output: Path, patient_id: str = "0014_H_AO_COA") -> dict:
    """Parse checkMesh log to extract quality metrics."""

    # The patient_runner outputs to output/{patient_id}/run_{timestamp}/
    patient_output = PROJECT_ROOT / "output" / patient_id
    run_dirs = list(patient_output.glob("run_*"))
    if not run_dirs:
        # Also check test_output directly
        run_dirs = list(test_output.glob("run_*"))
    if not run_dirs:
        return {"error": f"No run directory found in {patient_output}"}

    latest_run = max(run_dirs, key=lambda p: p.stat().st_mtime)
    log_path = latest_run / "openfoam/logs/log.checkMesh"

    if not log_path.exists():
        return {"error": f"No checkMesh log found at {log_path}"}

    with open(log_path) as f:
        content = f.read()

    # Note: checkMesh uses default thresholds (skewness=4) regardless of snappyHexMesh settings
    # We consider a mesh "acceptable" if:
    # - No mesh errors (only warnings about high skew faces)
    # - max_skewness < 8 (our relaxed cardiovascular threshold)
    # - non-orthogonality < 65°
    result = {
        "passed": "Mesh OK" in content or "Failed 0 mesh checks" in content,
        "acceptable": False,  # Set based on our thresholds later
        "failed_checks": 0
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
        "polyhedra": r"polyhedra:\s+(\d+)"
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

    return result


def define_test_matrix():
    """Define the test configurations to run.

    Base config: 10 boundary layers, 0.5mm cell size
    Focus on parameters critical for 10-layer boundary mesh quality:
    - nSmoothSurfaceNormals: normal smoothing (critical for layers)
    - nSmoothThickness: thickness smoothing
    - nLayerIter: layer addition iterations
    - featureAngle: layer coverage at bifurcations
    - nRelaxedIter: when to switch to relaxed quality
    - expansionRatio: layer growth rate
    """

    tests = []

    # Test 1: Baseline with 10 layers (current config)
    tests.append({
        "name": "baseline_10layers",
        "overrides": {}
    })

    # Test 2: nSmoothSurfaceNormals sweep (most critical for curved geometry)
    for nsmooth in [15, 20, 30, 50, 75]:
        tests.append({
            "name": f"nSmoothNormals_{nsmooth}",
            "overrides": {
                "nSmoothSurfaceNormals": nsmooth
            }
        })

    # Test 3: nSmoothThickness sweep
    for nsmooth in [10, 15, 20, 30]:
        tests.append({
            "name": f"nSmoothThickness_{nsmooth}",
            "overrides": {
                "nSmoothThickness": nsmooth
            }
        })

    # Test 4: nLayerIter sweep (more iterations = better layer coverage)
    for nlayer in [50, 75, 100, 150]:
        tests.append({
            "name": f"nLayerIter_{nlayer}",
            "overrides": {
                "nLayerIter": nlayer
            }
        })

    # Test 5: featureAngle sweep (layer termination at corners)
    for fangle in [130, 150, 160, 170, 180]:
        tests.append({
            "name": f"featureAngle_{fangle}",
            "overrides": {
                "featureAngle": fangle
            }
        })

    # Test 6: nRelaxedIter sweep (when to switch to relaxed thresholds)
    for nrelax in [10, 20, 30, 50]:
        tests.append({
            "name": f"nRelaxedIter_{nrelax}",
            "overrides": {
                "nRelaxedIter": nrelax
            }
        })

    # Test 7: Expansion ratio sweep
    for ratio in [1.1, 1.15, 1.2, 1.25]:
        tests.append({
            "name": f"expansionRatio_{ratio}",
            "overrides": {
                "expansionRatio": ratio
            }
        })

    # Test 8: Combined candidates for 10-layer mesh
    tests.append({
        "name": "candidate_conservative",
        "overrides": {
            "nSmoothSurfaceNormals": 15,
            "nSmoothThickness": 10,
            "nLayerIter": 50,
            "featureAngle": 160,
            "nRelaxedIter": 20
        }
    })

    tests.append({
        "name": "candidate_balanced",
        "overrides": {
            "nSmoothSurfaceNormals": 30,
            "nSmoothThickness": 20,
            "nLayerIter": 75,
            "featureAngle": 170,
            "nRelaxedIter": 30
        }
    })

    tests.append({
        "name": "candidate_smooth",
        "overrides": {
            "nSmoothSurfaceNormals": 50,
            "nSmoothThickness": 30,
            "nLayerIter": 100,
            "featureAngle": 180,
            "nRelaxedIter": 40
        }
    })

    tests.append({
        "name": "candidate_aggressive",
        "overrides": {
            "nSmoothSurfaceNormals": 75,
            "nSmoothThickness": 40,
            "nLayerIter": 150,
            "featureAngle": 180,
            "nRelaxedIter": 50,
            "maxFaceThicknessRatio": 0.8
        }
    })

    return tests


def run_quick_tests():
    """Run a quick subset of tests - focus on most impactful parameters for 10-layer mesh."""
    tests = [
        # Baseline with 10 layers
        {"name": "quick_baseline", "overrides": {}},
        # Key smoothing tests
        {"name": "quick_smooth_30", "overrides": {"nSmoothSurfaceNormals": 30}},
        {"name": "quick_smooth_50", "overrides": {"nSmoothSurfaceNormals": 50}},
        # More layer iterations
        {"name": "quick_layerIter_100", "overrides": {"nLayerIter": 100}},
        # Combined best guess for 10 layers
        {"name": "quick_optimal", "overrides": {
            "nSmoothSurfaceNormals": 50,
            "nSmoothThickness": 30,
            "nLayerIter": 100,
            "featureAngle": 180,
            "nRelaxedIter": 40
        }},
    ]
    return tests


def print_results_table(results: list):
    """Print results in a formatted table."""

    print("\n" + "="*100)
    print("MESH PARAMETER STUDY RESULTS")
    print("="*100)

    # Header
    print(f"{'Test Name':<30} {'Pass':<6} {'Cells':<10} {'MaxSkew':<10} {'SkewFaces':<10} {'MaxNonOrtho':<12} {'Time(s)':<10}")
    print("-"*100)

    for r in results:
        cm = r.get("checkmesh", {})
        passed = "✓" if cm.get("passed", False) else "✗"
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

        print(f"{r['test_name']:<30} {passed:<6} {str(cells):<10} {str(max_skew):<10} {str(int(skew_faces)):<10} {str(max_ortho):<12} {time_s:.0f}")

    print("="*100)

    # Summary
    passed_tests = [r for r in results if r.get("checkmesh", {}).get("passed", False)]
    print(f"\nPassed: {len(passed_tests)}/{len(results)} tests")

    if passed_tests:
        print("\nBest configurations (by lowest max skewness):")
        sorted_passed = sorted(passed_tests,
                              key=lambda r: r.get("checkmesh", {}).get("max_skewness", 999))
        for i, r in enumerate(sorted_passed[:3], 1):
            cm = r.get("checkmesh", {})
            print(f"  {i}. {r['test_name']}: skew={cm.get('max_skewness', 'N/A'):.2f}, "
                  f"non-ortho={cm.get('max_non_ortho', 'N/A'):.1f}°, "
                  f"time={r.get('elapsed_seconds', 0):.0f}s")


def main():
    """Run the mesh parameter study."""

    import argparse
    parser = argparse.ArgumentParser(description="Run mesh parameter study")
    parser.add_argument("--quick", action="store_true", help="Run quick test subset only")
    parser.add_argument("--test", type=str, help="Run specific test by name")
    args = parser.parse_args()

    # Load base config
    base_config = load_base_config()

    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_BASE / f"study_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Mesh Parameter Study")
    print(f"Output directory: {output_dir}")
    print(f"Base config: {BASE_CONFIG_PATH}")

    # Get test matrix
    if args.quick:
        test_matrix = run_quick_tests()
        print(f"Running QUICK test suite ({len(test_matrix)} tests)")
    elif args.test:
        all_tests = define_test_matrix()
        test_matrix = [t for t in all_tests if args.test in t["name"]]
        if not test_matrix:
            print(f"No tests matching '{args.test}'")
            print(f"Available tests: {[t['name'] for t in all_tests]}")
            return
    else:
        test_matrix = define_test_matrix()
        print(f"Running FULL test suite ({len(test_matrix)} tests)")

    # Run tests
    results = []
    for i, test in enumerate(test_matrix, 1):
        print(f"\n[{i}/{len(test_matrix)}] Preparing test: {test['name']}")

        config = create_test_config(base_config, test["name"], test["overrides"])
        result = run_mesh_only(config, test["name"], output_dir)
        results.append(result)

        # Print immediate feedback
        cm = result.get("checkmesh", {})
        if cm.get("passed"):
            print(f"  ✓ PASSED - Cells: {cm.get('cells', 'N/A')}, MaxSkew: {cm.get('max_skewness', 'N/A')}")
        else:
            print(f"  ✗ FAILED - {cm.get('failed_checks', 0)} checks failed, MaxSkew: {cm.get('max_skewness', 'N/A')}")

    # Save results
    results_path = output_dir / "results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    # Print summary table
    print_results_table(results)

    print(f"\nResults saved to: {results_path}")


if __name__ == "__main__":
    main()
