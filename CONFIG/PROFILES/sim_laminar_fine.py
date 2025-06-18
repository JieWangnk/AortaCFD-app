# config/profiles/sim_laminar_fine.py
"""
Simulation profile for a high-fidelity, fine-mesh LAMINAR simulation.
"""

CONFIG = {
    # Choice of physics model
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
            "nNonOrthogonalCorrectors": 1
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
    "controlDict": {
        "startFrom": "startTime",
        "startTime": 0.0,
        "stopAt": "endTime",
        "endTime": "auto",  # We can use 'auto' to signal it should be calculated
        "deltaT": 1e-6,
        "writeControl": "timeStep",
        "writeInterval": 1000,
        "runTimeModifiable": "true",
        "functionList": ["wallShearStress"]
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