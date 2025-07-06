# CONFIG/profiles/laminar_medium.py
"""
Simulation profile for a medium-fidelity LAMINAR simulation.
This file defines the meshing, run settings, numerics, and solver parameters.
"""

config = {
    # --------------------------------------------------------------------------
    # Mesh and Run Settings
    # --------------------------------------------------------------------------
    "mesh": {
        "SNAPPY_SETTINGS": {
            "parallel": False,
            "nProcessors": 3,
            "addLayer": 5,
            "expansionFactor": 0.02,
            "featureLevel": 2,
            "surfaceRefinementLevels": [1, 1],
            "nCellsBetweenLevels": 3,
            "resolveFeatureAngle": 30,
            "nSmoothPatch": 3,
            
            # --- Add these keys based on your original config.py ---
            "relativeSizes": True,
            "expansionRatio": 1.2,
            "finalLayerThickness": 0.3,
            "minThickness": 0.1,
            "nGrow": 0,
            "featureAngle": 60,
            "slipFeatureAngle": 30,
            "nRelaxIter": 5,
            "nSmoothSurfaceNormals": 1,
            "nSmoothThickness": 10,
            "maxFaceThicknessRatio": 0.5,
            "maxThicknessToMedialRatio": 0.3,
            "minMedianAxisAngle": 90,
            "nBufferCellsNoExtrude": 0,
            "nLayerIter": 50
        }
    },
    "run_settings": {
        "solution_type": "parallel",
        "subdomains": 3,
        "decomposition_method": "scotch"
    },

    # --------------------------------------------------------------------------
    # Physics and Solver Settings
    # --------------------------------------------------------------------------
    "physics": {
        "simulation_type": "laminar",
        "outter_correction_loop": 100
    },

    # --- THIS IS THE MISSING DICTIONARY ---
    "fvSolution": {
        # These settings are from the _get_laminar_medium_fvSolution method
        # in your original solverSetup.py script.
        "solvers": {
            "p": {"solver": "GAMG", "smoother": "GaussSeidel", "tolerance": 1e-6, "relTol": 0.1},
            "U": {"solver": "PBiCGStab", "preconditioner": "DILU", "tolerance": 1e-6, "relTol": 0.1}
        },
        "solvers_final": { # Added this block for the final relaxation step
             "p": {"tolerance": 1e-7},
             "U": {"tolerance": 1e-6}
        },
        "PIMPLE": {
            "nOuterCorrectors": 100,
            "nCorrectors": 2,
            "nNonOrthogonalCorrectors": 1,
            "residualControl": {
                "p": {"tolerance": 1e-5, "relTol": 0},
                "U": {"tolerance": 1e-4, "relTol": 0}
            }
        },
        "relaxationFactors": {
            "fields": {"p": 0.7},
            "equations": {"U": 0.7}
        }
    },
    # ---------------------------------------

    "fvSchemes": {
        "ddtSchemes": {"default": "backward"},
        "gradSchemes": {"default": "cellLimited Gauss linear 0.5"},
        "divSchemes": {"div(phi,U)": "Gauss linear"},
        "laplacianSchemes": {"default": "Gauss linear limited 0.5"},
        "interpolationSchemes": {"default": "linear"},
        "snGradSchemes": {"default": "corrected"}
    },
    
    "simulation_control": {
        "controlDict": {
            "application": "pimpleFoam",
            "startFrom": "startTime",
            "startTime": 0.0,
            "stopAt": "endTime",
            "endTime": "auto",
            "deltaT": 1e-6,
            "writeControl": "timeStep",
            "writeInterval": 1,
            "runTimeModifiable": "true",
            "allowSystemOperations": "true",
            "purgeWrite": 0,
            "adjustTimeStep": "yes",
            "maxCo": 1,
            "functions": ["wallShearStress"]
        }
    }
}