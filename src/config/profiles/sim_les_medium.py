"""Fragment-driven medium LES profile leveraging reusable fragments.

This profile composes the medium spatial-resolution fragment with the balanced
solver recipe and WALE turbulence fragment for transitional studies requiring
finer turbulence resolution.
"""

from __future__ import annotations

from .profile_builder import ProfileComposer

composer = ProfileComposer()

LES_MEDIUM_EXTRAS = {
    "run_settings": {
        "solution_type": "parallel",
        "subdomains": 6,
        "decomposition_method": "scotch",
    },
    "mesh": {
        "automatic_refinement": {
            "enabled": True,
            "methodology": "murray_law_based",
        },
        "cells_per_patch_diameter": {
            "coarse": 14,
            "medium": 20,
            "fine": 26,
        },
    },
    "simulation_control": {
        "controlDict": {
            "application": "pimpleFoam",
            "startFrom": "startTime",
            "startTime": 0.0,
            "stopAt": "endTime",
            "endTime": "auto",
            "deltaT": 5e-06,
            "writeControl": "adjustableRunTime",
            "writeInterval": 0.005,
            "runTimeModifiable": "true",
            "adjustTimeStep": "yes",
            "maxCo": 0.5,
            "maxDeltaT": 1e-04,
            "functions": ["wallShearStress", "Q"],
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
    spatial_resolution="medium",
    solver_recipe="balanced",
    turbulence_model="les_wale",
    extras=LES_MEDIUM_EXTRAS,
)
