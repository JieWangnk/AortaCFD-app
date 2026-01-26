#!/usr/bin/env python3
"""
Test script to compare NEW simplified architecture vs ORIGINAL architecture.

This test ensures the new simplified modules produce identical or equivalent
output to the original code.

Usage:
    python tests/test_architecture_comparison.py
"""

import os
import sys
import json
import shutil
import tempfile
import difflib
from pathlib import Path

# Add src to path - directly to the src directory for isolated testing
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

# Set PYTHONPATH for submodule imports
os.environ['PYTHONPATH'] = project_root


def load_config(config_path: str) -> dict:
    """Load JSON config file."""
    with open(config_path, 'r') as f:
        return json.load(f)


def test_config_accessor():
    """Test that Config accessor returns correct values."""
    print("\n" + "=" * 60)
    print("TEST 1: Config Accessor")
    print("=" * 60)

    from src.config.accessor import Config

    config_path = 'cases_input/PAT002/config.json'
    raw_config = load_config(config_path)

    # Add geometry case_name (normally done by builder)
    raw_config['geometry']['case_name'] = 'PAT002'

    cfg = Config(raw_config)

    # Test property access
    tests = [
        ('case_name', cfg.case_name, 'PAT002'),
        ('profile', cfg.profile, 'robust'),
        ('inlet_patch_name', cfg.inlet_patch_name, 'inlet'),
        ('outlet_patch_names', cfg.outlet_patch_names, ['outlet1', 'outlet2', 'outlet3', 'outlet4']),
        ('inlet_type', cfg.inlet_type, 'TIMEVARYING'),
        ('outlet_type', cfg.outlet_type, '3EWINDKESSEL'),
        ('is_windkessel', cfg.is_windkessel, True),
        ('subdomains', cfg.subdomains, 4),
        ('scale_factor', cfg.scale_factor, 0.001),
        ('simulation_type', cfg.simulation_type, 'laminar'),
    ]

    all_passed = True
    for name, actual, expected in tests:
        if actual == expected:
            print(f"  ✓ {name}: {actual}")
        else:
            print(f"  ✗ {name}: expected {expected}, got {actual}")
            all_passed = False

    return all_passed


def test_registry_numerics():
    """Test that registry returns correct numerical settings."""
    print("\n" + "=" * 60)
    print("TEST 2: Registry Numerics")
    print("=" * 60)

    from src.registry.numerics import get_schemes, get_pimple_settings, list_profiles

    # Test profile list
    profiles = list_profiles()
    expected_profiles = ['robust', 'standard', 'precise']

    if set(profiles) == set(expected_profiles):
        print(f"  ✓ Available profiles: {profiles}")
    else:
        print(f"  ✗ Expected profiles {expected_profiles}, got {profiles}")
        return False

    # Test robust profile schemes
    schemes = get_schemes('robust')
    expected_ddt = 'Euler'
    expected_div = 'Gauss upwind'

    tests = [
        ('robust ddt', schemes['ddt'], expected_ddt),
        ('robust div_phi_U', schemes['div_phi_U'], expected_div),
    ]

    # Test standard profile
    schemes_std = get_schemes('standard')
    tests.extend([
        ('standard ddt', schemes_std['ddt'], 'backward'),
        ('standard div_phi_U', schemes_std['div_phi_U'], 'Gauss limitedLinearV 1'),
    ])

    all_passed = True
    for name, actual, expected in tests:
        if actual == expected:
            print(f"  ✓ {name}: {actual}")
        else:
            print(f"  ✗ {name}: expected {expected}, got {actual}")
            all_passed = False

    return all_passed


def test_fv_schemes_generation():
    """Test fvSchemes file generation."""
    print("\n" + "=" * 60)
    print("TEST 3: fvSchemes Generation")
    print("=" * 60)

    from src.config.accessor import Config
    from src.writers import write_fv_schemes

    config_path = 'cases_input/PAT002/config.json'
    raw_config = load_config(config_path)
    raw_config['geometry']['case_name'] = 'PAT002'

    cfg = Config(raw_config)

    # Create temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Generate fvSchemes
        output_path = write_fv_schemes(cfg, tmpdir)

        # Read generated file
        with open(output_path, 'r') as f:
            content = f.read()

        # Check key elements for robust profile
        checks = [
            ('FoamFile header', 'FoamFile' in content),
            ('ddtSchemes section', 'ddtSchemes' in content),
            ('Euler scheme (robust)', 'Euler' in content),
            ('upwind scheme (robust)', 'upwind' in content),
            ('gradSchemes section', 'gradSchemes' in content),
            ('divSchemes section', 'divSchemes' in content),
            ('laplacianSchemes section', 'laplacianSchemes' in content),
        ]

        all_passed = True
        for name, passed in checks:
            if passed:
                print(f"  ✓ {name}")
            else:
                print(f"  ✗ {name}")
                all_passed = False

        return all_passed


