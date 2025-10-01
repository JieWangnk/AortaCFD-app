"""
Unit tests for ConfigBuilder class.

Tests configuration building, merging, and validation.
"""

import pytest
from pathlib import Path
from src.config.builder import ConfigBuilder, deep_merge


class TestDeepMerge:
    """Test the deep_merge utility function."""

    def test_merge_simple_dicts(self):
        """Test merging simple dictionaries."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)

        assert result["a"] == 1
        assert result["b"] == 3  # Override wins
        assert result["c"] == 4

    def test_merge_nested_dicts(self):
        """Test merging nested dictionaries."""
        base = {
            "physics": {"density": 1000, "viscosity": 0.003},
            "mesh": {"type": "hex"}
        }
        override = {
            "physics": {"density": 1060},  # Override density only
            "solver": {"maxCo": 1.0}  # Add new section
        }
        result = deep_merge(base, override)

        assert result["physics"]["density"] == 1060  # Overridden
        assert result["physics"]["viscosity"] == 0.003  # Preserved
        assert result["mesh"]["type"] == "hex"  # Preserved
        assert result["solver"]["maxCo"] == 1.0  # Added

    def test_merge_modifies_destination_inplace(self):
        """Test that merge modifies destination dict in-place (by design)."""
        base = {"a": 1}
        override = {"b": 2}

        result = deep_merge(base, override)

        # deep_merge modifies destination in-place and returns it
        assert result is base  # Returns the modified destination
        assert result == {"a": 1, "b": 2}
        assert base == {"a": 1, "b": 2}  # Base was modified

    def test_merge_empty_dicts(self):
        """Test merging with empty dictionaries."""
        base = {"a": 1}
        result1 = deep_merge(base, {})
        result2 = deep_merge({}, base)

        assert result1 == {"a": 1}
        assert result2 == {"a": 1}

    def test_merge_override_with_none(self):
        """Test that None values in override are applied."""
        base = {"a": 1, "b": 2}
        override = {"a": None}
        result = deep_merge(base, override)

        assert result["a"] is None
        assert result["b"] == 2


class TestConfigBuilder:
    """Test ConfigBuilder class."""

    @pytest.fixture
    def builder(self):
        """Create a ConfigBuilder instance."""
        return ConfigBuilder()

    def test_builder_initialization(self, builder):
        """Test ConfigBuilder initializes correctly."""
        assert builder is not None
        assert hasattr(builder, 'logger')
        assert builder.logger.name == "ConfigBuilder"

    def test_build_base_and_profile_laminar_coarse(self, builder):
        """Test building base + profile without case overrides."""
        config = builder.build_base_and_profile("sim_laminar_coarse")

        # Check basic structure
        assert "physics" in config
        assert "mesh" in config
        assert "run_settings" in config

        # Check laminar-specific settings
        assert config["physics"]["simulation_type"] == "laminar"

    def test_build_base_and_profile_rans_medium(self, builder):
        """Test building RANS profile."""
        config = builder.build_base_and_profile("sim_rans_medium")

        # Check RANS-specific settings
        assert config["physics"]["simulation_type"] == "RAS"
        assert "turbulence_model" in config["physics"]
        assert config["physics"]["turbulence_model"] == "kOmegaSST"

    def test_build_base_and_profile_les_fine(self, builder):
        """Test building LES profile."""
        config = builder.build_base_and_profile("sim_les_fine")

        # Check LES-specific settings
        assert config["physics"]["simulation_type"] == "LES"

    def test_validate_physical_parameters_valid(self, builder, full_config):
        """Test validation passes for valid parameters."""
        # Should not raise any exceptions
        builder._validate_physical_parameters(full_config)

    def test_validate_physical_parameters_warns_high_density(self, builder, caplog):
        """Test validation warns for unrealistic density."""
        import logging
        caplog.set_level(logging.INFO)

        config = {
            "physics": {
                "default_density": 5000  # Way too high
            }
        }

        builder._validate_physical_parameters(config)
        log_text = caplog.text.lower()
        assert "density" in log_text or "warning" in log_text or "⚠" in caplog.text

    def test_validate_physical_parameters_warns_high_viscosity(self, builder, caplog):
        """Test validation warns for unrealistic viscosity."""
        import logging
        caplog.set_level(logging.INFO)

        config = {
            "physics": {
                "mu": 0.5  # Way too high (should be default_viscosity or mu)
            }
        }

        builder._validate_physical_parameters(config)
        log_text = caplog.text.lower()
        assert "viscosity" in log_text or "warning" in log_text

    def test_validate_physical_parameters_warns_negative_end_time(self, builder, caplog):
        """Test validation warns for negative end time."""
        import logging
        caplog.set_level(logging.INFO)

        config = {
            "simulation_control": {
                "end_time": -1.0
            }
        }

        builder._validate_physical_parameters(config)
        log_text = caplog.text.lower()
        assert "end" in log_text or "time" in log_text or "warning" in log_text

    def test_validate_physical_parameters_warns_maxco_too_low(self, builder, caplog):
        """Test validation warns for maxCo too low."""
        import logging
        caplog.set_level(logging.INFO)

        config = {
            "time_stepping": {
                "maxCo": 0.05  # Too low
            }
        }

        builder._validate_physical_parameters(config)
        log_text = caplog.text.lower()
        assert "maxco" in log_text or "courant" in log_text or "warning" in log_text

    def test_validate_physical_parameters_warns_maxco_too_high(self, builder, caplog):
        """Test validation warns for maxCo too high."""
        import logging
        caplog.set_level(logging.INFO)

        config = {
            "time_stepping": {
                "maxCo": 5.0  # Too high, may diverge
            }
        }

        builder._validate_physical_parameters(config)
        log_text = caplog.text.lower()
        assert "maxco" in log_text or "courant" in log_text or "warning" in log_text

    def test_validate_physical_parameters_warns_processor_mismatch(self, builder, caplog):
        """Test validation warns when mesh and solver processors don't match."""
        import logging
        caplog.set_level(logging.INFO)

        config = {
            "mesh": {
                "SNAPPY_SETTINGS": {
                    "nProcessors": 4
                }
            },
            "run_settings": {
                "subdomains": 8  # Mismatch
            }
        }

        builder._validate_physical_parameters(config)
        log_text = caplog.text.lower()
        assert "processor" in log_text or "cpu" in log_text or "core" in log_text

    def test_merge_order_user_config_wins(self, builder):
        """Test that user's config.json overrides everything."""
        # Build base + profile
        base_and_profile = builder.build_base_and_profile("sim_laminar_coarse")

        # User wants custom density
        user_config = {
            "physics": {
                "blood_density": 1100  # Custom value
            }
        }

        # Merge: base_and_profile → user_config
        result = deep_merge(base_and_profile, user_config)

        # User value should win
        assert result["physics"]["blood_density"] == 1100


