# src/config/generator.py
"""
Configuration template generator.

Generates complete configuration files from profiles, eliminating the need
for complex config merging at runtime.

Usage:
    from src.config.generator import generate_config, save_config_template

    # Generate a complete config for standard profile
    config = generate_config('standard')

    # Save as template for a case
    save_config_template('standard', 'cases_input/PAT001/config.json')

Design Philosophy:
- Generate COMPLETE configs upfront (no runtime merging)
- User edits ONE file with ALL settings visible
- Clear documentation of what each setting does
"""

import json
import os
from typing import Any, Dict, List, Optional
from copy import deepcopy

from ..registry.numerics import (
    get_numerics,
    get_schemes,
    get_solver_settings,
    get_relaxation_factors,
    get_pimple_settings,
    get_time_stepping,
    list_profiles,
)
from ..registry.physics import BLOOD_PROPERTIES, PHYSICAL_CONSTANTS
from ..registry.mesh import BOUNDARY_LAYER_DEFAULTS, SNAPPY_QUALITY_DEFAULTS


def generate_config(
    profile: str = 'standard',
    case_name: str = 'MY_CASE',
    include_comments: bool = True,
) -> Dict[str, Any]:
    """
    Generate a complete configuration dictionary for a profile.

    Args:
        profile: Numerical profile (robust, standard, precise)
        case_name: Case name for geometry section
        include_comments: Include _comment fields for documentation

    Returns:
        Complete configuration dictionary
    """
    if profile not in list_profiles():
        raise ValueError(f"Unknown profile '{profile}'. Available: {list_profiles()}")

    # Get numerical settings from registry
    numerics = get_numerics(profile)
    time_stepping = get_time_stepping(profile)

    config = {}

    # Geometry section
    config['geometry'] = _generate_geometry_section(case_name, include_comments)

    # Physics section
    config['physics'] = _generate_physics_section(include_comments)

    # Numerics section
    config['numerics'] = _generate_numerics_section(profile, include_comments)

    # Mesh section
    config['mesh'] = _generate_mesh_section(include_comments)

    # Boundary conditions section
    config['boundary_conditions'] = _generate_bc_section(include_comments)

    # Simulation control section
    config['simulation_control'] = _generate_simulation_control_section(
        time_stepping, include_comments
    )

    # Run settings section
    config['run_settings'] = _generate_run_settings_section(include_comments)

    # Hemodynamics section
    config['hemodynamics'] = _generate_hemodynamics_section(include_comments)

    return config


def _generate_geometry_section(case_name: str, include_comments: bool) -> Dict[str, Any]:
    """Generate geometry configuration section."""
    section = {
        'case_name': case_name,
        'scale_factor': 0.001,
        'inlet_keywords_ordered': 'inlet',
        'outlet_keywords_ordered': ['outlet1', 'outlet2'],
        'wall_keywords_ordered': 'wall',
    }

    if include_comments:
        section['_comment'] = (
            "Geometry settings. scale_factor converts input units to meters "
            "(0.001 = mm to m). Patch names must match STL file names without extension."
        )

    return section


def _generate_physics_section(include_comments: bool) -> Dict[str, Any]:
    """Generate physics configuration section."""
    section = {
        'simulation_type': 'laminar',
        'transport_properties': {
            'nu': BLOOD_PROPERTIES['kinematic_viscosity'],
            'rho': BLOOD_PROPERTIES['density'],
        },
    }

    if include_comments:
        section['_comment'] = (
            "Physics settings. simulation_type: laminar, rans, or les. "
            f"Default blood properties: nu={BLOOD_PROPERTIES['kinematic_viscosity']:.3e} m²/s, "
            f"rho={BLOOD_PROPERTIES['density']} kg/m³"
        )
        section['_turbulence_models'] = "For RANS: kOmegaSST (default), kEpsilon. For LES: WALE, Smagorinsky"

    return section


