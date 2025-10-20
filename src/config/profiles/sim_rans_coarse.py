"""Fragment-driven coarse RANS profile using solver recipes and turbulence fragments.

This profile composes the coarse spatial-resolution fragment with the robust
solver recipe and k-omega SST turbulence fragment for quick stability checks.
"""

from __future__ import annotations

from .profile_builder import ProfileComposer

composer = ProfileComposer()

RANS_COARSE_EXTRAS = {
    "run_settings": {
        "solution_type": "serial",
        "subdomains": 1,
        "decomposition_method": "scotch",
    },
    "mesh": {
        "automatic_refinement": {
            "enabled": True,
            "methodology": "murray_law_based",
        },
        "cells_per_patch_diameter": {
            "coarse": 8,
            "medium": 12,
            "fine": 16,
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
            "maxCo": 0.6,
            "maxDeltaT": 3e-04,
            "functions": ["wallShearStress"],
        }
    },
    "fvSolution": {
        "PIMPLE": {
            "nOuterCorrectors": 2,
            "nCorrectors": 2,
        },
        "relaxationFactors": {
            "fields": {"p": 0.25},
            "equations": {"U": 0.6, "k": 0.6, "omega": 0.6, "epsilon": 0.6}
        },
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
    turbulence_model="rans_komega_sst",
    extras=RANS_COARSE_EXTRAS,
)