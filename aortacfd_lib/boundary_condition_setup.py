import os
from jinja2 import Environment, FileSystemLoader
from .utils.logger import Logger
from .utils.ofVersionAdapter import OFVersionAdapter

class BoundaryConditionSetup:
    """
    Generates the initial condition files (U, p, etc.) by reading from the
    final config object and using Jinja2 templates.
    """
    def __init__(self, config: dict, case_directory: str):
        self.config = config
        self.case_dir = case_directory
        self.log = Logger("boundaryConditionSetup.log").get_logger()

        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_path), trim_blocks=True, lstrip_blocks=True)
        self.version_adapter = OFVersionAdapter(self.config['openfoam_version'])
        
        # Get all the necessary settings from the config
        self.geom_settings = self.config['geometry']
        self.inlet_settings = self.config['inlet']
        self.outlet_settings = self.config['outlets']
        self.physics_settings = self.config['physics']
        
        # Get the patch names that were auto-discovered by the ConfigBuilder
        self.inlet_patch = self.geom_settings['inlet_keywords_ordered']
        self.outlet_patches = self.geom_settings['outlet_keywords_ordered']
        self.wall_patch = self.geom_settings['wall_keywords_ordered']

    def write_all_bc_files(self):
        """A single method to generate all necessary boundary condition files."""
        self.log.info("Generating all boundary condition files...")
        
        # This context dictionary is now simpler, as it doesn't need initial_conditions
        context = {
            "inlet_patch": self.inlet_patch,
            "outlet_patches": self.outlet_patches,
            "wall_patch": self.wall_patch,
            "inlet_settings": self.inlet_settings,
            "outlet_settings": self.outlet_settings,
            "physics_settings": self.physics_settings
        }

        zero_dir = os.path.join(self.case_dir, "0")
        
        # Add headers to the context for each file
        context['header'] = self.version_adapter.get_foam_file_header("volVectorField", "U")
        self._write_file_from_template("U.tpl", os.path.join(zero_dir, "U"), context)
        
        context['header'] = self.version_adapter.get_foam_file_header("volScalarField", "p")
        self._write_file_from_template("p.tpl", os.path.join(zero_dir, "p"), context)

        if self.physics_settings['simulation_type'] in ["RAS", "LES"]:
            context['header'] = self.version_adapter.get_foam_file_header("volScalarField", "nut")
            self._write_file_from_template("nut.tpl", os.path.join(zero_dir, "nut"), context)

    def _write_file_from_template(self, template_name: str, output_path: str, context: dict):
        template = self.jinja_env.get_template(template_name)
        content = template.render(context)
        with open(output_path, "w") as f:
            f.write(content)
        self.log.info(f"Successfully wrote file: {os.path.basename(output_path)}")