# src/writers/decompose_par_dict.py
"""
Simplified decomposeParDict file writer.

Writes the decomposeParDict file for parallel decomposition.
"""

import os
import logging
from typing import Any, Dict, Optional, Union

from ..config.accessor import Config, wrap_config
from .header import openfoam_header

logger = logging.getLogger(__name__)


def write_decompose_par_dict(
    config: Union[Dict[str, Any], Config],
    case_dir: str,
    n_subdomains: Optional[int] = None,
    method: Optional[str] = None,
) -> str:
    """
    Write decomposeParDict file to case directory.

    Args:
        config: Configuration dictionary or Config accessor
        case_dir: Path to OpenFOAM case directory
        n_subdomains: Override number of subdomains
        method: Override decomposition method

    Returns:
        Path to written file
    """
    cfg = wrap_config(config)

    # Get settings
    if n_subdomains is None:
        n_subdomains = cfg.subdomains
    if method is None:
        method = cfg.decomposition_method

    # Validate
    if n_subdomains < 1:
        raise ValueError(f"Number of subdomains must be >= 1, got {n_subdomains}")

    valid_methods = ['scotch', 'hierarchical', 'simple', 'metis']
    if method not in valid_methods:
        logger.warning(f"Unknown decomposition method '{method}', using 'scotch'")
        method = 'scotch'

    # Generate content
    content = _generate_decompose_par_dict_content(n_subdomains, method)

    # Write file
    file_path = os.path.join(case_dir, "system", "decomposeParDict")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, 'w') as f:
        f.write(content)

    logger.info(f"Wrote decomposeParDict ({n_subdomains} subdomains, {method}) to {file_path}")
    return file_path


def _generate_decompose_par_dict_content(n_subdomains: int, method: str) -> str:
    """
    Generate decomposeParDict file content.

    Args:
        n_subdomains: Number of subdomains for parallel execution
        method: Decomposition method

    Returns:
        File content string
    """
    lines = [openfoam_header("dictionary", "decomposeParDict")]

    lines.extend([
        f"numberOfSubdomains  {n_subdomains};",
        "",
        f"method              {method};",
        "",
    ])

    # Method-specific coefficients
    if method == 'scotch':
        lines.extend([
            "scotchCoeffs",
            "{",
            "}",
            "",
        ])
    elif method == 'hierarchical':
        # Calculate reasonable n values
        # Try to find factors close to cube root
        n = _calculate_hierarchical_coeffs(n_subdomains)
        lines.extend([
            "hierarchicalCoeffs",
            "{",
            f"    n               ({n[0]} {n[1]} {n[2]});",
            "    order           xyz;",
            "}",
            "",
        ])
    elif method == 'simple':
        n = _calculate_hierarchical_coeffs(n_subdomains)
        lines.extend([
            "simpleCoeffs",
            "{",
            f"    n               ({n[0]} {n[1]} {n[2]});",
            "}",
            "",
        ])

    lines.append("// ************************************************************************* //")

    return "\n".join(lines)


def _calculate_hierarchical_coeffs(n_subdomains: int) -> tuple:
    """
    Calculate reasonable (nx, ny, nz) for hierarchical decomposition.

    Args:
        n_subdomains: Total number of subdomains

    Returns:
        Tuple of (nx, ny, nz) such that nx * ny * nz = n_subdomains
    """
    import math

    # Try to find factors close to cube root
    cube_root = round(n_subdomains ** (1/3))

    # Start from cube root and work outward
    for nz in range(cube_root, 0, -1):
        if n_subdomains % nz == 0:
            remaining = n_subdomains // nz
            sqrt_remaining = round(remaining ** 0.5)

            for ny in range(sqrt_remaining, 0, -1):
                if remaining % ny == 0:
                    nx = remaining // ny
                    return (nx, ny, nz)

    # Fallback: (n, 1, 1)
    return (n_subdomains, 1, 1)
