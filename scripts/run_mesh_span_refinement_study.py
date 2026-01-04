#!/usr/bin/env python3
"""
Span Refinement Study for snappyHexMesh
=======================================

Focused study to find working span refinement parameters for cardiovascular CFD.

Background:
-----------
Previous DOE study (22 tests) showed span refinement causes catastrophic mesh failure:
  - val_span_standard: skew = 59.14, ortho = 164°  (FAILED)
  - val_span_high_smooth: skew = 4.17, ortho = 122° (FAILED)

This study aims to find working span refinement configurations by:
1. Starting with very conservative parameters (cells_across_span=5)
2. Gradually increasing complexity
3. Testing interaction with proven DOE parameters

Strategy:
---------
Phase 1: Baseline - Find minimal working span config (cells_across_span=5-10)
Phase 2: Scaling - Test higher cell counts (12, 15, 20)
Phase 3: Optimization - Test span_refinement_level and smoothing interaction

Key Parameters:
- span_refinement_enabled: true/false
- cells_across_span: 5, 8, 10, 12, 15, 20
- span_refinement_level: 1, 2, 3 (auto-calculated if not set)
- nSmoothSurfaceNormals: 20, 50 (proven DOE values)
- nSmoothThickness: 10 (DOE: lower is better)

Test Case: 0014_H_AO_COA (Pediatric Aortic Coarctation)

Usage:
    python scripts/run_mesh_span_refinement_study.py [--phase 1|2|3|all]
"""

import json
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# =============================================================================
# STUDY CONFIGURATION
# =============================================================================

# Test case
CASE_ID = "0014_H_AO_COA"
INPUT_DIR = Path(__file__).parent.parent / "cases_input" / CASE_ID
OUTPUT_BASE = Path(__file__).parent.parent / "output" / CASE_ID / "span_study"

# Base config template (minimal - mesh only)
BASE_CONFIG = {
    "_study": "Span refinement study",
    "case_info": {
        "patient_id": CASE_ID,
        "description": "Span refinement parameter study"
    },
    "physics": {
        "model": "laminar",  # Simple for mesh study
        "transport_properties": {
            "rho": 1060,
            "nu": 3.7735849056603773e-06
        }
    },
    "numerics": {
        "profile": "standard"
    },
    "mesh": {
        "boundary_layers": {
            "enabled": True,
            "num_layers": 10,
            "expansion_ratio": 1.2,
            "final_layer_thickness": 0.3,
            "min_thickness": 0.05,
            "relativeSizes": True
        },
        "SNAPPY_SETTINGS": {
            "parallel": True,
            "nProcessors": 12,
            "surfaceRefinementLevels": [1, 2],
            "featureLevel": 2,
            # Proven DOE parameters
            "snapTolerance": 1.0,
            "nSolveIter": 10,
            "nFeatureSnapIter": 5,
            "nSmoothThickness": 10,  # DOE: lower is better
            "maxFaceThicknessRatio": 0.5,  # DOE: lower is better
            "featureAngle": 170,
            "nLayerIter": 50,
        }
    },
    "geometry": {
        "inlet_keywords_ordered": "inlet",
        "outlet_keywords_ordered": ["outlet1", "outlet2", "outlet3", "outlet4", "outlet5"],
        "wall_keywords_ordered": "wall_aorta",
        "scale_factor": 0.01
    },
    "boundary_conditions": {
        "inlet": {"type": "CONSTANT", "velocity": 0.5},
        "outlets": {"type": "ZEROGRADIENT"},
        "walls": {"type": "no_slip"}
    },
    "simulation_control": {
        "cardiac_cycle_period": 1.0,
        "number_of_cycles": 1
    },
    "run_settings": {
        "solution_type": "parallel",
        "subdomains": 4,
        "decomposition_method": "scotch"
    }
}

# =============================================================================
# TEST DEFINITIONS
# =============================================================================

