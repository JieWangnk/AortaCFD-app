# src/writers/transport_properties.py
"""
Simplified transportProperties file writer.

Writes the transportProperties file for fluid properties.
"""

import os
import logging
from typing import Any, Dict, Optional, Union

from ..config.accessor import Config, wrap_config
from ..registry.physics import BLOOD_PROPERTIES, get_blood_properties
from .header import openfoam_header, format_value

logger = logging.getLogger(__name__)


def write_transport_properties(
    config: Union[Dict[str, Any], Config],
    case_dir: str,
    nu: Optional[float] = None,
    rho: Optional[float] = None,
) -> str:
    """
    Write transportProperties file to case directory.

    Args:
        config: Configuration dictionary or Config accessor
        case_dir: Path to OpenFOAM case directory
        nu: Override kinematic viscosity (m²/s)
        rho: Override density (kg/m³)

    Returns:
        Path to written file
    """
    cfg = wrap_config(config)

    # Get properties (from config or defaults)
    if nu is None:
        nu = cfg.nu
    if rho is None:
        rho = cfg.rho

    # Validate
    _validate_properties(nu, rho)

    # Generate file content
    content = _generate_transport_properties_content(nu, rho)

    # Write file
    file_path = os.path.join(case_dir, "constant", "transportProperties")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, 'w') as f:
        f.write(content)

    logger.info(f"Wrote transportProperties (nu={nu:.6e} m²/s) to {file_path}")
    return file_path


def _validate_properties(nu: float, rho: float) -> None:
    """
    Validate physical properties are in reasonable ranges.

    Args:
        nu: Kinematic viscosity (m²/s)
        rho: Density (kg/m³)

    Raises:
        ValueError: If properties are out of reasonable range
    """
    # Kinematic viscosity should be positive and reasonable
    if nu <= 0:
        raise ValueError(f"Kinematic viscosity must be positive, got {nu}")

    # Check if nu is reasonable for blood (roughly 2e-6 to 6e-6 m²/s)
    if nu < 1e-7 or nu > 1e-4:
        logger.warning(
            f"Kinematic viscosity {nu:.3e} m²/s is outside typical blood range "
            f"(2e-6 to 6e-6 m²/s). Verify units are correct."
        )

    # Density validation
    rho_min, rho_max = BLOOD_PROPERTIES['density_range']
    if rho < rho_min or rho > rho_max:
        logger.warning(
            f"Density {rho} kg/m³ is outside typical blood range "
            f"({rho_min}-{rho_max} kg/m³)."
        )


def _generate_transport_properties_content(nu: float, rho: float) -> str:
    """
    Generate transportProperties file content.

    Args:
        nu: Kinematic viscosity (m²/s)
        rho: Density (kg/m³)

    Returns:
        File content string
    """
    lines = [openfoam_header("dictionary", "transportProperties", location="constant")]

    # OpenFOAM 12 format with dimensions
    lines.extend([
        "transportModel  Newtonian;",
        "",
        f"nu              [0 2 -1 0 0 0 0] {nu:.6e};",
        "",
        "// Density (for reference and post-processing)",
        f"rho             [1 -3 0 0 0 0 0] {rho};",
        "",
    ])

    lines.append("// ************************************************************************* //")

    return "\n".join(lines)


def write_momentum_transport(
    config: Union[Dict[str, Any], Config],
    case_dir: str,
) -> str:
    """
    Write momentumTransport file to case directory.

    Args:
        config: Configuration dictionary or Config accessor
        case_dir: Path to OpenFOAM case directory

    Returns:
        Path to written file
    """
    cfg = wrap_config(config)

    sim_type = cfg.simulation_type

    # Generate content based on simulation type
    content = _generate_momentum_transport_content(sim_type, cfg)

    # Write file
    file_path = os.path.join(case_dir, "constant", "momentumTransport")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, 'w') as f:
        f.write(content)

    logger.info(f"Wrote momentumTransport ({sim_type}) to {file_path}")
    return file_path


def _generate_momentum_transport_content(sim_type: str, cfg: Config) -> str:
    """
    Generate momentumTransport file content.

    Args:
        sim_type: Simulation type (laminar, rans, les)
        cfg: Config accessor

    Returns:
        File content string
    """
    lines = [openfoam_header("dictionary", "momentumTransport", location="constant")]

    if sim_type == 'laminar':
        lines.extend([
            "simulationType  laminar;",
            "",
        ])
    elif sim_type == 'rans':
        turb_model = cfg.physics.get('turbulence_model', 'kOmegaSST')
        lines.extend([
            "simulationType  RAS;",
            "",
            "RAS",
            "{",
            f"    model           {turb_model};",
            "    turbulence      on;",
            "    printCoeffs     on;",
            "}",
            "",
        ])
    elif sim_type == 'les':
        les_model = cfg.physics.get('les_model', 'WALE')
        lines.extend([
            "simulationType  LES;",
            "",
            "LES",
            "{",
            f"    model           {les_model};",
            "    turbulence      on;",
            "    printCoeffs     on;",
            "    delta           cubeRootVol;",
            "",
            "    cubeRootVolCoeffs",
            "    {",
            "        deltaCoeff      1;",
            "    }",
            "}",
            "",
        ])

    lines.append("// ************************************************************************* //")

    return "\n".join(lines)
