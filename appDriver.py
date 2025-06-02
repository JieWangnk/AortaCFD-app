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
from SCRIPTS.meshSetup_2V import GeometryAnalyzer
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

class AortaCFDError(Exception):
    """Custom exception for AortaCFD errors."""
    pass

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
    def __init__(self, clean=True):
        try:
            # Pull the OpenFOAM version from the config
            self.openfoam_version = CONFIG["openfoam_version"]
            # Pull in geometry config
            geom_cfg   = CONFIG["geometry"]
            self.geometry_case = geom_cfg["case_name"]
            self.refinement    = geom_cfg["refinement_level"]
            self.GEOMETRY_SCALE = geom_cfg["scale_factor"]
            self.rotate_stl_files = geom_cfg.get("rotation", True)
            self.target_normal = np.array(geom_cfg.get("target_normal", [0, 0, 1]))
            self.clean = clean
            self.CARDIAC_CYCLE = None 

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
            rotated_stl_files = self.__create_OFcase(clean=self.clean)

            # Initialize the geometry analyzer with rotated STL files
            self.geometry_analyzer = GeometryAnalyzer(
                DIRECTORY=self.directory, 
                geometry_case_name_from_config=geom_cfg["case_name"], 
                refinement_level_key=geom_cfg["refinement_level"],
                refinement_levels_dict=CONFIG["mesh"]["refinement_levels"],
                snappy_settings_dict=CONFIG["mesh"]["SNAPPY_SETTINGS"],
                rotated_stl_basenames=rotated_stl_files,  # Pass rotated STL files
                path_to_trisurface_dir=os.path.join(self.directory, "constant", "triSurface"),  # Path to rotated STL files
                expansion_factor=CONFIG.get("expansion_factor", 0.02),  
                log_file= os.path.join(self.directory, "geometry_analyzer.log"),
                global_config= CONFIG
            )
            
            self.boundary_condition = BoundaryConditionSetup(
                self.directory, 
                self.geometry_analyzer.stl_filenames, 
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
                self.openfoam_version
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

    def __create_OFcase(self,clean=True):
        """Creates the OpenFOAM case directory and subdirectories."""
        try:
            if not os.path.exists(self.directory):
                os.makedirs(self.directory)
            elif self.clean:
                # Remove if exists to ensure a clean directory
                shutil.rmtree(self.directory)
                os.makedirs(self.directory)
            
            # Create system, constant, and 0 folders
            for f in ["system", "constant", "0"]:
                directory = os.path.join(self.directory, f)
                os.makedirs(directory, exist_ok=True)
            
            # Create constant/triSurface folder
            directory_con_tri = os.path.join(self.directory, "constant", "triSurface")
            os.makedirs(directory_con_tri, exist_ok=True)

            # Create constant/boundaryData folder
            directory_con_bd = os.path.join(self.directory, "constant", "boundaryData")
            os.makedirs(directory_con_bd, exist_ok=True)

            # Rotate and copy STL files to constant/triSurface folder
            CADfolder = os.path.join("CAD", self.geometry_case)
            if not os.path.exists(CADfolder):
                raise FileNotFoundError(f"CAD folder {CADfolder} does not exist.")
            
            # List all STL files in the CAD directory
            stl_files = [f for f in os.listdir(CADfolder) if f.endswith(".stl")]

            # Rotate and copy all STL files to constant/triSurface
            rotated_stl_files = []
            if self.rotate_stl_files:
                inlet_stl = None
                for stl_file in stl_files:
                    if "inlet" in stl_file.lower():
                        inlet_stl = stl_file
                        break
                
                if not inlet_stl:
                    raise FileNotFoundError("No inlet STL file found for rotation.")

                # Calculate rotation for the inlet STL
                inlet_path = os.path.join(CADfolder, inlet_stl)
                patch_processor = PatchProcessing(
                    DIRECTORY=CADfolder,
                    STL_FILES=[inlet_stl],
                    PATH_NAME="inlet"
                )
                inlet_normal = patch_processor.compute_average_normal()
                rotation_vector, rotation_angle = patch_processor.compute_rotation_vector(
                    inlet_normal, self.target_normal
                )
                
                # Rotate all STL files
                for stl_file in stl_files:
                    src_path = os.path.join(CADfolder, stl_file)
                    dst_path = os.path.join(directory_con_tri, stl_file)
                    rotate_stl(src_path, rotation_vector, rotation_angle, dst_path)
                    rotated_stl_files.append(dst_path)
            else:
                # Copy STL files without rotation
                for stl_file in stl_files:
                    src_path = os.path.join(CADfolder, stl_file)
                    dst_path = os.path.join(directory_con_tri, stl_file)
                    shutil.copy(src_path, dst_path)
                    rotated_stl_files.append(dst_path)

            # Return the list of rotated STL files
            return rotated_stl_files
        except Exception as e:
            logger.error(f"Error creating OpenFOAM case structure: {e}")
            raise

    def write_geometry_files(self):
        self.geometry_analyzer.write_blockMeshDict()
        self.geometry_analyzer.write_surfaceFeaturesDict()
        self.geometry_analyzer.write_snappyHexMeshDict()
        print(f"Principal axis found: {self.geometry_analyzer.principal_aortic_axis}")

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
    def __init__(self, simulationSetup, cardiac_cycle=None):
        self.simulationSetup = simulationSetup  # Use the passed simulationSetup instance
        self.CARDIAC_CYCLE = cardiac_cycle
        self.openfoam_version = CONFIG["openfoam_version"]
        geom_cfg = CONFIG["geometry"]
        self.geometry_case = geom_cfg["case_name"]
        self.refinement = geom_cfg["refinement_level"]
        self.case_directory = os.path.join(
            os.getcwd(),
            "OPENFOAM",
            f"{self.geometry_case}_{self.refinement}"
        )
        self.parent_directory = os.path.dirname(os.path.abspath(__file__))

        boundary_cfg = CONFIG["boundary"]
        self.BC_INLET = boundary_cfg["BC_INLET"]
        self.BC_OUTLET = boundary_cfg["BC_OUTLET"]
        self.INLET_DATA_FILE = boundary_cfg.get("INLET_DATA_FILE", None)
        self.INLET_DATA_TYPE = boundary_cfg["INLET_DATA_TYPE"]
        self.INLET_ORIENTATION = boundary_cfg.get("INLET_ORIENTATION")
        self.INLET_PROFILE = boundary_cfg.get("INLET_PROFILE", None)
        self.WK_SETTING = boundary_cfg["WK_SETTING"]

        phys_cfg = CONFIG["physics"]
        self.simulation_type = phys_cfg["simulation_type"]
        self.rho_val = phys_cfg["rho"]
        self.nu_val = phys_cfg["nu"]

        sim_ctrl_cfg = CONFIG["simulation_control"]
        self.sim_ctrl_cfg = sim_ctrl_cfg
        self.NUMBER_OF_CYCLES = sim_ctrl_cfg["number_of_cycles"]

        run_cfg = CONFIG["run_settings"]
        self.SOLN_TYPE = run_cfg["solution_type"]
        self.SUBDOMAINS = run_cfg["subdomains"]

        mesh_cfg = CONFIG["mesh"]["SNAPPY_SETTINGS"]
        self.SNAPPY_SETTINGS = mesh_cfg

        self.GEOMETRY_SCALE = geom_cfg["scale_factor"]

        pp_cfg = CONFIG["post_processing"]
        self.TIME_STEPS = pp_cfg["time_steps"]
        self.CASE_TYPE = pp_cfg["case_type"]
        self.FIELDS = pp_cfg["fields"]
        self.RESCALESETTINGS = pp_cfg.get("rescaleSettings", {})
        self.ANIMATION = pp_cfg["animation"]

    def _run_command(self, command, log_file, cwd=None):
        """
        Helper function to run a shell command using subprocess.run().
        Args:
            command (list): Command to execute as a list of arguments.
            log_file (str): Path to the log file to capture stdout and stderr.
            cwd (str): Working directory for the command.
        """
        try:
            with open(log_file, "w") as log:
                subprocess.run(
                    command,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                    text=True,
                    cwd=cwd
                )
        except subprocess.CalledProcessError as e:
            logger.error(f"Command '{' '.join(command)}' failed. See {log_file} for details.")
            raise AortaCFDError(f"Command '{' '.join(command)}' failed. Check {log_file} for details.")

    def run_mesh(self):
        """
        Runs the meshing process for AortaCFD.
        """
        start_time = time.time()
        logger.info("Running mesh generation...")
        self._run_command(
            ["blockMesh"],
            os.path.join(self.case_directory, "blockMesh.log"),
            cwd=self.case_directory
        )
        self._run_command(
            ["surfaceFeatures"],
            os.path.join(self.case_directory, "surfaceFeatures.log"),
            cwd=self.case_directory
        )

        # Run snappyHexMesh
        if self.SNAPPY_SETTINGS["parallel"]:
            n_proc = self.SNAPPY_SETTINGS["nProcessors"]
            if not isinstance(n_proc, int) or n_proc <= 0:
                raise ValueError(f"Invalid number of processors: {n_proc}")

            decompose_par_dict = os.path.join(self.case_directory, "system", "decomposeParDict")
            if not os.path.isfile(decompose_par_dict):
                raise FileNotFoundError(f"decomposeParDict file not found: {decompose_par_dict}")

            # Adjust decomposeParDict for parallel execution
            self._run_command(
                ["foamDictionary", "-entry", "numberOfSubdomains", "-set", str(n_proc), decompose_par_dict],
                os.path.join(self.case_directory, "foamDictionary.log"),
                cwd=self.case_directory
            )
            self._run_command(
                ["foamDictionary", "-entry", "simpleCoeffs/n", "-set", f"(1 1 {n_proc})", decompose_par_dict],
                os.path.join(self.case_directory, "foamDictionary.log"),
                cwd=self.case_directory
            )

            # Run decomposePar
            self._run_command(
                ["decomposePar", "-noZero", "-force"],
                os.path.join(self.case_directory, "decomposePar.log"),
                cwd=self.case_directory
            )

            # Run snappyHexMesh in parallel
            self._run_command(
                ["mpirun", "-np", str(n_proc), "snappyHexMesh", "-parallel", "-overwrite"],
                os.path.join(self.case_directory, "snappyHexMesh.log"),
                cwd=self.case_directory
            )

            # Reconstruct the mesh
            self._run_command(
                ["reconstructParMesh", "-constant", "-latestTime"],
                os.path.join(self.case_directory, "reconstructParMesh.log"),
                cwd=self.case_directory
            )

            # Remove processor directories
            for d in os.listdir(self.case_directory):
                if d.startswith("processor"):
                    shutil.rmtree(os.path.join(self.case_directory, d), ignore_errors=True)
        else:
            self._run_command(
                ["snappyHexMesh", "-overwrite"],
                os.path.join(self.case_directory, "snappyHexMesh.log"),
                cwd=self.case_directory
            )

        # Run checkMesh
        self._run_command(
            ["checkMesh"],
            os.path.join(self.case_directory, "checkMesh.log"),
            cwd=self.case_directory
        )

        # Transform points (scaling)
        # check if this is openfoam 8 version 
        if self.openfoam_version == "8":
            self._run_command(
                ["transformPoints", "-scale", f"({self.GEOMETRY_SCALE} {self.GEOMETRY_SCALE} {self.GEOMETRY_SCALE})"],
                os.path.join(self.case_directory, "transformPoints.log"),
                cwd=self.case_directory
            )
        else:
            self._run_command(
                ["transformPoints", 'scale=({self.GEOMETRY_SCALE} {self.GEOMETRY_SCALE} {self.GEOMETRY_SCALE})'],
                os.path.join(self.case_directory, "transformPoints.log"),
                cwd=self.case_directory
            )
        # Optional: Uncomment if you want to use the old command
        
        # Create a dummy file for ParaView
        with open(os.path.join(self.case_directory, "f.foam"), "w") as f:
            pass

        elapsed_time = time.time() - start_time
        logger.info(f"Mesh created in {elapsed_time/60:.2f} minutes.")

    def run_bc(self):
        """
        Sets up the boundary conditions for the simulation.
        """
        start_time = time.time()
        logger.info("Running boundary condition...")

        # Get the full path to the triSurface directory
        triSurfaceDir = os.path.join(self.case_directory, "constant", "triSurface")
        if not os.path.exists(triSurfaceDir):
            logger.error(f"Directory '{triSurfaceDir}' does not exist. Ensure 'createCase' and 'runMesh' are executed first.")
            raise AortaCFDError(f"Directory '{triSurfaceDir}' does not exist.")

        # Get inlet STL file name
        stl_files = [f for f in os.listdir(triSurfaceDir) if f.endswith(".stl")]
        if not stl_files:
            logger.error(f"No STL files found in '{triSurfaceDir}'. Ensure the directory is populated correctly.")
            raise AortaCFDError(f"No STL files found in '{triSurfaceDir}'.")

        inlet_stl = [f for f in stl_files if "inlet" in f]
        if not inlet_stl:
            logger.error(f"No inlet STL file found in '{triSurfaceDir}'. Ensure the inlet STL file is present.")
            raise AortaCFDError(f"No inlet STL file found in '{triSurfaceDir}'.")
        inlet_stl = inlet_stl[0].split(".")[0]

        # Write the inlet cell centers to map the inlet velocity
        self._run_command(
            ["writeMeshObj"],
            os.path.join(self.case_directory, "meshObj.log"),
            cwd=self.case_directory
        )
        shutil.move(
            os.path.join(self.case_directory, "patch_inlet_0.obj"),
            os.path.join(self.case_directory, "points-new")
        )
        for file in os.listdir(self.case_directory):
            if file.startswith("mesh") or file.startswith("patch"):
                os.remove(os.path.join(self.case_directory, file))
        
        # Format the points file
        formatter = EnhancedPointsFormatter(format_version=1, case_directory=self.case_directory)
        formatter.format_coordinates()

        # Create the boundaryData directory for the inlet
        boundaryDataInletDir = os.path.join(self.case_directory, "constant", "boundaryData", inlet_stl)
        os.makedirs(boundaryDataInletDir, exist_ok=True)
        
        # Check if the points file already exists in the destination and remove it
        destination_points_file = os.path.join(boundaryDataInletDir, "points")
        if os.path.exists(destination_points_file):
            os.remove(destination_points_file)
        
        # Copy the inlet data file
        inlet_dir = os.path.join(self.parent_directory, "INLET")
        source_file = os.path.join(inlet_dir, self.INLET_DATA_FILE or "inletFlowRate.csv")
        if not os.path.isfile(source_file):
            logger.error(f"Inlet data file '{source_file}' not found.")
            raise AortaCFDError(f"Inlet data file '{source_file}' not found.")
        shutil.copy(source_file, boundaryDataInletDir)
        
        # Copy the formatted points file
        shutil.move(os.path.join(self.case_directory, "points"), boundaryDataInletDir)
        
        # Calculate the inlet radius and center
        inlet_radius_calculator = PatchProcessing(
            DIRECTORY=triSurfaceDir,
            STL_FILES=stl_files,
            PATH_NAME="inlet"
        )
        inlet_center, inlet_radius, inlet_normal = inlet_radius_calculator.calculate_inlet_center_radius(
            scale_factor=self.GEOMETRY_SCALE
        )
        
        # Run inletMapping
        inlet_mapping = InletMapping(
            center=inlet_center,
            radius=inlet_radius,
            inlet_data_file=self.INLET_DATA_FILE,
            inlet_name="inlet",
            data_type=self.INLET_DATA_TYPE,
            orientation=self.INLET_ORIENTATION,
            profile=self.INLET_PROFILE,
            case_directory=self.case_directory,
            rho=self.rho_val,
            nu=self.nu_val
        )
        inlet_mapping.run()

        # Get the cardiac cycle period from inletMapping
        self.CARDIAC_CYCLE = float(inlet_mapping.cardiac_cycle)
        logger.info(f"Cardiac cycle period determined: {self.CARDIAC_CYCLE} seconds.")

        # Run cycleDataSetup
        cycle_data = CycleDataSetup(
            inletDataFile=self.INLET_DATA_FILE,
            determined_cardiac_period=self.CARDIAC_CYCLE,
            number_of_cycles=int(self.NUMBER_OF_CYCLES),
            case_directory=self.case_directory
        )
        cycle_data.execute()

        # Windkessel setup (if applicable)
        if self.BC_OUTLET == "3EWINDKESSEL":
            wk_setup = wk_Setup(
                DIRECTORY=self.case_directory,
                GEOMETRY_SCALE=self.GEOMETRY_SCALE,
                STL_FILES=stl_files,
                WK_SETTING=self.WK_SETTING,
                CARDIAC_CYCLE=self.CARDIAC_CYCLE,
                INLET_DATA_FILE=self.INLET_DATA_FILE,
                DATA_TYPE=self.INLET_DATA_TYPE,
                OPENFOAM_VERSION=self.openfoam_version
            )
            wk_setup.write_WK_Setup()
        
        # Format the points file for timeVaryingMappedFixedValue BC
        formatter = EnhancedPointsFormatter(format_version=2, case_directory=self.case_directory)
        formatter.format_coordinates()
        # Copy the formatted points file
        destination_points_file = os.path.join(boundaryDataInletDir, "points")
        if os.path.exists(destination_points_file):
            os.remove(destination_points_file)

        shutil.move(os.path.join(self.case_directory, "points"), destination_points_file)   
        
        elapsed_time = time.time() - start_time
        logger.info(f"Boundary condition setup completed in {elapsed_time / 60:.2f} minutes.")

    def run_simulation(self, latest_time=False, specific_time=None, end_time=None):
        """
        Runs the simulation based on the specified solution type.
        """
        start_time = time.time()
        logger.info("Running Simulation...")
        
        # Dynamically set endTime if not already set
        if self.sim_ctrl_cfg["controlDict"]["endTime"] is None:
            self.simulationSetup.write_controlDict(
                cardiac_period=self.CARDIAC_CYCLE,
                number_of_cycles=self.NUMBER_OF_CYCLES
            )
               
        # Adjust decomposeParDict for parallel execution
        decompose_par_dict = os.path.join(self.case_directory, "system", "decomposeParDict")
        if self.SOLN_TYPE == "parallel":
            self._run_command(
                ["foamDictionary", "-entry", "numberOfSubdomains", "-set", str(self.SUBDOMAINS), decompose_par_dict],
                os.path.join(self.case_directory, "foamDictionary.log"),
                cwd=self.case_directory
            )
            self._run_command(
                ["foamDictionary", "-entry", "simpleCoeffs/n", "-set", f"(1 1 {self.SUBDOMAINS})", decompose_par_dict],
                os.path.join(self.case_directory, "foamDictionary.log"),
                cwd=self.case_directory
            )

        # Build the simulation command
        simulation_command = "pimpleFoam"
        if self.BC_OUTLET == "3EWINDKESSEL":
            simulation_command = "pimpleFoam_WK_2.0" # Adjust as needed

        # Run the simulation
        if self.SOLN_TYPE == "serial":
            self._run_command(
                [simulation_command],
                os.path.join(self.case_directory, "simulation.log"),
                cwd=self.case_directory
            )
        elif self.SOLN_TYPE == "parallel":
            self._run_command(
                ["decomposePar", "-force"],
                os.path.join(self.case_directory, "decomposePar.log"),
                cwd=self.case_directory
            )
            self._run_command(
                ["mpirun", "-np", str(self.SUBDOMAINS), simulation_command, "-parallel"],
                os.path.join(self.case_directory, "simulation.log"),
                cwd=self.case_directory
            )
            self._run_command(
                ["reconstructPar"],
                os.path.join(self.case_directory, "reconstructPar.log"),
                cwd=self.case_directory
            )
            for d in os.listdir(self.case_directory):
                if d.startswith("processor"):
                    shutil.rmtree(os.path.join(self.case_directory, d), ignore_errors=True)
        else:
            logger.error("Invalid solution mode. Please specify either 'serial' or 'parallel'.")
            sys.exit(1)

        elapsed_time = time.time() - start_time
        logger.info(f"Simulation run in {elapsed_time / 60:.2f} minutes.")

    def run_postprocessing(self, reAnimate=False):
        """
        Runs ParaView-based post-processing.
        """
        start_time = time.time()
        logger.info("Running post-processing...")
        # Generate time array
        if self.TIME_STEPS.get("Customized"):
            time_array = _generate_time_array(self.TIME_STEPS)
        else:
            try:
                if self.CASE_TYPE == "Decomposed":
                    # Use foamListTimes for processor directories
                    result = subprocess.check_output(["foamListTimes", "-processor"], cwd=self.case_directory, text=True)
                else:
                    # Use foamListTimes for the case directory
                    result = subprocess.check_output(["foamListTimes"], cwd=self.case_directory, text=True)
                time_array = [line.strip() for line in result.splitlines() if line.strip()]
                # Convert to float and format to avoid scientific notation
                time_array = [f"{float(t):.6f}" for t in time_array]
            except subprocess.CalledProcessError as e:
                logger.error(f"Error running foamListTimes: {e}")
                time_array = []
        # Set environment variables
        os.environ["CASE_TYPE"] = self.CASE_TYPE
        os.environ["CASE_PATH"] = self.case_directory
        os.environ["TIME_ARRAY"] = ",".join(str(x) for x in time_array)
        os.environ["REANIMATION"] = str(reAnimate)
        os.environ["FIELDS"] = ",".join(self.FIELDS)
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
            json.dump(self.RESCALESETTINGS, temp_file)
            os.environ["RESCALE_JSON"] = temp_file.name
        os.environ["ANIMATION_ENABLED"] = str(self.ANIMATION["enabled"])
        os.environ["FPS"] = str(self.ANIMATION["fps"]) if self.ANIMATION["fps"] else "None"

        # Run ParaView script
        script_path = os.path.join(self.parent_directory, "SCRIPTS", "postProcessParaView.py")
        pvbatch_exe = CONFIG["post_processing"]["pvbatch_exe"]
        self._run_command(
            [pvbatch_exe, script_path],
            os.path.join(self.case_directory, "postProcessing.log"),
            cwd=self.case_directory
        )

        elapsed_time = time.time() - start_time
        logger.info(f"Post-processing completed in {elapsed_time / 60:.2f} minutes.")

    def run_all(self):
        """
        Runs all steps of the simulation pipeline.
        """
        case = OpenFOAMCase(clean=True)
        case.casePilot()
        logger.info(f"Directory {self.directory} created.")
        runner = OpenFOAMRunner(case.simulationSetup, cardiac_cycle=case.CARDIAC_CYCLE) 
        runner.run_mesh()
        runner.run_bc()
        runner.run_simulation()
        runner.run_postprocessing()

if __name__ == "__main__":
    try:
        # Initialize argument parser
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

        # Parse arguments
        args = parser.parse_args()

        # Validate command
        if not args.command:
            parser.print_help()
            raise AortaCFDError("No command specified.")

        # Override configuration if specified
        if args.geometry:
            if args.geometry not in CONFIG["geometry"]["valid_cases"]:
                logger.error(f"Error: Invalid geometry case '{args.geometry}'.")
                raise AortaCFDError(f"Invalid geometry case '{args.geometry}'.")

        if args.refinement:
            if args.refinement not in CONFIG["mesh"]["refinement_levels"]:
                logger.error(f"Error: Invalid refinement level '{args.refinement}'.")
                raise AortaCFDError(f"Invalid refinement level '{args.refinement}'.")

        case = OpenFOAMCase(clean=False)
        runner = OpenFOAMRunner(case.simulationSetup)  # Pass the simulationSetup instance
        # Execute the appropriate command
        if args.command == 'createCase':
            logger.info("Creating OpenFOAM case...")
            case.casePilot()
        elif args.command == 'runMesh':
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
            case = OpenFOAMCase(clean=False)  # Do not delete the case directory
            runner = OpenFOAMRunner(case.simulationSetup)
            runner.run_postprocessing(reAnimate=args.reAnimate)
        elif args.command == 'runAll':
            logger.info("Running entire workflow: createCase, runMesh, runBC, runSimulation, runPost")
            case = OpenFOAMCase(clean=True)  # Create a clean case directory
            case.casePilot()
            runner = OpenFOAMRunner(case.simulationSetup, cardiac_cycle=case.CARDIAC_CYCLE)  # Pass CARDIAC_CYCLE
            runner.run_mesh()
            runner.run_bc()
            runner.run_simulation()
            runner.run_postprocessing()
        else:
            parser.print_help()
    except AortaCFDError as e:
        logger.error(f"AortaCFD error: {e}")
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        print(f"Unhandled error: {e}")
        sys.exit(1)
