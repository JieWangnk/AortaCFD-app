# config/profiles/sim_laminar_coarse.py
"""
Simulation profile for a coarse-mesh, low-fidelity LAMINAR simulation.
This profile defines the meshing, run settings, numerics, and solver parameters
for a fast, lower-accuracy run.
"""

config = {
    # --------------------------------------------------------------------------
    # Mesh Running Settings
    # --------------------------------------------------------------------------
    "mesh": {
        # These are the settings for the snappyHexMesh utility.
        # For a coarse run, we use fewer refinement levels and features.
        "SNAPPY_SETTINGS": {
            # A coarse mesh is small, so we can generate it in serial.
            "parallel": False, #
            "nProcessors": 1, #
            "expansionFactor": 0.02, #
            "regionRefinementLevel": 3, #
            "nCellsBetweenLevels": 3, #
            # Higher feature level to capture inlet/outlet patches
            "featureLevel": 3, #
            "surfaceRefinementLevels": [2, 3], #
            "resolveFeatureAngle": 30, #
            "nSmoothPatch": 3, #
            # Disable boundary layers to reduce aspect ratio
            "addLayer": 0, #            # No boundary layers to improve aspect ratio
            # Layer thickness controls to reduce aspect ratio
            "expansionRatio": 1.1,      # Smaller expansion ratio (default 1.2)
            "finalLayerThickness": 0.5, # Thicker final layer (default 0.3)
            "minThickness": 0.2,        # Increase minimum thickness (default 0.1)
            # Mesh quality constraints to improve aspect ratio
            "maxAspectRatio": 8,        # Limit aspect ratio (default 10) 
            "maxNonOrtho": 60,          # Reduce non-orthogonality (default 65)
            "maxInternalSkewness": 3,   # Reduce skewness (default 4)
            "nSmoothScale": 6,          # More smoothing iterations (default 4)
            "errorReduction": 0.8       # More aggressive error reduction (default 0.75)
        },
        # Refinement levels for different mesh quality
        "refinement_levels": {
            "coarse": 0.001,    # 1mm cells (default for coarse)
            "medium": 0.0005,   # 0.5mm cells (increased from 1mm)
            "fine": 0.0002      # 0.2mm cells (increased from 0.5mm)
        },
        # Automatic refinement configuration
        "cells_per_patch_diameter": {
            "coarse": 8,    # 8 cells across minimum patch diameter (truly coarse)
            "medium": 12,   # 12 cells across minimum patch diameter
            "fine": 16      # 16 cells across minimum patch diameter
        },
        "automatic_refinement": {
            "enabled": True,    # Enable automatic refinement level calculation
            "methodology": "murray_law_based"
        }
    },

    # --------------------------------------------------------------------------
    # Run Settings
    # --------------------------------------------------------------------------
    "run_settings": {
        # A coarse simulation is typically run in serial for speed on small meshes.
        "solution_type": "serial", #
        "subdomains": 1, #
        "decomposition_method": "scotch" #
    },

    # --------------------------------------------------------------------------
    # Physics and Solver Settings
    # --------------------------------------------------------------------------
    "physics": {
        "simulation_type": "laminar", #
    },
    "fvSolution": {
        # Using simpler, faster solvers.
        "solvers": {
            "p": {"solver": "PCG", "preconditioner": "DIC", "tolerance": 1e-5, "relTol": 0.1},
            "U": {"solver": "PBiCGStab", "preconditioner": "DILU", "tolerance": 1e-5, "relTol": 0.1}
        },
        "PIMPLE": {
            "nOuterCorrectors": 20,
            "nCorrectors": 2,
            "nNonOrthogonalCorrectors": 1,
            "residualControl": {
                "p": {"tolerance": 1e-3, "relTol": 0},
                "U": {"tolerance": 1e-4, "relTol": 0}
            }
        },
        "relaxationFactors": { "fields": {"p": 1.0}, "equations": {"U": 1.0} }
    },
    "fvSchemes": {
        # Using more stable schemes for initial transients
        "ddtSchemes": {"default": "backward"},
        "gradSchemes": {"default": "cellLimited Gauss linear 0.33"},
        "divSchemes": {"div(phi,U)": "Gauss linearUpwind grad(U)"},
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
            "endTime": "auto",  # Auto-calculate based on cycles
            "deltaT": 1e-5,  # Smaller initial time step for stability
            "writeControl": "adjustableRunTime",
            "writeInterval": 0.01,  # Write every 0.01s
            "runTimeModifiable": "true",
            "adjustTimeStep": "yes",
            "maxCo": 1.0,  # Increase Courant for faster simulation
            "maxDeltaT": 1e-3,  # Smaller max time step for stability
            "minDeltaT": 1e-6,  # Prevent extremely small time steps
            "functions": ["wallShearStress"]
        }
    },

    # Add boundary condition defaults compatible with the case
    "boundary": {
        "BC_INLET": "TIMEVARYING",
        "BC_OUTLET": "ZEROGRADIENT",
        "INLET_DATA_TYPE": "velocity",
        "INLET_PROFILE": "womersley",
        "INLET_ORIENTATION": "out"
    }
}