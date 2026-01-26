# src/inlet/__init__.py
"""
Inlet boundary condition processing package.

This package handles:
- Velocity profile calculations (plug, parabolic, Womersley)
- CSV file parsing for flow waveforms
- Mapping velocity data to mesh points
- Writing OpenFOAM boundaryData files

Usage:
    from src.inlet import process_inlet, VelocityProfile

    # Process inlet CSV and write boundaryData
    cardiac_cycle = process_inlet(config, case_dir)

    # Calculate velocity profile at a point
    profile = VelocityProfile('parabolic', center, radius, normal)
    velocity = profile.calculate(point, mean_velocity)

Design Philosophy:
- Split complex inlet_mapping.py into focused modules
- Each module has single responsibility
- Clear data flow between components
"""

from .profiles import (
    VelocityProfile,
    PlugProfile,
    ParabolicProfile,
    WomersleyProfile,
    create_profile,
)

from .csv_reader import (
    read_flow_csv,
    FlowData,
    interpolate_flow,
)

from .mapping import (
    InletMapper,
    process_inlet,
    write_boundary_data,
)

__all__ = [
    # Profiles
    'VelocityProfile',
    'PlugProfile',
    'ParabolicProfile',
    'WomersleyProfile',
    'create_profile',
    # CSV
    'read_flow_csv',
    'FlowData',
    'interpolate_flow',
    # Mapping
    'InletMapper',
    'process_inlet',
    'write_boundary_data',
]
