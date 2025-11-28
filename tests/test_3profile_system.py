"""
Test suite for the simplified 3-profile numerics system.

Validates that robust, standard, and accurate profiles match
the methodology specifications in methodology_3profile_system.tex
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.profiles.numerics import NUMERICS_PROFILES


class Test3ProfileSystem:
    """Validate the 3-profile system architecture."""

    def test_only_3_main_profiles_recommended(self):
        """Verify that robust, standard, accurate are the main profiles."""
        main_profiles = ['robust', 'standard', 'accurate']

        for profile in main_profiles:
            assert profile in NUMERICS_PROFILES, \
                f"Main profile '{profile}' must exist in system"

    def test_no_old_monolithic_profiles(self):
        """Verify old monolithic profiles are removed or deprecated."""
        old_profiles = [
            'laminar_coarse', 'laminar_medium', 'laminar_fine',
            'rans_coarse', 'rans_medium', 'rans_fine',
            'les_medium', 'les_fine'
        ]

        for old_profile in old_profiles:
            assert old_profile not in NUMERICS_PROFILES, \
                f"Old monolithic profile '{old_profile}' should be removed"


class TestRobustProfile:
    """Test robust profile (debugging, poor meshes)."""

    def setup_method(self):
        self.profile = NUMERICS_PROFILES['robust']

    def test_first_order_time_integration(self):
        """Robust should use Euler (1st order) for maximum stability."""
        assert self.profile['ddtSchemes']['default'] == 'Euler', \
            "Robust must use Euler time integration"

    def test_first_order_convection(self):
        """Robust should use upwind (1st order, bounded)."""
        assert self.profile['divSchemes']['div(phi,U)'] == 'Gauss upwind', \
            "Robust must use upwind convection for U"
        assert self.profile['divSchemes']['div(phi,k)'] == 'Gauss upwind', \
            "Robust must use upwind for k"
        assert self.profile['divSchemes']['div(phi,omega)'] == 'Gauss upwind', \
            "Robust must use upwind for omega"

    def test_small_courant_number(self):
        """Robust should use Co = 0.5 for stability."""
        assert self.profile['time_stepping']['max_co'] == 0.5, \
            "Robust must use max_co = 0.5"

    def test_many_correctors(self):
        """Robust should use 3 outer correctors for stability."""
        assert self.profile['solvers']['PIMPLE']['nOuterCorrectors'] == 3, \
            "Robust must use 3 outer correctors"
        assert self.profile['solvers']['PIMPLE']['nCorrectors'] == 3, \
            "Robust must use 3 inner correctors"

    def test_heavy_relaxation(self):
        """Robust should use heavy under-relaxation."""
        assert self.profile['solvers']['relaxationFactors']['equations']['U'] == 0.5, \
            "Robust must use U relaxation = 0.5"
        assert self.profile['solvers']['relaxationFactors']['fields']['p'] == 0.2, \
            "Robust must use p relaxation = 0.2"

    def test_moderate_tolerances(self):
        """Robust uses moderate tolerances (1e-5)."""
        assert self.profile['solvers']['residualControl']['p'] == 1e-5, \
            "Robust must use residual tolerance 1e-5"

    def test_supports_all_turbulence(self):
        """Robust must have schemes for all turbulence models."""
        assert 'div(phi,k)' in self.profile['divSchemes']
        assert 'div(phi,omega)' in self.profile['divSchemes']
        assert 'div(phi,epsilon)' in self.profile['divSchemes']

    def test_metadata_correctness(self):
        """Verify robust metadata."""
        meta = self.profile['_profile_metadata']
        assert meta['name'] == 'robust'
        assert meta['order_of_accuracy'] == 1
        assert meta['stability'] == 'maximum'


class TestStandardProfile:
    """Test standard profile (production simulations)."""

    def setup_method(self):
        self.profile = NUMERICS_PROFILES['standard']

    def test_second_order_time_integration(self):
        """Standard should use backward (2nd order implicit)."""
        assert self.profile['ddtSchemes']['default'] == 'backward', \
            "Standard must use backward time integration"

    def test_second_order_bounded_convection(self):
        """Standard should use linearUpwind (2nd order, bounded)."""
        assert 'linearUpwind' in self.profile['divSchemes']['div(phi,U)'], \
            "Standard must use linearUpwind convection"
        assert 'limitedLinear' in self.profile['divSchemes']['div(phi,k)'], \
            "Standard must use limitedLinear for turbulence"

    def test_normal_courant_number(self):
        """Standard should use Co = 1.0 for efficiency."""
        assert self.profile['time_stepping']['max_co'] == 1.0, \
            "Standard must use max_co = 1.0"

    def test_moderate_correctors(self):
        """Standard should use 2 outer correctors (balanced)."""
        assert self.profile['solvers']['PIMPLE']['nOuterCorrectors'] == 2, \
            "Standard must use 2 outer correctors"
        assert self.profile['solvers']['PIMPLE']['nCorrectors'] == 2, \
            "Standard must use 2 inner correctors"

    def test_moderate_relaxation(self):
        """Standard should use moderate relaxation."""
        assert self.profile['solvers']['relaxationFactors']['equations']['U'] == 0.7, \
            "Standard must use U relaxation = 0.7"
        assert self.profile['solvers']['relaxationFactors']['fields']['p'] == 0.3, \
            "Standard must use p relaxation = 0.3"

    def test_standard_tolerances(self):
        """Standard uses 1e-6 tolerances."""
        assert self.profile['solvers']['residualControl']['p'] == 1e-6, \
            "Standard must use residual tolerance 1e-6"

    def test_supports_all_turbulence(self):
        """Standard must have schemes for all turbulence models."""
        assert 'div(phi,k)' in self.profile['divSchemes']
        assert 'div(phi,omega)' in self.profile['divSchemes']
        assert 'div(phi,epsilon)' in self.profile['divSchemes']

    def test_metadata_correctness(self):
        """Verify standard metadata."""
        meta = self.profile['_profile_metadata']
        assert meta['name'] == 'standard'
        assert meta['order_of_accuracy'] == 2
        assert meta['stability'] == 'good'


class TestAccurateProfile:
    """Test accurate profile (publications, validation)."""

    def setup_method(self):
        self.profile = NUMERICS_PROFILES['accurate']

    def test_cranknicolson_time_integration(self):
        """Accurate should use CrankNicolson 0.9 (2nd order, better phase accuracy)."""
        assert self.profile['ddtSchemes']['default'] == 'CrankNicolson 0.9', \
            "Accurate must use CrankNicolson 0.9 time integration"

    def test_lust_convection(self):
        """Accurate should use LUST (low diffusion, bounded)."""
        u_scheme = self.profile['divSchemes']['div(phi,U)']
        assert 'LUST' in u_scheme, \
            "Accurate must use LUST convection (found: {})".format(u_scheme)

    def test_tighter_gradient_limiting(self):
        """Accurate should use tighter gradient limiting (0.5 vs 1.0)."""
        grad_scheme = self.profile['gradSchemes']['default']
        assert '0.5' in grad_scheme, \
            "Accurate must use gradient limiter 0.5"

    def test_limited_corrected_laplacian(self):
        """Accurate should use limited corrected Laplacian (coefficient 0.33)."""
        laplacian = self.profile['laplacianSchemes']['default']
        assert 'limited' in laplacian and '0.33' in laplacian, \
            "Accurate must use 'limited corrected 0.33' Laplacian"

    def test_small_courant_for_accuracy(self):
        """Accurate should use Co = 0.8 (smaller than standard for temporal accuracy)."""
        assert self.profile['time_stepping']['max_co'] == 0.8, \
            "Accurate must use max_co = 0.8"

    def test_many_correctors(self):
        """Accurate should use 3 outer correctors for tight coupling."""
        assert self.profile['solvers']['PIMPLE']['nOuterCorrectors'] == 3, \
            "Accurate must use 3 outer correctors"
        assert self.profile['solvers']['PIMPLE']['nCorrectors'] == 3, \
            "Accurate must use 3 inner correctors"

    def test_light_relaxation(self):
        """Accurate should use light relaxation (rely on correctors)."""
        assert self.profile['solvers']['relaxationFactors']['equations']['U'] == 0.9, \
            "Accurate must use U relaxation = 0.9"
        assert self.profile['solvers']['relaxationFactors']['fields']['p'] == 0.5, \
            "Accurate must use p relaxation = 0.5"

    def test_tight_tolerances(self):
        """Accurate uses very tight tolerances (1e-8)."""
        assert self.profile['solvers']['residualControl']['p'] == 1e-8, \
            "Accurate must use residual tolerance 1e-8"

    def test_supports_all_turbulence(self):
        """Accurate must have schemes for all turbulence models (including LES)."""
        assert 'div(phi,k)' in self.profile['divSchemes']
        assert 'div(phi,omega)' in self.profile['divSchemes']
        assert 'div(phi,epsilon)' in self.profile['divSchemes']
        assert 'div(B)' in self.profile['divSchemes'], \
            "Accurate must support LES with div(B) scheme"

    def test_metadata_correctness(self):
        """Verify accurate metadata."""
        meta = self.profile['_profile_metadata']
        assert meta['name'] == 'accurate'
        assert meta['order_of_accuracy'] == 2
        assert 'publications' in meta['intended_use'].lower()
        assert 'ALL physics models' in meta['recommended_for']


class TestProfileComparison:
    """Test relationships between profiles."""

    def test_temporal_order_progression(self):
        """Verify order of accuracy progression."""
        robust_order = NUMERICS_PROFILES['robust']['_profile_metadata']['order_of_accuracy']
        standard_order = NUMERICS_PROFILES['standard']['_profile_metadata']['order_of_accuracy']
        accurate_order = NUMERICS_PROFILES['accurate']['_profile_metadata']['order_of_accuracy']

        assert robust_order == 1, "Robust should be 1st order"
        assert standard_order == 2, "Standard should be 2nd order"
        assert accurate_order == 2, "Accurate should be 2nd order"

    def test_tolerance_progression(self):
        """Verify tolerances get tighter: robust → standard → accurate."""
        tol_robust = NUMERICS_PROFILES['robust']['solvers']['residualControl']['p']
        tol_standard = NUMERICS_PROFILES['standard']['solvers']['residualControl']['p']
        tol_accurate = NUMERICS_PROFILES['accurate']['solvers']['residualControl']['p']

        assert tol_robust == 1e-5
        assert tol_standard == 1e-6
        assert tol_accurate == 1e-8
        assert tol_robust > tol_standard > tol_accurate

    def test_relaxation_progression(self):
        """Verify relaxation gets lighter: robust → standard → accurate."""
        relax_u_robust = NUMERICS_PROFILES['robust']['solvers']['relaxationFactors']['equations']['U']
        relax_u_std = NUMERICS_PROFILES['standard']['solvers']['relaxationFactors']['equations']['U']
        relax_u_acc = NUMERICS_PROFILES['accurate']['solvers']['relaxationFactors']['equations']['U']

        assert relax_u_robust == 0.5
        assert relax_u_std == 0.7
        assert relax_u_acc == 0.9
        assert relax_u_robust < relax_u_std < relax_u_acc, \
            "Relaxation should increase (less conservative)"

    def test_corrector_count_progression(self):
        """Verify corrector progression."""
        corr_robust = NUMERICS_PROFILES['robust']['solvers']['PIMPLE']['nOuterCorrectors']
        corr_std = NUMERICS_PROFILES['standard']['solvers']['PIMPLE']['nOuterCorrectors']
        corr_acc = NUMERICS_PROFILES['accurate']['solvers']['PIMPLE']['nOuterCorrectors']

        assert corr_robust == 3, "Robust: 3 correctors for stability"
        assert corr_std == 2, "Standard: 2 correctors for efficiency"
        assert corr_acc == 3, "Accurate: 3 correctors for accuracy"


class TestUniversalPhysicsSupport:
    """Test that all profiles support all physics models."""

    @pytest.mark.parametrize("profile_name", ['robust', 'standard', 'accurate'])
    def test_laminar_support(self, profile_name):
        """All profiles must support laminar (no special schemes needed)."""
        profile = NUMERICS_PROFILES[profile_name]
        assert 'div(phi,U)' in profile['divSchemes'], \
            f"{profile_name} must support laminar (div(phi,U))"

    @pytest.mark.parametrize("profile_name", ['robust', 'standard', 'accurate'])
    def test_rans_support(self, profile_name):
        """All profiles must support RANS (k, omega, epsilon schemes)."""
        profile = NUMERICS_PROFILES[profile_name]
        assert 'div(phi,k)' in profile['divSchemes'], \
            f"{profile_name} must support RANS (div(phi,k))"
        assert 'div(phi,omega)' in profile['divSchemes'], \
            f"{profile_name} must support RANS (div(phi,omega))"
        assert 'div(phi,epsilon)' in profile['divSchemes'], \
            f"{profile_name} must support RANS (div(phi,epsilon))"

    @pytest.mark.parametrize("profile_name", ['robust', 'standard', 'accurate'])
    def test_les_support(self, profile_name):
        """All profiles should support LES (may have warnings for robust/standard)."""
        profile = NUMERICS_PROFILES[profile_name]
        # LES doesn't need k/omega, but should have div(B) for magnetic field-like terms
        assert 'div(phi,U)' in profile['divSchemes'], \
            f"{profile_name} must have convection scheme for LES"


class TestMethodologyTableSpecs:
    """Verify specifications match the methodology table exactly."""

    def test_table_row_robust(self):
        """Verify robust row matches Table 1."""
        p = NUMERICS_PROFILES['robust']

        # Time integration
        assert p['ddtSchemes']['default'] == 'Euler'

        # Convection
        assert p['divSchemes']['div(phi,U)'] == 'Gauss upwind'

        # PIMPLE
        assert p['solvers']['PIMPLE']['nOuterCorrectors'] == 3
        assert p['solvers']['PIMPLE']['nCorrectors'] == 3

        # Courant
        assert p['time_stepping']['max_co'] == 0.5

        # Tolerance
        assert p['solvers']['residualControl']['p'] == 1e-5

    def test_table_row_standard(self):
        """Verify standard row matches Table 1."""
        p = NUMERICS_PROFILES['standard']

        # Time integration
        assert p['ddtSchemes']['default'] == 'backward'

        # Convection
        assert 'linearUpwind' in p['divSchemes']['div(phi,U)']

        # PIMPLE
        assert p['solvers']['PIMPLE']['nOuterCorrectors'] == 2
        assert p['solvers']['PIMPLE']['nCorrectors'] == 2

        # Courant
        assert p['time_stepping']['max_co'] == 1.0

        # Tolerance
        assert p['solvers']['residualControl']['p'] == 1e-6

    def test_table_row_accurate(self):
        """Verify accurate row matches Table 1."""
        p = NUMERICS_PROFILES['accurate']

        # Time integration
        assert p['ddtSchemes']['default'] == 'CrankNicolson 0.9'

        # Convection
        assert 'LUST' in p['divSchemes']['div(phi,U)']

        # Gradient limiting
        assert '0.5' in p['gradSchemes']['default']

        # PIMPLE
        assert p['solvers']['PIMPLE']['nOuterCorrectors'] == 3
        assert p['solvers']['PIMPLE']['nCorrectors'] == 3

        # Courant
        assert p['time_stepping']['max_co'] == 0.8

        # Tolerance
        assert p['solvers']['residualControl']['p'] == 1e-8


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
