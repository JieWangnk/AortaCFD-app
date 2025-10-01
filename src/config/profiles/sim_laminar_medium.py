"""Composable medium laminar profile built from fragments.

This profile pairs the medium spatial-resolution fragment with the balanced
solver recipe and laminar turbulence fragment for routine clinical runs.
"""

from __future__ import annotations

from .profile_builder import ProfileComposer

composer = ProfileComposer()

LAMINAR_MEDIUM_EXTRAS = {
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
            "coarse": 10,
            "medium": 14,
            "fine": 18,
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
            "maxDeltaT": 2e-4,
            "minDeltaT": 1e-7,
            "functions": ["wallShearStress"],
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
    solver_recipe="balanced",
    turbulence_model="laminar",
    extras=LAMINAR_MEDIUM_EXTRAS,
)