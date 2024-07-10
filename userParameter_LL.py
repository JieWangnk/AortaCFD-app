import os
import numpy as np

REFINEMENT_LEVELS = {
<<<<<<< HEAD
    "coarse":1,
=======
    "coarse":0.4,
>>>>>>> 98e3dfd6f57ee2f4239f74b7e5651cee3db6e047
    "medium":0.2,
    "fine":0.1
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
        "inlet_normal": "(0, 0, 1)",
        "inlet_radius": "[-0.015923, -0.0212171, -0.0128499]",
        "heart_rate": "60",
        "inlet_center" : "0.0055"
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
    "deltaT" : "0.001",
    "writeControl" : "runTime",    #timeStep, runTime, adjustableRunTime
    "writeInterval" : "0.1",       # 1, 0.1, 0.01
    "runTimeModifiable" : "true",
<<<<<<< HEAD
    "functionList" : ["wallShearStress"]
=======
    "functionList" : ["wallShearStress", "turbulenceFields"]
>>>>>>> 98e3dfd6f57ee2f4239f74b7e5651cee3db6e047
}

WK_SETTING = {
    "A_rcca" : "2.880E-05",  # RCCA area
    "A_lcca" : "1.089E-05",  # LCCA area
    "A_lsca" : "1.827E-05",  # LSCA area
    "A_DAo" : "3.944E-05",   # DAo area
    "percentage" : "40",  # Insert percentage flow through branches (30% average) 
    "SP" : "113",  # Systole Pressure   
    "DP" : "62",   # Dystole Pressure     
    "HR" : "120"  # Heart Rate
}




