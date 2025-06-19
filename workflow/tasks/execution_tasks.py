# workflow/tasks/execution_tasks.py
import os
import subprocess
from ..base_task import Task, AortaCFDError # Import base classes and exceptions

# This helper function can be moved to a shared utility file later,
# but for simplicity, we can define it here for the execution tasks.
def run_command(command, log_file, cwd):
    """Helper function to run a shell command and log its output."""
    logger.info(f"Executing command: {' '.join(command)}")
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
    except subprocess.CalledProcessError:
        logger.error(f"Command '{' '.join(command)}' failed. See {log_file} for details.")
        raise AortaCFDError(f"Command '{' '.join(command)}' failed. See log file.")


class ExecuteMeshingTask(Task):
    """Runs the external meshing commands (blockMesh, snappyHexMesh, etc.)."""

    def execute(self, context: dict) -> bool:
        # This logic is from the run_mesh method in your appDriver.py
        self.log.info("Executing OpenFOAM meshing commands...")
        case_dir = context["case_directory"]

        run_command(["blockMesh"], os.path.join(case_dir, "log.blockMesh"), cwd=case_dir)
        run_command(["surfaceFeatures"], os.path.join(case_dir, "log.surfaceFeatures"), cwd=case_dir)

        snappy_settings = self.config.get("mesh", {}).get("SNAPPY_SETTINGS", {})
        if snappy_settings.get("parallel"):
            n_proc = snappy_settings.get("nProcessors", 1)
            run_command(["decomposePar", "-force"], os.path.join(case_dir, "log.decomposePar.preMesh"), cwd=case_dir)
            run_command(["mpirun", "-np", str(n_proc), "snappyHexMesh", "-parallel", "-overwrite"], os.path.join(case_dir, "log.snappyHexMesh"), cwd=case_dir)
            run_command(["reconstructParMesh", "-constant"], os.path.join(case_dir, "log.reconstructParMesh"), cwd=case_dir)
        else:
            run_command(["snappyHexMesh", "-overwrite"], os.path.join(case_dir, "log.snappyHexMesh"), cwd=case_dir)

        run_command(["checkMesh"], os.path.join(case_dir, "log.checkMesh"), cwd=case_dir)
        self.log.info("Meshing commands completed successfully.")
        return True


class ExecuteSolverTask(Task):
    """Runs the OpenFOAM solver (e.g., pimpleFoam)."""

    def execute(self, context: dict) -> bool:
        # This logic is from the run_simulation method in your appDriver.py
        self.log.info("Executing OpenFOAM solver...")
        case_dir = context["case_directory"]
        run_settings = self.config.get("run_settings", {})
        
        solver_cmd = "pimpleFoam" # Default solver
        if self.config.get("outlets", {}).get("type") == "3ElementWindkessel":
            solver_cmd = "pimpleFoam_WK_2.0" # Your custom solver
            self.log.info(f"Using custom Windkessel solver: {solver_cmd}")

        if run_settings.get("solution_type") == "parallel":
            n_proc = run_settings.get("subdomains", 1)
            run_command(["decomposePar", "-force"], os.path.join(case_dir, "log.decomposePar"), cwd=case_dir)
            run_command(["mpirun", "-np", str(n_proc), solver_cmd, "-parallel"], os.path.join(case_dir, "log.solver"), cwd=case_dir)
            run_command(["reconstructPar", "-latestTime"], os.path.join(case_dir, "log.reconstructPar"), cwd=case_dir)
        else:
            run_command([solver_cmd], os.path.join(case_dir, "log.solver"), cwd=case_dir)

        self.log.info("Solver execution completed successfully.")
        return True

class ExecutePostProcessingTask(Task):
    """Runs the pvbatch post-processing script."""
    
    def execute(self, context: dict) -> bool:
        # This logic is from the run_postprocessing method in your appDriver.py
        self.log.info("Executing post-processing script...")
        case_dir = context["case_directory"]
        pp_config = self.config.get("post_processing", {})
        
        # Set up environment variables for the script
        os.environ["CASE_PATH"] = case_dir
        # ... set other environment variables for time steps, fields, etc. ...
        
        pvbatch_exe = pp_config.get("pvbatch_exe")
        if not pvbatch_exe or not os.path.exists(pvbatch_exe):
            self.log.error(f"pvbatch executable not found at path: {pvbatch_exe}")
            return False
            
        script_path = os.path.join("aortacfd_lib", "post_processor.py")
        run_command([pvbatch_exe, script_path], os.path.join(case_dir, "log.postProcessing"), cwd=".")
        
        self.log.info("Post-processing completed successfully.")
        return True