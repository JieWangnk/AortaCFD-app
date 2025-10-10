import os
import sys
import math
import numpy as np

from .utils.patch_processing import PatchProcessing
from .utils.logger import Logger

class WkSetup:
    """
    Computes 3-element Windkessel coefficients (R1, R2, C) for all outlets
    using clinical MAP-based methodology.

    Method: Clinical Windkessel (Westerhof et al. 2009)
    1. MAP = DP + (SP-DP)/3
    2. Flow distribution: Murray's law (r³) or Area-based
    3. R_total = (MAP - P_venous) / mean_flow
    4. R1 (proximal) = ρ·c/A (characteristic impedance from PWV)
    5. R2 (distal) = R_total - R1
    6. C (compliance) = tau / R2 (from diastolic decay time constant)

    References:
    - Westerhof et al., Med Biol Eng Comput 2009 (DC allocation)
    - Nichols & O'Rourke, McDonald's Blood Flow in Arteries (MAP formula)
    - Stergiopulos et al., J Biomech 1992 (tau=R2·C)
    """

    # Unit conversions
    MMHG_TO_PA = 133.322  # 1 mmHg = 133.322 Pa
    ML_TO_M3 = 1e-6       # 1 mL = 1e-6 m³

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
        self.log.info("=" * 80)
        self.log.info("Calculating 3-Element Windkessel Coefficients (Clinical Method)")
        self.log.info("=" * 80)

        tri_surface_dir = os.path.join(self.case_dir, "constant", "triSurface")
        scale_factor = self.geom_settings.get('scale_factor', 1e-3)

        # Step 0: Extract geometry
        inlet_patch_name = self.geom_settings['inlet_keywords_ordered']
        area_inlet = PatchProcessing(tri_surface_dir, inlet_patch_name).calculate_surface_area(scale_factor=scale_factor)

        outlet_patches = self.geom_settings['outlet_keywords_ordered']
        outlet_areas = {name: PatchProcessing(tri_surface_dir, name).calculate_surface_area(scale_factor=scale_factor)
                       for name in outlet_patches}

        # Calculate outlet radii for Murray's law
        outlet_radii = {name: math.sqrt(area / math.pi) for name, area in outlet_areas.items()}

        # Determine mean inlet flow
        inlet_type = self.inlet_settings.get('type', 'TIMEVARYING').upper()

        if inlet_type in ['TIMEVARYING', 'WOMERSLEY']:
            # Read inlet flow from CSV
            inlet_csv_path = os.path.join("cases_input", self.geom_settings['case_name'], self.inlet_settings['csv_file'])
            times, flow_inlet = self._read_inlet_flow(inlet_csv_path, self.inlet_settings['data_type'], area_inlet)
            mean_Q_inlet = np.mean(flow_inlet)
        elif inlet_type in ['CONSTANT', 'PARABOLIC']:
            # Calculate flow from either velocity or cardiac_output
            if 'cardiac_output' in self.inlet_settings:
                # Cardiac output specified directly (L/min)
                cardiac_output_Lmin = self.inlet_settings['cardiac_output']
                mean_Q_inlet = cardiac_output_Lmin / 60.0 / 1000.0  # Convert L/min to m³/s
                mean_velocity = mean_Q_inlet / area_inlet

                self.log.info(f"Constant inlet: cardiac_output = {cardiac_output_Lmin:.2f} L/min → "
                             f"velocity = {mean_velocity:.3f} m/s, mean flow Q = {mean_Q_inlet*1e6:.2f} mL/s")

                if 'velocity' in self.inlet_settings:
                    self.log.warning(f"Both 'velocity' and 'cardiac_output' specified. Using cardiac_output.")

            elif 'velocity' in self.inlet_settings:
                # Velocity specified
                velocity = self.inlet_settings['velocity']

                # For parabolic profile, velocity is centerline, mean is v_centerline/2
                if inlet_type == 'PARABOLIC':
                    mean_velocity = velocity / 2.0
                else:
                    mean_velocity = velocity

                mean_Q_inlet = mean_velocity * area_inlet
                self.log.info(f"Constant inlet: velocity = {velocity:.3f} m/s, mean flow Q = {mean_Q_inlet*1e6:.2f} mL/s")
            else:
                raise ValueError(f"CONSTANT/PARABOLIC inlet requires either 'velocity' or 'cardiac_output' parameter")
        else:
            raise ValueError(f"Unknown inlet type: {inlet_type}")

        # Step 1: Calculate MAP from cuff pressures
        SP = self.wk_model_settings.get("systolic_pressure", 120)  # mmHg
        DP = self.wk_model_settings.get("diastolic_pressure", 80)  # mmHg
        P_venous = self.wk_model_settings.get("venous_pressure", 0)  # mmHg (0-5 typical)

        MAP = DP + (SP - DP) / 3.0  # Mean arterial pressure (mmHg)
        MAP_Pa = MAP * self.MMHG_TO_PA  # Convert to Pa
        P_venous_Pa = P_venous * self.MMHG_TO_PA

        self.log.info(f"Step 1: Pressure targets")
        self.log.info(f"  Systolic pressure (SP): {SP} mmHg")
        self.log.info(f"  Diastolic pressure (DP): {DP} mmHg")
        self.log.info(f"  Mean arterial pressure (MAP): {MAP:.1f} mmHg ({MAP_Pa:.0f} Pa)")
        self.log.info(f"  Venous pressure (P_v): {P_venous} mmHg")
        self.log.info(f"  Driving pressure (MAP - P_v): {MAP - P_venous:.1f} mmHg")

        # Step 2: Flow distribution
        flow_split_method = self.wk_model_settings.get('flow_split_method', 'murray')
        flow_split_ratios = self.wk_model_settings.get('flow_split')

        if flow_split_ratios is None:
            # Auto-calculate using specified method
            if flow_split_method == 'murray':
                self.log.info(f"\nStep 2: Flow distribution (Murray's law: f_i = r³/Σr³)")
                flow_split_ratios = self._calculate_murray_flow_split(outlet_radii)
            elif flow_split_method == 'area':
                self.log.info(f"\nStep 2: Flow distribution (Area-based: f_i = A_i/ΣA_i)")
                flow_split_ratios = self._calculate_area_flow_split(outlet_areas)
            else:
                self.log.info(f"\nStep 2: Flow distribution (Equal split)")
                flow_split_ratios = self._calculate_equal_flow_split(outlet_patches)

            self.wk_model_settings['flow_split'] = flow_split_ratios
        else:
            self.log.info(f"\nStep 2: Flow distribution (User-specified percentage with {flow_split_method} method)")
            if not isinstance(flow_split_ratios, dict):
                # Flow split is a percentage - use the specified method to distribute
                flow_split_ratios = self._parse_flow_split_percentage(
                    flow_split_ratios,
                    outlet_patches,
                    flow_split_method,
                    outlet_radii if flow_split_method == 'murray' else outlet_areas
                )
                self.wk_model_settings['flow_split'] = flow_split_ratios

        # Calculate outlet flows
        num_outlets = len(outlet_patches)
        mean_Q_outlets = np.zeros(num_outlets)

        for i, name in enumerate(outlet_patches):
            mean_Q_outlets[i] = mean_Q_inlet * flow_split_ratios[name]
            self.log.info(f"  {name}: {flow_split_ratios[name]*100:.1f}% → mean Q = {mean_Q_outlets[i]*1e6:.2f} mL/s")

        # Step 3: Total (DC) resistance per outlet
        self.log.info(f"\nStep 3: Total resistance R_total = (MAP - P_v) / Q_mean")
        R_total = np.zeros(num_outlets)

        for i, outlet in enumerate(outlet_patches):
            if mean_Q_outlets[i] > 1e-15:
                R_total[i] = (MAP_Pa - P_venous_Pa) / mean_Q_outlets[i]
            else:
                R_total[i] = 1e15  # Very high for zero flow

            # Convert to mmHg·s/mL for logging
            R_total_mmHg = R_total[i] / (self.MMHG_TO_PA * 1e6)
            self.log.info(f"  {outlet}: R_total = {R_total[i]:.2e} Pa·s/m³ ({R_total_mmHg:.1f} mmHg·s/mL)")

        # Step 4: Proximal resistance R1 (characteristic impedance)
        self.log.info(f"\nStep 4: Proximal resistance R1 = ρ·c/A (characteristic impedance)")

        rho = self.config['physics']['rho']  # kg/m³
        pwv_method = self.wk_model_settings.get('pwv_method', 'empirical')
        pwv_value = self.wk_model_settings.get('pwv', None)  # m/s, if specified

        R1 = np.zeros(num_outlets)

        for i, outlet in enumerate(outlet_patches):
            A_i = outlet_areas[outlet]

            # Determine pulse wave velocity (PWV)
            if pwv_value is not None:
                # User-specified PWV
                c_i = pwv_value
                method = "user-specified"
            elif pwv_method == 'empirical':
                # Empirical PWV from diameter (typical aortic values)
                # Arch: 4-6 m/s, Thoracic: 5-7 m/s, Abdominal: 6-8 m/s
                # Use simple formula based on area
                diameter_mm = 2 * outlet_radii[outlet] * 1000
                if diameter_mm > 15:
                    c_i = 5.0  # Large vessels (arch/thoracic)
                elif diameter_mm > 8:
                    c_i = 6.0  # Medium vessels (abdominal)
                else:
                    c_i = 7.0  # Smaller vessels (branches)
                method = "empirical"
            else:
                # Fallback: use fraction of R_total
                R1[i] = 0.15 * R_total[i]
                self.log.info(f"  {outlet}: R1 = {R1[i]:.2e} Pa·s/m³ (15% of R_total)")
                continue

            # Calculate characteristic impedance
            R1[i] = rho * c_i / A_i

            R1_mmHg = R1[i] / (self.MMHG_TO_PA * 1e6)
            self.log.info(f"  {outlet}: PWV = {c_i:.1f} m/s ({method}) → R1 = {R1[i]:.2e} Pa·s/m³ ({R1_mmHg:.1f} mmHg·s/mL)")

        # Step 5: Distal resistance R2
        self.log.info(f"\nStep 5: Distal resistance R2 = R_total - R1")
        R2 = np.zeros(num_outlets)

        for i, outlet in enumerate(outlet_patches):
            R2[i] = R_total[i] - R1[i]
            if R2[i] < 0:
                self.log.warning(f"  {outlet}: R2 < 0, setting R1 = 0.1*R_total")
                R1[i] = 0.1 * R_total[i]
                R2[i] = 0.9 * R_total[i]

            R2_mmHg = R2[i] / (self.MMHG_TO_PA * 1e6)
            self.log.info(f"  {outlet}: R2 = {R2[i]:.2e} Pa·s/m³ ({R2_mmHg:.1f} mmHg·s/mL)")

        # Step 6: Compliance C
        self.log.info(f"\nStep 6: Compliance C = tau / R2 (from diastolic decay)")

        tau_systemic = self.wk_model_settings.get('tau', 1.8)  # seconds (typical: 1.5-2.0)
        C_distribution = self.wk_model_settings.get('compliance_distribution', 'proportional')

        C = np.zeros(num_outlets)

        if C_distribution == 'proportional':
            # Distribute compliance proportional to flow split
            # C_i = f_i * C_total, where C_total = tau / R_parallel
            R2_parallel_inv = np.sum(1.0 / R2)
            R2_parallel = 1.0 / R2_parallel_inv
            C_total = tau_systemic / R2_parallel

            self.log.info(f"  Systemic tau: {tau_systemic:.2f} s")
            self.log.info(f"  R2 parallel: {R2_parallel:.2e} Pa·s/m³")
            self.log.info(f"  C_total: {C_total:.2e} m³/Pa")

            for i, outlet in enumerate(outlet_patches):
                C[i] = flow_split_ratios[outlet] * C_total
                RC_i = R2[i] * C[i]
                C_mmHg = C[i] / (self.ML_TO_M3 / self.MMHG_TO_PA)
                self.log.info(f"  {outlet}: C = {C[i]:.2e} m³/Pa ({C_mmHg:.2e} mL/mmHg), RC = {RC_i:.2f} s")
        else:
            # Uniform tau for all outlets
            for i, outlet in enumerate(outlet_patches):
                C[i] = tau_systemic / R2[i]
                RC_i = R2[i] * C[i]
                C_mmHg = C[i] / (self.ML_TO_M3 / self.MMHG_TO_PA)
                self.log.info(f"  {outlet}: C = {C[i]:.2e} m³/Pa ({C_mmHg:.2e} mL/mmHg), RC = {RC_i:.2f} s")

        # Store calculated WK coefficients
        self.log.info(f"\n" + "=" * 80)
        self.log.info("SUMMARY: Windkessel Parameters (OpenFOAM units: Pa·s/m³, m³/Pa)")
        self.log.info("=" * 80)

        outlet_parameters = {}
        for i, name in enumerate(outlet_patches):
            outlet_parameters[name] = {
                "R": float(R2[i]),  # OpenFOAM uses R2 as "R"
                "C": float(C[i]),
                "Z": float(R1[i])   # OpenFOAM uses R1 as "Z"
            }
            self.log.info(f"{name:15s}: R(R2)={R2[i]:12.2e}  C={C[i]:12.2e}  Z(R1)={R1[i]:12.2e}")

        self.wk_model_settings['outlet_parameters'] = outlet_parameters
        self.log.info("=" * 80)
        self.log.info("Windkessel calculation complete - coefficients stored in config")
        self.log.info("=" * 80)

    def _calculate_murray_flow_split(self, outlet_radii: dict) -> dict:
        """
        Calculate flow split using Murray's law: f_i = r³ / Σr³

        Args:
            outlet_radii: Dictionary of outlet names to radii (m)

        Returns:
            Dictionary of flow split ratios (sum to 1.0)
        """
        r_cubed = {name: r**3 for name, r in outlet_radii.items()}
        total_r_cubed = sum(r_cubed.values())

        flow_split = {name: r3 / total_r_cubed for name, r3 in r_cubed.items()}

        self.log.info(f"  Murray's law (r³) distribution:")
        for name, ratio in flow_split.items():
            r_mm = outlet_radii[name] * 1000
            self.log.info(f"    {name}: r={r_mm:.2f} mm → {ratio*100:.1f}%")

        return flow_split

    def _calculate_area_flow_split(self, outlet_areas: dict) -> dict:
        """
        Calculate flow split based on areas: f_i = A_i / ΣA_i

        Args:
            outlet_areas: Dictionary of outlet names to areas (m²)

        Returns:
            Dictionary of flow split ratios (sum to 1.0)
        """
        total_area = sum(outlet_areas.values())
        flow_split = {name: area / total_area for name, area in outlet_areas.items()}

        self.log.info(f"  Area-based distribution:")
        for name, ratio in flow_split.items():
            A_mm2 = outlet_areas[name] * 1e6
            self.log.info(f"    {name}: A={A_mm2:.1f} mm² → {ratio*100:.1f}%")

        return flow_split

    def _calculate_equal_flow_split(self, outlet_patches: list) -> dict:
        """Equal flow distribution among outlets."""
        num_outlets = len(outlet_patches)
        equal_ratio = 1.0 / num_outlets
        return {name: equal_ratio for name in outlet_patches}

    def _parse_flow_split_percentage(self, flow_split_value, outlet_patches, method='murray', geometry_data=None):
        """
        Parse flow_split percentage value into flow ratios using specified distribution method.

        The percentage defines how to group outlets:
        - First N-1 outlets share the specified percentage
        - Last outlet gets the remainder
        - Within each group, distribution follows the specified method (Murray, area, or equal)

        Args:
            flow_split_value: Percentage (e.g., 40 means 40% for first N-1 outlets, 60% for last)
            outlet_patches: List of outlet patch names
            method: Distribution method - 'murray', 'area', or 'equal'
            geometry_data: Dictionary of outlet radii (for Murray) or areas (for area-based)

        Returns:
            Dictionary of flow ratios summing to 1.0

        Example:
            flow_split = 40, method = 'murray', 4 outlets:
            - First 3 outlets: share 40% by Murray's law (r³)
            - Outlet 4: gets remaining 60%
        """
        num_outlets = len(outlet_patches)
        if num_outlets == 0:
            raise ValueError("No outlet patches provided")

        # Convert percentage to fraction
        first_group_fraction = float(flow_split_value) / 100.0
        last_group_fraction = 1.0 - first_group_fraction

        if num_outlets == 1:
            return {outlet_patches[0]: 1.0}

        # Split outlets into groups
        num_first_outlets = num_outlets - 1
        first_outlets = outlet_patches[:num_first_outlets]
        last_outlet = outlet_patches[-1]

        flow_split_ratios = {}

        # Distribute within first group using specified method
        if method == 'murray' and geometry_data:
            # Murray's law distribution among first N-1 outlets
            first_group_data = {name: geometry_data[name] for name in first_outlets}
            r_cubed = {name: r**3 for name, r in first_group_data.items()}
            total_r_cubed = sum(r_cubed.values())

            for name in first_outlets:
                # Fraction within first group
                group_fraction = r_cubed[name] / total_r_cubed
                # Scale to overall first group allocation
                flow_split_ratios[name] = group_fraction * first_group_fraction

        elif method == 'area' and geometry_data:
            # Area-based distribution among first N-1 outlets
            first_group_data = {name: geometry_data[name] for name in first_outlets}
            total_area = sum(first_group_data.values())

            for name in first_outlets:
                # Fraction within first group
                group_fraction = first_group_data[name] / total_area
                # Scale to overall first group allocation
                flow_split_ratios[name] = group_fraction * first_group_fraction

        else:
            # Equal distribution among first N-1 outlets
            each_first_outlet = first_group_fraction / num_first_outlets
            for name in first_outlets:
                flow_split_ratios[name] = each_first_outlet

        # Last outlet gets the remainder
        flow_split_ratios[last_outlet] = last_group_fraction

        return flow_split_ratios

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
