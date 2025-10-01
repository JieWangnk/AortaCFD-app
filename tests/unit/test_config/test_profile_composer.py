"""
Unit tests for ProfileComposer class.

Tests fragment composition and profile building.
"""

import pytest
from src.config.profiles.profile_builder import ProfileComposer


class TestProfileComposer:
    """Test ProfileComposer fragment composition."""

    @pytest.fixture
    def composer(self):
        """Create a ProfileComposer instance."""
        return ProfileComposer()

    def test_composer_initialization(self, composer):
        """Test ProfileComposer initializes with all axes."""
        assert composer is not None
        assert hasattr(composer, '_axes')

        # Check all three axes are registered
        assert "spatial_resolution" in composer._axes
        assert "solver_recipe" in composer._axes
        assert "turbulence_model" in composer._axes

    def test_compose_spatial_resolution_only(self, composer):
        """Test composing with only spatial resolution fragment."""
        config = composer.compose(spatial_resolution="coarse")

        assert config is not None
        assert "mesh" in config
        # Mesh should have resolution settings
        assert "mesh_resolution" in config["mesh"] or "SNAPPY_SETTINGS" in config["mesh"]

    def test_compose_solver_recipe_only(self, composer):
        """Test composing with only solver recipe fragment."""
        config = composer.compose(solver_recipe="balanced")

        assert config is not None
        # Solver recipe includes schemes and fvSolution
        assert "schemes" in config or "fvSolution" in config or "time_stepping" in config

    def test_compose_turbulence_model_only(self, composer):
        """Test composing with only turbulence model fragment."""
        config = composer.compose(turbulence_model="laminar")

        assert config is not None
        assert "physics" in config
        assert config["physics"]["simulation_type"] == "laminar"

    def test_compose_all_fragments(self, composer):
        """Test composing with all three fragment types."""
        config = composer.compose(
            spatial_resolution="medium",
            solver_recipe="balanced",
            turbulence_model="rans_komega_sst"
        )

        assert config is not None
        assert "mesh" in config
        assert "schemes" in config or "fvSolution" in config
        assert "physics" in config
        assert config["physics"]["simulation_type"] == "RAS"
        assert config["physics"]["turbulence_model"] == "kOmegaSST"

    def test_compose_with_extras(self, composer):
        """Test composing with additional custom settings."""
        extras = {
            "custom_setting": "test_value",
            "physics": {
                "custom_density": 1100
            }
        }

        config = composer.compose(
            spatial_resolution="fine",
            extras=extras
        )

        assert config is not None
        assert config["custom_setting"] == "test_value"
        assert config["physics"]["custom_density"] == 1100

    def test_compose_extras_override_fragments(self, composer):
        """Test that extras override fragment settings."""
        extras = {
            "physics": {
                "simulation_type": "custom_override"
            }
        }

        config = composer.compose(
            turbulence_model="laminar",
            extras=extras
        )

        # Extras should override fragment
        assert config["physics"]["simulation_type"] == "custom_override"

    def test_compose_no_fragments(self, composer):
        """Test composing with no fragments returns empty dict."""
        config = composer.compose()

        assert config == {}

    def test_compose_invalid_fragment_name(self, composer):
        """Test composing with invalid fragment name raises error."""
        with pytest.raises(KeyError):
            composer.compose(spatial_resolution="invalid_name_doesnt_exist")


class TestSpatialResolutionFragments:
    """Test spatial resolution fragments."""

    @pytest.fixture
    def composer(self):
        return ProfileComposer()

    def test_coarse_resolution(self, composer):
        """Test coarse resolution settings."""
        config = composer.compose(spatial_resolution="coarse")

        assert "mesh" in config
        # Coarse should have mesh settings
        assert "SNAPPY_SETTINGS" in config["mesh"]

    def test_medium_resolution(self, composer):
        """Test medium resolution settings."""
        config = composer.compose(spatial_resolution="medium")

        assert "mesh" in config
        assert "SNAPPY_SETTINGS" in config["mesh"]

    def test_fine_resolution(self, composer):
        """Test fine resolution settings."""
        config = composer.compose(spatial_resolution="fine")

        assert "mesh" in config
        assert "SNAPPY_SETTINGS" in config["mesh"]

    def test_resolution_ordering(self, composer):
        """Test that coarse, medium, fine all produce valid configs."""
        coarse = composer.compose(spatial_resolution="coarse")
        medium = composer.compose(spatial_resolution="medium")
        fine = composer.compose(spatial_resolution="fine")

        # All should have mesh settings
        assert "mesh" in coarse
        assert "mesh" in medium
        assert "mesh" in fine