def get_phase1_tests() -> List[Dict[str, Any]]:
    """
    Phase 1: Baseline - Find minimal working span configuration.

    Start very conservative with cells_across_span=5 and work up.
    Use proven DOE smoothing parameters.
    """
    tests = []

    # Test 1.1-1.3: Very coarse span (5 cells) with different span levels
    for span_level in [1, 2, 3]:
        tests.append({
            "name": f"span5_level{span_level}",
            "description": f"cells_across_span=5, span_refinement_level={span_level}",
            "snappy_overrides": {
                "span_refinement_enabled": True,
                "cells_across_span": 5,
                "span_refinement_level": span_level,
                "nSmoothSurfaceNormals": 20,
            }
        })

    # Test 1.4-1.6: Slightly more cells (8) with different span levels
    for span_level in [1, 2, 3]:
        tests.append({
            "name": f"span8_level{span_level}",
            "description": f"cells_across_span=8, span_refinement_level={span_level}",
            "snappy_overrides": {
                "span_refinement_enabled": True,
                "cells_across_span": 8,
                "span_refinement_level": span_level,
                "nSmoothSurfaceNormals": 20,
            }
        })

    # Test 1.7-1.9: 10 cells (minimum for CFD) with different span levels
    for span_level in [1, 2, 3]:
        tests.append({
            "name": f"span10_level{span_level}",
            "description": f"cells_across_span=10, span_refinement_level={span_level}",
            "snappy_overrides": {
                "span_refinement_enabled": True,
                "cells_across_span": 10,
                "span_refinement_level": span_level,
                "nSmoothSurfaceNormals": 20,
            }
        })

    return tests


def get_phase2_tests() -> List[Dict[str, Any]]:
    """
    Phase 2: Scaling - Test higher cell counts.

    If Phase 1 finds working configs, test higher cell counts.
    Use the span_refinement_level that worked best in Phase 1.
    """
    tests = []

    # Test 2.1-2.3: 12 cells with different span levels
    for span_level in [1, 2]:
        tests.append({
            "name": f"span12_level{span_level}",
            "description": f"cells_across_span=12, span_refinement_level={span_level}",
            "snappy_overrides": {
                "span_refinement_enabled": True,
                "cells_across_span": 12,
                "span_refinement_level": span_level,
                "nSmoothSurfaceNormals": 20,
            }
        })

    # Test 2.4-2.5: 15 cells (previous failing config)
    for span_level in [1, 2]:
        tests.append({
            "name": f"span15_level{span_level}",
            "description": f"cells_across_span=15, span_refinement_level={span_level}",
            "snappy_overrides": {
                "span_refinement_enabled": True,
                "cells_across_span": 15,
                "span_refinement_level": span_level,
                "nSmoothSurfaceNormals": 20,
            }
        })

    # Test 2.6-2.7: 20 cells (production quality)
    for span_level in [1, 2]:
        tests.append({
            "name": f"span20_level{span_level}",
            "description": f"cells_across_span=20, span_refinement_level={span_level}",
            "snappy_overrides": {
                "span_refinement_enabled": True,
                "cells_across_span": 20,
                "span_refinement_level": span_level,
                "nSmoothSurfaceNormals": 20,
            }
        })

    return tests


def get_phase3_tests() -> List[Dict[str, Any]]:
    """
    Phase 3: Optimization - Test smoothing interaction with span refinement.

    Test if higher smoothing can rescue higher cell counts.
    """
    tests = []

    # Test 3.1-3.3: High smoothing with 15 cells (failed in previous study)
    for nSmooth in [30, 50, 100]:
        tests.append({
            "name": f"span15_smooth{nSmooth}",
            "description": f"cells_across_span=15, nSmoothSurfaceNormals={nSmooth}",
            "snappy_overrides": {
                "span_refinement_enabled": True,
                "cells_across_span": 15,
                "span_refinement_level": 2,
                "nSmoothSurfaceNormals": nSmooth,
            }
        })

    # Test 3.4-3.6: High smoothing with 20 cells
    for nSmooth in [30, 50, 100]:
        tests.append({
            "name": f"span20_smooth{nSmooth}",
            "description": f"cells_across_span=20, nSmoothSurfaceNormals={nSmooth}",
            "snappy_overrides": {
                "span_refinement_enabled": True,
                "cells_across_span": 20,
                "span_refinement_level": 2,
                "nSmoothSurfaceNormals": nSmooth,
            }
        })

    # Test 3.7-3.9: Surface refinement level interaction
    # Maybe higher surface refinement helps with span?
    for surf_level in [[1, 1], [1, 2], [2, 3]]:
        tests.append({
            "name": f"span15_surf{surf_level[1]}",
            "description": f"cells_across_span=15, surfaceRefinementLevels={surf_level}",
            "snappy_overrides": {
                "span_refinement_enabled": True,
                "cells_across_span": 15,
                "span_refinement_level": 2,
                "surfaceRefinementLevels": surf_level,
                "nSmoothSurfaceNormals": 50,
            }
        })

    return tests