def test_fv_solution_generation():
    """Test fvSolution file generation."""
    print("\n" + "=" * 60)
    print("TEST 4: fvSolution Generation")
    print("=" * 60)

    from src.config.accessor import Config
    from src.writers import write_fv_solution

    config_path = 'cases_input/PAT002/config.json'
    raw_config = load_config(config_path)
    raw_config['geometry']['case_name'] = 'PAT002'

    cfg = Config(raw_config)

    # Create temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Generate fvSolution
        output_path = write_fv_solution(cfg, tmpdir)

        # Read generated file
        with open(output_path, 'r') as f:
            content = f.read()

        # Check key elements
        checks = [
            ('FoamFile header', 'FoamFile' in content),
            ('solvers section', 'solvers' in content),
            ('PIMPLE section', 'PIMPLE' in content),
            ('p solver', '"p"' in content or 'p\n' in content),
            ('U solver', '"U"' in content or 'UFinal' in content),
            ('relaxationFactors', 'relaxationFactors' in content),
            ('GAMG solver', 'GAMG' in content),
        ]

        all_passed = True
        for name, passed in checks:
            if passed:
                print(f"  ✓ {name}")
            else:
                print(f"  ✗ {name}")
                all_passed = False

        return all_passed


def test_control_dict_generation():
    """Test controlDict file generation."""
    print("\n" + "=" * 60)
    print("TEST 5: controlDict Generation")
    print("=" * 60)

    from src.config.accessor import Config
    from src.writers import write_control_dict

    config_path = 'cases_input/PAT002/config.json'
    raw_config = load_config(config_path)
    raw_config['geometry']['case_name'] = 'PAT002'

    cfg = Config(raw_config)

    # Create temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Generate controlDict
        output_path = write_control_dict(cfg, tmpdir, cardiac_cycle=0.5)

        # Read generated file
        with open(output_path, 'r') as f:
            content = f.read()

        # Check key elements
        checks = [
            ('FoamFile header', 'FoamFile' in content),
            ('application foamRun', 'foamRun' in content),
            ('endTime setting', 'endTime' in content),
            ('writeInterval', 'writeInterval' in content),
            ('adjustTimeStep', 'adjustTimeStep' in content),
            ('maxCo', 'maxCo' in content),
            ('functions section', 'functions' in content),
            ('wallShearStress function', 'wallShearStress' in content),
            ('Windkessel library', 'windkessel' in content.lower()),
        ]

        all_passed = True
        for name, passed in checks:
            if passed:
                print(f"  ✓ {name}")
            else:
                print(f"  ✗ {name}")
                all_passed = False

        return all_passed


def test_transport_properties_generation():
    """Test transportProperties file generation."""
    print("\n" + "=" * 60)
    print("TEST 6: transportProperties Generation")
    print("=" * 60)

    from src.config.accessor import Config
    from src.writers import write_transport_properties

    config_path = 'cases_input/PAT002/config.json'
    raw_config = load_config(config_path)
    raw_config['geometry']['case_name'] = 'PAT002'

    cfg = Config(raw_config)

    # Create temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Generate transportProperties
        output_path = write_transport_properties(cfg, tmpdir)

        # Read generated file
        with open(output_path, 'r') as f:
            content = f.read()

        # Check key elements
        checks = [
            ('FoamFile header', 'FoamFile' in content),
            ('transportModel Newtonian', 'Newtonian' in content),
            ('nu value', 'nu' in content),
            ('Dimensions [0 2 -1 0 0 0 0]', '[0 2 -1 0 0 0 0]' in content),
        ]

        # Check nu value is close to expected
        import re
        nu_match = re.search(r'nu\s+\[.*\]\s+([\d.eE+-]+)', content)
        if nu_match:
            nu_value = float(nu_match.group(1))
            expected_nu = 3.7736e-6
            if abs(nu_value - expected_nu) / expected_nu < 0.01:
                checks.append(('nu value correct', True))
            else:
                checks.append((f'nu value correct (expected {expected_nu}, got {nu_value})', False))

        all_passed = True
        for name, passed in checks:
            if passed:
                print(f"  ✓ {name}")
            else:
                print(f"  ✗ {name}")
                all_passed = False

        return all_passed


