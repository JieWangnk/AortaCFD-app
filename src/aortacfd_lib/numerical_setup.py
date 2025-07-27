import os
from jinja2 import Environment, FileSystemLoader
from .utils.logger import Logger
from .utils.ofVersionAdapter import OFVersionAdapter

class FvSchemesWriter:
    """
    Generates the fvSchemes file using a unified config object and a
    single, intelligent Jinja2 template.
    """
    def __init__(self, config: dict, case_directory: str):
        """The constructor now takes the unified config object."""
        self.config = config
        self.case_dir = case_directory
        self.log = Logger("numerical_setup").get_logger()

        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_path))
        self.version_adapter = OFVersionAdapter(self.config['openfoam_version'])

    def write_fvSchemes_file(self):
        """
        Generates the fvSchemes file by rendering a template with the
        physics settings from the config.
        """
        # This single method replaces all the previous private _get... methods.
        template = self.jinja_env.get_template("fvSchemes.tpl")
        
        # The template will use these settings to decide which schemes to write.
        context = {
            "header": self.version_adapter.get_foam_file_header("dictionary", "fvSchemes"),
            "physics": self.config['physics'],
            "template_vars": self.config.get('template_vars', {}),
            "openfoam_version": self.config.get('openfoam_version', '8'),
            "openfoam_major_version": self.config.get('openfoam_major_version', 8)
        }
        
        output_path = os.path.join(self.case_dir, "system", "fvSchemes")
        with open(output_path, 'w') as f:
            f.write(template.render(context))
        self.log.info(f"Successfully wrote fvSchemes file to {output_path}")