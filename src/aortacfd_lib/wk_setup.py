import os
import sys
import numpy as np

from .utils.patch_processing import PatchProcessing
from .utils.logger import Logger

class WkSetup:
    """
    Computes 3-element Windkessel coefficients (R, C, Z) for all outlets
    and stores them in config for boundary condition templates to use.
    """

    def __init__(self, config: dict, stl_files: list, case_directory: str, cardiac_cycle: float):
        """Initialize with config and case context."""
        self.config = config
        self.stl_files = stl_files
        self.case_dir = case_directory
        self.cardiac_cycle = cardiac_cycle
        self.log = Logger("wk_setup").get_logger()

        self.geom_settings = self.config['geometry']
        self.inlet_settings = self.config['inlet']
        self.outlet_settings = self.config['outlets']
        self.wk_model_settings = self.outlet_settings['windkessel_settings']

    def execute(self):
        """Main method to compute Windkessel coefficients and store them in config."""
        self.log.info("Calculating Windkessel coefficients for all outlets...")
        
        tri_surface_dir = os.path.join(self.case_dir, "constant", "triSurface")
        scale_factor = self.geom_settings.get('scale_factor', 1e-3)
        
        inlet_patch_name = self.geom_settings['inlet_keywords_ordered']
        area_inlet = PatchProcessing(tri_surface_dir, inlet_patch_name).calculate_surface_area(scale_factor=scale_factor)

        outlet_patches = self.geom_settings['outlet_keywords_ordered']
        outlet_areas = {name: PatchProcessing(tri_surface_dir, name).calculate_surface_area(scale_factor=scale_factor) for name in outlet_patches}

        inlet_csv_path = os.path.join("cases_input", self.geom_settings['case_name'], self.inlet_settings['csv_file'])
        times, flow_inlet = self._read_inlet_flow(inlet_csv_path, self.inlet_settings['data_type'], area_inlet)

        methodology = self.wk_model_settings.get('methodology', 'murray_law_automatic')
        flow_split_ratios = self.wk_model_settings.get('flow_split')

        # Parse flow_split - can be dict or percentage value
        if flow_split_ratios is not None and not isinstance(flow_split_ratios, dict):
            # User provided a percentage (e.g., 30) - interpret as percentage for first N-1 outlets
            # with remainder going to last outlet
            flow_split_ratios = self._parse_flow_split_percentage(flow_split_ratios, outlet_patches)
            self.wk_model_settings['flow_split'] = flow_split_ratios

        if not flow_split_ratios:
            if methodology == 'murray_law_automatic':
                self.log.info("Flow split not provided; computing automatically using Murray's law...")
                try:
                    from .murray_calculator import MurrayCalculator

                    calculator = MurrayCalculator(self.case_dir, self.config)
                    flow_ratios = calculator.calculate_murray_flow_ratios()
                    murray_config = calculator.update_windkessel_coefficients(flow_ratios)

                    # Persist computed parameters back into configuration
                    self.wk_model_settings.update(murray_config)
                    flow_split_ratios = self.wk_model_settings.get('flow_split', {})
                except Exception as e:
                    self.log.warning(f"Automatic Murray flow split failed: {e}")
                    flow_split_ratios = {}
            else:
                flow_split_ratios = {}

            if not flow_split_ratios:
                self.log.info("Falling back to equal flow distribution among outlets.")
                num_outlets_fallback = len(outlet_patches)
                if num_outlets_fallback == 0:
                    raise ValueError("No outlet patches found for Windkessel flow split calculation.")
                equal_ratio = 1.0 / num_outlets_fallback
                flow_split_ratios = {name: equal_ratio for name in outlet_patches}
                self.wk_model_settings['flow_split'] = flow_split_ratios

        num_outlets = len(outlet_patches)
        Q_out = np.zeros((len(flow_inlet), num_outlets))
        
        for i, name in enumerate(outlet_patches):
            if name not in flow_split_ratios:
                raise ValueError(f"Flow split for outlet '{name}' not defined in boundary_conditions.json")
            Q_out[:, i] = flow_inlet * flow_split_ratios[name]

        # Calculate Windkessel coefficients based on methodology
        if methodology == 'murray_law_automatic':
            # Murray's law already populated outlet_parameters in config
            if 'outlet_parameters' in self.wk_model_settings:
                self.log.info("Using Murray's law Windkessel coefficients from outlet_parameters")
                R_wk, C_wk, Z_wk = self._extract_wk_from_outlet_params(outlet_patches)
            else:
                self.log.warning("Murray's law selected but outlet_parameters not found, using empirical fallback")
                methodology = 'WKEmpirical'  # Fall through to empirical calculation

        if methodology == 'WKEmpirical' or methodology not in ['murray_law_automatic']:
            # Pure empirical calculation: R = P/Q (no base scaling)
            self.log.info("Using WKEmpirical methodology with pure R=P/Q calculation")

            # Get pressure from config
            SP = self.wk_model_settings["systolic_pressure"]
            DP = self.wk_model_settings["diastolic_pressure"]
            rho = self.config['physics']['rho']
            mP = ((SP + DP) / 2.0) * 133.33  # Mean pressure in Pa

            # Empirical constants
            a = 13.3; b = 0.3; tau = 1.92

            # Calculate mean flows
            mean_flows = np.mean(Q_out, axis=0)
            areas_np = np.array([outlet_areas[name] for name in outlet_patches])

            # Pure empirical formulas (from literature)
            num_outlets = len(outlet_patches)
            R_wk = np.zeros(num_outlets)
            C_wk = np.zeros(num_outlets)
            Z_wk = np.zeros(num_outlets)

            for i, outlet in enumerate(outlet_patches):
                # R_total = mean_pressure / mean_flow (Ohm's law)
                if mean_flows[i] > 1e-15:
                    R_total = mP / mean_flows[i]
                else:
                    R_total = 1e15  # Very high for no flow

                # Wave speed: c = a / (2*sqrt(A/π))^b
                c = a / (2.0 * np.sqrt((areas_np[i] * 1e6) / np.pi))**b

                # Proximal resistance: Z = ρ*c/A
                Z_wk[i] = rho * c / areas_np[i]

                # Peripheral resistance: R = R_total - Z
                R_wk[i] = R_total - Z_wk[i]
                if R_wk[i] < 0:
                    R_wk[i] = 0.0

                # Compliance: C = τ/R_total
                C_wk[i] = tau / R_total

            self.log.info("Calculated PURE WKEmpirical coefficients (R=P/Q, no scaling):")
            for i, outlet in enumerate(outlet_patches):
                self.log.info(f"  {outlet}: R={R_wk[i]:.2e}, C={C_wk[i]:.2e}, Z={Z_wk[i]:.2e} "
                             f"(flow={flow_split_ratios[outlet]*100:.1f}%, mean_Q={mean_flows[i]:.6e} m³/s, "
                             f"area={areas_np[i]:.6e} m²)")

        # Store calculated WK coefficients back into config for use by p.tpl and U.tpl templates
        outlet_parameters = {}
        for i, name in enumerate(outlet_patches):
            outlet_parameters[name] = {
                "R": float(R_wk[i]),
                "C": float(C_wk[i]),
                "Z": float(Z_wk[i])
            }
        self.wk_model_settings['outlet_parameters'] = outlet_parameters
        self.log.info(f"Stored outlet_parameters in config for template rendering")
        self.log.info(f"Windkessel calculation complete - coefficients stored in config")

    def _parse_flow_split_percentage(self, flow_split_value, outlet_patches):
        """
        Parse flow_split percentage value into flow ratios.

        Args:
            flow_split_value: Percentage (e.g., 30 means 30% for first N-1 outlets, 70% for last)
            outlet_patches: List of outlet patch names

        Returns:
            Dictionary of flow ratios summing to 1.0
        """
        num_outlets = len(outlet_patches)
        if num_outlets == 0:
            raise ValueError("No outlet patches provided")

        # Convert percentage to fraction
        first_outlets_fraction = float(flow_split_value) / 100.0

        if num_outlets == 1:
            # Only one outlet gets 100%
            return {outlet_patches[0]: 1.0}

        # Split the first_outlets_fraction equally among first N-1 outlets
        num_first_outlets = num_outlets - 1
        each_first_outlet = first_outlets_fraction / num_first_outlets

        # Last outlet gets the remainder
        last_outlet_fraction = 1.0 - first_outlets_fraction

        flow_split_ratios = {}
        for i, outlet in enumerate(outlet_patches):
            if i < num_first_outlets:
                flow_split_ratios[outlet] = each_first_outlet
            else:
                flow_split_ratios[outlet] = last_outlet_fraction

        self.log.info(f"Parsed flow_split={flow_split_value}% as:")
        for outlet, ratio in flow_split_ratios.items():
            self.log.info(f"  {outlet}: {ratio:.4f} ({ratio*100:.1f}%)")

        return flow_split_ratios

    def _calculate_wk_empirical(self, flow_split_ratios, outlet_patches):
        """
        Calculate Windkessel coefficients using empirical formulas from flow data.

        Uses the classical empirical approach:
        - R_total = mean_pressure / mean_flow
        - Z (proximal resistance) from wave speed formula
        - R (peripheral resistance) = R_total - Z
        - C (compliance) from time constant

        Args:
            flow_split_ratios: Dictionary of flow ratios for each outlet
            outlet_patches: List of outlet patch names

        Returns:
            Tuple of (R_array, C_array, Z_array) as numpy arrays
        """
        # This method needs access to flow data and areas, so we need to pass them
        # For now, return default values and let the main execute() handle the calculation
        # This is called when methodology='WKEmpirical' is set

        self.log.info("WKEmpirical methodology requires flow data - will be calculated in main execute()")
        # Return None to signal that main execute() should handle it
        return None, None, None

    def _extract_wk_from_outlet_params(self, outlet_patches):
        """
        Extract R, C, Z values from outlet_parameters (populated by Murray's law).

        Args:
            outlet_patches: List of outlet patch names

        Returns:
            Tuple of (R_array, C_array, Z_array) as numpy arrays
        """
        num_outlets = len(outlet_patches)
        outlet_params = self.wk_model_settings.get('outlet_parameters', {})

        R_wk = np.zeros(num_outlets)
        C_wk = np.zeros(num_outlets)
        Z_wk = np.zeros(num_outlets)

        for i, outlet in enumerate(outlet_patches):
            if outlet in outlet_params:
                params = outlet_params[outlet]
                R_wk[i] = params.get('R', 1000.0)
                C_wk[i] = params.get('C', 1.0e-6)
                Z_wk[i] = params.get('Z', 100.0)
            else:
                # Fallback to default values
                self.log.warning(f"Outlet {outlet} not found in outlet_parameters, using defaults")
                R_wk[i] = 1000.0
                C_wk[i] = 1.0e-6
                Z_wk[i] = 100.0

        self.log.info("Extracted Windkessel coefficients from outlet_parameters:")
        for i, outlet in enumerate(outlet_patches):
            self.log.info(f"  {outlet}: R={R_wk[i]:.1f}, C={C_wk[i]:.2e}, Z={Z_wk[i]:.1f}")

        return R_wk, C_wk, Z_wk

    # --- FILLED IN HELPER FUNCTION ---
    def _read_inlet_flow(self, file_path, data_type, inlet_area):
        """Reads the inlet flow CSV and converts to flow rate if necessary."""
        if not os.path.isfile(file_path):
            self.log.error(f"Could not find inlet data file: {file_path}")
            raise FileNotFoundError(f"Could not find inlet data file: {file_path}")

        with open(file_path, 'r') as f:
            first_line = f.readline()
            if "time" in first_line.lower() or "flow" in first_line.lower() or "velocity" in first_line.lower():
                Q_data = np.loadtxt(file_path, delimiter=",", skiprows=1)
            else:
                Q_data = np.loadtxt(file_path, delimiter=",")

        if data_type == "flowRate":
            times = Q_data[:, 0]
            flow_inlet = Q_data[:, 1]
        elif data_type == "velocity":
            times = Q_data[:, 0]
            flow_inlet = Q_data[:, 1] * inlet_area
        else:
            self.log.error(f"Unknown data type: {data_type}. Use 'flowRate' or 'velocity'.")
            raise ValueError(f"Unknown data type: {data_type}. Use 'flowRate' or 'velocity'.")

        return times, flow_inlet