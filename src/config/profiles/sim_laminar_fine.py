# config/profiles/sim_laminar_fine.py
"""
OpenFOAM 12 specific simulation profile for high-fidelity laminar simulation.
All version compatibility removed.
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
            "addLayer": 5,  # More boundary layers
            # Span-based refinement for coarctation
            "span_refinement_enabled": True,
            "span_refinement_distance": 1000,  # 1mm
            "span_refinement_level": 2,
            "cells_across_span": 20,
            # High-quality mesh constraints for fine mesh
            "maxAspectRatio": 6,        # Stricter aspect ratio for fine mesh
            "maxNonOrtho": 50,          # Lower non-orthogonality
            "maxInternalSkewness": 2,   # Lower skewness
            "nSmoothScale": 8,          # More smoothing for better quality
            "errorReduction": 0.85      # Higher error reduction for fine mesh
        },
        # Refinement levels for different mesh quality
        "refinement_levels": {
            "coarse": 0.002,    # 2mm cells (increased from 5mm to capture inlet/outlet patches)
            "medium": 0.001,    # 1mm cells (increased from 2mm)
            "fine": 0.0005      # 0.5mm cells (increased from 1mm)
        },
        # Automatic refinement configuration for fine mesh
        "cells_per_patch_diameter": {
            "coarse": 12,   # 12 cells across minimum patch diameter (fine profile baseline)
            "medium": 16,   # 16 cells across minimum patch diameter
            "fine": 20      # 20 cells across minimum patch diameter
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
        "solution_type": "parallel",
        "subdomains": 4,
        "decomposition_method": "scotch"
    },

    # --------------------------------------------------------------------------
    # Physics and Solver Settings (OpenFOAM 12)
    # --------------------------------------------------------------------------
    "physics": {
        "simulation_type": "laminar",
        "simulation_performance": "high",
        "steady_state": False
    },

    # Settings for the fvSolution dictionary (OpenFOAM 12 optimized)
    "fvSolution": {
        "SIMPLE": {
            "nNonOrthogonalCorrectors": 0,
            "residualControl": {
                "p": "1e-4",
                "U": "1e-5",
                "k": "1e-5"
            }
        },
        "PIMPLE": {
            "nOuterCorrectors": 100,
            "nCorrectors": 3,
            "nNonOrthogonalCorrectors": 1,
            "outerCorrectorResidualControl": {
                "p": "1e-4",
                "U": "1e-5",
                "k": "1e-5"
            }
        },
        "relaxationFactors": {
            "fields": {"p": "0.3"},
            "equations": {"U": "0.7", "k": "0.7"}
        }
    },

    # Settings for the controlDict dictionary (OpenFOAM 12)
    "simulation_control": {
        "controlDict": {
            "startFrom": "startTime",
            "startTime": 0.0,
            "stopAt": "endTime",
            "endTime": "auto",  # Will be calculated based on cardiac cycles
            "deltaT": 1e-5,  # Initial time step
            "writeControl": "adjustableRunTime",
            "writeInterval": 0.01,  # Write every 0.01s
            "runTimeModifiable": "true",
            "adjustTimeStep": "yes",
            "maxCo": 1.2,  # Balanced Courant number
            "maxDeltaT": 1e-3,  # Maximum time step
            "minDeltaT": 1e-8,  # Minimum time step
            "functions": ["wallShearStress"]
        }
    },

    # Boundary conditions (OpenFOAM 12)
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
            "use_murray_law": True  # Enable automatic Murray's law calculation
        }
    }
}