import os
import shutil
import numpy as np
from pathlib import Path
from stl import mesh as np_stl_mesh

# Use centralized import resolver to avoid duplicate try/except blocks
try:
    from ...utils.imports import (
        Task, logger,
        run_command, CommandExecutionError,
        GeometryValidator, BoundaryConditionValidator,
        GeometryAnalyzer, BoundaryConditionSetup,
        PhysicalPropertiesWriter, FvSchemesWriter,
        FvSolutionWriter, SimulationSetup, SolnType,
        InletMapping, CycleDataSetup,
        detect_world_patch_mode, EnhancedPointsFormatter,
        WkSetup, SimulationReportGenerator,
        DistanceWallInletProfile,
    )
except ImportError:
    from utils.imports import (
        Task, logger,
        run_command, CommandExecutionError,
        GeometryValidator, BoundaryConditionValidator,
        GeometryAnalyzer, BoundaryConditionSetup,
        PhysicalPropertiesWriter, FvSchemesWriter,
        FvSolutionWriter, SimulationSetup, SolnType,
        InletMapping, CycleDataSetup,
        detect_world_patch_mode, EnhancedPointsFormatter,
        WkSetup, SimulationReportGenerator,
        DistanceWallInletProfile,
    )

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
            # Note: Inlet CSV file is now copied in PrepareBoundaryDataTask (setup:bc step)

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

            # Verify mesh exists before running writeMeshObj
            mesh_path = os.path.join(case_dir, "constant", "polyMesh")
            if not os.path.exists(mesh_path):
                self.log.error(f"Mesh not found at {mesh_path}. Run 'run:mesh' before 'setup:bc'.")
                return False

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

            # Clean up old timestep directories (0.*, 0, etc.) to ensure fresh boundary data
            if os.path.exists(boundary_data_inlet_dir):
                for item in os.listdir(boundary_data_inlet_dir):
                    item_path = os.path.join(boundary_data_inlet_dir, item)
                    # Remove timestep directories (start with digit) but keep points file
                    if item[0].isdigit():
                        if os.path.islink(item_path):
                            # Handle symbolic links (from multi-cycle setup)
                            os.unlink(item_path)
                            self.log.debug(f"Removed old timestep symlink: {item}")
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                            self.log.debug(f"Removed old timestep directory: {item}")
                self.log.info("Cleaned up old boundaryData timestep directories")

            shutil.move(os.path.join(case_dir, "points"), os.path.join(boundary_data_inlet_dir, "points"))
            os.remove(temp_points_file)

            # Check inlet type - only process CSV for time-varying inlets
            # Support both flattened (inlet) and nested (boundary_conditions.inlet) config structures
            inlet_config = self.config.get('boundary_conditions', {}).get('inlet') or self.config.get('inlet', {})
            inlet_type = inlet_config.get('type', 'TIMEVARYING').upper()

            if inlet_type == 'MRI':
                # MRI inlet type: pre-processed 4D flow MRI data in OpenFOAM format
                # User provides directory with time directories containing U files
                mri_source_dir = inlet_config.get('file', inlet_config.get('source_dir', ''))
                if not mri_source_dir:
                    raise ValueError("MRI inlet type requires 'file' parameter pointing to inlet data directory")

                # Resolve the source directory path
                if not os.path.isabs(mri_source_dir):
                    # Try relative to patient case directory first
                    patient_case_dir = self.config.get('patient_case_directory', '')
                    if patient_case_dir and os.path.isdir(os.path.join(patient_case_dir, mri_source_dir)):
                        mri_source_dir = os.path.join(patient_case_dir, mri_source_dir)
                    elif os.path.isdir(mri_source_dir):
                        pass  # Already a valid relative path
                    else:
                        raise FileNotFoundError(f"MRI inlet source directory not found: {mri_source_dir}")

                if not os.path.isdir(mri_source_dir):
                    raise FileNotFoundError(f"MRI inlet source directory not found: {mri_source_dir}")

                self.log.info(f"Using pre-processed MRI inlet data from: {mri_source_dir}")

                # Find time directories in source
                source_time_dirs = [d for d in os.listdir(mri_source_dir)
                                   if os.path.isdir(os.path.join(mri_source_dir, d))
                                   and d.replace('.', '', 1).isdigit()]

                if not source_time_dirs:
                    raise ValueError(f"No time directories found in MRI source: {mri_source_dir}")

                source_times = sorted([float(d) for d in source_time_dirs])

                # Determine cardiac cycle from the data (max time in source)
                cardiac_cycle = max(source_times)
                context['cardiac_cycle'] = cardiac_cycle
                self.log.info(f"MRI inlet data: {len(source_times)} time points, cardiac cycle = {cardiac_cycle}s")

                # Copy time directories from source to boundaryData
                for time_str in source_time_dirs:
                    src_path = os.path.join(mri_source_dir, time_str)
                    dst_path = os.path.join(boundary_data_inlet_dir, time_str)
                    if os.path.exists(dst_path):
                        shutil.rmtree(dst_path)
                    shutil.copytree(src_path, dst_path)
                    self.log.debug(f"Copied MRI inlet data: {time_str}")

                self.log.info(f"Copied {len(source_time_dirs)} time directories to boundaryData")

                # Interpolate MRI velocity data from MRI source points onto mesh face centres.
                # The mesh face centres were already written to boundaryData/inlet/points (line 210).
                # This ensures the flowrate is preserved regardless of mesh resolution.
                mri_points_file = os.path.join(mri_source_dir, 'points')
                if os.path.exists(mri_points_file):
                    self.log.info("Interpolating MRI velocity data onto mesh face centres...")
                    self._interpolate_mri_to_mesh_faces(
                        mri_points_file, boundary_data_inlet_dir, source_time_dirs
                    )

                # Set up data for multiple cycles using symbolic links
                self.log.info("Setting up data for multiple cardiac cycles...")
                cycle_setup = CycleDataSetup(config=self.config, cardiac_cycle=cardiac_cycle, case_directory=case_dir)
                cycle_setup.execute()

                # Save MRI inlet audit
                try:
                    from aortacfd_lib.inlet_qc import InletAudit
                    # Read spatial point count from the mesh face centres file
                    mesh_pts_file = os.path.join(boundary_data_inlet_dir, 'points')
                    n_spatial_points = len(self._read_bare_points(mesh_pts_file)) if os.path.exists(mesh_pts_file) else 0
                    audit = InletAudit(
                        inlet_area_m2=0.0, inlet_radius_eq_m=0.0,
                        inlet_center=[0, 0, 0], inlet_normal=[0, 0, 0],
                        csv_file=str(mri_source_dir),
                        data_type="MRI_4D_flow",
                        n_points=n_spatial_points,
                        detected_period_s=cardiac_cycle,
                        inlet_type="MRI",
                        profile="patient-specific",
                        orientation="from_data",
                        n_output_timesteps=len(source_time_dirs),
                    )
                    reports_dir = os.path.join(os.path.dirname(case_dir), "reports")
                    os.makedirs(reports_dir, exist_ok=True)
                    audit.save_json(Path(os.path.join(reports_dir, "inlet_audit.json")))
                    self.log.info(f"MRI inlet audit saved: {reports_dir}/inlet_audit.json")
                except Exception as e:
                    self.log.warning(f"InletQC audit skipped: {e}")

            elif inlet_type in ['TIMEVARYING', 'WOMERSLEY']:
                # Copy inlet CSV file to boundaryData directory if not already present
                csv_file = inlet_config.get('csv_file')
                if csv_file:
                    csv_dest = os.path.join(boundary_data_inlet_dir, csv_file)
                    if not os.path.exists(csv_dest):
                        # Try to find CSV in patient case directory
                        csv_src = self._find_inlet_csv(csv_file, case_dir)
                        if csv_src:
                            # Validate CSV format before copying
                            self._validate_inlet_csv(csv_src)
                            shutil.copy(csv_src, csv_dest)
                            self.log.info(f"Copied inlet CSV file: {csv_file} -> {boundary_data_inlet_dir}")
                        else:
                            self.log.error(f"Inlet CSV file '{csv_file}' not found in patient case directory")
                            raise FileNotFoundError(f"Inlet CSV file not found: {csv_file}")

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

                # Save inlet QC audit
                try:
                    from aortacfd_lib.inlet_qc import InletQC
                    inlet_qc = InletQC(self.config, case_dir)
                    audit = inlet_qc.run_full_qc()
                    reports_dir = os.path.join(os.path.dirname(case_dir), "reports")
                    os.makedirs(reports_dir, exist_ok=True)
                    audit.save_json(Path(os.path.join(reports_dir, "inlet_audit.json")))
                    self.log.info(f"Inlet QC audit saved: {reports_dir}/inlet_audit.json")
                except Exception as e:
                    self.log.warning(f"InletQC audit skipped: {e}")

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

                # Save steady inlet audit
                try:
                    from aortacfd_lib.inlet_qc import InletAudit
                    from aortacfd_lib.utils.patch_processing import PatchProcessing

                    # Get inlet geometry from triSurface STL
                    tri_surface_dir = os.path.join(case_dir, "constant", "triSurface")
                    inlet_name = self.config['geometry']['inlet_keywords_ordered']
                    patch_proc = PatchProcessing(tri_surface_dir, inlet_name)
                    inlet_area = patch_proc.calculate_surface_area()
                    inlet_radius = np.sqrt(inlet_area / np.pi)

                    # Derive mean velocity and flow rate from whichever is configured
                    raw_velocity = inlet_config.get('velocity')
                    raw_flowrate_lmin = inlet_config.get('flowrate') or inlet_config.get('cardiac_output')
                    if raw_velocity:
                        mean_vel = float(raw_velocity)
                        mean_flow = mean_vel * inlet_area
                    elif raw_flowrate_lmin:
                        mean_flow = float(raw_flowrate_lmin) / 60.0 / 1000.0
                        mean_vel = mean_flow / inlet_area if inlet_area > 0 else None
                    else:
                        mean_vel = None
                        mean_flow = None

                    audit = InletAudit(
                        inlet_area_m2=inlet_area, inlet_radius_eq_m=inlet_radius,
                        inlet_center=[0, 0, 0], inlet_normal=[0, 0, 0],
                        csv_file="N/A",
                        data_type="constant",
                        n_points=0,
                        detected_period_s=0.0,
                        inlet_type=inlet_type,
                        profile=inlet_profile,
                        orientation="normal",
                        mean_velocity_ms=mean_vel,
                        mean_flow_m3s=mean_flow,
                    )
                    reports_dir = os.path.join(os.path.dirname(case_dir), "reports")
                    os.makedirs(reports_dir, exist_ok=True)
                    audit.save_json(Path(os.path.join(reports_dir, "inlet_audit.json")))
                    self.log.info(f"Inlet audit saved: {reports_dir}/inlet_audit.json")
                except Exception as e:
                    self.log.warning(f"InletQC audit skipped: {e}")

            # Set up Windkessel if needed (case-insensitive) - supports both 2-element and 3-element
            # Support both nested (boundary_conditions.outlets) and flattened (outlets) config structures
            outlets = self.config.get('boundary_conditions', {}).get('outlets') or self.config.get('outlets', {})
            outlet_type = outlets.get("type", "").upper()
            if outlet_type in ["2EWINDKESSEL", "3EWINDKESSEL"]:
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

    def _interpolate_mri_to_mesh_faces(self, mri_points_file, boundary_data_dir, time_dirs):
        """Interpolate MRI velocity data from MRI source points onto mesh face centres.

        The mesh face centres (already in boundaryData/points) are used as target points.
        MRI source points and velocity data are used as source. This ensures the flowrate
        is conserved regardless of mesh resolution.
        """
        from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator

        # Read MRI source points
        mri_pts = self._read_bare_points(mri_points_file)

        # Read mesh face centres (already written to boundaryData/points by the mesh step)
        mesh_pts_file = os.path.join(boundary_data_dir, 'points')
        mesh_pts = self._read_bare_points(mesh_pts_file)

        self.log.info(f"Mapping {len(mri_pts)} MRI points → {len(mesh_pts)} mesh face centres")

        # Build interpolators lazily (reuse across timesteps for the same component)
        # Process all time directories
        for time_str in sorted(time_dirs):
            u_file = os.path.join(boundary_data_dir, time_str, 'U')
            if not os.path.exists(u_file):
                continue

            # Read MRI velocity at this timestep
            mri_vels = self._read_bare_velocities(u_file)

            # Interpolate each component: linear with nearest-neighbor fallback
            interp_vels = np.zeros((len(mesh_pts), 3))
            for comp in range(3):
                lin = LinearNDInterpolator(mri_pts, mri_vels[:, comp])
                vals = lin(mesh_pts)
                nan_mask = np.isnan(vals)
                if nan_mask.any():
                    near = NearestNDInterpolator(mri_pts, mri_vels[:, comp])
                    vals[nan_mask] = near(mesh_pts[nan_mask])
                interp_vels[:, comp] = vals

            # Write interpolated velocity (bare format, matching mesh face count)
            n = len(interp_vels)
            lines = [str(n), '(']
            lines.extend(f'({v[0]:.6e} {v[1]:.6e} {v[2]:.6e})' for v in interp_vels)
            lines.append(')')
            with open(u_file, 'w') as f:
                f.write('\n'.join(lines) + '\n')

        self.log.info(f"Interpolated {len(time_dirs)} timesteps onto mesh face centres")

    @staticmethod
    def _read_bare_points(filepath):
        """Read OpenFOAM points file (bare or with FoamFile header)."""
        with open(filepath) as f:
            content = f.read()
        lines = content.strip().splitlines()
        # Skip any header lines to find the count line
        for i, line in enumerate(lines):
            if line.strip().isdigit():
                break
        n = int(lines[i].strip())
        pts = []
        for l in lines[i + 2:i + 2 + n]:
            vals = l.strip().strip('()').split()
            pts.append([float(v) for v in vals])
        return np.array(pts)

    @staticmethod
    def _read_bare_velocities(filepath):
        """Read OpenFOAM velocity file (bare or with FoamFile header)."""
        with open(filepath) as f:
            lines = f.readlines()
        # Skip any header lines to find the count line
        for i, line in enumerate(lines):
            if line.strip().isdigit():
                break
        n = int(lines[i].strip())
        vels = []
        for l in lines[i + 2:i + 2 + n]:
            vals = l.strip().strip('()').split()
            vels.append([float(v) for v in vals])
        return np.array(vels)

    def _find_inlet_csv(self, csv_filename: str, case_dir: str = None) -> str:
        """
        Find the inlet CSV file in the patient case directory.

        Searches in order:
        1. Case directory (where CSV files are copied for sensitivity studies)
        2. Same directory as config file (cases_input/PATIENT_ID/)
        3. Config's cad_folder if specified

        Args:
            csv_filename: Name of the CSV file (e.g., 'BPM120.csv')
            case_dir: The case directory path (optional)

        Returns:
            str: Full path to the CSV file, or None if not found
        """
        # First, try the case directory (where CSV files are copied for sensitivity studies)
        if case_dir:
            # Check directly in case directory
            csv_path = os.path.join(case_dir, csv_filename)
            if os.path.exists(csv_path):
                self.log.debug(f"Found inlet CSV in case directory: {csv_path}")
                return csv_path
            # Also check parent directory (for nested openfoam/ structure)
            case_parent = os.path.dirname(case_dir)
            csv_path = os.path.join(case_parent, csv_filename)
            if os.path.exists(csv_path):
                self.log.debug(f"Found inlet CSV in case parent directory: {csv_path}")
                return csv_path

        # Get the config file path from the config
        config_path = self.config.get('_config_file_path')

        if config_path:
            # Look in the same directory as the config file
            config_dir = os.path.dirname(config_path)
            csv_path = os.path.join(config_dir, csv_filename)
            if os.path.exists(csv_path):
                self.log.debug(f"Found inlet CSV at: {csv_path}")
                return csv_path

        # Try cad_folder if specified
        cad_folder = self.config.get('geometry', {}).get('cad_folder')
        if cad_folder and os.path.isdir(cad_folder):
            csv_path = os.path.join(cad_folder, csv_filename)
            if os.path.exists(csv_path):
                self.log.debug(f"Found inlet CSV in cad_folder: {csv_path}")
                return csv_path

        # Not found
        self.log.warning(f"Could not find inlet CSV file '{csv_filename}'")
        return None

    def _validate_inlet_csv(self, csv_path: str) -> bool:
        """
        Validate inlet CSV file format and content.

        Checks:
        1. File is not empty
        2. Has at least 2 columns (time, value)
        3. Contains valid numeric data
        4. Time values are monotonically increasing
        5. Has reasonable number of data points

        Args:
            csv_path: Path to the CSV file

        Returns:
            bool: True if valid, raises ValueError if invalid
        """
        import numpy as np

        try:
            # Check file is not empty
            if os.path.getsize(csv_path) == 0:
                raise ValueError(f"CSV file is empty: {csv_path}")

            # Read with numpy, handling comments and headers
            comment_lines = 0
            header_line = 0

            with open(csv_path, 'r') as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped or stripped.startswith('#'):
                        comment_lines += 1
                    else:
                        # First non-comment line - check if it's a header
                        if any(c.isalpha() for c in stripped):
                            header_line = 1
                        break

            skiprows = comment_lines + header_line
            data = np.genfromtxt(csv_path, delimiter=',', skip_header=skiprows)

            # Check shape
            if data.ndim < 2:
                raise ValueError(f"CSV must have at least 2 columns (time, value). Got 1D array.")
            if data.shape[1] < 2:
                raise ValueError(f"CSV must have at least 2 columns. Got {data.shape[1]} column(s).")
            if data.shape[0] < 2:
                raise ValueError(f"CSV must have at least 2 data points. Got {data.shape[0]} point(s).")

            # Check for NaN values
            if np.any(np.isnan(data)):
                nan_count = np.sum(np.isnan(data))
                raise ValueError(f"CSV contains {nan_count} NaN/invalid values. Check data format.")

            # Check time column is monotonically increasing
            times = data[:, 0]
            if not np.all(np.diff(times) > 0):
                raise ValueError("Time column must be monotonically increasing.")

            # Validate time range
            time_range = times[-1] - times[0]
            if time_range <= 0:
                raise ValueError(f"Invalid time range: {time_range}s")

            self.log.info(f"CSV validation passed: {data.shape[0]} points, time range {times[0]:.4f} to {times[-1]:.4f}s")
            return True

        except ValueError:
            raise  # Re-raise validation errors
        except Exception as e:
            raise ValueError(f"Error reading CSV file {csv_path}: {e}")


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
                if os.path.islink(item_path):
                    os.unlink(item_path)
                    logger.debug(f"Removed stale field symlink: {item}")
                elif os.path.isfile(item_path):
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
    """Generates the transportProperties, momentumTransport, and fvOptions files."""
    def execute(self, context: dict) -> bool:
        logger.info("Generating physical properties files...")
        writer = PhysicalPropertiesWriter(config=self.config, case_directory=context["case_directory"])
        writer.write_transportProperties_file()
        writer.write_momentumTransport_file()
        # Generate fvOptions for LES stability (bounds nut to prevent FPE)
        writer.write_fvOptions_file()
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
        writer.write_controlDict(final_control_dict=control_dict_template, cardiac_cycle=cardiac_cycle)

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
        # Check if Windkessel BC is used (case-insensitive)
        bc_type = self.config.get('boundary_conditions', {}).get('outlets', {}).get('type', '').upper()

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
