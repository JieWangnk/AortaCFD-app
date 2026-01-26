# src/writers/fv_schemes.py
"""
Simplified fvSchemes file writer.

Writes the fvSchemes file using settings from the registry.
"""

import os
import logging
from typing import Any, Dict, Optional, Union

from ..config.accessor import Config, wrap_config
from ..registry.numerics import get_schemes
from .header import openfoam_header

logger = logging.getLogger(__name__)


def write_fv_schemes(
    config: Union[Dict[str, Any], Config],
    case_dir: str,
    profile: Optional[str] = None,
) -> str:
    """
    Write fvSchemes file to case directory.

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

    # Get schemes from registry
    schemes = get_schemes(profile)

    # Check simulation type for LES-specific settings
    is_les = cfg.is_les
    is_steady = cfg.physics.get('steady_state', False)

    # Override ddt scheme for steady state
    if is_steady:
        schemes['ddt'] = 'steadyState'

    # Generate file content
    content = _generate_fv_schemes_content(schemes, is_les, cfg)

    # Write file
    file_path = os.path.join(case_dir, "system", "fvSchemes")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, 'w') as f:
        f.write(content)

    logger.info(f"Wrote fvSchemes ({profile} profile) to {file_path}")
    return file_path


def _generate_fv_schemes_content(
    schemes: Dict[str, str],
    is_les: bool,
    cfg: Config,
) -> str:
    """
    Generate fvSchemes file content.

    Args:
        schemes: Scheme settings from registry
        is_les: Whether LES is used
        cfg: Config accessor

    Returns:
        File content string
    """
    lines = [openfoam_header("dictionary", "fvSchemes")]

    # ddtSchemes
    lines.extend([
        "ddtSchemes",
        "{",
        f"    default         {schemes['ddt']};",
        "}",
        "",
    ])

    # gradSchemes
    lines.extend([
        "gradSchemes",
        "{",
        f"    default         {schemes['grad_default']};",
        f"    grad(U)         {schemes['grad_U']};",
        f"    grad(p)         {schemes['grad_p']};",
        "}",
        "",
    ])

    # divSchemes
    lines.extend([
        "divSchemes",
        "{",
        "    default         none;",
        f"    div(phi,U)      {schemes['div_phi_U']};",
    ])

    # Add turbulence schemes if needed
    if cfg.is_turbulent:
        lines.extend([
            f"    div(phi,k)      {schemes['div_phi_k']};",
            f"    div(phi,omega)  {schemes['div_phi_omega']};",
            f"    div(phi,epsilon) {schemes['div_phi_epsilon']};",
        ])

    # LES-specific
    if is_les:
        lines.append("    div(phi,nuTilda) Gauss limitedLinear 1;")

    lines.extend([
        f"    div((nuEff*dev2(T(grad(U))))) {schemes['div_nuEff_dev_T_grad_U']};",
        "}",
        "",
    ])

    # laplacianSchemes
    lines.extend([
        "laplacianSchemes",
        "{",
        f"    default         {schemes['laplacian_default']};",
        "}",
        "",
    ])

    # interpolationSchemes
    lines.extend([
        "interpolationSchemes",
        "{",
        f"    default         {schemes['interpolation_default']};",
        "}",
        "",
    ])

    # snGradSchemes
    lines.extend([
        "snGradSchemes",
        "{",
        f"    default         {schemes['snGrad_default']};",
        "}",
        "",
    ])

    # wallDist (for turbulence models)
    if cfg.is_turbulent:
        lines.extend([
            "wallDist",
            "{",
            "    method          meshWave;",
            "}",
            "",
        ])

    lines.append("// ************************************************************************* //")

    return "\n".join(lines)
