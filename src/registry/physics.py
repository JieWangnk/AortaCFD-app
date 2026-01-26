# src/registry/physics.py
"""
Centralized physical constants and blood properties.

This module is the SINGLE SOURCE OF TRUTH for all physical constants
used in cardiovascular CFD simulations.

Usage:
    from src.registry.physics import BLOOD_PROPERTIES, calculate_reynolds

    nu = BLOOD_PROPERTIES['kinematic_viscosity']
    Re = calculate_reynolds(velocity=0.5, diameter=0.02, nu=nu)
"""

import math
from typing import Dict, Any, Optional


# =============================================================================
# BLOOD PROPERTIES (Standard human blood at 37°C)
# =============================================================================

BLOOD_PROPERTIES = {
    # Density
    'density': 1060.0,              # kg/m³ (rho)
    'density_unit': 'kg/m³',

    # Dynamic viscosity
    'dynamic_viscosity': 0.004,     # Pa·s (mu)
    'dynamic_viscosity_unit': 'Pa·s',

    # Kinematic viscosity (nu = mu/rho)
    'kinematic_viscosity': 3.774e-6,  # m²/s
    'kinematic_viscosity_unit': 'm²/s',

    # Valid ranges for validation
    'density_range': (1000, 1200),           # kg/m³
    'dynamic_viscosity_range': (0.001, 0.01),  # Pa·s

    # Notes
    'notes': 'Standard human blood at 37°C, Newtonian approximation',
}


# =============================================================================
# PHYSICAL CONSTANTS
# =============================================================================

PHYSICAL_CONSTANTS = {
    # Pressure conversions
    'pa_to_mmhg': 0.00750062,       # 1 Pa = 0.00750062 mmHg
    'mmhg_to_pa': 133.322,          # 1 mmHg = 133.322 Pa

    # Flow rate conversions
    'lpm_to_m3s': 1.0 / 60000.0,    # L/min to m³/s
    'm3s_to_lpm': 60000.0,          # m³/s to L/min
    'mlps_to_m3s': 1e-6,            # mL/s to m³/s

    # Length conversions
    'mm_to_m': 0.001,               # mm to m
    'cm_to_m': 0.01,                # cm to m

    # Typical physiological values
    'typical_cardiac_cycle': 0.8,   # seconds (75 bpm)
    'typical_aortic_diameter': 0.025,  # m (25 mm)
    'typical_aortic_velocity': 0.5,    # m/s (mean)
    'typical_peak_velocity': 1.2,      # m/s (systolic peak)

    # Reference pressure (atmospheric)
    'p_ref': 0.0,                   # Pa (gauge pressure reference)
}


# =============================================================================
# NON-NEWTONIAN BLOOD MODELS (for future use)
# =============================================================================

CARREAU_YASUDA_PARAMS = {
    # Carreau-Yasuda model parameters for blood
    # mu(gamma_dot) = mu_inf + (mu_0 - mu_inf) * [1 + (lambda * gamma_dot)^a]^((n-1)/a)
    'mu_0': 0.056,          # Pa·s (zero shear viscosity)
    'mu_inf': 0.00345,      # Pa·s (infinite shear viscosity)
    'lambda': 3.313,        # s (relaxation time)
    'a': 2.0,               # Yasuda exponent
    'n': 0.3568,            # Power law index
}

CROSS_MODEL_PARAMS = {
    # Cross model parameters
    # mu(gamma_dot) = mu_inf + (mu_0 - mu_inf) / (1 + (K * gamma_dot)^n)
    'mu_0': 0.056,          # Pa·s
    'mu_inf': 0.00345,      # Pa·s
    'K': 1.007,             # s
    'n': 1.028,
}


# =============================================================================
# TURBULENCE INLET CONDITIONS
# =============================================================================

TURBULENCE_INLET_DEFAULTS = {
    # Typical inlet turbulence for cardiovascular flows
    'turbulence_intensity': 0.05,   # 5% (fraction, not percent)
    'length_scale_ratio': 0.07,     # As fraction of hydraulic diameter

    # k-omega SST specific
    'k_method': 'intensity',        # Calculate k from intensity
    'omega_method': 'mixing_length',  # Calculate omega from mixing length

    # Alternative: specify directly
    'k_direct': None,               # m²/s² (if specified directly)
    'omega_direct': None,           # 1/s (if specified directly)
}


# =============================================================================
# ACCESS FUNCTIONS
# =============================================================================

