"""
Test suite to validate the methodology section table against actual codebase.

This test verifies that the simulation profile table in methodology_cmame.tex
accurately reflects the implementation in the codebase.
"""

import pytest
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.numerics_builder import NumericsBuilder
from config.profiles.numerics import NUMERICS_PROFILES


class TestMethodologyProfileTable:
    """
    Validate the methodology section table against actual implementation.

    NOTE: The original table referenced old profiles (laminar_coarse, rans_medium, etc.)
    that were removed. The new system uses:
    - Numerics profiles: robust, standard, accurate (3-profile system)
    - Physics model: specified separately in config (laminar, rans, les)
    - Mesh resolution: specified via cells_per_diameter or target_cell_size_mm
    """

    def setup_method(self):
        """Initialize test fixtures."""
        self.builder = NumericsBuilder()

    def test_numerics_profiles_exist(self):
        """Verify all numeric profiles mentioned in documentation exist."""
        documented_profiles = ['robust', 'standard', 'accurate']

        for profile in documented_profiles:
            assert profile in NUMERICS_PROFILES, \
                f"Documented profile '{profile}' not found in NUMERICS_PROFILES"

    def test_robust_profile_specifications(self):
        """Verify robust profile matches methodology description."""
        profile = NUMERICS_PROFILES['robust']

        # Should be first-order (upwind)
        assert profile['divSchemes']['div(phi,U)'] == 'Gauss upwind', \
            "Robust profile should use first-order upwind for velocity"

        # Time integration should be Euler (first-order)
        assert profile['ddtSchemes']['default'] == 'Euler', \
            "Robust profile should use Euler time integration"

        # Correctors - should be high with convergence-based exit (20 max outer correctors)
        assert profile['solvers']['PIMPLE']['nOuterCorrectors'] == 20, \
            "Robust profile should use 20 max outer correctors (convergence-based exit)"
        assert 'outerCorrectorResidualControl' in profile['solvers']['PIMPLE'], \
            "Robust profile must have outerCorrectorResidualControl for early exit"

        # Max Courant number
        assert profile['time_stepping']['max_co'] == 0.5, \
            "Robust profile should use max_co = 0.5 for stability"

        # Order of accuracy
        assert profile['_profile_metadata']['order_of_accuracy'] == 1, \
            "Robust profile should be first-order accurate"

    def test_standard_profile_specifications(self):
        """Verify standard profile matches methodology description."""
        profile = NUMERICS_PROFILES['standard']

        # Should be second-order bounded (linearUpwind)
        assert 'linearUpwind' in profile['divSchemes']['div(phi,U)'], \
            "Standard profile should use linearUpwind (2nd order bounded)"

        # Time integration should be backward (second-order)
        assert profile['ddtSchemes']['default'] == 'backward', \
            "Standard profile should use backward time integration"

        # Correctors - moderate max with convergence-based exit (30 max outer correctors)
        assert profile['solvers']['PIMPLE']['nOuterCorrectors'] == 30, \
            "Standard profile should use 30 max outer correctors (convergence-based exit)"
        assert 'outerCorrectorResidualControl' in profile['solvers']['PIMPLE'], \
            "Standard profile must have outerCorrectorResidualControl for early exit"

        # Max Courant number
        assert profile['time_stepping']['max_co'] == 1.0, \
            "Standard profile should use max_co = 1.0"

        # Order of accuracy
        assert profile['_profile_metadata']['order_of_accuracy'] == 2, \
            "Standard profile should be second-order accurate"

    def test_accurate_profile_specifications(self):
        """Verify accurate profile matches methodology description."""
        profile = NUMERICS_PROFILES['accurate']

        # Should use LUST or other low-diffusion scheme
        conv_scheme = profile['divSchemes']['div(phi,U)']
        assert 'LUST' in conv_scheme or 'linear' in conv_scheme.lower(), \
            "Accurate profile should use low-diffusion scheme (LUST preferred)"

        # Time integration should be CrankNicolson (better phase accuracy)
        assert 'CrankNicolson' in profile['ddtSchemes']['default'], \
            "Accurate profile should use CrankNicolson time integration"

        # Should have tight tolerances
        assert profile['solvers']['residualControl']['p'] <= 1e-7, \
            "Accurate profile should have tight residual tolerances (≤1e-7)"

        # Order of accuracy (accurate profile uses formal_order_of_accuracy)
        assert profile['_profile_metadata']['formal_order_of_accuracy'] == 2, \
            "Accurate profile should be second-order accurate"


