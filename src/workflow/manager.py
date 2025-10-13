import os
try:
    from .base_task import logger, AortaCFDError
    from .tasks import setup_tasks, execution_tasks
except ImportError:
    from workflow.base_task import logger, AortaCFDError
    from workflow.tasks import setup_tasks, execution_tasks

class WorkflowManager:
    """
    Orchestrates the execution of a series of tasks based on a user command.
    """
    def __init__(self, config: dict):
        self.config = config
        self.context = {}
        self._register_tasks()

    def _register_tasks(self):
        """Creates a complete library of all available tasks."""
        self.available_tasks = {
            "create_case_structure": setup_tasks.CreateCaseStructureTask,
            "generate_mesh_files": setup_tasks.GenerateMeshFilesTask,
            "generate_physical_properties": setup_tasks.GeneratePhysicalPropertiesTask,
            "generate_numerical_schemes": setup_tasks.GenerateNumericalSchemesTask,
            "generate_solver_settings": setup_tasks.GenerateSolverSettingsTask,
            "generate_decompose_par_dict": setup_tasks.GenerateDecomposeParDictTask,
            "prepare_boundary_data": setup_tasks.PrepareBoundaryDataTask,
            "generate_bc_files": setup_tasks.GenerateBCFilesTask,
            "generate_control_dict": setup_tasks.GenerateControlDictTask,
            "update_control_dict": setup_tasks.GenerateControlDictTask,
            "generate_simulation_report": setup_tasks.GenerateSimulationReportTask,
            "execute_meshing": execution_tasks.ExecuteMeshingTask,
            "execute_solver": execution_tasks.ExecuteSolverTask,
            "execute_post": execution_tasks.ExecutePostProcessingTask
        }
        
    def run_workflow(self, command: str):
        """Looks up the recipe for a command and runs the tasks."""
        
        recipes = {
            # COMMAND 1: Generates all non-mesh-dependent dictionary files.
            "setup:dict": [
                "create_case_structure",
                "generate_mesh_files",
                "generate_physical_properties",
                "generate_numerical_schemes",
                "generate_solver_settings",
                "generate_decompose_par_dict",
                "generate_control_dict" # Writes preliminary controlDict
            ],

            # COMMAND 2: Generates BC files and data AFTER a mesh exists.
            # This is the command you will use to update BCs.
            "setup:bc": [
                "prepare_boundary_data",    # Runs writeMeshObj, InletMapping, etc.
                "generate_bc_files",        # Writes the final 0/ files
                "update_control_dict"       # Overwrites controlDict with final endTime
            ],

            # COMMAND 3: Executes the meshing utilities.
            "run:mesh": ["execute_meshing"],

            # COMMAND 4: Executes the solver.
            "run:solver": ["execute_solver"],

            # COMMAND 5: Executes post-processing.
            "run:post": ["execute_post"],
            "execute_post": ["execute_post"],  # Alias

            # COMMAND 7: A user-friendly alias to set up a case completely.
            "createCase": [
                "create_case_structure",
                "generate_mesh_files",
                "generate_physical_properties",
                "generate_numerical_schemes",
                "generate_solver_settings",
                "generate_decompose_par_dict",
                "generate_control_dict",
                "execute_meshing",
                "prepare_boundary_data",
                "generate_bc_files",
                "update_control_dict"
            ],

            # COMMAND 8: The full end-to-end run.
            "runAll": [
                "create_case_structure",
                "generate_mesh_files",
                "generate_physical_properties",
                "generate_numerical_schemes",
                "generate_solver_settings",
                "generate_decompose_par_dict",
                "generate_control_dict",
                "generate_simulation_report",  # Generate report after setup
                "execute_meshing",
                "prepare_boundary_data",
                "generate_bc_files",
                "update_control_dict",
                "execute_solver",
                "execute_post"
            ]
        }
        
        task_sequence = recipes.get(command)
        if not task_sequence:
            raise AortaCFDError(f"Unknown command '{command}'")

        # Set up the execution context with case directory (only if not already set)
        if "case_directory" not in self.context:
            geom_cfg = self.config["geometry"]
            refinement = geom_cfg.get("refinement_level", "default")
            self.context["case_directory"] = os.path.join(
                os.getcwd(), "output", "OPENFOAM", f"{geom_cfg['case_name']}_{refinement}"
            )
        logger.info(f"Starting workflow for command: '{command}'")
        for task_name in task_sequence:
            task_class = self.available_tasks.get(task_name)
            if not task_class:
                raise AortaCFDError(f"Task '{task_name}' is not registered in the manager.")
            task_instance = task_class(self.config)
            logger.info(f"--- Executing Task: {task_instance.__class__.__name__} ---")
            success = task_instance.execute(self.context)
            if not success:
                logger.error(f"Task '{task_name}' failed. Aborting workflow.")
                raise AortaCFDError(f"Workflow aborted due to failure in task: {task_name}")
        logger.info("Workflow completed successfully.")