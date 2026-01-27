#!/usr/bin/env python3
"""
Cross-validation test for postprocessing.

Uses existing PAT003 simulation data to verify the hemodynamics postprocessor
produces consistent results.

Usage:
    python tests/test_postprocessing_crosscheck.py
"""

import os
import sys
import json
import importlib.util
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


def load_module(module_path: Path, module_name: str):
    """Dynamically load a Python module from file path."""
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Load the hemodynamics postprocessor directly
hemodynamics_module = load_module(
    PROJECT_ROOT / "src" / "aortacfd_lib" / "hemodynamics_postprocessor.py",
    "hemodynamics_postprocessor"
)
HemodynamicsPostProcessor = hemodynamics_module.HemodynamicsPostProcessor
HemodynamicsResults = hemodynamics_module.HemodynamicsResults


def load_config(config_path: str) -> dict:
    """Load JSON config file."""
    with open(config_path, 'r') as f:
        return json.load(f)


def parse_old_report(report_path: str) -> dict:
    """
    Parse the old hemodynamics report to extract values for comparison.

    Returns:
        Dictionary with extracted values
    """
    with open(report_path, 'r') as f:
        content = f.read()

    results = {}

    # Parse WSS values
    import re

    # WSS section
    wss_max = re.search(r'Maximum:\s*([\d.]+)\s*Pa', content)
    wss_mean = re.search(r'Mean:\s*([\d.]+)\s*Pa', content)
    wss_min = re.search(r'Minimum:\s*([\d.]+)\s*Pa', content)

    if wss_max:
        results['wss_max'] = float(wss_max.group(1))
    if wss_mean:
        results['wss_mean'] = float(wss_mean.group(1))
    if wss_min:
        results['wss_min'] = float(wss_min.group(1))

    # TAWSS section
    tawss_max = re.search(r'TAWSS Maximum:\s*([\d.]+)\s*Pa', content)
    tawss_mean = re.search(r'TAWSS Mean:\s*([\d.]+)\s*Pa', content)

    if tawss_max:
        results['tawss_max'] = float(tawss_max.group(1))
    if tawss_mean:
        results['tawss_mean'] = float(tawss_mean.group(1))

    # OSI section
    osi_max = re.search(r'OSI Maximum:\s*([\d.]+)', content)
    osi_mean = re.search(r'OSI Mean:\s*([\d.]+)', content)

    if osi_max:
        results['osi_max'] = float(osi_max.group(1))
    if osi_mean:
        results['osi_mean'] = float(osi_mean.group(1))

    # RRT section
    rrt_max = re.search(r'RRT Maximum:\s*([\d.]+)\s*Pa', content)
    rrt_mean = re.search(r'RRT Mean:\s*([\d.]+)\s*Pa', content)

    if rrt_max:
        results['rrt_max'] = float(rrt_max.group(1))
    if rrt_mean:
        results['rrt_mean'] = float(rrt_mean.group(1))

    # Pressure drop
    inlet_pressure = re.search(r'Inlet pressure:\s*([\d.]+)\s*mmHg', content)
    if inlet_pressure:
        results['pressure_inlet_mmhg'] = float(inlet_pressure.group(1))

    # Cardiac cycle
    cardiac_cycle = re.search(r'Cardiac Cycle:\s*([\d.]+)\s*s', content)
    if cardiac_cycle:
        results['cardiac_cycle'] = float(cardiac_cycle.group(1))

    # Flow type
    results['is_pulsatile'] = 'Pulsatile' in content

    return results


def compare_values(name: str, old_val: float, new_val: float, tolerance: float = 0.01) -> bool:
    """
    Compare two values with relative tolerance.

    Args:
        name: Name of the metric
        old_val: Old (reference) value
        new_val: New (computed) value
        tolerance: Relative tolerance (default 1%)

    Returns:
        True if values match within tolerance
    """
    if old_val == 0:
        diff = abs(new_val)
        ok = diff < 1e-6
    else:
        diff = abs(new_val - old_val) / abs(old_val)
        ok = diff < tolerance

    status = "✓" if ok else "✗"
    print(f"  {status} {name}: old={old_val:.4f}, new={new_val:.4f}, diff={diff*100:.2f}%")

    return ok


