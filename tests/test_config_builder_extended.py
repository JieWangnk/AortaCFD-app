"""
Extended test suite for config/builder.py module.

Tests cover:
- deep_merge function
- ConfigBuilder helper methods
- OpenFOAM settings application
- Validation methods
"""

import pytest
import sys
import tempfile
import os
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.builder import deep_merge, ConfigBuilder


class TestDeepMerge:
    """Test deep_merge helper function."""

    def test_merge_flat_dicts(self):
        """Test merging flat dictionaries."""
        dest = {'a': 1, 'b': 2}
        source = {'c': 3, 'd': 4}

        result = deep_merge(dest, source)

        assert result == {'a': 1, 'b': 2, 'c': 3, 'd': 4}

    def test_merge_overwrites_values(self):
        """Test that source overwrites destination values."""
        dest = {'a': 1, 'b': 2}
        source = {'b': 99}

        result = deep_merge(dest, source)

        assert result == {'a': 1, 'b': 99}

    def test_merge_nested_dicts(self):
        """Test merging nested dictionaries."""
        dest = {
            'level1': {
                'a': 1,
                'b': 2
            }
        }
        source = {
            'level1': {
                'c': 3
            }
        }

        result = deep_merge(dest, source)

        assert result['level1'] == {'a': 1, 'b': 2, 'c': 3}

    def test_merge_deep_nested(self):
        """Test merging deeply nested dictionaries."""
        dest = {
            'l1': {
                'l2': {
                    'l3': {
                        'a': 1
                    }
                }
            }
        }
        source = {
            'l1': {
                'l2': {
                    'l3': {
                        'b': 2
                    },
                    'new': 'value'
                }
            }
        }

        result = deep_merge(dest, source)

        assert result['l1']['l2']['l3'] == {'a': 1, 'b': 2}
        assert result['l1']['l2']['new'] == 'value'

    def test_merge_creates_new_keys(self):
        """Test that merge creates new nested keys."""
        dest = {'existing': 1}
        source = {'new': {'nested': {'deep': 'value'}}}

        result = deep_merge(dest, source)

        assert result['existing'] == 1
        assert result['new']['nested']['deep'] == 'value'

    def test_merge_non_dict_overwrites_dict(self):
        """Test that non-dict values overwrite dict values."""
        dest = {'key': {'nested': 'value'}}
        source = {'key': 'flat_value'}

        result = deep_merge(dest, source)

        assert result['key'] == 'flat_value'

    def test_merge_empty_dicts(self):
        """Test merging empty dictionaries."""
        assert deep_merge({}, {}) == {}
        assert deep_merge({'a': 1}, {}) == {'a': 1}
        assert deep_merge({}, {'b': 2}) == {'b': 2}

    def test_merge_returns_destination(self):
        """Test that merge modifies and returns destination."""
        dest = {'a': 1}
        source = {'b': 2}

        result = deep_merge(dest, source)

        assert result is dest
        assert dest == {'a': 1, 'b': 2}


class TestConfigBuilderInit:
    """Test ConfigBuilder initialization."""

    def test_init(self):
        """Test ConfigBuilder initializes correctly."""
        builder = ConfigBuilder()
        assert builder.logger is not None


