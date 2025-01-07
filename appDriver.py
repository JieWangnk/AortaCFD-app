from userParameter_HL import * 
from SCRIPTS.meshSetup import *
from SCRIPTS.boundaryConditionSetup import *
from SCRIPTS.physicalProperitesSetup import *
from SCRIPTS.numericalSetup import *
from SCRIPTS.solverSetup import *
from SCRIPTS.simulationSetup import *
from SCRIPTS.inletMapping import *
from SCRIPTS.patchProcessing import *
from SCRIPTS.cycleDataSetup import *
from SCRIPTS.solnTypeSetup import *
from SCRIPTS.wkSetup import *
from SCRIPTS.formatPoints import *
import sys
import os
import time
import shutil
import argparse
import subprocess

def _generate_time_array(time_steps_dict):
    start = float(time_steps_dict["START"])
    end   = float(time_steps_dict["END"])
    step  = float(time_steps_dict["STEP"])

    times = []
    val = start
    while val <= end + 1e-12:
        times.append(round(val, 4))
        val += step
    return times

class OpenFOAMCase:
    def __init__(self, geometry_case, refinement, directory, bc_inlet,
                bc_outlet, initial_condition_U, initial_condition_p,initial_condition_K, initial_condition_omega,
                nu, rho, simulation_type, simulation_performace,simulation_control, soln_type, subdomains, decomposition_method):
        """ Helper class to create an OpenFOAM case for AortaCFD.
        Handles the creation of the case directory, system, constant, and 0 folders.
        Args:
            geometry_case (str): Name of the geometry case.
            refinement (str): Mesh refinement level.
            feature_level (int): Feature level for snappyHexMesh.
            surface_refinement_levels (tuple): Surface refinement levels for snappyHexMesh.
            directory (str): Path to the case directory.
            bc_inlet (str): Inlet boundary condition type.
            bc_outlet (str): Outlet boundary condition type.
            initial_condition_U (dict): Initial condition for velocity.
            initial_condition_p (dict): Initial condition for pressure.
            initial_condition_K (dict): Initial condition for turbulent kinetic energy.
            initial_condition_omega (dict): Initial condition for turbulent omega.
            nu (str): Kinematic viscosity.
            rho (str): Density.
            simulation_type (str): Simulation type (laminar, RAS, LES).
            simulation_performace (str): Handling HPC or advanced solver configs.
            simulation_control (dict): Simulation control parameters.
            soln_type (str): Solution type (serial, parallel).
            subdomains (str): Number of subdomains for parallel processing.
            decomposition_method (str): Decomposition method for parallel processing."""
        self.geometry_case = geometry_case
        self.refinement = refinement
        self.directory = directory
        self.BC_INLET = bc_inlet
        self.BC_OUTLET = bc_outlet
        self.initial_condition_U = initial_condition_U
        self.initial_condition_p = initial_condition_p
        self.initial_condition_K = initial_condition_K
        self.initial_condition_omega = initial_condition_omega
        self.nu = nu
        self.rho = rho
        self.simulation_type = simulation_type
        self.simulation_performace = simulation_performace
        self.simulation_control = simulation_control
        self.soln_type = soln_type
        self.subdomains = subdomains
        self.decomposition_method = decomposition_method
           
        self.__create_OFcase()

        self.geometry_analyzer = GeometryAnalyzer(
            DIRECTORY=self.directory, 
            geometry_case=self.geometry_case, 
            refinement=self.refinement
        )
        
        self.boundary_condition = BoundaryConditionSetup(
            self.directory, 
            self.geometry_analyzer.stl_files, 
            self.BC_INLET, 
            self.BC_OUTLET, 
            self.initial_condition_U, 
            self.initial_condition_p, 
            self.initial_condition_K, 
            self.initial_condition_omega, 
            self.simulation_type
        )
        
        self.physical_condition = PhysicalPropertiesWriter(
            self.directory, 
            self.nu, 
            self.rho, 
            self.simulation_type
        )

        self.numericalSetup = FvSchemesWriter(
            self.directory, 
            self.simulation_type, 
            self.simulation_performace
        )

        self.solverSetup = FvSolutionWriter(
            self.directory, 
            self.simulation_type, 
            self.simulation_performace
        )

        self.simulationSetup = SimulationSetup(
            self.directory, 
            self.simulation_control
        )

        self.solnType = SolnType(
            self.directory, 
            soln_type, 
            subdomains, 
            decomposition_method
        )

    def __create_OFcase(self):
        """ Creates the OpenFOAM case directory and subdirectories."""

        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
        else:
            # Remove if exists to ensure a clean directory
            shutil.rmtree(self.directory)
            os.makedirs(self.directory)
        print("Directory ", self.directory, " Created ")
           
        # create system, constant, and 0 folders 
        for f in ["system", "constant", "0"]:
            directory = os.path.join(self.directory, f)
            try:
                os.makedirs(directory)
            except OSError as e:
                print(f"Error: {e}")
        
        # create constant/triSurface folder
        directory_con_tri = os.path.join(self.directory, "constant", "triSurface")
        try:
            os.makedirs(directory_con_tri)
        except OSError as e:
            print(f"Error: {e}")
        
        # create constant/boundaryData folder
        directory_con_bd = os.path.join(self.directory, "constant", "boundaryData")
        try:
            os.makedirs(directory_con_bd)
        except OSError as e:
            print(f"Error: {e}")

        # Copy STL files to constant/triSurface folder
        CADfolder = os.path.join("CAD", self.geometry_case)
        for f in os.listdir(CADfolder):
            shutil.copy(os.path.join(CADfolder, f), directory_con_tri)
            # if file name indicates "inlet"
            if "inlet" in f:
                inletBoundary = os.path.join(self.directory, "constant", "boundaryData", f.split(".")[0])
                try:
                    os.makedirs(inletBoundary)
                except OSError as e:
                    print(f"Error: {e}")
                if INLET_DATA_FILE:
                    shutil.copy(os.path.join("INLET", INLET_DATA_FILE), inletBoundary)
    
    def write_geometry_files(self):
        self.geometry_analyzer.write_blockMeshDict()
        self.geometry_analyzer.write_snappyHexMeshDict()
        self.geometry_analyzer.write_surfaceFeaturesDict()

    def write_boundary_conditions(self):
        self.boundary_condition.write_U_file()
        self.boundary_condition.write_p_file()
        if self.simulation_type in ["RAS", "LES"]:
            self.boundary_condition.write_nut_file()
        if self.simulation_type == "RAS":
            self.boundary_condition.write_k_file()
            self.boundary_condition.write_omega_file()
        # for inlet extraction
        self.boundary_condition.write_sampleDict_file()   

    def write_physical_properties(self):
        self.physical_condition.write_transportProperties_file()
        self.physical_condition.write_momentumProperties_file()

    def write_numericalSetup(self):
        self.numericalSetup.write_fvSchemes_file()

    def write_solverSetup(self):
        self.solverSetup.write_fvSolution_file()
    
    def write_simulationSetup(self):
        self.simulationSetup.write_controlDict()
    
    def write_decomposeParDict(self):
        self.solnType.write_decomposeParDict()
           

    def casePoilt(self):
        """Call the geometry, boundary, physical property,
           numerical, solver, simulation and parallel-subdomains setup writers."""
        self.write_geometry_files()
        self.write_boundary_conditions()
        self.write_physical_properties()
        self.write_numericalSetup()
        self.write_solverSetup()
        self.write_simulationSetup()
        self.write_decomposeParDict()


