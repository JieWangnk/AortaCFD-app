# aortacfd_lib/template_context.py
"""
Template context preprocessing module.

This module extracts business logic from Jinja2 templates into Python functions,
making the logic testable, maintainable, and reusable. Templates should only
contain formatting and presentation logic, not business decisions.

Usage:
    from aortacfd_lib.template_context import prepare_control_dict_context
    context = prepare_control_dict_context(config)
    rendered = template.render(context)
"""

from typing import Any, Dict, List, Optional, Tuple, Union


# =============================================================================
# CONTROL DICT CONTEXT
# =============================================================================

def prepare_control_dict_context(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare template context for controlDict generation.

    Extracts all business logic decisions from the template into
    testable Python code.

    Args:
        config: Full simulation configuration

    Returns:
        Dictionary with pre-computed template variables
    """
    # Extract boundary condition settings
    # Support both nested (boundary_conditions.outlets) and flattened (outlets) config structures
    bc = config.get('boundary_conditions', {})
    outlets = bc.get('outlets') or config.get('outlets', {})
    inlet = bc.get('inlet') or config.get('inlet', {})

    # Determine outlet type
    outlet_type = outlets.get('type', '').upper()

    # Check if Windkessel is enabled
    needs_windkessel = (
        config.get('windkessel_enabled', False) or
        outlet_type in ['2EWINDKESSEL', '3EWINDKESSEL', 'WINDKESSEL']
    )

    # Determine inlet type
    inlet_settings = config.get('inlet_settings', inlet)
    inlet_type = inlet_settings.get('type', 'CONSTANT').upper()
    is_pulsatile = inlet_type in ['TIMEVARYING', 'WOMERSLEY']

    # Get simulation timing
    end_time = config.get('end_time', 5.0)
    cardiac_cycle = config.get('cardiac_cycle', 1.0)
    num_cycles = config.get('num_cycles', 5)

    # Calculate end time from cycles if not specified
    if end_time <= 0 and cardiac_cycle > 0:
        end_time = cardiac_cycle * num_cycles

    # Get write intervals
    write_interval = config.get('write_interval', 0.1)

    # Get physics settings
    physics = config.get('physics', {})
    simulation_type = physics.get('simulation_type', 'laminar').upper()
    is_les = simulation_type == 'LES'

    # Get numerics settings
    numerics = config.get('numerics', {})
    max_co = numerics.get('max_co', 1.0 if not is_les else 0.5)
    max_delta_t = numerics.get('max_delta_t', 0.001)

    # Determine purgeWrite for disk space management
    keep_last_cycles = config.get('keep_last_cycles', 0)
    if keep_last_cycles > 0 and cardiac_cycle > 0:
        purge_write = int(keep_last_cycles * cardiac_cycle / write_interval)
    else:
        purge_write = 0

    return {
        # Windkessel settings
        'needs_windkessel_lib': needs_windkessel,
        'outlet_type': outlet_type,

        # Inlet settings
        'inlet_type': inlet_type,
        'is_pulsatile': is_pulsatile,

        # Timing settings
        'end_time': end_time,
        'cardiac_cycle': cardiac_cycle,
        'num_cycles': num_cycles,
        'write_interval': write_interval,
        'purge_write': purge_write,

        # Physics settings
        'simulation_type': simulation_type,
        'is_les': is_les,

        # Numerics settings
        'max_co': max_co,
        'max_delta_t': max_delta_t,
        'adjust_time_step': True,

        # OpenFOAM settings
        'application': 'foamRun',
        'solver': 'incompressibleFluid',
        'start_from': 'startTime',
        'start_time': 0,
        'stop_at': 'endTime',
    }


# =============================================================================
# FV SCHEMES CONTEXT
# =============================================================================

def prepare_fv_schemes_context(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare template context for fvSchemes generation.

    Args:
        config: Full simulation configuration

    Returns:
        Dictionary with pre-computed scheme selections
    """
    physics = config.get('physics', {})
    schemes = config.get('schemes', {})
    numerics = config.get('numerics', {})

    simulation_type = physics.get('simulation_type', 'laminar').lower()
    is_steady = physics.get('steady_state', False)
    profile = numerics.get('profile', 'standard')

    # Read all schemes from the authoritative profile definitions
    # (single source of truth — no hardcoded duplicates)
    from config.profiles.numerics import NUMERICS_PROFILES
    profile_config = NUMERICS_PROFILES.get(profile, NUMERICS_PROFILES.get('standard', {}))

    # Time discretization
    if is_steady:
        ddt_scheme = 'steadyState'
    else:
        ddt_scheme = profile_config.get('ddtSchemes', {}).get('default', 'Euler')

    # Convection schemes — read from profile
    div_schemes = profile_config.get('divSchemes', {})
    div_scheme = div_schemes.get('div(phi,U)', 'Gauss limitedLinearV 1')
    div_scheme_k = div_schemes.get('div(phi,k)', 'Gauss limitedLinear 1')

    # LES override: always use LUST for resolved turbulence regardless of profile
    if simulation_type == 'les' and 'LUST' not in div_scheme:
        div_scheme = 'Gauss LUST grad(U)'

    # Gradient limiter coefficient — extract from profile's grad scheme string
    grad_default = profile_config.get('gradSchemes', {}).get('default', 'cellLimited Gauss linear 0.5')
    # Parse the trailing number from e.g. "cellLimited Gauss linear 0.5"
    grad_parts = grad_default.split()
    try:
        grad_limiter = float(grad_parts[-1])
    except (ValueError, IndexError):
        grad_limiter = 0.5

    # Laplacian and snGrad schemes — read from profile
    laplacian_scheme = profile_config.get('laplacianSchemes', {}).get('default', 'Gauss linear corrected')
    sngrad_scheme = profile_config.get('snGradSchemes', {}).get('default', 'corrected')

    return {
        'is_steady': is_steady,
        'simulation_type': simulation_type,
        'profile': profile,

        'ddt_scheme': ddt_scheme,
        'div_scheme_U': div_scheme,
        'div_scheme_k': div_scheme_k,
        'grad_limiter': grad_limiter,
        'laplacian_scheme': laplacian_scheme,
        'sngrad_scheme': sngrad_scheme,

        # Allow override from schemes dict
        'schemes': schemes,
    }


# =============================================================================
# FV SOLUTION CONTEXT
# =============================================================================

def prepare_fv_solution_context(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare template context for fvSolution generation.

    Args:
        config: Full simulation configuration

    Returns:
        Dictionary with pre-computed solver settings
    """
    numerics = config.get('numerics', {})
    fv_solution = config.get('fvSolution', {})
    profile = numerics.get('profile', 'standard')

    # PIMPLE settings by profile
    # Updated March 2026 to match proven cardiovascular CFD settings
    pimple_settings = {
        'robust': {
            'nOuterCorrectors': 25,
            'nCorrectors': 3,
            'nNonOrthogonalCorrectors': 2,
        },
        'standard': {
            'nOuterCorrectors': 10,
            'nCorrectors': 2,
            'nNonOrthogonalCorrectors': 0,
        },
        'accurate': {
            'nOuterCorrectors': 10,
            'nCorrectors': 2,
            'nNonOrthogonalCorrectors': 0,
        },
        'precise': {
            'nOuterCorrectors': 10,
            'nCorrectors': 2,
            'nNonOrthogonalCorrectors': 0,
        },
    }

    # Relaxation factors by profile
    relaxation_settings = {
        'robust': {
            'p': 0.3, 'pFinal': 1.0,
            'U': 0.7, 'UFinal': 1.0,
            'k': 0.7, 'kFinal': 1.0,
        },
        'standard': {
            'p': 0.5, 'pFinal': 1.0,
            'U': 0.8, 'UFinal': 1.0,
            'k': 0.7, 'kFinal': 1.0,
        },
        'accurate': {
            'p': 0.5, 'pFinal': 1.0,
            'U': 0.8, 'UFinal': 1.0,
            'k': 0.8, 'kFinal': 1.0,
        },
        'precise': {
            'p': 0.5, 'pFinal': 1.0,
            'U': 0.8, 'UFinal': 1.0,
            'k': 0.8, 'kFinal': 1.0,
        },
    }

    # Convergence tolerances by profile
    tolerance_settings = {
        'robust': {'p': 1e-3, 'U': 1e-3},
        'standard': {'p': 1e-3, 'U': 1e-4},
        'accurate': {'p': 1e-3, 'U': 1e-4},
        'precise': {'p': 1e-3, 'U': 1e-4},
    }

    pimple = pimple_settings.get(profile, pimple_settings['standard'])
    relaxation = relaxation_settings.get(profile, relaxation_settings['standard'])
    tolerances = tolerance_settings.get(profile, tolerance_settings['standard'])

    return {
        'profile': profile,
        'pimple': pimple,
        'relaxation': relaxation,
        'tolerances': tolerances,
        'fvSolution': fv_solution,  # Allow user overrides
    }


# =============================================================================
# BOUNDARY CONDITION CONTEXT
# =============================================================================

def prepare_bc_context(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare template context for boundary condition files.

    Args:
        config: Full simulation configuration

    Returns:
        Dictionary with pre-computed BC settings
    """
    bc = config.get('boundary_conditions', {})
    physics = config.get('physics', {})
    inlet = bc.get('inlet', {})
    outlets = bc.get('outlets', {})

    simulation_type = physics.get('simulation_type', 'laminar').lower()
    is_turbulent = simulation_type in ['rans', 'les']

    # Inlet settings
    inlet_type = inlet.get('type', 'CONSTANT').upper()
    inlet_velocity = inlet.get('velocity', 0.1)
    inlet_profile = inlet.get('profile_type', 'plug')

    # Turbulence inlet conditions
    if is_turbulent:
        turbulence_intensity = inlet.get('turbulence_intensity', 0.05)
        mixing_length = inlet.get('mixing_length', 0.07)  # As fraction of diameter
    else:
        turbulence_intensity = 0
        mixing_length = 0

    # Outlet type
    outlet_type = outlets.get('type', 'zeroGradient')
    is_windkessel = 'WINDKESSEL' in outlet_type.upper()

    return {
        'simulation_type': simulation_type,
        'is_turbulent': is_turbulent,

        'inlet_type': inlet_type,
        'inlet_velocity': inlet_velocity,
        'inlet_profile': inlet_profile,
        'turbulence_intensity': turbulence_intensity,
        'mixing_length': mixing_length,

        'outlet_type': outlet_type,
        'is_windkessel': is_windkessel,
    }


# =============================================================================
# FV OPTIONS CONTEXT (LES Stability)
# =============================================================================

def prepare_fv_options_context(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare template context for fvOptions (LES stability).

    Args:
        config: Full simulation configuration

    Returns:
        Dictionary with pre-computed fvOptions settings
    """
    physics = config.get('physics', {})
    simulation_type = physics.get('simulation_type', 'laminar').upper()

    is_les = simulation_type == 'LES'

    return {
        'is_les': is_les,
        'simulation_type': simulation_type,
        # Nut bounding for WALE stability
        'bound_nut': is_les,
        'nut_min': 1e-15,
    }


# =============================================================================
# CONSOLIDATED CONTEXT
# =============================================================================

def prepare_all_contexts(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Prepare all template contexts at once.

    Args:
        config: Full simulation configuration

    Returns:
        Dictionary mapping template name to context dict
    """
    return {
        'controlDict': prepare_control_dict_context(config),
        'fvSchemes': prepare_fv_schemes_context(config),
        'fvSolution': prepare_fv_solution_context(config),
        'bc': prepare_bc_context(config),
        'fvOptions': prepare_fv_options_context(config),
    }
