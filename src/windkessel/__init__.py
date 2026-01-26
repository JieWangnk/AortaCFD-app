# src/windkessel/__init__.py
"""
Windkessel outlet boundary condition package.

This package handles:
- Windkessel circuit parameter calculations
- Murray's law flow splitting
- Windkessel properties file generation

Windkessel Models:
- 2-Element (R-C): Simple resistance-compliance model
- 3-Element (R-C-R): Includes proximal resistance for wave reflection

Usage:
    from src.windkessel import calculate_windkessel_params, write_windkessel_properties

    # Calculate parameters for all outlets
    params = calculate_windkessel_params(config, outlet_areas)

    # Write properties file
    write_windkessel_properties(params, case_dir)

Design Philosophy:
- Split complex wk_setup.py (50KB) into focused modules
- Separate physics (circuit.py) from file I/O (writer.py)
- Clear data flow between components
"""

from .circuit import (
    WindkesselParams,
    calculate_2element_params,
    calculate_3element_params,
    calculate_total_resistance,
    calculate_compliance,
)

from .murray import (
    calculate_murray_flow_split,
    area_to_diameter,
    diameter_to_area,
)

from .writer import (
    write_windkessel_properties,
    WindkesselConfig,
)

__all__ = [
    # Circuit
    'WindkesselParams',
    'calculate_2element_params',
    'calculate_3element_params',
    'calculate_total_resistance',
    'calculate_compliance',
    # Murray's law
    'calculate_murray_flow_split',
    'area_to_diameter',
    'diameter_to_area',
    # Writer
    'write_windkessel_properties',
    'WindkesselConfig',
]
