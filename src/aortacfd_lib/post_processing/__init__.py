"""
AortaCFD Post-Processing Module
================================

Unified post-processing for OpenFOAM CFD simulations with:
- ParaView-based visualization (screenshots, animations)
- Hemodynamic metrics (TAWSS, OSI, RRT, pressure drop)
- CLI and configuration file support

Usage:
    # Python API
    from aortacfd_lib.post_processing import PostProcessor

    processor = PostProcessor(case_dir, config)
    processor.run_all()

    # Command-line
    python -m aortacfd_lib.post_processing --case /path/to/case --config config.json

    # ParaView-specific (requires pvbatch)
    pvbatch -m aortacfd_lib.post_processing.visualization /path/to/case

Author: AortaCFD Team
"""

from .config import PostProcessingConfig, load_config
from .dependencies import check_dependencies, DependencyStatus
from .core import PostProcessor
from .exceptions import (
    PostProcessingError,
    MissingFieldError,
    ParaViewError,
    ConfigurationError,
    CaseNotFoundError,
    DependencyError,
    HemodynamicsError,
)

# Re-export hemodynamics from existing module
from ..hemodynamics_postprocessor import HemodynamicsPostProcessor, HemodynamicsResults, run_hemodynamics_analysis

__all__ = [
    # Core
    "PostProcessor",
    "PostProcessingConfig",
    "load_config",
    # Dependencies
    "check_dependencies",
    "DependencyStatus",
    # Exceptions
    "PostProcessingError",
    "MissingFieldError",
    "ParaViewError",
    "ConfigurationError",
    "CaseNotFoundError",
    "DependencyError",
    "HemodynamicsError",
    # Hemodynamics (re-exported)
    "HemodynamicsPostProcessor",
    "HemodynamicsResults",
    "run_hemodynamics_analysis",
]