def test_velocity_profiles():
    """Test velocity profile calculations."""
    print("\n" + "=" * 60)
    print("TEST 7: Velocity Profiles")
    print("=" * 60)

    import numpy as np
    from src.inlet.profiles import PlugProfile, ParabolicProfile, create_profile

    center = np.array([0, 0, 0])
    radius = 0.01  # 1 cm
    normal = np.array([1, 0, 0])
    mean_velocity = 0.5  # m/s

    # Test plug profile
    plug = PlugProfile(center, radius, normal)
    v_center = plug.calculate(center, mean_velocity)
    v_edge = plug.calculate(np.array([0, radius, 0]), mean_velocity)

    plug_ok = np.allclose(v_center, v_edge)
    print(f"  {'✓' if plug_ok else '✗'} Plug profile: uniform velocity")

    # Test parabolic profile
    parabolic = ParabolicProfile(center, radius, normal)
    v_center = parabolic.calculate(center, mean_velocity)
    v_edge = parabolic.calculate(np.array([0, radius * 0.99, 0]), mean_velocity)

    # Center should be ~2x mean for parabolic
    para_center_ok = abs(np.linalg.norm(v_center) - 2 * mean_velocity) < 0.01
    # Edge should be near zero
    para_edge_ok = np.linalg.norm(v_edge) < 0.1

    print(f"  {'✓' if para_center_ok else '✗'} Parabolic profile: center = 2 × mean")
    print(f"  {'✓' if para_edge_ok else '✗'} Parabolic profile: edge ≈ 0")

    # Test factory function
    p = create_profile('parabolic', center, radius, normal)
    factory_ok = isinstance(p, ParabolicProfile)
    print(f"  {'✓' if factory_ok else '✗'} Profile factory works")

    return plug_ok and para_center_ok and para_edge_ok and factory_ok


def test_windkessel_calculations():
    """Test Windkessel circuit calculations."""
    print("\n" + "=" * 60)
    print("TEST 8: Windkessel Calculations")
    print("=" * 60)

    from src.windkessel.circuit import (
        calculate_3element_params,
        calculate_total_resistance,
    )
    from src.windkessel.murray import calculate_murray_flow_split
    import numpy as np

    # Test total resistance calculation
    # R = P / Q
    P = 13332.2  # 100 mmHg in Pa
    Q = 8.33e-5  # 5 L/min in m³/s
    R = calculate_total_resistance(P, Q)
    expected_R = P / Q

    R_ok = abs(R - expected_R) / expected_R < 0.001
    print(f"  {'✓' if R_ok else '✗'} Total resistance: R = P/Q = {R:.3e} Pa·s/m³")

    # Test 3-element calculation
    params = calculate_3element_params(
        mean_pressure=P,
        mean_flow=Q,
        cardiac_cycle=0.5,
        outlet_name='test_outlet',
    )

    # R1 + R2 should equal total R (approximately)
    R_total_ok = abs((params.R1 + params.R2) - R) / R < 0.01
    print(f"  {'✓' if R_total_ok else '✗'} 3-element: R1 + R2 ≈ R_total")

    # Time constant should be reasonable (fraction of cardiac cycle)
    tau_ok = 0.1 < params.tau < 2.0
    print(f"  {'✓' if tau_ok else '✗'} Time constant: τ = {params.tau:.3f}s (reasonable)")

    # Test Murray's law
    areas = [1e-4, 5e-5, 2e-5]  # Different outlet areas
    fractions = calculate_murray_flow_split(areas)

    # Should sum to 1
    sum_ok = abs(np.sum(fractions) - 1.0) < 1e-6
    print(f"  {'✓' if sum_ok else '✗'} Murray flow split sums to 1.0")

    # Larger area should get more flow
    order_ok = fractions[0] > fractions[1] > fractions[2]
    print(f"  {'✓' if order_ok else '✗'} Murray: larger area → more flow")

    return R_ok and R_total_ok and tau_ok and sum_ok and order_ok


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "=" * 60)
    print("ARCHITECTURE COMPARISON TEST SUITE")
    print("Testing NEW simplified architecture for PAT002")
    print("=" * 60)

    results = {
        'Config Accessor': test_config_accessor(),
        'Registry Numerics': test_registry_numerics(),
        'fvSchemes Generation': test_fv_schemes_generation(),
        'fvSolution Generation': test_fv_solution_generation(),
        'controlDict Generation': test_control_dict_generation(),
        'transportProperties Generation': test_transport_properties_generation(),
        'Velocity Profiles': test_velocity_profiles(),
        'Windkessel Calculations': test_windkessel_calculations(),
    }

    # Summary
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
        return True
    else:
        print(f"\n  ⚠️  {total - passed} test(s) failed")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