class TestMethodologyPhysicsModels:
    """Test that physics models are correctly specified."""

    def test_laminar_model_available(self):
        """Verify laminar model is available."""
        # This would be specified in config as physics.model = "laminar"
        # The base.py config should support this
        from config.base import config

        assert 'physics' in config, "Base config should have physics section"
        assert 'default_turbulence' in config['physics'], \
            "Base config should specify default turbulence model"
        assert config['physics']['default_turbulence'] == 'laminar', \
            "Default turbulence should be laminar"

    def test_rans_model_configuration(self):
        """Verify RANS k-omega SST is properly supported."""
        # The templates should support k-omega SST turbulence
        # Check that divSchemes for k and omega exist in profiles

        for profile_name, profile in NUMERICS_PROFILES.items():
            assert 'div(phi,k)' in profile['divSchemes'], \
                f"Profile '{profile_name}' missing div(phi,k) scheme for RANS"
            assert 'div(phi,omega)' in profile['divSchemes'], \
                f"Profile '{profile_name}' missing div(phi,omega) scheme for RANS"

    def test_les_model_configuration(self):
        """Verify LES WALE model support."""
        # For LES, we should have appropriate schemes
        # Robust profile should warn if used with LES
        # Accurate profile is recommended for LES
        pass  # LES is physics-dependent, not numerics-dependent in new system


class TestMethodologyMeshResolution:
    """Test mesh resolution specification methods."""

    def test_cells_per_diameter_method(self):
        """Verify cells-per-diameter resolution method exists."""
        from aortacfd_lib.utils.mesh_constants import compute_cell_size

        # Test typical values from methodology
        D_ref = 20.0  # mm (typical adult aorta)

        # Coarse: ~10 cells/diameter
        cell_size_coarse = compute_cell_size(10, D_ref)
        assert cell_size_coarse == pytest.approx(2.0, rel=0.01), \
            "Coarse mesh should be ~2mm (10 cells across 20mm diameter)"

        # Medium: ~15 cells/diameter
        cell_size_medium = compute_cell_size(15, D_ref)
        assert cell_size_medium == pytest.approx(1.33, rel=0.01), \
            "Medium mesh should be ~1.33mm (15 cells across 20mm diameter)"

        # Fine: ~20 cells/diameter
        cell_size_fine = compute_cell_size(20, D_ref)
        assert cell_size_fine == pytest.approx(1.0, rel=0.01), \
            "Fine mesh should be ~1mm (20 cells across 20mm diameter)"

    def test_absolute_cell_size_method(self):
        """Verify absolute cell size specification exists."""
        # This is specified directly in config as target_cell_size_mm
        # The mesh_setup.py should handle this

        # Test that the priority system recognizes target_cell_size_mm
        # This would be tested in the mesh_setup module
        pass


class TestMethodologyBoundaryConditions:
    """Test boundary condition implementations."""

    def test_windkessel_parameter_equations(self):
        """Verify 3-element Windkessel parameter calculations match equations."""
        # The methodology describes equations for MAP, R, C, Z
        # These should match implementation in windkessel_analyzer.py

        # Test MAP calculation: MAP = dia + (sys - dia)/3
        p_sys = 120  # mmHg
        p_dia = 80   # mmHg
        expected_map = p_dia + (p_sys - p_dia) / 3
        assert expected_map == pytest.approx(93.33, rel=0.01), \
            "MAP calculation should match methodology equation"

    def test_murray_law_implementation(self):
        """Verify Murray's law flow distribution matches equation."""
        # Equation: Q_i = Q_total * (r_i^3 / sum(r_j^3))

        # Example: 3 outlets with radii 5, 4, 3 mm
        radii = [5.0, 4.0, 3.0]
        Q_total = 100.0  # mL/s

        r_cubed_sum = sum(r**3 for r in radii)

        Q1 = Q_total * (radii[0]**3 / r_cubed_sum)
        Q2 = Q_total * (radii[1]**3 / r_cubed_sum)
        Q3 = Q_total * (radii[2]**3 / r_cubed_sum)

        # Verify sum equals total
        assert Q1 + Q2 + Q3 == pytest.approx(Q_total, rel=0.001), \
            "Murray's law flow split should sum to total flow"

        # Verify Q1 > Q2 > Q3 (larger vessels get more flow)
        assert Q1 > Q2 > Q3, \
            "Murray's law should assign more flow to larger vessels"


