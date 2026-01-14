"""
Test suite for the simplified 3-profile numerics system.

Validates that robust, standard, and accurate profiles match
the actual profile specifications in src/config/profiles/numerics/.

Updated to match v2.1 profile configurations.
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
        """Robust should use 25 max outer correctors with convergence-based early exit."""
        assert self.profile['solvers']['PIMPLE']['nOuterCorrectors'] == 25, \
            "Robust must use 25 max outer correctors (convergence-based exit)"
        assert self.profile['solvers']['PIMPLE']['nCorrectors'] == 3, \
            "Robust must use 3 inner correctors"
        # Verify convergence-based early exit is configured
        assert 'outerCorrectorResidualControl' in self.profile['solvers']['PIMPLE'], \
            "Robust must have outerCorrectorResidualControl for early exit"

    def test_heavy_relaxation(self):
        """Robust should use conservative under-relaxation (Windkessel compatible)."""
        assert self.profile['solvers']['relaxationFactors']['equations']['U'] == 0.55, \
            "Robust must use U relaxation = 0.55 (Windkessel compatible)"
        assert self.profile['solvers']['relaxationFactors']['fields']['p'] == 0.25, \
            "Robust must use p relaxation = 0.25 (Windkessel compatible)"

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
        assert 'limitedLinear' in self.profile['divSchemes']['div(phi,U)'], \
            "Standard must use limitedLinearV convection (TVD bounded)"
        assert 'limitedLinear' in self.profile['divSchemes']['div(phi,k)'], \
            "Standard must use limitedLinear for turbulence"

    def test_normal_courant_number(self):
        """Standard should use Co = 1.0 for efficiency."""
        assert self.profile['time_stepping']['max_co'] == 1.0, \
            "Standard must use max_co = 1.0"

    def test_moderate_correctors(self):
        """Standard should use 50 max outer correctors with convergence-based early exit."""
        assert self.profile['solvers']['PIMPLE']['nOuterCorrectors'] == 50, \
            "Standard must use 50 max outer correctors (convergence-based exit)"
        assert self.profile['solvers']['PIMPLE']['nCorrectors'] == 2, \
            "Standard must use 2 inner correctors"
        # Verify convergence-based early exit is configured
        assert 'outerCorrectorResidualControl' in self.profile['solvers']['PIMPLE'], \
            "Standard must have outerCorrectorResidualControl for early exit"

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
        assert meta['stability'] == 'high'


class TestAccurateProfile:
    """Test accurate profile (publications, validation)."""

    def setup_method(self):
        self.profile = NUMERICS_PROFILES['accurate']

    def test_backward_time_integration(self):
        """Accurate should use backward (2nd order implicit, stable)."""
        assert self.profile['ddtSchemes']['default'] == 'backward', \
            "Accurate must use backward time integration"

    def test_linearupwind_convection(self):
        """Accurate should use linearUpwind (low diffusion, 2nd order)."""
        u_scheme = self.profile['divSchemes']['div(phi,U)']
        assert 'linearUpwind' in u_scheme, \
            "Accurate must use linearUpwind convection (found: {})".format(u_scheme)

    def test_standard_gradient_limiting(self):
        """Accurate should use standard gradient limiting (1.0)."""
        grad_scheme = self.profile['gradSchemes']['default']
        assert 'cellLimited' in grad_scheme and '1' in grad_scheme, \
            "Accurate must use cellLimited Gauss linear 1"

    def test_full_corrected_laplacian(self):
        """Accurate should use full corrected Laplacian (requires good mesh)."""
        laplacian = self.profile['laplacianSchemes']['default']
        assert 'corrected' in laplacian, \
            "Accurate must use 'Gauss linear corrected' Laplacian"

    def test_standard_courant_for_efficiency(self):
        """Accurate should use Co = 1.0 (same as standard for efficiency)."""
        assert self.profile['time_stepping']['max_co'] == 1.0, \
            "Accurate must use max_co = 1.0"

    def test_many_correctors(self):
        """Accurate should use 50 max outer correctors with convergence-based early exit."""
        assert self.profile['solvers']['PIMPLE']['nOuterCorrectors'] == 50, \
            "Accurate must use 50 max outer correctors (convergence-based exit)"
        assert self.profile['solvers']['PIMPLE']['nCorrectors'] == 2, \
            "Accurate must use 2 inner correctors"
        # Verify convergence-based early exit is configured
        assert 'outerCorrectorResidualControl' in self.profile['solvers']['PIMPLE'], \
            "Accurate must have outerCorrectorResidualControl for early exit"

    def test_moderate_relaxation(self):
        """Accurate should use moderate relaxation (same as standard)."""
        assert self.profile['solvers']['relaxationFactors']['equations']['U'] == 0.7, \
            "Accurate must use U relaxation = 0.7"
        assert self.profile['solvers']['relaxationFactors']['fields']['p'] == 0.3, \
            "Accurate must use p relaxation = 0.3"

    def test_tight_tolerances(self):
        """Accurate uses tighter tolerances (1e-7) than standard."""
        assert self.profile['solvers']['residualControl']['p'] == 1e-7, \
            "Accurate must use residual tolerance 1e-7"

    def test_supports_all_turbulence(self):
        """Accurate must have schemes for all turbulence models."""
        assert 'div(phi,k)' in self.profile['divSchemes']
        assert 'div(phi,omega)' in self.profile['divSchemes']
        assert 'div(phi,epsilon)' in self.profile['divSchemes']

    def test_metadata_correctness(self):
        """Verify accurate metadata."""
        meta = self.profile['_profile_metadata']
        assert meta['name'] == 'accurate'
        assert meta['order_of_accuracy'] == 2
        assert 'convergence' in meta['intended_use'].lower() or 'validation' in meta['intended_use'].lower()


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

        assert tol_robust == 1e-4
        assert tol_standard == 1e-6
        assert tol_accurate == 1e-7
        assert tol_robust > tol_standard > tol_accurate

    def test_relaxation_progression(self):
        """Verify relaxation: robust is conservative, standard/accurate are moderate."""
        relax_u_robust = NUMERICS_PROFILES['robust']['solvers']['relaxationFactors']['equations']['U']
        relax_u_std = NUMERICS_PROFILES['standard']['solvers']['relaxationFactors']['equations']['U']
        relax_u_acc = NUMERICS_PROFILES['accurate']['solvers']['relaxationFactors']['equations']['U']

        assert relax_u_robust == 0.55, "Robust uses 0.55 (Windkessel compatible)"
        assert relax_u_std == 0.7, "Standard uses 0.7"
        assert relax_u_acc == 0.7, "Accurate uses 0.7 (same as standard)"
        assert relax_u_robust < relax_u_std, \
            "Robust relaxation should be more conservative than standard"

    def test_corrector_progression(self):
        """Verify max corrector counts (all use convergence-based exit)."""
        corr_robust = NUMERICS_PROFILES['robust']['solvers']['PIMPLE']['nOuterCorrectors']
        corr_std = NUMERICS_PROFILES['standard']['solvers']['PIMPLE']['nOuterCorrectors']
        corr_acc = NUMERICS_PROFILES['accurate']['solvers']['PIMPLE']['nOuterCorrectors']

        # Higher nOuterCorrectors with convergence-based exit per OpenFOAM Wiki best practice
        assert corr_robust == 25, "Robust: 25 max correctors (convergence-based exit)"
        assert corr_std == 50, "Standard: 50 max correctors (convergence-based exit)"
        assert corr_acc == 50, "Accurate: 50 max correctors (convergence-based exit)"
        assert corr_robust < corr_std, "Max correctors should be lower for robust"


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

        # Courant
        assert p['time_stepping']['max_co'] == 0.5

        # Tolerance
        assert p['solvers']['residualControl']['p'] == 1e-4

    def test_table_row_standard(self):
        """Verify standard row matches actual profile."""
        p = NUMERICS_PROFILES['standard']

        # Time integration
        assert p['ddtSchemes']['default'] == 'backward'

        # Convection (TVD bounded limitedLinearV)
        assert 'limitedLinear' in p['divSchemes']['div(phi,U)']

        # PIMPLE (convergence-based exit)
        assert p['solvers']['PIMPLE']['nOuterCorrectors'] == 50
        assert p['solvers']['PIMPLE']['nCorrectors'] == 2
        assert 'outerCorrectorResidualControl' in p['solvers']['PIMPLE']

        # Courant
        assert p['time_stepping']['max_co'] == 1.0

        # Tolerance
        assert p['solvers']['residualControl']['p'] == 1e-6

    def test_table_row_accurate(self):
        """Verify accurate row matches actual profile."""
        p = NUMERICS_PROFILES['accurate']

        # Time integration
        assert p['ddtSchemes']['default'] == 'backward'

        # Convection (linearUpwind for low diffusion)
        assert 'linearUpwind' in p['divSchemes']['div(phi,U)']

        # Gradient limiting (standard 1.0)
        assert 'cellLimited' in p['gradSchemes']['default']

        # PIMPLE (convergence-based exit)
        assert p['solvers']['PIMPLE']['nOuterCorrectors'] == 50
        assert p['solvers']['PIMPLE']['nCorrectors'] == 2
        assert 'outerCorrectorResidualControl' in p['solvers']['PIMPLE']

        # Courant
        assert p['time_stepping']['max_co'] == 1.0

        # Tolerance
        assert p['solvers']['residualControl']['p'] == 1e-7


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
