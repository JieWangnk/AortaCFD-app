import os
from jinja2 import Environment, FileSystemLoader
from .utils.logger import Logger
from .utils.ofVersionAdapter import OFVersionAdapter

class SimulationSetup:
    """
    Generates the controlDict file using a configuration object and a template.
    """
    def __init__(self, config: dict, case_directory: str):
        """The constructor now takes the unified config object."""
        self.config = config
        self.case_dir = case_directory
        self.log = Logger("simulationSetup.log").get_logger()

        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_path))
        self.version_adapter = OFVersionAdapter(self.config['openfoam_version'])

    def write_controlDict(self, final_control_dict: dict):
        """
        Writes the controlDict file using a finalized dictionary passed from a workflow task.
        """
        template = self.jinja_env.get_template("controlDict.tpl")
        
        context = {
            "version": self.config["openfoam_version"],
            "controlDict": final_control_dict, # Use the finalized dict passed from the task
            "config": self.config
        }
        
        output_path = os.path.join(self.case_dir, "system", "controlDict")
        with open(output_path, 'w') as f:
            f.write(template.render(context))
        self.log.info(f"Successfully wrote controlDict to {output_path}")