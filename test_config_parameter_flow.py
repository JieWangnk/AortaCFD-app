#!/usr/bin/env python3
"""
Test script to verify config parameter flow from user config → profile → final config
Tests each parameter to ensure proper override behavior.
"""

import json
import sys
import os
sys.path.insert(0, 'src')

from patient_runner.core import PatientCaseRunner

def test_parameter_flow():
    """Test that user config properly overrides profile defaults"""

    # Load user config
    config_path = 'cases_input/patient1/config_simple_rans_medium.json'
    with open(config_path) as f:
        user_config = json.load(f)

    # Initialize runner and prepare config
    runner = PatientCaseRunner()
    case_info = runner.load_patient_case('patient1', config_path)
    result = runner.prepare_simulation(case_info, {})
    final_config = result['config']

    # Test results
    tests_passed = []
    tests_failed = []

    print("=" * 80)
    print("CONFIG PARAMETER FLOW VERIFICATION TEST")
    print("=" * 80)
    print(f"\nUser Config: {config_path}")
    print(f"Profile Selected: {result.get('profile_key', 'N/A')}")
    print("\n" + "-" * 80)

    # TEST 1: Physics Parameters
    print("\n📋 TEST 1: PHYSICS PARAMETERS")
    print("-" * 80)

    user_density = user_config.get('physics', {}).get('blood_density')
    user_viscosity = user_config.get('physics', {}).get('blood_viscosity')

    final_rho = final_config['physics'].get('rho')
    final_mu = final_config['physics'].get('mu')
    final_nu = final_config['physics'].get('nu')

    print(f"  User blood_density:     {user_density} kg/m³")
    print(f"  Final rho:              {final_rho} kg/m³")

    if user_density == final_rho:
        print("  ✅ Density override works!")
        tests_passed.append("Physics: blood_density → rho")
    else:
        print(f"  ❌ Density mismatch! Expected {user_density}, got {final_rho}")
        tests_failed.append("Physics: blood_density → rho")

    print(f"\n  User blood_viscosity:   {user_viscosity} Pa·s")
    print(f"  Final mu:               {final_mu} Pa·s")

    if user_viscosity == final_mu:
        print("  ✅ Viscosity override works!")
        tests_passed.append("Physics: blood_viscosity → mu")
    else:
        print(f"  ❌ Viscosity mismatch! Expected {user_viscosity}, got {final_mu}")
        tests_failed.append("Physics: blood_viscosity → mu")

    expected_nu = user_viscosity / user_density
    print(f"\n  Calculated nu:          {expected_nu:.6e} m²/s")
    print(f"  Final nu:               {final_nu:.6e} m²/s")

    if abs(expected_nu - final_nu) < 1e-10:
        print("  ✅ Kinematic viscosity calculation correct!")
        tests_passed.append("Physics: nu calculation")
    else:
        print(f"  ❌ nu calculation error!")
        tests_failed.append("Physics: nu calculation")

    # Profile-provided parameters
    print(f"\n  Profile turbulence_model: {final_config['physics'].get('turbulence_model')}")
    print(f"  Profile simulation_type:  {final_config['physics'].get('simulation_type')}")

    # TEST 2: Mesh Settings
    print("\n\n📋 TEST 2: MESH SETTINGS")
    print("-" * 80)

    user_cell_size = user_config.get('mesh', {}).get('mesh_resolution', {}).get('target_cell_size_mm')
    final_cell_size = final_config.get('mesh', {}).get('mesh_resolution', {}).get('target_cell_size_mm')

    print(f"  User target_cell_size_mm: {user_cell_size}")
    print(f"  Final target_cell_size_mm: {final_cell_size}")

    if user_cell_size == final_cell_size:
        print("  ✅ Mesh resolution override works!")
        tests_passed.append("Mesh: target_cell_size_mm")
    else:
        print(f"  ❌ Mesh resolution mismatch!")
        tests_failed.append("Mesh: target_cell_size_mm")

    user_parallel = user_config.get('mesh', {}).get('SNAPPY_SETTINGS', {}).get('parallel')
    final_parallel = final_config.get('mesh', {}).get('SNAPPY_SETTINGS', {}).get('parallel')

    print(f"\n  User SNAPPY parallel:     {user_parallel}")
    print(f"  Final SNAPPY parallel:    {final_parallel}")

    if user_parallel == final_parallel:
        print("  ✅ SNAPPY parallel override works!")
        tests_passed.append("Mesh: SNAPPY_SETTINGS.parallel")
    else:
        print(f"  ❌ SNAPPY parallel mismatch!")
        tests_failed.append("Mesh: SNAPPY_SETTINGS.parallel")

    # TEST 3: Run Settings (CRITICAL FIX)
    print("\n\n📋 TEST 3: RUN SETTINGS (CRITICAL)")
    print("-" * 80)

    user_solution_type = user_config.get('run_settings', {}).get('solution_type')
    final_solution_type = final_config.get('run_settings', {}).get('solution_type')

    print(f"  User solution_type:       '{user_solution_type}'")
    print(f"  Final solution_type:      '{final_solution_type}'")
    print(f"  Profile default:          'parallel' (4 cores)")

    if user_solution_type == final_solution_type:
        print("  ✅ Solution type override works! (FIX VERIFIED)")
        tests_passed.append("RunSettings: solution_type")
    else:
        print(f"  ❌ Solution type NOT overridden! BUG STILL EXISTS!")
        tests_failed.append("RunSettings: solution_type")

    user_subdomains = user_config.get('run_settings', {}).get('subdomains')
    final_subdomains = final_config.get('run_settings', {}).get('subdomains')

    print(f"\n  User subdomains:          {user_subdomains}")
    print(f"  Final subdomains:         {final_subdomains}")
    print(f"  Profile default:          4")

    if user_subdomains == final_subdomains:
        print("  ✅ Subdomains override works!")
        tests_passed.append("RunSettings: subdomains")
    else:
        print(f"  ❌ Subdomains NOT overridden!")
        tests_failed.append("RunSettings: subdomains")

    # TEST 4: Simulation Control
    print("\n\n📋 TEST 4: SIMULATION CONTROL")
    print("-" * 80)

    user_end_time = user_config.get('simulation_control', {}).get('end_time')
    final_end_time = final_config.get('simulation_control', {}).get('end_time')

    print(f"  User end_time:            '{user_end_time}'")
    print(f"  Final end_time:           '{final_end_time}'")

    if user_end_time == final_end_time:
        print("  ✅ End time override works!")
        tests_passed.append("SimControl: end_time")
    else:
        print(f"  ❌ End time mismatch!")
        tests_failed.append("SimControl: end_time")

    user_cycles = user_config.get('simulation_control', {}).get('number_of_cycles')
    final_cycles = final_config.get('simulation_control', {}).get('number_of_cycles')

    print(f"\n  User number_of_cycles:    {user_cycles}")
    print(f"  Final number_of_cycles:   {final_cycles}")

    if user_cycles == final_cycles:
        print("  ✅ Number of cycles override works!")
        tests_passed.append("SimControl: number_of_cycles")
    else:
        print(f"  ❌ Number of cycles mismatch!")
        tests_failed.append("SimControl: number_of_cycles")

    # TEST 5: Boundary Conditions
    print("\n\n📋 TEST 5: BOUNDARY CONDITIONS")
    print("-" * 80)

    # Note: Final config stores BCs in FLAT format (inlet, outlets) for backward compatibility
    # User provides nested format (boundary_conditions.inlet) which gets flattened
    user_inlet_type = user_config.get('boundary_conditions', {}).get('inlet', {}).get('type')
    final_inlet_type = final_config.get('inlet', {}).get('type')  # Flat format!

    print(f"  User inlet type:          '{user_inlet_type}'")
    print(f"  Final inlet type:         '{final_inlet_type}'")
    print(f"  Note: Config uses flat format (inlet) not nested (boundary_conditions.inlet)")

    if user_inlet_type == final_inlet_type:
        print("  ✅ Inlet BC override works!")
        tests_passed.append("BC: inlet.type")
    else:
        print(f"  ❌ Inlet BC mismatch!")
        tests_failed.append("BC: inlet.type")

    user_outlet_type = user_config.get('boundary_conditions', {}).get('outlets', {}).get('type')
    final_outlet_type = final_config.get('outlets', {}).get('type')  # Flat format!

    print(f"\n  User outlet type:         '{user_outlet_type}'")
    print(f"  Final outlet type:        '{final_outlet_type}'")

    if user_outlet_type == final_outlet_type:
        print("  ✅ Outlet BC override works!")
        tests_passed.append("BC: outlets.type")
    else:
        print(f"  ❌ Outlet BC mismatch!")
        tests_failed.append("BC: outlets.type")

    # Check Windkessel settings
    user_wk = user_config.get('boundary_conditions', {}).get('outlets', {}).get('windkessel_settings', {})
    final_wk = final_config.get('outlets', {}).get('windkessel_settings', {})  # Flat format!

    if user_wk:
        print(f"\n  User WK methodology:      '{user_wk.get('methodology')}'")
        print(f"  Final WK methodology:     '{final_wk.get('methodology')}'")

        if user_wk.get('methodology') == final_wk.get('methodology'):
            print("  ✅ Windkessel settings override works!")
            tests_passed.append("BC: windkessel_settings")
        else:
            print(f"  ❌ Windkessel settings mismatch!")
            tests_failed.append("BC: windkessel_settings")

    # TEST 6: Geometry
    print("\n\n📋 TEST 6: GEOMETRY SETTINGS")
    print("-" * 80)

    user_scale = user_config.get('geometry', {}).get('scale_factor')
    final_scale = final_config.get('geometry', {}).get('scale_factor')

    print(f"  User scale_factor:        {user_scale}")
    print(f"  Final scale_factor:       {final_scale}")

    if user_scale == final_scale:
        print("  ✅ Scale factor override works!")
        tests_passed.append("Geometry: scale_factor")
    else:
        print(f"  ❌ Scale factor mismatch!")
        tests_failed.append("Geometry: scale_factor")

    # Auto-discovered patches
    print(f"\n  Auto-discovered inlet:    '{final_config.get('geometry', {}).get('inlet_keywords_ordered')}'")
    print(f"  Auto-discovered outlets:  {final_config.get('geometry', {}).get('outlet_keywords_ordered')}")
    print(f"  Auto-discovered walls:    '{final_config.get('geometry', {}).get('wall_keywords_ordered')}'")

    # FINAL SUMMARY
    print("\n\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    total_tests = len(tests_passed) + len(tests_failed)
    print(f"\nTotal Tests: {total_tests}")
    print(f"✅ Passed: {len(tests_passed)}")
    print(f"❌ Failed: {len(tests_failed)}")

    if tests_passed:
        print("\n✅ Passed Tests:")
        for test in tests_passed:
            print(f"   • {test}")

    if tests_failed:
        print("\n❌ Failed Tests:")
        for test in tests_failed:
            print(f"   • {test}")

    print("\n" + "=" * 80)

    # Return exit code
    if tests_failed:
        print("\n⚠️  Some tests FAILED! Check parameter override logic.")
        return 1
    else:
        print("\n🎉 All tests PASSED! Parameter flow is working correctly.")
        return 0

if __name__ == "__main__":
    exit_code = test_parameter_flow()
    sys.exit(exit_code)
