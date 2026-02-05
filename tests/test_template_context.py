"""
Comprehensive test suite for template_context module.

Tests the template context preprocessing functions that extract business logic
from Jinja2 templates into testable Python code.
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aortacfd_lib.template_context import (
    prepare_control_dict_context,
    prepare_fv_schemes_context,
    prepare_fv_solution_context,
    prepare_bc_context,
    prepare_fv_options_context,
    prepare_all_contexts,
)


class TestControlDictContext:
    """Test prepare_control_dict_context function."""

    def test_windkessel_detection_from_outlet_type(self):
        """Test Windkessel detection from outlet type."""
        config = {
            'boundary_conditions': {
                'outlets': {'type': '3EWINDKESSEL'}
            }
        }
        result = prepare_control_dict_context(config)
        assert result['needs_windkessel_lib'] is True

    def test_windkessel_detection_from_flag(self):
        """Test Windkessel detection from explicit flag."""
        config = {
            'windkessel_enabled': True,
            'boundary_conditions': {'outlets': {'type': 'pressure'}}
        }
        result = prepare_control_dict_context(config)
        assert result['needs_windkessel_lib'] is True

    def test_no_windkessel_for_simple_outlets(self):
        """Test no Windkessel for simple outlet types."""
        config = {
            'boundary_conditions': {
                'outlets': {'type': 'pressure'}
            }
        }
        result = prepare_control_dict_context(config)
        assert result['needs_windkessel_lib'] is False

    def test_pulsatile_detection_timevarying(self):
        """Test pulsatile detection for TIMEVARYING inlet."""
        config = {
            'boundary_conditions': {
                'inlet': {'type': 'TIMEVARYING'}
            }
        }
        result = prepare_control_dict_context(config)
        assert result['is_pulsatile'] is True
        assert result['inlet_type'] == 'TIMEVARYING'

    def test_pulsatile_detection_womersley(self):
        """Test pulsatile detection for WOMERSLEY inlet."""
        config = {
            'boundary_conditions': {
                'inlet': {'type': 'womersley'}  # lowercase should work
            }
        }
        result = prepare_control_dict_context(config)
        assert result['is_pulsatile'] is True
        assert result['inlet_type'] == 'WOMERSLEY'

    def test_constant_inlet_not_pulsatile(self):
        """Test CONSTANT inlet is not pulsatile."""
        config = {
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT'}
            }
        }
        result = prepare_control_dict_context(config)
        assert result['is_pulsatile'] is False
        assert result['inlet_type'] == 'CONSTANT'

    def test_default_inlet_type(self):
        """Test default inlet type when not specified."""
        config = {}
        result = prepare_control_dict_context(config)
        assert result['inlet_type'] == 'CONSTANT'
        assert result['is_pulsatile'] is False

    def test_les_max_co(self):
        """Test LES gets lower maxCo."""
        config = {
            'physics': {'simulation_type': 'LES'}
        }
        result = prepare_control_dict_context(config)
        assert result['is_les'] is True
        assert result['max_co'] == 0.5

    def test_laminar_max_co(self):
        """Test laminar gets standard maxCo."""
        config = {
            'physics': {'simulation_type': 'laminar'}
        }
        result = prepare_control_dict_context(config)
        assert result['is_les'] is False
        assert result['max_co'] == 1.0

    def test_purge_write_calculation(self):
        """Test purgeWrite calculation from keep_last_cycles."""
        config = {
            'keep_last_cycles': 2,
            'cardiac_cycle': 1.0,
            'write_interval': 0.1
        }
        result = prepare_control_dict_context(config)
        # 2 cycles * 1.0s / 0.1s = 20 timesteps
        assert result['purge_write'] == 20


class TestFvSchemesContext:
    """Test prepare_fv_schemes_context function."""

    def test_robust_profile_euler(self):
        """Test robust profile uses Euler time scheme."""
        config = {
            'physics': {'simulation_type': 'laminar'},
            'numerics': {'profile': 'robust'}
        }
        result = prepare_fv_schemes_context(config)
        assert result['profile'] == 'robust'
        assert result['ddt_scheme'] == 'Euler'

    def test_standard_profile_backward(self):
        """Test standard profile uses backward time scheme."""
        config = {
            'physics': {'simulation_type': 'laminar'},
            'numerics': {'profile': 'standard'}
        }
        result = prepare_fv_schemes_context(config)
        assert result['profile'] == 'standard'
        assert result['ddt_scheme'] == 'backward'

    def test_steady_state_scheme(self):
        """Test steady state uses steadyState scheme."""
        config = {
            'physics': {'steady_state': True},
            'numerics': {'profile': 'standard'}
        }
        result = prepare_fv_schemes_context(config)
        assert result['is_steady'] is True
        assert result['ddt_scheme'] == 'steadyState'

    def test_robust_profile_upwind(self):
        """Test robust profile uses upwind convection."""
        config = {
            'numerics': {'profile': 'robust'}
        }
        result = prepare_fv_schemes_context(config)
        assert result['div_scheme_U'] == 'Gauss upwind'

    def test_precise_profile_lust(self):
        """Test precise profile uses LUST (minimal diffusion)."""
        config = {
            'numerics': {'profile': 'precise'}
        }
        result = prepare_fv_schemes_context(config)
        assert 'LUST' in result['div_scheme_U']

    def test_les_uses_lust(self):
        """Test LES uses LUST scheme."""
        config = {
            'physics': {'simulation_type': 'les'},
            'numerics': {'profile': 'standard'}
        }
        result = prepare_fv_schemes_context(config)
        assert 'LUST' in result['div_scheme_U']

    def test_robust_grad_limiter(self):
        """Test robust profile has higher gradient limiter."""
        config = {
            'numerics': {'profile': 'robust'}
        }
        result = prepare_fv_schemes_context(config)
        assert result['grad_limiter'] == 1.0

    def test_standard_grad_limiter(self):
        """Test standard profile has moderate gradient limiter."""
        config = {
            'numerics': {'profile': 'standard'}
        }
        result = prepare_fv_schemes_context(config)
        assert result['grad_limiter'] == 0.5


class TestFvSolutionContext:
    """Test prepare_fv_solution_context function."""

    def test_robust_profile_pimple(self):
        """Test robust profile PIMPLE settings."""
        config = {
            'numerics': {'profile': 'robust'}
        }
        result = prepare_fv_solution_context(config)
        assert result['profile'] == 'robust'
        assert result['pimple']['nOuterCorrectors'] == 20
        assert result['pimple']['nNonOrthogonalCorrectors'] == 3

    def test_standard_profile_pimple(self):
        """Test standard profile PIMPLE settings."""
        config = {
            'numerics': {'profile': 'standard'}
        }
        result = prepare_fv_solution_context(config)
        assert result['pimple']['nOuterCorrectors'] == 30
        assert result['pimple']['nNonOrthogonalCorrectors'] == 1

    def test_precise_profile_pimple(self):
        """Test precise profile PIMPLE settings."""
        config = {
            'numerics': {'profile': 'precise'}
        }
        result = prepare_fv_solution_context(config)
        assert result['pimple']['nOuterCorrectors'] == 50
        assert result['pimple']['nNonOrthogonalCorrectors'] == 2

    def test_robust_relaxation_factors(self):
        """Test robust profile relaxation factors."""
        config = {
            'numerics': {'profile': 'robust'}
        }
        result = prepare_fv_solution_context(config)
        assert result['relaxation']['p'] == 0.15
        assert result['relaxation']['pFinal'] == 1.0
        assert result['relaxation']['U'] == 0.4
        assert result['relaxation']['UFinal'] == 1.0

    def test_standard_relaxation_factors(self):
        """Test standard profile relaxation factors."""
        config = {
            'numerics': {'profile': 'standard'}
        }
        result = prepare_fv_solution_context(config)
        assert result['relaxation']['p'] == 0.3
        assert result['relaxation']['pFinal'] == 1.0
        assert result['relaxation']['U'] == 0.7

    def test_robust_tolerances(self):
        """Test robust profile tolerances."""
        config = {
            'numerics': {'profile': 'robust'}
        }
        result = prepare_fv_solution_context(config)
        assert result['tolerances']['p'] == 1e-3
        assert result['tolerances']['U'] == 1e-3

    def test_precise_tolerances(self):
        """Test precise profile tolerances are tighter."""
        config = {
            'numerics': {'profile': 'precise'}
        }
        result = prepare_fv_solution_context(config)
        assert result['tolerances']['p'] == 1e-5
        assert result['tolerances']['U'] == 1e-6

    def test_default_profile(self):
        """Test default profile when not specified."""
        config = {}
        result = prepare_fv_solution_context(config)
        assert result['profile'] == 'standard'


class TestBCContext:
    """Test prepare_bc_context function."""

    def test_turbulent_simulation(self):
        """Test turbulent simulation detection."""
        config = {
            'physics': {'simulation_type': 'RANS'}
        }
        result = prepare_bc_context(config)
        assert result['is_turbulent'] is True
        assert result['simulation_type'] == 'rans'

    def test_laminar_simulation(self):
        """Test laminar simulation detection."""
        config = {
            'physics': {'simulation_type': 'laminar'}
        }
        result = prepare_bc_context(config)
        assert result['is_turbulent'] is False

    def test_les_is_turbulent(self):
        """Test LES is detected as turbulent."""
        config = {
            'physics': {'simulation_type': 'LES'}
        }
        result = prepare_bc_context(config)
        assert result['is_turbulent'] is True

    def test_inlet_settings(self):
        """Test inlet settings extraction."""
        config = {
            'boundary_conditions': {
                'inlet': {
                    'type': 'TIMEVARYING',
                    'velocity': 0.5,
                    'profile_type': 'parabolic'
                }
            }
        }
        result = prepare_bc_context(config)
        assert result['inlet_type'] == 'TIMEVARYING'
        assert result['inlet_velocity'] == 0.5
        assert result['inlet_profile'] == 'parabolic'

    def test_turbulence_inlet_conditions(self):
        """Test turbulence inlet conditions for RANS."""
        config = {
            'physics': {'simulation_type': 'RANS'},
            'boundary_conditions': {
                'inlet': {
                    'turbulence_intensity': 0.1,
                    'mixing_length': 0.05
                }
            }
        }
        result = prepare_bc_context(config)
        assert result['turbulence_intensity'] == 0.1
        assert result['mixing_length'] == 0.05

    def test_windkessel_outlet_detection(self):
        """Test Windkessel outlet detection."""
        config = {
            'boundary_conditions': {
                'outlets': {'type': '3EWINDKESSEL'}
            }
        }
        result = prepare_bc_context(config)
        assert result['is_windkessel'] is True


class TestFvOptionsContext:
    """Test prepare_fv_options_context function."""

    def test_les_enables_nut_bound(self):
        """Test LES enables nut bounding."""
        config = {
            'physics': {'simulation_type': 'LES'}
        }
        result = prepare_fv_options_context(config)
        assert result['is_les'] is True
        assert result['bound_nut'] is True
        assert result['nut_min'] == 1e-15

    def test_rans_no_nut_bound(self):
        """Test RANS doesn't enable nut bounding."""
        config = {
            'physics': {'simulation_type': 'RANS'}
        }
        result = prepare_fv_options_context(config)
        assert result['is_les'] is False
        assert result['bound_nut'] is False

    def test_laminar_no_nut_bound(self):
        """Test laminar doesn't enable nut bounding."""
        config = {
            'physics': {'simulation_type': 'laminar'}
        }
        result = prepare_fv_options_context(config)
        assert result['is_les'] is False
        assert result['bound_nut'] is False


