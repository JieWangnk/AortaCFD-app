# workflow/tasks/setup_tasks.py
import os
import shutil
from ..base_task import Task
# Import the logic classes from your new core library
from aortacfd_lib.mesh_setup import GeometryAnalyzer
from aortacfd_lib.boundary_condition_setup import BoundaryConditionSetup
from aortacfd_lib.physical_properties_setup import PhysicalPropertiesWriter
from aortacfd_lib.numerical_setup import FvSchemesWriter
from aortacfd_lib.solver_setup import FvSolutionWriter
from aortacfd_lib.simulation_control import SimulationSetup
from aortacfd_lib.utils.patch_processing import PatchProcessing

# Helper function from your original appDriver.py
def rotate_stl(stl_path, rotation_axis, rotation_angle, output_path):
    # ... (paste the rotate_stl function code here) ...
    pass

class CreateCaseStructureTask(Task):
    """Creates the case directory and copies/rotates the necessary geometry files."""
    def execute(self, context: dict) -> bool:
        # This logic is from the __create_OFcase method in your appDriver.py
        case_dir = context["case_directory"]
        self.log.info(f"Creating case structure in: {case_dir}")
        if os.path.exists(case_dir):
            shutil.rmtree(case_dir)
        os.makedirs(os.path.join(case_dir, "system"))
        os.makedirs(os.path.join(case_dir, "constant", "triSurface"))
        os.makedirs(os.path.join(case_dir, "0"))

        cad_folder = os.path.join("CAD", self.config["geometry"]["case_name"])
        # Add logic to copy (or rotate and copy) STLs from cad_folder to constant/triSurface
        # For simplicity, we'll just copy now.
        for f in os.listdir(cad_folder):
            if f.endswith('.stl'):
                shutil.copy(os.path.join(cad_folder, f), os.path.join(case_dir, "constant", "triSurface"))
        return True

class GenerateMeshFilesTask(Task):
    """Generates blockMeshDict, snappyHexMeshDict, and other mesh-related files."""
    def execute(self, context: dict) -> bool:
        # This logic is from the write_geometry_files method in your appDriver.py
        self.log.info("Generating mesh definition files...")
        analyzer = GeometryAnalyzer(
            DIRECTORY=context["case_directory"],
            global_config=self.config
        )
        analyzer.write_blockMeshDict()
        analyzer.write_snappyHexMeshDict()
        analyzer.write_surfaceFeaturesDict()
        return True

class GenerateBCFilesTask(Task):
    """Generates the 0/U, 0/p, and other initial condition field files."""
    def execute(self, context: dict) -> bool:
        self.log.info("Generating boundary condition field files...")
        # This logic is from the write_boundary_conditions method in your appDriver.py
        tri_surface_dir = os.path.join(context["case_directory"], "constant", "triSurface")
        stl_files = os.listdir(tri_surface_dir)
        
        bc_setup = BoundaryConditionSetup(context["case_directory"], stl_files, self.config)
        bc_setup.write_U_file()
        bc_setup.write_p_file()
        # ... add calls for other fields like nut, k, omega based on config ...
        return True

class PrepareControlDictTask(Task):
    """Generates the final controlDict file with calculated end time."""
    def execute(self, context: dict) -> bool:
        self.log.info("Preparing final controlDict...")
        # This is the new task we designed to handle dynamic endTime
        control_dict = self.config["simulation_control"]["controlDict"]
        
        # In a real run, a previous task would calculate this and put it in the context
        cardiac_cycle = context.get("cardiac_cycle", 0.8) # Using default for now
        num_cycles = self.config["simulation_control"]["number_of_cycles"]
        
        if control_dict.get("endTime") == "auto":
            control_dict["endTime"] = float(cardiac_cycle) * int(num_cycles)
        
        # Instantiate the writer and generate the file
        sim_setup = SimulationSetup(context["case_directory"], self.config)
        sim_setup.write_controlDict()
        return True