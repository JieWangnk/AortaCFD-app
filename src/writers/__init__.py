# src/writers/__init__.py
"""
Simplified OpenFOAM file writers.

This module provides simple functions for writing OpenFOAM dictionary files.
Each function takes a config and case directory, and writes the appropriate file.

Usage:
    from src.writers import write_fv_schemes, write_fv_solution

    write_fv_schemes(config, case_dir)
    write_fv_solution(config, case_dir)

Design Philosophy:
- Functions, not classes (simpler to understand and test)
- Each function writes ONE file
- Uses registry for numerical settings
- Uses Config accessor for clean config access
"""

from .fv_schemes import write_fv_schemes
from .fv_solution import write_fv_solution
from .control_dict import write_control_dict
from .transport_properties import write_transport_properties
from .decompose_par_dict import write_decompose_par_dict
from .header import openfoam_header

__all__ = [
    'write_fv_schemes',
    'write_fv_solution',
    'write_control_dict',
    'write_transport_properties',
    'write_decompose_par_dict',
    'openfoam_header',
]
