import os
import shutil

from ..base_task import Task, AortaCFDError, logger
from aortacfd_lib.utils.runner import run_command, CommandExecutionError
from aortacfd_lib.utils.validation import MeshQualityChecker

class ExecuteMeshingTask(Task):
    """Runs the external meshing commands and scales the final mesh."""

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
                run_command(self.config, ["decomposePar", "-force"], case_dir, "log.decomposePar.preMesh")

                run_command(
                    self.config,
                    ["mpirun", "-np", str(n_proc), "snappyHexMesh", "-parallel", "-overwrite"],
                    case_dir,
                    "log.snappyHexMesh",
                )
                run_command(self.config, ["reconstructPar", "-constant"], case_dir, "log.reconstructPar")
            else:
                run_command(self.config, ["snappyHexMesh", "-overwrite"], case_dir, "log.snappyHexMesh")

            run_command(self.config, ["checkMesh"], case_dir, "log.checkMesh")

            # Analyze mesh quality and provide alerts
            self._check_mesh_quality(case_dir)

            logger.info("Scaling final mesh with transformPoints...")
            scale = self.config['geometry']['scale_factor']

            scale_arg = f"scale=({scale} {scale} {scale})"
            run_command(self.config, ["transformPoints", f'"{scale_arg}"'], case_dir, "log.transformPoints")

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
                run_command(self.config, ["reconstructPar"], case_dir, "log.reconstructPar")
            else:
                run_command(self.config, [solver_cmd], case_dir, "log.solver")
        
        except CommandExecutionError as e:
            logger.error(f"Solver execution failed: {e}")
            return False

        logger.info("Solver execution completed successfully.")
        return True

class ExecutePostProcessingTask(Task):
    """Runs the pvbatch post-processing script."""
    
    def execute(self, context: dict) -> bool:
        """This task contains the execution logic from your original run_postprocessing method."""
        logger.info("Executing post-processing script...")
        case_dir = context["case_directory"]
        pp_config = self.config.get("post_processing", {})
        
        # Setup environment variables for the script
        os.environ["CASE_PATH"] = case_dir
        # Additional environment variables can be added here if needed
        
        pvbatch_exe = pp_config.get("pvbatch_exe")
        if not pvbatch_exe or not os.path.exists(pvbatch_exe):
            logger.error(f"pvbatch executable not found at path: {pvbatch_exe}")
            return False
            
        # The script to run should be in your library
        script_path = os.path.join("aortacfd_lib", "post_processor.py")

        try:
            # We use the standard run_command, which will source the OF environment.
            # This isn't strictly necessary for pvbatch but is good practice.
            run_command(self.config, [pvbatch_exe, script_path], ".", "log.postProcessing")
        except CommandExecutionError as e:
            logger.error(f"Post-processing failed: {e}")
            return False
        
        logger.info("Post-processing completed successfully.")
        return True