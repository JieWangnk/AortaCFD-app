import os
import numpy as np

REFINEMENT_LEVELS = {   
    "coarse":1,
    "medium":0.6,
    "fine":0.1
}
SNAPPY_SETTINGS = {
    "parallel":True,
    "nProcessors":2,
    "expansion_factor":0.02,
    "region_refinement":1,
    "nCellsBetweenLevels":3,
    "feature_level":3,
    "surface_refinement_levels": (2,3),
    "resolveFeatureAngle":30,
    "nSmoothPatch":3,
    "nSurfaceLayvers": 5
}
# ----------------- #
# initial condition #
# ----------------- #
# define initial condition for U, p, nut
# 1 inlet, 4 outlets, 1 wall_aorta
# inlet_type, outlet1_type, outlet2_type, outlet3_type, outlet4_type, wall_aorta_type = self.INITIAL_CONDITION_U.keys()

INITIAL_CONDITION_U = {
        #"inlet_volumetric_flow_rate": "7.84e-5",
        "inlet_max_velocity": "0.1",
        "heart_rate": "120",
}

INITIAL_CONDITION_P = {
        "inlet": "zeroGradient",
        "outlet": "zeroGradient"
}

INITIAL_CONDITION_K = {
        "kInlet": "0.001",
        "intensityInlet": "0.01"
}

INITIAL_CONDITION_OMEGA = {
        "omegaInlet": "0.0001"
}

SIMULATION_CONTROL = {
    "startFrom" : "startTime",
    "startTime" : "0",
    "stopAt" : "endTime",
    "endTime" : "1",
    "deltaT" : "0.000001",
    "writeControl" : "adjustableRunTime",    #timeStep, runTime, adjustableRunTime
    "writeInterval" : "0.01",       # 1, 0.1, 0.01
    "runTimeModifiable" : "true",
    "functionList" : ["wallShearStress"]
}

WK_SETTING = {
    "percentage" : "70",  # Insert percentage flow through branches (30% average) 
    "SP" : "133.5",  # Systole Pressure   
    "DP" : "72",   # Dystole Pressure     
    "HR" : "120"  # Heart Rate
}




