"""Composable coarse laminar profile built from fragments.

This profile composes the coarse spatial resolution fragment with the
robust solver recipe and laminar turbulence fragment for draft-quality runs.
"""

from __future__ import annotations

from .profile_builder import ProfileComposer

composer = ProfileComposer()

LAMINAR_COARSE_EXTRAS = {
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
            "coarse": 6,
            "medium": 8,
            "fine": 10,
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
            "maxCo": 0.5,
            "maxDeltaT": 1e-3,
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
    spatial_resolution="coarse",
    solver_recipe="robust",
    turbulence_model="laminar",
    extras=LAMINAR_COARSE_EXTRAS,
)