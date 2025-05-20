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
import numpy as np
import tempfile
import json
from scipy.spatial.transform import Rotation as R
from stl import mesh
from SCRIPTS.logger import Logger

# Initialize the logger
log_file_path = os.path.join(os.getcwd(), "AortaCFD.log")
logger = Logger(log_file_path).get_logger()

# Import the unified configuration dictionary
from config import CONFIG

# Import all relevant setup scripts
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
    logger.info(f"Generated time array: {times}")
    return times

def rotate_stl(stl_path, rotation_axis, rotation_angle, output_path):
    """
    Rotates an STL file based on the given rotation axis and angle.

    Args:
        stl_path (str): Path to the input STL file.
        rotation_axis (np.ndarray): The axis of rotation (3D vector).
        rotation_angle (float): The angle of rotation in radians.
        output_path (str): Path to save the rotated STL file.
    """
    try:
        # Load the STL file
        stl_mesh = mesh.Mesh.from_file(stl_path)

        # Create a rotation object
        rotation = R.from_rotvec(rotation_angle * rotation_axis)

        # Apply the rotation to all vertices
        stl_mesh.vectors = rotation.apply(stl_mesh.vectors.reshape(-1, 3)).reshape(-1, 3, 3)

        # Save the rotated STL file
        stl_mesh.save(output_path)
        
    except Exception as e:
        logger.error(f"Error rotating STL file {stl_path}: {e}")
        raise

