# src/workflow/simple_runner.py
"""
Simplified workflow runner using the new architecture.

This module provides a clean, function-based interface to run
CFD simulations without complex class hierarchies.

Usage:
    from src.workflow.simple_runner import run_simulation, run_setup

    # Run complete setup
    run_setup(config_path='cases_input/PAT001/config.json')

    # Run with specific steps
    run_simulation(
        config_path='cases_input/PAT001/config.json',
        steps=['setup', 'mesh', 'solve'],
    )

Design Philosophy:
- Simple function calls, not class instantiation
- Clear step-by-step execution
- Easy to understand and modify
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional, Union

from ..config.accessor import Config, wrap_config
from ..config.generator import generate_config
from ..registry.numerics import get_numerics
from ..writers import (
    write_fv_schemes,
    write_fv_solution,
    write_control_dict,
    write_transport_properties,
    write_decompose_par_dict,
)
from ..writers.transport_properties import write_momentum_transport
from .steps import (
    create_case_structure,
    copy_and_scale_geometry,
    validate_geometry,
)

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> Config:
    """
    Load configuration from JSON file.

    Args:
        config_path: Path to config.json

    Returns:
        Config accessor
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, 'r') as f:
        raw_config = json.load(f)

    # Store config path for reference
    raw_config['_config_file_path'] = config_path

    return Config(raw_config)


def run_setup(
    config_path: str,
    output_dir: Optional[str] = None,
    clean: bool = False,
) -> str:
    """
    Run the setup phase (create case structure and dictionaries).

    Steps:
    1. Load and validate config
    2. Create case directory structure
    3. Copy and scale STL files
    4. Generate all dictionary files

    Args:
        config_path: Path to config.json
        output_dir: Output directory (default: output/{case_name}/openfoam)
        clean: If True, remove existing output directory

    Returns:
        Path to case directory
    """
    logger.info("=" * 60)
    logger.info("SETUP PHASE")
    logger.info("=" * 60)

    # Load config
    cfg = load_config(config_path)
    case_name = cfg.case_name
    profile = cfg.profile

    logger.info(f"Case: {case_name}")
    logger.info(f"Profile: {profile}")

    # Determine output directory
    if output_dir is None:
        output_dir = os.path.join("output", case_name, "openfoam")

    # Get source directory (where STLs and config are)
    source_dir = os.path.dirname(config_path)

    # Step 1: Validate geometry
    logger.info("Step 1: Validating geometry...")
    is_valid, messages = validate_geometry(cfg, source_dir)
    for msg in messages:
        logger.info(f"  {msg}")
    if not is_valid:
        raise ValueError("Geometry validation failed")

    # Step 2: Create case structure
    logger.info(f"Step 2: Creating case structure in {output_dir}...")
    create_case_structure(cfg, output_dir, clean=clean)

    # Step 3: Copy and scale geometry
    logger.info("Step 3: Copying and scaling STL files...")
    copy_and_scale_geometry(cfg, output_dir, source_dir)

    # Step 4: Generate dictionary files
    logger.info("Step 4: Generating dictionary files...")
    write_fv_schemes(cfg, output_dir)
    write_fv_solution(cfg, output_dir)
    write_control_dict(cfg, output_dir)
    write_decompose_par_dict(cfg, output_dir)
    write_transport_properties(cfg, output_dir)
    write_momentum_transport(cfg, output_dir)

    logger.info("=" * 60)
    logger.info(f"Setup complete: {output_dir}")
    logger.info("=" * 60)

    return output_dir


def run_with_profile(
    case_name: str,
    profile: str = 'standard',
    source_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
    clean: bool = False,
) -> str:
    """
    Run setup using a profile without requiring a config file.

    This generates a config from the profile and runs setup.
    Useful for quick tests or when you want default settings.

    Args:
        case_name: Case name (must match directory in cases_input/)
        profile: Numerical profile (robust, standard, precise)
        source_dir: Source directory with STLs (default: cases_input/{case_name})
        output_dir: Output directory (default: output/{case_name}/openfoam)
        clean: If True, remove existing output directory

    Returns:
        Path to case directory
    """
    logger.info(f"Running with profile: {profile}")

    # Generate config from profile
    config_dict = generate_config(profile, case_name, include_comments=False)
    cfg = Config(config_dict)

    # Determine directories
    if source_dir is None:
        source_dir = os.path.join("cases_input", case_name)
    if output_dir is None:
        output_dir = os.path.join("output", case_name, "openfoam")

    # Run setup steps
    logger.info("Step 1: Validating geometry...")
    is_valid, messages = validate_geometry(cfg, source_dir)
    if not is_valid:
        raise ValueError("Geometry validation failed")

    logger.info("Step 2: Creating case structure...")
    create_case_structure(cfg, output_dir, clean=clean)

    logger.info("Step 3: Copying and scaling STL files...")
    copy_and_scale_geometry(cfg, output_dir, source_dir)

    logger.info("Step 4: Generating dictionary files...")
    write_fv_schemes(cfg, output_dir)
    write_fv_solution(cfg, output_dir)
    write_control_dict(cfg, output_dir)
    write_decompose_par_dict(cfg, output_dir)
    write_transport_properties(cfg, output_dir)
    write_momentum_transport(cfg, output_dir)

    logger.info(f"Setup complete: {output_dir}")
    return output_dir


def show_config_summary(config_path: str) -> None:
    """
    Display a summary of the configuration.

    Args:
        config_path: Path to config.json
    """
    cfg = load_config(config_path)

    print("\n" + "=" * 60)
    print("CONFIGURATION SUMMARY")
    print("=" * 60)
    print(f"Case Name:     {cfg.case_name}")
    print(f"Profile:       {cfg.profile}")
    print(f"Simulation:    {cfg.simulation_type}")
    print(f"Inlet Type:    {cfg.inlet_type}")
    print(f"Outlet Type:   {cfg.outlet_type}")
    print(f"Subdomains:    {cfg.subdomains}")
    print(f"Num Cycles:    {cfg.num_cycles}")
    print("=" * 60 + "\n")


def compare_profiles() -> None:
    """
    Display a comparison of available numerical profiles.
    """
    from ..registry.numerics import list_profiles, get_schemes, get_pimple_settings

    print("\n" + "=" * 70)
    print("NUMERICAL PROFILE COMPARISON")
    print("=" * 70)
    print(f"{'Setting':<30} {'robust':<15} {'standard':<15} {'precise':<15}")
    print("-" * 70)

    for profile in list_profiles():
        schemes = get_schemes(profile)
        pimple = get_pimple_settings(profile)

    # Time discretization
    print(f"{'Time (ddt)':<30}", end="")
    for profile in list_profiles():
        schemes = get_schemes(profile)
        print(f"{schemes['ddt']:<15}", end="")
    print()

    # Convection scheme
    print(f"{'Convection (div U)':<30}", end="")
    for profile in list_profiles():
        schemes = get_schemes(profile)
        scheme = schemes['div_phi_U'].replace('Gauss ', '')
        print(f"{scheme:<15}", end="")
    print()

    # Outer correctors
    print(f"{'nOuterCorrectors':<30}", end="")
    for profile in list_profiles():
        pimple = get_pimple_settings(profile)
        print(f"{pimple['nOuterCorrectors']:<15}", end="")
    print()

    print("=" * 70)
    print("\nRecommendations:")
    print("  robust:   Problematic meshes, debugging, initial runs")
    print("  standard: Production runs, clinical studies (RECOMMENDED)")
    print("  precise:  Validation, excellent mesh, LES")
    print()
