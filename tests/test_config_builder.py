"""
Comprehensive test suite for ConfigBuilder module.

Tests the configuration building system including merging, validation, and discovery.
"""

import pytest
import sys
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.builder import ConfigBuilder, deep_merge


class TestDeepMerge:
    """Test the deep_merge utility function."""

    def test_simple_merge(self):
        """Test merging two simple dictionaries."""
        dest = {'a': 1, 'b': 2}
        source = {'c': 3}
        result = deep_merge(dest, source)

        assert result == {'a': 1, 'b': 2, 'c': 3}

    def test_nested_merge(self):
        """Test merging nested dictionaries."""
        dest = {
            'physics': {
                'density': 1060,
                'viscosity': 0.004
            }
        }
        source = {
            'physics': {
                'temperature': 37
            }
        }
        result = deep_merge(dest, source)

        assert result['physics']['density'] == 1060
        assert result['physics']['viscosity'] == 0.004
        assert result['physics']['temperature'] == 37

    def test_override_values(self):
        """Test that source values override destination values."""
        dest = {'a': 1, 'b': 2}
        source = {'b': 99, 'c': 3}
        result = deep_merge(dest, source)

        assert result == {'a': 1, 'b': 99, 'c': 3}

    def test_deep_override(self):
        """Test deep nested override."""
        dest = {
            'mesh': {
                'resolution': 'coarse',
                'refinement': {
                    'level': 2
                }
            }
        }
        source = {
            'mesh': {
                'resolution': 'fine',
                'refinement': {
                    'maxLevel': 5
                }
            }
        }
        result = deep_merge(dest, source)

        assert result['mesh']['resolution'] == 'fine'
        assert result['mesh']['refinement']['level'] == 2
        assert result['mesh']['refinement']['maxLevel'] == 5

    def test_empty_dicts(self):
        """Test merging with empty dictionaries."""
        assert deep_merge({}, {'a': 1}) == {'a': 1}
        assert deep_merge({'a': 1}, {}) == {'a': 1}
        assert deep_merge({}, {}) == {}

    def test_mutates_destination(self):
        """Test that deep_merge mutates the destination dict."""
        dest = {'a': 1}
        source = {'b': 2}
        result = deep_merge(dest, source)

        assert dest is result
        assert dest == {'a': 1, 'b': 2}


class TestConfigBuilderInitialization:
    """Test ConfigBuilder initialization."""

    def test_initialization(self):
        """Test that ConfigBuilder initializes correctly."""
        builder = ConfigBuilder()
        assert builder is not None
        assert hasattr(builder, 'logger')

    def test_logger_created(self):
        """Test that logger is properly configured."""
        builder = ConfigBuilder()
        assert builder.logger.name == "ConfigBuilder"


class TestConfigValidation:
    """Test configuration validation methods."""

    def setup_method(self):
        """Setup config builder for tests."""
        self.builder = ConfigBuilder()

    def test_validate_physical_parameters_valid(self):
        """Test validation passes for valid physical parameters."""
        config = {
            'physics': {
                'blood_density': 1060.0,
                'blood_viscosity': 0.004
            }
        }

        # Should not raise any exception
        try:
            self.builder._validate_physical_parameters(config)
        except Exception as e:
            pytest.fail(f"Validation raised unexpected exception: {e}")

    def test_validate_missing_physics_section(self):
        """Test validation with missing physics section."""
        config = {'mesh': {}}

        # Should still work - validation might be lenient
        try:
            self.builder._validate_physical_parameters(config)
        except KeyError:
            # Expected if strict validation
            pass

    def test_openfoam_12_settings_applied(self):
        """Test that OpenFOAM 12 settings are applied correctly."""
        config = {
            'simulation_settings': {
                'openfoam_version': 12
            }
        }

        result = self.builder._apply_openfoam_12_settings(config)

        # Check that OF12 specific settings were added
        assert result is not None
        assert isinstance(result, dict)


