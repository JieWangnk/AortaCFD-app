# src/workflow/steps.py
"""
Simplified workflow steps as functions.

This module replaces the Task class-based approach with simple functions.
Each function performs one step of the workflow and returns success/failure.

Usage:
    from src.workflow.steps import setup_case, generate_mesh_files

    success = setup_case(config, case_dir)
    success = generate_mesh_files(config, case_dir)

Design Philosophy:
- Functions, not classes (simpler to understand and test)
- Each function does ONE thing
- Clear inputs and outputs
- No hidden state
"""

import os
import shutil
import logging
from typing import Any, Dict, Optional, Tuple, Union

from stl import mesh as np_stl_mesh

from ..config.accessor import Config, wrap_config
from ..writers import (
    write_fv_schemes,
    write_fv_solution,
    write_control_dict,
    write_transport_properties,
    write_decompose_par_dict,
)
from ..writers.transport_properties import write_momentum_transport

logger = logging.getLogger(__name__)


# =============================================================================
# CASE SETUP STEPS
# =============================================================================

def create_case_structure(
    config: Union[Dict[str, Any], Config],
    case_dir: str,
    clean: bool = False,
) -> bool:
    """
    Create OpenFOAM case directory structure.

    Creates:
    - system/
    - constant/triSurface/
    - constant/boundaryData/{inlet}/
    - 0/
    - logs/

    Args:
        config: Configuration dict or Config accessor
        case_dir: Path to case directory
        clean: If True, remove existing case directory first

    Returns:
        True if successful
    """
    cfg = wrap_config(config)

    # Clean if requested
    if clean and os.path.exists(case_dir):
        logger.warning(f"Removing existing case directory: {case_dir}")
        shutil.rmtree(case_dir)

    logger.info(f"Creating case structure: {case_dir}")

    # Create directories
    os.makedirs(os.path.join(case_dir, "system"), exist_ok=True)
    os.makedirs(os.path.join(case_dir, "constant", "triSurface"), exist_ok=True)
    os.makedirs(os.path.join(case_dir, "0"), exist_ok=True)
    os.makedirs(os.path.join(case_dir, "logs"), exist_ok=True)

    # Create boundaryData directory for inlet
    inlet_name = cfg.inlet_patch_name
    if inlet_name:
        os.makedirs(
            os.path.join(case_dir, "constant", "boundaryData", inlet_name),
            exist_ok=True
        )

    return True


def copy_and_scale_geometry(
    config: Union[Dict[str, Any], Config],
    case_dir: str,
    source_dir: Optional[str] = None,
) -> bool:
    """
    Copy and scale STL files from source to case directory.

    This is the ONLY place scaling happens. STL files are scaled from
    input units (typically mm) to SI units (meters).

    Args:
        config: Configuration dict or Config accessor
        case_dir: Path to case directory
        source_dir: Source directory with STL files (default: cases_input/{case_name})

    Returns:
        True if successful
    """
    cfg = wrap_config(config)

    # Determine source directory
    if source_dir is None:
        source_dir = os.path.join("cases_input", cfg.case_name)

    if not os.path.isdir(source_dir):
        logger.error(f"Source directory not found: {source_dir}")
        return False

    # Get scale factor
    scale_factor = cfg.scale_factor
    logger.info(f"Scaling STL files with factor {scale_factor} (mm -> m)")

    # Destination directory
    tri_surface_dir = os.path.join(case_dir, "constant", "triSurface")
    os.makedirs(tri_surface_dir, exist_ok=True)

    # Process STL files
    stl_files = [f for f in os.listdir(source_dir) if f.lower().endswith('.stl')]

    if not stl_files:
        logger.warning(f"No STL files found in {source_dir}")
        return False

    for stl_file in stl_files:
        src_path = os.path.join(source_dir, stl_file)
        dst_path = os.path.join(tri_surface_dir, stl_file)

        try:
            _scale_stl_file(src_path, dst_path, scale_factor)
            logger.debug(f"Scaled: {stl_file}")
        except Exception as e:
            logger.error(f"Failed to scale {stl_file}: {e}")
            return False

    logger.info(f"Scaled {len(stl_files)} STL files to {tri_surface_dir}")
    return True


def _scale_stl_file(src_path: str, dst_path: str, scale_factor: float) -> None:
    """
    Scale an STL file and save to destination.

    Args:
        src_path: Source STL file path
        dst_path: Destination STL file path
        scale_factor: Scale factor to apply
    """
    stl_mesh = np_stl_mesh.Mesh.from_file(src_path)
    stl_mesh.vectors *= scale_factor
    stl_mesh.update_normals()
    stl_mesh.save(dst_path)


# =============================================================================
# DICTIONARY GENERATION STEPS
# =============================================================================

def generate_all_dicts(
    config: Union[Dict[str, Any], Config],
    case_dir: str,
    cardiac_cycle: Optional[float] = None,
) -> bool:
    """
    Generate all OpenFOAM dictionary files.

    Generates:
    - system/fvSchemes
    - system/fvSolution
    - system/controlDict
    - system/decomposeParDict
    - constant/transportProperties
    - constant/momentumTransport

    Args:
        config: Configuration dict or Config accessor
        case_dir: Path to case directory
        cardiac_cycle: Cardiac cycle duration (for controlDict)

    Returns:
        True if successful
    """
    cfg = wrap_config(config)
    profile = cfg.profile

    logger.info(f"Generating dictionaries with '{profile}' profile")

    try:
        # System dictionaries
        write_fv_schemes(cfg, case_dir)
        write_fv_solution(cfg, case_dir)
        write_control_dict(cfg, case_dir, cardiac_cycle=cardiac_cycle)
        write_decompose_par_dict(cfg, case_dir)

        # Constant dictionaries
        write_transport_properties(cfg, case_dir)
        write_momentum_transport(cfg, case_dir)

        logger.info("All dictionaries generated successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to generate dictionaries: {e}")
        return False


