# CONFIG/profiles/sim_laminar_coarse.py
"""
Simulation profile for a coarse-mesh, low-fidelity LAMINAR simulation.

This profile prioritizes speed and stability over high accuracy, making it
ideal for initial tests and quick runs. It uses first-order numerical schemes
and simpler solvers.
"""

CONFIG = {
    # Physics model selection
    "physics": {
        "simulation_type": "laminar", #
        # For a coarse simulation, fewer outer correction loops are needed.
        "outter_correction_loop": 20 #
    },

    # fvSolution settings tuned for speed and robustness.
    "fvSolution": {
        # Using simpler, faster solvers like PCG.
        "solvers": {
            "p": {"solver": "PCG", "preconditioner": "DIC", "tolerance": 1e-5, "relTol": 0.1},
            "U": {"solver": "PBiCGStab", "preconditioner": "DILU", "tolerance": 1e-5, "relTol": 0.1}
        },
        # Fewer correctors for a faster PIMPLE loop.
        "PIMPLE": {
            "nOuterCorrectors": 20, # Linked to outter_correction_loop
            "nCorrectors": 2,
            "nNonOrthogonalCorrectors": 1
        },
        # Relaxation is turned off (factors of 1.0) for speed,
        # which is acceptable with robust first-order schemes.
        "relaxationFactors": {
            "fields": {"p": 1.0},
            "equations": {"U": 1.0}
        }
    },

    # fvSchemes settings using first-order schemes for stability.
    "fvSchemes": {
        # Using first-order 'Euler' for the time derivative.
        "ddtSchemes": {"default": "Euler"},
        "gradSchemes": {"default": "cellLimited Gauss linear 0.5"},
        # Using first-order 'upwind' for divergence, which is very stable.
        "divSchemes": {"div(phi,U)": "Gauss upwind"},
        "laplacianSchemes": {"default": "Gauss linear limited 0.5"},
        "interpolationSchemes": {"default": "linear"},
        "snGradSchemes": {"default": "corrected"}
    },

    # Simulation control settings for a coarse run.
    "simulation_control": {
        "controlDict": {
            "application": "pimpleFoam",
            "startFrom": "startTime", #
            "startTime": 0.0, #
            "stopAt": "endTime", #
            "endTime": "auto",  # This is calculated dynamically by the workflow
            "deltaT": 1e-6, #
            "writeControl": "timeStep", #
            # Writing data less frequently for a coarse run to save time and disk space.
            "writeInterval": 5000,
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