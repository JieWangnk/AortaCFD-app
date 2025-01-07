from userParameter_LL import *

GEOMETRY_CASE ="geometry1"
REFINEMENT = "coarse" #options: "coarse", "medium", "fine"
GEOMETRY_SCALE = "1e-3"
#-------------------------------------------------------------------------------------------#
# Boundary conditions
#TODO: {Vincent} Change name of waveform to plugFlow.
BC_INLET = "TIME_VARYING_MAPPED_FIXED_VALUE" #options: FIXED_PARABOLIC_VELOCITY, TIMEVARYING_PARABOLIC_VELOCITY, TIME_VARYING_MAPPED_FIXED_VALUE, WAVEFORM
BC_OUTLET = "3EWINDKESSEL" #options: ZERO_GRADIENT, 3EWINDKESSEL
#-------------------------------------------------------------------------------------------#
# Inlet details
INLET_DATA_FILE = "BPM120.csv"
INLET_PROFILE = "plug" #options: plug, womersley, parabolic
INLET_ORINTATION = "out" # Often is out!!! options: in or out, as normal vector up to z-axis is out, down to z-axis is in 
#-------------------------------------------------------------------------------------------#
# Physical properties: transportProperteis and momentumTransport
NU = "3.3e-06"
RHO = "1060"
SIMULATIONTYPE ="laminar" #options: laminar, RAS, LES
SIMULATIONPERFORMACE = "low" #options: low, medium, high
#-------------------------------------------------------------------------------------------#
# Cardiac cycle details
NUMBER_OF_CYCLES = "1"
START_TIME = "0"
HEART_RATE = "120"
SYSTOLIC_PRESSURE = "133.5"
DIASTOLIC_PRESSURE = "72"   

WK_SETTING = {
    "percentage" : "70",  # Insert percentage flow through branches (30% average) 
}
#-------------------------------------------------------------------------------------------#
# Solution type
SOLN_TYPE = "parallel" #options: serial or parallel
SUBDOMAINS = "3"
DECOMPOSITION_METHOD = "scotch" #options: scotch, simple, hierarchical
#-------------------------------------------------------------------------------------------#
# Post-processing settings
CASE_TYPE = "Reconstructed" #options: Decomposed, Reconstrcuted
TIME_STEPS = {
    "Customized": False,
    "START": "0",
    "END": "0.008",
    "STEP": "0.0001",
}
FIELDS = None # Defults: ["U", "p", "wallShearStress"] options: ["KE","TKE"]
#-------------------------------------------------------------------------------------------#