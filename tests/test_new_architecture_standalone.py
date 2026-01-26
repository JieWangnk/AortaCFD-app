#!/usr/bin/env python3
"""
Standalone test for NEW simplified architecture modules.

This test runs independently without relying on existing package structure.

Usage:
    cd /path/to/AortaCFD-app
    python3 tests/test_new_architecture_standalone.py
"""

import os
import sys
import json
import tempfile
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


def load_config(config_path: str) -> dict:
    """Load JSON config file."""
    with open(config_path, 'r') as f:
        return json.load(f)


def test_config_accessor():
    """Test that Config accessor returns correct values."""
    print("\n" + "=" * 60)
    print("TEST 1: Config Accessor")
    print("=" * 60)

    # Load the accessor module directly
    accessor_path = PROJECT_ROOT / "src" / "config" / "accessor.py"
    accessor = load_module(accessor_path, "accessor")
    Config = accessor.Config

    config_path = PROJECT_ROOT / 'cases_input' / 'PAT002' / 'config.json'
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

    # Load the numerics module directly
    numerics_path = PROJECT_ROOT / "src" / "registry" / "numerics.py"
    numerics = load_module(numerics_path, "numerics")

    get_schemes = numerics.get_schemes
    get_pimple_settings = numerics.get_pimple_settings
    list_profiles = numerics.list_profiles

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
    tests = [
        ('robust ddt', schemes['ddt'], 'Euler'),
        ('robust div_phi_U', schemes['div_phi_U'], 'Gauss upwind'),
    ]

    # Test standard profile
    schemes_std = get_schemes('standard')
    tests.extend([
        ('standard ddt', schemes_std['ddt'], 'backward'),
        ('standard div_phi_U', schemes_std['div_phi_U'], 'Gauss limitedLinearV 1'),
    ])

    # Test precise profile
    schemes_precise = get_schemes('precise')
    tests.extend([
        ('precise ddt', schemes_precise['ddt'], 'CrankNicolson 0.9'),
        ('precise div_phi_U', schemes_precise['div_phi_U'], 'Gauss LUST grad(U)'),
    ])

    all_passed = True
    for name, actual, expected in tests:
        if actual == expected:
            print(f"  ✓ {name}: {actual}")
        else:
            print(f"  ✗ {name}: expected {expected}, got {actual}")
            all_passed = False

    return all_passed


def test_registry_physics():
    """Test physics registry."""
    print("\n" + "=" * 60)
    print("TEST 3: Registry Physics")
    print("=" * 60)

    physics_path = PROJECT_ROOT / "src" / "registry" / "physics.py"
    physics = load_module(physics_path, "physics")

    BLOOD_PROPERTIES = physics.BLOOD_PROPERTIES

    tests = [
        ('density', BLOOD_PROPERTIES['density'], 1060.0),
        ('dynamic_viscosity', BLOOD_PROPERTIES['dynamic_viscosity'], 0.004),
    ]

    # Check kinematic viscosity is correct: nu = mu / rho
    expected_nu = 0.004 / 1060.0
    actual_nu = BLOOD_PROPERTIES['kinematic_viscosity']
    nu_ok = abs(actual_nu - expected_nu) / expected_nu < 0.01
    tests.append(('kinematic_viscosity', nu_ok, True))

    all_passed = True
    for name, actual, expected in tests:
        if actual == expected:
            print(f"  ✓ {name}: {actual}")
        else:
            print(f"  ✗ {name}: expected {expected}, got {actual}")
            all_passed = False

    return all_passed


def test_velocity_profiles():
    """Test velocity profile calculations."""
    print("\n" + "=" * 60)
    print("TEST 4: Velocity Profiles")
    print("=" * 60)

    import numpy as np

    profiles_path = PROJECT_ROOT / "src" / "inlet" / "profiles.py"
    profiles = load_module(profiles_path, "profiles")

    PlugProfile = profiles.PlugProfile
    ParabolicProfile = profiles.ParabolicProfile
    create_profile = profiles.create_profile

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

    print(f"  {'✓' if para_center_ok else '✗'} Parabolic profile: center = 2 × mean (got {np.linalg.norm(v_center):.3f})")
    print(f"  {'✓' if para_edge_ok else '✗'} Parabolic profile: edge ≈ 0 (got {np.linalg.norm(v_edge):.3f})")

    # Test factory function
    p = create_profile('parabolic', center, radius, normal)
    factory_ok = isinstance(p, ParabolicProfile)
    print(f"  {'✓' if factory_ok else '✗'} Profile factory works")

    return plug_ok and para_center_ok and para_edge_ok and factory_ok


def test_windkessel_calculations():
    """Test Windkessel circuit calculations."""
    print("\n" + "=" * 60)
    print("TEST 5: Windkessel Calculations")
    print("=" * 60)

    import numpy as np

    circuit_path = PROJECT_ROOT / "src" / "windkessel" / "circuit.py"
    circuit = load_module(circuit_path, "circuit")

    murray_path = PROJECT_ROOT / "src" / "windkessel" / "murray.py"
    murray = load_module(murray_path, "murray")

    calculate_3element_params = circuit.calculate_3element_params
    calculate_total_resistance = circuit.calculate_total_resistance
    calculate_murray_flow_split = murray.calculate_murray_flow_split

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


