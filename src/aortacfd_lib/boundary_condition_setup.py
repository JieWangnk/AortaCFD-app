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
        # Support both flattened and nested config structures
        self.inlet_settings = self.config.get('boundary_conditions', {}).get('inlet') or self.config.get('inlet', {})
        self.outlet_settings = self.config.get('boundary_conditions', {}).get('outlets') or self.config.get('outlets', {})
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

        # Calculate inlet velocity vector for CONSTANT/PARABOLIC types
        inlet_velocity_vector = self._calculate_inlet_velocity_vector()

        # Calculate initial pressure for better convergence
        initial_pressure, outlet_initial_pressures = self._calculate_initial_pressure()

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
            "world_patch_mode": self.world_patch_mode,
            "inlet_velocity_vector": inlet_velocity_vector,
            "initial_pressure": initial_pressure,
            "outlet_initial_pressures": outlet_initial_pressures
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

    def _calculate_inlet_velocity_vector(self):
        """
        Calculate inlet velocity vector for CONSTANT/PARABOLIC inlet types.
        For TIMEVARYING/WOMERSLEY, returns None (use boundaryData).

        Returns:
            str: OpenFOAM vector format "(vx vy vz)" or None
        """
        import numpy as np
        from .utils.patch_processing import PatchProcessing

        inlet_type = self.inlet_settings.get('type', 'TIMEVARYING').upper()

        # Only calculate for CONSTANT/PARABOLIC types
        if inlet_type not in ['CONSTANT', 'PARABOLIC']:
            return None

        # Get inlet geometry first (needed for cardiac_output calculation)
        tri_surface_dir = os.path.join(self.case_dir, "constant", "triSurface")
        inlet_patch_name = self.geom_settings['inlet_keywords_ordered']
        scale_factor = self.geom_settings.get('scale_factor', 1e-3)

        patch_processor = PatchProcessing(tri_surface_dir, inlet_patch_name)

        # Determine velocity magnitude from either velocity, flowrate, or cardiac_output
        # Note: flowrate is an alias for cardiac_output
        if 'flowrate' in self.inlet_settings and 'cardiac_output' not in self.inlet_settings:
            self.inlet_settings['cardiac_output'] = self.inlet_settings['flowrate']

        if 'cardiac_output' in self.inlet_settings:
            # Calculate velocity from cardiac output (L/min) and inlet area
            cardiac_output_Lmin = self.inlet_settings['cardiac_output']
            cardiac_output_m3s = cardiac_output_Lmin / 60.0 / 1000.0  # Convert L/min to m³/s

            # Get inlet area
            inlet_area = patch_processor.calculate_surface_area(scale_factor=scale_factor)

            # Calculate velocity
            velocity_magnitude = cardiac_output_m3s / inlet_area

            self.log.info(f"Cardiac output: {cardiac_output_Lmin:.2f} L/min → velocity: {velocity_magnitude:.4f} m/s "
                         f"(inlet area: {inlet_area*1e6:.2f} mm²)")

            # Warn if both velocity and cardiac_output are specified
            if 'velocity' in self.inlet_settings:
                self.log.warning(f"Both 'velocity' and 'cardiac_output' specified. Using cardiac_output ({cardiac_output_Lmin} L/min).")

        elif 'velocity' in self.inlet_settings:
            # Use directly specified velocity
            velocity_magnitude = self.inlet_settings['velocity']
            self.log.info(f"Using specified velocity: {velocity_magnitude:.4f} m/s")
        else:
            self.log.error("Neither 'velocity', 'flowrate', nor 'cardiac_output' specified for CONSTANT/PARABOLIC inlet!")
            return "(0 0 0)"

        # For parabolic profile at the boundary, we use centerline velocity
        # (the actual parabolic distribution would need non-uniform BC)
        if inlet_type == 'PARABOLIC':
            # For uniform BC with parabolic intent, use mean velocity
            velocity_magnitude = velocity_magnitude / 2.0
            self.log.warning("PARABOLIC inlet type with fixedValue BC uses mean velocity. "
                           "For true parabolic profile, consider using groovyBC or codedFixedValue.")

        # Get inlet normal direction from geometry
        try:
            _, _, inlet_normal = patch_processor.calculate_inlet_center_radius(scale_factor=scale_factor)

            # Check orientation setting
            orientation = self.inlet_settings.get('orientation', 'auto').lower()

            if orientation == 'out':
                direction = inlet_normal
            elif orientation == 'in':
                direction = -inlet_normal
            elif orientation == 'auto':
                # Auto-detect using outlet positions (same logic as inlet_mapping.py)
                outlet_patches = self.geom_settings['outlet_keywords_ordered']
                outlet_centers = []

                for outlet_name in outlet_patches:
                    outlet_processor = PatchProcessing(tri_surface_dir, outlet_name)
                    outlet_center, _, _ = outlet_processor.calculate_inlet_center_radius(scale_factor=scale_factor)
                    outlet_centers.append(outlet_center)

                if outlet_centers:
                    inlet_center = patch_processor.calculate_inlet_center_radius(scale_factor=scale_factor)[0]
                    avg_outlet_center = np.mean(outlet_centers, axis=0)
                    flow_direction = avg_outlet_center - inlet_center
                    flow_direction = flow_direction / np.linalg.norm(flow_direction)

                    # Check alignment
                    dot_product = np.dot(inlet_normal, flow_direction)
                    if dot_product < 0:
                        direction = -inlet_normal  # Flip
                        self.log.info(f"Auto-orientation: flipping inlet normal (dot={dot_product:.3f})")
                    else:
                        direction = inlet_normal
                        self.log.info(f"Auto-orientation: keeping inlet normal (dot={dot_product:.3f})")
                else:
                    direction = inlet_normal
                    self.log.warning("Auto-orientation: no outlets found, using normal as-is")
            else:
                direction = inlet_normal

            # Calculate velocity vector
            velocity_vector = velocity_magnitude * direction

            # Format as OpenFOAM vector
            vector_str = f"({velocity_vector[0]:.6e} {velocity_vector[1]:.6e} {velocity_vector[2]:.6e})"

            self.log.info(f"Inlet velocity vector calculated: {vector_str} (magnitude={velocity_magnitude:.3f} m/s)")

            return vector_str

        except Exception as e:
            self.log.error(f"Failed to calculate inlet velocity vector: {e}")
            self.log.warning("Falling back to zero velocity (0 0 0)")
            return "(0 0 0)"

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

    def _calculate_initial_pressure(self):
        """
        Calculate initial pressure field based on outlet boundary conditions.
        For Windkessel BC: Initialize to flow-weighted pressure accounting for resistance distribution.
        For other BC: Initialize to 0 (gauge pressure).

        NOTE: Empirical testing shows this provides NO measurable convergence improvement.
        Convergence time remains ~10-15 cycles regardless of initialization method.
        Kept for code correctness and physical meaningfulness, but don't expect performance gains.
        See PRESSURE_INIT_POSTMORTEM.md for detailed analysis.

        This method accounts for the fact that outlets with:
        - High flow fraction + Low resistance → Lower pressure needed
        - Low flow fraction + High resistance → Higher pressure needed

        Returns:
            tuple: (internal_field_pressure, outlet_pressures_dict)
                - internal_field_pressure: Uniform pressure for internal field (Pa)
                - outlet_pressures_dict: Dictionary mapping outlet names to pressures (Pa)
        """
        outlet_type = self.outlet_settings.get('type', 'zeroGradient')

        if outlet_type == '3EWINDKESSEL':
            # Get Windkessel pressure settings
            wk_settings = self.outlet_settings.get('windkessel_settings', {})

            # Get systolic and diastolic pressures (mmHg)
            systolic = wk_settings.get('systolic_pressure', 120)  # Default adult normal
            diastolic = wk_settings.get('diastolic_pressure', 80)   # Default adult normal

            # Calculate baseline MAP
            MMHG_TO_PA = 133.322
            MAP_mmHg = (systolic + diastolic) / 2.0
            MAP_Pa = MAP_mmHg * MMHG_TO_PA

            # Try to get flow splits and outlet parameters for better initialization
            flow_splits = wk_settings.get('flow_split', {})
            outlet_params = wk_settings.get('outlet_parameters', {})

            # If we have resistance data, calculate flow-weighted pressure
            if flow_splits and outlet_params and len(outlet_params) > 0:
                try:
                    # Calculate average resistance weighted by flow
                    R_avg = 0.0
                    total_fraction = 0.0

                    for outlet, fraction in flow_splits.items():
                        if outlet in outlet_params:
                            R = outlet_params[outlet].get('R', 0)
                            R_avg += R * fraction
                            total_fraction += fraction

                    if total_fraction > 0:
                        R_avg = R_avg / total_fraction

                    # Initialize all outlets to uniform MAP to avoid initial pressure gradients
                    # NOTE: Resistance-weighted initialization was causing timestep collapse due to
                    # pressure-driven velocity spikes at t=0 (Co > 10). Uniform initialization is safer.
                    outlet_pressures = {}
                    for outlet in flow_splits.keys():
                        outlet_pressures[outlet] = MAP_Pa

                    # Use uniform MAP for internal field
                    p_init = MAP_Pa

                    self.log.info(f"Initializing pressure field to uniform MAP (avoids initial velocity spikes):")
                    self.log.info(f"  Systolic: {systolic} mmHg, Diastolic: {diastolic} mmHg")
                    self.log.info(f"  MAP = {MAP_mmHg:.1f} mmHg = {MAP_Pa:.0f} Pa")
                    self.log.info(f"  All outlets and internal field initialized to: {MAP_Pa:.0f} Pa")
                    self.log.info(f"  (Uniform to prevent pressure-driven acceleration at t=0)")

                    return p_init, outlet_pressures

                except Exception as e:
                    self.log.warning(f"Could not calculate resistance-weighted pressure: {e}")
                    self.log.info(f"Falling back to uniform MAP = {MAP_Pa:.0f} Pa")
                    return MAP_Pa, {}
            else:
                # No resistance data available, use uniform MAP
                self.log.info(f"Initializing pressure field to MAP for faster convergence:")
                self.log.info(f"  Systolic: {systolic} mmHg, Diastolic: {diastolic} mmHg")
                self.log.info(f"  MAP = {MAP_mmHg:.1f} mmHg = {MAP_Pa:.0f} Pa")
                self.log.info(f"  (Resistance data not yet available for flow-weighted initialization)")

                return MAP_Pa, {}
        else:
            # For non-Windkessel cases (zeroGradient, fixedValue), use 0
            self.log.info(f"Outlet type '{outlet_type}': Initializing pressure to 0 Pa (gauge)")
            return 0.0, {}