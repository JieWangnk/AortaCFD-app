import os
from jinja2 import Environment, FileSystemLoader
from .utils.logger import Logger
from .utils.ofVersionAdapter import OFVersionAdapter

class PhysicalPropertiesWriter:
    """
    Generates transportProperties and momentumTransport files using a unified
    config object and Jinja2 templates.
    """
    def __init__(self, config: dict, case_directory: str):
        """The constructor now takes the unified config object."""
        self.config = config
        self.case_dir = case_directory
        self.log = Logger("physicalPropertiesSetup.log").get_logger()

        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_path))
        self.version_adapter = OFVersionAdapter(self.config['openfoam_version'])

    def write_transportProperties_file(self):
        template = self.jinja_env.get_template("transportProperties.tpl")
        context = {
            "header": self.version_adapter.get_foam_file_header("dictionary", "transportProperties"),
            "physics": self.config['physics']
        }
        output_path = os.path.join(self.case_dir, "constant", "transportProperties")
        with open(output_path, 'w') as f:
            f.write(template.render(context))

    def write_momentumTransport_file(self):
        template = self.jinja_env.get_template("momentumTransport.tpl")
        context = {
            "header": self.version_adapter.get_foam_file_header("dictionary", "momentumTransport"),
            "physics": self.config['physics']
        }
        output_path = os.path.join(self.case_dir, "constant", "momentumTransport")
        with open(output_path, 'w') as f:
            f.write(template.render(context))