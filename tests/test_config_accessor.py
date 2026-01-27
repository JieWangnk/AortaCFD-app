# tests/test_config_accessor.py
"""
Comprehensive test for Config accessor.

Tests that all configuration properties are accessible and return expected values.
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config.accessor import Config, wrap_config


def load_full_config():
    """Load the full example config."""
    config_path = Path(__file__).parent.parent / 'examples' / 'config_full.json'
    with open(config_path) as f:
        return json.load(f)


def test_raw_access():
    """Test raw dictionary access methods."""
    config = {"test": "value", "nested": {"key": "nested_value"}}
    cfg = Config(config)

    assert cfg.get("test") == "value"
    assert cfg.get("missing", "default") == "default"
    assert cfg["test"] == "value"
    assert "test" in cfg
    assert "missing" not in cfg
    assert cfg.to_dict() == config
    assert cfg.get_nested("nested", "key") == "nested_value"
    assert cfg.get_nested("nested", "missing", default="fallback") == "fallback"
    print("✓ Raw access methods working")


def test_case_info():
    """Test case info/metadata properties."""
    cfg = Config(load_full_config())

    # case_info section
    assert isinstance(cfg.case_info, dict)
    assert cfg.patient_id == "EXAMPLE"
    assert isinstance(cfg.case_notes, str)
    print("✓ Case info properties working")


def test_geometry_properties():
    """Test geometry configuration properties."""
    cfg = Config(load_full_config())

    # Geometry section
    assert isinstance(cfg.geometry, dict)
    assert isinstance(cfg.case_name, str)  # May be empty if not specified
    assert cfg.scale_factor == 0.001
    assert cfg.inlet_patch_name == "inlet"
    assert isinstance(cfg.outlet_patch_names, list)
    assert "outlet" in cfg.outlet_patch_names[0]
    assert cfg.wall_patch_name == "wall_aorta"
    assert cfg.reference_radius_strategy in ["inlet", "minimum", "average"]
    print("✓ Geometry properties working")


def test_inlet_bc_properties():
    """Test inlet boundary condition properties."""
    cfg = Config(load_full_config())

    # Inlet section
    assert isinstance(cfg.inlet, dict)
    assert cfg.inlet_type in ["CONSTANT", "PARABOLIC", "TIMEVARYING", "WOMERSLEY", "MRI"]
    assert cfg.inlet_velocity is None or isinstance(cfg.inlet_velocity, (int, float))
    assert cfg.inlet_cardiac_output is None or isinstance(cfg.inlet_cardiac_output, (int, float))
    assert cfg.inlet_csv_file is None or isinstance(cfg.inlet_csv_file, str)
    assert cfg.inlet_data_type in ["velocity", "flowrate"]
    assert cfg.inlet_velocity_profile in ["plug", "parabolic", "elliptical", "wall_distance", "womersley"]
    assert isinstance(cfg.inlet_profile_exponent, (int, float))
    assert cfg.inlet_n_harmonics == "auto" or isinstance(cfg.inlet_n_harmonics, int)
    assert cfg.inlet_mri_file is None or isinstance(cfg.inlet_mri_file, str)
    assert isinstance(cfg.is_pulsatile, bool)
    print("✓ Inlet BC properties working")


def test_outlet_bc_properties():
    """Test outlet boundary condition properties."""
    cfg = Config(load_full_config())

    # Outlet section
    assert isinstance(cfg.outlets, dict)
    assert isinstance(cfg.outlet_type, str)
    assert isinstance(cfg.is_windkessel, bool)

    # Windkessel settings
    assert isinstance(cfg.windkessel_settings, dict)
    assert isinstance(cfg.windkessel_systolic_pressure, (int, float))
    assert isinstance(cfg.windkessel_diastolic_pressure, (int, float))
    assert isinstance(cfg.windkessel_venous_pressure, (int, float))
    assert isinstance(cfg.windkessel_tau, (int, float))
    assert isinstance(cfg.windkessel_betaT, (int, float))
    assert isinstance(cfg.windkessel_betaN, (int, float))
    assert cfg.windkessel_flow_split is None or isinstance(cfg.windkessel_flow_split, (dict, float))
    assert cfg.windkessel_order in [1, 2, 3]
    assert cfg.windkessel_coupling_mode in ["implicit", "explicit"]
    assert isinstance(cfg.windkessel_enable_stabilization, bool)
    assert cfg.windkessel_initial_pressure_method in ["diastolic", "systolic", "MAP", "zero"]
    assert cfg.windkessel_outlet_parameters is None or isinstance(cfg.windkessel_outlet_parameters, dict)
    assert cfg.windkessel_pwv_method in ["matlab", "empirical", "fixed"]
    assert cfg.windkessel_pwv is None or isinstance(cfg.windkessel_pwv, (int, float))
    print("✓ Outlet BC (Windkessel) properties working")


def test_wall_bc_properties():
    """Test wall boundary condition properties."""
    cfg = Config(load_full_config())

    # Wall section
    assert isinstance(cfg.walls, dict)
    assert cfg.wall_type in ["no_slip", "slip", "moving_wall"]
    print("✓ Wall BC properties working")


def test_physics_properties():
    """Test physics configuration properties."""
    cfg = Config(load_full_config())

    # Physics section
    assert isinstance(cfg.physics, dict)
    assert cfg.simulation_type in ["laminar", "rans", "les"]
    assert isinstance(cfg.is_turbulent, bool)
    assert isinstance(cfg.is_les, bool)
    assert isinstance(cfg.nu, float)
    assert isinstance(cfg.rho, (int, float))
    assert isinstance(cfg.turbulence_intensity, float)
    assert isinstance(cfg.turbulence_model, str)
    assert isinstance(cfg.les_model, str)
    assert cfg.physics_model in ["laminar", "rans", "les"]
    print("✓ Physics properties working")


def test_numerics_properties():
    """Test numerics configuration properties."""
    cfg = Config(load_full_config())

    # Numerics section
    assert isinstance(cfg.numerics, dict)
    assert cfg.profile in ["robust", "standard", "precise"]
    assert isinstance(cfg.mesh_adaptive, bool)
    assert cfg.max_co is None or isinstance(cfg.max_co, (int, float))
    assert isinstance(cfg.adjustable_timestep, bool)
    assert isinstance(cfg.correctors, dict)
    assert isinstance(cfg.relaxation_factors, dict)
    assert isinstance(cfg.residual_control, dict)
    print("✓ Numerics properties working")


def test_mesh_properties():
    """Test mesh configuration properties."""
    cfg = Config(load_full_config())

    # Mesh section
    assert isinstance(cfg.mesh, dict)
    assert isinstance(cfg.snappy_settings, dict)
    assert isinstance(cfg.boundary_layers, dict)
    assert isinstance(cfg.mesh_resolution, dict)
    print("✓ Mesh properties working")


def test_simulation_control_properties():
    """Test simulation control properties."""
    cfg = Config(load_full_config())

    # Simulation control section
    assert isinstance(cfg.simulation_control, dict)
    assert cfg.end_time is None or isinstance(cfg.end_time, (int, float))
    assert isinstance(cfg.num_cycles, int)
    assert isinstance(cfg.control_dict, dict)
    assert isinstance(cfg.write_interval, (int, float))
    assert isinstance(cfg.cardiac_cycle, (int, float))
    assert isinstance(cfg.delta_t, (int, float))
    assert cfg.write_format in ["ascii", "binary"]
    assert isinstance(cfg.purge_write, int)
    assert isinstance(cfg.simulation_functions, dict)
    assert cfg.keep_last_cycles is None or isinstance(cfg.keep_last_cycles, int)

    # Function objects
    assert isinstance(cfg.simulation_wss_function, dict)
    assert isinstance(cfg.simulation_field_average_function, dict)
    assert isinstance(cfg.simulation_forces_function, dict)
    assert isinstance(cfg.simulation_probes_function, dict)
    print("✓ Simulation control properties working")


def test_run_settings_properties():
    """Test run settings properties."""
    cfg = Config(load_full_config())

    # Run settings section
    assert isinstance(cfg.run_settings, dict)
    assert isinstance(cfg.subdomains, int)
    assert cfg.decomposition_method in ["simple", "hierarchical", "scotch", "metis"]
    assert cfg.solution_type in ["serial", "parallel"]
    assert isinstance(cfg.is_parallel, bool)
    assert isinstance(cfg.decomposition_coeffs, dict)
    print("✓ Run settings properties working")


def test_hemodynamics_properties():
    """Test hemodynamics configuration properties."""
    cfg = Config(load_full_config())

    # Hemodynamics section
    assert isinstance(cfg.hemodynamics, dict)
    assert isinstance(cfg.runtime_functions, dict)
    assert isinstance(cfg.runtime_wss_enabled, bool)
    assert cfg.runtime_field_average in [True, False, "auto"]
    assert isinstance(cfg.runtime_velocity_field_average, bool)
    assert isinstance(cfg.runtime_pressure_monitoring, bool)

    # TAWSS settings
    assert isinstance(cfg.tawss_settings, dict)
    assert isinstance(cfg.tawss_skip_cycles, int)
    assert isinstance(cfg.tawss_periodic_restart, bool)
    assert isinstance(cfg.tawss_keep_all_cycles, bool)
    print("✓ Hemodynamics properties working")


def test_post_processing_properties():
    """Test post-processing configuration properties."""
    cfg = Config(load_full_config())

    # Post-processing section
    assert isinstance(cfg.post_processing, dict)
    assert isinstance(cfg.compute_hemodynamics_enabled, bool)

    # Extract surfaces
    assert isinstance(cfg.extract_surfaces_settings, dict)
    assert isinstance(cfg.extract_surfaces_enabled, bool)
    assert isinstance(cfg.extract_surfaces_patches, list)
    assert cfg.extract_surfaces_time_points in ["all", "last"] or isinstance(cfg.extract_surfaces_time_points, list)

    # Flow rate
    assert isinstance(cfg.compute_flow_rate_settings, dict)
    assert isinstance(cfg.compute_flow_rate_enabled, bool)
    assert isinstance(cfg.compute_flow_rate_patches, list)

    # Pressure drop
    assert isinstance(cfg.pressure_drop_settings, dict)
    assert isinstance(cfg.pressure_drop_enabled, bool)
    assert isinstance(cfg.pressure_drop_inlet_patch, str)
    assert isinstance(cfg.pressure_drop_outlet_patches, list)
    print("✓ Post-processing properties working")


def test_advanced_properties():
    """Test advanced configuration properties."""
    cfg = Config(load_full_config())

    # Advanced section
    assert isinstance(cfg.advanced, dict)
    assert isinstance(cfg.custom_templates, dict)
    assert isinstance(cfg.custom_templates_enabled, bool)
    assert isinstance(cfg.solver_overrides, dict)
    assert isinstance(cfg.momentum_predictor, bool)
    assert isinstance(cfg.pimple_consistent, bool)
    assert isinstance(cfg.turb_on_final_iter_only, bool)
    print("✓ Advanced properties working")


def test_visualization_and_openfoam_properties():
    """Test visualization and OpenFOAM properties."""
    cfg = Config(load_full_config())

    # Visualization
    assert isinstance(cfg.visualization, dict)

    # OpenFOAM settings
    assert isinstance(cfg.openfoam_version, str)
    assert isinstance(cfg.solver_application, str)
    assert isinstance(cfg.solver_module, str)
    print("✓ Visualization and OpenFOAM properties working")


def test_wrap_config():
    """Test wrap_config utility function."""
    raw_config = {"test": "value"}

    # Wrap dict
    cfg = wrap_config(raw_config)
    assert isinstance(cfg, Config)

    # Don't re-wrap Config
    cfg2 = wrap_config(cfg)
    assert cfg2 is cfg
    print("✓ wrap_config utility working")


def test_minimal_config():
    """Test that minimal config with defaults works."""
    minimal_config = {
        "geometry": {
            "case_name": "test_case"
        }
    }
    cfg = Config(minimal_config)

    # All properties should work with defaults
    assert cfg.case_name == "test_case"
    assert cfg.profile == "standard"  # Default
    assert cfg.simulation_type == "laminar"  # Default
    assert cfg.num_cycles == 3  # Default
    assert cfg.is_turbulent == False  # Default
    assert cfg.windkessel_systolic_pressure == 120  # Default
    assert cfg.tawss_skip_cycles == 2  # Default
    print("✓ Minimal config with defaults working")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("Config Accessor Comprehensive Test")
    print("=" * 60)

    tests = [
        test_raw_access,
        test_case_info,
        test_geometry_properties,
        test_inlet_bc_properties,
        test_outlet_bc_properties,
        test_wall_bc_properties,
        test_physics_properties,
        test_numerics_properties,
        test_mesh_properties,
        test_simulation_control_properties,
        test_run_settings_properties,
        test_hemodynamics_properties,
        test_post_processing_properties,
        test_advanced_properties,
        test_visualization_and_openfoam_properties,
        test_wrap_config,
        test_minimal_config,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
