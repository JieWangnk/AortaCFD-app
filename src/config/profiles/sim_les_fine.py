"""Fragment-driven fine LES profile assembling high-resolution fragments.

This profile composes the fine spatial-resolution fragment with the aggressive
solver recipe and WALE turbulence fragment to deliver publication-grade LES
settings for arterial flow simulations.
"""

from __future__ import annotations

from .profile_builder import ProfileComposer

composer = ProfileComposer()

LES_FINE_EXTRAS = {
    "run_settings": {
        "solution_type": "parallel",
        "subdomains": 10,
        "decomposition_method": "scotch",
    },
    "mesh": {
        "automatic_refinement": {
            "enabled": True,
            "methodology": "murray_law_based",
        },
        "cells_per_patch_diameter": {
            "coarse": 16,
            "medium": 22,
            "fine": 30,
        },
    },
    "simulation_control": {
        "controlDict": {
            "application": "pimpleFoam",
            "startFrom": "startTime",
            "startTime": 0.0,
            "stopAt": "endTime",
            "endTime": "auto",
            "deltaT": 2e-06,
            "writeControl": "adjustableRunTime",
            "writeInterval": 0.0025,
            "runTimeModifiable": "true",
            "adjustTimeStep": "yes",
            "maxCo": 0.5,
            "maxDeltaT": 5e-05,
            "functions": ["wallShearStress", "Q", "Lambda2"],
        }
    },
    "boundary": {
        "BC_INLET": "TIMEVARYING",
        "BC_OUTLET": "3EWINDKESSEL",
        "INLET_DATA_TYPE": "velocity",
        "INLET_PROFILE": "womersley",
        "INLET_ORIENTATION": "out",
        "WK_SETTING": {
            "percentage": 25,
            "systolic_pressure": 120,
            "diastolic_pressure": 80,
            "use_murray_law": True,
        },
    },
}

config = composer.compose(
    spatial_resolution="fine",
    solver_recipe="aggressive",
    turbulence_model="les_wale",
    extras=LES_FINE_EXTRAS,
)
