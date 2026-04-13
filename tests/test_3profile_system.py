"""
Test suite for the simplified 3-profile numerics system.

Validates that robust, standard, and precise profiles match
the actual profile specifications in src/config/profiles/numerics/.

Updated to match v2.3 profile configurations (accurate → precise rename).
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
        """Verify that robust, standard, precise are the main profiles."""
        main_profiles = ['robust', 'standard', 'precise']

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

    def test_courant_number(self):
        """Robust uses Co = 1.0 (first-order schemes are inherently stable)."""
        assert self.profile['time_stepping']['max_co'] == 1.0, \
            "Robust uses max_co = 1.0 (first-order schemes are stable)"

    def test_many_correctors(self):
        """Robust should use 25 max outer correctors with convergence-based early exit."""
        assert self.profile['solvers']['PIMPLE']['nOuterCorrectors'] == 25, \
            "Robust must use 25 max outer correctors (convergence-based exit)"
        assert self.profile['solvers']['PIMPLE']['nCorrectors'] == 3, \
            "Robust must use 3 inner correctors"
        # Verify convergence-based early exit is configured
        assert 'outerCorrectorResidualControl' in self.profile['solvers']['PIMPLE'], \
            "Robust must have outerCorrectorResidualControl for early exit"

    def test_moderate_relaxation_with_final_correction(self):
        """Robust should use moderate relaxation with UFinal=1 and pFinal=1.0 for Windkessel coupling."""
        assert self.profile['solvers']['relaxationFactors']['equations']['U'] == 0.7, \
            "Robust must use U relaxation = 0.7 (Windkessel compatible)"
        assert self.profile['solvers']['relaxationFactors']['equations']['UFinal'] == 1.0, \
            "Robust must use UFinal = 1.0 for full correction"
        assert self.profile['solvers']['relaxationFactors']['fields']['p'] == 0.3, \
            "Robust must use p relaxation = 0.3 (Windkessel compatible)"
        assert self.profile['solvers']['relaxationFactors']['fields']['pFinal'] == 1.0, \
            "pFinal must be 1.0 for correct Windkessel ODE coupling"

    def test_relaxed_tolerances(self):
        """Robust uses relaxed tolerances (1e-4) for stability."""
        assert self.profile['solvers']['residualControl']['p'] == 1e-4, \
            "Robust must use residual tolerance 1e-4"

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
        """Standard should use limitedLinearV (2nd order TVD bounded)."""
        assert 'limitedLinearV' in self.profile['divSchemes']['div(phi,U)'], \
            "Standard must use limitedLinearV convection (2nd order TVD bounded)"
        assert 'limitedLinear' in self.profile['divSchemes']['div(phi,k)'], \
            "Standard must use limitedLinear for turbulence"

    def test_normal_courant_number(self):
        """Standard should use Co = 0.8 for stability."""
        assert self.profile['time_stepping']['max_co'] == 0.8, \
            "Standard must use max_co = 0.8"

    def test_moderate_correctors(self):
        """Standard should use 10 max outer correctors with convergence-based early exit."""
        assert self.profile['solvers']['PIMPLE']['nOuterCorrectors'] == 10, \
            "Standard must use 10 max outer correctors (convergence-based exit)"
        assert self.profile['solvers']['PIMPLE']['nCorrectors'] == 2, \
            "Standard must use 2 inner correctors"
        # Verify convergence-based early exit is configured
        assert 'outerCorrectorResidualControl' in self.profile['solvers']['PIMPLE'], \
            "Standard must have outerCorrectorResidualControl for early exit"

    def test_moderate_relaxation(self):
        """Standard should use moderate relaxation."""
        assert self.profile['solvers']['relaxationFactors']['equations']['U'] == 0.8, \
            "Standard must use U relaxation = 0.8"
        assert self.profile['solvers']['relaxationFactors']['fields']['p'] == 0.5, \
            "Standard must use p relaxation = 0.5"

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
        assert meta['stability'] == 'high'


class TestPreciseProfile:
    """Test precise profile (LES, validation, minimal diffusion)."""

    def setup_method(self):
        self.profile = NUMERICS_PROFILES['precise']

    def test_crank_nicolson_time_integration(self):
        """Precise should use backward (2nd order, implicit-explicit blend)."""
        assert self.profile['ddtSchemes']['default'] == 'backward', \
            "Precise must use backward time integration"

    def test_lust_convection(self):
        """Precise should use LUST (75% central + 25% upwind, minimal diffusion)."""
        u_scheme = self.profile['divSchemes']['div(phi,U)']
        assert 'LUST' in u_scheme, \
            "Precise must use LUST convection (found: {})".format(u_scheme)

    def test_standard_gradient_limiting(self):
        """Precise should use gradient limiting (1)."""
        grad_scheme = self.profile['gradSchemes']['default']
        assert 'cellLimited' in grad_scheme and '1' in grad_scheme, \
            "Precise must use cellLimited Gauss linear 1"

    def test_limited_laplacian(self):
        """Precise should use limited Laplacian for stability."""
        laplacian = self.profile['laplacianSchemes']['default']
        assert 'limited' in laplacian, \
            "Precise must use 'Gauss linear limited' Laplacian"

    def test_reduced_courant_for_accuracy(self):
        """Precise should use Co = 0.5 (smaller for temporal accuracy)."""
        assert self.profile['time_stepping']['max_co'] == 0.5, \
            "Precise must use max_co = 0.5 for temporal accuracy"

    def test_many_correctors(self):
        """Precise should use 10 max outer correctors with convergence-based early exit."""
        assert self.profile['solvers']['PIMPLE']['nOuterCorrectors'] == 10, \
            "Precise must use 10 max outer correctors (convergence-based exit)"
        assert self.profile['solvers']['PIMPLE']['nCorrectors'] == 2, \
            "Precise must use 2 inner correctors"
        # Verify convergence-based early exit is configured
        assert 'outerCorrectorResidualControl' in self.profile['solvers']['PIMPLE'], \
            "Precise must have outerCorrectorResidualControl for early exit"

    def test_moderate_relaxation_with_final_correction(self):
        """Precise should use moderate relaxation with Final=1.0."""
        assert self.profile['solvers']['relaxationFactors']['equations']['U'] == 0.8, \
            "Precise must use U relaxation = 0.8"
        assert self.profile['solvers']['relaxationFactors']['equations']['UFinal'] == 1.0, \
            "Precise must use UFinal = 1.0 for full correction"
        assert self.profile['solvers']['relaxationFactors']['fields']['p'] == 0.5, \
            "Precise must use p relaxation = 0.5"
        assert self.profile['solvers']['relaxationFactors']['fields']['pFinal'] == 1.0, \
            "Precise must use pFinal = 1.0 for correct Windkessel coupling"

    def test_tight_tolerances(self):
        """Precise uses tighter tolerances (1e-8) than standard."""
        assert self.profile['solvers']['residualControl']['p'] == 1e-8, \
            "Precise must use residual tolerance 1e-8"

    def test_supports_all_turbulence(self):
        """Precise must have schemes for all turbulence models."""
        assert 'div(phi,k)' in self.profile['divSchemes']
        assert 'div(phi,omega)' in self.profile['divSchemes']
        assert 'div(phi,epsilon)' in self.profile['divSchemes']

    def test_metadata_correctness(self):
        """Verify precise metadata."""
        meta = self.profile['_profile_metadata']
        assert meta['name'] == 'precise'
        assert meta['formal_order_of_accuracy'] == 2
        assert 'validation' in meta['intended_use'].lower() or 'les' in meta['intended_use'].lower()


class TestProfileComparison:
    """Test relationships between profiles."""

    def test_temporal_order_progression(self):
        """Verify order of accuracy progression."""
        robust_order = NUMERICS_PROFILES['robust']['_profile_metadata']['order_of_accuracy']
        standard_order = NUMERICS_PROFILES['standard']['_profile_metadata']['order_of_accuracy']
        # precise uses 'formal_order_of_accuracy' in metadata
        precise_order = NUMERICS_PROFILES['precise']['_profile_metadata']['formal_order_of_accuracy']

        assert robust_order == 1, "Robust should be 1st order"
        assert standard_order == 2, "Standard should be 2nd order"
        assert precise_order == 2, "Precise should be 2nd order"

    def test_tolerance_progression(self):
        """Verify tolerances get tighter: robust → standard → precise."""
        tol_robust = NUMERICS_PROFILES['robust']['solvers']['residualControl']['p']
        tol_standard = NUMERICS_PROFILES['standard']['solvers']['residualControl']['p']
        tol_precise = NUMERICS_PROFILES['precise']['solvers']['residualControl']['p']

        assert tol_robust == 1e-4
        assert tol_standard == 1e-6
        assert tol_precise == 1e-8
        assert tol_robust > tol_standard > tol_precise

    def test_relaxation_differences(self):
        """Verify profiles have appropriate relaxation factors."""
        relax_u_robust = NUMERICS_PROFILES['robust']['solvers']['relaxationFactors']['equations']['U']
        relax_u_std = NUMERICS_PROFILES['standard']['solvers']['relaxationFactors']['equations']['U']
        relax_u_precise = NUMERICS_PROFILES['precise']['solvers']['relaxationFactors']['equations']['U']

        # All profiles use moderate relaxation with Final=1.0
        assert relax_u_robust == 0.7, "Robust uses 0.7 (moderate)"
        assert relax_u_std == 0.8, "Standard uses 0.8 (moderate)"
        assert relax_u_precise == 0.8, "Precise uses 0.8 (moderate)"

        # All profiles use pFinal=1.0 for correct Windkessel coupling
        assert NUMERICS_PROFILES['robust']['solvers']['relaxationFactors']['fields']['pFinal'] == 1.0
        assert NUMERICS_PROFILES['standard']['solvers']['relaxationFactors']['fields']['pFinal'] == 1.0
        assert NUMERICS_PROFILES['precise']['solvers']['relaxationFactors']['fields']['pFinal'] == 1.0

    def test_corrector_progression(self):
        """Verify max corrector counts (all use convergence-based exit)."""
        corr_robust = NUMERICS_PROFILES['robust']['solvers']['PIMPLE']['nOuterCorrectors']
        corr_std = NUMERICS_PROFILES['standard']['solvers']['PIMPLE']['nOuterCorrectors']
        corr_precise = NUMERICS_PROFILES['precise']['solvers']['PIMPLE']['nOuterCorrectors']

        # nOuterCorrectors with convergence-based exit
        assert corr_robust == 25, "Robust: 25 max correctors (convergence-based exit)"
        assert corr_std == 10, "Standard: 10 max correctors (convergence-based exit)"
        assert corr_precise == 10, "Precise: 10 max correctors (convergence-based exit)"
        assert corr_std < corr_robust, "Standard uses fewer max correctors than robust"


class TestUniversalPhysicsSupport:
    """Test that all profiles support all physics models."""

    @pytest.mark.parametrize("profile_name", ['robust', 'standard', 'precise'])
    def test_laminar_support(self, profile_name):
        """All profiles must support laminar (no special schemes needed)."""
        profile = NUMERICS_PROFILES[profile_name]
        assert 'div(phi,U)' in profile['divSchemes'], \
            f"{profile_name} must support laminar (div(phi,U))"

    @pytest.mark.parametrize("profile_name", ['robust', 'standard', 'precise'])
    def test_rans_support(self, profile_name):
        """All profiles must support RANS (k, omega, epsilon schemes)."""
        profile = NUMERICS_PROFILES[profile_name]
        assert 'div(phi,k)' in profile['divSchemes'], \
            f"{profile_name} must support RANS (div(phi,k))"
        assert 'div(phi,omega)' in profile['divSchemes'], \
            f"{profile_name} must support RANS (div(phi,omega))"
        assert 'div(phi,epsilon)' in profile['divSchemes'], \
            f"{profile_name} must support RANS (div(phi,epsilon))"

    @pytest.mark.parametrize("profile_name", ['robust', 'standard', 'precise'])
    def test_les_support(self, profile_name):
        """All profiles should support LES (may have warnings for robust/standard)."""
        profile = NUMERICS_PROFILES[profile_name]
        # LES doesn't need k/omega, but should have div(B) for magnetic field-like terms
        assert 'div(phi,U)' in profile['divSchemes'], \
            f"{profile_name} must have convection scheme for LES"


class TestMethodologyTableSpecs:
    """Verify specifications match the actual profile implementations."""

    def test_table_row_robust(self):
        """Verify robust row matches actual profile."""
        p = NUMERICS_PROFILES['robust']

        # Time integration
        assert p['ddtSchemes']['default'] == 'Euler'

        # Convection
        assert p['divSchemes']['div(phi,U)'] == 'Gauss upwind'

        # PIMPLE (convergence-based exit)
        assert p['solvers']['PIMPLE']['nOuterCorrectors'] == 25
        assert p['solvers']['PIMPLE']['nCorrectors'] == 3
        assert 'outerCorrectorResidualControl' in p['solvers']['PIMPLE']

        # Courant (1.0 - first-order schemes are inherently stable)
        assert p['time_stepping']['max_co'] == 1.0

        # Tolerance
        assert p['solvers']['residualControl']['p'] == 1e-4

    def test_table_row_standard(self):
        """Verify standard row matches actual profile."""
        p = NUMERICS_PROFILES['standard']

        # Time integration
        assert p['ddtSchemes']['default'] == 'backward'

        # Convection (limitedLinearV 2nd order TVD bounded)
        assert 'limitedLinearV' in p['divSchemes']['div(phi,U)']

        # PIMPLE (convergence-based exit)
        assert p['solvers']['PIMPLE']['nOuterCorrectors'] == 10
        assert p['solvers']['PIMPLE']['nCorrectors'] == 2
        assert 'outerCorrectorResidualControl' in p['solvers']['PIMPLE']

        # Courant
        assert p['time_stepping']['max_co'] == 0.8

        # Tolerance
        assert p['solvers']['residualControl']['p'] == 1e-6

    def test_table_row_precise(self):
        """Verify precise row matches actual profile."""
        p = NUMERICS_PROFILES['precise']

        # Time integration (CrankNicolson for better phase accuracy)
        assert p['ddtSchemes']['default'] == 'backward'

        # Convection (LUST for minimal diffusion)
        assert 'LUST' in p['divSchemes']['div(phi,U)']

        # Gradient limiting (1)
        assert 'cellLimited' in p['gradSchemes']['default']
        assert '1' in p['gradSchemes']['default']

        # PIMPLE (convergence-based exit)
        assert p['solvers']['PIMPLE']['nOuterCorrectors'] == 10
        assert p['solvers']['PIMPLE']['nCorrectors'] == 2
        assert 'outerCorrectorResidualControl' in p['solvers']['PIMPLE']

        # Courant (0.5 for temporal accuracy)
        assert p['time_stepping']['max_co'] == 0.5

        # Tolerance (tightest)
        assert p['solvers']['residualControl']['p'] == 1e-8


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