def run_crosscheck():
    """Run the cross-validation test."""
    print("=" * 70)
    print("POSTPROCESSING CROSS-VALIDATION TEST")
    print("=" * 70)
    print()

    # Paths
    run_dir = PROJECT_ROOT / "output" / "PAT003" / "run_20260124_081905"
    case_dir = run_dir / "openfoam"
    config_path = run_dir / "reports" / "merged_config.json"
    old_report_path = run_dir / "reports" / "hemodynamics_report.txt"

    # Check paths exist
    if not case_dir.exists():
        print(f"ERROR: Case directory not found: {case_dir}")
        return False

    if not old_report_path.exists():
        print(f"ERROR: Old report not found: {old_report_path}")
        return False

    print(f"Case directory: {case_dir}")
    print(f"Old report: {old_report_path}")
    print()

    # Load config
    config = load_config(config_path)

    # Parse old report
    print("Parsing old hemodynamics report...")
    old_results = parse_old_report(old_report_path)
    print(f"  Parsed {len(old_results)} values from old report")
    print()

    # Run new postprocessor
    print("Running HemodynamicsPostProcessor...")
    processor = HemodynamicsPostProcessor(str(case_dir), config)
    new_results = processor.compute_all()
    print(f"  Computation complete")
    print()

    # Compare results
    print("-" * 70)
    print("COMPARISON: Old Report vs New Computation")
    print("-" * 70)

    all_passed = True

    # Flow type
    print(f"\nFlow Type:")
    print(f"  Old: {'Pulsatile' if old_results.get('is_pulsatile') else 'Steady'}")
    print(f"  New: {'Pulsatile' if new_results.is_pulsatile else 'Steady'}")
    if old_results.get('is_pulsatile') != new_results.is_pulsatile:
        print("  ✗ Flow type mismatch!")
        all_passed = False
    else:
        print("  ✓ Flow type matches")

    # Cardiac cycle
    if 'cardiac_cycle' in old_results:
        print(f"\nCardiac Cycle:")
        if not compare_values("cardiac_cycle", old_results['cardiac_cycle'], new_results.cardiac_cycle):
            all_passed = False

    # WSS comparison
    print(f"\nWall Shear Stress (WSS):")
    if 'wss_max' in old_results:
        if not compare_values("wss_max", old_results['wss_max'], new_results.wss_max):
            all_passed = False
    if 'wss_mean' in old_results:
        if not compare_values("wss_mean", old_results['wss_mean'], new_results.wss_mean):
            all_passed = False
    if 'wss_min' in old_results:
        if not compare_values("wss_min", old_results['wss_min'], new_results.wss_min):
            all_passed = False

    # TAWSS comparison (pulsatile only)
    if new_results.is_pulsatile:
        print(f"\nTime-Averaged Wall Shear Stress (TAWSS):")
        if 'tawss_max' in old_results:
            if not compare_values("tawss_max", old_results['tawss_max'], new_results.tawss_max):
                all_passed = False
        if 'tawss_mean' in old_results:
            if not compare_values("tawss_mean", old_results['tawss_mean'], new_results.tawss_mean):
                all_passed = False

        print(f"\nOscillatory Shear Index (OSI):")
        if 'osi_max' in old_results:
            if not compare_values("osi_max", old_results['osi_max'], new_results.osi_max):
                all_passed = False
        if 'osi_mean' in old_results:
            if not compare_values("osi_mean", old_results['osi_mean'], new_results.osi_mean):
                all_passed = False

        print(f"\nRelative Residence Time (RRT):")
        if 'rrt_max' in old_results:
            if not compare_values("rrt_max", old_results['rrt_max'], new_results.rrt_max):
                all_passed = False
        if 'rrt_mean' in old_results:
            if not compare_values("rrt_mean", old_results['rrt_mean'], new_results.rrt_mean):
                all_passed = False

    # Pressure comparison
    # Note: pressure_inlet is kinematic pressure (p/rho), need to multiply by rho for Pa, then convert to mmHg
    print(f"\nPressure (converted to mmHg):")
    if 'pressure_inlet_mmhg' in old_results:
        new_inlet_mmhg = new_results.pressure_inlet * HemodynamicsPostProcessor.PA_TO_MMHG * HemodynamicsPostProcessor.BLOOD_DENSITY
        if not compare_values("inlet_pressure", old_results['pressure_inlet_mmhg'], new_inlet_mmhg, tolerance=0.01):
            all_passed = False

    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if all_passed:
        print("🎉 ALL CROSS-CHECKS PASSED!")
        print("   New postprocessor produces consistent results with old report.")
    else:
        print("⚠️  SOME CROSS-CHECKS FAILED")
        print("   Review the differences above.")

    print()

    # Also generate a new report to compare format
    print("Generating new report for format comparison...")
    new_report_path = run_dir / "reports" / "hemodynamics_report_NEW.txt"
    processor.generate_report(new_results, str(run_dir / "reports"))
    print(f"  New report saved to: {new_report_path}")

    return all_passed


if __name__ == '__main__':
    success = run_crosscheck()
    sys.exit(0 if success else 1)