class OpenFOAMRunner:
    def __init__(self, geometry_case, refinement):
        """ Manages the OpenFOAM simulation workflow for AortaCFD."""
        self.geometry_case = geometry_case
        self.refinement = refinement
        self.case_directory = os.path.join(os.getcwd(), "OPENFOAM", f"{self.geometry_case}_{self.refinement}")
        self.GEOMETRY_SCALE = GEOMETRY_SCALE
        self.HEART_RATE = HEART_RATE
        self.NUMBER_OF_CYCLES = NUMBER_OF_CYCLES
        self.SOLN_TYPE = SOLN_TYPE
        self.SUBDOMAINS = SUBDOMAINS
        self.BC_OUTLET = BC_OUTLET
        self.BC_INLET = BC_INLET
        self.INLET_DATA_FILE = INLET_DATA_FILE
        self.INLET_PROFILE = INLET_PROFILE
        self.WK_SETTING = WK_SETTING

    def create_openfoam_case(self):
        """
        Creates an OpenFOAM case with the specified parameters.
        Returns:
            None
        """
        print("Creating OpenFOAM case...")
        my_case = OpenFOAMCase(
            geometry_case=self.geometry_case, 
            refinement=self.refinement,
            directory=self.case_directory,
            bc_inlet=BC_INLET,
            bc_outlet=BC_OUTLET,
            initial_condition_U=INITIAL_CONDITION_U,
            initial_condition_p=INITIAL_CONDITION_P,
            initial_condition_K=INITIAL_CONDITION_K,
            initial_condition_omega=INITIAL_CONDITION_OMEGA,
            nu=NU,
            rho=RHO,
            simulation_type=SIMULATIONTYPE,
            simulation_performace=SIMULATIONPERFORMACE,
            simulation_control=SIMULATION_CONTROL,
            soln_type=SOLN_TYPE,
            subdomains=SUBDOMAINS,
            decomposition_method=DECOMPOSITION_METHOD
        )
        my_case.casePoilt()
        print("OpenFOAM case created")

    def run_mesh(self):
        """
        Runs the meshing process for AortaCFD.
        Returns:
            None
        """
        print("Running meshing process...")
        start_time = time.time()
        # Change to case directory
        os.chdir(self.case_directory)
        # Run blockMesh
        os.system("blockMesh > blockMesh.log")
        # Run surfaceFeatureExtract
        os.system("surfaceFeatures > surfaceFeatures.log")
        # Run snappyHexMesh
        if SNAPPY_SETTINGS["parallel"]:
            os.system("foamDictionary -entry 'method' -set 'simple' system/decomposeParDict")
            os.system("foamDictionary -entry 'numberOfSubdomains' -set '{}' system/decomposeParDict".format(SNAPPY_SETTINGS["nProcessors"]))
            os.system("foamDictionary -entry 'simpleCoeffs/n' -set '(1 1 {})' system/decomposeParDict".format(SNAPPY_SETTINGS["nProcessors"]))
            os.system("decomposePar -noZero -force > snappyHex.log")
            os.system("mpirun -np {} snappyHexMesh -parallel -overwrite > snappyHex.log".format(SNAPPY_SETTINGS["nProcessors"]))
            os.system("reconstructParMesh -constant -latestTime > reconstructParMesh.log")
            os.system("rm -r processor*")
        else:
            os.system("snappyHexMesh -overwrite > snappyHex.log")
        # run checkMesh
        os.system("checkMesh > checkMesh.log")
        # transfer mesh scale based on GEOMETRY_SCALE
        os.system("transformPoints 'scale=({} {} {})' > transform.log".format(
            self.GEOMETRY_SCALE, self.GEOMETRY_SCALE, self.GEOMETRY_SCALE)
        )
        os.system("touch f.foam")
        end_time = time.time()
        elapsed_time = end_time - start_time
        print("Mesh created in {:.2f} minutes.".format(elapsed_time / 60))

    def run_bc(self):
        """
        Sets up the boundary conditions for the simulation.
        Returns:
            None
        """
        print("Setting boundary conditions...")
        start_time = time.time()
        # Change to case directory
        os.chdir(self.case_directory)
        # get inlet stl file name
        inlet_stl = [f for f in os.listdir(os.path.join("constant", "triSurface")) if "inlet" in f][0].split(".")[0] 
        # write the inlet cell centers to map the inlet velocity
        os.system("writeMeshObj > meshObj.log")
        os.system("mv patch_inlet_0.obj points-new")
        os.system("rm -r mesh* patch*")
        formatter = EnhancedPointsFormatter(format_version=1)
        formatter.format_coordinates()
        os.system("cp points constant/boundaryData/{}/".format(inlet_stl))
        os.system("rm points")
        
        stl_files = [f for f in os.listdir(os.path.join("constant", "triSurface")) if f.endswith(".stl")]
        # Create an instance of PatchProcessing
        inlet_radius_calculator = PatchProcessing(
            DIRECTORY=self.case_directory, 
            STL_FILES=stl_files, 
            PATH_NAME="inlet"
        )
        # calculate the inlet radius
        inlet_center, inlet_radius, inlet_normal = inlet_radius_calculator.calculate_inlet_center_radius()
 
        # run inletMapping 
        processor = InletMapping(
            center=inlet_center * eval(self.GEOMETRY_SCALE), 
            radius=inlet_radius * eval(self.GEOMETRY_SCALE), 
            inlet_data_file=self.INLET_DATA_FILE, 
            inlet_name="inlet", 
            profile=self.INLET_PROFILE
        )
        processor.run()
        # run cycleDataSetup
        cycle_data = CycleDataSetup(
            BPM=int(self.HEART_RATE), 
            numberOfCycle=int(self.NUMBER_OF_CYCLES)
        )
        cycle_data.execute()
        # wkSetup for 3-element Windkessel if applicable
        if self.BC_OUTLET == "3EWINDKESSEL":
            wk_setup = wk_Setup(
                DIRECTORY=self.case_directory, 
                STL_FILES=stl_files, 
                WK_SETTING=self.WK_SETTING
            )  
            wk_setup.write_WK_Setup()
        
        # change the format of "points" file to match the timeVaryingMappedFixedValue BC requirements
        formatter = EnhancedPointsFormatter(format_version=2)
        formatter.format_coordinates()
        os.system("cp points constant/boundaryData/{}/".format(inlet_stl))
        end_time = time.time()
        elapsed_time = end_time - start_time

        print("Boundary condition set in {:.2f} minutes.".format(elapsed_time / 60))

    def run_simulation(self):
        """
        Runs the simulation based on the specified solution type.
        Returns:
            None
        """
        print("Running simulation...")
        start_time = time.time()
        # Change to case directory
        os.chdir(self.case_directory)
        # Logic to run simulation
        if self.SOLN_TYPE == "serial":
            if self.BC_OUTLET == "3EWINDKESSEL":
                os.system("pimpleFoam_WK_2.1 > log.log")    # Adjust as needed
            else:
                os.system("pimpleFoam > log.log")
        elif self.SOLN_TYPE == "parallel":
            os.system("decomposePar > decompose.log")
            os.system("renumberMesh > renumberMesh.log")
            if self.BC_OUTLET == "3EWINDKESSEL":
                os.system("mpirun -np {} pimpleFoam_WK_2.1 -parallel  > log.log".format(self.SUBDOMAINS))
            else:
                os.system("mpirun -np {} pimpleFoam > log.log".format(self.SUBDOMAINS))     
            os.system("reconstructPar > reconstruct.log")
            os.system("rm -r processor*")
            os.system("foamLog log.log")  # Extract residuals from log file
        else:
            print("Invalid solution mode. Please specify either 'serial' or 'parallel'.")
        end_time = time.time()
        elapsed_time = end_time - start_time

        print("Simulation run in {:.2f} minutes.".format(elapsed_time / 60))

    def run_postprocessing(self):
        print("Running post-processing...")
        start_time = time.time()

        # Build the time array based on user parameters or foamListTimes results
        if TIME_STEPS.get("Customized"):  # Safely check for a customized setting
            time_array = _generate_time_array(TIME_STEPS)
        else:
            # Save the current working directory
            original_dir = os.getcwd()

            # Change to the case directory where foamListTimes should be executed
            os.chdir(self.case_directory)  # Ensure this variable is defined in context

            try:
                # Run the foamListTimes command using subprocess
                result = subprocess.check_output(["foamListTimes"], text=True)
                # Process the output: split into lines and remove empty entries
                time_array = [line for line in result.splitlines() if line.strip()]
            except subprocess.CalledProcessError as e:
                print(f"Error running foamListTimes: {e}")
                time_array = []
            except Exception as e:
                print(f"Unexpected error: {e}")
                time_array = []

            # Restore the original directory
            os.chdir(original_dir)

        # Set up environment variables if needed
        os.environ["CASE_TYPE"]   = CASE_TYPE
        os.environ["CASE_PATH"]   = self.case_directory
        os.environ["TIME_ARRAY"]  = ",".join(str(x) for x in time_array)

        # Compute the absolute path to the postProcessParaView.py script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Assuming appDriver.py is in the repo root and SCRIPTS is a subfolder:
        pv_script_path = os.path.join(current_dir, "SCRIPTS", "postProcessParaView.py")

        # Run the ParaView script using pvbatch with the dynamic path
        os.system(f"pvbatch {pv_script_path}")

        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Post-processing done in {elapsed_time/60:.2f} minutes.")

    def run_all(self):
        print("Running all steps...")
        self.run_mesh()
        self.run_bc()
        self.run_simulation()
        self.run_postprocessing()


