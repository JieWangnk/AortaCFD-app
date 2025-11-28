import os
import shutil

from ..base_task import Task, AortaCFDError, logger
from aortacfd_lib.utils.runner import run_command, CommandExecutionError
from aortacfd_lib.utils.validation import MeshQualityChecker

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

            if snappy_settings.get("parallel"):
                n_proc = snappy_settings.get("nProcessors", 1)

                # Temporarily override decomposeParDict for parallel meshing
                self._override_decompose_par_dict(case_dir, n_proc)

                run_command(self.config, ["decomposePar", "-force"], case_dir, "log.decomposePar.preMesh")

                run_command(
                    self.config,
                    ["mpirun", "-np", str(n_proc), "snappyHexMesh", "-parallel", "-overwrite"],
                    case_dir,
                    "log.snappyHexMesh",
                )
                run_command(self.config, ["reconstructPar", "-constant"], case_dir, "log.reconstructPar")

                # Restore original decomposeParDict (using run_settings.subdomains for solver)
                solver_subdomains = self.config.get("run_settings", {}).get("subdomains", 1)
                self._override_decompose_par_dict(case_dir, solver_subdomains)
            else:
                run_command(self.config, ["snappyHexMesh", "-overwrite"], case_dir, "log.snappyHexMesh")

            run_command(self.config, ["checkMesh"], case_dir, "log.checkMesh")

            # Analyze mesh quality and provide alerts
            self._check_mesh_quality(case_dir)

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

    def _check_mesh_quality(self, case_dir: str):
        """
        Analyze mesh quality and provide alerts/recommendations.
        This helps identify potential simulation stability issues early.
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
            else:
                if len(result.warnings) == 0:
                    logger.info("Mesh quality validation passed - no issues detected")
                else:
                    logger.info("Mesh quality acceptable with minor warnings")

        except Exception as e:
            logger.warning(f"Could not analyze mesh quality: {e}")
            logger.warning("Proceeding without mesh quality check")

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
            else:
                run_command(self.config, [solver_cmd], case_dir, "log.solver")
                context["case_decomposed"] = False

        except CommandExecutionError as e:
            logger.error(f"Solver execution failed: {e}")
            return False

        logger.info("Solver execution completed successfully.")
        return True


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