def get_blood_properties(
    density: Optional[float] = None,
    dynamic_viscosity: Optional[float] = None,
) -> Dict[str, float]:
    """
    Get blood properties, optionally with overrides.

    Args:
        density: Override density (kg/m³)
        dynamic_viscosity: Override dynamic viscosity (Pa·s)

    Returns:
        Dictionary with rho, mu, nu
    """
    rho = density if density is not None else BLOOD_PROPERTIES['density']
    mu = dynamic_viscosity if dynamic_viscosity is not None else BLOOD_PROPERTIES['dynamic_viscosity']
    nu = mu / rho

    return {
        'rho': rho,
        'mu': mu,
        'nu': nu,
        'density': rho,
        'dynamic_viscosity': mu,
        'kinematic_viscosity': nu,
    }


def calculate_reynolds(
    velocity: float,
    diameter: float,
    nu: Optional[float] = None,
) -> float:
    """
    Calculate Reynolds number.

    Re = U * D / nu

    Args:
        velocity: Characteristic velocity (m/s)
        diameter: Characteristic length/diameter (m)
        nu: Kinematic viscosity (m²/s), default: blood

    Returns:
        Reynolds number (dimensionless)
    """
    if nu is None:
        nu = BLOOD_PROPERTIES['kinematic_viscosity']

    return velocity * diameter / nu


def calculate_womersley(
    diameter: float,
    cardiac_cycle: float,
    nu: Optional[float] = None,
) -> float:
    """
    Calculate Womersley number.

    alpha = (D/2) * sqrt(omega / nu)
    where omega = 2*pi/T (angular frequency)

    Args:
        diameter: Vessel diameter (m)
        cardiac_cycle: Cardiac cycle period (s)
        nu: Kinematic viscosity (m²/s), default: blood

    Returns:
        Womersley number (dimensionless)
    """
    if nu is None:
        nu = BLOOD_PROPERTIES['kinematic_viscosity']

    omega = 2 * math.pi / cardiac_cycle
    radius = diameter / 2
    return radius * math.sqrt(omega / nu)


def calculate_dean_number(
    velocity: float,
    pipe_diameter: float,
    curvature_radius: float,
    nu: Optional[float] = None,
) -> float:
    """
    Calculate Dean number for curved pipe flow.

    De = Re * sqrt(D / (2*R_c))

    Args:
        velocity: Mean velocity (m/s)
        pipe_diameter: Pipe diameter (m)
        curvature_radius: Radius of curvature (m)
        nu: Kinematic viscosity (m²/s), default: blood

    Returns:
        Dean number (dimensionless)
    """
    Re = calculate_reynolds(velocity, pipe_diameter, nu)
    return Re * math.sqrt(pipe_diameter / (2 * curvature_radius))


def pressure_pa_to_mmhg(pressure_pa: float) -> float:
    """Convert pressure from Pa to mmHg."""
    return pressure_pa * PHYSICAL_CONSTANTS['pa_to_mmhg']


def pressure_mmhg_to_pa(pressure_mmhg: float) -> float:
    """Convert pressure from mmHg to Pa."""
    return pressure_mmhg * PHYSICAL_CONSTANTS['mmhg_to_pa']


def flowrate_lpm_to_m3s(flowrate_lpm: float) -> float:
    """Convert flow rate from L/min to m³/s."""
    return flowrate_lpm * PHYSICAL_CONSTANTS['lpm_to_m3s']


def flowrate_m3s_to_lpm(flowrate_m3s: float) -> float:
    """Convert flow rate from m³/s to L/min."""
    return flowrate_m3s * PHYSICAL_CONSTANTS['m3s_to_lpm']


def calculate_inlet_turbulence(
    velocity: float,
    diameter: float,
    intensity: float = 0.05,
    length_scale_ratio: float = 0.07,
) -> Dict[str, float]:
    """
    Calculate inlet turbulence quantities for k-omega SST.

    Args:
        velocity: Inlet velocity (m/s)
        diameter: Inlet diameter (m)
        intensity: Turbulence intensity (fraction, e.g., 0.05 for 5%)
        length_scale_ratio: Mixing length as fraction of diameter

    Returns:
        Dictionary with k, omega, epsilon, nut
    """
    # Turbulent kinetic energy: k = 1.5 * (U * I)^2
    k = 1.5 * (velocity * intensity) ** 2

    # Mixing length
    mixing_length = diameter * length_scale_ratio

    # Turbulent dissipation rate (k-epsilon)
    # epsilon = C_mu^0.75 * k^1.5 / l
    C_mu = 0.09
    epsilon = (C_mu ** 0.75) * (k ** 1.5) / mixing_length

    # Specific dissipation rate (k-omega)
    # omega = epsilon / (C_mu * k)
    omega = epsilon / (C_mu * k) if k > 0 else 1.0

    # Turbulent viscosity
    # nut = k / omega
    nut = k / omega if omega > 0 else 0.0

    return {
        'k': k,
        'omega': omega,
        'epsilon': epsilon,
        'nut': nut,
        'intensity': intensity,
        'mixing_length': mixing_length,
    }
