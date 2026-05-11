"""
Import resolver for AortaCFD modules.

Handles imports that need to work both as relative imports (when running as package)
and absolute imports (when running standalone or testing).

Usage:
    from utils.imports import (
        Task, logger,
        run_command, CommandExecutionError,
        GeometryValidator, BoundaryConditionValidator,
        # ... other imports
    )

This eliminates the need for try/except import blocks in each module.
"""

import sys
from pathlib import Path

# Ensure src is in path for absolute imports
_src_path = str(Path(__file__).parent.parent)
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)


def _try_import(relative_path: str, absolute_path: str, names: list):
    """
    Try relative import first, fall back to absolute import.

    Args:
        relative_path: Relative import path (e.g., '..base_task')
        absolute_path: Absolute import path (e.g., 'workflow.base_task')
        names: List of names to import

    Returns:
        dict: Mapping of name -> imported object
    """
    import importlib

    try:
        # Try relative import (works when running as package)
        module = importlib.import_module(relative_path, package=__name__)
    except ImportError:
        # Fall back to absolute import (works standalone)
        module = importlib.import_module(absolute_path)

    return {name: getattr(module, name) for name in names}


# =============================================================================
# Workflow imports
# =============================================================================

try:
    from workflow.base_task import Task, logger
except ImportError:
    from ..workflow.base_task import Task, logger

# =============================================================================
# AortaCFD lib - Utils
# =============================================================================

try:
    from aortacfd_lib.utils.runner import run_command, CommandExecutionError
    from aortacfd_lib.utils.validation import GeometryValidator, BoundaryConditionValidator
    from aortacfd_lib.utils.patch_utils import detect_world_patch_mode
    from aortacfd_lib.utils.format_points import EnhancedPointsFormatter
    from aortacfd_lib.utils.logger import Logger
except ImportError:
    from ..aortacfd_lib.utils.runner import run_command, CommandExecutionError
    from ..aortacfd_lib.utils.validation import GeometryValidator, BoundaryConditionValidator
    from ..aortacfd_lib.utils.patch_utils import detect_world_patch_mode
    from ..aortacfd_lib.utils.format_points import EnhancedPointsFormatter
    from ..aortacfd_lib.utils.logger import Logger

# =============================================================================
# AortaCFD lib - Core modules
# =============================================================================

try:
    from aortacfd_lib.mesh_setup import GeometryAnalyzer
    from aortacfd_lib.boundary_condition_setup import BoundaryConditionSetup
    from aortacfd_lib.physical_properties_setup import PhysicalPropertiesWriter
    from aortacfd_lib.numerical_setup import FvSchemesWriter
    from aortacfd_lib.solver_setup import FvSolutionWriter
    from aortacfd_lib.simulation_control import SimulationSetup
    from aortacfd_lib.decompose_setup import SolnType
    from aortacfd_lib.inlet_mapping import InletMapping
    from aortacfd_lib.cycle_data_setup import CycleDataSetup
    from aortacfd_lib.wk_setup import WkSetup
    from aortacfd_lib.simulation_report_generator import SimulationReportGenerator
    from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile
except ImportError:
    from ..aortacfd_lib.mesh_setup import GeometryAnalyzer
    from ..aortacfd_lib.boundary_condition_setup import BoundaryConditionSetup
    from ..aortacfd_lib.physical_properties_setup import PhysicalPropertiesWriter
    from ..aortacfd_lib.numerical_setup import FvSchemesWriter
    from ..aortacfd_lib.solver_setup import FvSolutionWriter
    from ..aortacfd_lib.simulation_control import SimulationSetup
    from ..aortacfd_lib.decompose_setup import SolnType
    from ..aortacfd_lib.inlet_mapping import InletMapping
    from ..aortacfd_lib.cycle_data_setup import CycleDataSetup
    from ..aortacfd_lib.wk_setup import WkSetup
    from ..aortacfd_lib.simulation_report_generator import SimulationReportGenerator
    from ..aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

# =============================================================================
# Export all imports
# =============================================================================

__all__ = [
    # Workflow
    "Task",
    "logger",
    # Utils
    "run_command",
    "CommandExecutionError",
    "GeometryValidator",
    "BoundaryConditionValidator",
    "detect_world_patch_mode",
    "EnhancedPointsFormatter",
    "Logger",
    # Core modules
    "GeometryAnalyzer",
    "BoundaryConditionSetup",
    "PhysicalPropertiesWriter",
    "FvSchemesWriter",
    "FvSolutionWriter",
    "SimulationSetup",
    "SolnType",
    "InletMapping",
    "CycleDataSetup",
    "WkSetup",
    "SimulationReportGenerator",
    "DistanceWallInletProfile",
]
