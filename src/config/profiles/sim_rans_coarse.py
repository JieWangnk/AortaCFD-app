# config/profiles/sim_rans_coarse.py
"""
Simulation profile for a coarse-mesh, low-fidelity RANS simulation.
This profile defines the meshing, run settings, numerics, and solver parameters
for a fast, lower-accuracy RANS run using k-omega SST turbulence model.
"""

config = {
    # --------------------------------------------------------------------------
    # Mesh Running Settings
    # --------------------------------------------------------------------------
    "mesh": {
        # These are the settings for the snappyHexMesh utility.
        # For a coarse RANS run, we use fewer refinement levels and features.
        "SNAPPY_SETTINGS": {
            # A coarse mesh is small, so we can generate it in serial.
            "parallel": False, #
            "nProcessors": 1, #
            "expansionFactor": 0.02, #
            "regionRefinementLevel": 4, #
            "nCellsBetweenLevels": 3, #
            # Higher feature level to capture inlet/outlet patches
            "featureLevel": 4, #
            "surfaceRefinementLevels": [4, 5], #
            "resolveFeatureAngle": 30, #
            "nSmoothPatch": 3, #
            # More layers for RANS boundary layer mesh.
            "addLayer": 5 #
        },
        # Automatic refinement configuration for RANS (targeting actual smallest patch: 3.64mm)
        "cells_per_patch_diameter": {
            "coarse": 8,    # 8 cells across minimum patch diameter (coarse for RANS)
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
        "simulation_type": "RAS", #
        "turbulence_model": "kOmegaSST", #
        "turbulence_intensity": 0.05, #
        "turbulence_viscosity_ratio": 10.0, #
        "nu": 3.77e-06,  # Kinematic viscosity (m^2/s) for blood
        "rho": 1060      # Density (kg/m^3) for blood
    },
    "fvSolution": {
        # Using RANS-appropriate solvers.
        "solvers": {
            "p": {"solver": "GAMG", "smoother": "GaussSeidel", "tolerance": 1e-6, "relTol": 0.05},
            "U": {"solver": "smoothSolver", "smoother": "symGaussSeidel", "tolerance": 1e-5, "relTol": 0.1},
            "k": {"solver": "smoothSolver", "smoother": "symGaussSeidel", "tolerance": 1e-5, "relTol": 0.1},
            "omega": {"solver": "smoothSolver", "smoother": "symGaussSeidel", "tolerance": 1e-5, "relTol": 0.1},
            "nut": {"solver": "smoothSolver", "smoother": "symGaussSeidel", "tolerance": 1e-5, "relTol": 0.1}
        },
        "PIMPLE": {
            "nOuterCorrectors": 20,
            "nCorrectors": 2,
            "nNonOrthogonalCorrectors": 1,
            "residualControl": {
                "p": {"tolerance": 1e-3, "relTol": 0},
                "U": {"tolerance": 1e-4, "relTol": 0},
                "k": {"tolerance": 1e-4, "relTol": 0},
                "omega": {"tolerance": 1e-4, "relTol": 0}
            }
        },
        "relaxationFactors": { 
            "fields": {"p": 0.3}, 
            "equations": {"U": 0.7, "k": 0.7, "omega": 0.7} 
        }
    },
    "fvSchemes": {
        # Using bounded schemes for RANS stability.
        "ddtSchemes": {"default": "backward"},
        "gradSchemes": {
            "default": "cellLimited Gauss linear 0.5",
            "grad(p)": "cellLimited Gauss linear 0.33",
            "grad(U)": "cellLimited Gauss linear 0.5"
        },
        "divSchemes": {
            "default": "none",
            "div(phi,U)": "bounded Gauss linearUpwindV grad(U)",
            "div(phi,k)": "bounded Gauss limitedLinear 1",
            "div(phi,omega)": "bounded Gauss limitedLinear 1",
            "div((nuEff*dev2(T(grad(U)))))": "Gauss linear"
        },
        "laplacianSchemes": {"default": "Gauss linear corrected"},
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
            "deltaT": 1e-4,  # Larger time step for coarse mesh
            "writeControl": "adjustableRunTime",
            "writeInterval": 0.01,  # Write every 0.01s
            "runTimeModifiable": "true",
            "adjustTimeStep": "yes",
            "maxCo": 1.0,  # Lower Courant for RANS stability
            "maxDeltaT": 1e-3,  # Smaller max time step for RANS
            "minDeltaT": 1e-7,  # Prevent very small time steps
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
    },

    # Fallback manual refinement levels (used if automatic calculation fails)
    "refinement_levels": {
        "coarse": 0.0012,   # 1.2mm cells (fallback)
        "medium": 0.0008,   # 0.8mm cells (fallback)
        "fine": 0.0005      # 0.5mm cells (fallback)
    }
}