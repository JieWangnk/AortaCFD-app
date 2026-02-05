import os
import shutil

from ..base_task import Task, AortaCFDError, logger
from aortacfd_lib.utils.runner import run_command, CommandExecutionError
from aortacfd_lib.utils.validation import MeshQualityChecker
from aortacfd_lib.utils.logger import Logger

class ExecuteMeshingTask(Task):
    """Runs the external meshing commands. STLs are pre-scaled to meters during case setup."""

    def execute(self, context: dict) -> bool:
        """This task contains the execution logic from your original run_mesh method."""
        logger.info("Executing OpenFOAM meshing commands...")
        case_dir = context["case_directory"]
        snappy_settings = self.config.get("mesh", {}).get("SNAPPY_SETTINGS", {})

        try:
            run_command(self.config, ["blockMesh"], case_dir, "log.blockMesh")
            run_command(self.config, ["surfaceFeatures"], case_dir, "log.surfaceFeatures")

            # Note: surfaceFeatures creates closeness files with .stl in name
            # e.g., wall_aorta.stl.closeness.internalPointCloseness
            # snappyHexMesh expects this format when geometry is named "wall_aorta.stl"
            # So we do NOT rename them - just distribute to processor directories

            if snappy_settings.get("parallel"):
                n_proc = snappy_settings.get("nProcessors", 1)

                # Temporarily override decomposeParDict for parallel meshing
                self._override_decompose_par_dict(case_dir, n_proc)

                # Use -noFields to only decompose geometry (mesh), not field data
                # Field files (0/p, 0/U) expect post-snappyHexMesh patches, not blockMesh "world" patch
                run_command(self.config, ["decomposePar", "-force", "-noFields"], case_dir, "log.decomposePar.preMesh")

                # Distribute closeness files to processor directories for parallel span refinement
                self._distribute_closeness_files(case_dir, n_proc)

                run_command(
                    self.config,
                    ["mpirun", "-np", str(n_proc), "snappyHexMesh", "-parallel", "-overwrite"],
                    case_dir,
                    "log.snappyHexMesh",
                )
                run_command(self.config, ["reconstructPar", "-constant"], case_dir, "log.reconstructPar")

                # Clean up processor directories to save disk space
                self._cleanup_processor_directories(case_dir)

                # Restore original decomposeParDict (using run_settings.subdomains for solver)
                solver_subdomains = self.config.get("run_settings", {}).get("subdomains", 1)
                self._override_decompose_par_dict(case_dir, solver_subdomains)
            else:
                run_command(self.config, ["snappyHexMesh", "-overwrite"], case_dir, "log.snappyHexMesh")

            run_command(self.config, ["checkMesh"], case_dir, "log.checkMesh")

            # Analyze mesh quality and provide alerts
            mesh_result = self._check_mesh_quality(case_dir)
            if mesh_result:
                Logger.console(f"     Mesh: {mesh_result}")

            # NOTE: transformPoints is NO LONGER NEEDED
            # STL files are pre-scaled to meters during case setup (CreateCaseStructureTask)
            # Mesh is generated directly in SI units (meters)
            logger.info("Mesh is already in SI units (meters) - no post-mesh scaling needed")

        except CommandExecutionError as e:
            logger.error(f"Meshing failed: {e}")
            return False
        
        # Create .foam file for easy ParaView loading
        self._create_foam_file(case_dir)
            
        logger.info("Meshing commands completed successfully.")
        return True
    
    def _create_foam_file(self, case_dir: str):
        """
        Creates a .foam file in the case directory for easy ParaView loading.
        This is a standard practice in OpenFOAM workflows.
        """
        foam_file_path = os.path.join(case_dir, f"{os.path.basename(case_dir)}.foam")
        try:
            with open(foam_file_path, 'w') as f:
                f.write("// OpenFOAM case file for ParaView\n")
                f.write("// Created automatically after mesh generation\n")
            logger.info(f"Created .foam file: {foam_file_path}")
        except OSError as e:
            logger.warning(f"Could not create .foam file: {e}")

    def _check_mesh_quality(self, case_dir: str) -> str:
        """
        Analyze mesh quality and provide alerts/recommendations.
        This helps identify potential simulation stability issues early.

        Returns:
            Summary string for console output (e.g., "125,432 cells, quality OK")
        """
        try:
            # Use new validation-based quality checker
            quality_checker = MeshQualityChecker(case_dir)
            result = quality_checker.validate_mesh_quality()

            # Log warnings
            for warning in result.warnings:
                logger.warning(f"Mesh quality warning: {warning}")

            # Log errors
            if not result.is_valid:
                for error in result.errors:
                    logger.error(f"Mesh quality error: {error}")
                logger.error("Mesh quality issues detected. Simulation may be unstable.")
                logger.warning("Consider:")
                logger.warning("  - Refining mesh settings")
                logger.warning("  - Using 'draft' profile with 1st order numerics")
                logger.warning("  - Reviewing geometry for sharp features")
                # Don't abort - let user decide whether to proceed
                return f"{result.cell_count:,} cells (quality issues)"
            else:
                if len(result.warnings) == 0:
                    logger.info("Mesh quality validation passed - no issues detected")
                    return f"{result.cell_count:,} cells, quality OK"
                else:
                    logger.info("Mesh quality acceptable with minor warnings")
                    return f"{result.cell_count:,} cells (minor warnings)"

        except Exception as e:
            logger.warning(f"Could not analyze mesh quality: {e}")
            logger.warning("Proceeding without mesh quality check")
            return ""

    def _fix_closeness_file_names(self, case_dir: str):
        """
        Fix closeness file names for snappyHexMesh compatibility.

        OpenFOAM 12's surfaceFeatures creates files like:
            wall_aorta.stl.closeness.internalPointCloseness
        But snappyHexMesh with insideSpan refinement expects:
            wall_aorta.closeness.internalPointCloseness

        This renames the files to remove the .stl extension.
        """
        import glob

        tri_surface_dir = os.path.join(case_dir, "constant", "triSurface")

        # Find all closeness files with .stl in the name
        closeness_files = glob.glob(os.path.join(tri_surface_dir, "*.stl.closeness.*"))

        fixed_count = 0
        for old_path in closeness_files:
            # Remove .stl from the filename
            new_path = old_path.replace(".stl.closeness.", ".closeness.")
            if old_path != new_path:
                try:
                    os.rename(old_path, new_path)
                    fixed_count += 1
                except OSError as e:
                    logger.warning(f"Could not rename {old_path}: {e}")

        if fixed_count > 0:
            logger.info(f"Fixed {fixed_count} closeness file names for snappyHexMesh compatibility")

    def _distribute_closeness_files(self, case_dir: str, n_proc: int):
        """
        Copy closeness files to processor directories for parallel meshing.

        For parallel snappyHexMesh with insideSpan refinement, each processor
        needs access to the closeness files in its own triSurface directory.

        Note: surfaceFeatures creates files like wall_aorta.closeness.internalPointCloseness
        But snappyHexMesh (when geometry is named "wall_aorta.stl") expects:
        wall_aorta.stl.closeness.internalPointCloseness

        So we need to copy with renamed files adding .stl before .closeness
        """
        import glob
        import re

        tri_surface_dir = os.path.join(case_dir, "constant", "triSurface")

        # Find all closeness files
        closeness_files = glob.glob(os.path.join(tri_surface_dir, "*.closeness.*"))

        if not closeness_files:
            logger.warning("No closeness files found - span refinement may not work")
            return

        logger.info(f"Distributing {len(closeness_files)} closeness files to {n_proc} processor directories...")

        for i in range(n_proc):
            proc_tri_dir = os.path.join(case_dir, f"processor{i}", "constant", "triSurface")

            # Create directory if it doesn't exist
            os.makedirs(proc_tri_dir, exist_ok=True)

            # Copy each closeness file with .stl added to name
            for src_file in closeness_files:
                src_basename = os.path.basename(src_file)
                # Convert: wall_aorta.closeness.xyz -> wall_aorta.stl.closeness.xyz
                # Use regex to insert .stl before .closeness
                if ".stl.closeness." not in src_basename:
                    dst_basename = re.sub(r'\.closeness\.', '.stl.closeness.', src_basename)
                else:
                    dst_basename = src_basename
                dst_file = os.path.join(proc_tri_dir, dst_basename)
                try:
                    shutil.copy2(src_file, dst_file)
                except OSError as e:
                    logger.warning(f"Could not copy {src_file} to processor{i}: {e}")

        logger.info("Closeness files distributed to processor directories")

    def _cleanup_processor_directories(self, case_dir: str):
        """
        Remove processor* directories after parallel meshing to save disk space.

        After reconstructPar -constant, the mesh is consolidated in constant/polyMesh
        and the processor directories are no longer needed.
        """
        import glob

        processor_dirs = glob.glob(os.path.join(case_dir, "processor*"))

        if not processor_dirs:
            return

        # Calculate total size before deletion
        total_size = 0
        for proc_dir in processor_dirs:
            for dirpath, dirnames, filenames in os.walk(proc_dir):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total_size += os.path.getsize(fp)
                    except OSError:
                        pass

        # Remove directories
        removed_count = 0
        for proc_dir in processor_dirs:
            try:
                shutil.rmtree(proc_dir)
                removed_count += 1
            except OSError as e:
                logger.warning(f"Could not remove {proc_dir}: {e}")

        # Format size for display
        if total_size > 1024 * 1024 * 1024:
            size_str = f"{total_size / (1024 * 1024 * 1024):.1f} GB"
        elif total_size > 1024 * 1024:
            size_str = f"{total_size / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{total_size / 1024:.1f} KB"

        logger.info(f"🧹 Cleaned up {removed_count} processor directories (freed {size_str})")

    def _override_decompose_par_dict(self, case_dir: str, n_subdomains: int):
        """
        Temporarily modify decomposeParDict to use a specific number of subdomains.

        This allows different processor counts for meshing vs solving:
        - Parallel meshing: uses SNAPPY_SETTINGS.nProcessors
        - Parallel solving: uses run_settings.subdomains

        Args:
            case_dir: Path to OpenFOAM case directory
            n_subdomains: Number of subdomains to set
        """
        import re

        decompose_dict_path = os.path.join(case_dir, "system", "decomposeParDict")

        if not os.path.exists(decompose_dict_path):
            logger.warning(f"decomposeParDict not found at {decompose_dict_path}")
            return

        try:
            # Read current file
            with open(decompose_dict_path, 'r') as f:
                content = f.read()

            # Replace numberOfSubdomains
            content = re.sub(
                r'numberOfSubdomains\s+\d+;',
                f'numberOfSubdomains  {n_subdomains};',
                content
            )

            # Replace n coefficients (for simple and hierarchical methods)
            content = re.sub(
                r'\bn\s+\(1 1 \d+\);',
                f'n               (1 1 {n_subdomains});',
                content
            )

            # Write back
            with open(decompose_dict_path, 'w') as f:
                f.write(content)

            logger.info(f"Updated decomposeParDict: numberOfSubdomains = {n_subdomains}")

        except Exception as e:
            logger.warning(f"Could not update decomposeParDict: {e}")

