# CONFIG/profiles/sim_laminar_coarse.py
"""
Simulation profile for a coarse-mesh, low-fidelity LAMINAR simulation.
This profile defines the meshing, run settings, numerics, and solver parameters
for a fast, lower-accuracy run.
"""

CONFIG = {
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
            "regionRefinementLevel": 2, #
            "nCellsBetweenLevels": 3, #
            # Lower feature level for a coarser capture of geometry.
            "featureLevel": 2, #
            "surfaceRefinementLevels": [1, 1], #
            "resolveFeatureAngle": 30, #
            "nSmoothPatch": 3, #
            # Fewer layers for a coarse boundary layer mesh.
            "addLayer": 3 #
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
        "PIMPLE": { "nOuterCorrectors": 20, "nCorrectors": 2, "nNonOrthogonalCorrectors": 1 },
        "relaxationFactors": { "fields": {"p": 1.0}, "equations": {"U": 1.0} }
    },
    "fvSchemes": {
        # Using first-order schemes for stability on coarse meshes.
        "ddtSchemes": {"default": "Euler"},
        "gradSchemes": {"default": "cellLimited Gauss linear 0.5"},
        "divSchemes": {"div(phi,U)": "Gauss upwind"},
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
            "endTime": 1.0,  # Default/placeholder value
            "deltaT": 1e-6,
            "writeControl": "timeStep",
            "writeInterval": 1000, # Default/placeholder value
            "runTimeModifiable": "true",
            "functions": ["wallShearStress"]
        }
    }
}