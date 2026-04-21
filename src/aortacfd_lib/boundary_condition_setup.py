"""Boundary condition setup for OpenFOAM CFD simulations.

This module generates initial condition files (U, p, nut, k, omega) by reading
from the configuration and using Jinja2 templates.
"""

import os
import re
from typing import Any, Dict, Optional, Tuple

from jinja2 import Environment, FileSystemLoader

from .utils.logger import Logger
from .utils.ofVersionAdapter import OFVersionAdapter
from .utils.patch_utils import detect_world_patch_mode, get_murray_law_cache_key
from .constants import (
    MMHG_TO_PA,
    SYSTOLIC_PRESSURE_DEFAULT,
    DIASTOLIC_PRESSURE_DEFAULT,
    AORTIC_DIAMETER_DEFAULT,
    AORTIC_VELOCITY_REFERENCE,
    C_MU,
    TURBULENCE_INTENSITY_DEFAULT,
    TURBULENCE_VISCOSITY_RATIO_DEFAULT,
    MIXING_LENGTH_FACTOR,
)

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

        # Auto-adjust stabilisation for LES
        self._apply_les_stabilisation_override()

        # Check if we need to calculate Murray's law flow distribution
        outlet_settings = self._prepare_outlet_settings()

        # Calculate inlet velocity vector for CONSTANT/PARABOLIC types
        inlet_velocity_vector = self._calculate_inlet_velocity_vector()

        # Calculate initial pressure for better convergence
        initial_pressure, outlet_initial_pressures = self._calculate_initial_pressure()

        # Check if a residual 'world' patch exists in the mesh (alongside proper patches)
        has_world_patch = False
        if not self.world_patch_mode:
            boundary_file = os.path.join(self.case_dir, "constant", "polyMesh", "boundary")
            if os.path.exists(boundary_file):
                with open(boundary_file, 'r') as f:
                    has_world_patch = bool(re.search(r'\bworld\b\s*\{', f.read()))

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
            "has_world_patch": has_world_patch,
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

        # Case-insensitive simulation type comparison
        sim_type = self.physics_settings.get('simulation_type', '').upper()

        if sim_type in ["RAS", "LES"]:
            context['header'] = self.version_adapter.get_foam_file_header("volScalarField", "nut")
            self._write_file_from_template("nut.tpl", os.path.join(zero_dir, "nut"), context)

        # Add RANS-specific fields (k, omega)
        if sim_type == "RAS":
            # Calculate turbulence parameters
            turbulence_params = self._calculate_turbulence_parameters()
            context.update(turbulence_params)
            
            # Generate k field
            context['header'] = self.version_adapter.get_foam_file_header("volScalarField", "k")
            self._write_file_from_template("k.tpl", os.path.join(zero_dir, "k"), context)
            
            # Generate omega field
            context['header'] = self.version_adapter.get_foam_file_header("volScalarField", "omega")
            self._write_file_from_template("omega.tpl", os.path.join(zero_dir, "omega"), context)
    
    def _apply_les_stabilisation_override(self):
        """
        Auto-disable hard backflow stabilisation for LES simulations.

        The stabilizedWindkesselVelocity BC uses a Heaviside step function
        H(-phi) to detect backflow. In LES, resolved turbulent fluctuations
        at outlet patches trigger the Heaviside frequently, creating
        discontinuous velocity gradients that feed into the subgrid model
        and cause nut blowup.

        For LES with Windkessel outlets:
        - Disable stabilisation (use pressureInletOutletVelocity instead)
        - This preserves the Windkessel pressure-flow coupling
        - Backflow is handled naturally by the pressure BC

        The user can override this by explicitly setting enable_stabilization: true
        in their config (the override only applies when not explicitly set).
        """
        sim_type = self.physics_settings.get('simulation_type', '').upper()
        if sim_type != "LES":
            return

        outlet_type = self.outlet_settings.get('type', 'zeroGradient').upper()
        if 'WINDKESSEL' not in outlet_type:
            return

        wk_settings = self.outlet_settings.get('windkessel_settings', {})

        # Only override if user hasn't explicitly set it
        if 'enable_stabilization' not in wk_settings:
            self.log.warning(
                "LES detected: auto-disabling hard backflow stabilisation at "
                "Windkessel outlets. The Heaviside step function in "
                "stabilizedWindkesselVelocity creates velocity gradient "
                "discontinuities that cause nut blowup in LES. "
                "Using pressureInletOutletVelocity instead."
            )
            wk_settings['enable_stabilization'] = False
            self.outlet_settings.setdefault('windkessel_settings', {}).update(wk_settings)
        elif wk_settings.get('enable_stabilization', False):
            self.log.warning(
                "LES with hard backflow stabilisation enabled. This can cause "
                "nut blowup from Heaviside-induced velocity gradient discontinuities. "
                "Consider enable_stabilization: false for LES."
            )

    def _prepare_outlet_settings(self):
        """
        Prepare outlet settings, automatically calculating Murray's law if needed.
        Only calculate Murray's law for Windkessel cases.
        """
        outlet_settings = self.outlet_settings.copy()

        # Only process Windkessel cases (case-insensitive)
        outlet_type = outlet_settings.get('type', 'ZEROGRADIENT').upper()
        if outlet_type not in ['2EWINDKESSEL', '3EWINDKESSEL']:
            self.log.info(f"Using outlet type: {outlet_type}")
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
        # STL files in constant/triSurface/ are PRE-SCALED to meters during case setup
        tri_surface_dir = os.path.join(self.case_dir, "constant", "triSurface")
        inlet_patch_name = self.geom_settings['inlet_keywords_ordered']

        patch_processor = PatchProcessing(tri_surface_dir, inlet_patch_name)

        # Determine velocity magnitude from either velocity, flowrate, or cardiac_output
        # Note: flowrate is an alias for cardiac_output
        if 'flowrate' in self.inlet_settings and 'cardiac_output' not in self.inlet_settings:
            self.inlet_settings['cardiac_output'] = self.inlet_settings['flowrate']

        if 'cardiac_output' in self.inlet_settings:
            # Calculate velocity from cardiac output (L/min) and inlet area
            cardiac_output_Lmin = self.inlet_settings['cardiac_output']
            cardiac_output_m3s = cardiac_output_Lmin / 60.0 / 1000.0  # Convert L/min to m³/s

            # Get inlet area (STLs are pre-scaled to meters, no scale_factor needed)
            inlet_area = patch_processor.calculate_surface_area()

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

        # Get inlet normal direction from geometry (STLs are pre-scaled, no scale_factor)
        try:
            _, _, inlet_normal = patch_processor.calculate_inlet_center_radius()

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
                    outlet_center, _, _ = outlet_processor.calculate_inlet_center_radius()
                    outlet_centers.append(outlet_center)

                if outlet_centers:
                    inlet_center = patch_processor.calculate_inlet_center_radius()[0]
                    # Use wall centroid as robust interior reference
                    wall_name = self.geom_settings.get('wall_keywords_ordered', 'wall')
                    wall_stl = os.path.join(tri_surface_dir, f"{wall_name}.stl")
                    if os.path.exists(wall_stl):
                        from stl import mesh as stl_mesh
                        wm = stl_mesh.Mesh.from_file(wall_stl)
                        interior_ref = np.array([np.mean(wm.vectors[:, :, i]) for i in range(3)])
                    else:
                        interior_ref = np.mean(outlet_centers, axis=0)
                    flow_direction = interior_ref - inlet_center
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
    
    
    def _calculate_turbulence_parameters(self) -> Dict[str, float]:
        """
        Calculate turbulence parameters for RANS simulation.

        Based on typical cardiovascular flow conditions using k-omega SST model.

        Returns:
            Dictionary containing:
            - k_initial: Initial turbulent kinetic energy (m²/s²)
            - omega_initial: Initial specific dissipation rate (1/s)
            - turbulence_intensity: Turbulence intensity fraction
            - mixing_length: Mixing length for boundary conditions (m)
        """
        # Get turbulence parameters from physics settings or use defaults
        turbulence_intensity = self.physics_settings.get(
            'turbulence_intensity', TURBULENCE_INTENSITY_DEFAULT
        )
        turbulence_viscosity_ratio = self.physics_settings.get(
            'turbulence_viscosity_ratio', TURBULENCE_VISCOSITY_RATIO_DEFAULT
        )

        # Estimate characteristic velocity from inlet settings
        if 'mean_velocity' in self.inlet_settings:
            U_ref = self.inlet_settings['mean_velocity']
        else:
            U_ref = AORTIC_VELOCITY_REFERENCE

        # Calculate turbulent kinetic energy: k = 1.5 * (U * I)^2
        k_initial = 1.5 * (U_ref * turbulence_intensity) ** 2

        # Calculate characteristic length scale (hydraulic diameter estimate)
        L_ref = AORTIC_DIAMETER_DEFAULT

        # Calculate omega: omega = k^0.5 / (C_mu^0.25 * L)
        omega_initial = k_initial**0.5 / (C_MU**0.25 * L_ref)

        # Calculate mixing length for omega boundary condition
        mixing_length = MIXING_LENGTH_FACTOR * L_ref

        return {
            'k_initial': k_initial,
            'omega_initial': omega_initial,
            'turbulence_intensity': turbulence_intensity,
            'mixing_length': mixing_length
        }

    def _calculate_initial_pressure(self):
        """
        Calculate initial pressure field based on outlet boundary conditions.

        Supports multiple initialization methods via 'initial_pressure_method' setting:

        - 'diastolic' (default): End-diastolic pressure - physically correct if simulation
          starts at end-diastole (most common and recommended)

        - 'systolic': Peak systolic pressure

        - 'map': Mean Arterial Pressure using physiologically correct formula:
          MAP = DBP + (1/3) × (SBP - DBP) = (2×DBP + SBP) / 3
          Accounts for diastole being ~2/3 of cardiac cycle.
          Reference: Klabunde (2011) Cardiovascular Physiology Concepts

        - 'mean' or 'arithmetic': Simple arithmetic mean (SBP + DBP) / 2
          Less accurate than MAP but sometimes used in literature

        - 'zero': Gauge pressure (0 Pa) - for non-physiological simulations

        DEPRECATED (not recommended):
        - 'windkessel': P = Q_mean × R_total - AVOID: Creates non-uniform pressure
          gradients causing velocity spikes and numerical instability.

        For non-Windkessel BC: Always initialize to 0 (gauge pressure).

        IMPORTANT - Why uniform diastolic pressure is recommended:
            Per Pfaller et al. (2021), uniform pressure initialization is critical
            for numerical stability. Non-uniform pressures create large gradients
            that cause velocity spikes as the solver equilibrates the pressure field.
            The exact pressure value matters less than spatial uniformity - flow
            converges in 1-2 cardiac cycles regardless of initial pressure.

        Returns:
            tuple: (internal_field_pressure, outlet_pressures_dict)
                - internal_field_pressure: Uniform pressure for internal field (Pa)
                - outlet_pressures_dict: Dictionary mapping outlet names to pressures (Pa)

        References:
            - Pfaller MR, et al. On the Periodicity of Cardiovascular Fluid
              Dynamics Simulations. Ann Biomed Eng. 2021.
            - Klabunde RE. Cardiovascular Physiology Concepts. 2nd ed. 2011.
            - Westerhof N, et al. The arterial Windkessel. Med Biol Eng Comput. 2009.
        """
        outlet_type = self.outlet_settings.get('type', 'zeroGradient').upper()  # Case-insensitive

        if outlet_type in ['2EWINDKESSEL', '3EWINDKESSEL']:
            # Get Windkessel pressure settings
            wk_settings = self.outlet_settings.get('windkessel_settings', {})

            # Get systolic and diastolic pressures (mmHg)
            systolic = wk_settings.get('systolic_pressure', SYSTOLIC_PRESSURE_DEFAULT)
            diastolic = wk_settings.get('diastolic_pressure', DIASTOLIC_PRESSURE_DEFAULT)

            # Get initialization method (default: diastolic - simulation starts at end-diastole)
            init_method = wk_settings.get('initial_pressure_method', 'diastolic').lower()

            # Calculate pressure based on method
            # Reference: Klabunde (2011) Cardiovascular Physiology Concepts
            pulse_pressure = systolic - diastolic

            if init_method == 'diastolic':
                # End-diastolic pressure - physically correct if simulation starts at end-diastole
                p_init_mmHg = diastolic
                method_desc = "diastolic (simulation starts at end-diastole)"

            elif init_method == 'systolic':
                p_init_mmHg = systolic
                method_desc = "systolic (peak pressure)"

            elif init_method == 'map':
                # Correct MAP formula: diastole is ~2/3 of cardiac cycle
                # MAP = DBP + (1/3) × (SBP - DBP) = (2×DBP + SBP) / 3
                p_init_mmHg = diastolic + (1.0 / 3.0) * pulse_pressure
                method_desc = f"MAP = DBP + PP/3 = {diastolic} + {pulse_pressure}/3"

            elif init_method == 'mean' or init_method == 'arithmetic':
                # Simple arithmetic mean (less accurate but sometimes used)
                p_init_mmHg = (systolic + diastolic) / 2.0
                method_desc = "arithmetic mean (SBP + DBP) / 2"

            elif init_method == 'windkessel':
                # DEPRECATED: This method creates non-uniform pressure gradients
                # that cause velocity spikes and numerical instability.
                # Per Pfaller et al. (2021), uniform diastolic pressure is recommended.
                self.log.warning(
                    "DEPRECATED: 'windkessel' initialization method is not recommended. "
                    "Non-uniform pressure initialization creates large gradients causing "
                    "velocity spikes and numerical instability. Using 'diastolic' instead. "
                    "Reference: Pfaller et al. (2021) On the Periodicity of Cardiovascular "
                    "Fluid Dynamics Simulations."
                )
                # Fall back to diastolic (recommended approach)
                p_init_mmHg = diastolic
                method_desc = "diastolic (windkessel method deprecated)"

            elif init_method == 'zero':
                p_init_mmHg = 0.0
                method_desc = "zero (gauge pressure)"

            else:
                self.log.warning(f"Unknown initial_pressure_method '{init_method}', using 'diastolic'")
                p_init_mmHg = diastolic
                method_desc = "diastolic (default)"

            p_init_Pa = p_init_mmHg * MMHG_TO_PA

            # Try to get flow splits for outlet initialization
            flow_splits = wk_settings.get('flow_split', {})
            outlet_params = wk_settings.get('outlet_parameters', {})

            # Initialize all outlets to uniform pressure
            outlet_pressures = {}
            if flow_splits:
                for outlet in flow_splits.keys():
                    outlet_pressures[outlet] = p_init_Pa
            elif outlet_params:
                for outlet in outlet_params.keys():
                    outlet_pressures[outlet] = p_init_Pa

            self.log.info(f"Initial pressure field method: {method_desc}")
            self.log.info(f"  Systolic: {systolic} mmHg, Diastolic: {diastolic} mmHg")
            self.log.info(f"  Initial pressure: {p_init_mmHg:.1f} mmHg = {p_init_Pa:.0f} Pa")

            return p_init_Pa, outlet_pressures
        else:
            # For non-Windkessel cases (zeroGradient, fixedValue), use 0
            self.log.info(f"Outlet type '{outlet_type}': Initializing pressure to 0 Pa (gauge)")
            return 0.0, {}