class ExecuteSolverTask(Task):
    """Runs the OpenFOAM 12 solver (foamRun with incompressibleFluid)."""

    def execute(self, context: dict) -> bool:
        """This task contains the execution logic from your original run_simulation method."""
        logger.info("Executing OpenFOAM 12 solver...")
        case_dir = context["case_directory"]
        run_settings = self.config.get("run_settings", {})

        solver_cmd = self.config["simulation_control"]["controlDict"].get("application", "foamRun")
        logger.info(f"Using OpenFOAM 12 solver: {solver_cmd} (incompressibleFluid)")

        try:
            if run_settings.get("solution_type") == "parallel":
                n_proc = run_settings.get("subdomains", 1)
                run_command(self.config, ["decomposePar", "-force"], case_dir, "log.decomposePar")
                run_command(self.config, ["mpirun", "-np", str(n_proc), solver_cmd, "-parallel"], case_dir, "log.solver")

                # Handle reconstruction based on skip_reconstruction flag
                skip_reconstruction = run_settings.get("skip_reconstruction", False)
                if skip_reconstruction:
                    logger.info("⏭️  Skipping reconstruction (skip_reconstruction=True)")
                    logger.info("📂 Case remains in decomposed state (processor directories)")
                    logger.info("💡 Use 'reconstructPar' manually if needed, or run: python run_patient.py <patient> --step reconstruct")
                    context["case_decomposed"] = True  # Flag for downstream tasks
                else:
                    logger.info("🔄 Reconstructing case...")
                    run_command(self.config, ["reconstructPar"], case_dir, "log.reconstructPar")
                    context["case_decomposed"] = False

                    # Clean up processor directories to save disk space
                    cleanup_processors = run_settings.get("cleanup_processors", True)
                    if cleanup_processors:
                        self._cleanup_processor_directories(case_dir)
            else:
                run_command(self.config, [solver_cmd], case_dir, "log.solver")
                context["case_decomposed"] = False

        except CommandExecutionError as e:
            logger.error(f"Solver execution failed: {e}")
            return False

        logger.info("Solver execution completed successfully.")
        Logger.console("     Solver completed")
        return True

    def _cleanup_processor_directories(self, case_dir: str):
        """
        Remove processor* directories after reconstruction to save disk space.

        After reconstructPar, the fields are consolidated in time directories
        and the processor directories are no longer needed.
        """
        import glob

        processor_dirs = glob.glob(os.path.join(case_dir, "processor*"))

        if not processor_dirs:
            return

        # Calculate total size before deletion
        total_size = 0
        for proc_dir in processor_dirs:
            for dirpath, dirnames, filenames in os.walk(proc_dir):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total_size += os.path.getsize(fp)
                    except OSError:
                        pass

        # Remove directories
        removed_count = 0
        for proc_dir in processor_dirs:
            try:
                shutil.rmtree(proc_dir)
                removed_count += 1
            except OSError as e:
                logger.warning(f"Could not remove {proc_dir}: {e}")

        # Format size for display
        if total_size > 1024 * 1024 * 1024:
            size_str = f"{total_size / (1024 * 1024 * 1024):.1f} GB"
        elif total_size > 1024 * 1024:
            size_str = f"{total_size / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{total_size / 1024:.1f} KB"

        logger.info(f"🧹 Cleaned up {removed_count} processor directories (freed {size_str})")


