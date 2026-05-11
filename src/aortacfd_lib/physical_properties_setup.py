import os
from jinja2 import Environment, FileSystemLoader
from .utils.logger import Logger
from .utils.ofVersionAdapter import OFVersionAdapter
from .template_context import prepare_fv_options_context


class PhysicalPropertiesWriter:
    """
    Generates transportProperties and momentumTransport files using a unified
    config object and Jinja2 templates.
    """

    def __init__(self, config: dict, case_directory: str):
        """The constructor now takes the unified config object."""
        self.config = config
        self.case_dir = case_directory
        self.log = Logger("physical_properties").get_logger()

        template_path = os.path.join(os.path.dirname(__file__), "..", "templates")
        self.jinja_env = Environment(  # nosec B701 - renders OpenFOAM dictionaries, not HTML
            loader=FileSystemLoader(template_path)
        )
        self.version_adapter = OFVersionAdapter(self.config["openfoam_version"])

    def write_transportProperties_file(self):
        template = self.jinja_env.get_template("transportProperties.tpl")
        context = {
            "header": self.version_adapter.get_foam_file_header("dictionary", "transportProperties"),
            "physics": self.config["physics"],
        }
        output_path = os.path.join(self.case_dir, "constant", "transportProperties")
        with open(output_path, "w") as f:
            f.write(template.render(context))

    def write_momentumTransport_file(self):
        template = self.jinja_env.get_template("momentumTransport.tpl")
        context = {
            "header": self.version_adapter.get_foam_file_header("dictionary", "momentumTransport"),
            "physics": self.config["physics"],
            "template_vars": self.config.get("template_vars", {}),
            "openfoam_version": self.config.get("openfoam_version", "8"),
            "openfoam_major_version": self.config.get("openfoam_major_version", 8),
        }
        output_path = os.path.join(self.case_dir, "constant", "momentumTransport")
        with open(output_path, "w") as f:
            f.write(template.render(context))

    def write_fvOptions_file(self):
        """
        Generates fvOptions file for LES stability.

        For LES simulations (especially WALE), adds a bound constraint on nut
        to prevent floating point exceptions from extreme SGS viscosity values.
        """
        template = self.jinja_env.get_template("fvOptions.tpl")

        # Pre-process business logic using template_context module
        # This extracts LES stability decisions into testable Python code
        preprocessed = prepare_fv_options_context(self.config)

        context = {
            # Pre-computed values
            "is_les": preprocessed["is_les"],
            "bound_nut": preprocessed["bound_nut"],
            "nut_min": preprocessed["nut_min"],
            # Raw data for backward compatibility
            "physics": self.config["physics"],
        }
        output_path = os.path.join(self.case_dir, "system", "fvOptions")
        with open(output_path, "w") as f:
            f.write(template.render(context))

        # Only log if LES (when fvOptions actually has content)
        if preprocessed["is_les"]:
            self.log.info("Generated fvOptions with nut bound for LES stability")