class OpenFOAMCase:
    """
    Helper class to create an OpenFOAM case for AortaCFD.
    Handles the creation of the case directory, system, constant, and 0 folders.
    """
    def __init__(self):
        try:
            # Pull the OpenFOAM version from the config
            self.openfoam_version = CONFIG["openfoam_version"]

            # Pull in geometry config
            geom_cfg   = CONFIG["geometry"]
            self.geometry_case = geom_cfg["case_name"]
            self.refinement    = geom_cfg["refinement_level"]
            self.GEOMETRY_SCALE = geom_cfg["scale_factor"]

            if not isinstance(self.GEOMETRY_SCALE, (int, float)) or self.GEOMETRY_SCALE <= 0:
                raise ValueError(f"Invalid GEOMETRY_SCALE value: {self.GEOMETRY_SCALE}")
            
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

            # Create the case folder structure and rotate STL files
            rotated_stl_files = self.__create_OFcase()

            # Initialize the geometry analyzer with rotated STL files
            self.geometry_analyzer = GeometryAnalyzer(
                DIRECTORY=self.directory, 
                geometry_case=self.geometry_case, 
                refinement=self.refinement,
                refinement_levels=CONFIG["mesh"]["refinement_levels"],
                snappy_settings=CONFIG["mesh"]["SNAPPY_SETTINGS"],
                stl_files=rotated_stl_files,  # Pass rotated STL files
                geometry_path=os.path.join(self.directory, "constant", "triSurface"),  # Path to rotated STL files
                expansion_factor=CONFIG.get("expansion_factor", 0.02)  # Optional: Pass from config or use default
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
                self.simulation_type,
                self.openfoam_version
            )
            
            self.physical_condition = PhysicalPropertiesWriter(
                self.directory, 
                self.nu, 
                self.rho, 
                self.simulation_type,
                self.openfoam_version
            )

            self.numericalSetup = FvSchemesWriter(
                self.directory, 
                self.simulation_type, 
                self.simulation_performance,
                self.openfoam_version
            )

            self.solverSetup = FvSolutionWriter(
                self.directory, 
                self.simulation_type, 
                self.simulation_performance,
                self.outter_corr,
                self.openfoam_version  
            )

            self.simulationSetup = SimulationSetup(
                self.directory, 
                self.simulation_control,
                self.simulation_type
            )

            self.solnType = SolnType(
                self.directory, 
                self.soln_type, 
                self.subdomains, 
                self.decomposition_method,
                self.openfoam_version
            )
        except Exception as e:
            logger.error(f"Error initializing OpenFOAM case: {e}")
            raise

    def __create_OFcase(self):
        """Creates the OpenFOAM case directory and subdirectories."""
        try:
            if not os.path.exists(self.directory):
                os.makedirs(self.directory)
            else:
                # Remove if exists to ensure a clean directory
                shutil.rmtree(self.directory)
                os.makedirs(self.directory)
            logger.info(f"Directory {self.directory} created.")
            
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

            # Rotate and copy STL files to constant/triSurface folder
            CADfolder = os.path.join("CAD", self.geometry_case)
            if not os.path.exists(CADfolder):
                raise FileNotFoundError(f"CAD folder {CADfolder} does not exist.")
            
            # List all STL files in the CAD directory
            stl_files = [f for f in os.listdir(CADfolder) if f.endswith(".stl")]

            # Find the inlet STL file
            inlet_stl = [f for f in stl_files if "inlet" in f]
            if not inlet_stl:
                raise FileNotFoundError("No inlet STL file found in the CAD directory.")
            inlet_stl = inlet_stl[0]
            inlet_stl_path = os.path.join(CADfolder, inlet_stl)

            # Calculate the rotation vector for the inlet STL
            patch_processor = PatchProcessing(
                DIRECTORY=CADfolder,  # Ensure this points to the CAD directory
                STL_FILES=stl_files,
                PATH_NAME="inlet"
            )
            inlet_center, inlet_radius, inlet_normal = patch_processor.calculate_inlet_center_radius(scale_factor=self.GEOMETRY_SCALE)

            # Compute the rotation vector to align inlet_normal to (0, 0, 1)
            target_normal = np.array([0, 0, 1])
            rotation_axis, rotation_angle = patch_processor.compute_rotation_vector(inlet_normal, target_normal)

            # Rotate and copy all STL files to constant/triSurface
            rotated_stl_files = []
            for stl_file in stl_files:
                src_path = os.path.join(CADfolder, stl_file)
                dst_path = os.path.join(directory_con_tri, stl_file)

                # Rotate the STL file and save it directly in the target directory
                rotate_stl(src_path, rotation_axis, rotation_angle, dst_path)
                
                rotated_stl_files.append(dst_path)

            # Return the list of rotated STL files
            return rotated_stl_files
        except Exception as e:
            logger.error(f"Error creating OpenFOAM case structure: {e}")
            raise

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
        self.openfoam_version = CONFIG["openfoam_version"]
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
        self.FIELDS    = pp_cfg["fields"]
        self.RESCALESETTINGS = pp_cfg.get("rescaleSettings", {})
        self.ANIMATION = pp_cfg["animation"]

    def create_openfoam_case(self):
        """
        Creates an OpenFOAM case with the specified parameters.
        """

        # Create the OpenFOAM case
        my_case = OpenFOAMCase()

        # Call the casePilot method to set up the case
        my_case.casePilot()

    def run_mesh(self):
        """
        Runs the meshing process for AortaCFD.
        Returns:
            None
        """
        logger.info("Running meshing process...")
        start_time = time.time()

        # Change to case directory
        os.chdir(self.case_directory)

        # Run blockMesh
        try:
            subprocess.run(["blockMesh"], stdout=open("blockMesh.log", "w"), stderr=subprocess.STDOUT, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running blockMesh: {e}")
            sys.exit(1)

        # Run surfaceFeatureExtract
        try:
            subprocess.run(["surfaceFeatures"], stdout=open("surfaceFeatures.log", "w"), stderr=subprocess.STDOUT, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running surfaceFeatureExtract: {e}")
            sys.exit(1)

        # Run snappyHexMesh
        if self.SNAPPY_SETTINGS["parallel"]:
            n_proc = self.SNAPPY_SETTINGS["nProcessors"]
            if not isinstance(n_proc, int) or n_proc <= 0:
                raise ValueError(f"Invalid number of processors: {n_proc}")

            decompose_par_dict = os.path.join(self.case_directory, "system", "decomposeParDict")
            if not os.path.isfile(decompose_par_dict):
                raise FileNotFoundError(f"decomposeParDict file not found: {decompose_par_dict}")

            # Suppress foamDictionary output and log it
            try:
                with open("foamDictionary.log", "a") as log_file:
                    subprocess.run(
                        ["foamDictionary", "-entry", "method", "-set", "simple", decompose_par_dict],
                        stdout=log_file, stderr=subprocess.STDOUT, check=True
                    )
                    subprocess.run(
                        ["foamDictionary", "-entry", "numberOfSubdomains", "-set", str(n_proc), decompose_par_dict],
                        stdout=log_file, stderr=subprocess.STDOUT, check=True
                    )
                    subprocess.run(
                        ["foamDictionary", "-entry", "simpleCoeffs/n", "-set", f"(1 1 {n_proc})", decompose_par_dict],
                        stdout=log_file, stderr=subprocess.STDOUT, check=True
                    )
            except subprocess.CalledProcessError as e:
                logger.error(f"Error running foamDictionary: {e}")
                sys.exit(1)

            os.system("decomposePar -noZero -force > decomposePar_snappy.log")
            os.system(f"mpirun -np {n_proc} snappyHexMesh -parallel -overwrite > snappyHex.log")
            os.system("reconstructParMesh -constant -latestTime > reconstructParMesh.log")
            os.system("rm -rf processor*")
        else:
            try:
                subprocess.run(["snappyHexMesh", "-overwrite"], stdout=open("snappyHex.log", "w"), stderr=subprocess.STDOUT, check=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"Error running snappyHexMesh: {e}")
                sys.exit(1)

        # Run checkMesh
        try:
            subprocess.run(["checkMesh"], stdout=open("checkMesh.log", "w"), stderr=subprocess.STDOUT, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running checkMesh: {e}")
            sys.exit(1)

        # Transform points (scaling)
        if not isinstance(self.GEOMETRY_SCALE, (int, float)) or self.GEOMETRY_SCALE <= 0:
            raise ValueError(f"Invalid GEOMETRY_SCALE value: {self.GEOMETRY_SCALE}")
        # os.system(f"transformPoints 'scale=({self.GEOMETRY_SCALE} {self.GEOMETRY_SCALE} {self.GEOMETRY_SCALE})' > transform.log")
        # optional openfoam 8
        os.system(f"transformPoints -scale '({self.GEOMETRY_SCALE} {self.GEOMETRY_SCALE} {self.GEOMETRY_SCALE})' > transform.log")
        os.system("touch f.foam")  # Create a dummy file for ParaView

        elapsed_time = time.time() - start_time
        logger.info(f"Mesh created in {elapsed_time/60:.2f} minutes.")

    def run_bc(self):
        """
        Sets up the boundary conditions for the simulation.
        Returns:
            None
        """
        logger.info("Setting boundary conditions...")
        start_time = time.time()

        # Change to the case directory
        os.chdir(self.case_directory)

        # Get inlet STL file name
        triSurfaceDir = os.path.join("constant", "triSurface")
        stl_files = [f for f in os.listdir(triSurfaceDir) if f.endswith(".stl")]
        inlet_stl = [f for f in stl_files if "inlet" in f]
        if not inlet_stl:
            raise FileNotFoundError("No inlet STL file found in the triSurface directory.")
        inlet_stl = inlet_stl[0].split(".")[0]

        # Write the inlet cell centers to map the inlet velocity
        try:
            os.system("writeMeshObj > meshObj.log")
            os.system("mv patch_inlet_0.obj points-new")
            os.system("rm -rf mesh* patch*")
        except Exception as e:
            raise RuntimeError(f"Error during mesh object writing: {e}")

        # Format the points file
        formatter = EnhancedPointsFormatter(format_version=1)
        formatter.format_coordinates()

        # Create the boundaryData directory for the inlet
        boundaryDataInletDir = os.path.join("constant", "boundaryData", inlet_stl)
        os.makedirs(boundaryDataInletDir, exist_ok=True)

        # Copy the inlet data file
        inlet_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "INLET")
        if self.INLET_DATA_FILE:
            source_file = os.path.join(inlet_dir, self.INLET_DATA_FILE)
            if not os.path.isfile(source_file):
                raise FileNotFoundError(f"INLET_DATA_FILE '{self.INLET_DATA_FILE}' does not exist in '{inlet_dir}'.")
            os.system(f"cp {source_file} {boundaryDataInletDir}")
        else:
            logger.info("No INLET_DATA_FILE specified. Using default values.")
            default_file = os.path.join(inlet_dir, "inletFlowRate.csv")
            if not os.path.isfile(default_file):
                raise FileNotFoundError(f"Default inlet data file '{default_file}' not found.")
            os.system(f"cp {default_file} {boundaryDataInletDir}")

        # Copy the formatted points file
        os.system(f"cp points {boundaryDataInletDir}")
        os.system("rm points")

        # Calculate the inlet radius and center
        inlet_radius_calculator = PatchProcessing(
            DIRECTORY=os.path.join(self.case_directory, "constant", "triSurface"),
            STL_FILES=stl_files,
            PATH_NAME="inlet"
        )
        inlet_center, inlet_radius, inlet_normal = inlet_radius_calculator.calculate_inlet_center_radius(scale_factor=self.GEOMETRY_SCALE)

        # Run inletMapping
        scale_val = float(self.GEOMETRY_SCALE)
        processor = InletMapping(
            center=inlet_center,
            radius=inlet_radius,
            inlet_data_file=self.INLET_DATA_FILE,
            data_type=self.INLET_DATA_TYPE,
            inlet_name="inlet",
            orientation=self.INLET_ORIENTATION,
            profile=self.INLET_PROFILE
        )
        processor.run()

        # Run cycleDataSetup
        cycle_data = CycleDataSetup(
            INELT_DATA_FILE=self.INLET_DATA_FILE,
            cardiacCycle=float(processor.cardiac_cycle),
            numberOfCycle=int(self.NUMBER_OF_CYCLES)
        )
        cycle_data.execute()

        # Windkessel setup (if applicable)
        if self.BC_OUTLET == "3EWINDKESSEL":
            wk_setup = wk_Setup(
                DIRECTORY=self.case_directory,
                GEOMETRY_SCALE=scale_val,
                STL_FILES=stl_files,
                WK_SETTING=self.WK_SETTING,
                CARDIAC_CYCLE=float(processor.cardiac_cycle),
                INLET_DATA_FILE=self.INLET_DATA_FILE,
                DATA_TYPE=self.INLET_DATA_TYPE,
                OPENFOAM_VERSION=self.openfoam_version
            )
            wk_setup.write_WK_Setup()

        # Format the points file for timeVaryingMappedFixedValue BC
        formatter = EnhancedPointsFormatter(format_version=2)
        formatter.format_coordinates()
        os.system(f"cp points {boundaryDataInletDir}")

        # # Renumber the mesh (optional)
        # try:
        #     os.system("renumberMesh -overwrite -noZero > renumberMesh.log")
        # except Exception as e:
        #     raise RuntimeError(f"Error during renumberMesh: {e}")

        elapsed_time = time.time() - start_time
        logger.info(f"Boundary condition setup completed in {elapsed_time / 60:.2f} minutes.")

    def run_simulation(self, latest_time=False, specific_time=None, end_time=None):
        """
        Runs the simulation based on the specified solution type.
        Args:
            latest_time (bool): If True, run the simulation starting from the latest time.
            specific_time (str): If provided, run the simulation starting from the specified time.
            end_time (str): If provided, specify the end time for the simulation.
        Returns:
            None
        """
        logger.info("Running simulation...")
        start_time = time.time()

        os.chdir(self.case_directory)

        decompose_par_dict = os.path.join(self.case_directory, "system", "decomposeParDict")
        if not os.path.isfile(decompose_par_dict):
            raise FileNotFoundError(f"decomposeParDict file not found: {decompose_par_dict}")

        if self.SOLN_TYPE == "parallel" and (not isinstance(self.SUBDOMAINS, int) or self.SUBDOMAINS <= 0):
            logger.error("Error: Invalid number of subdomains for parallel execution.")
            sys.exit(1)

        # Build the simulation command
        simulation_command = "pimpleFoam"
        if self.BC_OUTLET == "3EWINDKESSEL":
            simulation_command = "pimpleFoam_WK_2.0" # OpenFOAM8 is name as pimpleFoam_WK_2.0 OF10 is pimpleFoam_WK_2.1

        # Build the decomposePar command
        decompose_command = "decomposePar -force"
        if latest_time:
            decompose_command += " -latestTime"
        elif specific_time:
            decompose_command += f" -time {specific_time}"

        if self.SOLN_TYPE == "serial":
            os.system(f"{simulation_command} > log.log")
        elif self.SOLN_TYPE == "parallel":
            # Adjust decomposeParDict for parallel execution
            try:
                with open("foamDictionary.log", "a") as log_file:
                    subprocess.run(
                        ["foamDictionary", "-entry", "numberOfSubdomains", "-set", str(self.SUBDOMAINS), decompose_par_dict],
                        stdout=log_file, stderr=subprocess.STDOUT, check=True
                    )
                    subprocess.run(
                        ["foamDictionary", "-entry", "simpleCoeffs/n", "-set", f"(1 1 {self.SUBDOMAINS})", decompose_par_dict],
                        stdout=log_file, stderr=subprocess.STDOUT, check=True
                    )
            except subprocess.CalledProcessError as e:
                logger.error(f"Error running foamDictionary: {e}")
                sys.exit(1)

            os.system(f"{decompose_command} > decompose.log")
            os.system(f"mpirun -np {self.SUBDOMAINS} {simulation_command} -parallel > log.log")
            os.system("reconstructPar > reconstruct.log")
            os.system("rm -rf processor*")
            os.system("foamLog log.log")  # Extract residuals from log file
        else:
            logger.error("Invalid solution mode. Please specify either 'serial' or 'parallel'.")

        elapsed_time = time.time() - start_time
        logger.info(f"Simulation run in {elapsed_time/60:.2f} minutes.")

    def run_postprocessing(self, reAnimate=False):
        """
        Example: run ParaView-based post-processing from a parent directory.
        Ensures we can find postProcessParaView.py even if not co-located with this code.
        """
        logger.info("Running post-processing...")
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
                logger.error(f"Error running foamListTimes: {e}")
                time_array = []
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time_array = []
            finally:
                os.chdir(original_dir)

        # 2) Set environment variables for the ParaView script
        os.environ["CASE_TYPE"]  = self.CASE_TYPE
        os.environ["CASE_PATH"]  = self.case_directory
        os.environ["TIME_ARRAY"] = ",".join(str(x) for x in time_array)
        os.environ["REANIMATION"] = str(reAnimate)
        os.environ["FIELDS"]     = ",".join(self.FIELDS)
        # Save rescale settings as temp JSON file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
            json.dump(self.RESCALESETTINGS, temp_file)
            os.environ["RESCALE_JSON"] = temp_file.name
        os.environ["ANIMATION_ENABLEd"]  = str(self.ANIMATION["enabled"])
        os.environ["FPS"]        = str(self.ANIMATION["fps"]) if self.ANIMATION["fps"] else "None"

        script_path = os.path.join(self.parent_directory , "SCRIPTS", "postProcessParaView.py")
        pvbatch_exe = CONFIG["post_processing"]["pvbatch_exe"]
        if not os.path.isfile(pvbatch_exe):
            raise FileNotFoundError(f"ParaView executable '{pvbatch_exe}' not found.")
        if not os.path.isfile(script_path):
            raise FileNotFoundError(f"Post-processing script '{script_path}' not found.")
        # 3) Run the ParaView script
        cmd = f"{pvbatch_exe} {script_path}"
        os.system(cmd)
        
        elapsed_time = time.time() - start_time
        #logger.info(f"Post-processing done in {elapsed_time/60:.2f} minutes.")

    def run_all(self):
        """
        Runs all steps of the simulation pipeline.
        """
        logger.info("Running entire workflow: mesh, BC, simulation, post-processing...")
        self.create_openfoam_case()
        self.run_mesh()
        self.run_bc()
        self.run_simulation()
        self.run_postprocessing()

if __name__ == "__main__":
    try:
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
        run_simulation_parser = subparsers.add_parser('runSimulation', help='Run the simulation.')
        run_simulation_parser.add_argument('--latestTime', action='store_true', help='Run simulation starting from the latest time.')
        run_simulation_parser.add_argument('--time', type=str, help='Specify the start time for the simulation.')
        run_simulation_parser.add_argument('--endTime', type=str, help='Specify the end time for the simulation.')

        # Subcommand: runPost
        run_post_parser = subparsers.add_parser('runPost', help='Run post-processing.')
        run_post_parser.add_argument('--reAnimate', dest='reAnimate', action='store_true', help='Force re-generation of animation.')
        run_post_parser.set_defaults(reAnimate=False)

        # Subcommand: runAll
        subparsers.add_parser('runAll', help='Run the entire workflow.')

        # Optional overrides
        parser.add_argument('--geometry', type=str, help='Override geometry case name.')
        parser.add_argument('--refinement', type=str, help='Override mesh refinement level.')

        args = parser.parse_args()

        # Validate command
        if not args.command:
            parser.print_help()
            sys.exit(1)

        # Override config if specified
        if args.geometry:
            if args.geometry not in CONFIG["geometry"]["valid_cases"]:
                logger.error(f"Error: Invalid geometry case '{args.geometry}'.")
                sys.exit(1)
            CONFIG["geometry"]["case_name"] = args.geometry

        if args.refinement:
            if args.refinement not in CONFIG["mesh"]["refinement_levels"]:
                logger.error(f"Error: Invalid refinement level '{args.refinement}'.")
                sys.exit(1)
            CONFIG["geometry"]["refinement_level"] = args.refinement

        # Execute command
        runner = OpenFOAMRunner()
        if args.command == 'createCase':
            runner.create_openfoam_case()
        else:
            if not os.path.exists(runner.case_directory):
                logger.error(f"Error: Case directory '{runner.case_directory}' does not exist.")
                sys.exit(1)

            if args.command == 'runMesh':
                runner.run_mesh()
            elif args.command == 'runBC':
                runner.run_bc()
            elif args.command == 'runSimulation':
                runner.run_simulation(
                    latest_time=args.latestTime,
                    specific_time=args.time,
                    end_time=args.endTime
                )
            elif args.command == 'runPost':
                runner.run_postprocessing(reAnimate=args.reAnimate)
            elif args.command == 'runAll':
                runner.run_all()
            else:
                parser.print_help()
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        sys.exit(1)
