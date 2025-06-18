# CONFIG/profiles/sim_laminar_medium.py
"""
Simulation profile for a medium-fidelity LAMINAR simulation.
This file defines the numerics, solver settings, and simulation controls.
"""

CONFIG = {
    # Choice of physics model
    "physics": {
        "simulation_type": "laminar", #
        "outter_correction_loop": 100 #
    },

    # Settings for the fvSolution dictionary (example for medium fidelity)
    "fvSolution": {
        "solvers": {
            "p": {"solver": "GAMG", "tolerance": 1e-6, "relTol": 0.1},
            "U": {"solver": "PBiCGStab", "preconditioner": "DILU", "tolerance": 1e-6, "relTol": 0.1}
        },
        "PIMPLE": {
            "nOuterCorrectors": 100, # This can be linked to outter_correction_loop
            "nCorrectors": 2,
            "nNonOrthogonalCorrectors": 1
        }
        # ... other fvSolution settings ...
    },

    # Settings for the fvSchemes dictionary (example for medium fidelity)
    "fvSchemes": {
        "ddtSchemes": {"default": "backward"},
        "gradSchemes": {"default": "cellLimited Gauss linear 0.5"},
        "divSchemes": {"div(phi,U)": "Gauss linear"},
        # ... other fvSchemes settings ...
    },

    # --- Simulation Control Settings ---
    "simulation_control": {
        "controlDict": {
            "application": "pimpleFoam", # This should be set here, not hardcoded
            "startFrom": "startTime", #
            "startTime": 0.0, #
            "stopAt": "endTime", #
            "endTime": "auto",  # Special keyword for dynamic calculation
            "deltaT": 1e-6, #
            "writeControl": "timeStep", #
            "writeInterval": 1, #
            "purgeWrite": 0,
            "writeFormat": "binary",
            "writeCompression": "off",
            "timeFormat": "general",
            "timePrecision": 6,
            "runTimeModifiable": "true", #
            "functions": ["wallShearStress"] #
        }
    }
}