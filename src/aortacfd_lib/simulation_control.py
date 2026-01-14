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
        self.log = Logger("simulation_control").get_logger()

        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_path))
        self.version_adapter = OFVersionAdapter(self.config['openfoam_version'])

    def write_controlDict(self, final_control_dict: dict, cardiac_cycle: float = None):
        """
        Writes the controlDict file using a finalized dictionary passed from a workflow task.

        Args:
            final_control_dict: Dictionary of controlDict settings
            cardiac_cycle: Cardiac cycle duration in seconds (for TAWSS averaging settings)
        """
        template = self.jinja_env.get_template("controlDict.tpl")

        # Use provided cardiac_cycle or fall back to config value
        if cardiac_cycle is None:
            cardiac_cycle = self.config.get('cardiac_cycle', 0.8)

        context = {
            "version": self.config["openfoam_version"],
            "controlDict": final_control_dict,
            "config": self.config,
            "cardiac_cycle": cardiac_cycle,  # Pass actual cardiac cycle to template
            "template_vars": self.config.get('template_vars', {}),
            "openfoam_version": self.config.get('openfoam_version', '8'),
            "openfoam_major_version": self.config.get('openfoam_major_version', 8)
        }

        output_path = os.path.join(self.case_dir, "system", "controlDict")
        with open(output_path, 'w') as f:
            f.write(template.render(context))
        self.log.info(f"Successfully wrote controlDict to {output_path}")