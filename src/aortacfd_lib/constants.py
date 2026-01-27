"""Physical and numerical constants for cardiovascular CFD simulations.

This module centralizes all magic numbers and physical constants used throughout
the AortaCFD application. Constants are organized by category:
- Unit conversions
- Blood properties
- Turbulence model constants
- Cardiovascular physiology defaults
- Mesh quality thresholds

References:
    - Klabunde RE. Cardiovascular Physiology Concepts. 2nd ed. 2011.
    - Westerhof N, et al. Med Biol Eng Comput. 2009;47:131-141.
    - Nichols WW, O'Rourke MF. McDonald's Blood Flow in Arteries. 6th ed. 2011.
    - Fung YC. Biomechanics: Circulation. 2nd ed. 1997.
"""

from typing import Final

# =============================================================================
# UNIT CONVERSION FACTORS
# =============================================================================

# Pressure conversions
MMHG_TO_PA: Final[float] = 133.322
"""Convert mmHg to Pascal. 1 mmHg = 133.322 Pa exactly (by definition)."""

PA_TO_MMHG: Final[float] = 1.0 / MMHG_TO_PA
"""Convert Pascal to mmHg."""

# Volume conversions
ML_TO_M3: Final[float] = 1e-6
"""Convert milliliters to cubic meters. 1 mL = 1e-6 m³."""

M3_TO_ML: Final[float] = 1e6
"""Convert cubic meters to milliliters."""

L_TO_M3: Final[float] = 1e-3
"""Convert liters to cubic meters. 1 L = 1e-3 m³."""

# Length conversions
MM_TO_M: Final[float] = 1e-3
"""Convert millimeters to meters."""

M_TO_MM: Final[float] = 1e3
"""Convert meters to millimeters."""

# Time conversions
MIN_TO_S: Final[float] = 60.0
"""Convert minutes to seconds."""

# =============================================================================
# BLOOD PROPERTIES (Adult Human Normal Values)
# =============================================================================

# Density
BLOOD_DENSITY_DEFAULT: Final[float] = 1060.0
"""Default blood density in kg/m³. Typical adult range: 1050-1060 kg/m³."""

BLOOD_DENSITY_MIN: Final[float] = 1000.0
"""Minimum physiological blood density in kg/m³."""

BLOOD_DENSITY_MAX: Final[float] = 1100.0
"""Maximum physiological blood density in kg/m³."""

# Viscosity (dynamic)
BLOOD_VISCOSITY_DEFAULT: Final[float] = 0.004
"""Default blood dynamic viscosity in Pa·s (4 mPa·s). Newtonian approximation."""

BLOOD_VISCOSITY_MIN: Final[float] = 0.003
"""Minimum physiological blood viscosity in Pa·s (at high shear rates)."""

BLOOD_VISCOSITY_MAX: Final[float] = 0.006
"""Maximum physiological blood viscosity in Pa·s."""

# Kinematic viscosity (computed from dynamic viscosity / density)
BLOOD_KINEMATIC_VISCOSITY_DEFAULT: Final[float] = 3.7736e-6
"""Default blood kinematic viscosity in m²/s (ν = μ/ρ = 0.004/1060)."""

# =============================================================================
# CARDIOVASCULAR PHYSIOLOGY DEFAULTS
# =============================================================================

# Blood pressure (adult normal values)
SYSTOLIC_PRESSURE_DEFAULT: Final[float] = 120.0
"""Default systolic blood pressure in mmHg (adult normal)."""

DIASTOLIC_PRESSURE_DEFAULT: Final[float] = 80.0
"""Default diastolic blood pressure in mmHg (adult normal)."""

VENOUS_PRESSURE_DEFAULT: Final[float] = 5.0
"""Default central venous pressure in mmHg."""

# Cardiac output
CARDIAC_OUTPUT_DEFAULT: Final[float] = 5.0
"""Default cardiac output in L/min (adult at rest)."""

# Heart rate
HEART_RATE_DEFAULT: Final[float] = 72.0
"""Default heart rate in beats per minute (adult at rest)."""

# Cardiac cycle period
CARDIAC_CYCLE_DEFAULT: Final[float] = 0.8
"""Default cardiac cycle period in seconds (60/72 ≈ 0.833s)."""

# Pulse wave velocity
PWV_DEFAULT: Final[float] = 6.0
"""Default aortic pulse wave velocity in m/s (young healthy adult)."""

PWV_ELDERLY: Final[float] = 10.0
"""Typical aortic PWV in elderly subjects in m/s."""