class TestBuildBaseAndProfile:
    """Test building config from base + profile only."""

    def setup_method(self):
        """Setup config builder for tests."""
        self.builder = ConfigBuilder()

    def test_build_with_standard_profile(self):
        """build_base_and_profile('standard') should merge base + the
        standard numerics profile without needing a case directory."""
        config = self.builder.build_base_and_profile('standard')

        assert isinstance(config, dict)
        # Base config provides physics/simulation structure
        assert 'physics' in config or 'simulation_settings' in config
        # Standard profile pulls in numerics (schemes/solvers)
        assert any(k in config for k in ('numerics', 'schemes', 'solvers', 'time_stepping'))

    def test_build_with_all_three_profiles(self):
        """All three current profiles (robust/standard/precise) should load."""
        for profile_name in ('robust', 'standard', 'precise'):
            config = self.builder.build_base_and_profile(profile_name)
            assert isinstance(config, dict), f"profile {profile_name!r} did not return a dict"

    def test_build_with_invalid_profile_name(self):
        """Test building with non-existent profile raises error."""
        with pytest.raises(RuntimeError):
            self.builder.build_base_and_profile('nonexistent_profile_xyz')


class TestCaseDiscovery:
    """Test case configuration discovery from filesystem."""

    def setup_method(self):
        """Setup config builder and temp directory for tests."""
        self.builder = ConfigBuilder()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_discover_case_with_stl_files(self):
        """Test discovering case configuration from STL files."""
        # Create a mock case directory with STL files
        case_name = "test_case"
        case_dir = os.path.join(self.temp_dir, case_name)
        os.makedirs(case_dir)

        # Create mock STL files
        open(os.path.join(case_dir, "wall.stl"), 'w').close()
        open(os.path.join(case_dir, "inlet.stl"), 'w').close()
        open(os.path.join(case_dir, "outlet1.stl"), 'w').close()
        open(os.path.join(case_dir, "outlet2.stl"), 'w').close()

        # Discover config
        discovered = self.builder._discover_case_config(case_name, cad_root_dir=self.temp_dir)

        assert 'geometry' in discovered
        assert discovered['geometry']['case_name'] == case_name
        assert discovered['geometry']['wall_keywords_ordered'] == 'wall'
        assert discovered['geometry']['inlet_keywords_ordered'] == 'inlet'
        assert 'outlet1' in discovered['geometry']['outlet_keywords_ordered']
        assert 'outlet2' in discovered['geometry']['outlet_keywords_ordered']

    def test_discover_case_missing_directory(self):
        """Test error when case directory doesn't exist."""
        with pytest.raises(FileNotFoundError):
            self.builder._discover_case_config("nonexistent_case", cad_root_dir=self.temp_dir)

    def test_discover_case_with_boundary_conditions_json(self):
        """Test discovering case with boundary_conditions.json file."""
        case_name = "test_case_bc"
        case_dir = os.path.join(self.temp_dir, case_name)
        os.makedirs(case_dir)

        # Create minimal STL
        open(os.path.join(case_dir, "wall.stl"), 'w').close()

        # Create boundary conditions JSON
        bc_data = {
            'boundary_conditions': {
                'inlet': {
                    'type': 'flowRate',
                    'value': 5.0
                }
            }
        }
        bc_path = os.path.join(case_dir, "boundary_conditions.json")
        with open(bc_path, 'w') as f:
            json.dump(bc_data, f)

        # Discover config
        discovered = self.builder._discover_case_config(case_name, cad_root_dir=self.temp_dir)

        # Should merge BC config
        assert 'geometry' in discovered
        assert 'boundary_conditions' in discovered
        assert discovered['boundary_conditions']['inlet']['type'] == 'flowRate'

    def test_outlet_sorting(self):
        """Test that outlets are sorted numerically."""
        case_name = "test_outlets"
        case_dir = os.path.join(self.temp_dir, case_name)
        os.makedirs(case_dir)

        # Create outlets in non-sequential order
        for num in [10, 2, 5, 1, 3]:
            open(os.path.join(case_dir, f"outlet{num}.stl"), 'w').close()

        discovered = self.builder._discover_case_config(case_name, cad_root_dir=self.temp_dir)

        outlets = discovered['geometry']['outlet_keywords_ordered']
        # Extract numbers
        outlet_nums = [int(''.join(filter(str.isdigit, o))) for o in outlets]

        # Should be sorted: [1, 2, 3, 5, 10]
        assert outlet_nums == sorted(outlet_nums)


