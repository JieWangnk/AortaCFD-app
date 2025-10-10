import os
import shutil
try:
    from ..base_task import Task, logger
    from ...aortacfd_lib.utils.runner import run_command, CommandExecutionError
    from ...aortacfd_lib.utils.validation import GeometryValidator, BoundaryConditionValidator
    from ...aortacfd_lib.mesh_setup import GeometryAnalyzer
    from ...aortacfd_lib.boundary_condition_setup import BoundaryConditionSetup
    from ...aortacfd_lib.physical_properties_setup import PhysicalPropertiesWriter
    from ...aortacfd_lib.numerical_setup import FvSchemesWriter
except ImportError:
    from workflow.base_task import Task, logger
    from aortacfd_lib.utils.runner import run_command, CommandExecutionError
    from aortacfd_lib.utils.validation import GeometryValidator, BoundaryConditionValidator
    from aortacfd_lib.mesh_setup import GeometryAnalyzer
    from aortacfd_lib.boundary_condition_setup import BoundaryConditionSetup
    from aortacfd_lib.physical_properties_setup import PhysicalPropertiesWriter
    from aortacfd_lib.numerical_setup import FvSchemesWriter

try:
    from ...aortacfd_lib.solver_setup import FvSolutionWriter
    from ...aortacfd_lib.simulation_control import SimulationSetup
    from ...aortacfd_lib.decompose_setup import SolnType
    from ...aortacfd_lib.inlet_mapping import InletMapping
    from ...aortacfd_lib.cycle_data_setup import CycleDataSetup
    from ...aortacfd_lib.utils.patch_utils import detect_world_patch_mode
    from ...aortacfd_lib.utils.format_points import EnhancedPointsFormatter
    from ...aortacfd_lib.wk_setup import WkSetup