def test_openfoam_header():
    """Test OpenFOAM header generation."""
    print("\n" + "=" * 60)
    print("TEST 6: OpenFOAM Header Generation")
    print("=" * 60)

    header_path = PROJECT_ROOT / "src" / "writers" / "header.py"
    header = load_module(header_path, "header")

    openfoam_header = header.openfoam_header

    # Generate a header
    h = openfoam_header("dictionary", "fvSchemes")

    checks = [
        ('Contains FoamFile', 'FoamFile' in h),
        ('Contains version', 'version' in h),
        ('Contains format', 'format' in h),
        ('Contains class dictionary', 'dictionary' in h),
        ('Contains object fvSchemes', 'fvSchemes' in h),
        ('Contains location system', '"system"' in h),
    ]

    all_passed = True
    for name, passed in checks:
        if passed:
            print(f"  ✓ {name}")
        else:
            print(f"  ✗ {name}")
            all_passed = False

    return all_passed


def test_csv_reader():
    """Test CSV flow waveform reader."""
    print("\n" + "=" * 60)
    print("TEST 7: CSV Flow Reader")
    print("=" * 60)

    csv_path = PROJECT_ROOT / "src" / "inlet" / "csv_reader.py"
    csv_reader = load_module(csv_path, "csv_reader")

    read_flow_csv = csv_reader.read_flow_csv

    # Read the PAT002 BPM120 CSV
    csv_file = PROJECT_ROOT / 'cases_input' / 'PAT002' / 'BPM120.csv'

    try:
        flow_data = read_flow_csv(str(csv_file), data_type='flow_rate')

        checks = [
            ('Has time data', len(flow_data.times) > 0),
            ('Has value data', len(flow_data.values) > 0),
            ('Same length', len(flow_data.times) == len(flow_data.values)),
            ('Positive cardiac cycle', flow_data.cardiac_cycle > 0),
            ('Times start at 0', abs(flow_data.times[0]) < 0.001),
        ]

        # Check cardiac cycle is approximately 0.5s (120 BPM)
        expected_cycle = 0.5
        cycle_ok = abs(flow_data.cardiac_cycle - expected_cycle) < 0.1
        checks.append(('Cardiac cycle ≈ 0.5s', cycle_ok))

        all_passed = True
        for name, passed in checks:
            if passed:
                print(f"  ✓ {name}")
            else:
                print(f"  ✗ {name}")
                all_passed = False

        print(f"  Info: {len(flow_data.times)} points, cycle={flow_data.cardiac_cycle:.3f}s")

        return all_passed

    except Exception as e:
        print(f"  ✗ Failed to read CSV: {e}")
        return False


def test_config_generator():
    """Test config template generator."""
    print("\n" + "=" * 60)
    print("TEST 8: Config Generator")
    print("=" * 60)

    generator_path = PROJECT_ROOT / "src" / "config" / "generator.py"

    # Need to first load registry modules that generator depends on
    numerics_path = PROJECT_ROOT / "src" / "registry" / "numerics.py"
    physics_path = PROJECT_ROOT / "src" / "registry" / "physics.py"
    mesh_path = PROJECT_ROOT / "src" / "registry" / "mesh.py"

    # Load as src.registry.* to match import statements
    sys.modules['src'] = type(sys)('src')
    sys.modules['src.registry'] = type(sys)('src.registry')
    sys.modules['src.registry.numerics'] = load_module(numerics_path, "src.registry.numerics")
    sys.modules['src.registry.physics'] = load_module(physics_path, "src.registry.physics")
    sys.modules['src.registry.mesh'] = load_module(mesh_path, "src.registry.mesh")

    generator = load_module(generator_path, "generator")

    generate_config = generator.generate_config
    list_available_profiles = generator.list_available_profiles

    # Test profile list
    profiles = list_available_profiles()
    profiles_ok = set(profiles) == {'robust', 'standard', 'precise'}
    print(f"  {'✓' if profiles_ok else '✗'} Available profiles: {profiles}")

    # Generate config for standard profile
    config = generate_config('standard', case_name='TEST_CASE')

    checks = [
        ('Has geometry', 'geometry' in config),
        ('Has numerics', 'numerics' in config),
        ('Has boundary_conditions', 'boundary_conditions' in config),
        ('Has physics', 'physics' in config),
        ('Case name correct', config.get('geometry', {}).get('case_name') == 'TEST_CASE'),
        ('Profile correct', config.get('numerics', {}).get('profile') == 'standard'),
    ]

    all_passed = profiles_ok
    for name, passed in checks:
        if passed:
            print(f"  ✓ {name}")
        else:
            print(f"  ✗ {name}")
            all_passed = False

    return all_passed


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "=" * 60)
    print("SIMPLIFIED ARCHITECTURE TEST SUITE")
    print("Testing modules for PAT002 case compatibility")
    print("=" * 60)

    results = {}

    # Run each test in try/except to continue even if one fails
    test_functions = [
        ('Config Accessor', test_config_accessor),
        ('Registry Numerics', test_registry_numerics),
        ('Registry Physics', test_registry_physics),
        ('Velocity Profiles', test_velocity_profiles),
        ('Windkessel Calculations', test_windkessel_calculations),
        ('OpenFOAM Header', test_openfoam_header),
        ('CSV Flow Reader', test_csv_reader),
        ('Config Generator', test_config_generator),
    ]

    for name, test_func in test_functions:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n  ✗ {name} EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False

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
        print("  The new simplified architecture produces correct results.")
        return True
    else:
        print(f"\n  ⚠️  {total - passed} test(s) failed")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