# Characteristic dimensions
AORTIC_DIAMETER_DEFAULT: Final[float] = 0.025
"""Default ascending aortic diameter in meters (25mm)."""

# Reference velocities
AORTIC_VELOCITY_REFERENCE: Final[float] = 0.5
"""Reference aortic velocity for turbulence estimation in m/s."""

# =============================================================================
# TURBULENCE MODEL CONSTANTS
# =============================================================================

# k-omega SST model constants
C_MU: Final[float] = 0.09
"""Turbulent viscosity coefficient for k-omega SST model."""

TURBULENCE_INTENSITY_DEFAULT: Final[float] = 0.05
"""Default turbulence intensity (5%) for cardiovascular flows."""

TURBULENCE_VISCOSITY_RATIO_DEFAULT: Final[float] = 10.0
"""Default turbulent-to-laminar viscosity ratio (νt/ν)."""

MIXING_LENGTH_FACTOR: Final[float] = 0.07
"""Mixing length as fraction of characteristic length (7%)."""

# =============================================================================
# MESH QUALITY THRESHOLDS
# =============================================================================

# Cell count guidelines
MIN_CELLS_PER_DIAMETER: Final[int] = 6
"""Minimum cells across vessel diameter for reliable results."""

DEFAULT_CELLS_PER_DIAMETER: Final[int] = 10
"""Default cells per diameter (conservative fallback)."""

RECOMMENDED_CELLS_PER_DIAMETER: Final[int] = 20
"""Recommended cells per diameter for production simulations."""

PUBLICATION_CELLS_PER_DIAMETER: Final[int] = 30
"""Recommended cells per diameter for publication-quality results."""

# Mesh quality thresholds (OpenFOAM checkMesh)
MESH_ORTHOGONALITY_MIN: Final[float] = 60.0
"""Minimum acceptable mesh orthogonality in degrees (lower is worse)."""

MESH_ORTHOGONALITY_GOOD: Final[float] = 70.0
"""Good mesh orthogonality threshold in degrees."""

MESH_ORTHOGONALITY_EXCELLENT: Final[float] = 80.0
"""Excellent mesh orthogonality threshold in degrees."""

MESH_SKEWNESS_MAX: Final[float] = 4.0
"""Maximum acceptable mesh skewness (higher is worse)."""

MESH_SKEWNESS_GOOD: Final[float] = 2.0
"""Good mesh skewness threshold."""

MESH_SKEWNESS_EXCELLENT: Final[float] = 1.0
"""Excellent mesh skewness threshold."""

MESH_ASPECT_RATIO_MAX: Final[float] = 100.0
"""Maximum acceptable cell aspect ratio."""

# =============================================================================
# COURANT NUMBER GUIDELINES
# =============================================================================

MAX_COURANT_CONSERVATIVE: Final[float] = 0.5
"""Conservative maximum Courant number for stability."""

MAX_COURANT_STANDARD: Final[float] = 1.0
"""Standard maximum Courant number."""

MAX_COURANT_LES: Final[float] = 0.3
"""Maximum Courant number recommended for LES simulations."""

# =============================================================================
# WINDKESSEL MODEL DEFAULTS
# =============================================================================

# Time constants
TAU_RC_DEFAULT: Final[float] = 1.5
"""Default RC time constant in seconds (typical: 1.0-2.0s)."""

TAU_RC_MIN: Final[float] = 0.5
"""Minimum physiological RC time constant in seconds."""

TAU_RC_MAX: Final[float] = 3.0
"""Maximum physiological RC time constant in seconds."""

# =============================================================================
# MATHEMATICAL CONSTANTS
# =============================================================================

# Murray's law exponent
# Classical value is 3.0 (laminar flow), but 2.6-2.7 is more accurate for pulsatile arterial flow
# Default 2.6 matches schema.py for cardiovascular applications
MURRAY_LAW_EXPONENT: Final[float] = 2.6
"""Murray's law exponent: flow ∝ diameter^n (2.6 for pulsatile, 3.0 for laminar)."""

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def mmhg_to_pa(pressure_mmhg: float) -> float:
    """Convert pressure from mmHg to Pascal.

    Args:
        pressure_mmhg: Pressure in mmHg.

    Returns:
        Pressure in Pascal.

    Example:
        >>> mmhg_to_pa(120)  # Systolic pressure
        15998.64
    """
    return pressure_mmhg * MMHG_TO_PA


def pa_to_mmhg(pressure_pa: float) -> float:
    """Convert pressure from Pascal to mmHg.

    Args:
        pressure_pa: Pressure in Pascal.

    Returns:
        Pressure in mmHg.
    """
    return pressure_pa * PA_TO_MMHG