except ImportError:
    from aortacfd_lib.solver_setup import FvSolutionWriter
    from aortacfd_lib.simulation_control import SimulationSetup
    from aortacfd_lib.decompose_setup import SolnType
    from aortacfd_lib.inlet_mapping import InletMapping
    from aortacfd_lib.cycle_data_setup import CycleDataSetup
    from aortacfd_lib.utils.patch_utils import detect_world_patch_mode
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

        cad_folder = os.path.join("cases_input", self.config["geometry"]["case_name"])

        # Validate geometry before copying
        self.log.info("Validating geometry files...")
        scale_factor = self.config.get('geometry', {}).get('scale_factor', 1.0)
        validator = GeometryValidator(cad_folder, scale_factor=scale_factor)
        validation_result = validator.validate_all()

        # Log warnings
        for warning in validation_result.warnings:
            self.log.warning(f"Geometry validation warning: {warning}")

        # Check for errors
        if not validation_result.is_valid:
            for error in validation_result.errors:
                self.log.error(f"Geometry validation error: {error}")
            self.log.error("Geometry validation failed. Please fix the errors above and try again.")
            return False

        self.log.info("Geometry validation passed.")

        # Copy files
        for f in os.listdir(cad_folder):
            if f.endswith('.stl'):
                shutil.copy(os.path.join(cad_folder, f), os.path.join(case_dir, "constant", "triSurface"))
            # Check for inlet CSV file (support both flattened and nested config structures)
            inlet_config = self.config.get('boundary_conditions', {}).get('inlet') or self.config.get('inlet', {})
            csv_file = inlet_config.get('csv_file') if isinstance(inlet_config, dict) else None
            if csv_file and f == csv_file:
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
            # Check if we have proper patches or just world patch
            world_patch_mode = detect_world_patch_mode(case_dir, self.log)
            
            if world_patch_mode:
                # Set a default cardiac cycle for world patch scenario
                context['cardiac_cycle'] = 1.0
                self.log.info("Using default cardiac cycle of 1.0s for world patch scenario")
                return True
            
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

            # Check inlet type - only process CSV for time-varying inlets
            inlet_type = self.config.get('inlet', {}).get('type', 'TIMEVARYING').upper()

            if inlet_type in ['TIMEVARYING', 'WOMERSLEY']:
                # Process Inlet CSV and generate velocity files
                self.log.info(f"Processing time-varying inlet boundary condition ({inlet_type})...")
                inlet_mapper = InletMapping(config=self.config, case_directory=case_dir)
                inlet_mapper.run()

                # Save the calculated cardiac cycle to the shared context
                cardiac_cycle = float(inlet_mapper.cardiac_cycle)
                context['cardiac_cycle'] = cardiac_cycle
                self.log.info(f"Cardiac cycle determined to be {cardiac_cycle}s and saved to context.")

                # Set up data for multiple cycles
                self.log.info("Setting up data for multiple cardiac cycles...")
                cycle_setup = CycleDataSetup(config=self.config, cardiac_cycle=cardiac_cycle, case_directory=case_dir)
                cycle_setup.execute()
            else:
                # For CONSTANT/PARABOLIC inlets, use a default cardiac cycle for context
                cardiac_cycle = 1.0  # Default 1.0s (not used for steady inlet)
                context['cardiac_cycle'] = cardiac_cycle
                self.log.info(f"Inlet type is {inlet_type} (steady-state). No CSV processing needed. Using default cardiac_cycle={cardiac_cycle}s for context.")

            # Set up Windkessel if needed
            if self.config.get("outlets", {}).get("type") == "3EWINDKESSEL":
                self.log.info("Calculating and writing Windkessel properties...")
                tri_surface_dir = os.path.join(case_dir, "constant", "triSurface")
                stl_files = os.listdir(tri_surface_dir)
                # This class will also need to be refactored to use 'cardiac_cycle'
                wk_setup = WkSetup(config=self.config, stl_files=stl_files, case_directory=case_dir, cardiac_cycle=cardiac_cycle)
                wk_setup.execute()
            
            # Clean up temporary .obj files generated during mesh processing
            self._cleanup_temp_obj_files(case_dir)
            
            self.log.info("Boundary data preparation completed successfully.")
            return True

        except (CommandExecutionError, FileNotFoundError, ValueError) as e:
            self.log.error(f"A critical error occurred during boundary data preparation: {e}")
            return False


    def _cleanup_temp_obj_files(self, case_dir: str):
        """
        Clean up temporary .obj files generated during OpenFOAM mesh processing.
        These files are used for debugging/visualization but not needed for simulation.
        """
        obj_files = [f for f in os.listdir(case_dir) if f.endswith('.obj')]
        if obj_files:
            self.log.info(f"Cleaning up {len(obj_files)} temporary .obj files...")
            for obj_file in obj_files:
                obj_path = os.path.join(case_dir, obj_file)
                try:
                    os.remove(obj_path)
                    self.log.debug(f"Removed: {obj_file}")
                except OSError as e:
                    self.log.warning(f"Could not remove {obj_file}: {e}")
            self.log.info("Temporary .obj files cleanup completed.")
        else:
            self.log.debug("No .obj files found to clean up.")

class GenerateBCFilesTask(Task):
    """Generates the 0/U, 0/p, and other initial condition field files."""
    def execute(self, context: dict) -> bool:
        logger.info("Generating boundary condition field files...")

        # Validate boundary conditions before generating files
        logger.info("Validating boundary condition configuration...")
        bc_validator = BoundaryConditionValidator(self.config, context["case_directory"])
        validation_result = bc_validator.validate_all()

        # Log warnings
        for warning in validation_result.warnings:
            logger.warning(f"BC validation warning: {warning}")

        # Check for errors
        if not validation_result.is_valid:
            for error in validation_result.errors:
                logger.error(f"BC validation error: {error}")
            logger.error("Boundary condition validation failed. Please fix the errors above and try again.")
            return False

        logger.info("Boundary condition validation passed.")

        # Generate BC files
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
                # Cardiac cycle not yet calculated - use temporary value
                # Will be updated later by update_control_dict task
                number_of_cycles = sim_controls.get("number_of_cycles", 1)
                final_end_time = 1.0 * number_of_cycles  # Temporary: assume 1s per cycle
                logger.warning(f"Cardiac cycle not yet determined. Using temporary endTime: {final_end_time}s")
                logger.info("This will be updated after boundary data preparation.")
            else:
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
    
