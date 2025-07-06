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
        
        # Check if we need to calculate Murray's law flow distribution
        outlet_settings = self._prepare_outlet_settings()
        
        # This context dictionary is now simpler, as it doesn't need initial_conditions
        context = {
            "inlet_patch": self.inlet_patch,
            "outlet_patches": self.outlet_patches,
            "wall_patch": self.wall_patch,
            "inlet_settings": self.inlet_settings,
            "outlet_settings": outlet_settings,  # Use processed outlet settings
            "physics_settings": self.physics_settings,
            "template_vars": self.config.get('template_vars', {}),
            "openfoam_version": self.config.get('openfoam_version', '8'),
            "openfoam_major_version": self.config.get('openfoam_major_version', 8)
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
    
    def _prepare_outlet_settings(self):
        """
        Prepare outlet settings, automatically calculating Murray's law if needed.
        """
        outlet_settings = self.outlet_settings.copy()
        
        # Check if this is a Windkessel case without predefined flow_split
        if (outlet_settings.get('type') == '3EWINDKESSEL' and 
            'windkessel_settings' in outlet_settings):
            
            wk_settings = outlet_settings['windkessel_settings']
            
            # If flow_split is not defined, calculate using Murray's law
            if 'flow_split' not in wk_settings or not wk_settings['flow_split']:
                self.log.info("Flow split not defined - calculating using Murray's law from geometry...")
                
                try:
                    from .murray_calculator import MurrayCalculator
                    
                    calculator = MurrayCalculator(self.case_dir, self.config)
                    
                    # Calculate flow ratios from actual geometry
                    flow_ratios = calculator.calculate_murray_flow_ratios()
                    
                    # Update Windkessel coefficients based on Murray's law
                    murray_config = calculator.update_windkessel_coefficients(flow_ratios)
                    
                    # Update the outlet settings
                    wk_settings.update(murray_config)
                    
                    self.log.info("Successfully calculated Murray's law based coefficients")
                    self.log.info(f"Flow ratios: {flow_ratios}")
                    self.log.info(f"Outlet settings after update: {wk_settings.get('outlet_parameters', 'NOT FOUND')}")
                    
                except Exception as e:
                    self.log.warning(f"Could not calculate Murray's law coefficients: {e}")
                    self.log.info("Using default equal flow distribution")
                    
                    # Fallback to equal distribution
                    num_outlets = len(self.outlet_patches)
                    equal_ratio = 1.0 / num_outlets
                    wk_settings['flow_split'] = {
                        outlet: equal_ratio for outlet in self.outlet_patches
                    }
        
        return outlet_settings

    def _write_file_from_template(self, template_name: str, output_path: str, context: dict):
        template = self.jinja_env.get_template(template_name)
        content = template.render(context)
        with open(output_path, "w") as f:
            f.write(content)
        self.log.info(f"Successfully wrote file: {os.path.basename(output_path)}")