class TestConfigBuilderOpenFOAMSettings:
    """Test OpenFOAM settings application."""

    def test_apply_openfoam_12_settings_basic(self):
        """Test basic OpenFOAM 12 settings are applied."""
        builder = ConfigBuilder()
        config = {}

        result = builder._apply_openfoam_12_settings(config)

        assert result['openfoam_version'] == '12'
        assert result['openfoam_env_path'] == '/opt/openfoam12/etc/bashrc'
        assert result['openfoam_major_version'] == 12
        assert result['openfoam_foundation'] is True
        assert result['solver_application'] == 'foamRun'
        assert result['solver_module'] == 'incompressibleFluid'

    def test_apply_openfoam_12_settings_template_vars(self):
        """Test template variables are set."""
        builder = ConfigBuilder()
        config = {}

        result = builder._apply_openfoam_12_settings(config)

        assert 'template_vars' in result
        assert result['template_vars']['openfoam_version'] == '12'
        assert result['template_vars']['openfoam_major_version'] == 12

    def test_apply_openfoam_12_settings_run_settings(self):
        """Test run_settings defaults are set."""
        builder = ConfigBuilder()
        config = {}

        result = builder._apply_openfoam_12_settings(config)

        assert 'run_settings' in result
        assert result['run_settings']['decomposition_method'] == 'scotch'

    def test_apply_openfoam_12_settings_preserves_existing_run_settings(self):
        """Test existing run_settings are preserved."""
        builder = ConfigBuilder()
        config = {
            'run_settings': {
                'decomposition_method': 'hierarchical',
                'custom_key': 'custom_value'
            }
        }

        result = builder._apply_openfoam_12_settings(config)

        assert result['run_settings']['decomposition_method'] == 'hierarchical'
        assert result['run_settings']['custom_key'] == 'custom_value'

    def test_apply_openfoam_12_settings_new_physics_format(self):
        """Test new physics.transport_properties format."""
        builder = ConfigBuilder()
        config = {
            'physics': {
                'transport_properties': {
                    'nu': 3.77e-6,  # Kinematic viscosity in m²/s
                    'rho': 1060.0   # Density in kg/m³
                }
            }
        }

        result = builder._apply_openfoam_12_settings(config)

        assert result['physics']['nu'] == 3.77e-6
        assert result['physics']['rho'] == 1060.0
        # mu = nu * rho
        expected_mu = 3.77e-6 * 1060.0
        assert result['physics']['mu'] == pytest.approx(expected_mu, rel=1e-6)

    def test_apply_openfoam_12_settings_old_physics_format(self):
        """Test old physics format with default_viscosity/density."""
        builder = ConfigBuilder()
        mu = 0.004  # Dynamic viscosity in Pa·s
        rho = 1060.0  # Density in kg/m³
        config = {
            'physics': {
                'default_viscosity': mu,
                'default_density': rho
            }
        }

        result = builder._apply_openfoam_12_settings(config)

        expected_nu = mu / rho
        assert result['physics']['nu'] == pytest.approx(expected_nu, rel=1e-6)
        assert result['physics']['rho'] == rho
        assert result['physics']['mu'] == mu


class TestConfigBuilderValidation:
    """Test validation methods."""

    def test_validate_physical_parameters_valid(self):
        """Test validation passes for valid parameters."""
        builder = ConfigBuilder()
        config = {
            'physics': {
                'transport_properties': {
                    'nu': 3.77e-6,
                    'rho': 1060.0
                }
            }
        }

        # Should not raise
        builder._validate_physical_parameters(config)

    def test_validate_windkessel_parameters_valid(self):
        """Test Windkessel validation passes for valid parameters."""
        builder = ConfigBuilder()
        config = {
            'boundary_conditions': {
                'outlets': {
                    'type': '3EWINDKESSEL',
                    'windkessel_settings': {
                        'systolic_pressure': 120,
                        'diastolic_pressure': 80,
                        'tau': 1.8
                    }
                }
            }
        }

        # Should not raise
        builder._validate_windkessel_parameters(config)


class TestConfigBuilderMeshPresets:
    """Test mesh preset application."""

    def test_apply_mesh_quality_preset_none(self):
        """Test no preset applied when not specified."""
        builder = ConfigBuilder()
        config = {}

        result = builder._apply_mesh_quality_preset(config)

        # Should return config unchanged
        assert result == {}

    def test_apply_mesh_quality_preset_specified(self):
        """Test preset is applied when specified."""
        builder = ConfigBuilder()
        config = {
            'mesh': {
                'quality_preset': 'balanced'
            }
        }

        result = builder._apply_mesh_quality_preset(config)

        # Should have mesh quality settings
        assert 'mesh' in result


