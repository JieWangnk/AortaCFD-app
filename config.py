# config.py
"""
Configuration file for the Aorta CFD Application
------------------------------------------------
All simulation parameters are stored here in Python dictionaries.
"""

CONFIG = {
    # OpenFOAM version
    "openfoam_version": "8",
    # Directory where the case will be created
    "geometry": {
        "case_name": "PAT002_rotated",
        "scale_factor": 1e-3,
        "refinement_level": "medium", # options: "coarse", "medium", "fine"
        "rotation": True # options to adjust geometry alignment of coordinate system, defult is (0,0,1)
    },
    "mesh": {
        "SNAPPY_SETTINGS": {
            "parallel": True, # options: True, False
            "nProcessors": 3,
            "expansionFactor": 0.02,
            "regionRefinementLevel": 2,
            "regionRefinementBox": None,
            "nCellsBetweenLevels": 3,
            "featureLevel": 2,
            "surfaceRefinementLevels": [1, 1],
            "resolveFeatureAngle": 30,
            "nSmoothPatch": 3,
            "addLayer": 5
        },
        "refinement_levels": {
            "coarse": 2,
            "medium": 1.5,
            "fine": 1
        } 
    },
    "boundary": {
        "BC_INLET": "TIMEVARYING", # only two options: "TIMEVARYING", "STEADYSATE"  
        "BC_OUTLET": "3EWINDKESSEL", # only two options: "3EWINDKESSEL", "ZEROGRADIENT"
        "INLET_DATA_FILE": "BPM75.csv",
        "INLET_DATA_TYPE": "velocity", # only two options: "flowRate", "velocity"
        "INLET_PROFILE": "womersley", # only three profiles: "plug", "parabolic" and "womersley"
        "INLET_ORIENTATION": "out",
        "WK_SETTING": {
            "percentage": 30,        
            "systolic_pressure": 120,
            "diastolic_pressure": 80
        }
    },
    "physics": {
        "nu": 3.3e-06,
        "rho": 1060,
        "simulation_type": "laminar",
        "simulation_performance": "high",
        "outter_correction_loop": 100
    },
    "simulation_control": {
        "number_of_cycles": 2,
        "start_time": 0.0,
        "cardiac_cycle": 0.8, # can be removed
        "controlDict": {
            "startFrom": "startTime",
            "startTime": 0.0,
            "stopAt": "endTime",
            "endTime": 0.8,
            "deltaT": 1e-6,
            "writeControl": "adjustableRunTime",
            "writeInterval": 0.01,
            "runTimeModifiable": "true",
            "functionList": ["wallShearStress"]
        }
    },
    "initial_conditions": {
        "velocity": {
            "inlet_max_velocity": 0.1
        },
        "pressure": {
            "inlet": "zeroGradient",
            "outlet": "zeroGradient"
        },
        "k": {
            "kInlet": 0.001,
            "intensityInlet": 0.01
        },
        "omega": {
            "omegaInlet": 0.0001
        }
    },
    "run_settings": {
        "solution_type": "parallel",
        "subdomains": 3,
        "decomposition_method": "scotch"
    },
    "post_processing": {
        "case_type": "Reconstructed",
        "time_steps": {
            "customized": False,
            "start": 0.0,
            "end": 0.008,
            "step": 0.0001
        },
        "fields": ["U", "p", "wallShearStress"]  # Could be ["U", "p", "wallShearStress"], etc.
    }
}
