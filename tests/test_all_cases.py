#!/usr/bin/env python3
"""
Test simplified architecture against ALL cases:
- PAT002: robust profile, TIMEVARYING inlet, 4 outlets
- BPM120: standard profile, TIMEVARYING inlet, 4 outlets
- 0014_H_AO_COA: robust profile, MRI inlet, LES, 5 outlets

Usage:
    python3 tests/test_all_cases.py
"""

import os
import sys
import json
import importlib.util
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def load_module(module_path: Path, module_name: str):
    """Dynamically load a Python module from file path."""
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_config(config_path: str) -> dict:
    """Load JSON config file."""
    with open(config_path, 'r') as f:
        return json.load(f)


# Load modules once
accessor = load_module(PROJECT_ROOT / "src" / "config" / "accessor.py", "accessor")
numerics = load_module(PROJECT_ROOT / "src" / "registry" / "numerics.py", "numerics")
physics = load_module(PROJECT_ROOT / "src" / "registry" / "physics.py", "physics")
csv_reader = load_module(PROJECT_ROOT / "src" / "inlet" / "csv_reader.py", "csv_reader")

Config = accessor.Config


def test_case(case_name: str, config_path: Path, expected: dict) -> bool:
    """
    Test a single case against expected values.

    Args:
        case_name: Name of the case
        config_path: Path to config.json
        expected: Dictionary of expected values

    Returns:
        True if all tests pass
    """
    print(f"\n{'=' * 60}")
    print(f"TESTING: {case_name}")
    print(f"{'=' * 60}")

    if not config_path.exists():
        print(f"  ✗ Config file not found: {config_path}")
        return False

    raw_config = load_config(config_path)
    raw_config['geometry']['case_name'] = case_name

    cfg = Config(raw_config)

    all_passed = True

    # Test each expected value
    for attr, expected_value in expected.items():
        try:
            actual = getattr(cfg, attr)

            if actual == expected_value:
                print(f"  ✓ {attr}: {actual}")
            else:
                print(f"  ✗ {attr}: expected {expected_value}, got {actual}")
                all_passed = False
        except Exception as e:
            print(f"  ✗ {attr}: ERROR - {e}")
            all_passed = False

    return all_passed


def test_csv_for_case(case_name: str, csv_path: Path, expected_cycle: float) -> bool:
    """Test CSV reading for a case."""
    print(f"\n  CSV Test for {case_name}:")

    if not csv_path.exists():
        print(f"    ✗ CSV file not found: {csv_path}")
        return False

    try:
        flow_data = csv_reader.read_flow_csv(str(csv_path), data_type='flow_rate')

        checks = [
            ('Has data', len(flow_data.times) > 0),
            ('Positive cycle', flow_data.cardiac_cycle > 0),
        ]

        # Check cycle is close to expected
        cycle_diff = abs(flow_data.cardiac_cycle - expected_cycle)
        cycle_ok = cycle_diff < 0.1  # Within 0.1s
        checks.append((f'Cycle ≈ {expected_cycle}s', cycle_ok))

        all_ok = True
        for name, passed in checks:
            status = "✓" if passed else "✗"
            print(f"    {status} {name}")
            if not passed:
                all_ok = False

        print(f"    Info: {len(flow_data.times)} points, cycle={flow_data.cardiac_cycle:.4f}s")
        return all_ok

    except Exception as e:
        print(f"    ✗ Failed to read CSV: {e}")
        return False


def test_numerical_profiles():
    """Test that all profiles work correctly."""
    print(f"\n{'=' * 60}")
    print("TESTING: Numerical Profiles")
    print(f"{'=' * 60}")

    profiles_to_test = {
        'robust': {
            'ddt': 'Euler',
            'div_phi_U': 'Gauss upwind',
        },
        'standard': {
            'ddt': 'backward',
            'div_phi_U': 'Gauss limitedLinearV 1',
        },
        'precise': {
            'ddt': 'CrankNicolson 0.9',
            'div_phi_U': 'Gauss LUST grad(U)',
        },
    }

    all_passed = True

    for profile_name, expected_schemes in profiles_to_test.items():
        schemes = numerics.get_schemes(profile_name)

        for scheme_key, expected_value in expected_schemes.items():
            actual = schemes[scheme_key]
            if actual == expected_value:
                print(f"  ✓ {profile_name}.{scheme_key}: {actual}")
            else:
                print(f"  ✗ {profile_name}.{scheme_key}: expected {expected_value}, got {actual}")
                all_passed = False

    return all_passed