# =============================================================================
# TEST EXECUTION
# =============================================================================

def create_test_config(test: Dict[str, Any], output_dir: Path) -> Path:
    """Create configuration file for a test."""
    config = json.loads(json.dumps(BASE_CONFIG))  # Deep copy

    # Apply SNAPPY_SETTINGS overrides
    for key, value in test["snappy_overrides"].items():
        config["mesh"]["SNAPPY_SETTINGS"][key] = value

    # Add test metadata
    config["_test_name"] = test["name"]
    config["_test_description"] = test["description"]

    # Write config
    config_path = output_dir / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    return config_path


def run_mesh_only(config_path: Path, test_name: str) -> Dict[str, Any]:
    """Run mesh generation only and return results."""
    project_root = Path(__file__).parent.parent

    result = {
        "config_path": str(config_path),
        "passed": False,
        "error": None,
        "cells": 0,
        "max_skewness": 0,
        "max_non_ortho": 0,
        "time_seconds": 0
    }

    start_time = datetime.now()

    try:
        # Use venv python if available (has numpy-stl and other deps)
        venv_python = project_root / "venv" / "bin" / "python"
        if venv_python.exists():
            python_exe = str(venv_python)
        else:
            python_exe = sys.executable

        # Run patient_runner with patient_id and --config
        cmd = [
            python_exe, "-m", "patient_runner.cli",
            CASE_ID,  # Patient ID
            "--config", str(config_path),
            "--steps", "case,mesh"
        ]

        # Set PYTHONPATH to include src directory
        env = os.environ.copy()
        src_path = str(project_root / "src")
        env["PYTHONPATH"] = src_path + ":" + env.get("PYTHONPATH", "")

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 min timeout
            cwd=str(project_root),
            env=env
        )

        result["stdout"] = proc.stdout
        result["stderr"] = proc.stderr
        result["returncode"] = proc.returncode

        if proc.returncode != 0:
            result["error"] = f"Mesh generation failed with code {proc.returncode}"
            # Still try to parse checkMesh if available
            pass

        # Parse checkMesh output - look for latest run directory
        patient_output = project_root / "output" / CASE_ID
        run_dirs = sorted(patient_output.glob("run_*"), key=lambda p: p.stat().st_mtime)

        if run_dirs:
            latest_run = run_dirs[-1]
            checkmesh_log = latest_run / "openfoam" / "logs" / "log.checkMesh"

            if checkmesh_log.exists():
                mesh_quality = parse_checkmesh_log(checkmesh_log)
                result.update(mesh_quality)

                # Check pass/fail criteria
                # Pass if: skewness < 4.0 AND non-ortho < 75°
                if result["max_skewness"] > 0:  # Only if we got valid data
                    result["passed"] = (
                        result["max_skewness"] < 4.0 and
                        result["max_non_ortho"] < 75
                    )
            else:
                if not result["error"]:
                    result["error"] = "checkMesh log not found"
        else:
            if not result["error"]:
                result["error"] = "No run directory found"

    except subprocess.TimeoutExpired:
        result["error"] = "Timeout (30 min)"
    except Exception as e:
        result["error"] = str(e)

    result["time_seconds"] = (datetime.now() - start_time).total_seconds()
    return result


def parse_checkmesh_log(log_path: Path) -> Dict[str, Any]:
    """Parse checkMesh log for quality metrics."""
    result = {
        "cells": 0,
        "max_skewness": 0,
        "max_non_ortho": 0,
        "mesh_ok": False
    }

    try:
        with open(log_path, 'r') as f:
            content = f.read()

        # Parse cell count
        import re
        cells_match = re.search(r'cells:\s*(\d+)', content)
        if cells_match:
            result["cells"] = int(cells_match.group(1))

        # Parse max skewness
        skew_match = re.search(r'Max skewness = ([\d.]+)', content)
        if skew_match:
            result["max_skewness"] = float(skew_match.group(1))

        # Parse max non-orthogonality
        ortho_match = re.search(r'Mesh non-orthogonality Max:\s*([\d.]+)', content)
        if ortho_match:
            result["max_non_ortho"] = float(ortho_match.group(1))

        # Check if mesh is OK
        result["mesh_ok"] = "Mesh OK" in content

    except Exception as e:
        result["parse_error"] = str(e)

    return result


