import os
import shutil
from ..base_task import Task, logger
from aortacfd_lib.utils.runner import run_command, CommandExecutionError

# Import all the refactored library classes from your core library
from aortacfd_lib.mesh_setup import GeometryAnalyzer
from aortacfd_lib.boundary_condition_setup import BoundaryConditionSetup
from aortacfd_lib.physical_properties_setup import PhysicalPropertiesWriter
from aortacfd_lib.numerical_setup import FvSchemesWriter
from aortacfd_lib.solver_setup import FvSolutionWriter
from aortacfd_lib.simulation_control import SimulationSetup
from aortacfd_lib.decompose_setup import SolnType
from aortacfd_lib.inlet_mapping import InletMapping
from aortacfd_lib.cycle_data_setup import CycleDataSetup
from aortacfd_lib.utils.format_points import EnhancedPointsFormatter
from aortacfd_lib.wk_setup import WkSetup

class CreateCaseStructureTask(Task):
    """
    Creates the case directory structure.
    It will only delete the directory if 'clean_run' is true in the config.
    """
    def execute(self, context: dict) -> bool:
        case_dir = context["case_directory"]
        
        # This check is now controlled by a command-line flag
        if self.config.get('clean_run', False) and os.path.exists(case_dir):
            self.log.warning(f"--- CLEAN RUN ENABLED: Deleting existing case directory: {case_dir} ---")
            shutil.rmtree(case_dir)

        logger.info(f"Creating case structure in: {case_dir}")
        os.makedirs(os.path.join(case_dir, "system"), exist_ok=True)
        os.makedirs(os.path.join(case_dir, "constant", "triSurface"), exist_ok=True)
        os.makedirs(os.path.join(case_dir, "0"), exist_ok=True)
        
        inlet_patch_name = self.config['geometry']['inlet_keywords_ordered']
        os.makedirs(os.path.join(case_dir, "constant", "boundaryData", inlet_patch_name), exist_ok=True)

        cad_folder = os.path.join("CAD", self.config["geometry"]["case_name"])
        for f in os.listdir(cad_folder):
            if f.endswith('.stl'):
                shutil.copy(os.path.join(cad_folder, f), os.path.join(case_dir, "constant", "triSurface"))
            elif f == self.config['inlet']['csv_file']:
                 shutil.copy(os.path.join(cad_folder, f), os.path.join(case_dir, "constant", "boundaryData", inlet_patch_name))
        return True

class GenerateMeshFilesTask(Task):
    """Generates blockMeshDict, snappyHexMeshDict, and surfaceFeaturesDict."""
    def execute(self, context: dict) -> bool:
        logger.info("Generating mesh definition files...")
        analyzer = GeometryAnalyzer(config=self.config, case_directory=context["case_directory"])
        analyzer.write_all_mesh_files()
        return True

class PrepareBoundaryDataTask(Task):
    """
    Prepares all time-varying and physiological boundary condition data.
    """
    def execute(self, context: dict) -> bool:
        self.log.info("Preparing boundary condition data...")
        case_dir = context["case_directory"]

        try:
            # Run writeMeshObj to get the inlet patch face centers
            run_command(
                config=self.config,
                command=["writeMeshObj"],
                case_directory=case_dir,
                log_filename="log.writeMeshObj"
            )

            # Find and format the points file
            inlet_patch_name = self.config['geometry']['inlet_keywords_ordered']
            inlet_obj_file = None
            for f in os.listdir(case_dir):
                if f.startswith("patch_") and inlet_patch_name in f and f.endswith(".obj"):
                    inlet_obj_file = f
                    break
            
            if not inlet_obj_file:
                self.log.error(f"Could not find generated .obj file for inlet patch '{inlet_patch_name}'.")
                return False

            temp_points_file = os.path.join(case_dir, "points-new")
            shutil.move(os.path.join(case_dir, inlet_obj_file), temp_points_file)
            formatter = EnhancedPointsFormatter(input_filename=temp_points_file, output_filename=os.path.join(case_dir, "points"))
            formatter.format_coordinates()

            boundary_data_inlet_dir = os.path.join(case_dir, "constant", "boundaryData", inlet_patch_name)
            shutil.move(os.path.join(case_dir, "points"), os.path.join(boundary_data_inlet_dir, "points"))
            os.remove(temp_points_file)

            # Process Inlet CSV and generate velocity files
            inlet_mapper = InletMapping(config=self.config, case_directory=case_dir)
            inlet_mapper.run()

            # Save the calculated cardiac cycle to the shared context
            cardiac_cycle = float(inlet_mapper.cardiac_cycle)
            context['cardiac_cycle'] = cardiac_cycle
            self.log.info(f"Cardiac cycle determined to be {cardiac_cycle}s and saved to context.")

            # Set up data for multiple cycles
            self.log.info("Setting up data for multiple cardiac cycles...")
            # THIS CALL IS NOW CORRECT
            cycle_setup = CycleDataSetup(config=self.config, cardiac_cycle=cardiac_cycle, case_directory=case_dir)
            cycle_setup.execute()

            # Set up Windkessel if needed
            if self.config.get("outlets", {}).get("type") == "3ElementWindkessel":
                self.log.info("Calculating and writing Windkessel properties...")
                tri_surface_dir = os.path.join(case_dir, "constant", "triSurface")
                stl_files = os.listdir(tri_surface_dir)
                # This class will also need to be refactored to use 'cardiac_cycle'
                wk_setup = WkSetup(config=self.config, stl_files=stl_files, case_directory=case_dir, cardiac_cycle=cardiac_cycle)
                wk_setup.execute()
            
            self.log.info("Boundary data preparation completed successfully.")
            return True

        except (CommandExecutionError, FileNotFoundError, ValueError) as e:
            self.log.error(f"A critical error occurred during boundary data preparation: {e}")
            return False

