import os
from jinja2 import Environment, FileSystemLoader
from .utils.logger import Logger
from .utils.ofVersionAdapter import OFVersionAdapter
from .utils.patch_utils import detect_world_patch_mode, get_murray_law_cache_key

class BoundaryConditionSetup:
    """
    Generates the initial condition files (U, p, etc.) by reading from the
    final config object and using Jinja2 templates.
    """
    def __init__(self, config: dict, case_directory: str):
        self.config = config
        self.case_dir = case_directory
        self.log = Logger("boundary_conditions").get_logger()

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
        
        # Check if we have world patch scenario
        self.world_patch_mode = detect_world_patch_mode(self.case_dir, self.log)

    def write_all_bc_files(self):
        """A single method to generate all necessary boundary condition files."""
        self.log.info("Generating all boundary condition files...")
        
        # Check if we need to calculate Murray's law flow distribution
        outlet_settings = self._prepare_outlet_settings()
        
        # This context dictionary is now simpler, as it doesn't need initial_conditions
        context = {
            "inlet_patch": "world" if self.world_patch_mode else self.inlet_patch,
            "outlet_patches": ["world"] if self.world_patch_mode else self.outlet_patches,
            "wall_patch": "world" if self.world_patch_mode else self.wall_patch,
            "inlet_settings": self.inlet_settings,
            "outlet_settings": outlet_settings,  # Use processed outlet settings
            "physics_settings": self.physics_settings,
            "template_vars": self.config.get('template_vars', {}),
            "openfoam_version": self.config.get('openfoam_version', '8'),
            "openfoam_major_version": self.config.get('openfoam_major_version', 8),
            "world_patch_mode": self.world_patch_mode
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
            
        # Add RANS-specific fields (k, omega)
        if self.physics_settings['simulation_type'] == "RAS":
            # Calculate turbulence parameters
            turbulence_params = self._calculate_turbulence_parameters()
            context.update(turbulence_params)
            
            # Generate k field
            context['header'] = self.version_adapter.get_foam_file_header("volScalarField", "k")
            self._write_file_from_template("k.tpl", os.path.join(zero_dir, "k"), context)
            
            # Generate omega field
            context['header'] = self.version_adapter.get_foam_file_header("volScalarField", "omega")
            self._write_file_from_template("omega.tpl", os.path.join(zero_dir, "omega"), context)
    
    def _prepare_outlet_settings(self):
        """
        Prepare outlet settings, automatically calculating Murray's law if needed.
        Only calculate Murray's law for Windkessel cases.
        """
        outlet_settings = self.outlet_settings.copy()
        
        # Only process Windkessel cases
        if outlet_settings.get('type') != '3EWINDKESSEL':
            self.log.info(f"Using outlet type: {outlet_settings.get('type', 'ZEROGRADIENT')}")
            return outlet_settings
            
        # Check if this is a Windkessel case without predefined flow_split
        if 'windkessel_settings' in outlet_settings:
            wk_settings = outlet_settings['windkessel_settings']
            
            # Check if Murray's law results are already cached in context
            cache_key = get_murray_law_cache_key()
            if hasattr(self, 'context') and cache_key in self.context:
                self.log.info("Using cached Murray's law results from context")
                cached_results = self.context[cache_key]
                wk_settings.update(cached_results)
                return outlet_settings
            
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
                    
                    # Cache the results in context to avoid recalculation
                    if hasattr(self, 'context'):
                        self.context[cache_key] = murray_config
                    
                    self.log.info("Successfully calculated Murray's law based coefficients")
                    self.log.info(f"Flow ratios: {flow_ratios}")
                    
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
    
    
    def _calculate_turbulence_parameters(self):
        """
        Calculate turbulence parameters for RANS simulation.
        Based on typical cardiovascular flow conditions.
        """
        # Get turbulence parameters from physics settings or use defaults
        turbulence_intensity = self.physics_settings.get('turbulence_intensity', 0.05)  # 5% default
        turbulence_viscosity_ratio = self.physics_settings.get('turbulence_viscosity_ratio', 10.0)  # 10:1 default
        
        # Estimate characteristic velocity from inlet settings
        if 'mean_velocity' in self.inlet_settings:
            U_ref = self.inlet_settings['mean_velocity']
        else:
            U_ref = 0.5  # Default reference velocity in m/s for aortic flow
        
        # Calculate turbulent kinetic energy: k = 1.5 * (U * I)^2
        k_initial = 1.5 * (U_ref * turbulence_intensity) ** 2
        
        # Calculate characteristic length scale (hydraulic diameter estimate)
        # For aortic flow, assume ~25mm diameter
        L_ref = 0.025  # 25mm in meters
        
        # Calculate omega: omega = k^0.5 / (C_mu^0.25 * L)
        # Where C_mu = 0.09 for k-omega SST
        C_mu = 0.09
        omega_initial = k_initial**0.5 / (C_mu**0.25 * L_ref)
        
        # Calculate mixing length for omega boundary condition
        mixing_length = 0.07 * L_ref  # 7% of characteristic length
        
        return {
            'k_initial': k_initial,
            'omega_initial': omega_initial,
            'turbulence_intensity': turbulence_intensity,
            'mixing_length': mixing_length
        }