def cardiac_output_to_m3s(co_lpm: float) -> float:
    """Convert cardiac output from L/min to m³/s.

    Args:
        co_lpm: Cardiac output in liters per minute.

    Returns:
        Flow rate in m³/s.

    Example:
        >>> cardiac_output_to_m3s(5.0)  # 5 L/min
        8.333e-05
    """
    return co_lpm * L_TO_M3 / MIN_TO_S


def calculate_map(systolic: float, diastolic: float) -> float:
    """Calculate Mean Arterial Pressure using physiological formula.

    MAP = DBP + (1/3) × (SBP - DBP) = (2×DBP + SBP) / 3

    This formula accounts for diastole being approximately 2/3 of the
    cardiac cycle duration.

    Args:
        systolic: Systolic blood pressure (mmHg).
        diastolic: Diastolic blood pressure (mmHg).

    Returns:
        Mean arterial pressure in mmHg.

    References:
        Klabunde RE. Cardiovascular Physiology Concepts. 2nd ed. 2011.

    Example:
        >>> calculate_map(120, 80)
        93.33
    """
    return diastolic + (systolic - diastolic) / 3.0


def calculate_kinematic_viscosity(
    dynamic_viscosity: float = BLOOD_VISCOSITY_DEFAULT,
    density: float = BLOOD_DENSITY_DEFAULT
) -> float:
    """Calculate kinematic viscosity from dynamic viscosity and density.

    Args:
        dynamic_viscosity: Dynamic viscosity in Pa·s (default: blood).
        density: Density in kg/m³ (default: blood).

    Returns:
        Kinematic viscosity in m²/s.

    Example:
        >>> calculate_kinematic_viscosity()
        3.7736e-06
    """
    return dynamic_viscosity / density


__all__ = [
    # Unit conversions
    'MMHG_TO_PA', 'PA_TO_MMHG', 'ML_TO_M3', 'M3_TO_ML', 'L_TO_M3',
    'MM_TO_M', 'M_TO_MM', 'MIN_TO_S',
    # Blood properties
    'BLOOD_DENSITY_DEFAULT', 'BLOOD_DENSITY_MIN', 'BLOOD_DENSITY_MAX',
    'BLOOD_VISCOSITY_DEFAULT', 'BLOOD_VISCOSITY_MIN', 'BLOOD_VISCOSITY_MAX',
    'BLOOD_KINEMATIC_VISCOSITY_DEFAULT',
    # Cardiovascular defaults
    'SYSTOLIC_PRESSURE_DEFAULT', 'DIASTOLIC_PRESSURE_DEFAULT',
    'VENOUS_PRESSURE_DEFAULT', 'CARDIAC_OUTPUT_DEFAULT',
    'HEART_RATE_DEFAULT', 'CARDIAC_CYCLE_DEFAULT',
    'PWV_DEFAULT', 'PWV_ELDERLY', 'AORTIC_DIAMETER_DEFAULT',
    'AORTIC_VELOCITY_REFERENCE',
    # Turbulence
    'C_MU', 'TURBULENCE_INTENSITY_DEFAULT', 'TURBULENCE_VISCOSITY_RATIO_DEFAULT',
    'MIXING_LENGTH_FACTOR',
    # Mesh quality
    'MIN_CELLS_PER_DIAMETER', 'DEFAULT_CELLS_PER_DIAMETER',
    'RECOMMENDED_CELLS_PER_DIAMETER', 'PUBLICATION_CELLS_PER_DIAMETER',
    'MESH_ORTHOGONALITY_MIN', 'MESH_ORTHOGONALITY_GOOD', 'MESH_ORTHOGONALITY_EXCELLENT',
    'MESH_SKEWNESS_MAX', 'MESH_SKEWNESS_GOOD', 'MESH_SKEWNESS_EXCELLENT',
    'MESH_ASPECT_RATIO_MAX',
    # Courant numbers
    'MAX_COURANT_CONSERVATIVE', 'MAX_COURANT_STANDARD', 'MAX_COURANT_LES',
    # Windkessel
    'TAU_RC_DEFAULT', 'TAU_RC_MIN', 'TAU_RC_MAX',
    # Murray's law
    'MURRAY_LAW_EXPONENT',
    # Functions
    'mmhg_to_pa', 'pa_to_mmhg', 'cardiac_output_to_m3s',
    'calculate_map', 'calculate_kinematic_viscosity',
]
