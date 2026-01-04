#!/usr/bin/env python3
"""
Efficient Mesh Parameter Study for Cardiovascular CFD
======================================================

Uses Design of Experiments (DOE) principles to minimize test count
while maximizing parameter coverage. Instead of testing every parameter
individually (116 tests), we use:

1. SCREENING PHASE (8 tests): Identify which parameters matter
   - Uses fractional factorial design
   - Tests HIGH vs LOW for key parameters
   - Identifies significant parameters

2. OPTIMIZATION PHASE (10-15 tests): Fine-tune important parameters
   - Focus on parameters that showed sensitivity
   - Test intermediate values

3. VALIDATION PHASE (5 tests): Confirm optimal configuration
   - Test candidate presets
   - Verify with/without span refinement

Total: ~25-30 tests instead of 116 (75% reduction!)

Usage:
======
    # Run efficient study (recommended - ~25 tests)
    python scripts/run_mesh_parameter_study_efficient.py

    # Run only screening phase (8 tests)
    python scripts/run_mesh_parameter_study_efficient.py --phase screening

    # Run only optimization phase
    python scripts/run_mesh_parameter_study_efficient.py --phase optimization

    # Run only validation phase
    python scripts/run_mesh_parameter_study_efficient.py --phase validation

    # Dry run
    python scripts/run_mesh_parameter_study_efficient.py --dry-run

    # Custom core count
    python scripts/run_mesh_parameter_study_efficient.py --cores 8
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path
import re
import argparse
from typing import Dict, List, Any, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Configuration
BASE_CONFIG_PATH = PROJECT_ROOT / "cases_input/0014_H_AO_COA/config_mesh_test.json"
OUTPUT_BASE = PROJECT_ROOT / "output/0014_H_AO_COA/mesh_study_efficient"


# =============================================================================
# PARAMETER DEFINITIONS
# =============================================================================
# Based on previous study findings and OpenFOAM documentation

PARAMETERS = {
    # Parameter: (LOW, HIGH, description)
    # LOW = faster/less quality, HIGH = slower/more quality

    # CRITICAL - from previous study
    "nSmoothSurfaceNormals": (10, 50, "Surface normal smoothing (MOST CRITICAL)"),
    "snapTolerance": (1.0, 2.0, "Snap attraction distance"),

    # IMPORTANT - affect quality
    "nSmoothThickness": (10, 30, "Thickness distribution smoothing"),
    "featureAngle": (160, 180, "Layer termination angle"),
    "expansionRatio": (1.1, 1.25, "Layer growth rate"),
    "nCellsBetweenLevels": (2, 4, "Refinement transition cells"),

    # MODERATE - may affect quality
    "nLayerIter": (50, 100, "Layer addition iterations"),
    "maxFaceThicknessRatio": (0.5, 0.8, "Layer coverage in tight regions"),

    # SPAN REFINEMENT
    "span_refinement_enabled": (False, True, "Enable span refinement"),
    "cells_across_span": (15, 25, "Span resolution"),
}


# =============================================================================
# SCREENING PHASE - Fractional Factorial Design
# =============================================================================

def get_screening_tests() -> List[Dict[str, Any]]:
    """
    Screening phase using 2^(k-p) fractional factorial design.

    Tests 8 key parameters with only 8 runs (instead of 2^8 = 256).
    Each parameter is tested at HIGH and LOW levels.
    Uses Plackett-Burman-like design for efficiency.
    """
    tests = []

    # Design matrix for 8 factors in 8 runs
    # Each row is a test, each column is a parameter
    # +1 = HIGH, -1 = LOW
    # This is a Resolution III design - main effects are aliased with 2-factor interactions
    design_matrix = [
        # nSmooth  snapTol  nThick  featAng  expRat  nCells  nLayer  maxFace
        [   -1,      -1,      -1,      -1,      -1,     -1,     -1,     -1  ],  # All LOW
        [   +1,      -1,      -1,      +1,      -1,     +1,     +1,     -1  ],
        [   -1,      +1,      -1,      +1,      +1,     -1,     +1,     +1  ],
        [   +1,      +1,      -1,      -1,      +1,     +1,     -1,     +1  ],
        [   -1,      -1,      +1,      +1,      +1,     +1,     -1,     -1  ],
        [   +1,      -1,      +1,      -1,      +1,     -1,     +1,     -1  ],
        [   -1,      +1,      +1,      -1,      -1,     +1,     +1,     +1  ],
        [   +1,      +1,      +1,      +1,      -1,     -1,     -1,     +1  ],  # Mixed
    ]

    param_keys = [
        "nSmoothSurfaceNormals",
        "snapTolerance",
        "nSmoothThickness",
        "featureAngle",
        "expansionRatio",
        "nCellsBetweenLevels",
        "nLayerIter",
        "maxFaceThicknessRatio"
    ]

    for i, row in enumerate(design_matrix):
        overrides = {}
        name_parts = []

        for j, level in enumerate(row):
            param = param_keys[j]
            low, high, _ = PARAMETERS[param]
            value = high if level == 1 else low
            overrides[param] = value

            # Short name for test
            short_names = {
                "nSmoothSurfaceNormals": "sN",
                "snapTolerance": "sT",
                "nSmoothThickness": "tH",
                "featureAngle": "fA",
                "expansionRatio": "eR",
                "nCellsBetweenLevels": "cB",
                "nLayerIter": "lI",
                "maxFaceThicknessRatio": "fT"
            }
            name_parts.append(f"{short_names[param]}{'H' if level == 1 else 'L'}")

        tests.append({
            "name": f"screen_{i+1}_{'_'.join(name_parts[:4])}",
            "phase": "screening",
            "description": f"Screening run {i+1}/8",
            "overrides": overrides,
            "design_row": row
        })

    return tests


# =============================================================================
# OPTIMIZATION PHASE - Focus on Critical Parameters
# =============================================================================

def get_optimization_tests() -> List[Dict[str, Any]]:
    """
    Optimization phase focusing on parameters identified as critical
    from previous study: nSmoothSurfaceNormals, expansionRatio, snapTolerance

    Tests intermediate values to find optimum.
    """
    tests = []

    # nSmoothSurfaceNormals sweep (MOST CRITICAL from previous study)
    for n in [15, 20, 30, 40]:
        tests.append({
            "name": f"opt_nSmooth_{n}",
            "phase": "optimization",
            "description": f"nSmoothSurfaceNormals = {n}",
            "overrides": {"nSmoothSurfaceNormals": n}
        })

    # expansionRatio sweep (showed sensitivity in previous study)
    for ratio in [1.15, 1.2]:
        tests.append({
            "name": f"opt_expRatio_{ratio}",
            "phase": "optimization",
            "description": f"expansionRatio = {ratio}",
            "overrides": {"expansionRatio": ratio}
        })

    # Combined optimization - test promising combinations
    tests.append({
        "name": "opt_combo_balanced",
        "phase": "optimization",
        "description": "Balanced: nSmooth=20, expRatio=1.2",
        "overrides": {
            "nSmoothSurfaceNormals": 20,
            "expansionRatio": 1.2,
            "nSmoothThickness": 15
        }
    })

    tests.append({
        "name": "opt_combo_quality",
        "phase": "optimization",
        "description": "Quality: nSmooth=30, expRatio=1.15",
        "overrides": {
            "nSmoothSurfaceNormals": 30,
            "expansionRatio": 1.15,
            "nSmoothThickness": 20
        }
    })

    tests.append({
        "name": "opt_combo_high",
        "phase": "optimization",
        "description": "High: nSmooth=50, expRatio=1.2",
        "overrides": {
            "nSmoothSurfaceNormals": 50,
            "expansionRatio": 1.2,
            "nSmoothThickness": 30,
            "featureAngle": 180
        }
    })

    return tests


# =============================================================================
# VALIDATION PHASE - Test Preset Candidates
# =============================================================================

def get_validation_tests() -> List[Dict[str, Any]]:
    """
    Validation phase to confirm optimal configurations and test presets.
    """
    tests = []

    # Draft preset
    tests.append({
        "name": "val_preset_draft",
        "phase": "validation",
        "description": "Draft preset validation",
        "overrides": {
            "nCellsBetweenLevels": 2,
            "nSmoothSurfaceNormals": 10,
            "nSmoothThickness": 10,
            "nLayerIter": 30,
            "featureAngle": 160,
            "snapTolerance": 1.0,
            "nSolveIter": 10
        }
    })

    # Standard preset (validated in previous study)
    tests.append({
        "name": "val_preset_standard",
        "phase": "validation",
        "description": "Standard preset validation",
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

    # High quality preset
    tests.append({
        "name": "val_preset_high_quality",
        "phase": "validation",
        "description": "High quality preset validation",
        "overrides": {
            "nSmoothSurfaceNormals": 50,
            "nSmoothThickness": 30,
            "nLayerIter": 100,
            "featureAngle": 180,
            "nRelaxedIter": 40,
            "nCellsBetweenLevels": 4,
            "snapTolerance": 1.0,
            "nSolveIter": 10
        }
    })

    # Span refinement test
    tests.append({
        "name": "val_span_standard",
        "phase": "validation",
        "description": "Standard + span refinement",
        "overrides": {
            "span_refinement_enabled": True,
            "cells_across_span": 15,
            "span_refinement_level": 3,
            "nSmoothSurfaceNormals": 30,
            "nSmoothThickness": 20,
            "snapTolerance": 1.0
        }
    })

    # Span with high smoothing
    tests.append({
        "name": "val_span_high_smooth",
        "phase": "validation",
        "description": "Span + high smoothing",
        "overrides": {
            "span_refinement_enabled": True,
            "cells_across_span": 20,
            "span_refinement_level": 3,
            "nSmoothSurfaceNormals": 50,
            "nSmoothThickness": 30,
            "nCellsBetweenLevels": 4,
            "snapTolerance": 1.0
        }
    })

    return tests


# =============================================================================
# QUICK TEST - Minimal validation
# =============================================================================

def get_quick_tests() -> List[Dict[str, Any]]:
    """Minimal test set for quick validation (3 tests)."""
    return [
        {
            "name": "quick_baseline",
            "phase": "quick",
            "description": "Baseline (no changes)",
            "overrides": {}
        },
        {
            "name": "quick_standard",
            "phase": "quick",
            "description": "Standard preset",
            "overrides": {
                "nSmoothSurfaceNormals": 20,
                "nSmoothThickness": 15,
                "featureAngle": 170,
                "snapTolerance": 1.0
            }
        },
        {
            "name": "quick_span",
            "phase": "quick",
            "description": "With span refinement",
            "overrides": {
                "span_refinement_enabled": True,
                "cells_across_span": 15,
                "span_refinement_level": 3,
                "nSmoothSurfaceNormals": 30
            }
        }
    ]


# =============================================================================
# TEST EXECUTION (same as comprehensive script)
# =============================================================================

def load_base_config() -> dict:
    """Load the base configuration."""
    if not BASE_CONFIG_PATH.exists():
        raise FileNotFoundError(f"Base config not found: {BASE_CONFIG_PATH}")
    with open(BASE_CONFIG_PATH) as f:
        return json.load(f)


def create_test_config(base_config: dict, test_name: str, overrides: dict) -> dict:
    """Create a test configuration with specific overrides."""
    config = json.loads(json.dumps(base_config))  # Deep copy
    config["_mesh_study"] = test_name

    boundary_layer_keys = {
        "addLayers": "enabled",
        "num_layers": "num_layers",
        "expansionRatio": "expansion_ratio",
        "finalLayerThickness": "final_layer_thickness",
        "minThickness": "min_thickness",
    }

    for key, value in overrides.items():
        if key == "quality_preset":
            config["mesh"]["quality_preset"] = value
        elif key in boundary_layer_keys:
            bl_key = boundary_layer_keys[key]
            if "boundary_layers" not in config["mesh"]:
                config["mesh"]["boundary_layers"] = {}
            config["mesh"]["boundary_layers"][bl_key] = value
        else:
            if "SNAPPY_SETTINGS" not in config["mesh"]:
                config["mesh"]["SNAPPY_SETTINGS"] = {}
            config["mesh"]["SNAPPY_SETTINGS"][key] = value

    return config


def run_mesh_only(config: dict, test_name: str, output_dir: Path) -> dict:
    """Run meshing only and return results."""
    test_output = output_dir / test_name
    test_output.mkdir(parents=True, exist_ok=True)

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

    print(f"\n{'='*60}")
    print(f"Running: {test_name}")
    print(f"{'='*60}")

    start_time = datetime.now()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=2400,
            env=env,
            cwd=str(PROJECT_ROOT)
        )

        elapsed = (datetime.now() - start_time).total_seconds()
        check_mesh_result = parse_checkmesh_output(patient_id)

        return {
            "test_name": test_name,
            "success": result.returncode == 0,
            "elapsed_seconds": elapsed,
            "checkmesh": check_mesh_result,
        }

    except subprocess.TimeoutExpired:
        return {"test_name": test_name, "success": False, "error": "Timeout"}
    except Exception as e:
        return {"test_name": test_name, "success": False, "error": str(e)}


def parse_checkmesh_output(patient_id: str) -> dict:
    """Parse checkMesh log."""
    patient_output = PROJECT_ROOT / "output" / patient_id
    run_dirs = list(patient_output.glob("run_*"))
    if not run_dirs:
        return {"error": "No run directory found"}

    latest_run = max(run_dirs, key=lambda p: p.stat().st_mtime)
    log_path = latest_run / "openfoam/logs/log.checkMesh"

    if not log_path.exists():
        return {"error": "No checkMesh log"}

    with open(log_path) as f:
        content = f.read()

    result = {
        "passed": "Mesh OK" in content or "Failed 0 mesh checks" in content,
        "failed_checks": 0
    }

    patterns = {
        "cells": r"cells:\s+(\d+)",
        "max_non_ortho": r"Mesh non-orthogonality Max:\s+([\d.]+)",
        "max_skewness": r"Max skewness = ([\d.]+)",
        "skew_faces": r"(\d+) highly skew faces",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, content)
        if match:
            try:
                result[key] = float(match.group(1))
            except ValueError:
                result[key] = match.group(1)

    failed_match = re.search(r"Failed (\d+) mesh checks", content)
    if failed_match:
        result["failed_checks"] = int(failed_match.group(1))

    return result


def print_results_table(results: list):
    """Print results summary."""
    print("\n" + "="*90)
    print("EFFICIENT MESH PARAMETER STUDY RESULTS")
    print("="*90)

    print(f"{'Test Name':<30} {'Pass':<6} {'Cells':<12} {'MaxSkew':<10} {'MaxOrtho':<10} {'Time':<8}")
    print("-"*90)

    for r in results:
        cm = r.get("checkmesh", {})
        passed = "✓" if cm.get("passed", False) else "✗"
        cells = cm.get("cells", "N/A")
        skew = cm.get("max_skewness", "N/A")
        ortho = cm.get("max_non_ortho", "N/A")
        time_s = r.get("elapsed_seconds", 0)

        if isinstance(cells, float):
            cells = f"{int(cells):,}"
        if isinstance(skew, float):
            skew = f"{skew:.2f}"
        if isinstance(ortho, float):
            ortho = f"{ortho:.1f}°"

        print(f"{r['test_name']:<30} {passed:<6} {str(cells):<12} {str(skew):<10} {str(ortho):<10} {time_s:.0f}s")

    print("="*90)

    passed_tests = [r for r in results if r.get("checkmesh", {}).get("passed", False)]
    print(f"\nPassed: {len(passed_tests)}/{len(results)}")

    if passed_tests:
        print("\nBest by skewness:")
        sorted_passed = sorted(passed_tests,
                              key=lambda r: r.get("checkmesh", {}).get("max_skewness", 999))
        for i, r in enumerate(sorted_passed[:3], 1):
            cm = r.get("checkmesh", {})
            print(f"  {i}. {r['test_name']}: skew={cm.get('max_skewness', 'N/A'):.2f}")


def analyze_screening_results(results: list):
    """Analyze screening phase to identify significant parameters."""
    print("\n" + "="*60)
    print("SCREENING ANALYSIS - Parameter Effects")
    print("="*60)

    # Get screening results only
    screening = [r for r in results if r.get("test_name", "").startswith("screen_")]

    if len(screening) < 8:
        print("Not enough screening results for analysis")
        return

    # Calculate main effects for each parameter
    param_keys = [
        "nSmoothSurfaceNormals",
        "snapTolerance",
        "nSmoothThickness",
        "featureAngle",
        "expansionRatio",
        "nCellsBetweenLevels",
        "nLayerIter",
        "maxFaceThicknessRatio"
    ]

    print("\nEffect on Max Skewness (negative = parameter reduces skewness):")
    print("-" * 60)

    effects = {}
    for j, param in enumerate(param_keys):
        high_skews = []
        low_skews = []

        for r in screening:
            row = r.get("design_row", [])
            if len(row) <= j:
                continue
            skew = r.get("checkmesh", {}).get("max_skewness")
            if skew is None:
                continue

            if row[j] == 1:
                high_skews.append(skew)
            else:
                low_skews.append(skew)

        if high_skews and low_skews:
            effect = sum(high_skews)/len(high_skews) - sum(low_skews)/len(low_skews)
            effects[param] = effect
            significance = "***" if abs(effect) > 0.5 else "**" if abs(effect) > 0.2 else "*" if abs(effect) > 0.1 else ""
            print(f"  {param:<25}: {effect:+.3f} {significance}")

    print("\nSignificance: *** = major, ** = moderate, * = minor")

    # Identify most significant parameters
    if effects:
        sorted_effects = sorted(effects.items(), key=lambda x: abs(x[1]), reverse=True)
        print(f"\nMost significant parameters:")
        for param, effect in sorted_effects[:3]:
            direction = "INCREASE" if effect < 0 else "DECREASE"
            print(f"  - {param}: {direction} HIGH value to reduce skewness")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Efficient mesh parameter study using DOE principles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Phases:
  screening     - 8 tests using fractional factorial design
  optimization  - 9 tests focusing on critical parameters
  validation    - 5 tests confirming preset configurations

Examples:
  python run_mesh_parameter_study_efficient.py           # Full study (~22 tests)
  python run_mesh_parameter_study_efficient.py --quick   # Quick (3 tests)
  python run_mesh_parameter_study_efficient.py --phase screening
  python run_mesh_parameter_study_efficient.py --dry-run
        """
    )
    parser.add_argument("--phase", type=str,
                       choices=["screening", "optimization", "validation"],
                       help="Run specific phase only")
    parser.add_argument("--quick", action="store_true",
                       help="Run minimal test set (3 tests)")
    parser.add_argument("--dry-run", action="store_true",
                       help="List tests without running")
    parser.add_argument("--cores", type=int, default=12,
                       help="Number of cores (default: 12)")
    args = parser.parse_args()

    # Build test list
    if args.quick:
        test_matrix = get_quick_tests()
        study_name = "quick"
    elif args.phase == "screening":
        test_matrix = get_screening_tests()
        study_name = "screening"
    elif args.phase == "optimization":
        test_matrix = get_optimization_tests()
        study_name = "optimization"
    elif args.phase == "validation":
        test_matrix = get_validation_tests()
        study_name = "validation"
    else:
        # Full study - all phases
        test_matrix = []
        test_matrix.extend(get_screening_tests())
        test_matrix.extend(get_optimization_tests())
        test_matrix.extend(get_validation_tests())
        study_name = "full"

    # Dry run
    if args.dry_run:
        print(f"\nEfficient Study: {study_name} ({len(test_matrix)} tests)")
        print("="*60)

        by_phase = {}
        for t in test_matrix:
            phase = t.get("phase", "unknown")
            if phase not in by_phase:
                by_phase[phase] = []
            by_phase[phase].append(t)

        for phase, tests in by_phase.items():
            print(f"\n{phase.upper()} ({len(tests)} tests):")
            for t in tests:
                print(f"  - {t['name']}: {t.get('description', '')}")

        print(f"\nTotal: {len(test_matrix)} tests")
        print(f"Estimated time: {len(test_matrix) * 7:.0f} minutes ({len(test_matrix) * 7 / 60:.1f} hours)")
        return 0

    # Load config
    try:
        base_config = load_base_config()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    # Set cores
    if "mesh" in base_config and "SNAPPY_SETTINGS" in base_config["mesh"]:
        base_config["mesh"]["SNAPPY_SETTINGS"]["nProcessors"] = args.cores

    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_BASE / f"study_{study_name}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nEfficient Mesh Parameter Study")
    print(f"="*60)
    print(f"Study: {study_name}")
    print(f"Tests: {len(test_matrix)}")
    print(f"Cores: {args.cores}")
    print(f"Output: {output_dir}")
    print(f"Estimated time: {len(test_matrix) * 7:.0f} min")

    # Run tests
    results = []
    for i, test in enumerate(test_matrix, 1):
        print(f"\n[{i}/{len(test_matrix)}] {test['name']}")

        config = create_test_config(base_config, test["name"], test["overrides"])
        result = run_mesh_only(config, test["name"], output_dir)
        result["phase"] = test.get("phase", "unknown")
        result["design_row"] = test.get("design_row")
        results.append(result)

        cm = result.get("checkmesh", {})
        status = "✓ PASS" if cm.get("passed") else "✗ FAIL"
        skew = cm.get("max_skewness", "N/A")
        skew_str = f"{skew:.2f}" if isinstance(skew, (int, float)) else skew
        print(f"    {status} - Skew: {skew_str}")

    # Save results
    results_path = output_dir / "results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    # Print summary
    print_results_table(results)

    # Analyze screening if applicable
    if study_name in ["full", "screening"]:
        analyze_screening_results(results)

    print(f"\nResults saved to: {results_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
