import os
from ..base_task import Task, AortaCFDError, logger
from ...aortacfd_lib.utils.runner import run_command, CommandExecutionError

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
                run_command(self.config, ["mpirun", "-np", str(n_proc), "snappyHexMesh", "-parallel", "-overwrite"], case_dir, "log.snappyHexMesh")
                # OpenFOAM 12 uses reconstructPar instead of reconstructParMesh
                of_version = self.config.get('openfoam_major_version', 8)
                if of_version >= 12:
                    run_command(self.config, ["reconstructPar", "-constant"], case_dir, "log.reconstructPar")
                else:
                    run_command(self.config, ["reconstructParMesh", "-constant"], case_dir, "log.reconstructParMesh")
            else:
                run_command(self.config, ["snappyHexMesh", "-overwrite"], case_dir, "log.snappyHexMesh")

            run_command(self.config, ["checkMesh"], case_dir, "log.checkMesh")
            
            logger.info("Scaling final mesh with transformPoints...")
            scale = self.config['geometry']['scale_factor']
            
            # Use version-specific syntax for transformPoints
            of_version = self.config.get('openfoam_major_version', 8)
            if of_version >= 12:
                # OpenFOAM 12+ uses: transformPoints "scale=(0.001 0.001 0.001)"
                scale_arg = f"scale=({scale} {scale} {scale})"
                run_command(self.config, ["transformPoints", f'"{scale_arg}"'], case_dir, "log.transformPoints")
            else:
                # OpenFOAM 8 uses: transformPoints -scale '(0.001 0.001 0.001)'
                scale_arg = f"'({scale} {scale} {scale})'"
                run_command(self.config, ["transformPoints", "-scale", scale_arg], case_dir, "log.transformPoints")

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
    
class ExecuteSolverTask(Task):
    """Runs the OpenFOAM solver (e.g., pimpleFoam)."""

    def execute(self, context: dict) -> bool:
        """This task contains the execution logic from your original run_simulation method."""
        logger.info("Executing OpenFOAM solver...")
        case_dir = context["case_directory"]
        run_settings = self.config.get("run_settings", {})
        
        solver_cmd = self.config["simulation_control"]["controlDict"].get("application", "pimpleFoam")
        
        # Handle version-specific solver selection
        of_version = self.config.get('openfoam_major_version', 8)
        if self.config.get("outlets", {}).get("type") == "3ElementWindkessel":
            if of_version >= 12:
                # OpenFOAM 12+ uses foamRun with modularWKPressure boundary condition
                solver_cmd = "foamRun"
                logger.info(f"Using OpenFOAM 12 foamRun solver with Windkessel boundary conditions")
            else:
                # OpenFOAM 8 uses custom pimpleFoam_WK solver
                solver_cmd = "pimpleFoam_WK_2.0"
                logger.info(f"Using OpenFOAM 8 custom Windkessel solver: {solver_cmd}")
        else:
            logger.info(f"Using standard solver: {solver_cmd}")

        try:
            if run_settings.get("solution_type") == "parallel":
                n_proc = run_settings.get("subdomains", 1)
                run_command(self.config, ["decomposePar", "-force"], case_dir, "log.decomposePar")
                run_command(self.config, ["mpirun", "-np", str(n_proc), solver_cmd, "-parallel"], case_dir, "log.solver")
                run_command(self.config, ["reconstructPar", "-latestTime"], case_dir, "log.reconstructPar")
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
        # ... You can add other os.environ calls here if needed ...
        
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