# src/windkessel/writer.py
"""
Windkessel properties file writer.

Generates the windkesselProperties file for OpenFOAM's
Windkessel boundary condition.

Usage:
    from src.windkessel.writer import write_windkessel_properties

    write_windkessel_properties(
        case_dir='/path/to/case',
        outlet_params={'outlet1': params1, 'outlet2': params2},
    )
"""

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
import logging

from .circuit import WindkesselParams

logger = logging.getLogger(__name__)


@dataclass
class WindkesselConfig:
    """
    Complete Windkessel configuration for all outlets.

    Attributes:
        outlet_params: Dictionary of outlet name -> WindkesselParams
        model_type: '2E' or '3E' (2 or 3 element)
        venous_pressure: Venous/reference pressure (Pa)
    """
    outlet_params: Dict[str, WindkesselParams]
    model_type: str = '3E'
    venous_pressure: float = 0.0

    @property
    def n_outlets(self) -> int:
        """Number of outlets."""
        return len(self.outlet_params)

    @property
    def outlet_names(self) -> List[str]:
        """List of outlet names."""
        return list(self.outlet_params.keys())


def write_windkessel_properties(
    case_dir: str,
    outlet_params: Dict[str, WindkesselParams],
    model_type: str = '3E',
    venous_pressure: float = 0.0,
) -> str:
    """
    Write windkesselProperties file to case directory.

    Args:
        case_dir: Path to OpenFOAM case directory
        outlet_params: Dictionary of outlet name -> WindkesselParams
        model_type: '2E' or '3E' (2 or 3 element model)
        venous_pressure: Venous/reference pressure (Pa)

    Returns:
        Path to written file
    """
    file_path = os.path.join(case_dir, "constant", "windkesselProperties")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    content = _generate_windkessel_content(
        outlet_params, model_type, venous_pressure
    )

    with open(file_path, 'w') as f:
        f.write(content)

    logger.info(f"Wrote windkesselProperties ({len(outlet_params)} outlets) to {file_path}")

    return file_path


def _generate_windkessel_content(
    outlet_params: Dict[str, WindkesselParams],
    model_type: str,
    venous_pressure: float,
) -> str:
    """
    Generate windkesselProperties file content.

    Args:
        outlet_params: Dictionary of outlet name -> WindkesselParams
        model_type: '2E' or '3E'
        venous_pressure: Venous pressure (Pa)

    Returns:
        File content string
    """
    lines = [_openfoam_header()]

    # Global settings
    lines.extend([
        "// Windkessel model type: 2E (R-C) or 3E (R-C-R)",
        f'modelType        "{model_type}";',
        "",
        "// Reference (venous) pressure [Pa]",
        f"Pref             {venous_pressure};",
        "",
    ])

    # Outlet-specific settings
    lines.append("// Outlet-specific Windkessel parameters")
    lines.append("outlets")
    lines.append("{")

    for name, params in outlet_params.items():
        lines.extend([
            f"    {name}",
            "    {",
            f"        R1              {params.R1:.6e};  // Proximal resistance [Pa.s/m³]",
            f"        R2              {params.R2:.6e};  // Distal resistance [Pa.s/m³]",
            f"        C               {params.C:.6e};  // Compliance [m³/Pa]",
            "    }",
            "",
        ])

    lines.append("}")
    lines.append("")

    # Summary comments
    lines.extend([
        "// Summary:",
    ])
    for name, params in outlet_params.items():
        tau = params.R2 * params.C
        lines.append(
            f"//   {name}: Rt={params.Rt:.3e}, tau={tau:.3f}s, R1/Rt={params.R1_ratio:.1%}"
        )

    lines.append("")
    lines.append("// ************************************************************************* //")

    return "\n".join(lines)


def _openfoam_header() -> str:
    """Generate OpenFOAM file header."""
    return """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  12                                    |
|   \\\\  /    A nd           | Website:  www.openfoam.org                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "constant";
    object      windkesselProperties;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
"""


