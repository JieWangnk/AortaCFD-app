# config/profiles/sim_laminar_fine.py
"""
Simulation profile for a high-fidelity, fine-mesh LAMINAR simulation.
"""

config = {
    # --------------------------------------------------------------------------
    # Mesh Settings
    # --------------------------------------------------------------------------
    "mesh": {
        # Fine mesh settings for high-fidelity simulation
        "SNAPPY_SETTINGS": {
            "parallel": True,
            "nProcessors": 4,
            "expansionFactor": 0.01,  # Smaller for finer mesh
            "regionRefinementLevel": 3,  # Higher for finer mesh
            "nCellsBetweenLevels": 4,
            "featureLevel": 3,  # Higher feature capture
            "surfaceRefinementLevels": [2, 3],  # Higher refinement
            "resolveFeatureAngle": 20,  # More strict angle
            "nSmoothPatch": 5,
            "addLayer": 5  # More boundary layers
        }
    },

    # --------------------------------------------------------------------------
    # Run Settings
    # --------------------------------------------------------------------------
    "run_settings": {
        "solution_type": "parallel",
        "subdomains": 4,
        "decomposition_method": "scotch"
    },

    # --------------------------------------------------------------------------
    # Physics and Solver Settings
    # --------------------------------------------------------------------------
    "physics": {
        "simulation_type": "laminar",
        "simulation_performance": "high" # Used by old scripts, can be phased out
    },

    # Settings for the fvSolution dictionary
    "fvSolution": {
        "solvers": {
            "p": {"solver": "GAMG", "smoother": "GaussSeidel", "tolerance": 1e-6, "relTol": 0.1},
            "U": {"solver": "smoothSolver", "smoother": "symGaussSeidel", "tolerance": 1e-6, "relTol": 0.1}
        },
        "PIMPLE": {
            "nOuterCorrectors": 100,
            "nCorrectors": 3,
            "nNonOrthogonalCorrectors": 1,
            "residualControl": {
                "p": {"tolerance": 1e-4, "relTol": 0},
                "U": {"tolerance": 1e-5, "relTol": 0}
            }
        },
        "relaxationFactors": {
            "fields": {"p": 0.3},
            "equations": {"U": 0.3}
        }
    },

    # Settings for the fvSchemes dictionary
    "fvSchemes": {
        "ddtSchemes": {"default": "backward"},
        "gradSchemes": {"default": "cellLimited Gauss linear 1"},
        "divSchemes": {"div(phi,U)": "Gauss linearUpwind default"},
        "laplacianSchemes": {"default": "Gauss linear limited 0.5"},
        "interpolationSchemes": {"default": "linear"},
        "snGradSchemes": {"default": "corrected"}
    },

    # Settings for the controlDict dictionary
    "simulation_control": {
        "controlDict": {
            "application": "pimpleFoam",
            "startFrom": "startTime",
            "startTime": 0.0,
            "stopAt": "endTime",
            "endTime": "auto",  # We can use 'auto' to signal it should be calculated
            "deltaT": 1e-5,  # Larger initial time step for robustness
            "writeControl": "adjustableRunTime",
            "writeInterval": 0.01,  # Write every 0.01s
            "runTimeModifiable": "true",
            "adjustTimeStep": "yes",
            "maxCo": 1.2,  # Balanced Courant number for efficiency
            "maxDeltaT": 1e-3,  # Larger maximum time step
            "minDeltaT": 1e-8,  # Prevent extremely small time steps
            "functions": ["wallShearStress"]
        }
    },

    # The CHOICE of boundary conditions is defined here.
    "boundary": {
        "BC_INLET": "TIMEVARYING",
        "BC_OUTLET": "3EWINDKESSEL",
        "INLET_DATA_TYPE": "velocity",
        "INLET_PROFILE": "womersley",
        "INLET_ORIENTATION": "out",
        "WK_SETTING": {
            "percentage": 30,
            "systolic_pressure": 120,
            "diastolic_pressure": 80
        }
    }
}