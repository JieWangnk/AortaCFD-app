"""
AortaCFD: Patient-Specific Aortic Blood Flow Simulation
======================================================

A comprehensive CFD simulation package for patient-specific aortic analysis.
"""

__version__ = "1.2.0"
__author__ = "AortaCFD Development Team"

# Expose main components for easier imports
from .config.builder import ConfigBuilder
from .workflow.manager import WorkflowManager
from .aortacfd_lib.utils.logger import Logger

__all__ = [
    'ConfigBuilder',
    'WorkflowManager', 
    'Logger',
    '__version__',
    '__author__'
]