#!/usr/bin/env python3.10
"""
appDriver.py
------------
Main pilot file for running the Aorta CFD case using a single config.py.
"""

import sys
import os
import time
import shutil
import argparse
import subprocess

# Import the unified configuration dictionary
from config import CONFIG

# Import all relevant setup scripts (unchanged from your original code)
from SCRIPTS.meshSetup import GeometryAnalyzer
from SCRIPTS.boundaryConditionSetup import BoundaryConditionSetup
from SCRIPTS.physicalProperitesSetup import PhysicalPropertiesWriter
from SCRIPTS.numericalSetup import FvSchemesWriter
from SCRIPTS.solverSetup import FvSolutionWriter
from SCRIPTS.simulationSetup import SimulationSetup
from SCRIPTS.inletMapping import InletMapping
from SCRIPTS.patchProcessing import PatchProcessing
from SCRIPTS.cycleDataSetup import CycleDataSetup
from SCRIPTS.solnTypeSetup import SolnType
from SCRIPTS.wkSetup import wk_Setup
from SCRIPTS.formatPoints import EnhancedPointsFormatter

def _generate_time_array(time_steps_dict):
    """
    Generates an array of time values based on the dictionary specifying
    start, end, and step. 
    """
    start = float(time_steps_dict["START"])
    end = float(time_steps_dict["END"])
    step = float(time_steps_dict["STEP"])

    times = []
    val = start
    while val <= end + 1e-12:
        times.append(round(val, 4))
        val += step
    return times


class OpenFOAMCase:
    """
    Helper class to create an OpenFOAM case for AortaCFD.
    Handles the creation of the case directory, system, constant, and 0 folders.
    """
    def __init__(self):
        # Pull in geometry config
        geom_cfg   = CONFIG["geometry"]
        self.geometry_case = geom_cfg["case_name"]
        self.refinement    = geom_cfg["refinement_level"]
        
        # Create the actual case directory name
        # e.g., "OPENFOAM/geometry1_coarse"
        self.directory = os.path.join(
            os.getcwd(), 
            "OPENFOAM", 
            f"{self.geometry_case}_{self.refinement}"
        )

        # Boundary config
        boundary_cfg = CONFIG["boundary"]
        self.BC_INLET  = boundary_cfg["BC_INLET"]
        self.BC_OUTLET = boundary_cfg["BC_OUTLET"]

        # Physics config
        phys_cfg = CONFIG["physics"]
        self.nu  = phys_cfg["nu"]
        self.rho = phys_cfg["rho"]
        self.simulation_type        = phys_cfg["simulation_type"]
        self.simulation_performance = phys_cfg["simulation_performance"]
        self.outter_corr            = phys_cfg["outter_correction_loop"]

        # Simulation control config
        sim_ctrl_cfg     = CONFIG["simulation_control"]
        self.simulation_control = sim_ctrl_cfg

        # Run settings (solver type, parallelization, etc.)
        run_cfg       = CONFIG["run_settings"]
        self.soln_type          = run_cfg["solution_type"]
        self.subdomains         = run_cfg["subdomains"]
        self.decomposition_method = run_cfg["decomposition_method"]

        # Initial conditions
        init_cfg = CONFIG["initial_conditions"]
        self.initial_condition_U     = init_cfg["velocity"]
        self.initial_condition_p     = init_cfg["pressure"]
        self.initial_condition_K     = init_cfg["k"]    
        self.initial_condition_omega = init_cfg["omega"]

        # Create the case folder structure
        self.__create_OFcase()

        # Initialize the geometry analyzer
        self.geometry_analyzer = GeometryAnalyzer(
            DIRECTORY=self.directory, 
            geometry_case=self.geometry_case, 
            refinement=self.refinement,
            refinement_levels=CONFIG["mesh"]["refinement_levels"],
            snappy_settings=CONFIG["mesh"]["SNAPPY_SETTINGS"]
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
            self.simulation_performance
        )

        self.solverSetup = FvSolutionWriter(
            self.directory, 
            self.simulation_type, 
            self.simulation_performance,
            self.outter_corr  
        )

        self.simulationSetup = SimulationSetup(
            self.directory, 
            self.simulation_control
        )

        self.solnType = SolnType(
            self.directory, 
            self.soln_type, 
            self.subdomains, 
            self.decomposition_method
        )

    def __create_OFcase(self):
        """Creates the OpenFOAM case directory and subdirectories."""
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
            os.makedirs(directory, exist_ok=True)
        
        # create constant/triSurface folder
        directory_con_tri = os.path.join(self.directory, "constant", "triSurface")
        os.makedirs(directory_con_tri, exist_ok=True)

        # create constant/boundaryData folder
        directory_con_bd = os.path.join(self.directory, "constant", "boundaryData")
        os.makedirs(directory_con_bd, exist_ok=True)

        # Copy STL files to constant/triSurface folder
        CADfolder = os.path.join("CAD", self.geometry_case)
        if not os.path.exists(CADfolder):
            raise FileNotFoundError(f"CAD folder {CADfolder} does not exist.")
        for f in os.listdir(CADfolder):
            src = os.path.join(CADfolder, f)
            dst = os.path.join(directory_con_tri, f)
            shutil.copy(src, dst)

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
           
    def casePilot(self):
        """
        Call all setup writers:
            1. Geometry (blockMesh, snappyHexMesh)
            2. Boundary (U, p, etc.)
            3. Physical properties
            4. Numerical setup
            5. Solver setup
            6. Simulation control
            7. Decompose par (parallel)
        """
        self.write_geometry_files()
        self.write_boundary_conditions()
        self.write_physical_properties()
        self.write_numericalSetup()
        self.write_solverSetup()
        self.write_simulationSetup()
        self.write_decomposeParDict()