class TestConfigBuilderDiscovery:
    """Test case discovery methods."""

    def test_discover_case_config_missing_dir(self):
        """Test error when case directory doesn't exist."""
        builder = ConfigBuilder()

        with pytest.raises(FileNotFoundError) as exc_info:
            builder._discover_case_config("nonexistent_case", "/nonexistent/path")

        assert "not found" in str(exc_info.value)

    def test_discover_case_config_with_stl_files(self):
        """Test STL file discovery."""
        builder = ConfigBuilder()

        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = os.path.join(tmpdir, "test_case")
            os.makedirs(case_dir)

            # Create mock STL files
            Path(case_dir, "wall.stl").touch()
            Path(case_dir, "inlet.stl").touch()
            Path(case_dir, "outlet1.stl").touch()
            Path(case_dir, "outlet2.stl").touch()

            result = builder._discover_case_config("test_case", tmpdir)

            assert result['geometry']['case_name'] == "test_case"
            assert result['geometry']['wall_keywords_ordered'] == "wall"
            assert result['geometry']['inlet_keywords_ordered'] == "inlet"
            assert 'outlet1' in result['geometry']['outlet_keywords_ordered']
            assert 'outlet2' in result['geometry']['outlet_keywords_ordered']

    def test_discover_case_config_with_bc_json(self):
        """Test boundary conditions JSON discovery."""
        builder = ConfigBuilder()

        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = os.path.join(tmpdir, "test_case")
            os.makedirs(case_dir)

            # Create mock STL files
            Path(case_dir, "wall.stl").touch()
            Path(case_dir, "inlet.stl").touch()
            Path(case_dir, "outlet.stl").touch()

            # Create boundary_conditions.json
            bc_config = {
                'boundary_conditions': {
                    'inlet': {'type': 'TIMEVARYING'},
                    'outlets': {'type': '3EWINDKESSEL'}
                }
            }
            with open(os.path.join(case_dir, "boundary_conditions.json"), 'w') as f:
                json.dump(bc_config, f)

            result = builder._discover_case_config("test_case", tmpdir)

            assert result['boundary_conditions']['inlet']['type'] == 'TIMEVARYING'
            assert result['boundary_conditions']['outlets']['type'] == '3EWINDKESSEL'


class TestConfigBuilderConvertUnifiedConfig:
    """Test unified config conversion."""

    def test_convert_unified_config_basic(self):
        """Test basic unified config conversion."""
        builder = ConfigBuilder()

        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = os.path.join(tmpdir, "test_case")
            os.makedirs(case_dir)

            # Create mock STL files
            Path(case_dir, "wall.stl").touch()
            Path(case_dir, "inlet.stl").touch()
            Path(case_dir, "outlet.stl").touch()

            case_config = {
                'cardiac_cycle': 0.85,
                'boundary_conditions': {
                    'inlet': {'type': 'CONSTANT', 'velocity': 0.5}
                },
                'simulation_control': {
                    'end_time': 5.0
                }
            }

            result = builder._convert_unified_config("test_case", case_config, tmpdir)

            assert result['cardiac_cycle'] == 0.85
            assert result['boundary_conditions']['inlet']['type'] == 'CONSTANT'
            assert result['simulation_control']['end_time'] == 5.0

    def test_convert_unified_config_missing_dir(self):
        """Test error when case directory doesn't exist."""
        builder = ConfigBuilder()

        with pytest.raises(FileNotFoundError):
            builder._convert_unified_config("nonexistent", {}, "/nonexistent/path")


class TestConfigBuilderWarnings:
    """Test warning methods."""

    def test_warn_if_no_explicit_mesh_with_explicit(self):
        """Test no warning when mesh is explicit."""
        builder = ConfigBuilder()
        config = {
            'mesh': {
                'mesh_resolution': {
                    'target_cell_size_mm': 1.0
                }
            }
        }

        # Should not warn (we can't easily test warnings, but should not raise)
        builder._warn_if_no_explicit_mesh(config, 'standard')

    def test_warn_if_no_explicit_mesh_without_explicit(self):
        """Test warning when mesh is not explicit."""
        builder = ConfigBuilder()
        config = {}

        # Should warn but not raise
        builder._warn_if_no_explicit_mesh(config, 'standard')


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