class TestAllContexts:
    """Test prepare_all_contexts consolidated function."""

    def test_returns_all_context_dicts(self):
        """Test all context dictionaries are returned."""
        config = {
            'physics': {'simulation_type': 'laminar'},
            'numerics': {'profile': 'standard'}
        }
        result = prepare_all_contexts(config)

        assert 'controlDict' in result
        assert 'fvSchemes' in result
        assert 'fvSolution' in result
        assert 'bc' in result
        assert 'fvOptions' in result

    def test_contexts_have_required_keys(self):
        """Test each context has required keys."""
        config = {
            'physics': {'simulation_type': 'LES'},
            'numerics': {'profile': 'robust'}
        }
        result = prepare_all_contexts(config)

        # controlDict context
        assert 'needs_windkessel_lib' in result['controlDict']
        assert 'is_pulsatile' in result['controlDict']

        # fvSchemes context
        assert 'ddt_scheme' in result['fvSchemes']
        assert 'div_scheme_U' in result['fvSchemes']

        # fvSolution context
        assert 'pimple' in result['fvSolution']
        assert 'relaxation' in result['fvSolution']

        # fvOptions context
        assert 'is_les' in result['fvOptions']
        assert 'bound_nut' in result['fvOptions']


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_config(self):
        """Test with empty config uses defaults."""
        config = {}

        # Should not raise, should return defaults
        ctrl = prepare_control_dict_context(config)
        assert ctrl['inlet_type'] == 'CONSTANT'

        schemes = prepare_fv_schemes_context(config)
        assert schemes['profile'] == 'standard'

        solution = prepare_fv_solution_context(config)
        assert solution['profile'] == 'standard'

    def test_missing_physics_section(self):
        """Test with missing physics section."""
        config = {
            'numerics': {'profile': 'robust'}
        }
        result = prepare_fv_schemes_context(config)
        assert result['simulation_type'] == 'laminar'  # Default

    def test_case_insensitive_simulation_type(self):
        """Test simulation type is case insensitive."""
        for sim_type in ['LES', 'les', 'Les']:
            config = {'physics': {'simulation_type': sim_type}}
            result = prepare_fv_options_context(config)
            assert result['is_les'] is True

    def test_unknown_profile_uses_standard(self):
        """Test unknown profile falls back to standard."""
        config = {
            'numerics': {'profile': 'unknown_profile'}
        }
        result = prepare_fv_solution_context(config)
        # Should use standard defaults
        assert result['pimple']['nOuterCorrectors'] == 30


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
