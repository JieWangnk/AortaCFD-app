# src/registry/numerics.py
"""
Centralized numerical settings registry.

This module is the SINGLE SOURCE OF TRUTH for all numerical schemes,
solver settings, relaxation factors, and PIMPLE parameters.

Profile Philosophy:
- robust:   1st order schemes, maximum stability, for problematic meshes
- standard: 2nd order TVD-bounded, production runs, Windkessel-stable
- precise:  2nd order minimal diffusion, validation, excellent mesh required

Usage:
    from src.registry.numerics import get_numerics, get_schemes

    # Get all settings for a profile
    settings = get_numerics('standard')

    # Get just schemes
    schemes = get_schemes('standard')
"""

from typing import Any, Dict, List, Optional
from copy import deepcopy


# =============================================================================
# NUMERICAL SCHEMES BY PROFILE
# =============================================================================

SCHEMES = {
    'robust': {
        # Time discretization
        'ddt': 'Euler',

        # Gradient schemes
        'grad_default': 'Gauss linear',
        'grad_U': 'cellLimited Gauss linear 1.0',
        'grad_p': 'Gauss linear',

        # Divergence schemes (convection)
        'div_phi_U': 'Gauss upwind',
        'div_phi_k': 'Gauss upwind',
        'div_phi_omega': 'Gauss upwind',
        'div_phi_epsilon': 'Gauss upwind',
        'div_phi_nuTilda': 'Gauss upwind',
        'div_nuEff_dev_T_grad_U': 'Gauss linear',

        # Laplacian schemes
        'laplacian_default': 'Gauss linear corrected',

        # Interpolation
        'interpolation_default': 'linear',

        # Surface normal gradient
        'snGrad_default': 'corrected',
    },

    'standard': {
        # Time discretization
        'ddt': 'backward',

        # Gradient schemes
        'grad_default': 'Gauss linear',
        'grad_U': 'cellLimited Gauss linear 0.5',
        'grad_p': 'Gauss linear',

        # Divergence schemes (convection) - TVD bounded
        'div_phi_U': 'Gauss limitedLinearV 1',
        'div_phi_k': 'Gauss limitedLinear 1',
        'div_phi_omega': 'Gauss limitedLinear 1',
        'div_phi_epsilon': 'Gauss limitedLinear 1',
        'div_phi_nuTilda': 'Gauss limitedLinear 1',
        'div_nuEff_dev_T_grad_U': 'Gauss linear',

        # Laplacian schemes
        'laplacian_default': 'Gauss linear corrected',

        # Interpolation
        'interpolation_default': 'linear',

        # Surface normal gradient
        'snGrad_default': 'corrected',
    },

    'precise': {
        # Time discretization
        'ddt': 'CrankNicolson 0.9',

        # Gradient schemes
        'grad_default': 'Gauss linear',
        'grad_U': 'cellLimited Gauss linear 0.333',
        'grad_p': 'Gauss linear',

        # Divergence schemes (convection) - minimal diffusion
        'div_phi_U': 'Gauss LUST grad(U)',
        'div_phi_k': 'Gauss limitedLinear 1',
        'div_phi_omega': 'Gauss limitedLinear 1',
        'div_phi_epsilon': 'Gauss limitedLinear 1',
        'div_phi_nuTilda': 'Gauss limitedLinear 1',
        'div_nuEff_dev_T_grad_U': 'Gauss linear',

        # Laplacian schemes
        'laplacian_default': 'Gauss linear corrected',

        # Interpolation
        'interpolation_default': 'linear',

        # Surface normal gradient
        'snGrad_default': 'corrected',
    },
}


# =============================================================================
# SOLVER SETTINGS BY PROFILE
# =============================================================================

