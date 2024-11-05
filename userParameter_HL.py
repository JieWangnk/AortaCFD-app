from userParameter_LL import *

GEOMETRY_CASE = "PAT1_2024"
REFINEMENT = "coarse" #options: "coarse", "medium", "fine"
GEOMETRY_SCALE = "1e-3"
#-------------------------------------------------------------------------------------------#
# Boundary conditions
BC_INLET = "TIME_VARYING_MAPPED_FIXED_VALUE" #options: FIXED_PARABOLIC_VELOCITY, TIMEVARYING_PARABOLIC_VELOCITY, TIME_VARYING_MAPPED_FIXED_VALUE, WAVEFORM
BC_OUTLET = "3EWINDKESSEL" #options: ZERO_GRADIENT, 3EWINDKESSEL
#-------------------------------------------------------------------------------------------#
# Inlet details
INLET_DATA_FILE = "BPM120.csv"
INLET_PROFILE = "womersley" #options: womersley, parabolic
WOMERSLEY_PARAMETERS = {
    "MAX_VELOCITY": "1.0",
    "MEAN_VELOCITY": "0.73",
    "SYSTOLIC_PRESSURE": "118",
    "DIASTOLIC_PRESSURE": "82"
    #"DELTA_P": "2" # Pressure gradient amplitude
}
#-------------------------------------------------------------------------------------------#
# Physical properties: transportProperteis and momentumTransport
NU = "3.3e-06"
RHO = "1060"
SIMULATIONTYPE ="laminar" #options: laminar, RAS, LES
#-------------------------------------------------------------------------------------------#
# Cardiac cycle details
NUMBER_OF_CYCLES = "2"
START_TIME = "0"
CARDIAC_PEROID = "0.53"
INLET_DATA = "113"
HEART_RATE = "113"
#-------------------------------------------------------------------------------------------#
# Solution type
SOLN_TYPE = "parallel" #options: serial or parallel
SUBDOMAINS = "2"
DECOMPOSITION_METHOD = "scotch" #options: scotch, simple, hierarchical
#-------------------------------------------------------------------------------------------#