def generate_fv_schemes_step(
    config: Union[Dict[str, Any], Config],
    case_dir: str,
) -> bool:
    """Generate fvSchemes file."""
    try:
        write_fv_schemes(config, case_dir)
        return True
    except Exception as e:
        logger.error(f"Failed to generate fvSchemes: {e}")
        return False


def generate_fv_solution_step(
    config: Union[Dict[str, Any], Config],
    case_dir: str,
) -> bool:
    """Generate fvSolution file."""
    try:
        write_fv_solution(config, case_dir)
        return True
    except Exception as e:
        logger.error(f"Failed to generate fvSolution: {e}")
        return False


def generate_control_dict_step(
    config: Union[Dict[str, Any], Config],
    case_dir: str,
    cardiac_cycle: Optional[float] = None,
) -> bool:
    """Generate controlDict file."""
    try:
        write_control_dict(config, case_dir, cardiac_cycle=cardiac_cycle)
        return True
    except Exception as e:
        logger.error(f"Failed to generate controlDict: {e}")
        return False


def generate_transport_properties_step(
    config: Union[Dict[str, Any], Config],
    case_dir: str,
) -> bool:
    """Generate transportProperties and momentumTransport files."""
    try:
        write_transport_properties(config, case_dir)
        write_momentum_transport(config, case_dir)
        return True
    except Exception as e:
        logger.error(f"Failed to generate transport properties: {e}")
        return False


def generate_decompose_par_dict_step(
    config: Union[Dict[str, Any], Config],
    case_dir: str,
) -> bool:
    """Generate decomposeParDict file."""
    try:
        write_decompose_par_dict(config, case_dir)
        return True
    except Exception as e:
        logger.error(f"Failed to generate decomposeParDict: {e}")
        return False


# =============================================================================
# VALIDATION STEPS
# =============================================================================

def validate_geometry(
    config: Union[Dict[str, Any], Config],
    source_dir: Optional[str] = None,
) -> Tuple[bool, list]:
    """
    Validate geometry files before processing.

    Args:
        config: Configuration dict or Config accessor
        source_dir: Source directory with STL files

    Returns:
        Tuple of (is_valid, list of warnings/errors)
    """
    cfg = wrap_config(config)

    if source_dir is None:
        source_dir = os.path.join("cases_input", cfg.case_name)

    messages = []

    if not os.path.isdir(source_dir):
        return False, [f"Source directory not found: {source_dir}"]

    stl_files = [f for f in os.listdir(source_dir) if f.lower().endswith('.stl')]

    if not stl_files:
        return False, [f"No STL files found in {source_dir}"]

    # Check for required patches
    has_inlet = any('inlet' in f.lower() for f in stl_files)
    has_outlet = any('outlet' in f.lower() for f in stl_files)
    has_wall = any('wall' in f.lower() for f in stl_files)

    if not has_inlet:
        messages.append("Warning: No inlet STL file found (expected *inlet*.stl)")
    if not has_outlet:
        messages.append("Warning: No outlet STL file found (expected *outlet*.stl)")
    if not has_wall:
        messages.append("Warning: No wall STL file found (expected *wall*.stl)")

    # Basic STL validation
    for stl_file in stl_files:
        try:
            stl_path = os.path.join(source_dir, stl_file)
            mesh = np_stl_mesh.Mesh.from_file(stl_path)

            if len(mesh.vectors) == 0:
                messages.append(f"Error: {stl_file} has no triangles")
                return False, messages

        except Exception as e:
            messages.append(f"Error: Failed to read {stl_file}: {e}")
            return False, messages

    is_valid = not any(m.startswith("Error:") for m in messages)
    return is_valid, messages


# =============================================================================
# SIMPLE WORKFLOW RUNNER
# =============================================================================

def run_setup_workflow(
    config: Union[Dict[str, Any], Config],
    case_dir: str,
    source_dir: Optional[str] = None,
    clean: bool = False,
    cardiac_cycle: Optional[float] = None,
) -> bool:
    """
    Run the complete setup workflow.

    Steps:
    1. Validate geometry
    2. Create case structure
    3. Copy and scale geometry
    4. Generate all dictionaries

    Args:
        config: Configuration dict or Config accessor
        case_dir: Path to case directory
        source_dir: Source directory with STL files
        clean: If True, remove existing case directory
        cardiac_cycle: Cardiac cycle duration

    Returns:
        True if all steps successful
    """
    cfg = wrap_config(config)

    logger.info("=" * 60)
    logger.info("Starting setup workflow")
    logger.info("=" * 60)

    # Step 1: Validate geometry
    logger.info("Step 1: Validating geometry...")
    is_valid, messages = validate_geometry(cfg, source_dir)
    for msg in messages:
        if msg.startswith("Error:"):
            logger.error(msg)
        else:
            logger.warning(msg)

    if not is_valid:
        logger.error("Geometry validation failed")
        return False

    # Step 2: Create case structure
    logger.info("Step 2: Creating case structure...")
    if not create_case_structure(cfg, case_dir, clean=clean):
        return False

    # Step 3: Copy and scale geometry
    logger.info("Step 3: Copying and scaling geometry...")
    if not copy_and_scale_geometry(cfg, case_dir, source_dir):
        return False

    # Step 4: Generate dictionaries
    logger.info("Step 4: Generating dictionaries...")
    if not generate_all_dicts(cfg, case_dir, cardiac_cycle=cardiac_cycle):
        return False

    logger.info("=" * 60)
    logger.info("Setup workflow completed successfully")
    logger.info("=" * 60)

    return True