class TestConfigMergeOrder:
    """Test the correct merge order: Base → Profile → Fragments → Case Config."""

    def test_fragment_does_not_override_user(self):
        """Test that fragments don't override user's case config."""
        base = {"physics": {"density": 1000}}
        profile = {"physics": {"viscosity": 0.003}}
        fragment = {"physics": {"density": 1050}}
        user_config = {"physics": {"density": 1100}}

        # Correct order: Base → Profile → Fragments → User
        result = deep_merge({}, base)
        result = deep_merge(result, profile)
        result = deep_merge(result, fragment)
        result = deep_merge(result, user_config)

        # User value should be final
        assert result["physics"]["density"] == 1100
        assert result["physics"]["viscosity"] == 0.003

    def test_profile_overrides_base(self):
        """Test that profile overrides base settings."""
        base = {"solver": {"maxCo": 0.5}}
        profile = {"solver": {"maxCo": 1.0}}

        result = deep_merge(base, profile)

        assert result["solver"]["maxCo"] == 1.0


@pytest.mark.unit
class TestConfigValidation:
    """Test configuration validation logic."""

    @pytest.fixture
    def builder(self):
        return ConfigBuilder()

    def test_validation_allows_normal_blood_density(self, builder):
        """Test that normal blood density (1060) passes validation."""
        config = {"physics": {"default_density": 1060}}
        # Should not raise or warn excessively
        builder._validate_physical_parameters(config)

    def test_validation_allows_normal_blood_viscosity(self, builder):
        """Test that normal blood viscosity (0.004) passes validation."""
        config = {"physics": {"nu": 3.77e-06}}  # Kinematic viscosity
        builder._validate_physical_parameters(config)

    def test_validation_handles_missing_physics_section(self, builder):
        """Test validation doesn't crash when physics section is missing."""
        config = {"mesh": {"type": "hex"}}
        # Should not crash
        builder._validate_physical_parameters(config)

    def test_validation_handles_empty_config(self, builder):
        """Test validation handles completely empty config."""
        config = {}
        # Should not crash
        builder._validate_physical_parameters(config)