class ExecuteReconstructionTask(Task):
    """Reconstructs parallel case from processor directories."""

    def execute(self, context: dict) -> bool:
        """Reconstruct decomposed OpenFOAM case."""
        logger.info("Reconstructing case from processor directories...")
        case_dir = context["case_directory"]
        run_settings = self.config.get("run_settings", {})

        # Check if case is actually decomposed
        import glob
        processor_dirs = glob.glob(os.path.join(case_dir, "processor*"))
        if not processor_dirs:
            logger.warning("No processor directories found - case may already be reconstructed")
            return True

        try:
            # Run reconstructPar for all times
            run_command(self.config, ["reconstructPar"], case_dir, "log.reconstructPar")
            logger.info("✅ Case reconstructed successfully")
            context["case_decomposed"] = False
            return True

        except CommandExecutionError as e:
            logger.error(f"Reconstruction failed: {e}")
            return False


class ExecutePostProcessingTask(Task):
    """Runs the pvbatch post-processing script."""

    def execute(self, context: dict) -> bool:
        """This task contains the execution logic from your original run_postprocessing method."""
        logger.info("Executing post-processing script...")
        case_dir = context["case_directory"]
        pp_config = self.config.get("post_processing", {})

        # Setup environment variables for the script
        os.environ["CASE_PATH"] = case_dir

        # Try to find pvbatch executable
        pvbatch_exe = pp_config.get("pvbatch_exe")
        if not pvbatch_exe:
            # Try to find pvbatch in PATH
            import shutil as sh
            pvbatch_exe = sh.which("pvbatch")
            if not pvbatch_exe:
                logger.error("pvbatch executable not found in PATH")
                logger.error("Install ParaView: sudo apt-get install paraview")
                logger.error("Or set 'pvbatch_exe' in config.json post_processing section")
                return False
            logger.info(f"Found pvbatch: {pvbatch_exe}")

        if not os.path.exists(pvbatch_exe):
            logger.error(f"pvbatch executable not found at path: {pvbatch_exe}")
            return False

        # Find the post_processor.py script
        # Look in src/aortacfd_lib/ relative to current directory
        script_path = os.path.join(os.getcwd(), "src", "aortacfd_lib", "post_processor.py")
        if not os.path.exists(script_path):
            # Try alternative path
            script_path = os.path.join("aortacfd_lib", "post_processor.py")

        if not os.path.exists(script_path):
            logger.error(f"post_processor.py not found at: {script_path}")
            return False

        logger.info(f"Using post-processor script: {script_path}")
        logger.info(f"Case directory: {case_dir}")

        try:
            # Run pvbatch with the case directory as argument
            cmd = [pvbatch_exe, script_path, case_dir]
            logger.info(f"Running: {' '.join(cmd)}")

            run_command(self.config, cmd, ".", "log.postProcessing")
        except CommandExecutionError as e:
            logger.error(f"Post-processing failed: {e}")
            logger.warning("You can run post-processing manually:")
            logger.warning(f"  cd {case_dir}")
            logger.warning(f"  pvbatch {script_path}")
            return False

        logger.info("Post-processing completed successfully.")
        logger.info(f"Check results in: {case_dir}/Images/")
        return True


