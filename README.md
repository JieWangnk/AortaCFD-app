# AortaCFD-app
### Setting Up the Environment: OpenFOAM and pvbatch[paraview]

1. **Source OpenFOAM**:
   Every time you open a new terminal and want to use OpenFOAM, you should source the bashrc file:
    ```bash
    source /opt/openfoam10/etc/bashrc
    ```
    For Windkessel BC, pimpleFoam_WK is needed be installed by compiling the following library:
    ```bash
      check emily's github
    ```
-  ```/opt/openfoam8/``` can be replaced with the path to your OpenFOAM installation.
2. **Source pvbatch**:
   Every time you open a new terminal and want to use pvbatch, you should source the bashrc file:
    ```bash
    source /opt/ParaView-5.9.1-MPI-Linux-Python3.8-64bit/bin/pvbatch
    ```
-  ```/opt/ParaView-5.9.1-MPI-Linux-Python3.8-64bit/``` can be replaced with the path to your paraview installation.

**Troubleshooting**: If you encounter issues, please referernce [OpenFOAM installation](https://openfoam.org/download/) and [paraview installation](https://www.paraview.org/download/).

3. **Python Library**
   - python version 3.10
   - numpy-stl: Allowed to handle both ASCII and Binary STL format.
   - pip install numpy
   - pip install numpy-stl
   - pip install scipy
   - pip install matplotlib

### Setting Up the Parameters for the Simulation
1. ```userParameter_HL.py```:

2. **STL file**:
   - The Geomtery folder should be placed in the /CAD folder.
   - Insider the Geometry folder, there should be a .stl file 
   - The .stl file names should contain the name of the geometry and the name of the part. For example, if the geometry is a sphere and the part is the inlet, the .stl file name should be "sphere_inlet.stl".
   - The .stl file should include the following information:
     - The inlet should be named "inlet"
     - The outlet should be named "outlet"
     - The wall should be named "wall"
     - The .stl file can be either ASCII or Binary format.
  
3. **INLET file**: 
   - The INLET folder should contain the inlet doppler echo data .csv file.
   - The .csv file is informat of two columns: time and velocity by one cardiac cycle.
   - The .csv that going to be simulated should be updated in the userParameter_HL.py file.

### Running the Code (Python3 or above)

1. **Run the code**:
   ```bash
   python3 appDriver.py
   ```
   The script defines a class OpenFOAMCase which is used to set up and manage a simulation case for the OpenFOAM computational fluid dynamics (CFD) software. 
   The __init__ method is the constructor for the class, which initializes the object with several parameters such as geometry_case, refinement, directory, bc_inlet, bc_outlet, initial_condition_U, initial_condition_p, nu, rho, simulation_type, and simulation_control. These parameters represent various aspects of the simulation such as the geometry of the case, the refinement level, the directory where the case files are stored, the boundary conditions at the inlet and outlet, the initial conditions for velocity (U) and pressure (p), the kinematic viscosity (nu), the density (rho), the type of simulation, and the simulation control parameters. 

   After initializing these parameters, the constructor calls the [`__create_OFcase`](./appDriver.py) method to create the necessary directories and files for the OpenFOAM case. It then creates several objects for handling different aspects of the case setup, such as the geometry, boundary conditions, physical properties, numerical setup, solver setup, and simulation setup. These objects are instances of other classes (not shown in the provided code) that presumably provide methods for writing the corresponding setup files for the OpenFOAM case.

   The OpenFOAMCase class also provides several methods for writing the setup files for the different aspects of the case, such as [`write_geometry_files`](./appDriver.py#L<67>), [`write_boundary_conditions`](./appDriver.py#L<72>), [`write_physical_properties`](./appDriver.py#L<78>), [`write_numericalSetup`](./appDriver.py#L<82>), [`write_solverSetup`](./appDriver.py#L<85>), and [`write_simulationSetup`](./appDriver.py#L<88>). Each of these methods calls the corresponding file-writing method on the appropriate setup object.

   Finally, the casePoilt method calls all the file-writing methods in sequence to write all the setup files for the OpenFOAM case. This method would typically be called after creating an OpenFOAMCase object and setting up all the parameters, to generate the complete set of setup files for the OpenFOAM simulation.
   
   MESH GENRATION?

2. **Individual scripts**:
   The [```appDriver.py```](./appDriver.py)
   1.  [```meshsetup.py```](./SCRIPTS/meshSetup.py): a Python script to automatically generate blockMeshDict and snappyHexMeshDict files.  This script will create very basic dictionary files, and modify parameter based on the ```userParameter.py```. 
   
3.  **Post-Processing**
    1.  [```phaseAverage.py```](./SCRIPTS/phaseAverage.py): 
