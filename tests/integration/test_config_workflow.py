"""
Integration tests for configuration workflow.

Tests end-to-end configuration loading, merging, and validation.
"""

import pytest
import json
from pathlib import Path
from src.config.builder import ConfigBuilder
from src.config.profiles.profile_builder import ProfileComposer


@pytest.mark.integration
class TestConfigurationWorkflow:
    """Test complete configuration workflow."""

    def test_full_config_build_laminar_coarse(self, temp_case_dir):
        """Test building complete configuration for laminar coarse simulation."""
        builder = ConfigBuilder()

        # Step 1: Build base + profile
        config = builder.build_base_and_profile("sim_laminar_coarse")

        # Verify structure
        assert "physics" in config
        assert "mesh" in config
        assert "run_settings" in config

        # Verify laminar settings
        assert config["physics"]["simulation_type"] == "laminar"

        # Step 2: Validate (should not raise warnings for valid config)
        builder._validate_physical_parameters(config)

    def test_full_config_build_rans_medium(self, temp_case_dir):
        """Test building complete configuration for RANS medium simulation."""
        builder = ConfigBuilder()

        config = builder.build_base_and_profile("sim_rans_medium")

        # Verify RANS settings
        assert config["physics"]["simulation_type"] == "RAS"
        assert config["physics"]["turbulence_model"] == "kOmegaSST"
        assert "turbulence_intensity" in config["physics"]

        builder._validate_physical_parameters(config)

    def test_user_override_workflow(self, temp_case_dir, write_json_file):
        """Test that user config overrides profile settings."""
        builder = ConfigBuilder()

        # Step 1: Build base + profile
        base_and_profile = builder.build_base_and_profile("sim_laminar_coarse")

        # Step 2: User wants custom settings
        user_config_file = temp_case_dir / "config.json"
        user_config = {
            "physics": {
                "blood_density": 1100,  # Custom density
                "blood_viscosity": 0.005  # Custom viscosity
            },
            "mesh": {
                "SNAPPY_SETTINGS": {
                    "nProcessors": 8  # User wants 8 cores
                }
            }
        }
        write_json_file(user_config_file, user_config)

        # Step 3: Load and merge user config
        with open(user_config_file) as f:
            loaded_user_config = json.load(f)

        from src.config.builder import deep_merge
        final_config = deep_merge(base_and_profile, loaded_user_config)

        # User values should win
        assert final_config["physics"]["blood_density"] == 1100
        assert final_config["physics"]["blood_viscosity"] == 0.005
        assert final_config["mesh"]["SNAPPY_SETTINGS"]["nProcessors"] == 8

        # Profile values should be preserved where not overridden
        assert "simulation_type" in final_config["physics"]

    def test_fragment_composition_workflow(self):
        """Test composing configuration from multiple fragments."""
        composer = ProfileComposer()

        # Compose from three axes
        config = composer.compose(
            spatial_resolution="medium",
            solver_recipe="balanced",
            turbulence_model="rans_komega_sst"
        )

        # Verify all fragments contributed
        assert "mesh" in config
        assert "solver_settings" in config
        assert "physics" in config

        # Verify RANS settings from turbulence fragment
        assert config["physics"]["simulation_type"] == "RAS"
        assert config["physics"]["turbulence_model"] == "kOmegaSST"

    def test_profile_loading_all_profiles(self):
        """Test that all standard profiles load without errors."""
        builder = ConfigBuilder()

        profiles = [
            "sim_laminar_coarse",
            "sim_laminar_medium",
            "sim_laminar_fine",
            "sim_rans_coarse",
            "sim_rans_medium",
            "sim_rans_fine",
            "sim_les_medium",
            "sim_les_fine"
        ]

        for profile_name in profiles:
            config = builder.build_base_and_profile(profile_name)

            # Basic validation
            assert "physics" in config
            assert "mesh" in config
            assert "simulation_type" in config["physics"]

            # Validate physical parameters (should not crash)
            builder._validate_physical_parameters(config)

    def test_validation_workflow_catches_issues(self, caplog):
        """Test that validation catches common issues."""
        builder = ConfigBuilder()

        # Create config with suspicious values
        config = {
            "physics": {
                "default_density": 5000,  # Too high
                "nu": 0.5  # Too high
            },
            "solver_settings": {
                "maxCo": 10.0  # Dangerously high
            },
            "time_settings": {
                "end_time": -1.0  # Invalid
            }
        }

        builder._validate_physical_parameters(config)

        # Should have warnings in log
        log_text = caplog.text.lower()
        assert "density" in log_text or "warning" in log_text
        assert "viscosity" in log_text or "nu" in log_text or "warning" in log_text


@pytest.mark.integration
class TestConfigurationMergeOrder:
    """Test correct merge order in realistic scenarios."""

    def test_realistic_patient_case_merge(self, temp_case_dir, write_json_file):
        """Test realistic patient case with merge order: Base → Profile → Fragments → User."""
        builder = ConfigBuilder()
        composer = ProfileComposer()

        # Step 1: Base + Profile
        base_and_profile = builder.build_base_and_profile("sim_rans_medium")

        # Step 2: Fragments (happens inside profile, but simulating here)
        # Already included in sim_rans_medium profile

        # Step 3: User config
        user_config = {
            "case_info": {
                "patient_id": "test_patient_123",
                "description": "Test patient with aortic coarctation"
            },
            "physics": {
                "blood_density": 1055,  # Patient-specific
                "blood_viscosity": 0.0042  # Patient-specific
            },
            "mesh": {
                "SNAPPY_SETTINGS": {
                    "nProcessors": 12  # User has 12-core workstation
                }
            }
        }

        # Final merge
        from src.config.builder import deep_merge
        final_config = deep_merge(base_and_profile, user_config)

        # Verify merge order
        assert final_config["case_info"]["patient_id"] == "test_patient_123"
        assert final_config["physics"]["blood_density"] == 1055  # User wins
        assert final_config["physics"]["blood_viscosity"] == 0.0042  # User wins
        assert final_config["mesh"]["SNAPPY_SETTINGS"]["nProcessors"] == 12  # User wins

        # RANS settings from profile should be preserved
        assert final_config["physics"]["simulation_type"] == "RAS"
        assert final_config["physics"]["turbulence_model"] == "kOmegaSST"


@pytest.mark.integration
@pytest.mark.slow
class TestConfigurationPerformance:
    """Test configuration system performance."""

    def test_config_loading_performance(self):
        """Test that configuration loading is fast."""
        import time

        builder = ConfigBuilder()

        start = time.time()
        for _ in range(10):
            config = builder.build_base_and_profile("sim_rans_medium")
        elapsed = time.time() - start

        # Should load 10 configs in under 1 second
        assert elapsed < 1.0

    def test_validation_performance(self):
        """Test that validation is fast."""
        import time

        builder = ConfigBuilder()
        config = builder.build_base_and_profile("sim_rans_medium")

        start = time.time()
        for _ in range(100):
            builder._validate_physical_parameters(config)
        elapsed = time.time() - start

        # Should validate 100 times in under 0.1 seconds
        assert elapsed < 0.1