class ExecuteHemodynamicsTask(Task):
    """
    Compute hemodynamic metrics: WSS, TAWSS, OSI, RRT, pressure drop.

    This task can be run:
    1. After simulation completes (uses runtime function object data)
    2. As standalone post-processing (runs postProcess -func wallShearStress if needed)

    For pulsatile flow: Computes TAWSS, OSI, RRT from fieldAverage data
    For steady flow: Computes steady WSS and pressure drop only
    """

    def execute(self, context: dict) -> bool:
        """Execute hemodynamics post-processing."""
        logger.info("=" * 60)
        logger.info("HEMODYNAMICS ANALYSIS")
        logger.info("=" * 60)

        case_dir = context["case_directory"]

        # Determine output directory (reports folder)
        run_dir = os.path.dirname(case_dir)  # Parent of openfoam/
        reports_dir = os.path.join(run_dir, "reports")
        os.makedirs(reports_dir, exist_ok=True)

        try:
            from aortacfd_lib.hemodynamics_postprocessor import (
                HemodynamicsPostProcessor,
                run_hemodynamics_analysis
            )

            # Run complete analysis
            results = run_hemodynamics_analysis(case_dir, self.config, reports_dir)

            # Log summary
            logger.info("-" * 60)
            logger.info("HEMODYNAMICS SUMMARY")
            logger.info("-" * 60)
            logger.info(f"  Inlet type: {results.inlet_type}")

            if results.wss_mean > 0:
                logger.info(f"  WSS max/mean: {results.wss_max:.4f} / {results.wss_mean:.4f} Pa")

            if results.is_pulsatile and results.tawss_mean > 0:
                logger.info(f"  TAWSS max/mean: {results.tawss_max:.4f} / {results.tawss_mean:.4f} Pa")
                logger.info(f"  OSI max/mean: {results.osi_max:.4f} / {results.osi_mean:.4f}")
                logger.info(f"  RRT max/mean: {results.rrt_max:.4f} / {results.rrt_mean:.4f} Pa⁻¹")

            if results.pressure_drop_mmhg:
                logger.info("  Pressure drops:")
                for outlet, dp in results.pressure_drop_mmhg.items():
                    logger.info(f"    → {outlet}: {dp:.2f} mmHg")

            logger.info("-" * 60)
            logger.info(f"Full report: {reports_dir}/hemodynamics_report.txt")

            # Clean console summary
            if results.is_pulsatile and results.tawss_mean > 0:
                Logger.console(f"     TAWSS: {results.tawss_mean:.2f} Pa (mean), OSI: {results.osi_mean:.3f}")
            elif results.wss_mean > 0:
                Logger.console(f"     WSS: {results.wss_mean:.2f} Pa (mean)")
            return True

        except ImportError as e:
            logger.error(f"Failed to import hemodynamics module: {e}")
            logger.warning("Hemodynamics analysis skipped.")
            return False
        except Exception as e:
            logger.error(f"Hemodynamics analysis failed: {e}")
            import traceback
            traceback.print_exc()
            return False