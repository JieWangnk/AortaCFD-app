# Tutorial 1
This document gives a general overview on how to use the AortaCFD-app

## Step 1
### Setting Up Files for the Simulation
1. **STL file**:
   - The Geometry folder should be placed in the /CAD folder.
   - Inside the Geometry folder, there should be the .stl files of your geometry. 
   - The .stl file names should contain the name of the geometry and the name of the part. For example, if the geometry is a sphere and the part is the inlet, the .stl file name should be "sphere_inlet.stl".
   - The Geometry folder should contain the following .stl files:
     - The inlet should be named "inlet"
     - The outlet should be named "outlet"
     - The wall should be named "wall"
     - The .stl file can be either ASCII or Binary format.
  
2. **INLET file**: 
   - The INLET folder should contain the inlet doppler echo data .csv file.
   - The .csv file should have two columns: time and velocity for one cardiac cycle.
   - **Important**: The .csv filename should use the following naming convention BPM<Heart Rate>.csv (e.g. BPM120)
   - **Note:** The .csv file name that is going to be us in a simulation should be updated in the userParameter_HL.py file.

## Step 2
### Setting up Simulation Parameters
- High level parameter setting use userParameter_HL.py
- Low level parameter setting use userParameter_LL.py

For this tutorial we will use userParameter_HL.py to set the high level parameters.

- GEOMETRY_CASE: Give the same name your GEOMETRY folder that is in the CAD/ directory.
- INLET_DATA_FILE: Give the name of the .csv file that contains the inlet profile data.
- All other simulation parameters can be left to the default.

## Step 3
### Running the Simulation
To run your simulation follow the following steps:

1. **Create OpenFoam Case directory**:
   Run the code below to create the simulation openfoam case directory.
   ```
   python appDriver.py createCase
   ```
2. **Create Mesh**:
   Run the code below to create the meshed geometry using snappy hex mesh.
   ```
   python appDriver.py runMesh
   ```
3. **Prescribe Boundary Conditions**:
   Run the code below to prescribe the inlet and outlet 3 boundary conditions.
   ```
   python appDriver.py runBC
   ```
4. **Run the Simulation**:
   Run the code below to run the simulation with the specified setup, mesh and boundary conditions.
   ```
   python appDriver.py runSimulation
   ```
5. **Postprocessing**:
   The simulation results can be post processed in paraview (automatic postprocessing coming soon.)
    - Open paraview and load the ``f.foam`` file.
    - Note: If parallel was used as the solution type, in the properties window select``Decompose Case`` under Case Type.

# Some notes 