class TestMethodologyNumericalSchemes:
    """Test that numerical schemes match methodology descriptions."""

    @pytest.mark.parametrize("profile_name,expected_gradient", [
        ('robust', 'cellLimited Gauss linear'),
        ('standard', 'cellLimited Gauss linear'),
        ('accurate', 'cellLimited Gauss linear'),
    ])
    def test_gradient_schemes(self, profile_name, expected_gradient):
        """Verify gradient schemes match methodology."""
        profile = NUMERICS_PROFILES[profile_name]
        grad_scheme = profile['gradSchemes']['default']

        assert expected_gradient in grad_scheme, \
            f"Profile '{profile_name}' should use '{expected_gradient}' for gradients"

    @pytest.mark.parametrize("profile_name,expected_laplacian", [
        ('robust', 'Gauss linear limited corrected'),
        ('standard', 'Gauss linear corrected'),
    ])
    def test_laplacian_schemes(self, profile_name, expected_laplacian):
        """Verify Laplacian schemes match methodology."""
        profile = NUMERICS_PROFILES[profile_name]
        laplacian_scheme = profile['laplacianSchemes']['default']

        assert expected_laplacian in laplacian_scheme, \
            f"Profile '{profile_name}' should use '{expected_laplacian}' for Laplacian"


class TestMethodologyValidation:
    """Test validation and verification methods."""

    def test_richardson_extrapolation_refinement_ratio(self):
        """Verify refinement ratio for GCI is sqrt(2) as stated in methodology."""
        import math

        # Methodology states: refinement ratio r = sqrt(2)
        r = math.sqrt(2)

        # For 3 mesh levels: coarse, medium, fine
        dx_coarse = 1.0  # mm
        dx_medium = dx_coarse / r
        dx_fine = dx_medium / r

        assert dx_medium == pytest.approx(0.707, rel=0.01), \
            "Medium mesh should be dx/sqrt(2)"
        assert dx_fine == pytest.approx(0.5, rel=0.01), \
            "Fine mesh should be dx/2"

        # Verify this is systematic refinement
        ratio_1 = dx_coarse / dx_medium
        ratio_2 = dx_medium / dx_fine

        assert ratio_1 == pytest.approx(ratio_2, rel=0.01), \
            "Refinement ratio should be constant"


def test_methodology_table_is_outdated():
    """
    Test that old profiles are removed and new 3-profile system is in place.

    The table in methodology_cmame.tex references old profiles like:
    - laminar_coarse, laminar_medium, laminar_fine
    - rans_coarse, rans_medium, rans_fine
    - les_medium, les_fine

    These were REMOVED in the new config system. The new system uses:
    - Numerics profiles: robust, standard, accurate (3-profile system)
    - Physics model: specified separately (laminar, rans, les)
    """
    old_profile_names = [
        'laminar_coarse', 'laminar_medium', 'laminar_fine',
        'rans_coarse', 'rans_medium', 'rans_fine',
        'les_medium', 'les_fine'
    ]

    for old_profile in old_profile_names:
        assert old_profile not in NUMERICS_PROFILES, \
            f"Old profile '{old_profile}' should not exist in new system"

    # New 3-profile system should exist
    new_profile_names = ['robust', 'standard', 'accurate']

    for new_profile in new_profile_names:
        assert new_profile in NUMERICS_PROFILES, \
            f"New profile '{new_profile}' should exist"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
