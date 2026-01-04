#!/usr/bin/env python3
"""
Test Mesh Quality Presets - Span Refinement Study
==================================================

This script tests the new mesh quality preset system with the 9 span
refinement study configurations across 3 patient cases.

Test Matrix:
    Patient Cases: BPM120, PAT002, 0014_H_AO_COA
    Span Values:   15 (draft), 20 (standard), 25 (high_quality)

Expected Behavior:
    - span=15 uses draft preset:        nSolveIter=10, faster meshing
    - span=20 uses standard preset:     nSolveIter=50, balanced
    - span=25 uses high_quality preset: nSolveIter=150, best quality

Usage:
    # Dry run - validate configs only
    python scripts/validate_mesh_quality_presets.py --dry-run

    # Run one case for quick test
    python scripts/validate_mesh_quality_presets.py --patient BPM120 --span 20

    # Run all 9 combinations
    python scripts/validate_mesh_quality_presets.py --all

    # Run all span variants for one patient
    python scripts/validate_mesh_quality_presets.py --patient BPM120
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from config.mesh_quality_presets import get_mesh_preset, get_available_presets


def apply_mesh_quality_preset(config: dict) -> dict:
    """
    Apply mesh quality preset if specified in config.

    This is a standalone version of ConfigBuilder._apply_mesh_quality_preset
    for use in validation scripts.

    Args:
        config: Configuration dictionary

    Returns:
        Configuration with preset values applied
    """
    mesh_config = config.get('mesh', {})
    preset_name = mesh_config.get('quality_preset')

    if not preset_name:
        return config

    # Validate preset name
    available = get_available_presets()
    if preset_name not in available:
        print(f"⚠️  Unknown mesh quality preset: '{preset_name}'. Valid options: {available}")
        return config

    # Get preset values
    preset_values = get_mesh_preset(preset_name)

    # Get current SNAPPY_SETTINGS
    current_snappy = mesh_config.get('SNAPPY_SETTINGS', {})

    # Apply preset values, then user overrides
    merged_snappy = preset_values.copy()
    merged_snappy.update(current_snappy)

    # Update config
    if 'mesh' not in config:
        config['mesh'] = {}
    config['mesh']['SNAPPY_SETTINGS'] = merged_snappy

    return config


# Test configurations
TEST_MATRIX = {
    "BPM120": {
        15: "cases_input/BPM120/config_mesh_span15.json",
        20: "cases_input/BPM120/config_mesh_span20.json",
        25: "cases_input/BPM120/config_mesh_span25.json",
    },
    "PAT002": {
        15: "cases_input/PAT002/config_mesh_span15.json",
        20: "cases_input/PAT002/config_mesh_span20.json",
        25: "cases_input/PAT002/config_mesh_span25.json",
    },
    "0014_H_AO_COA": {
        15: "cases_input/0014_H_AO_COA/config_mesh_span15.json",
        20: "cases_input/0014_H_AO_COA/config_mesh_span20.json",
        25: "cases_input/0014_H_AO_COA/config_mesh_span25.json",
    },
}

# Expected presets for each span value
EXPECTED_PRESETS = {
    15: "draft",
    20: "standard",
    25: "high_quality",
}

# Expected parameter values for each preset
PRESET_PARAMS = {
    "draft": {"nSolveIter": 10, "nSmoothSurfaceNormals": 5, "nLayerIter": 20},
    "standard": {"nSolveIter": 50, "nSmoothSurfaceNormals": 15, "nLayerIter": 50},
    "high_quality": {"nSolveIter": 150, "nSmoothSurfaceNormals": 30, "nLayerIter": 100},
}


def validate_config(config_path: str) -> Dict:
    """Validate a config file and return details."""
    result = {
        "path": config_path,
        "valid": False,
        "preset": None,
        "span": None,
        "params": {},
        "errors": [],
    }

    if not os.path.exists(config_path):
        result["errors"].append(f"Config file not found: {config_path}")
        return result

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        result["errors"].append(f"Invalid JSON: {e}")
        return result

    # Check for mesh section
    if "mesh" not in config:
        result["errors"].append("Missing 'mesh' section")
        return result

    mesh = config["mesh"]

    # Get preset
    result["preset"] = mesh.get("quality_preset", "not specified")

    # Get span
    snappy = mesh.get("SNAPPY_SETTINGS", {})
    result["span"] = snappy.get("cells_across_span", "not specified")

    # Apply preset and get effective parameters
    effective = apply_mesh_quality_preset(config)
    effective_snappy = effective.get("mesh", {}).get("SNAPPY_SETTINGS", {})

    result["params"] = {
        "nSolveIter": effective_snappy.get("nSolveIter"),
        "nSmoothSurfaceNormals": effective_snappy.get("nSmoothSurfaceNormals"),
        "nLayerIter": effective_snappy.get("nLayerIter"),
    }

    result["valid"] = True
    return result


def run_mesh_step(patient: str, config_path: str, dry_run: bool = False) -> Dict:
    """Run the mesh step for a config and capture results."""
    result = {
        "patient": patient,
        "config": config_path,
        "success": False,
        "mesh_time": None,
        "quality_tier": None,
        "metrics": {},
        "log_path": None,
        "error": None,
    }

    if dry_run:
        print(f"  [DRY RUN] Would run: python run_patient.py {patient} -c {config_path} -s case,mesh")
        result["success"] = True
        return result

    # Run mesh step
    cmd = [
        sys.executable, "run_patient.py",
        patient,
        "-c", config_path,
        "-s", "case,mesh"
    ]

    print(f"  Running: {' '.join(cmd)}")
    start_time = datetime.now()

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )

        result["mesh_time"] = (datetime.now() - start_time).total_seconds()

        if proc.returncode == 0:
            result["success"] = True
            # Parse output for quality tier
            for line in proc.stdout.split('\n'):
                if "Mesh quality tier:" in line:
                    result["quality_tier"] = line.split(":")[-1].strip()
                elif "Max skewness:" in line:
                    result["metrics"]["max_skewness"] = line.split(":")[-1].strip()
                elif "Max non-orthogonality:" in line:
                    result["metrics"]["max_non_ortho"] = line.split(":")[-1].strip()
        else:
            result["error"] = proc.stderr or "Unknown error"

    except subprocess.TimeoutExpired:
        result["error"] = "Timeout (1 hour)"
    except Exception as e:
        result["error"] = str(e)

    return result


def print_validation_summary(validations: List[Dict]):
    """Print summary of config validations."""
    print("\n" + "=" * 80)
    print("CONFIGURATION VALIDATION SUMMARY")
    print("=" * 80)

    print(f"\n{'Config':<50} {'Preset':<15} {'Span':<6} {'nSolveIter':<12} {'Valid':<6}")
    print("-" * 80)

    for v in validations:
        preset = v.get("preset", "N/A")
        span = v.get("span", "N/A")
        n_solve = v.get("params", {}).get("nSolveIter", "N/A")
        valid = "OK" if v["valid"] else "FAIL"

        short_path = os.path.basename(os.path.dirname(v["path"])) + "/" + os.path.basename(v["path"])
        print(f"{short_path:<50} {preset:<15} {span:<6} {n_solve:<12} {valid:<6}")

        if v.get("errors"):
            for error in v["errors"]:
                print(f"  ERROR: {error}")

    # Check preset/span alignment
    print("\n" + "-" * 80)
    print("PRESET/SPAN ALIGNMENT CHECK:")

    all_aligned = True
    for v in validations:
        if not v["valid"]:
            continue
        span = v.get("span")
        preset = v.get("preset")
        expected = EXPECTED_PRESETS.get(span)

        if expected and preset != expected:
            print(f"  MISMATCH: {v['path']}")
            print(f"    span={span} should use '{expected}' preset, but uses '{preset}'")
            all_aligned = False

    if all_aligned:
        print("  All configs correctly aligned!")


def print_test_results(results: List[Dict]):
    """Print summary of test results."""
    print("\n" + "=" * 80)
    print("MESH GENERATION TEST RESULTS")
    print("=" * 80)

    print(f"\n{'Patient':<15} {'Span':<6} {'Preset':<15} {'Time (s)':<10} {'Quality':<12} {'Status':<8}")
    print("-" * 80)

    for r in results:
        patient = r.get("patient", "N/A") or "N/A"
        config_name = os.path.basename(r.get("config", ""))
        span = "".join(c for c in config_name if c.isdigit()) or "?"
        preset = EXPECTED_PRESETS.get(int(span) if span.isdigit() else 0, "?") or "?"
        time_str = f"{r['mesh_time']:.1f}" if r.get("mesh_time") else "N/A"
        quality = r.get("quality_tier") or "N/A"
        status = "OK" if r.get("success") else "FAIL"

        print(f"{patient:<15} {span:<6} {preset:<15} {time_str:<10} {quality:<12} {status:<8}")

        if r.get("error"):
            print(f"  Error: {r['error'][:60]}...")


def main():
    parser = argparse.ArgumentParser(
        description="Test mesh quality presets with span refinement study configs"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate configs without running meshing")
    parser.add_argument("--patient", type=str,
                        choices=list(TEST_MATRIX.keys()),
                        help="Run tests for specific patient only")
    parser.add_argument("--span", type=int, choices=[15, 20, 25],
                        help="Run tests for specific span value only")
    parser.add_argument("--all", action="store_true",
                        help="Run all 9 test combinations")
    parser.add_argument("--validate-only", action="store_true",
                        help="Only validate configs, don't run meshing")

    args = parser.parse_args()

    print("=" * 80)
    print("MESH QUALITY PRESET TEST - Span Refinement Study")
    print("=" * 80)
    print(f"\nProject root: {PROJECT_ROOT}")
    print(f"Available presets: {get_available_presets()}")

    # Determine which configs to test
    configs_to_test = []
    for patient, spans in TEST_MATRIX.items():
        if args.patient and patient != args.patient:
            continue
        for span, config_path in spans.items():
            if args.span and span != args.span:
                continue
            configs_to_test.append((patient, span, config_path))

    if not configs_to_test:
        print("\nNo configs selected. Use --all, --patient, or --span to select tests.")
        return

    print(f"\nConfigs to test: {len(configs_to_test)}")
    for patient, span, config_path in configs_to_test:
        print(f"  - {patient} span={span}: {config_path}")

    # Validate all configs
    print("\n" + "-" * 80)
    print("PHASE 1: Configuration Validation")
    print("-" * 80)

    validations = []
    for patient, span, config_path in configs_to_test:
        full_path = str(PROJECT_ROOT / config_path)
        print(f"\nValidating: {config_path}")
        validation = validate_config(full_path)
        validations.append(validation)

        if validation["valid"]:
            print(f"  Preset: {validation['preset']}")
            print(f"  Span: {validation['span']}")
            print(f"  Effective nSolveIter: {validation['params'].get('nSolveIter')}")
        else:
            for error in validation["errors"]:
                print(f"  ERROR: {error}")

    print_validation_summary(validations)

    # Stop here if validate-only or dry-run
    if args.validate_only or args.dry_run:
        if args.dry_run:
            print("\n" + "-" * 80)
            print("PHASE 2: Mesh Generation (DRY RUN)")
            print("-" * 80)
            for patient, span, config_path in configs_to_test:
                run_mesh_step(patient, config_path, dry_run=True)
        print("\nValidation complete. Use --all to run actual meshing.")
        return

    # Run meshing
    print("\n" + "-" * 80)
    print("PHASE 2: Mesh Generation")
    print("-" * 80)

    results = []
    for patient, span, config_path in configs_to_test:
        print(f"\n[{len(results)+1}/{len(configs_to_test)}] {patient} span={span}")
        result = run_mesh_step(patient, config_path)
        results.append(result)

    print_test_results(results)

    # Summary
    successful = sum(1 for r in results if r.get("success"))
    print(f"\n{'=' * 80}")
    print(f"SUMMARY: {successful}/{len(results)} tests passed")
    print("=" * 80)


if __name__ == "__main__":
    main()
