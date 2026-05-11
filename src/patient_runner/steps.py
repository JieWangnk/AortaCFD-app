"""
Workflow step interface - provides individual workflow step access
"""

from typing import List, Dict, Any
from .core import PatientCaseRunner


class WorkflowSteps:
    """
    Provides individual workflow step execution capabilities.

    Workflow steps available:
    1. case - Create case structure and configuration files
    2. mesh - Generate mesh (blockMesh, surfaceFeatures, snappyHexMesh)
    3. boundary - Setup boundary conditions and flow data
    4. regenerate-numerics - Regenerate fvSchemes/fvSolution with mesh-adaptive adjustments
    5. solver - Run CFD solver
    6. reconstruct - Reconstruct parallel case from processor directories
    7. post - Execute post-processing
    """

    def __init__(self):
        self.runner = PatientCaseRunner()
        self._step_mapping = {
            "case": "setup:dict",
            "mesh": "run:mesh",
            "boundary": "setup:bc",
            "solver": "run:solver",
            "reconstruct": "run:reconstruct",
            "post": "execute_post",
            "regenerate-numerics": "setup:regenerate-numerics",
        }
        self._step_descriptions = {
            "case": "Create case structure and configuration files",
            "mesh": "Generate mesh using blockMesh, surfaceFeatures, snappyHexMesh",
            "boundary": "Setup boundary conditions and flow data",
            "solver": "Run CFD solver (pimpleFoam/foamRun)",
            "reconstruct": "Reconstruct parallel case from processor directories",
            "post": "Execute post-processing",
            "regenerate-numerics": "Regenerate fvSchemes/fvSolution with mesh-adaptive adjustments (use AFTER meshing)",
        }

    def list_available_steps(self) -> List[str]:
        """List all available workflow steps."""
        return list(self._step_mapping.keys())

    def get_step_description(self, step: str) -> str:
        """Get description of a workflow step."""
        return self._step_descriptions.get(step, f"Unknown step: {step}")

    def run_step(self, patient_id: str, step: str, options: Dict[str, Any] = None) -> bool:
        """
        Run a specific workflow step for a patient.

        Args:
            patient_id: Patient identifier
            step: Workflow step name ('case', 'mesh', 'boundary', 'solver', 'post')
            options: Optional configuration overrides

        Returns:
            True if step completed successfully, False otherwise
        """
        if step not in self._step_mapping:
            raise ValueError(f"Invalid workflow step: {step}. Available: {list(self._step_mapping.keys())}")

        # Load patient case
        case_info = self.runner.load_patient_case(patient_id)

        # Prepare simulation
        sim_config = self.runner.prepare_simulation(case_info, options)

        # Execute the specific workflow step
        workflow_command = self._step_mapping[step]
        return self.runner.run_workflow_step(sim_config, workflow_command)

    def run_multiple_steps(self, patient_id: str, steps: List[str], options: Dict[str, Any] = None) -> bool:
        """
        Run multiple workflow steps in sequence.

        Args:
            patient_id: Patient identifier
            steps: List of workflow step names
            options: Optional configuration overrides

        Returns:
            True if all steps completed successfully, False otherwise
        """
        # Validate all steps first
        invalid_steps = [step for step in steps if step not in self._step_mapping]
        if invalid_steps:
            raise ValueError(f"Invalid workflow steps: {invalid_steps}")

        # Load patient case once
        case_info = self.runner.load_patient_case(patient_id)
        sim_config = self.runner.prepare_simulation(case_info, options)

        # Run steps in sequence
        for step in steps:
            workflow_command = self._step_mapping[step]
            success = self.runner.run_workflow_step(sim_config, workflow_command)
            if not success:
                return False

        return True

    def get_step_dependencies(self, step: str) -> List[str]:
        """
        Get the prerequisite steps for a given workflow step.

        Args:
            step: Workflow step name

        Returns:
            List of prerequisite step names
        """
        dependencies = {
            "case": [],
            "mesh": ["case"],
            "boundary": ["case", "mesh"],
            "regenerate-numerics": ["case", "mesh"],
            "solver": ["case", "mesh", "boundary"],
            "reconstruct": ["case", "mesh", "boundary", "solver"],
            "post": ["case", "mesh", "boundary", "solver"],
        }
        return dependencies.get(step, [])

    def validate_step_sequence(self, steps: List[str]) -> Dict[str, Any]:
        """
        Validate that a sequence of workflow steps is valid.

        Args:
            steps: List of workflow step names

        Returns:
            Dictionary with 'valid' boolean and 'errors' list
        """
        errors = []

        # Check for invalid steps
        invalid_steps = [step for step in steps if step not in self._step_mapping]
        if invalid_steps:
            errors.append(f"Invalid steps: {invalid_steps}")

        # Check dependencies
        completed_steps = set()
        for step in steps:
            if step in self._step_mapping:
                deps = self.get_step_dependencies(step)
                missing_deps = [dep for dep in deps if dep not in completed_steps]
                if missing_deps:
                    errors.append(f"Step '{step}' missing dependencies: {missing_deps}")
                completed_steps.add(step)

        return {"valid": len(errors) == 0, "errors": errors}

    def create_complete_patient_analysis(self, patient_id: str, options: Dict[str, Any] = None) -> str:
        """
        Run complete patient analysis workflow.

        Args:
            patient_id: Patient identifier
            options: Optional configuration overrides

        Returns:
            Path to results directory
        """
        return self.runner.run_patient_case(patient_id, options)
