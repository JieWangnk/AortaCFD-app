import os
import numpy as np

REFINEMENT_LEVELS = {   
    "coarse":2,
    "medium":0.6,
    "fine":0.25
}
SNAPPY_SETTINGS = {
    "parallel": True,
    "nProcessors":3,
    "expansionFactor":0.02,
    "regionRefinementLevel": 2,
    "regionRefinementBox": None,
    "nCellsBetweenLevels":3,
    "featureLevel":2,
    "surfaceRefinementLevels": (1,2),
    "resloveFeatureAngle":10,
    "nSmoothPatch":3,
    "addLayer": 5
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