class GenerateBCFilesTask(Task):
    """Generates the 0/U, 0/p, and other initial condition field files."""
    def execute(self, context: dict) -> bool:
        logger.info("Generating boundary condition field files...")
        bc_generator = BoundaryConditionSetup(config=self.config, case_directory=context["case_directory"])
        bc_generator.write_all_bc_files()
        return True

class GeneratePhysicalPropertiesTask(Task):
    """Generates the transportProperties and momentumTransport files."""
    def execute(self, context: dict) -> bool:
        logger.info("Generating physical properties files...")
        writer = PhysicalPropertiesWriter(config=self.config, case_directory=context["case_directory"])
        writer.write_transportProperties_file()
        # CORRECTED: Use the new, correct method name
        writer.write_momentumTransport_file()
        return True
    
class GenerateNumericalSchemesTask(Task):
    """Generates the fvSchemes file."""
    def execute(self, context: dict) -> bool:
        logger.info("Generating fvSchemes file...")
        writer = FvSchemesWriter(config=self.config, case_directory=context["case_directory"])
        writer.write_fvSchemes_file()
        return True

class GenerateSolverSettingsTask(Task):
    """Generates the fvSolution file."""
    def execute(self, context: dict) -> bool:
        logger.info("Generating fvSolution file...")
        writer = FvSolutionWriter(config=self.config, case_directory=context["case_directory"])
        writer.write_fvSolution_file()
        return True

class GenerateDecomposeParDictTask(Task):
    """Generates the decomposeParDict file."""
    def execute(self, context: dict) -> bool:
        logger.info("Generating decomposeParDict file...")
        writer = SolnType(config=self.config, case_directory=context["case_directory"])
        writer.write_decomposeParDict()
        return True
        
class GenerateControlDictTask(Task):
    """
    Generates the final controlDict file by taking the user's settings
    and injecting the dynamically calculated endTime.
    It prioritizes a fixed end_time if provided.
    """
    def execute(self, context: dict) -> bool:
        logger.info("Generating final controlDict file...")
        
        sim_controls = self.config.get("simulation_control", {})
        final_end_time = sim_controls.get("end_time") # Check for the new key

        # --- THIS IS THE NEW LOGIC ---
        # If a specific end_time is NOT provided in the JSON, calculate it.
        if final_end_time is None or final_end_time == "auto":
            cardiac_cycle = context.get("cardiac_cycle")
            if not cardiac_cycle:
                logger.error("Cardiac cycle not found in context. Cannot calculate endTime.")
                return False
            
            number_of_cycles = sim_controls.get("number_of_cycles", 1)
            final_end_time = float(cardiac_cycle) * int(number_of_cycles)
            logger.info(f"Calculated endTime: {final_end_time}s ({number_of_cycles} cycles of {cardiac_cycle}s)")
        else:
            logger.info(f"Using fixed endTime from configuration: {final_end_time}s")
        # ---------------------------

        # The rest of the logic remains the same
        control_dict_template = self.config["simulation_control"]["controlDict"].copy()
        control_dict_template['endTime'] = final_end_time
        
        writer = SimulationSetup(config=self.config, case_directory=context["case_directory"])
        writer.write_controlDict(final_control_dict=control_dict_template)
        
        return True
    
class ValidationTask(Task):
    def execute(self, context: dict) -> bool:
        self.log.info("Performing pre-flight validation checks...")
        
        # 1. Check if required files exist
        bc_path = os.path.join("CAD", self.config['geometry']['case_name'], "boundary_conditions.json")
        if not os.path.exists(bc_path):
            self.log.error(f"Validation failed: boundary_conditions.json not found at {bc_path}")
            return False

        # 2. Check for logical consistency
        if self.config['outlets']['type'] == '3ElementWindkessel':
            split_ratios = self.config['outlets']['windkessel_settings']['flow_split']
            total_split = sum(split_ratios.values())
            if not np.isclose(total_split, 1.0):
                self.log.warning(f"Validation Warning: Windkessel flow splits add up to {total_split}, not 1.0.")

        # 3. Check for heuristic best practices
        if self.config['physics']['simulation_type'] == 'LES' and self.config['geometry']['refinement_level'] != 'fine':
            self.log.warning("Validation Warning: Running an LES simulation with a non-fine mesh profile is not recommended.")
            
        self.log.info("Validation checks passed.")
        return True