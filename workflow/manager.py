# workflow/manager.py
import os
from .base_task import logger
# Now importing both setup and execution tasks
from .tasks import setup_tasks, execution_tasks

class AortaCFDError(Exception):
    pass

class WorkflowManager:
    def __init__(self, config: dict):
        self.config = config
        self.context = {}
        self._register_tasks()

    def _register_tasks(self):
        """Creates a library of all available tasks."""
        self.available_tasks = {
            # Setup Tasks
            "create_case_structure": setup_tasks.CreateCaseStructureTask,
            "generate_mesh_files": setup_tasks.GenerateMeshFilesTask,
            "prepare_boundary_data": setup_tasks.PrepareBoundaryDataTask, # Add this missing task
            "generate_bc_files": setup_tasks.GenerateBCFilesTask,
            "prepare_control_dict": setup_tasks.PrepareControlDictTask,
            # Execution Tasks
            "execute_meshing": execution_tasks.ExecuteMeshingTask,
            "execute_solver": execution_tasks.ExecuteSolverTask,
            "execute_post": execution_tasks.ExecutePostProcessingTask
        }

    def run_workflow(self, command: str):
        # The complete recipe book
        recipes = {
            "createCase": [
                "create_case_structure",
                "generate_mesh_files",
                "prepare_boundary_data",
                "generate_bc_files",
                "prepare_control_dict"
            ],
            "runMesh": ["execute_meshing"],
            "runSolver": ["execute_solver"],
            "runPost": ["execute_post"],
            "runAll": [
                "create_case_structure",
                "generate_mesh_files",
                "execute_meshing",
                "prepare_boundary_data",
                "generate_bc_files",
                "prepare_control_dict",
                "execute_solver",
                "execute_post"
            ]
        }
        
        task_sequence = recipes.get(command)
        if not task_sequence:
            raise AortaCFDError(f"Unknown command '{command}'")
        
        # Prepare the initial context
        geom_cfg = self.config["geometry"]
        refinement = geom_cfg.get("refinement_level", "default")
        self.context["case_directory"] = os.path.join(
            os.getcwd(), "OPENFOAM", f"{geom_cfg['case_name']}_{refinement}"
        )

        logger.info(f"Starting workflow for command: '{command}'")
        for task_name in task_sequence:
            task_class = self.available_tasks.get(task_name)
            if not task_class:
                raise AortaCFDError(f"Task '{task_name}' is not registered.")

            task_instance = task_class(self.config)
            logger.info(f"--- Executing Task: {task_instance.__class__.__name__} ---")
            success = task_instance.execute(self.context)

            if not success:
                logger.error(f"Task '{task_name}' failed. Aborting workflow.")
                raise AortaCFDError(f"Workflow aborted due to failure in task: {task_name}")
        logger.info("Workflow completed successfully.")