if __name__ == "__main__":
    # Create the top-level parser
    parser = argparse.ArgumentParser(
        description="Script to manage OpenFOAM simulations.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    # Define the subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    # Subcommand: createCase
    parser_create = subparsers.add_parser('createCase', help='Create the OpenFOAM case setup.')
    # Subcommand: runMesh
    parser_mesh = subparsers.add_parser('runMesh', help='Run mesh generation.')
    # Subcommand: runBC
    parser_bc = subparsers.add_parser('runBC', help='Run boundary conditions setup.')
    # Subcommand: runSimulation
    parser_simulation = subparsers.add_parser('runSimulation', help='Run the simulation.')
    # Subcommand: runPost
    parser_post = subparsers.add_parser('runPost', help='Run post-processing.')
    # Subcommand: runAll
    parser_all = subparsers.add_parser('runAll', help='Run the entire workflow.')
    # Add common arguments if necessary
    parser.add_argument('--geometry', type=str, default=GEOMETRY_CASE,
                        help='Geometry case name.')
    parser.add_argument('--refinement', type=str, default=REFINEMENT,
                        help='Mesh refinement level.')

    # Parse the arguments
    args = parser.parse_args()

    # Create an instance of OpenFOAMRunner
    runner = OpenFOAMRunner(args.geometry, args.refinement)

    # Check if the case directory exists if we're not creating it
    if args.command != 'createCase':
        if not os.path.exists(runner.case_directory):
            print(f"Error: Case directory '{runner.case_directory}' does not exist.")
            sys.exit(1)

    # Execute the corresponding function based on the command
    if args.command == 'createCase':
        runner.create_openfoam_case()
    elif args.command == 'runMesh':
        runner.run_mesh()
    elif args.command == 'runBC':
        runner.run_bc()
    elif args.command == 'runSimulation':
        runner.run_simulation()
    elif args.command == 'runPost':
        runner.run_postprocessing()
    elif args.command == 'runAll':
        runner.run_all()
    else:
        parser.print_help()
