"""Fragment-driven fine RANS profile for high-fidelity turbulence studies.

This profile assembles the fine spatial-resolution fragment with the balanced
solver recipe and k-omega SST turbulence fragment suitable for research and
publication-grade studies.
"""

from __future__ import annotations

from .profile_builder import ProfileComposer

composer = ProfileComposer()

RANS_FINE_EXTRAS = {
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
            "fine": 28,
        },
    },
    "simulation_control": {
        "controlDict": {
            "application": "pimpleFoam",
            "startFrom": "startTime",
            "startTime": 0.0,
            "stopAt": "endTime",
            "endTime": "auto",
            "deltaT": 2e-05,
            "writeControl": "adjustableRunTime",
            "writeInterval": 0.005,
            "runTimeModifiable": "true",
            "adjustTimeStep": "yes",
            "maxCo": 0.6,
            "maxDeltaT": 3e-04,
            "functions": ["wallShearStress", "pressureDrop"],
        }
    },
    "fvSolution": {
        "relaxationFactors": {
            "fields": {"p": 0.25},
            "equations": {"U": 0.55, "k": 0.55, "omega": 0.55, "epsilon": 0.55}
        },
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
    solver_recipe="robust",  # Robust recipe for RANS stability
    turbulence_model="rans_komega_sst",
    extras=RANS_FINE_EXTRAS,
)