SOLVER_SETTINGS = {
    'robust': {
        'p': {
            'solver': 'GAMG',
            'smoother': 'GaussSeidel',
            'tolerance': 1e-4,
            'relTol': 0.01,
            'nPreSweeps': 0,
            'nPostSweeps': 2,
            'cacheAgglomeration': True,
            'agglomerator': 'faceAreaPair',
            'nCellsInCoarsestLevel': 100,
            'mergeLevels': 1,
        },
        'pFinal': {
            'solver': 'GAMG',
            'smoother': 'GaussSeidel',
            'tolerance': 1e-5,
            'relTol': 0,
        },
        'U': {
            'solver': 'smoothSolver',
            'smoother': 'GaussSeidel',
            'tolerance': 1e-5,
            'relTol': 0.01,
            'nSweeps': 1,
        },
        'UFinal': {
            'solver': 'smoothSolver',
            'smoother': 'GaussSeidel',
            'tolerance': 1e-6,
            'relTol': 0,
        },
        'k': {
            'solver': 'smoothSolver',
            'smoother': 'GaussSeidel',
            'tolerance': 1e-6,
            'relTol': 0.01,
        },
        'omega': {
            'solver': 'smoothSolver',
            'smoother': 'GaussSeidel',
            'tolerance': 1e-6,
            'relTol': 0.01,
        },
    },

    'standard': {
        'p': {
            'solver': 'GAMG',
            'smoother': 'DICGaussSeidel',
            'tolerance': 1e-5,
            'relTol': 0.01,
            'nPreSweeps': 0,
            'nPostSweeps': 2,
            'cacheAgglomeration': True,
            'agglomerator': 'faceAreaPair',
            'nCellsInCoarsestLevel': 100,
            'mergeLevels': 1,
        },
        'pFinal': {
            'solver': 'GAMG',
            'smoother': 'DICGaussSeidel',
            'tolerance': 1e-6,
            'relTol': 0,
        },
        'U': {
            'solver': 'PBiCGStab',
            'preconditioner': 'DILU',
            'tolerance': 1e-6,
            'relTol': 0.01,
        },
        'UFinal': {
            'solver': 'PBiCGStab',
            'preconditioner': 'DILU',
            'tolerance': 1e-7,
            'relTol': 0,
        },
        'k': {
            'solver': 'PBiCGStab',
            'preconditioner': 'DILU',
            'tolerance': 1e-7,
            'relTol': 0.01,
        },
        'omega': {
            'solver': 'PBiCGStab',
            'preconditioner': 'DILU',
            'tolerance': 1e-7,
            'relTol': 0.01,
        },
    },

    'precise': {
        'p': {
            'solver': 'GAMG',
            'smoother': 'DICGaussSeidel',
            'tolerance': 1e-6,
            'relTol': 0.005,
            'nPreSweeps': 0,
            'nPostSweeps': 2,
            'cacheAgglomeration': True,
            'agglomerator': 'faceAreaPair',
            'nCellsInCoarsestLevel': 100,
            'mergeLevels': 1,
        },
        'pFinal': {
            'solver': 'GAMG',
            'smoother': 'DICGaussSeidel',
            'tolerance': 1e-7,
            'relTol': 0,
        },
        'U': {
            'solver': 'PBiCGStab',
            'preconditioner': 'DILU',
            'tolerance': 1e-7,
            'relTol': 0.005,
        },
        'UFinal': {
            'solver': 'PBiCGStab',
            'preconditioner': 'DILU',
            'tolerance': 1e-8,
            'relTol': 0,
        },
        'k': {
            'solver': 'PBiCGStab',
            'preconditioner': 'DILU',
            'tolerance': 1e-8,
            'relTol': 0.005,
        },
        'omega': {
            'solver': 'PBiCGStab',
            'preconditioner': 'DILU',
            'tolerance': 1e-8,
            'relTol': 0.005,
        },
    },
}


# =============================================================================
# RELAXATION FACTORS BY PROFILE
# =============================================================================

RELAXATION_FACTORS = {
    'robust': {
        'fields': {
            'p': 0.2,
            'pFinal': 1.0,
        },
        'equations': {
            'U': 0.5,
            'UFinal': 1.0,
            'k': 0.5,
            'kFinal': 1.0,
            'omega': 0.5,
            'omegaFinal': 1.0,
            'epsilon': 0.5,
            'epsilonFinal': 1.0,
        },
    },

    'standard': {
        'fields': {
            'p': 0.3,
            'pFinal': 0.9,  # Windkessel stability tuning
        },
        'equations': {
            'U': 0.7,
            'UFinal': 1.0,
            'k': 0.7,
            'kFinal': 1.0,
            'omega': 0.7,
            'omegaFinal': 1.0,
            'epsilon': 0.7,
            'epsilonFinal': 1.0,
        },
    },

    'precise': {
        'fields': {
            'p': 0.5,
            'pFinal': 1.0,
        },
        'equations': {
            'U': 0.9,
            'UFinal': 1.0,
            'k': 0.8,
            'kFinal': 1.0,
            'omega': 0.8,
            'omegaFinal': 1.0,
            'epsilon': 0.8,
            'epsilonFinal': 1.0,
        },
    },
}


# =============================================================================
# PIMPLE SETTINGS BY PROFILE
# =============================================================================

PIMPLE_SETTINGS = {
    'robust': {
        'nOuterCorrectors': 20,
        'nCorrectors': 3,
        'nNonOrthogonalCorrectors': 3,
        'momentumPredictor': True,
        'consistent': True,
    },

    'standard': {
        'nOuterCorrectors': 30,
        'nCorrectors': 2,
        'nNonOrthogonalCorrectors': 1,
        'momentumPredictor': True,
        'consistent': True,
    },

    'precise': {
        'nOuterCorrectors': 50,
        'nCorrectors': 3,
        'nNonOrthogonalCorrectors': 2,
        'momentumPredictor': True,
        'consistent': True,
    },
}


