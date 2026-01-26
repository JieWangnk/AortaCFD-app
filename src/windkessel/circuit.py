# src/windkessel/circuit.py
"""
Windkessel circuit calculations.

Provides calculations for 2-element and 3-element Windkessel models.

2-Element (R-C) Model:
    P(t) = R * Q(t) + P_venous

3-Element (R-C-R) Model:
    P(t) = R1 * Q(t) + integral of (Q - (P-Pv)/R2) / C

Parameters:
- R1: Characteristic (proximal) resistance - models wave impedance
- R2: Peripheral (distal) resistance - models microvascular resistance
- C: Arterial compliance - models vessel elasticity

Usage:
    from src.windkessel.circuit import calculate_3element_params

    params = calculate_3element_params(
        mean_pressure=100 * 133.322,  # mmHg to Pa
        mean_flow=5e-5,               # m³/s
        cardiac_cycle=0.8,            # s
    )
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class WindkesselParams:
    """
    Container for Windkessel circuit parameters.

    Attributes:
        R1: Characteristic/proximal resistance (Pa·s/m³)
        R2: Peripheral/distal resistance (Pa·s/m³)
        C: Compliance (m³/Pa)
        Rt: Total resistance R1 + R2 (Pa·s/m³)
        tau: Time constant R2 * C (s)
        outlet_name: Name of the outlet patch
    """
    R1: float  # Proximal resistance
    R2: float  # Distal resistance
    C: float   # Compliance
    outlet_name: str = ""

    @property
    def Rt(self) -> float:
        """Total resistance."""
        return self.R1 + self.R2

    @property
    def tau(self) -> float:
        """Time constant (diastolic decay)."""
        return self.R2 * self.C

    @property
    def R1_ratio(self) -> float:
        """Ratio of R1 to total resistance."""
        return self.R1 / self.Rt if self.Rt > 0 else 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'R1': self.R1,
            'R2': self.R2,
            'C': self.C,
            'Rt': self.Rt,
            'tau': self.tau,
            'outlet_name': self.outlet_name,
        }


def calculate_total_resistance(
    mean_pressure: float,
    mean_flow: float,
    venous_pressure: float = 0.0,
) -> float:
    """
    Calculate total vascular resistance.

    R_total = (P_mean - P_venous) / Q_mean

    Args:
        mean_pressure: Mean arterial pressure (Pa)
        mean_flow: Mean volumetric flow rate (m³/s)
        venous_pressure: Venous pressure (Pa), typically 0 for gauge

    Returns:
        Total resistance (Pa·s/m³)
    """
    if mean_flow <= 0:
        raise ValueError("Mean flow must be positive")

    return (mean_pressure - venous_pressure) / mean_flow


def calculate_compliance(
    pulse_pressure: float,
    stroke_volume: float,
) -> float:
    """
    Calculate arterial compliance.

    C = SV / PP

    where SV is stroke volume and PP is pulse pressure.

    Args:
        pulse_pressure: Pulse pressure (Pa) = P_systolic - P_diastolic
        stroke_volume: Stroke volume (m³) = integral of Q over systole

    Returns:
        Compliance (m³/Pa)
    """
    if pulse_pressure <= 0:
        raise ValueError("Pulse pressure must be positive")

    return stroke_volume / pulse_pressure


def calculate_2element_params(
    mean_pressure: float,
    mean_flow: float,
    pulse_pressure: float,
    stroke_volume: float,
    outlet_name: str = "",
) -> WindkesselParams:
    """
    Calculate 2-element Windkessel parameters.

    2-Element model has:
    - R: Single resistance (peripheral)
    - C: Compliance

    Args:
        mean_pressure: Mean arterial pressure (Pa)
        mean_flow: Mean flow rate (m³/s)
        pulse_pressure: Pulse pressure (Pa)
        stroke_volume: Stroke volume (m³)
        outlet_name: Name of outlet patch

    Returns:
        WindkesselParams with R1=0, R2=R_total
    """
    R_total = calculate_total_resistance(mean_pressure, mean_flow)
    C = calculate_compliance(pulse_pressure, stroke_volume)

    return WindkesselParams(
        R1=0.0,  # No proximal resistance in 2-element model
        R2=R_total,
        C=C,
        outlet_name=outlet_name,
    )


def calculate_3element_params(
    mean_pressure: float,
    mean_flow: float,
    pulse_pressure: Optional[float] = None,
    stroke_volume: Optional[float] = None,
    cardiac_cycle: float = 1.0,
    R1_ratio: float = 0.1,
    tau_ratio: float = 0.5,
    outlet_name: str = "",
) -> WindkesselParams:
    """
    Calculate 3-element Windkessel parameters.

    3-Element model has:
    - R1: Characteristic/proximal resistance (wave impedance)
    - R2: Peripheral/distal resistance
    - C: Compliance

    Two methods are available:
    1. If pulse_pressure and stroke_volume provided: direct calculation
    2. Otherwise: use typical ratios to estimate

    Args:
        mean_pressure: Mean arterial pressure (Pa)
        mean_flow: Mean flow rate (m³/s)
        pulse_pressure: Pulse pressure (Pa), optional
        stroke_volume: Stroke volume (m³), optional
        cardiac_cycle: Cardiac cycle duration (s)
        R1_ratio: Ratio of R1 to total resistance (default 0.1 = 10%)
        tau_ratio: Ratio of time constant to cardiac cycle (default 0.5)
        outlet_name: Name of outlet patch

    Returns:
        WindkesselParams
    """
    # Calculate total resistance
    R_total = calculate_total_resistance(mean_pressure, mean_flow)

    # Split into R1 and R2
    # R1 typically 5-20% of total (wave impedance)
    R1 = R1_ratio * R_total
    R2 = R_total - R1

    # Calculate compliance
    if pulse_pressure is not None and stroke_volume is not None:
        # Direct calculation
        C = calculate_compliance(pulse_pressure, stroke_volume)
    else:
        # Estimate from time constant
        # tau = R2 * C, typically 0.3-0.7 of cardiac cycle
        tau = tau_ratio * cardiac_cycle
        C = tau / R2 if R2 > 0 else 1e-9

    logger.debug(
        f"3-Element WK: R1={R1:.3e}, R2={R2:.3e}, C={C:.3e}, "
        f"Rt={R_total:.3e}, tau={R2*C:.3f}s"
    )

    return WindkesselParams(
        R1=R1,
        R2=R2,
        C=C,
        outlet_name=outlet_name,
    )


def calculate_params_from_literature(
    outlet_name: str,
    outlet_area: float,
    cardiac_output: float = 5e-5,  # 5 L/min in m³/s
    mean_arterial_pressure: float = 13332.2,  # 100 mmHg in Pa
) -> WindkesselParams:
    """
    Calculate Windkessel parameters using literature-based scaling.

    This uses typical physiological values and scales by outlet area.

    Args:
        outlet_name: Name of outlet
        outlet_area: Outlet cross-sectional area (m²)
        cardiac_output: Total cardiac output (m³/s)
        mean_arterial_pressure: Mean arterial pressure (Pa)

    Returns:
        WindkesselParams scaled for this outlet
    """
    # Total systemic resistance
    R_systemic = mean_arterial_pressure / cardiac_output

    # Typical aortic compliance (Westerhof 1969)
    # C_total ~ 1-2 mL/mmHg = 7.5e-9 to 1.5e-8 m³/Pa
    C_total = 1e-8  # m³/Pa

    # Scale by outlet area (larger outlets = more flow = lower resistance)
    # This is a simplification; real scaling depends on vascular bed
    flow_fraction = estimate_flow_fraction(outlet_name, outlet_area)

    R_outlet = R_systemic / flow_fraction if flow_fraction > 0 else R_systemic
    C_outlet = C_total * flow_fraction

    # 3-element split
    R1_ratio = 0.1
    R1 = R1_ratio * R_outlet
    R2 = R_outlet - R1

    return WindkesselParams(
        R1=R1,
        R2=R2,
        C=C_outlet,
        outlet_name=outlet_name,
    )


def estimate_flow_fraction(outlet_name: str, outlet_area: float) -> float:
    """
    Estimate flow fraction for an outlet based on name and area.

    This is a heuristic based on typical aortic branch flow distributions.

    Args:
        outlet_name: Name of outlet (e.g., 'outlet1', 'brachiocephalic')
        outlet_area: Outlet area (m²)

    Returns:
        Estimated fraction of total flow (0-1)
    """
    # Named outlets with typical flow fractions
    named_fractions = {
        'brachiocephalic': 0.15,
        'bca': 0.15,
        'left_carotid': 0.08,
        'lca': 0.08,
        'lcca': 0.08,
        'left_subclavian': 0.08,
        'lsa': 0.08,
        'lsca': 0.08,
        'descending': 0.70,
        'desc': 0.70,
        'dao': 0.70,
    }

    # Check for named outlet
    name_lower = outlet_name.lower()
    for key, fraction in named_fractions.items():
        if key in name_lower:
            return fraction

    # Default: estimate based on area
    # Typical total aortic outlet area ~ 4 cm² = 4e-4 m²
    typical_total_area = 4e-4
    return min(outlet_area / typical_total_area, 0.5)


def validate_params(params: WindkesselParams) -> bool:
    """
    Validate Windkessel parameters are physically reasonable.

    Args:
        params: WindkesselParams to validate

    Returns:
        True if valid, False otherwise
    """
    issues = []

    # Resistance checks
    if params.R1 < 0:
        issues.append(f"R1 is negative: {params.R1}")
    if params.R2 <= 0:
        issues.append(f"R2 must be positive: {params.R2}")

    # Compliance check
    if params.C <= 0:
        issues.append(f"C must be positive: {params.C}")

    # Typical ranges (Pa·s/m³ for R, m³/Pa for C)
    # R ~ 1e7 to 1e10 Pa·s/m³
    # C ~ 1e-10 to 1e-7 m³/Pa
    if params.Rt < 1e6 or params.Rt > 1e11:
        issues.append(f"Total resistance {params.Rt:.2e} outside typical range")

    if params.C < 1e-12 or params.C > 1e-6:
        issues.append(f"Compliance {params.C:.2e} outside typical range")

    # Time constant check (should be fraction of cardiac cycle)
    if params.tau < 0.1 or params.tau > 5.0:
        issues.append(f"Time constant {params.tau:.2f}s seems unusual")

    if issues:
        for issue in issues:
            logger.warning(f"WK validation: {issue}")
        return False

    return True
