import os
import shutil
import numpy as np
from stl import mesh as np_stl_mesh

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
    from ...aortacfd_lib.simulation_report_generator import SimulationReportGenerator
    from ...aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile
except ImportError:
    from aortacfd_lib.solver_setup import FvSolutionWriter
    from aortacfd_lib.simulation_control import SimulationSetup
    from aortacfd_lib.decompose_setup import SolnType
    from aortacfd_lib.inlet_mapping import InletMapping
    from aortacfd_lib.cycle_data_setup import CycleDataSetup
    from aortacfd_lib.utils.patch_utils import detect_world_patch_mode
    from aortacfd_lib.utils.format_points import EnhancedPointsFormatter
    from aortacfd_lib.wk_setup import WkSetup
    from aortacfd_lib.simulation_report_generator import SimulationReportGenerator
    from aortacfd_lib.distance_wall_inlet_profile import DistanceWallInletProfile

class CreateCaseStructureTask(Task):
    """
    Creates the case directory structure and copies/scales geometry files.

    IMPORTANT: STL files are scaled from input units (typically mm) to SI units (meters)
    during the copy process. This is the ONLY place scaling happens - all downstream
    code reads already-scaled STLs in meters.
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

        # Clean logs directory to remove stale log files from previous runs
        logs_dir = os.path.join(case_dir, "logs")
        if os.path.exists(logs_dir):
            for log_file in os.listdir(logs_dir):
                log_path = os.path.join(logs_dir, log_file)
                if os.path.isfile(log_path):
                    os.remove(log_path)
            logger.debug("Cleaned stale log files from logs directory")
        os.makedirs(logs_dir, exist_ok=True)

        inlet_patch_name = self.config['geometry']['inlet_keywords_ordered']
        os.makedirs(os.path.join(case_dir, "constant", "boundaryData", inlet_patch_name), exist_ok=True)

        cad_folder = os.path.join("cases_input", self.config["geometry"]["case_name"])

        # Validate geometry before copying (validation still uses scale_factor for size checks)
        self.log.info("Validating geometry files...")
        scale_factor = self.config.get('geometry', {}).get('scale_factor', 0.001)
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

        # Copy and scale STL files (CENTRAL SCALING - only place scaling happens)
        tri_surface_dir = os.path.join(case_dir, "constant", "triSurface")
        self.log.info(f"Copying and scaling STL files (scale_factor={scale_factor})...")

        for f in os.listdir(cad_folder):
            src_path = os.path.join(cad_folder, f)

            if f.endswith('.stl'):
                # Scale STL during copy - this is the ONLY place scaling happens
                dst_path = os.path.join(tri_surface_dir, f)
                self._copy_and_scale_stl(src_path, dst_path, scale_factor)

            # Check for inlet CSV file (support both flattened and nested config structures)
            inlet_config = self.config.get('boundary_conditions', {}).get('inlet') or self.config.get('inlet', {})
            csv_file = inlet_config.get('csv_file') if isinstance(inlet_config, dict) else None
            if csv_file and f == csv_file:
                shutil.copy(src_path, os.path.join(case_dir, "constant", "boundaryData", inlet_patch_name))

        self.log.info(f"STL files scaled and copied to {tri_surface_dir} (now in meters)")
        return True

    def _copy_and_scale_stl(self, src_path: str, dst_path: str, scale_factor: float):
        """
        Copy an STL file while applying scale factor to convert units.

        This is the CENTRAL SCALING OPERATION. STL files are typically in mm
        (from medical imaging), and we convert to meters for OpenFOAM.

        Args:
            src_path: Path to source STL file (in original units, e.g., mm)
            dst_path: Path to destination STL file (will be in SI units, meters)
            scale_factor: Conversion factor (e.g., 0.001 for mm -> m)
        """
        try:
            # Load the STL mesh
            stl_mesh = np_stl_mesh.Mesh.from_file(src_path)

            # Scale all vertices
            stl_mesh.vectors *= scale_factor

            # Update the mesh normals after scaling
            stl_mesh.update_normals()

            # Save the scaled mesh
            stl_mesh.save(dst_path)

            self.log.debug(f"Scaled and saved: {os.path.basename(src_path)} -> {os.path.basename(dst_path)}")

        except Exception as e:
            self.log.error(f"Failed to scale STL {src_path}: {e}")
            raise RuntimeError(f"Failed to scale STL file {src_path}: {e}")

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
            # Support both flattened (inlet) and nested (boundary_conditions.inlet) config structures
            inlet_config = self.config.get('boundary_conditions', {}).get('inlet') or self.config.get('inlet', {})
            inlet_type = inlet_config.get('type', 'TIMEVARYING').upper()

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
                # For CONSTANT/PARABOLIC inlets
                cardiac_cycle = 1.0  # Default 1.0s (not used for steady inlet)
                context['cardiac_cycle'] = cardiac_cycle

                # Check if this CONSTANT inlet uses a non-uniform profile (wall_distance, elliptical)
                inlet_profile = inlet_config.get('profile', 'plug').lower()

                if inlet_profile in ['wall_distance', 'elliptical']:
                    # For non-uniform profiles, generate boundaryData with wall_distance profile
                    self.log.info(f"CONSTANT inlet with '{inlet_profile}' profile - generating non-uniform velocity data...")

                    # Calculate flow rate from inlet config
                    flow_rate_m3s = self._calculate_constant_flowrate(inlet_config, case_dir)

                    # Generate wall_distance profile data
                    profile_gen = DistanceWallInletProfile(config=self.config, case_directory=case_dir)
                    profile_gen.run_constant(flow_rate_m3s)

                    # Mark that we need timeVaryingMappedFixedValue BC instead of fixedValue
                    context['constant_mapped_profile'] = True
                    self.log.info(f"Non-uniform profile generated. Will use timeVaryingMappedFixedValue BC.")
                else:
                    self.log.info(f"Inlet type is {inlet_type} with {inlet_profile} profile (uniform). Using fixedValue BC.")

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


    def _calculate_constant_flowrate(self, inlet_config: dict, case_dir: str) -> float:
        """
        Calculate flow rate in m³/s for CONSTANT inlet from config parameters.

        Supports:
        - flowrate: in L/min
        - cardiac_output: in L/min (alias for flowrate)
        - velocity: in m/s (converted using inlet area)

        Returns:
            float: Flow rate in m³/s
        """
        from aortacfd_lib.utils.patch_processing import PatchProcessing

        # Get inlet area for velocity-to-flowrate conversion
        tri_surface_dir = os.path.join(case_dir, "constant", "triSurface")
        inlet_name = self.config['geometry']['inlet_keywords_ordered']
        patch_processor = PatchProcessing(tri_surface_dir, inlet_name)
        inlet_area = patch_processor.calculate_surface_area()

        # Check for flowrate or cardiac_output (both in L/min)
        if 'flowrate' in inlet_config:
            flowrate_Lmin = inlet_config['flowrate']
            flow_rate_m3s = flowrate_Lmin / 60.0 / 1000.0  # L/min -> m³/s
            self.log.info(f"CONSTANT inlet flowrate: {flowrate_Lmin:.2f} L/min = {flow_rate_m3s:.6e} m³/s")
            return flow_rate_m3s

        elif 'cardiac_output' in inlet_config:
            cardiac_output_Lmin = inlet_config['cardiac_output']
            flow_rate_m3s = cardiac_output_Lmin / 60.0 / 1000.0  # L/min -> m³/s
            self.log.info(f"CONSTANT inlet cardiac_output: {cardiac_output_Lmin:.2f} L/min = {flow_rate_m3s:.6e} m³/s")
            return flow_rate_m3s

        elif 'velocity' in inlet_config:
            velocity = inlet_config['velocity']
            flow_rate_m3s = velocity * inlet_area
            self.log.info(f"CONSTANT inlet velocity: {velocity:.4f} m/s × area {inlet_area:.6e} m² = {flow_rate_m3s:.6e} m³/s")
            return flow_rate_m3s

        else:
            self.log.error("CONSTANT inlet with wall_distance profile requires 'flowrate', 'cardiac_output', or 'velocity'")
            raise ValueError("Missing flowrate/cardiac_output/velocity for CONSTANT inlet")

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

        # Clean 0/ directory to remove stale field files (e.g., wallShearStress from previous runs)
        # This prevents decomposePar errors due to field size mismatches with new mesh
        zero_dir = os.path.join(context["case_directory"], "0")
        if os.path.exists(zero_dir):
            for item in os.listdir(zero_dir):
                item_path = os.path.join(zero_dir, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                    logger.debug(f"Removed stale field file: {item}")
                elif os.path.isdir(item_path) and item != "uniform":
                    # Keep uniform/ directory but remove others
                    shutil.rmtree(item_path)
                    logger.debug(f"Removed stale field directory: {item}")

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

    Supports smart purgeWrite calculation:
    - purgeWrite: N  -> Keep last N time directories (direct value)
    - keep_last_cycles: N -> Calculate purgeWrite to keep last N cardiac cycles
    """
    def execute(self, context: dict) -> bool:
        logger.info("Generating final controlDict file...")

        sim_controls = self.config.get("simulation_control", {})
        final_end_time = sim_controls.get("end_time")  # Check for the new key

        # Get cardiac cycle from context
        cardiac_cycle = context.get("cardiac_cycle")

        # --- Calculate endTime ---
        # If a specific end_time is NOT provided in the JSON, calculate it.
        if final_end_time is None or final_end_time == "auto":
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

        # The rest of the logic remains the same
        control_dict_template = self.config["simulation_control"]["controlDict"].copy()
        control_dict_template['endTime'] = final_end_time

        # --- Calculate purgeWrite (smart keep_last_cycles feature) ---
        purge_write = self._calculate_purge_write(sim_controls, control_dict_template, cardiac_cycle)
        if purge_write is not None:
            control_dict_template['purgeWrite'] = purge_write

        writer = SimulationSetup(config=self.config, case_directory=context["case_directory"])
        writer.write_controlDict(final_control_dict=control_dict_template)

        return True

    def _calculate_purge_write(self, sim_controls: dict, control_dict: dict, cardiac_cycle: float) -> int:
        """
        Calculate purgeWrite value based on configuration.

        Supports:
        - purgeWrite: N (direct value in controlDict)
        - keep_last_cycles: N (smart calculation based on cardiac cycle)

        Parameters
        ----------
        sim_controls : dict
            simulation_control section of config
        control_dict : dict
            controlDict settings
        cardiac_cycle : float
            Duration of one cardiac cycle in seconds

        Returns
        -------
        int or None
            purgeWrite value, or None to use template default (0)
        """
        # Check for direct purgeWrite setting
        if 'purgeWrite' in control_dict and control_dict['purgeWrite'] != 0:
            logger.info(f"Using direct purgeWrite: {control_dict['purgeWrite']}")
            return control_dict['purgeWrite']

        # Check for keep_last_cycles setting
        keep_last_cycles = sim_controls.get('keep_last_cycles')

        if keep_last_cycles is None:
            return None  # Use template default (0 = keep all)

        if not cardiac_cycle or cardiac_cycle <= 0:
            logger.warning("Cannot calculate purgeWrite: cardiac_cycle not available")
            return None

        # Get writeInterval
        write_interval = control_dict.get('writeInterval', sim_controls.get('writeInterval', 0.01))

        if write_interval <= 0:
            logger.warning("Cannot calculate purgeWrite: invalid writeInterval")
            return None

        # Calculate timesteps per cycle
        timesteps_per_cycle = int(cardiac_cycle / write_interval)

        # Calculate purgeWrite to keep last N cycles
        purge_write = timesteps_per_cycle * int(keep_last_cycles)

        # Add small buffer (10%) for safety
        purge_write = int(purge_write * 1.1)

        logger.info(f"Smart purgeWrite calculation:")
        logger.info(f"  keep_last_cycles: {keep_last_cycles}")
        logger.info(f"  cardiac_cycle: {cardiac_cycle:.4f}s")
        logger.info(f"  writeInterval: {write_interval}s")
        logger.info(f"  timesteps_per_cycle: {timesteps_per_cycle}")
        logger.info(f"  purgeWrite: {purge_write} (keeps ~{keep_last_cycles} cycles)")

        return purge_write