class OpenFOAMRunner:
    """
    Manages the OpenFOAM simulation workflow for AortaCFD.
    """
    def __init__(self):
        geom_cfg = CONFIG["geometry"]
        self.geometry_case = geom_cfg["case_name"]
        self.refinement    = geom_cfg["refinement_level"]
        self.case_directory = os.path.join(
            os.getcwd(), 
            "OPENFOAM", 
            f"{self.geometry_case}_{self.refinement}"
        )
        # save the parents directory 
        self.parent_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)))

        boundary_cfg = CONFIG["boundary"]
        self.BC_INLET     = boundary_cfg["BC_INLET"]
        self.BC_OUTLET    = boundary_cfg["BC_OUTLET"]
        self.INLET_DATA_FILE = boundary_cfg.get("INLET_DATA_FILE", None)
        self.INLET_DATA_TYPE = boundary_cfg["INLET_DATA_TYPE"]
        self.INLET_ORIENTATION = boundary_cfg.get("INLET_ORIENTATION")
        self.INLET_PROFILE   = boundary_cfg.get("INLET_PROFILE", None)
        self.WK_SETTING      = boundary_cfg["WK_SETTING"]

        phys_cfg = CONFIG["physics"]
        self.simulation_type = phys_cfg["simulation_type"]

        sim_ctrl_cfg = CONFIG["simulation_control"]
        self.CARDIAC_CYCLE  = sim_ctrl_cfg["cardiac_cycle"]
        self.NUMBER_OF_CYCLES = sim_ctrl_cfg["number_of_cycles"]

        run_cfg = CONFIG["run_settings"]
        self.SOLN_TYPE        = run_cfg["solution_type"]
        self.SUBDOMAINS       = run_cfg["subdomains"]

        # Mesh config
        mesh_cfg         = CONFIG["mesh"]["SNAPPY_SETTINGS"]
        self.SNAPPY_SETTINGS = mesh_cfg

        # For geometry scale (if using transformPoints)
        self.GEOMETRY_SCALE = geom_cfg["scale_factor"]

        # For post-processing
        pp_cfg  = CONFIG["post_processing"]
        self.TIME_STEPS = pp_cfg["time_steps"]
        self.CASE_TYPE  = pp_cfg["case_type"]

    def create_openfoam_case(self):
        """
        Creates an OpenFOAM case with the specified parameters.
        Returns:
            None
        """
        print("Creating OpenFOAM case...")
        my_case = OpenFOAMCase()
        my_case.casePilot()
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
        if self.SNAPPY_SETTINGS["parallel"]:
            n_proc = self.SNAPPY_SETTINGS["nProcessors"]
            # Overwrite decomposition method for snappyHexMesh
            os.system(f"foamDictionary -entry 'method' -set 'simple' system/decomposeParDict")
            os.system(f"foamDictionary -entry 'numberOfSubdomains' -set '{n_proc}' system/decomposeParDict")
            os.system(f"foamDictionary -entry 'simpleCoeffs/n' -set '(1 1 {n_proc})' system/decomposeParDict")
            os.system("decomposePar -noZero -force > decomposePar_snappy.log")
            os.system(f"mpirun -np {n_proc} snappyHexMesh -parallel -overwrite > snappyHex.log")
            os.system("reconstructParMesh -constant -latestTime > reconstructParMesh.log")
            os.system("rm -rf processor*")
        else:
            os.system("snappyHexMesh -overwrite > snappyHex.log")

        # run checkMesh
        os.system("checkMesh > checkMesh.log")

        # transformPoints (scaling)
        os.system(f"transformPoints 'scale=({self.GEOMETRY_SCALE} {self.GEOMETRY_SCALE} {self.GEOMETRY_SCALE})' > transform.log")

        # renumberMesh
        os.system("renumberMesh -overwrite > renumberMesh.log")

        # Create a dummy file f.foam for ParaView
        os.system("touch f.foam")

        elapsed_time = time.time() - start_time
        print(f"Mesh created in {elapsed_time/60:.2f} minutes.")

    def run_bc(self):
        """
        Sets up the boundary conditions for the simulation.
        Returns:
            None
        """
        print("Setting boundary conditions...")
        start_time = time.time()

        os.chdir(self.case_directory)

        # get inlet stl file name
        triSurfaceDir = os.path.join("constant", "triSurface")
        stl_files = [f for f in os.listdir(triSurfaceDir) if f.endswith(".stl")]
        inlet_stl = [f for f in stl_files if "inlet" in f][0].split(".")[0]

        # write the inlet cell centers to map the inlet velocity
        os.system("writeMeshObj > meshObj.log")
        os.system("mv patch_inlet_0.obj points-new")
        os.system("rm -rf mesh* patch*")

        formatter = EnhancedPointsFormatter(format_version=1)
        formatter.format_coordinates()
        boundaryDataInletDir = os.path.join("constant", "boundaryData", inlet_stl)
        os.makedirs(boundaryDataInletDir, exist_ok=True)
        
        # get directory of current location and level up
        inlet_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),"INLET")

        if self.INLET_DATA_FILE:
            source_file = os.path.join(inlet_dir, self.INLET_DATA_FILE)
            if not os.path.isfile(source_file):
                raise FileNotFoundError(f"INLET_DATA_FILE '{self.INLET_DATA_FILE}' does not exist in '{inlet_dir}'.")
            os.system(f"cp {source_file} {boundaryDataInletDir}")
        else:
            print("No INLET_DATA_FILE specified. using default values.")
            os.system(f"cp {os.path.join(inlet_dir, 'inletFlowRate.csv')} {boundaryDataInletDir}")
        os.system(f"cp points {boundaryDataInletDir}")
        os.system("rm points")

        # Calculate the inlet radius
        inlet_radius_calculator = PatchProcessing(
            DIRECTORY=self.case_directory,
            STL_FILES=stl_files,
            PATH_NAME="inlet"
        )
        inlet_center, inlet_radius, inlet_normal = inlet_radius_calculator.calculate_inlet_center_radius(scale_factor=self.GEOMETRY_SCALE)

        # run inletMapping
        scale_val = float(self.GEOMETRY_SCALE)
        processor = InletMapping(
            center=inlet_center,
            radius=inlet_radius,
            inlet_data_file=self.INLET_DATA_FILE,
            data_type= self.INLET_DATA_TYPE,
            inlet_name= "inlet",
            orientation= self.INLET_ORIENTATION,    
            profile=self.INLET_PROFILE
        )
        processor.run()

        # run cycleDataSetup
        cycle_data = CycleDataSetup(
            INELT_DATA_FILE=self.INLET_DATA_FILE,
            cardiacCycle= float(processor.cardiac_cycle),
            numberOfCycle=int(self.NUMBER_OF_CYCLES)
        )
        cycle_data.execute()

        # Windkessel setup
        if self.BC_OUTLET == "3EWINDKESSEL":
            wk_setup = wk_Setup(
                DIRECTORY=self.case_directory,
                GEOMETRY_SCALE = scale_val,
                STL_FILES=stl_files,
                WK_SETTING=self.WK_SETTING,
                CARDIAC_CYCLE = float(processor.cardiac_cycle),
                INLET_DATA_FILE=self.INLET_DATA_FILE,
                DATA_TYPE= self.INLET_DATA_TYPE,
            )
            wk_setup.write_WK_Setup()

        # Format "points" file to match timeVaryingMappedFixedValue BC requirements
        formatter = EnhancedPointsFormatter(format_version=2)
        formatter.format_coordinates()
        os.system(f"cp points {boundaryDataInletDir}")

        elapsed_time = time.time() - start_time
        print(f"Boundary condition set in {elapsed_time/60:.2f} minutes.")

    def run_simulation(self):
        """
        Runs the simulation based on the specified solution type.
        Returns:
            None
        """
        print("Running simulation...")
        start_time = time.time()

        os.chdir(self.case_directory)

        if self.SOLN_TYPE == "serial":
            if self.BC_OUTLET == "3EWINDKESSEL":
                os.system("pimpleFoam_WK_2.1 > log.log")  # Adjust as needed
            else:
                os.system("pimpleFoam > log.log")
        elif self.SOLN_TYPE == "parallel":
            os.system("decomposePar -force -latestTime > decompose.log")
            if self.BC_OUTLET == "3EWINDKESSEL":
                os.system(f"mpirun -np {self.SUBDOMAINS} pimpleFoam_WK_2.1 -parallel  > log.log")
            else:
                os.system(f"mpirun -np {self.SUBDOMAINS} pimpleFoam -parallel > log.log")
            os.system("reconstructPar > reconstruct.log")
            os.system("rm -rf processor*")
            os.system("foamLog log.log")  # Extract residuals from log file
        else:
            print("Invalid solution mode. Please specify either 'serial' or 'parallel'.")

        elapsed_time = time.time() - start_time
        print(f"Simulation run in {elapsed_time/60:.2f} minutes.")

    def run_postprocessing(self):
        """
        Example: run ParaView-based post-processing from a parent directory.
        Ensures we can find postProcessParaView.py even if not co-located with this code.
        """
        print("Running post-processing...")
        start_time = time.time()

        # 1) Build the time array (either customized or from foamListTimes).
        if self.TIME_STEPS.get("Customized"):
            time_array = _generate_time_array(self.TIME_STEPS)  # your function
        else:
            # If not customized, try to get times from foamListTimes
            original_dir = os.getcwd()
            os.chdir(self.case_directory)
            try:
                result = subprocess.check_output(["foamListTimes"], text=True)
                time_array = [line.strip() for line in result.splitlines() if line.strip()]
            except subprocess.CalledProcessError as e:
                print(f"Error running foamListTimes: {e}")
                time_array = []
            except Exception as e:
                print(f"Unexpected error: {e}")
                time_array = []
            finally:
                os.chdir(original_dir)

        # 2) Set environment variables for the ParaView script
        os.environ["CASE_TYPE"]  = self.CASE_TYPE
        os.environ["CASE_PATH"]  = self.case_directory
        os.environ["TIME_ARRAY"] = ",".join(str(x) for x in time_array)

        script_path = os.path.join(self.parent_directory , "SCRIPTS", "postProcessParaView.py")
        pvbatch_exe = "/home/jie/ParaView-5.11.2-MPI-Linux-Python3.9-x86_64/bin/pvbatch"   # Adjust as needed
        if not os.path.isfile(pvbatch_exe):
            raise FileNotFoundError(f"ParaView executable '{pvbatch_exe}' not found.")
        if not os.path.isfile(script_path):
            raise FileNotFoundError(f"Post-processing script '{script_path}' not found.")
        # 3) Run the ParaView script
        cmd = f"{pvbatch_exe} {script_path}"
        os.system(cmd)

        elapsed_time = time.time() - start_time
        print(f"Post-processing done in {elapsed_time/60:.2f} minutes.")

    def run_all(self):
        """
        Runs all steps of the simulation pipeline.
        """
        print("Running entire workflow: mesh, BC, simulation, post-processing...")
        self.run_mesh()
        self.run_bc()
        self.run_simulation()
        self.run_postprocessing()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Script to manage OpenFOAM simulations (Aorta CFD).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Subcommand: createCase
    subparsers.add_parser('createCase', help='Create the OpenFOAM case setup.')
    # Subcommand: runMesh
    subparsers.add_parser('runMesh', help='Run mesh generation.')
    # Subcommand: runBC
    subparsers.add_parser('runBC', help='Run boundary conditions setup.')
    # Subcommand: runSimulation
    subparsers.add_parser('runSimulation', help='Run the simulation.')
    # Subcommand: runPost
    subparsers.add_parser('runPost', help='Run post-processing.')
    # Subcommand: runAll
    subparsers.add_parser('runAll', help='Run the entire workflow.')
    
    # (Optional) Add arguments that override config.py values
    parser.add_argument('--geometry', type=str, help='Override geometry case name.')
    parser.add_argument('--refinement', type=str, help='Override mesh refinement level.')

    args = parser.parse_args()

    # Decide whether to override config values from CLI
    if args.geometry:
        CONFIG["geometry"]["case_name"] = args.geometry
    if args.refinement:
        CONFIG["geometry"]["refinement_level"] = args.refinement

    # If 'createCase', build the base folder structure + dicts
    if args.command == 'createCase':
        runner_case = OpenFOAMCase()
        runner_case.casePilot()
    else:
        # For other commands, we assume the case has already been created
        runner = OpenFOAMRunner()
        if not os.path.exists(runner.case_directory) and args.command != 'createCase':
            print(f"Error: Case directory '{runner.case_directory}' does not exist.")
            sys.exit(1)

        # Route subcommands
        if args.command == 'runMesh':
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