def _generate_numerics_section(profile: str, include_comments: bool) -> Dict[str, Any]:
    """Generate numerics configuration section."""
    schemes = get_schemes(profile)

    section = {
        'profile': profile,
        'mesh_adaptive': False,
    }

    if include_comments:
        profile_desc = {
            'robust': "1st order upwind, maximum stability, for problematic meshes",
            'standard': "2nd order TVD-bounded, production runs (RECOMMENDED)",
            'precise': "2nd order minimal diffusion, validation, excellent mesh required",
        }
        section['_comment'] = f"Profile '{profile}': {profile_desc.get(profile, '')}"
        section['_schemes_preview'] = {
            'ddt': schemes['ddt'],
            'div_phi_U': schemes['div_phi_U'],
        }

    return section


def _generate_mesh_section(include_comments: bool) -> Dict[str, Any]:
    """Generate mesh configuration section."""
    section = {
        'mesh_resolution': {
            'cells_per_diameter': 15,
        },
        'boundary_layers': {
            'enabled': True,
            'nLayers': 10,
            'expansionRatio': 1.15,
            'finalLayerThickness': 0.2,
        },
    }

    if include_comments:
        section['_comment'] = (
            "Mesh settings. cells_per_diameter: automatic sizing based on geometry. "
            "Alternatively use target_cell_size_mm for manual sizing."
        )
        section['_boundary_layers_comment'] = (
            "Boundary layers important for wall shear stress accuracy. "
            "nLayers=10, expansionRatio=1.15 recommended for hemodynamics."
        )

    return section


def _generate_bc_section(include_comments: bool) -> Dict[str, Any]:
    """Generate boundary conditions configuration section."""
    section = {
        'inlet': {
            'type': 'TIMEVARYING',
            'csv_file': 'flow_waveform.csv',
            'data_type': 'flow_rate',
            'profile': 'plug',
        },
        'outlets': {
            'type': 'zeroGradient',
        },
    }

    if include_comments:
        section['_comment'] = (
            "Boundary conditions. inlet.type: CONSTANT, TIMEVARYING, WOMERSLEY, MRI. "
            "outlets.type: zeroGradient, fixedValue, 2EWINDKESSEL, 3EWINDKESSEL"
        )
        section['_inlet_types'] = {
            'CONSTANT': "Steady inlet, specify 'velocity' (m/s) or 'flowrate' (L/min)",
            'TIMEVARYING': "Pulsatile from CSV, specify 'csv_file' and 'data_type'",
            'WOMERSLEY': "Analytical Womersley profile, requires cardiac cycle",
            'MRI': "Pre-processed 4D flow MRI data",
        }
        section['_outlet_types'] = {
            'zeroGradient': "Simple outflow (development flows)",
            'fixedValue': "Fixed pressure outlet",
            '3EWINDKESSEL': "3-element Windkessel (recommended for aorta)",
            '2EWINDKESSEL': "2-element Windkessel (simpler)",
        }

    return section


def _generate_simulation_control_section(
    time_stepping: Dict[str, Any],
    include_comments: bool,
) -> Dict[str, Any]:
    """Generate simulation control configuration section."""
    section = {
        'number_of_cycles': 3,
        'end_time': 'auto',
        'controlDict': {
            'writeInterval': 0.01,
            'purgeWrite': 0,
        },
    }

    if include_comments:
        section['_comment'] = (
            "Simulation timing. end_time='auto' calculates from cardiac_cycle × number_of_cycles. "
            "purgeWrite=0 keeps all timesteps, or set to N to keep only last N."
        )
        section['_keep_last_cycles'] = (
            "Alternative to purgeWrite: set 'keep_last_cycles: 2' to automatically "
            "calculate purgeWrite to keep last 2 cardiac cycles."
        )

    return section