def run_all_tests():
    """Run tests for all cases."""
    print("\n" + "=" * 60)
    print("MULTI-CASE ARCHITECTURE TEST SUITE")
    print("=" * 60)

    results = {}

    # =========================================================================
    # Test 1: PAT002
    # =========================================================================
    pat002_expected = {
        'case_name': 'PAT002',
        'profile': 'robust',
        'inlet_patch_name': 'inlet',
        'outlet_patch_names': ['outlet1', 'outlet2', 'outlet3', 'outlet4'],
        'inlet_type': 'TIMEVARYING',
        'outlet_type': '3EWINDKESSEL',
        'is_windkessel': True,
        'subdomains': 4,
        'scale_factor': 0.001,
    }

    results['PAT002 Config'] = test_case(
        'PAT002',
        PROJECT_ROOT / 'cases_input' / 'PAT002' / 'config.json',
        pat002_expected
    )

    results['PAT002 CSV'] = test_csv_for_case(
        'PAT002',
        PROJECT_ROOT / 'cases_input' / 'PAT002' / 'BPM120.csv',
        expected_cycle=0.5  # 120 BPM
    )

    # =========================================================================
    # Test 2: BPM120
    # =========================================================================
    bpm120_expected = {
        'case_name': 'BPM120',
        'profile': 'standard',
        'inlet_patch_name': 'inlet',
        'outlet_patch_names': ['outlet1', 'outlet2', 'outlet3', 'outlet4'],
        'inlet_type': 'TIMEVARYING',
        'outlet_type': '3EWINDKESSEL',
        'is_windkessel': True,
        'subdomains': 8,
        'scale_factor': 0.001,
    }

    results['BPM120 Config'] = test_case(
        'BPM120',
        PROJECT_ROOT / 'cases_input' / 'BPM120' / 'config.json',
        bpm120_expected
    )

    results['BPM120 CSV'] = test_csv_for_case(
        'BPM120',
        PROJECT_ROOT / 'cases_input' / 'BPM120' / 'BPM120.csv',
        expected_cycle=0.5  # 120 BPM
    )

    # =========================================================================
    # Test 3: 0014_H_AO_COA
    # =========================================================================
    coa_expected = {
        'case_name': '0014_H_AO_COA',
        'profile': 'robust',
        'inlet_patch_name': 'inlet',
        'outlet_patch_names': ['outlet1', 'outlet2', 'outlet3', 'outlet4', 'outlet5'],
        'inlet_type': 'MRI',  # MRI inlet type
        'outlet_type': '3EWINDKESSEL',
        'is_windkessel': True,
        'subdomains': 12,
        'scale_factor': 0.01,  # cm to m (SimVascular)
    }

    results['0014_H_AO_COA Config'] = test_case(
        '0014_H_AO_COA',
        PROJECT_ROOT / 'cases_input' / '0014_H_AO_COA' / 'config.json',
        coa_expected
    )

    # Test inflow.csv for this case
    results['0014_H_AO_COA CSV'] = test_csv_for_case(
        '0014_H_AO_COA',
        PROJECT_ROOT / 'cases_input' / '0014_H_AO_COA' / 'inflow.csv',
        expected_cycle=0.845  # From config
    )

    # =========================================================================
    # Test 4: Numerical Profiles (used by all cases)
    # =========================================================================
    results['Numerical Profiles'] = test_numerical_profiles()

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")

    print("-" * 60)
    print(f"  Total: {passed}/{total} tests passed")

    if passed == total:
        print("\n  🎉 ALL TESTS PASSED!")
        print("  Simplified architecture works for ALL cases:")
        print("    - PAT002 (robust profile, 4 outlets)")
        print("    - BPM120 (standard profile, 4 outlets)")
        print("    - 0014_H_AO_COA (robust/LES, MRI inlet, 5 outlets)")
        return True
    else:
        print(f"\n  ⚠️  {total - passed} test(s) failed")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
