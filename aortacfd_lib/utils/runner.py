# aortacfd_lib/utils/runner.py
import subprocess
import os
from .logger import Logger

logger = Logger("AortaCFD.log").get_logger()

class CommandExecutionError(Exception):
    """Custom exception for failed command execution."""
    pass


class Runner:
    """Utility class for running external commands."""
    
    def __init__(self):
        """Initialize the Runner."""
        pass
    
    def run_command(
        self,
        command,
        timeout=None,
        cwd=None,
        env=None,
        capture_output=True
    ):
        """
        Run a command and return the result.
        
        Args:
            command: List of command arguments
            timeout: Timeout in seconds
            cwd: Working directory
            env: Environment variables
            capture_output: Whether to capture stdout/stderr
            
        Returns:
            CompletedProcess result
        """
        return subprocess.run(
            command,
            timeout=timeout,
            cwd=cwd,
            env=env,
            capture_output=capture_output,
            text=True
        )

def run_command(config: dict, command: list, case_directory: str, log_filename: str):
    """
    Executes a shell command after sourcing the OpenFOAM environment.

    Args:
        config (dict): The full application config, used to find the OF path.
        command (list): The command to run, as a list of strings.
        case_directory (str): The directory where the command should be run.
        log_filename (str): The name of the log file to capture output.
    """
    of_env_path = config.get("openfoam_env_path")
    if not of_env_path:
        raise ValueError("'openfoam_env_path' is not defined in your configuration.")

    # Convert the command list to a single string (e.g., "blockMesh -dict ...")
    command_str = ' '.join(command)
    
    # This is the key: we create a single shell command that first sources the
    # environment and then runs the desired OpenFOAM command.
    full_shell_command = f"source {of_env_path} && {command_str}"
    
    log_path = os.path.join(case_directory, log_filename)
    logger.info(f"Executing command in shell: {command_str}")

    try:
        with open(log_path, "w") as log_file:
            # We use 'bash -c' to execute the full command string in a new bash shell
            subprocess.run(
                ["bash", "-c", full_shell_command],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                check=True,
                text=True,
                cwd=case_directory
            )
    except subprocess.CalledProcessError:
        logger.error(f"Command failed. See full log at: {log_path}")
        raise CommandExecutionError(f"Command '{command_str}' failed.")
    except FileNotFoundError:
        # This error happens if 'bash' itself is not found
        logger.error("Error: 'bash' executable not found. This script requires a bash shell.")
        raise