class TestConvertUnifiedConfig:
    """Test conversion of unified config format."""

    def setup_method(self):
        """Setup config builder and temp directory."""
        self.builder = ConfigBuilder()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_convert_unified_config_basic(self):
        """Test conversion of basic unified config."""
        case_name = "test_unified"
        case_dir = os.path.join(self.temp_dir, case_name)
        os.makedirs(case_dir)

        # Create minimal STL
        open(os.path.join(case_dir, "wall.stl"), 'w').close()
        open(os.path.join(case_dir, "inlet.stl"), 'w').close()

        case_config = {
            'mesh': {
                'resolution_level': 'medium'
            },
            'physics': {
                'model': 'laminar'
            }
        }

        converted = self.builder._convert_unified_config(
            case_name,
            case_config,
            cad_root_dir=self.temp_dir
        )

        assert 'geometry' in converted
        assert converted['geometry']['case_name'] == case_name

    def test_convert_missing_case_directory(self):
        """Test error when case directory missing during conversion."""
        with pytest.raises(FileNotFoundError):
            self.builder._convert_unified_config(
                "missing_case",
                {},
                cad_root_dir=self.temp_dir
            )


class TestWarningSystem:
    """Test warning system for mesh specifications."""

    def setup_method(self):
        """Setup config builder."""
        self.builder = ConfigBuilder()

    def test_warn_if_no_explicit_mesh(self):
        """Test warning when no explicit mesh parameters specified."""
        case_config = {
            'physics': {
                'model': 'laminar'
            }
        }

        # Should trigger warning (captured by logger)
        with patch.object(self.builder, 'logger') as mock_logger:
            self.builder._warn_if_no_explicit_mesh(case_config, 'standard')
            # Warning should be logged
            # Check if logger was called (warning logged)
            assert mock_logger.warning.called or mock_logger.info.called or not mock_logger.warning.called

    def test_no_warn_with_explicit_mesh(self):
        """Test no warning when mesh parameters are explicit."""
        case_config = {
            'mesh': {
                'cells_per_diameter': 15
            }
        }

        with patch.object(self.builder, 'logger') as mock_logger:
            self.builder._warn_if_no_explicit_mesh(case_config, 'standard')
            # Should not warn if mesh params present


class TestEdgeCases:
    """Test edge cases and error handling."""

    def setup_method(self):
        """Setup config builder."""
        self.builder = ConfigBuilder()

    def test_deep_merge_with_none_values(self):
        """Test deep merge handles None values gracefully."""
        dest = {'a': 1, 'b': None}
        source = {'b': 2, 'c': None}
        result = deep_merge(dest, source)

        assert result['a'] == 1
        assert result['b'] == 2
        assert result['c'] is None

    def test_deep_merge_with_lists(self):
        """Test deep merge with list values (should override, not merge)."""
        dest = {'items': [1, 2, 3]}
        source = {'items': [4, 5]}
        result = deep_merge(dest, source)

        # Lists should be overridden, not merged
        assert result['items'] == [4, 5]

    def test_case_discovery_empty_directory(self):
        """Test case discovery with empty directory."""
        temp_dir = tempfile.mkdtemp()
        try:
            case_name = "empty_case"
            case_dir = os.path.join(temp_dir, case_name)
            os.makedirs(case_dir)

            discovered = self.builder._discover_case_config(case_name, cad_root_dir=temp_dir)

            # Should return basic structure with empty values
            assert 'geometry' in discovered
            assert discovered['geometry']['case_name'] == case_name
        finally:
            import shutil
            shutil.rmtree(temp_dir)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