def write_windkessel_bc_entry(
    outlet_name: str,
    params: WindkesselParams,
    field: str = 'p',
) -> str:
    """
    Generate boundary condition entry for p field file.

    Args:
        outlet_name: Name of outlet patch
        params: Windkessel parameters
        field: Field name (typically 'p')

    Returns:
        BC entry string for 0/p file
    """
    lines = [
        f"    {outlet_name}",
        "    {",
        "        type            windkessel;",
        f"        R1              {params.R1:.6e};",
        f"        R2              {params.R2:.6e};",
        f"        C               {params.C:.6e};",
        "        Pref            0;",
        "        value           uniform 0;",
        "    }",
    ]
    return "\n".join(lines)


def format_params_table(
    outlet_params: Dict[str, WindkesselParams],
) -> str:
    """
    Format Windkessel parameters as a readable table.

    Args:
        outlet_params: Dictionary of outlet name -> WindkesselParams

    Returns:
        Formatted table string
    """
    lines = [
        "Windkessel Parameters",
        "=" * 80,
        f"{'Outlet':<15} {'R1 (Pa.s/m³)':<15} {'R2 (Pa.s/m³)':<15} {'C (m³/Pa)':<15} {'tau (s)':<10}",
        "-" * 80,
    ]

    for name, params in outlet_params.items():
        lines.append(
            f"{name:<15} {params.R1:<15.3e} {params.R2:<15.3e} "
            f"{params.C:<15.3e} {params.tau:<10.3f}"
        )

    lines.append("=" * 80)

    return "\n".join(lines)


def calculate_and_write_windkessel(
    case_dir: str,
    outlet_names: List[str],
    outlet_areas: Dict[str, float],
    mean_pressure: float = 13332.2,  # 100 mmHg
    cardiac_output: float = 8.33e-5,  # 5 L/min
    cardiac_cycle: float = 1.0,
    model_type: str = '3E',
) -> WindkesselConfig:
    """
    Calculate and write Windkessel properties (high-level interface).

    This function:
    1. Calculates flow split using Murray's law
    2. Determines Windkessel parameters for each outlet
    3. Writes the windkesselProperties file

    Args:
        case_dir: Path to OpenFOAM case directory
        outlet_names: List of outlet names
        outlet_areas: Dictionary of outlet name -> area (m²)
        mean_pressure: Mean arterial pressure (Pa)
        cardiac_output: Cardiac output (m³/s)
        cardiac_cycle: Cardiac cycle duration (s)
        model_type: '2E' or '3E'

    Returns:
        WindkesselConfig with all parameters
    """
    from .murray import calculate_murray_flow_split_named
    from .circuit import calculate_3element_params, calculate_2element_params

    # Calculate flow split
    flow_fractions = calculate_murray_flow_split_named(outlet_areas)

    # Calculate total resistance
    R_total = mean_pressure / cardiac_output

    # Calculate parameters for each outlet
    outlet_params = {}

    for name in outlet_names:
        if name not in flow_fractions:
            logger.warning(f"No area found for outlet {name}, skipping")
            continue

        frac = flow_fractions[name]
        outlet_flow = cardiac_output * frac

        # Individual outlet resistance (parallel)
        R_outlet = mean_pressure / outlet_flow

        if model_type == '3E':
            params = calculate_3element_params(
                mean_pressure=mean_pressure,
                mean_flow=outlet_flow,
                cardiac_cycle=cardiac_cycle,
                outlet_name=name,
            )
        else:
            # 2-element: need pulse pressure and stroke volume estimates
            # Use typical values
            pulse_pressure = mean_pressure * 0.4  # ~40 mmHg for 100 mmHg MAP
            stroke_volume = cardiac_output * cardiac_cycle * 0.35  # Systolic fraction
            params = calculate_2element_params(
                mean_pressure=mean_pressure,
                mean_flow=outlet_flow,
                pulse_pressure=pulse_pressure,
                stroke_volume=stroke_volume * frac,
                outlet_name=name,
            )

        outlet_params[name] = params

    # Write file
    write_windkessel_properties(case_dir, outlet_params, model_type)

    # Log summary
    logger.info(format_params_table(outlet_params))

    return WindkesselConfig(
        outlet_params=outlet_params,
        model_type=model_type,
    )
