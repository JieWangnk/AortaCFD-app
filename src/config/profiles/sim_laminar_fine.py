"""Composable fine laminar profile built from fragments.

This profile assembles the fine spatial-resolution fragment with the balanced
solver recipe and laminar turbulence fragment for research-grade studies.
"""

from __future__ import annotations

from .profile_builder import ProfileComposer

composer = ProfileComposer()

LAMINAR_FINE_EXTRAS = {
    "run_settings": {
        "solution_type": "parallel",
        "subdomains": 4,
        "decomposition_method": "scotch",
    },
    "mesh": {
        "automatic_refinement": {
            "enabled": True,
            "methodology": "murray_law_based",
        },
        "cells_per_patch_diameter": {
            "coarse": 12,
            "medium": 18,
            "fine": 25,
        },
    },
    "simulation_control": {
        "controlDict": {
            "application": "pimpleFoam",
            "startFrom": "startTime",
            "startTime": 0.0,
            "stopAt": "endTime",
            "endTime": "auto",
            "deltaT": 1e-5,
            "writeControl": "adjustableRunTime",
            "writeInterval": 0.01,
            "runTimeModifiable": "true",
            "adjustTimeStep": "yes",
            "maxCo": 1.0,
            "maxDeltaT": 1e-4,
            "functions": ["wallShearStress"],
        }
    },
    "boundary": {
        "BC_INLET": "TIMEVARYING",
        "BC_OUTLET": "3EWINDKESSEL",
        "INLET_DATA_TYPE": "velocity",
        "INLET_PROFILE": "womersley",
        "INLET_ORIENTATION": "out",
        "WK_SETTING": {
            "percentage": 30,
            "systolic_pressure": 120,
            "diastolic_pressure": 80,
            "use_murray_law": True,
        },
    },
}

config = composer.compose(
    spatial_resolution="fine",
    solver_recipe="balanced",
    turbulence_model="laminar",
    extras=LAMINAR_FINE_EXTRAS,
)