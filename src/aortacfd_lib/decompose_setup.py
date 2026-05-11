import os
from jinja2 import Environment, FileSystemLoader
from .utils.logger import Logger
from .utils.ofVersionAdapter import OFVersionAdapter


class SolnType:
    """
    Generates the decomposeParDict file using a unified config object
    and a Jinja2 template.
    """

    def __init__(self, config: dict, case_directory: str):
        """The constructor now takes the unified config object."""
        self.config = config
        self.case_dir = case_directory
        self.log = Logger("decompose_setup").get_logger()

        template_path = os.path.join(os.path.dirname(__file__), "..", "templates")
        self.jinja_env = Environment(  # nosec B701 - renders OpenFOAM dictionaries, not HTML
            loader=FileSystemLoader(template_path)
        )
        self.version_adapter = OFVersionAdapter(self.config["openfoam_version"])

    def write_decomposeParDict(self):
        """
        Generates the decomposeParDict file by rendering a template with the
        run settings from the simulation profile.
        """
        template = self.jinja_env.get_template("decomposeParDict.tpl")

        # The template will use these settings to build the file.
        context = {
            "header": self.version_adapter.get_foam_file_header("dictionary", "decomposeParDict"),
            "run_settings": self.config["run_settings"],
            "version": self.config["openfoam_version"],
        }

        output_path = os.path.join(self.case_dir, "system", "decomposeParDict")
        with open(output_path, "w") as f:
            f.write(template.render(context))
        self.log.info(f"Successfully wrote decomposeParDict file to {output_path}")
