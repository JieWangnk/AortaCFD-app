import os
import numpy as np

REFINEMENT_LEVELS = {
    "coarse":1,
    "medium":0.2,
    "fine":0.1
}
SNAPPY_SETTINGS = {
    "expansion_factor":0.02,
    "feature_level":3,
    "surface_refinement_levels": (1,3),
    "number_of_layers": 5
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
        "heart_rate": "60",
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
    "percentage" : "40",  # Insert percentage flow through branches (30% average) 
    "SP" : "113",  # Systole Pressure   
    "DP" : "62",   # Dystole Pressure     
    "HR" : "120"  # Heart Rate
}