def run_study(phases: List[int] = None, dry_run: bool = False):
    """Run the span refinement study."""
    if phases is None:
        phases = [1, 2, 3]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    study_dir = OUTPUT_BASE / f"study_{timestamp}"
    study_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("SPAN REFINEMENT STUDY")
    print("=" * 70)
    print(f"Case: {CASE_ID}")
    print(f"Output: {study_dir}")
    print(f"Phases: {phases}")
    print()

    # Collect tests
    all_tests = []
    if 1 in phases:
        all_tests.extend([(1, t) for t in get_phase1_tests()])
    if 2 in phases:
        all_tests.extend([(2, t) for t in get_phase2_tests()])
    if 3 in phases:
        all_tests.extend([(3, t) for t in get_phase3_tests()])

    print(f"Total tests: {len(all_tests)}")
    print("-" * 70)

    if dry_run:
        print("\nDRY RUN - Tests that would be executed:")
        for phase, test in all_tests:
            print(f"  Phase {phase}: {test['name']} - {test['description']}")
        return

    results = []

    for i, (phase, test) in enumerate(all_tests, 1):
        test_name = test["name"]
        test_dir = study_dir / f"phase{phase}_{test_name}"

        print(f"\n[{i}/{len(all_tests)}] Phase {phase}: {test_name}")
        print(f"  Description: {test['description']}")

        # Create config
        config_path = create_test_config(test, test_dir)

        # Run mesh
        result = run_mesh_only(config_path, test_name)
        result["phase"] = phase
        result["test_name"] = test_name
        result["description"] = test["description"]
        result["snappy_overrides"] = test["snappy_overrides"]

        results.append(result)

        # Print result
        status = "✓ PASS" if result["passed"] else "✗ FAIL"
        print(f"  Result: {status}")
        print(f"  Cells: {result['cells']:,}")
        print(f"  Max Skewness: {result['max_skewness']:.2f}")
        print(f"  Max Non-Ortho: {result['max_non_ortho']:.1f}°")
        print(f"  Time: {result['time_seconds']:.0f}s")

        if result.get("error"):
            print(f"  Error: {result['error']}")

        # Save intermediate results
        with open(study_dir / "results.json", 'w') as f:
            json.dump(results, f, indent=2, default=str)

    # Print summary
    print("\n" + "=" * 70)
    print("STUDY SUMMARY")
    print("=" * 70)

    for phase in sorted(set(r["phase"] for r in results)):
        phase_results = [r for r in results if r["phase"] == phase]
        passed = sum(1 for r in phase_results if r["passed"])
        print(f"\nPhase {phase}: {passed}/{len(phase_results)} passed")
        print("-" * 40)

        for r in phase_results:
            status = "✓" if r["passed"] else "✗"
            print(f"  {status} {r['test_name']}: skew={r['max_skewness']:.2f}, ortho={r['max_non_ortho']:.1f}°")

    # Find best configuration
    passed_tests = [r for r in results if r["passed"]]
    if passed_tests:
        best = min(passed_tests, key=lambda r: r["max_skewness"])
        print(f"\n★ BEST CONFIGURATION: {best['test_name']}")
        print(f"  Skewness: {best['max_skewness']:.2f}")
        print(f"  Non-Ortho: {best['max_non_ortho']:.1f}°")
        print(f"  Settings: {best['snappy_overrides']}")
    else:
        print("\n⚠ NO PASSING CONFIGURATIONS FOUND")
        print("  Consider:")
        print("  - Even lower cells_across_span (3-4)")
        print("  - Different surface refinement levels")
        print("  - Disabling span refinement and using target_cell_size_mm instead")

    # Save final results
    with open(study_dir / "results.json", 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nResults saved to: {study_dir / 'results.json'}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Span refinement study for snappyHexMesh",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_mesh_span_refinement_study.py --phase 1        # Run Phase 1 only (9 tests)
  python run_mesh_span_refinement_study.py --phase 1 2      # Run Phase 1 and 2 (16 tests)
  python run_mesh_span_refinement_study.py --phase all      # Run all phases (27 tests)
  python run_mesh_span_refinement_study.py --dry-run        # Show tests without running
        """
    )

    parser.add_argument(
        "--phase",
        nargs="+",
        default=["1"],
        help="Phase(s) to run: 1, 2, 3, or 'all' (default: 1)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show tests without running"
    )

    args = parser.parse_args()

    # Parse phases
    if "all" in args.phase:
        phases = [1, 2, 3]
    else:
        phases = [int(p) for p in args.phase]

    run_study(phases=phases, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
