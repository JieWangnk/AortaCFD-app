# src/writers/fv_solution.py
"""
Simplified fvSolution file writer.

Writes the fvSolution file using settings from the registry.
"""

import os
import logging
from typing import Any, Dict, Optional, Union

from ..config.accessor import Config, wrap_config
from ..registry.numerics import (
    get_solver_settings,
    get_relaxation_factors,
    get_pimple_settings,
    get_convergence_criteria,
)
from .header import openfoam_header, format_value

logger = logging.getLogger(__name__)


def write_fv_solution(
    config: Union[Dict[str, Any], Config],
    case_dir: str,
    profile: Optional[str] = None,
) -> str:
    """
    Write fvSolution file to case directory.

    Args:
        config: Configuration dictionary or Config accessor
        case_dir: Path to OpenFOAM case directory
        profile: Override profile name (default: from config)

    Returns:
        Path to written file
    """
    cfg = wrap_config(config)

    # Get profile (override or from config)
    if profile is None:
        profile = cfg.profile

    # Get settings from registry
    solvers = get_solver_settings(profile)
    relaxation = get_relaxation_factors(profile)
    pimple = get_pimple_settings(profile)
    convergence = get_convergence_criteria(profile)

    # Generate file content
    content = _generate_fv_solution_content(
        solvers, relaxation, pimple, convergence, cfg
    )

    # Write file
    file_path = os.path.join(case_dir, "system", "fvSolution")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, 'w') as f:
        f.write(content)

    logger.info(f"Wrote fvSolution ({profile} profile) to {file_path}")
    return file_path


def _generate_fv_solution_content(
    solvers: Dict[str, Dict[str, Any]],
    relaxation: Dict[str, Dict[str, float]],
    pimple: Dict[str, Any],
    convergence: Dict[str, Dict[str, float]],
    cfg: Config,
) -> str:
    """
    Generate fvSolution file content.

    Args:
        solvers: Solver settings per field
        relaxation: Relaxation factors
        pimple: PIMPLE algorithm settings
        convergence: Convergence criteria
        cfg: Config accessor

    Returns:
        File content string
    """
    lines = [openfoam_header("dictionary", "fvSolution")]

    # Solvers section
    lines.extend([
        "solvers",
        "{",
    ])

    for field, settings in solvers.items():
        # Skip turbulence fields if laminar
        if field in ['k', 'omega', 'epsilon'] and not cfg.is_turbulent:
            continue

        lines.append(f"    {field}")
        lines.append("    {")
        for key, value in settings.items():
            lines.append(f"        {key:<20}{format_value(value)};")
        lines.append("    }")
        lines.append("")

    lines.extend([
        "}",
        "",
    ])

    # PIMPLE section
    lines.extend([
        "PIMPLE",
        "{",
    ])
    for key, value in pimple.items():
        lines.append(f"    {key:<24}{format_value(value)};")

    # Add residual control if using outer corrector convergence
    if 'outerLoop' in convergence:
        lines.extend([
            "",
            "    residualControl",
            "    {",
        ])
        for field, tol in convergence['outerLoop'].items():
            lines.append(f"        {field:<20}{format_value(tol)};")
        lines.extend([
            "    }",
        ])

    lines.extend([
        "}",
        "",
    ])

    # Relaxation factors section
    lines.extend([
        "relaxationFactors",
        "{",
        "    fields",
        "    {",
    ])
    for field, value in relaxation['fields'].items():
        lines.append(f"        {field:<20}{format_value(value)};")
    lines.extend([
        "    }",
        "    equations",
        "    {",
    ])
    for field, value in relaxation['equations'].items():
        # Skip turbulence fields if laminar
        if field.replace('Final', '') in ['k', 'omega', 'epsilon'] and not cfg.is_turbulent:
            continue
        lines.append(f"        {field:<20}{format_value(value)};")
    lines.extend([
        "    }",
        "}",
        "",
    ])

    lines.append("// ************************************************************************* //")

    return "\n".join(lines)