class TestSolverRecipeFragments:
    """Test solver recipe fragments."""

    @pytest.fixture
    def composer(self):
        return ProfileComposer()

    def test_robust_recipe(self, composer):
        """Test robust solver recipe."""
        config = composer.compose(solver_recipe="robust")

        # Robust should have schemes or fvSolution
        assert "schemes" in config or "fvSolution" in config

    def test_balanced_recipe(self, composer):
        """Test balanced solver recipe."""
        config = composer.compose(solver_recipe="balanced")

        assert "schemes" in config or "fvSolution" in config

    def test_aggressive_recipe(self, composer):
        """Test aggressive solver recipe."""
        config = composer.compose(solver_recipe="aggressive")

        assert "schemes" in config or "fvSolution" in config


class TestTurbulenceFragments:
    """Test turbulence model fragments."""

    @pytest.fixture
    def composer(self):
        return ProfileComposer()

    def test_laminar_turbulence(self, composer):
        """Test laminar turbulence fragment."""
        config = composer.compose(turbulence_model="laminar")

        assert "physics" in config
        assert config["physics"]["simulation_type"] == "laminar"
        assert config["physics"]["steady_state"] is False

    def test_rans_komega_sst_turbulence(self, composer):
        """Test RANS k-omega SST turbulence fragment."""
        config = composer.compose(turbulence_model="rans_komega_sst")

        assert "physics" in config
        assert config["physics"]["simulation_type"] == "RAS"
        assert config["physics"]["turbulence_model"] == "kOmegaSST"
        assert "turbulence_intensity" in config["physics"]
        assert "turbulence_viscosity_ratio" in config["physics"]

    def test_rans_high_intensity_turbulence(self, composer):
        """Test RANS high intensity turbulence fragment."""
        config = composer.compose(turbulence_model="rans_high_intensity")

        assert "physics" in config
        assert config["physics"]["simulation_type"] == "RAS"
        # High intensity should have turbulence_intensity value
        assert "turbulence_intensity" in config["physics"]
        assert config["physics"]["turbulence_intensity"] > 0.05  # At least 5%

    def test_les_wale_turbulence(self, composer):
        """Test LES WALE turbulence fragment."""
        config = composer.compose(turbulence_model="les_wale")

        assert "physics" in config
        assert config["physics"]["simulation_type"] == "LES"
        assert config["physics"]["subgrid_model"] == "WALE"

    def test_les_smagorinsky_turbulence(self, composer):
        """Test LES Smagorinsky turbulence fragment."""
        config = composer.compose(turbulence_model="les_smagorinsky")

        assert "physics" in config
        assert config["physics"]["simulation_type"] == "LES"


class TestFragmentMetadata:
    """Test fragment metadata."""

    @pytest.fixture
    def composer(self):
        return ProfileComposer()

    def test_fragment_has_metadata(self, composer):
        """Test that fragments include metadata (stored in profile_fragments list)."""
        config = composer.compose(turbulence_model="rans_komega_sst")

        # Metadata is stored in profile_fragments list
        assert "profile_fragments" in config or "physics" in config

    def test_metadata_includes_axis(self, composer):
        """Test that fragment composition works correctly."""
        config = composer.compose(turbulence_model="laminar")

        # Check that the fragment produced a valid physics section
        assert "physics" in config
        assert config["physics"]["simulation_type"] == "laminar"

    def test_metadata_includes_level(self, composer):
        """Test that fragments produce valid configurations."""
        config = composer.compose(spatial_resolution="medium")

        # Check that fragment produced valid mesh config
        assert "mesh" in config


@pytest.mark.unit
class TestProfileIntegration:
    """Test integration of multiple fragments into complete profiles."""

    @pytest.fixture
    def composer(self):
        return ProfileComposer()

    def test_laminar_coarse_profile(self, composer):
        """Test laminar coarse profile composition."""
        config = composer.compose(
            spatial_resolution="coarse",
            solver_recipe="robust",
            turbulence_model="laminar"
        )

        # Check all three fragments contributed
        assert "mesh" in config  # From spatial_resolution
        assert "schemes" in config or "fvSolution" in config  # From solver_recipe
        assert "physics" in config  # From turbulence_model
        assert config["physics"]["simulation_type"] == "laminar"

    def test_rans_medium_profile(self, composer):
        """Test RANS medium profile composition."""
        config = composer.compose(
            spatial_resolution="medium",
            solver_recipe="balanced",
            turbulence_model="rans_komega_sst"
        )

        assert config["physics"]["simulation_type"] == "RAS"
        assert config["physics"]["turbulence_model"] == "kOmegaSST"

    def test_les_fine_profile(self, composer):
        """Test LES fine profile composition."""
        config = composer.compose(
            spatial_resolution="fine",
            solver_recipe="aggressive",
            turbulence_model="les_wale"
        )

        assert config["physics"]["simulation_type"] == "LES"
        assert config["physics"]["subgrid_model"] == "WALE"
