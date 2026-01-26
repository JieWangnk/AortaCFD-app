# src/writers/control_dict.py
"""
Simplified controlDict file writer.

Writes the controlDict file for simulation control.
"""

import os
import logging
from typing import Any, Dict, Optional, Union

from ..config.accessor import Config, wrap_config
from ..registry.numerics import get_time_stepping
from .header import openfoam_header, format_value

logger = logging.getLogger(__name__)


def write_control_dict(
    config: Union[Dict[str, Any], Config],
    case_dir: str,
    end_time: Optional[float] = None,
    cardiac_cycle: Optional[float] = None,
    profile: Optional[str] = None,
) -> str:
    """
    Write controlDict file to case directory.

    Args:
        config: Configuration dictionary or Config accessor
        case_dir: Path to OpenFOAM case directory
        end_time: Override end time (default: calculated from config)
        cardiac_cycle: Cardiac cycle duration for function objects
        profile: Override profile name (default: from config)

    Returns:
        Path to written file
    """
    cfg = wrap_config(config)

    # Get profile
    if profile is None:
        profile = cfg.profile

    # Get time stepping from registry
    time_stepping = get_time_stepping(profile)

    # Calculate end time
    if end_time is None:
        end_time = cfg.end_time
        if end_time is None and cardiac_cycle is not None:
            end_time = cardiac_cycle * cfg.num_cycles
        elif end_time is None:
            end_time = 1.0  # Default fallback

    # Get write interval
    write_interval = cfg.write_interval

    # Calculate purge write
    purge_write = _calculate_purge_write(cfg, cardiac_cycle, write_interval)

    # Check if Windkessel is needed
    needs_windkessel = cfg.is_windkessel

    # Generate file content
    content = _generate_control_dict_content(
        cfg=cfg,
        end_time=end_time,
        write_interval=write_interval,
        purge_write=purge_write,
        time_stepping=time_stepping,
        needs_windkessel=needs_windkessel,
        cardiac_cycle=cardiac_cycle,
    )

    # Write file
    file_path = os.path.join(case_dir, "system", "controlDict")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, 'w') as f:
        f.write(content)

    logger.info(f"Wrote controlDict (endTime={end_time}s) to {file_path}")
    return file_path


def _calculate_purge_write(
    cfg: Config,
    cardiac_cycle: Optional[float],
    write_interval: float,
) -> int:
    """
    Calculate purgeWrite value for disk space management.

    Args:
        cfg: Config accessor
        cardiac_cycle: Cardiac cycle duration
        write_interval: Write interval

    Returns:
        purgeWrite value (0 = keep all)
    """
    # Check for direct purgeWrite setting
    direct_purge = cfg.control_dict.get('purgeWrite')
    if direct_purge is not None and direct_purge != 0:
        return direct_purge

    # Check for keep_last_cycles setting
    keep_last_cycles = cfg.simulation_control.get('keep_last_cycles')

    if keep_last_cycles is None or cardiac_cycle is None:
        return 0  # Keep all

    if cardiac_cycle <= 0 or write_interval <= 0:
        return 0

    # Calculate timesteps per cycle
    timesteps_per_cycle = int(cardiac_cycle / write_interval)

    # Calculate purgeWrite with 10% buffer
    purge_write = int(timesteps_per_cycle * keep_last_cycles * 1.1)

    logger.info(f"Calculated purgeWrite={purge_write} (keeps ~{keep_last_cycles} cycles)")
    return purge_write


def _generate_control_dict_content(
    cfg: Config,
    end_time: float,
    write_interval: float,
    purge_write: int,
    time_stepping: Dict[str, Any],
    needs_windkessel: bool,
    cardiac_cycle: Optional[float],
) -> str:
    """
    Generate controlDict file content.

    Args:
        cfg: Config accessor
        end_time: Simulation end time
        write_interval: Write interval
        purge_write: Purge write setting
        time_stepping: Time stepping settings from registry
        needs_windkessel: Whether Windkessel outlet is used
        cardiac_cycle: Cardiac cycle duration

    Returns:
        File content string
    """
    lines = [openfoam_header("dictionary", "controlDict")]

    # Windkessel library include
    if needs_windkessel:
        lines.extend([
            'libs ("libwindkesselBC.so");',
            "",
        ])

    # Main settings
    lines.extend([
        f"application     {cfg.solver_application};",
        f"solver          {cfg.solver_module};",
        "",
        "startFrom       startTime;",
        "startTime       0;",
        "stopAt          endTime;",
        f"endTime         {format_value(end_time)};",
        "",
        f"deltaT          1e-5;",
        f"writeControl    adjustableRunTime;",
        f"writeInterval   {format_value(write_interval)};",
        f"purgeWrite      {purge_write};",
        "",
        "writeFormat     binary;",
        "writePrecision  8;",
        "writeCompression off;",
        "timeFormat      general;",
        "timePrecision   8;",
        "",
        "runTimeModifiable yes;",
        f"adjustTimeStep  {format_value(time_stepping['adjustTimeStep'])};",
        f"maxCo           {format_value(time_stepping['maxCo'])};",
        f"maxDeltaT       {format_value(time_stepping['maxDeltaT'])};",
        "",
    ])

    # Function objects
    lines.extend(_generate_function_objects(cfg, cardiac_cycle))

    lines.append("// ************************************************************************* //")

    return "\n".join(lines)


def _generate_function_objects(
    cfg: Config,
    cardiac_cycle: Optional[float],
) -> list:
    """
    Generate function objects section.

    Args:
        cfg: Config accessor
        cardiac_cycle: Cardiac cycle duration

    Returns:
        List of lines for function objects
    """
    lines = [
        "functions",
        "{",
    ]

    # Wall shear stress
    lines.extend([
        "    wallShearStress",
        "    {",
        "        type            wallShearStress;",
        "        libs            (fieldFunctionObjects);",
        "        writeControl    writeTime;",
        "        patches         (wall);",
        "    }",
        "",
    ])

    # Field average (if cardiac cycle is known)
    if cardiac_cycle is not None and cardiac_cycle > 0:
        lines.extend([
            "    fieldAverage",
            "    {",
            "        type            fieldAverage;",
            "        libs            (fieldFunctionObjects);",
            "        writeControl    writeTime;",
            "        restartOnRestart false;",
            "        restartOnOutput false;",
            "",
            "        fields",
            "        (",
            "            U",
            "            {",
            "                mean        on;",
            "                prime2Mean  on;",
            "                base        time;",
            "            }",
            "            p",
            "            {",
            "                mean        on;",
            "                prime2Mean  off;",
            "                base        time;",
            "            }",
            "            wallShearStress",
            "            {",
            "                mean        on;",
            "                prime2Mean  off;",
            "                base        time;",
            "            }",
            "        );",
            "    }",
            "",
        ])

    lines.extend([
        "}",
        "",
    ])

    return lines
