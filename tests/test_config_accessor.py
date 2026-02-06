"""
Test suite for the Config accessor class.

Tests cover:
- Basic config access methods
- Nested vs flattened config handling
- All property accessors
- Boundary condition configuration
- Physics configuration
- Windkessel settings
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.accessor import Config


class TestConfigBasicAccess:
    """Test basic config access methods."""

    def test_init_with_empty_config(self):
        """Test initialization with empty config."""
        cfg = Config({})
        assert cfg.to_dict() == {}

    def test_init_with_config(self):
        """Test initialization with config dict."""
        raw = {'key': 'value', 'nested': {'inner': 42}}
        cfg = Config(raw)
        assert cfg.to_dict() == raw

    def test_get_top_level(self):
        """Test get method for top-level keys."""
        cfg = Config({'key': 'value'})
        assert cfg.get('key') == 'value'
        assert cfg.get('missing') is None
        assert cfg.get('missing', 'default') == 'default'

    def test_get_nested(self):
        """Test get_nested for multi-level access."""
        cfg = Config({'a': {'b': {'c': 123}}})
        assert cfg.get_nested('a', 'b', 'c') == 123
        assert cfg.get_nested('a', 'b') == {'c': 123}
        assert cfg.get_nested('a', 'x', default='missing') == 'missing'
        assert cfg.get_nested('x', 'y', 'z', default=None) is None

    def test_getitem(self):
        """Test dict-like access with []."""
        cfg = Config({'key': 'value'})
        assert cfg['key'] == 'value'
        with pytest.raises(KeyError):
            _ = cfg['missing']

    def test_contains(self):
        """Test 'in' operator."""
        cfg = Config({'key': 'value'})
        assert 'key' in cfg
        assert 'missing' not in cfg


class TestConfigCaseInfo:
    """Test case information accessors."""

    def test_case_info_present(self):
        """Test case_info when present."""
        cfg = Config({
            'case_info': {
                'patient_id': 'PAT001',
                'notes': 'Test case'
            }
        })
        assert cfg.case_info == {'patient_id': 'PAT001', 'notes': 'Test case'}
        assert cfg.patient_id == 'PAT001'
        assert cfg.case_notes == 'Test case'

    def test_case_info_missing(self):
        """Test case_info when missing."""
        cfg = Config({})
        assert cfg.case_info == {}
        assert cfg.patient_id == ''
        assert cfg.case_notes == ''


class TestConfigGeometry:
    """Test geometry configuration accessors."""

    def test_geometry_full(self):
        """Test geometry with all fields."""
        cfg = Config({
            'geometry': {
                'case_name': 'test_case',
                'scale_factor': 0.001,
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1', 'outlet2'],
                'wall_keywords_ordered': 'wall',
                'reference_radius_strategy': 'minimum'
            }
        })
        assert cfg.case_name == 'test_case'
        assert cfg.scale_factor == 0.001
        assert cfg.inlet_patch_name == 'inlet'
        assert cfg.outlet_patch_names == ['outlet1', 'outlet2']
        assert cfg.wall_patch_name == 'wall'
        assert cfg.reference_radius_strategy == 'minimum'

    def test_geometry_defaults(self):
        """Test geometry with defaults."""
        cfg = Config({})
        assert cfg.geometry == {}
        assert cfg.case_name == ''
        assert cfg.scale_factor == 0.001  # Default
        assert cfg.inlet_patch_name == ''
        assert cfg.outlet_patch_names == []
        assert cfg.wall_patch_name == ''
        assert cfg.reference_radius_strategy == 'inlet'

    def test_outlet_names_string(self):
        """Test outlet names when given as string."""
        cfg = Config({
            'geometry': {
                'outlet_keywords_ordered': 'single_outlet'
            }
        })
        # Should convert string to list
        assert cfg.outlet_patch_names == ['single_outlet']


class TestConfigBoundaryConditions:
    """Test boundary condition accessors."""

    def test_nested_bc_structure(self):
        """Test nested boundary_conditions.inlet/outlets structure."""
        cfg = Config({
            'boundary_conditions': {
                'inlet': {'type': 'TIMEVARYING', 'csv_file': 'inlet.csv'},
                'outlets': {'type': '3EWINDKESSEL'},
                'walls': {'type': 'no_slip'}
            }
        })
        assert cfg.inlet == {'type': 'TIMEVARYING', 'csv_file': 'inlet.csv'}
        assert cfg.outlets == {'type': '3EWINDKESSEL'}
        assert cfg.walls == {'type': 'no_slip'}
        assert cfg.inlet_type == 'TIMEVARYING'
        assert cfg.outlet_type == '3EWINDKESSEL'
        assert cfg.wall_type == 'no_slip'

    def test_flattened_bc_structure(self):
        """Test flattened inlet/outlets at top level."""
        cfg = Config({
            'inlet': {'type': 'CONSTANT', 'velocity': 0.5},
            'outlets': {'type': 'zeroGradient'},
            'walls': {'type': 'slip'}
        })
        assert cfg.inlet == {'type': 'CONSTANT', 'velocity': 0.5}
        assert cfg.outlets == {'type': 'zeroGradient'}
        assert cfg.walls == {'type': 'slip'}
        assert cfg.inlet_type == 'CONSTANT'
        assert cfg.outlet_type == 'ZEROGRADIENT'
        assert cfg.wall_type == 'slip'

    def test_windkessel_detection(self):
        """Test is_windkessel property."""
        cfg_wk = Config({'boundary_conditions': {'outlets': {'type': '3EWINDKESSEL'}}})
        cfg_no_wk = Config({'boundary_conditions': {'outlets': {'type': 'zeroGradient'}}})

        assert cfg_wk.is_windkessel is True
        assert cfg_no_wk.is_windkessel is False

    def test_pulsatile_detection(self):
        """Test is_pulsatile property."""
        for inlet_type in ['TIMEVARYING', 'WOMERSLEY', 'MRI']:
            cfg = Config({'boundary_conditions': {'inlet': {'type': inlet_type}}})
            assert cfg.is_pulsatile is True, f"Failed for {inlet_type}"

        for inlet_type in ['CONSTANT', 'PARABOLIC']:
            cfg = Config({'boundary_conditions': {'inlet': {'type': inlet_type}}})
            assert cfg.is_pulsatile is False, f"Failed for {inlet_type}"


class TestConfigInletSettings:
    """Test inlet BC detailed settings."""

    def test_inlet_velocity(self):
        """Test inlet velocity accessor."""
        cfg = Config({'inlet': {'velocity': 0.5}})
        assert cfg.inlet_velocity == 0.5

        cfg_none = Config({})
        assert cfg_none.inlet_velocity is None

    def test_inlet_cardiac_output(self):
        """Test inlet cardiac output accessor."""
        # cardiac_output
        cfg1 = Config({'inlet': {'cardiac_output': 5.0}})
        assert cfg1.inlet_cardiac_output == 5.0

        # flowrate alias
        cfg2 = Config({'inlet': {'flowrate': 6.0}})
        assert cfg2.inlet_cardiac_output == 6.0

        # cardiac_output takes precedence
        cfg3 = Config({'inlet': {'cardiac_output': 5.0, 'flowrate': 6.0}})
        assert cfg3.inlet_cardiac_output == 5.0

    def test_inlet_csv_settings(self):
        """Test inlet CSV settings."""
        cfg = Config({
            'inlet': {
                'csv_file': 'inlet_flow.csv',
                'data_type': 'velocity'
            }
        })
        assert cfg.inlet_csv_file == 'inlet_flow.csv'
        assert cfg.inlet_data_type == 'velocity'

        # Default data_type
        cfg_default = Config({'inlet': {'csv_file': 'test.csv'}})
        assert cfg_default.inlet_data_type == 'flowrate'

    def test_inlet_profile_settings(self):
        """Test inlet velocity profile settings."""
        cfg = Config({
            'inlet': {
                'profile': 'wall_distance',
                'exponent': 7.0,
                'n_harmonics': 10
            }
        })
        assert cfg.inlet_velocity_profile == 'wall_distance'
        assert cfg.inlet_profile_exponent == 7.0
        assert cfg.inlet_n_harmonics == 10

        # Defaults
        cfg_default = Config({})
        assert cfg_default.inlet_velocity_profile == 'parabolic'
        assert cfg_default.inlet_profile_exponent == 2.0
        assert cfg_default.inlet_n_harmonics == 'auto'

    def test_inlet_mri_file(self):
        """Test MRI inlet file accessor."""
        cfg = Config({'inlet': {'file': '/path/to/mri_data'}})
        assert cfg.inlet_mri_file == '/path/to/mri_data'


class TestConfigWindkesselSettings:
    """Test Windkessel outlet settings."""

    def test_windkessel_pressure_settings(self):
        """Test Windkessel pressure settings."""
        cfg = Config({
            'outlets': {
                'type': '3EWINDKESSEL',
                'windkessel_settings': {
                    'systolic_pressure': 130,
                    'diastolic_pressure': 85,
                    'venous_pressure': 3
                }
            }
        })
        assert cfg.windkessel_systolic_pressure == 130
        assert cfg.windkessel_diastolic_pressure == 85
        assert cfg.windkessel_venous_pressure == 3

    def test_windkessel_defaults(self):
        """Test Windkessel default values."""
        cfg = Config({})
        assert cfg.windkessel_systolic_pressure == 120
        assert cfg.windkessel_diastolic_pressure == 80
        assert cfg.windkessel_venous_pressure == 5
        assert cfg.windkessel_tau == 1.8
        assert cfg.windkessel_betaT == 0.3
        assert cfg.windkessel_betaN == 0.0
        assert cfg.windkessel_order == 3
        assert cfg.windkessel_coupling_mode == 'implicit'
        assert cfg.windkessel_enable_stabilization is True
        assert cfg.windkessel_initial_pressure_method == 'diastolic'
        assert cfg.windkessel_pwv_method == 'matlab'

    def test_windkessel_flow_split(self):
        """Test Windkessel flow split configuration."""
        # None (auto Murray's law)
        cfg1 = Config({})
        assert cfg1.windkessel_flow_split is None

        # Percentage
        cfg2 = Config({
            'outlets': {
                'windkessel_settings': {'flow_split': 60}
            }
        })
        assert cfg2.windkessel_flow_split == 60

        # Dict
        cfg3 = Config({
            'outlets': {
                'windkessel_settings': {
                    'flow_split': {'outlet1': 0.4, 'outlet2': 0.6}
                }
            }
        })
        assert cfg3.windkessel_flow_split == {'outlet1': 0.4, 'outlet2': 0.6}

    def test_windkessel_outlet_parameters(self):
        """Test direct R/C/Z outlet parameters."""
        cfg = Config({
            'outlets': {
                'windkessel_settings': {
                    'outlet_parameters': {
                        'outlet1': {'R': 1e8, 'C': 1e-9, 'Z': 1e7}
                    }
                }
            }
        })
        assert cfg.windkessel_outlet_parameters == {'outlet1': {'R': 1e8, 'C': 1e-9, 'Z': 1e7}}

    def test_windkessel_pwv_settings(self):
        """Test PWV calculation settings."""
        cfg = Config({
            'outlets': {
                'windkessel_settings': {
                    'pwv_method': 'fixed',
                    'pwv': 8.5
                }
            }
        })
        assert cfg.windkessel_pwv_method == 'fixed'
        assert cfg.windkessel_pwv == 8.5


class TestConfigPhysics:
    """Test physics configuration accessors."""

    def test_simulation_type(self):
        """Test simulation type accessors."""
        # Laminar
        cfg_lam = Config({'physics': {'simulation_type': 'laminar'}})
        assert cfg_lam.simulation_type == 'laminar'
        assert cfg_lam.is_turbulent is False
        assert cfg_lam.is_les is False

        # RANS
        cfg_rans = Config({'physics': {'simulation_type': 'RANS'}})
        assert cfg_rans.simulation_type == 'rans'
        assert cfg_rans.is_turbulent is True
        assert cfg_rans.is_les is False

        # LES
        cfg_les = Config({'physics': {'simulation_type': 'LES'}})
        assert cfg_les.simulation_type == 'les'
        assert cfg_les.is_turbulent is True
        assert cfg_les.is_les is True


class TestConfigNumerics:
    """Test numerics configuration accessors."""

    def test_profile_and_max_co(self):
        """Test numerics profile settings."""
        cfg = Config({
            'numerics': {
                'profile': 'robust',
                'max_co': 0.5
            }
        })
        assert cfg.get_nested('numerics', 'profile') == 'robust'
        assert cfg.get_nested('numerics', 'max_co') == 0.5


class TestConfigMesh:
    """Test mesh configuration accessors."""

    def test_mesh_settings(self):
        """Test mesh settings access."""
        cfg = Config({
            'mesh': {
                'refinement_level': 2,
                'boundary_layers': True,
                'SNAPPY_SETTINGS': {
                    'maxLocalCells': 1000000
                }
            }
        })
        mesh = cfg.get('mesh', {})
        assert mesh.get('refinement_level') == 2
        assert mesh.get('boundary_layers') is True
        assert mesh.get('SNAPPY_SETTINGS', {}).get('maxLocalCells') == 1000000


class TestConfigSimulation:
    """Test simulation settings accessors."""

    def test_simulation_settings(self):
        """Test simulation settings."""
        cfg = Config({
            'simulation': {
                'end_time': 5.0,
                'num_processors': 8
            },
            'cardiac_cycle': 0.85
        })
        assert cfg.get_nested('simulation', 'end_time') == 5.0
        assert cfg.get_nested('simulation', 'num_processors') == 8
        assert cfg.get('cardiac_cycle') == 0.85


class TestConfigPhysicsExtended:
    """Test extended physics configuration accessors."""

    def test_nu_property(self):
        """Test kinematic viscosity accessor."""
        cfg = Config({'physics': {'nu': 3.5e-6}})
        assert cfg.nu == 3.5e-6

    def test_nu_default(self):
        """Test default nu value (calculated from mu/rho)."""
        cfg = Config({})
        # Default is calculated from default_viscosity/default_density = 0.004/1060
        expected_nu = 0.004 / 1060
        assert abs(cfg.nu - expected_nu) < 1e-12

    def test_rho_property(self):
        """Test density accessor."""
        cfg = Config({'physics': {'rho': 1060}})
        assert cfg.rho == 1060

    def test_rho_default(self):
        """Test default rho value."""
        cfg = Config({})
        assert cfg.rho == 1060

    def test_turbulence_intensity(self):
        """Test turbulence intensity accessor."""
        cfg = Config({'physics': {'turbulence_intensity': 0.05}})
        assert cfg.turbulence_intensity == 0.05

    def test_turbulence_intensity_default(self):
        """Test default turbulence intensity."""
        cfg = Config({})
        assert cfg.turbulence_intensity == 0.05

    def test_turbulence_model(self):
        """Test turbulence model accessor."""
        cfg = Config({'physics': {'turbulence_model': 'kOmegaSST'}})
        assert cfg.turbulence_model == 'kOmegaSST'

    def test_turbulence_model_default(self):
        """Test default turbulence model."""
        cfg = Config({})
        assert cfg.turbulence_model == 'kOmegaSST'

    def test_les_model(self):
        """Test LES model accessor."""
        cfg = Config({'physics': {'les_model': 'Smagorinsky'}})
        assert cfg.les_model == 'Smagorinsky'

    def test_les_model_default(self):
        """Test default LES model."""
        cfg = Config({})
        assert cfg.les_model == 'WALE'

    def test_physics_model(self):
        """Test physics_model returns normalized model field."""
        # Laminar (default)
        cfg_lam = Config({'physics': {'model': 'laminar'}})
        assert cfg_lam.physics_model == 'laminar'

        # RAS -> rans
        cfg_rans = Config({'physics': {'model': 'RAS'}})
        assert cfg_rans.physics_model == 'rans'

        # LES -> les
        cfg_les = Config({'physics': {'model': 'LES'}})
        assert cfg_les.physics_model == 'les'

        # Default
        cfg_default = Config({})
        assert cfg_default.physics_model == 'laminar'


class TestConfigNumericsExtended:
    """Test extended numerics configuration accessors."""

    def test_profile(self):
        """Test numerics profile accessor."""
        cfg = Config({'numerics': {'profile': 'accurate'}})
        assert cfg.profile == 'accurate'

    def test_profile_default(self):
        """Test default numerics profile."""
        cfg = Config({})
        assert cfg.profile == 'standard'

    def test_mesh_adaptive(self):
        """Test mesh_adaptive accessor."""
        cfg = Config({'numerics': {'mesh_adaptive': True}})
        assert cfg.mesh_adaptive is True

    def test_mesh_adaptive_default(self):
        """Test default mesh_adaptive."""
        cfg = Config({})
        assert cfg.mesh_adaptive is False

    def test_max_co(self):
        """Test max_co accessor."""
        cfg = Config({'numerics': {'max_co': 0.8}})
        assert cfg.max_co == 0.8

    def test_max_co_none(self):
        """Test max_co when not specified."""
        cfg = Config({})
        assert cfg.max_co is None

    def test_adjustable_timestep(self):
        """Test adjustable_timestep accessor."""
        cfg = Config({'numerics': {'adjustable_timestep': False}})
        assert cfg.adjustable_timestep is False

    def test_adjustable_timestep_default(self):
        """Test default adjustable_timestep."""
        cfg = Config({})
        assert cfg.adjustable_timestep is True

    def test_correctors(self):
        """Test correctors accessor."""
        cfg = Config({'numerics': {'correctors': {'nOuterCorrectors': 5}}})
        assert cfg.correctors == {'nOuterCorrectors': 5}

    def test_correctors_default(self):
        """Test default correctors."""
        cfg = Config({})
        assert cfg.correctors == {}

    def test_relaxation_factors(self):
        """Test relaxation factors accessor."""
        cfg = Config({'numerics': {'relaxation_factors': {'p': 0.3, 'U': 0.7}}})
        assert cfg.relaxation_factors == {'p': 0.3, 'U': 0.7}

    def test_residual_control(self):
        """Test residual control accessor."""
        cfg = Config({'numerics': {'residual_control': {'p': 1e-5, 'U': 1e-6}}})
        assert cfg.residual_control == {'p': 1e-5, 'U': 1e-6}


class TestConfigMeshExtended:
    """Test extended mesh configuration accessors."""

    def test_mesh(self):
        """Test mesh accessor."""
        cfg = Config({'mesh': {'resolution': 'fine'}})
        assert cfg.mesh == {'resolution': 'fine'}

    def test_mesh_default(self):
        """Test default mesh."""
        cfg = Config({})
        assert cfg.mesh == {}

    def test_snappy_settings(self):
        """Test snappy settings accessor."""
        cfg = Config({'mesh': {'SNAPPY_SETTINGS': {'nCellsBetweenLevels': 5}}})
        assert cfg.snappy_settings == {'nCellsBetweenLevels': 5}

    def test_snappy_settings_default(self):
        """Test default snappy settings."""
        cfg = Config({})
        assert cfg.snappy_settings == {}

    def test_boundary_layers(self):
        """Test boundary layers accessor."""
        cfg = Config({'mesh': {'boundary_layers': {'nLayers': 3}}})
        assert cfg.boundary_layers == {'nLayers': 3}

    def test_mesh_resolution(self):
        """Test mesh resolution accessor."""
        cfg = Config({'mesh': {'mesh_resolution': {'min': 0.1, 'max': 1.0}}})
        assert cfg.mesh_resolution == {'min': 0.1, 'max': 1.0}


class TestConfigSimulationControl:
    """Test simulation control accessors."""

    def test_simulation_control(self):
        """Test simulation_control accessor."""
        cfg = Config({'simulation_control': {'start_time': 0}})
        assert cfg.simulation_control == {'start_time': 0}

    def test_simulation_control_default(self):
        """Test default simulation_control."""
        cfg = Config({})
        assert cfg.simulation_control == {}

    def test_end_time(self):
        """Test end_time accessor."""
        cfg = Config({'simulation_control': {'end_time': 5.0}})
        assert cfg.end_time == 5.0

    def test_end_time_none(self):
        """Test end_time when not specified."""
        cfg = Config({})
        assert cfg.end_time is None

    def test_num_cycles(self):
        """Test num_cycles accessor."""
        cfg = Config({'simulation_control': {'num_cycles': 3}})
        assert cfg.num_cycles == 3

    def test_num_cycles_default(self):
        """Test default num_cycles."""
        cfg = Config({})
        assert cfg.num_cycles == 3

    def test_control_dict(self):
        """Test control_dict accessor."""
        cfg = Config({'simulation_control': {'controlDict': {'application': 'foamRun'}}})
        assert cfg.control_dict == {'application': 'foamRun'}

    def test_write_interval(self):
        """Test write_interval accessor."""
        cfg = Config({'simulation_control': {'controlDict': {'writeInterval': 0.01}}})
        assert cfg.write_interval == 0.01

    def test_write_interval_default(self):
        """Test default write_interval."""
        cfg = Config({})
        assert cfg.write_interval == 0.01

    def test_cardiac_cycle(self):
        """Test cardiac_cycle accessor."""
        cfg = Config({'cardiac_cycle': 0.85})
        assert cfg.cardiac_cycle == 0.85

    def test_cardiac_cycle_default(self):
        """Test default cardiac_cycle."""
        cfg = Config({})
        assert cfg.cardiac_cycle == 0.8

    def test_delta_t(self):
        """Test delta_t accessor."""
        cfg = Config({'simulation_control': {'controlDict': {'deltaT': 1e-5}}})
        assert cfg.delta_t == 1e-5

    def test_delta_t_default(self):
        """Test default delta_t."""
        cfg = Config({})
        assert cfg.delta_t == 1e-5

    def test_write_format(self):
        """Test write_format accessor."""
        cfg = Config({'simulation_control': {'controlDict': {'writeFormat': 'binary'}}})
        assert cfg.write_format == 'binary'

    def test_write_format_default(self):
        """Test default write_format."""
        cfg = Config({})
        assert cfg.write_format == 'binary'

    def test_purge_write(self):
        """Test purge_write accessor."""
        cfg = Config({'simulation_control': {'purge_write': 5}})
        assert cfg.purge_write == 5

    def test_purge_write_default(self):
        """Test default purge_write."""
        cfg = Config({})
        assert cfg.purge_write == 0

    def test_keep_last_cycles(self):
        """Test keep_last_cycles accessor."""
        cfg = Config({'simulation_control': {'keep_last_cycles': 2}})
        assert cfg.keep_last_cycles == 2

    def test_keep_last_cycles_none(self):
        """Test keep_last_cycles when not specified."""
        cfg = Config({})
        assert cfg.keep_last_cycles is None


class TestConfigSimulationFunctions:
    """Test simulation functions accessors."""

    def test_simulation_functions(self):
        """Test simulation_functions accessor."""
        cfg = Config({'simulation_control': {'functions': {'wss': True}}})
        assert cfg.simulation_functions == {'wss': True}

    def test_simulation_wss_function(self):
        """Test simulation_wss_function accessor."""
        cfg = Config({'simulation_control': {'functions': {'wallShearStress': {'enabled': True}}}})
        assert cfg.simulation_wss_function == {'enabled': True}

    def test_simulation_field_average_function(self):
        """Test simulation_field_average_function accessor."""
        cfg = Config({'simulation_control': {'functions': {'fieldAverage': {'fields': ['U']}}}})
        assert cfg.simulation_field_average_function == {'fields': ['U']}

    def test_simulation_forces_function(self):
        """Test simulation_forces_function accessor."""
        cfg = Config({'simulation_control': {'functions': {'forces': {'patches': ['wall']}}}})
        assert cfg.simulation_forces_function == {'patches': ['wall']}

    def test_simulation_probes_function(self):
        """Test simulation_probes_function accessor."""
        cfg = Config({'simulation_control': {'functions': {'probes': {'points': []}}}})
        assert cfg.simulation_probes_function == {'points': []}


class TestConfigRunSettings:
    """Test run settings accessors."""

    def test_run_settings(self):
        """Test run_settings accessor."""
        cfg = Config({'run_settings': {'parallel': True}})
        assert cfg.run_settings == {'parallel': True}

    def test_run_settings_default(self):
        """Test default run_settings."""
        cfg = Config({})
        assert cfg.run_settings == {}

    def test_subdomains(self):
        """Test subdomains accessor."""
        cfg = Config({'run_settings': {'subdomains': 8}})
        assert cfg.subdomains == 8

    def test_subdomains_default(self):
        """Test default subdomains."""
        cfg = Config({})
        assert cfg.subdomains == 4

    def test_decomposition_method(self):
        """Test decomposition_method accessor."""
        cfg = Config({'run_settings': {'decomposition_method': 'hierarchical'}})
        assert cfg.decomposition_method == 'hierarchical'

    def test_decomposition_method_default(self):
        """Test default decomposition_method."""
        cfg = Config({})
        assert cfg.decomposition_method == 'scotch'

    def test_solution_type(self):
        """Test solution_type accessor."""
        cfg = Config({'run_settings': {'solution_type': 'serial'}})
        assert cfg.solution_type == 'serial'

    def test_solution_type_default(self):
        """Test default solution_type."""
        cfg = Config({})
        assert cfg.solution_type == 'parallel'

    def test_is_parallel(self):
        """Test is_parallel accessor."""
        cfg_par = Config({'run_settings': {'solution_type': 'parallel'}})
        assert cfg_par.is_parallel is True

        cfg_ser = Config({'run_settings': {'solution_type': 'serial'}})
        assert cfg_ser.is_parallel is False

    def test_decomposition_coeffs(self):
        """Test decomposition_coeffs accessor."""
        cfg = Config({'run_settings': {'decomposition_coeffs': {'n': [2, 2, 2]}}})
        assert cfg.decomposition_coeffs == {'n': [2, 2, 2]}


class TestConfigHemodynamics:
    """Test hemodynamics configuration accessors."""

    def test_hemodynamics(self):
        """Test hemodynamics accessor."""
        cfg = Config({'hemodynamics': {'compute_wss': True}})
        assert cfg.hemodynamics == {'compute_wss': True}

    def test_hemodynamics_default(self):
        """Test default hemodynamics."""
        cfg = Config({})
        assert cfg.hemodynamics == {}

    def test_runtime_functions(self):
        """Test runtime_functions accessor."""
        cfg = Config({'hemodynamics': {'runtime_functions': {'wss': True}}})
        assert cfg.runtime_functions == {'wss': True}

    def test_runtime_wss_enabled(self):
        """Test runtime_wss_enabled accessor."""
        cfg = Config({'hemodynamics': {'runtime_functions': {'wss': True}}})
        assert cfg.runtime_wss_enabled is True

    def test_runtime_wss_enabled_default(self):
        """Test default runtime_wss_enabled."""
        cfg = Config({})
        assert cfg.runtime_wss_enabled is True

    def test_runtime_field_average(self):
        """Test runtime_field_average accessor."""
        cfg = Config({'hemodynamics': {'runtime_functions': {'fieldAverage': 'velocity'}}})
        assert cfg.runtime_field_average == 'velocity'

    def test_runtime_velocity_field_average(self):
        """Test runtime_velocity_field_average accessor."""
        cfg = Config({'hemodynamics': {'runtime_functions': {'velocityFieldAverage': True}}})
        assert cfg.runtime_velocity_field_average is True

    def test_runtime_pressure_monitoring(self):
        """Test runtime_pressure_monitoring accessor."""
        cfg = Config({'hemodynamics': {'runtime_functions': {'pressure_monitoring': True}}})
        assert cfg.runtime_pressure_monitoring is True

    def test_runtime_pressure_monitoring_default(self):
        """Test default runtime_pressure_monitoring."""
        cfg = Config({})
        assert cfg.runtime_pressure_monitoring is True

    def test_tawss_settings(self):
        """Test tawss_settings accessor."""
        cfg = Config({'hemodynamics': {'tawss_settings': {'skip_cycles': 1}}})
        assert cfg.tawss_settings == {'skip_cycles': 1}

    def test_tawss_skip_cycles(self):
        """Test tawss_skip_cycles accessor."""
        cfg = Config({'hemodynamics': {'tawss_settings': {'skip_cycles': 2}}})
        assert cfg.tawss_skip_cycles == 2

    def test_tawss_skip_cycles_default(self):
        """Test default tawss_skip_cycles."""
        cfg = Config({})
        assert cfg.tawss_skip_cycles == 2

    def test_tawss_periodic_restart(self):
        """Test tawss_periodic_restart accessor."""
        cfg = Config({'hemodynamics': {'tawss_settings': {'periodicRestart': False}}})
        assert cfg.tawss_periodic_restart is False

    def test_tawss_periodic_restart_default(self):
        """Test default tawss_periodic_restart."""
        cfg = Config({})
        assert cfg.tawss_periodic_restart is True

    def test_tawss_keep_all_cycles(self):
        """Test tawss_keep_all_cycles accessor."""
        cfg = Config({'hemodynamics': {'tawss_settings': {'keep_all_cycles': False}}})
        assert cfg.tawss_keep_all_cycles is False

    def test_tawss_keep_all_cycles_default(self):
        """Test default tawss_keep_all_cycles."""
        cfg = Config({})
        assert cfg.tawss_keep_all_cycles is True


class TestConfigPostProcessing:
    """Test post-processing configuration accessors."""

    def test_post_processing(self):
        """Test post_processing accessor."""
        cfg = Config({'post_processing': {'enabled': True}})
        assert cfg.post_processing == {'enabled': True}

    def test_post_processing_default(self):
        """Test default post_processing."""
        cfg = Config({})
        assert cfg.post_processing == {}

    def test_compute_hemodynamics_enabled(self):
        """Test compute_hemodynamics_enabled accessor."""
        cfg = Config({'post_processing': {'compute_hemodynamics': False}})
        assert cfg.compute_hemodynamics_enabled is False

    def test_compute_hemodynamics_enabled_default(self):
        """Test default compute_hemodynamics_enabled."""
        cfg = Config({})
        assert cfg.compute_hemodynamics_enabled is True

    def test_extract_surfaces_settings(self):
        """Test extract_surfaces_settings accessor."""
        cfg = Config({'post_processing': {'extract_surfaces': {'patches': ['wall']}}})
        assert cfg.extract_surfaces_settings == {'patches': ['wall']}

    def test_extract_surfaces_enabled(self):
        """Test extract_surfaces_enabled accessor."""
        cfg = Config({'post_processing': {'extract_surfaces': {'enabled': True}}})
        assert cfg.extract_surfaces_enabled is True

    def test_extract_surfaces_enabled_default(self):
        """Test default extract_surfaces_enabled."""
        cfg = Config({})
        assert cfg.extract_surfaces_enabled is True

    def test_extract_surfaces_patches(self):
        """Test extract_surfaces_patches accessor."""
        cfg = Config({'post_processing': {'extract_surfaces': {'patches': ['wall', 'inlet']}}})
        assert cfg.extract_surfaces_patches == ['wall', 'inlet']

    def test_extract_surfaces_patches_default(self):
        """Test default extract_surfaces_patches (uses wall_patch_name)."""
        cfg = Config({})
        # Default falls back to wall_patch_name which is '' for empty config
        assert cfg.extract_surfaces_patches == ['']

    def test_extract_surfaces_time_points(self):
        """Test extract_surfaces_time_points accessor."""
        cfg = Config({'post_processing': {'extract_surfaces': {'time_points': [0.0, 0.5]}}})
        assert cfg.extract_surfaces_time_points == [0.0, 0.5]

    def test_extract_surfaces_time_points_default(self):
        """Test default extract_surfaces_time_points."""
        cfg = Config({})
        assert cfg.extract_surfaces_time_points == 'all'

    def test_compute_flow_rate_settings(self):
        """Test compute_flow_rate_settings accessor."""
        cfg = Config({'post_processing': {'compute_flow_rate': {'enabled': True}}})
        assert cfg.compute_flow_rate_settings == {'enabled': True}

    def test_compute_flow_rate_enabled(self):
        """Test compute_flow_rate_enabled accessor."""
        cfg = Config({'post_processing': {'compute_flow_rate': {'enabled': False}}})
        assert cfg.compute_flow_rate_enabled is False

    def test_compute_flow_rate_enabled_default(self):
        """Test default compute_flow_rate_enabled."""
        cfg = Config({})
        assert cfg.compute_flow_rate_enabled is True

    def test_compute_flow_rate_patches(self):
        """Test compute_flow_rate_patches accessor."""
        cfg = Config({'post_processing': {'compute_flow_rate': {'patches': ['inlet', 'outlet1']}}})
        assert cfg.compute_flow_rate_patches == ['inlet', 'outlet1']

    def test_compute_flow_rate_patches_default(self):
        """Test default compute_flow_rate_patches (uses inlet + outlets)."""
        cfg = Config({})
        # Default falls back to inlet_patch_name + outlet_patch_names
        # For empty config: [''] + [] = ['']
        assert cfg.compute_flow_rate_patches == ['']

    def test_pressure_drop_settings(self):
        """Test pressure_drop_settings accessor."""
        cfg = Config({'post_processing': {'pressure_drop': {'enabled': True}}})
        assert cfg.pressure_drop_settings == {'enabled': True}

    def test_pressure_drop_enabled(self):
        """Test pressure_drop_enabled accessor."""
        cfg = Config({'post_processing': {'pressure_drop': {'enabled': False}}})
        assert cfg.pressure_drop_enabled is False

    def test_pressure_drop_enabled_default(self):
        """Test default pressure_drop_enabled."""
        cfg = Config({})
        assert cfg.pressure_drop_enabled is True

    def test_pressure_drop_inlet_patch(self):
        """Test pressure_drop_inlet_patch accessor."""
        cfg = Config({'post_processing': {'pressure_drop': {'inlet_patch': 'inlet'}}})
        assert cfg.pressure_drop_inlet_patch == 'inlet'

    def test_pressure_drop_inlet_patch_default(self):
        """Test default pressure_drop_inlet_patch."""
        cfg = Config({})
        assert cfg.pressure_drop_inlet_patch == ''

    def test_pressure_drop_outlet_patches(self):
        """Test pressure_drop_outlet_patches accessor."""
        cfg = Config({'post_processing': {'pressure_drop': {'outlet_patches': ['out1', 'out2']}}})
        assert cfg.pressure_drop_outlet_patches == ['out1', 'out2']

    def test_pressure_drop_outlet_patches_default(self):
        """Test default pressure_drop_outlet_patches."""
        cfg = Config({})
        assert cfg.pressure_drop_outlet_patches == []


class TestConfigVisualization:
    """Test visualization configuration accessors."""

    def test_visualization(self):
        """Test visualization accessor."""
        cfg = Config({'visualization': {'format': 'png'}})
        assert cfg.visualization == {'format': 'png'}

    def test_visualization_default(self):
        """Test default visualization."""
        cfg = Config({})
        assert cfg.visualization == {}


class TestConfigAdvanced:
    """Test advanced configuration accessors."""

    def test_advanced(self):
        """Test advanced accessor."""
        cfg = Config({'advanced': {'debug': True}})
        assert cfg.advanced == {'debug': True}

    def test_advanced_default(self):
        """Test default advanced."""
        cfg = Config({})
        assert cfg.advanced == {}

    def test_custom_templates(self):
        """Test custom_templates accessor."""
        cfg = Config({'advanced': {'custom_templates': {'fvSchemes': 'path/to/template'}}})
        assert cfg.custom_templates == {'fvSchemes': 'path/to/template'}

    def test_custom_templates_enabled(self):
        """Test custom_templates_enabled accessor."""
        cfg = Config({'advanced': {'custom_templates': {'enabled': True}}})
        assert cfg.custom_templates_enabled is True

    def test_custom_templates_enabled_default(self):
        """Test default custom_templates_enabled."""
        cfg = Config({})
        assert cfg.custom_templates_enabled is False

    def test_solver_overrides(self):
        """Test solver_overrides accessor."""
        cfg = Config({'advanced': {'solver_overrides': {'tolerance': 1e-8}}})
        assert cfg.solver_overrides == {'tolerance': 1e-8}

    def test_momentum_predictor(self):
        """Test momentum_predictor accessor."""
        cfg = Config({'advanced': {'solver_overrides': {'momentum_predictor': False}}})
        assert cfg.momentum_predictor is False

    def test_momentum_predictor_default(self):
        """Test default momentum_predictor."""
        cfg = Config({})
        assert cfg.momentum_predictor is True

    def test_pimple_consistent(self):
        """Test pimple_consistent accessor."""
        cfg = Config({'advanced': {'solver_overrides': {'consistent': True}}})
        assert cfg.pimple_consistent is True

    def test_pimple_consistent_default(self):
        """Test default pimple_consistent."""
        cfg = Config({})
        assert cfg.pimple_consistent is False

    def test_turb_on_final_iter_only(self):
        """Test turb_on_final_iter_only accessor."""
        cfg = Config({'advanced': {'solver_overrides': {'turbOnFinalIterOnly': False}}})
        assert cfg.turb_on_final_iter_only is False

    def test_turb_on_final_iter_only_default(self):
        """Test default turb_on_final_iter_only."""
        cfg = Config({})
        assert cfg.turb_on_final_iter_only is True


class TestConfigOpenFOAMSettings:
    """Test OpenFOAM-specific settings accessors."""

    def test_openfoam_version(self):
        """Test openfoam_version accessor."""
        cfg = Config({'openfoam_version': '2412'})
        assert cfg.openfoam_version == '2412'

    def test_openfoam_version_default(self):
        """Test default openfoam_version."""
        cfg = Config({})
        assert cfg.openfoam_version == '12'

    def test_solver_application(self):
        """Test solver_application accessor."""
        cfg = Config({'solver_application': 'pimpleFoam'})
        assert cfg.solver_application == 'pimpleFoam'

    def test_solver_application_default(self):
        """Test default solver_application."""
        cfg = Config({})
        assert cfg.solver_application == 'foamRun'

    def test_solver_module(self):
        """Test solver_module accessor."""
        cfg = Config({'solver_module': 'compressibleFluid'})
        assert cfg.solver_module == 'compressibleFluid'

    def test_solver_module_default(self):
        """Test default solver_module."""
        cfg = Config({})
        assert cfg.solver_module == 'incompressibleFluid'


class TestWrapConfig:
    """Test wrap_config helper function."""

    def test_wrap_dict(self):
        """Test wrapping a dict returns Config."""
        from config.accessor import wrap_config

        data = {'key': 'value'}
        result = wrap_config(data)

        assert isinstance(result, Config)
        assert result.get('key') == 'value'

    def test_wrap_config_passthrough(self):
        """Test wrapping Config returns same object."""
        from config.accessor import wrap_config

        cfg = Config({'key': 'value'})
        result = wrap_config(cfg)

        assert result is cfg


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
