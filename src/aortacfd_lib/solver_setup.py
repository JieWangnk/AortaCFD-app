import os
from jinja2 import Environment, FileSystemLoader
from .utils.logger import Logger
from .utils.ofVersionAdapter import OFVersionAdapter

class FvSolutionWriter:
    """
    Generates the fvSolution file using a unified config object and a
    single, intelligent Jinja2 template.
    """
    def __init__(self, config: dict, case_directory: str):
        """The constructor now takes the unified config object."""
        self.config = config
        self.case_dir = case_directory
        self.log = Logger("solver_setup").get_logger()

        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_path))
        self.version_adapter = OFVersionAdapter(self.config['openfoam_version'])

    def write_fvSolution_file(self):
        """
        Generates the fvSolution file by rendering a template with the
        solver settings defined in the simulation profile.
        """
        # This single method replaces all the previous private _get... methods.
        template = self.jinja_env.get_template("fvSolution.tpl")
        
        # The template will use these dictionaries to build the file.
        # This data comes directly from your sim_*.py profile.
        context = {
            "header": self.version_adapter.get_foam_file_header("dictionary", "fvSolution"),
            "fvSolution": self.config['fvSolution'],
            "template_vars": self.config.get('template_vars', {}),
            "openfoam_version": self.config.get('openfoam_version', '8'),
            "openfoam_major_version": self.config.get('openfoam_major_version', 8)
        }
        
        output_path = os.path.join(self.case_dir, "system", "fvSolution")
        with open(output_path, 'w') as f:
            f.write(template.render(context))
        self.log.info(f"Successfully wrote fvSolution file to {output_path}")