def _generate_run_settings_section(include_comments: bool) -> Dict[str, Any]:
    """Generate run settings configuration section."""
    section = {
        'subdomains': 4,
        'decomposition_method': 'scotch',
    }

    if include_comments:
        section['_comment'] = (
            "Parallel execution settings. subdomains = number of CPU cores to use. "
            "decomposition_method: scotch (auto-balanced, recommended), hierarchical, simple"
        )

    return section


def _generate_hemodynamics_section(include_comments: bool) -> Dict[str, Any]:
    """Generate hemodynamics configuration section."""
    section = {
        'compute_wss': True,
        'compute_tawss': True,
        'compute_osi': True,
        'compute_rrt': False,
    }

    if include_comments:
        section['_comment'] = (
            "Hemodynamic metrics to compute. WSS=Wall Shear Stress, "
            "TAWSS=Time-Averaged WSS, OSI=Oscillatory Shear Index, "
            "RRT=Relative Residence Time"
        )

    return section


def save_config_template(
    profile: str,
    output_path: str,
    case_name: Optional[str] = None,
    include_comments: bool = True,
) -> str:
    """
    Generate and save a config template file.

    Args:
        profile: Numerical profile
        output_path: Output file path
        case_name: Case name (default: derived from output path)
        include_comments: Include documentation comments

    Returns:
        Path to saved file
    """
    # Derive case name from path if not provided
    if case_name is None:
        case_name = os.path.basename(os.path.dirname(output_path))
        if not case_name or case_name == '.':
            case_name = 'MY_CASE'

    # Generate config
    config = generate_config(profile, case_name, include_comments)

    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    # Save with nice formatting
    with open(output_path, 'w') as f:
        json.dump(config, f, indent=2)

    return output_path


def generate_minimal_config(
    profile: str = 'standard',
    case_name: str = 'MY_CASE',
) -> Dict[str, Any]:
    """
    Generate a minimal configuration with only essential settings.

    This is useful for users who want to see just the required settings
    without all the optional ones.

    Args:
        profile: Numerical profile
        case_name: Case name

    Returns:
        Minimal configuration dictionary
    """
    return {
        'geometry': {
            'case_name': case_name,
            'scale_factor': 0.001,
            'inlet_keywords_ordered': 'inlet',
            'outlet_keywords_ordered': ['outlet1'],
            'wall_keywords_ordered': 'wall',
        },
        'numerics': {
            'profile': profile,
        },
        'boundary_conditions': {
            'inlet': {
                'type': 'TIMEVARYING',
                'csv_file': 'flow.csv',
            },
            'outlets': {
                'type': 'zeroGradient',
            },
        },
        'simulation_control': {
            'number_of_cycles': 3,
        },
    }


def list_available_profiles() -> List[str]:
    """Return list of available numerical profiles."""
    return list_profiles()


def describe_profile(profile: str) -> str:
    """
    Get a description of a numerical profile.

    Args:
        profile: Profile name

    Returns:
        Description string
    """
    descriptions = {
        'robust': (
            "ROBUST PROFILE\n"
            "- 1st order upwind convection schemes\n"
            "- Maximum numerical stability\n"
            "- Use for: problematic meshes, debugging, initial runs\n"
            "- Accuracy: Lower (more numerical diffusion)\n"
            "- Stability: Highest"
        ),
        'standard': (
            "STANDARD PROFILE (RECOMMENDED)\n"
            "- 2nd order TVD-bounded schemes\n"
            "- Good balance of accuracy and stability\n"
            "- Use for: production runs, clinical studies, Windkessel\n"
            "- Accuracy: Good\n"
            "- Stability: High"
        ),
        'precise': (
            "PRECISE PROFILE\n"
            "- 2nd order minimal diffusion schemes (LUST)\n"
            "- Highest accuracy, requires excellent mesh\n"
            "- Use for: validation, LES, research\n"
            "- Accuracy: Highest\n"
            "- Stability: Moderate (needs good mesh)"
        ),
    }
    return descriptions.get(profile, f"Unknown profile: {profile}")