# =============================================================================
# TIME STEPPING BY PROFILE
# =============================================================================

TIME_STEPPING = {
    'robust': {
        'maxCo': 2.0,
        'maxDeltaT': 0.005,
        'adjustTimeStep': True,
    },

    'standard': {
        'maxCo': 1.0,
        'maxDeltaT': 0.001,
        'adjustTimeStep': True,
    },

    'precise': {
        'maxCo': 0.5,
        'maxDeltaT': 0.0005,
        'adjustTimeStep': True,
    },
}


# =============================================================================
# CONVERGENCE CRITERIA BY PROFILE
# =============================================================================

CONVERGENCE_CRITERIA = {
    'robust': {
        'outerLoop': {
            'p': 1e-3,
            'U': 1e-3,
        },
    },

    'standard': {
        'outerLoop': {
            'p': 1e-4,
            'U': 1e-5,
        },
    },

    'precise': {
        'outerLoop': {
            'p': 1e-5,
            'U': 1e-6,
        },
    },
}


# =============================================================================
# COMBINED PRESET (for backward compatibility)
# =============================================================================

NUMERICS_PRESETS = {
    profile: {
        'schemes': SCHEMES[profile],
        'solvers': SOLVER_SETTINGS[profile],
        'relaxation': RELAXATION_FACTORS[profile],
        'pimple': PIMPLE_SETTINGS[profile],
        'time_stepping': TIME_STEPPING[profile],
        'convergence': CONVERGENCE_CRITERIA[profile],
    }
    for profile in ['robust', 'standard', 'precise']
}


# =============================================================================
# ACCESS FUNCTIONS
# =============================================================================

def list_profiles() -> List[str]:
    """Return list of available profile names."""
    return list(NUMERICS_PRESETS.keys())


def get_numerics(profile: str = 'standard') -> Dict[str, Any]:
    """
    Get complete numerical settings for a profile.

    Args:
        profile: Profile name (robust, standard, precise)

    Returns:
        Dictionary with schemes, solvers, relaxation, pimple, time_stepping

    Raises:
        ValueError: If profile is not recognized
    """
    if profile not in NUMERICS_PRESETS:
        raise ValueError(
            f"Unknown profile '{profile}'. "
            f"Available profiles: {list_profiles()}"
        )
    return deepcopy(NUMERICS_PRESETS[profile])


def get_schemes(profile: str = 'standard') -> Dict[str, str]:
    """
    Get numerical schemes for a profile.

    Args:
        profile: Profile name

    Returns:
        Dictionary of scheme settings
    """
    if profile not in SCHEMES:
        raise ValueError(f"Unknown profile '{profile}'")
    return deepcopy(SCHEMES[profile])


def get_solver_settings(profile: str = 'standard') -> Dict[str, Dict[str, Any]]:
    """
    Get solver settings for a profile.

    Args:
        profile: Profile name

    Returns:
        Dictionary of solver settings per field
    """
    if profile not in SOLVER_SETTINGS:
        raise ValueError(f"Unknown profile '{profile}'")
    return deepcopy(SOLVER_SETTINGS[profile])


def get_relaxation_factors(profile: str = 'standard') -> Dict[str, Dict[str, float]]:
    """
    Get relaxation factors for a profile.

    Args:
        profile: Profile name

    Returns:
        Dictionary with 'fields' and 'equations' relaxation factors
    """
    if profile not in RELAXATION_FACTORS:
        raise ValueError(f"Unknown profile '{profile}'")
    return deepcopy(RELAXATION_FACTORS[profile])


def get_pimple_settings(profile: str = 'standard') -> Dict[str, Any]:
    """
    Get PIMPLE algorithm settings for a profile.

    Args:
        profile: Profile name

    Returns:
        Dictionary of PIMPLE settings
    """
    if profile not in PIMPLE_SETTINGS:
        raise ValueError(f"Unknown profile '{profile}'")
    return deepcopy(PIMPLE_SETTINGS[profile])


def get_time_stepping(profile: str = 'standard') -> Dict[str, Any]:
    """
    Get time stepping settings for a profile.

    Args:
        profile: Profile name

    Returns:
        Dictionary of time stepping settings
    """
    if profile not in TIME_STEPPING:
        raise ValueError(f"Unknown profile '{profile}'")
    return deepcopy(TIME_STEPPING[profile])


def get_convergence_criteria(profile: str = 'standard') -> Dict[str, Any]:
    """
    Get convergence criteria for a profile.

    Args:
        profile: Profile name

    Returns:
        Dictionary of convergence tolerances
    """
    if profile not in CONVERGENCE_CRITERIA:
        raise ValueError(f"Unknown profile '{profile}'")
    return deepcopy(CONVERGENCE_CRITERIA[profile])
