# config.py
"""
Configuration file for the Aorta CFD Application
------------------------------------------------
All simulation parameters are stored here in Python dictionaries.
"""

CONFIG = {
    "geometry": {
        "case_name": "VOL04",
        "scale_factor": 1e-3,
        "refinement_level": "coarse"
    },
    "mesh": {
        "SNAPPY_SETTINGS": {
            "parallel": True,
            "nProcessors": 3,
            "expansionFactor": 0.02,
            "regionRefinementLevel": 2,
            "regionRefinementBox": None,
            "nCellsBetweenLevels": 3,
            "featureLevel": 2,
            "surfaceRefinementLevels": [1, 2],
            "resolveFeatureAngle": 10,
            "nSmoothPatch": 3,
            "addLayer": 5
        },
        "refinement_levels": {
            "coarse": 2,
            "medium": 0.6,
            "fine": 0.25
        }
    },
    "boundary": {
        "BC_INLET": "TIMEVARYING", # only two options: "TIMEVARYING", "STEADYSATE"  
        "BC_OUTLET": "3EWINDKESSEL", # only two options: "3EWINDKESSEL", "ZERO_GRADIENT"
        "INLET_DATA_FILE": "BPM73.csv",
        "INLET_DATA_TYPE": "velocity", # only two options: "flowRate", "velocity"
        "INLET_PROFILE": "parabolic", # only three profiles: "plug", "parabolic" and "womersley"
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
        "simulation_performance": "low",
        "outter_correction_loop": 10
    },
    "simulation_control": {
        "number_of_cycles": 1,
        "start_time": 0.0,
        "cardiac_cycle": 0.82, # can be removed
        "controlDict": {
            "startFrom": "startTime",
            "startTime": 0.0,
            "stopAt": "endTime",
            "endTime": 0.82,
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
