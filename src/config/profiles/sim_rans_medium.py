"""Fragment-driven medium RANS profile composed from reusable fragments.

This profile combines the medium spatial-resolution fragment with the balanced
solver recipe and high-intensity RANS turbulence fragment for clinical-grade
turbulent simulations.
"""

from __future__ import annotations

from .profile_builder import ProfileComposer

composer = ProfileComposer()

RANS_MEDIUM_EXTRAS = {
    "run_settings": {
        "solution_type": "parallel",
        "subdomains": 4,
        "decomposition_method": "scotch",
        "skip_reconstruction": True,  # Skip blocking reconstruction for faster workflow
    },
    "mesh": {
        "automatic_refinement": {
            "enabled": True,
            "methodology": "murray_law_based",
        },
        "cells_per_patch_diameter": {
            "coarse": 12,
            "medium": 16,
            "fine": 22,
        },
    },
    "simulation_control": {
        "controlDict": {
            "application": "pimpleFoam",
            "startFrom": "startTime",
            "startTime": 0.0,
            "stopAt": "endTime",
            "endTime": "auto",
            "deltaT": 1e-05,
            "writeControl": "adjustableRunTime",
            "writeInterval": 0.01,
            "runTimeModifiable": "true",
            "adjustTimeStep": "yes",
            "maxCo": 0.5,
            "maxDeltaT": 2e-04,
            "functions": ["wallShearStress", "Q"],
        }
    },
    "boundary": {
        "BC_INLET": "TIMEVARYING",
        "BC_OUTLET": "ZEROGRADIENT",
        "INLET_DATA_TYPE": "velocity",
        "INLET_PROFILE": "womersley",
        "INLET_ORIENTATION": "out",
    },
}

config = composer.compose(
    spatial_resolution="medium",
    solver_recipe="robust",  # Robust recipe provides strong stability for all RANS cases
    turbulence_model="rans_high_intensity",
    extras=RANS_MEDIUM_EXTRAS,
)