class GenerateSimulationReportTask(Task):
    """
    Generates comprehensive technical report documenting the CFD simulation setup.
    Creates markdown, JSON, and text reports in the output/reports/ directory.
    """
    def execute(self, context: dict) -> bool:
        logger.info("Generating simulation technical report...")

        # Get output directory (parent of case_directory/openfoam)
        case_dir = context["case_directory"]
        output_dir = os.path.dirname(case_dir)
        case_name = context.get("patient_name", "unknown")

        # Initialize report generator
        report_gen = SimulationReportGenerator(output_dir, case_name)

        # Gather geometry info from context if available
        geometry_info = context.get("geometry_info", None)

        # Mesh info would be added after mesh generation
        mesh_info = context.get("mesh_info", None)

        # Generate all reports
        try:
            report_path = report_gen.generate_full_report(
                config=self.config,
                geometry_info=geometry_info,
                mesh_info=mesh_info
            )
            logger.info(f"Technical report generated: {report_path}")
            logger.info(f"Report directory: {output_dir}/reports/")
            context["report_path"] = report_path
            return True
        except Exception as e:
            logger.error(f"Failed to generate simulation report: {e}")
            # Don't fail the workflow if report generation fails
            return True



class GenerateWindkesselReportTask(Task):
    """
    Generates Windkessel analysis report with flow rate plots and parameters.
    Only runs if 3EWINDKESSEL outlets are configured.
    """
    def execute(self, context: dict) -> bool:
        # Check if Windkessel BC is used
        bc_type = self.config.get('boundary_conditions', {}).get('outlets', {}).get('type', '')

        if bc_type != '3EWINDKESSEL':
            logger.info("Skipping Windkessel analysis (not using 3EWINDKESSEL BC)")
            return True

        logger.info("Generating Windkessel analysis report...")

        try:
            from aortacfd_lib.windkessel_analyzer import WindkesselAnalyzer

            case_dir = context["case_directory"]
            output_dir = os.path.dirname(case_dir)
            reports_dir = os.path.join(output_dir, "reports")

            analyzer = WindkesselAnalyzer(case_dir, self.config)
            pdf_path = analyzer.generate_report(reports_dir)

            logger.info(f"Windkessel analysis report saved: {pdf_path}")
            context["windkessel_report_path"] = pdf_path
            return True

        except Exception as e:
            logger.error(f"Failed to generate Windkessel report: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Don't fail the workflow
            return True
