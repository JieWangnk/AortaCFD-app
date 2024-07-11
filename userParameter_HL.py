from userParameter_LL import *

GEOMETRY_CASE = "geometry1"
REFINEMENT = "coarse" #options: "coarse", "medium", "fine"
GEOMETRY_SCALE = "1e-3"
#-------------------------------------------------------------------------------------------#
# Boundary conditions
BC_INLET = "TIME_VARYING_MAPPED_FIXED_VALUE" #options: FIXED_PARABOLIC_VELOCITY, TIMEVARYING_PARABOLIC_VELOCITY, TIME_VARYING_MAPPED_FIXED_VALUE, WAVEFORM
BC_OUTLET = "3EWINDKESSEL" #options: ZERO_GRADIENT, 3EWINDKESSEL
#-------------------------------------------------------------------------------------------#
# Inlet details
INLET_DATA_FILE = "BPM120.csv"
INLET_CENTER = "[-0.0159618, -0.0217017, -0.0128172]"
INLET_RADIUS = "0.0055"
#-------------------------------------------------------------------------------------------#
# Physical properties: transportProperteis and momentumTransport
NU = "3.3e-06"
RHO = "1060"
SIMULATIONTYPE ="LES" #options: laminar, RAS, LES
#-------------------------------------------------------------------------------------------#
# Cardiac cycle details
NUMBER_OF_CYCLES = "2"
START_TIME = "0"
CARDIAC_PEROID = "0.5"
INLET_DATA = "120"
#-------------------------------------------------------------------------------------------#
# Solution type
SOLN_TYPE = "parallel" #options: serial or parallel
SUBDOMAINS = "2"
DECOMPOSITION_METHOD = "scotch" #options: scotch, simple, hierarchical
#-------------------------------------------------------------------------------------------#