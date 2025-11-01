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
    2. Flow distribution: Murray's law (r³) with optional main outlet percentage
    3. R_total = (MAP - P_venous) / mean_flow
    4. R1 (proximal) = ρ·c/A (characteristic impedance from PWV)
    5. R2 (distal) = R_total - R1
    6. C (compliance) = tau / R2 (from diastolic decay time constant)

    PHYSICAL UNITS (SI):
        Input Parameters:
            - systolic_pressure (SP): mmHg → converted to Pa (×133.322)
            - diastolic_pressure (DP): mmHg → Pa
            - venous_pressure (P_v): mmHg → Pa (default: 0 mmHg = 0 Pa)
            - pwv (pulse wave velocity): m/s (default: 6 m/s for aorta)
            - tau (diastolic decay time): s (default: 1.8 s)
            - blood density (ρ): kg/m³ (default: 1060 kg/m³)
            - flow rate (Q): m³/s (from inlet data)
            - vessel radius (r): m (from STL geometry)
            - vessel area (A): m² (A = πr²)

        Computed Windkessel Parameters:
            - R1 (proximal resistance): Pa·s/m³ = kg/(m⁴·s)
              Formula: R1 = ρ·c/A (characteristic impedance)
              Typical: 1e7-1e8 Pa·s/m³

            - R2 (distal resistance): Pa·s/m³
              Formula: R2 = R_total - R1
              Typical: 1e8-1e9 Pa·s/m³ (R2 >> R1)

            - C (compliance): m³/Pa = m⁴·s²/kg
              Formula: C = tau / R2
              Typical: 1e-9 to 1e-8 m³/Pa

        Physiological Ranges (adult aorta):
            - Systolic pressure: 90-140 mmHg (12-19 kPa)
            - Diastolic pressure: 60-90 mmHg (8-12 kPa)
            - Mean arterial pressure: 70-110 mmHg (9-15 kPa)
            - Cardiac output: 4-7 L/min (6.7e-5 to 1.2e-4 m³/s)
            - Pulse wave velocity: 4-10 m/s (increases with age/stiffness)
            - Diastolic decay time: 1.5-2.5 s

    Flow Split Options:
        - None: Auto Murray's law (Q_i ∝ r_i³) for all outlets
        - Percentage (e.g., 60): Main outlet (last) gets 60%, branches share 40% by Murray
        - Dict: User-specified ratios for each outlet

    References:
        - Westerhof et al., Med Biol Eng Comput 2009 (DC allocation)
        - Nichols & O'Rourke, McDonald's Blood Flow in Arteries (MAP formula)
        - Stergiopulos et al., J Biomech 1992 (tau=R2·C)
        - Reymond et al., J Biomech 2009 (lumped parameter models)
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
        # Support both flattened and nested config structures
        self.inlet_settings = self.config.get('boundary_conditions', {}).get('inlet') or self.config.get('inlet', {})
        self.outlet_settings = self.config.get('boundary_conditions', {}).get('outlets') or self.config.get('outlets', {})
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
            # Calculate flow from either velocity, flowrate, or cardiac_output
            # Note: flowrate is an alias for cardiac_output
            if 'flowrate' in self.inlet_settings and 'cardiac_output' not in self.inlet_settings:
                self.inlet_settings['cardiac_output'] = self.inlet_settings['flowrate']

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
                raise ValueError(f"CONSTANT/PARABOLIC inlet requires either 'velocity' (m/s), 'flowrate' (L/min), or 'cardiac_output' (L/min) parameter")
        else:
            raise ValueError(f"Unknown inlet type: {inlet_type}")

        # Step 1: Calculate MAP from cuff pressures
        SP = self.wk_model_settings.get("systolic_pressure", 120)  # mmHg
        DP = self.wk_model_settings.get("diastolic_pressure", 80)  # mmHg
        P_venous = self.wk_model_settings.get("venous_pressure", 0)  # mmHg (0-5 typical)

        # Use MATLAB formula: MAP = (SP + DP) / 2 (simple average)
        MAP = (SP + DP) / 2.0  # Mean arterial pressure (mmHg)
        MAP_Pa = MAP * self.MMHG_TO_PA  # Convert to Pa
        P_venous_Pa = P_venous * self.MMHG_TO_PA

        self.log.info(f"Step 1: Pressure targets")
        self.log.info(f"  Systolic pressure (SP): {SP} mmHg")
        self.log.info(f"  Diastolic pressure (DP): {DP} mmHg")
        self.log.info(f"  Mean arterial pressure (MAP): {MAP:.1f} mmHg ({MAP_Pa:.0f} Pa) [MATLAB formula: (SP+DP)/2]")
        self.log.info(f"  Venous pressure (P_v): {P_venous} mmHg")
        self.log.info(f"  Driving pressure (MAP - P_v): {MAP - P_venous:.1f} mmHg")

        # Step 2: Flow distribution
        flow_split_ratios = self.wk_model_settings.get('flow_split')

        if flow_split_ratios is None:
            # Auto-calculate using Murray's law (default)
            self.log.info(f"\nStep 2: Flow distribution (Murray's law: f_i = r³/Σr³)")
            flow_split_ratios = self._calculate_murray_flow_split(outlet_radii)
            self.wk_model_settings['flow_split'] = flow_split_ratios
        else:
            if not isinstance(flow_split_ratios, dict):
                # Flow split is a percentage for branches
                self.log.info(f"\nStep 2: Flow distribution (Branch percentage + area-based distribution - MATLAB method)")
                flow_split_ratios = self._parse_flow_split_percentage(
                    flow_split_ratios,
                    outlet_patches,
                    'area',  # MATLAB uses area-based, not Murray's law
                    outlet_radii
                )
                self.wk_model_settings['flow_split'] = flow_split_ratios
            else:
                # User provided complete dictionary of ratios
                self.log.info(f"\nStep 2: Flow distribution (User-specified ratios)")

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

        # Get density - support both 'blood_density' and 'rho' keys
        rho = self.config['physics'].get('blood_density', self.config['physics'].get('rho', 1060))  # kg/m³
        pwv_method = self.wk_model_settings.get('pwv_method', 'matlab')  # Default to MATLAB formula
        pwv_value = self.wk_model_settings.get('pwv', None)  # m/s, if specified

        # MATLAB PWV formula parameters
        pwv_a = self.wk_model_settings.get('pwv_a', 13.3)
        pwv_b = self.wk_model_settings.get('pwv_b', 0.3)

        R1 = np.zeros(num_outlets)

        for i, outlet in enumerate(outlet_patches):
            A_i = outlet_areas[outlet]
            A_mm2 = A_i * 1e6  # Convert m² to mm²

            # Determine pulse wave velocity (PWV)
            if pwv_value is not None:
                # User-specified PWV
                c_i = pwv_value
                method = "user-specified"
            elif pwv_method == 'matlab':
                # MATLAB formula: c = a / (2*sqrt(A_mm²/π))^b
                c_i = pwv_a / (2 * np.sqrt(A_mm2 / np.pi)) ** pwv_b
                method = f"MATLAB formula: {pwv_a}/(2√(A/π))^{pwv_b}"
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
            self.log.info(f"  {outlet}: A={A_mm2:.2f}mm², PWV = {c_i:.2f} m/s ({method}) → R1 = {R1[i]:.2e} Pa·s/m³ ({R1_mmHg:.1f} mmHg·s/mL)")

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
        self.log.info(f"\nStep 6: Compliance C = tau / R_total (from diastolic decay)")

        tau_systemic = self.wk_model_settings.get('tau', 1.92)  # seconds, MATLAB default: 1.92
        C_distribution = self.wk_model_settings.get('compliance_distribution', 'uniform')  # MATLAB uses uniform

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
            # Uniform tau for all outlets, C = tau / R2 (correct 3-element WK formula)
            self.log.info(f"  Systemic tau: {tau_systemic:.2f} s")
            for i, outlet in enumerate(outlet_patches):
                C[i] = tau_systemic / R2[i]  # Correct: C = tau / R2 (distal resistance only)
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

        # Generate flow distribution plot if inlet is time-varying
        if inlet_type in ['TIMEVARYING', 'WOMERSLEY']:
            # Save plot to reports folder
            reports_dir = os.path.join(os.path.dirname(self.case_dir), "reports")
            os.makedirs(reports_dir, exist_ok=True)
            plot_path = os.path.join(reports_dir, "flow_distribution.png")
            self.plot_flow_distribution(times, flow_inlet, flow_split_ratios, plot_path)

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

    def _parse_flow_split_percentage(self, flow_split_value, outlet_patches, method='area', geometry_data=None):
        """
        Simplified flow split: specify branches percentage, rest to main outlet.

        MATLAB METHOD (matching published code):
        - Branches (first N-1 outlets) get specified percentage, distributed by AREA ratio
        - Last outlet (descending aorta) gets remainder

        Logic:
        - flow_split_value: Percentage for BRANCHES (e.g., 70 means 70% to branches)
        - First N-1 outlets (branches) share this percentage by AREA ratio (A_i / Σ A_branches)
        - Last outlet gets remainder

        Args:
            flow_split_value: Percentage for BRANCHES (e.g., 70 means 70% to branches total)
            outlet_patches: List of outlet patch names (LAST is main outlet)
            method: 'area' (MATLAB method) or 'murray' (r³)
            geometry_data: Dictionary of outlet radii (meters) - will convert to areas

        Returns:
            Dictionary of flow ratios summing to 1.0

        Example (MATLAB matching):
            flow_split = 70, 4 outlets [outlet1, outlet2, outlet3, outlet4]:
            - Branches (outlet1, outlet2, outlet3): share 70% by area ratio
            - Main (outlet4): gets 30%
        """
        num_outlets = len(outlet_patches)
        if num_outlets == 0:
            raise ValueError("No outlet patches provided")

        # Convert percentage to fraction for BRANCHES
        branches_fraction = float(flow_split_value) / 100.0
        main_outlet_fraction = 1.0 - branches_fraction

        if num_outlets == 1:
            return {outlet_patches[0]: 1.0}

        # Last outlet is main (descending aorta/abdominal)
        # First N-1 are branches
        num_branches = num_outlets - 1
        branch_outlets = outlet_patches[:num_branches]
        main_outlet = outlet_patches[-1]

        flow_split_ratios = {}

        self.log.info(f"  Branches (outlets 1-{num_branches}): {branches_fraction*100:.1f}% total")
        self.log.info(f"  Main outlet '{main_outlet}': {main_outlet_fraction*100:.1f}%")

        if not geometry_data:
            raise ValueError("Geometry data (outlet radii) required for flow split")

        # MATLAB method: Distribute by AREA ratio
        branch_data = {name: geometry_data[name] for name in branch_outlets}

        if method == 'area':
            # Convert radii to areas: A = π r²
            branch_areas = {name: np.pi * r**2 for name, r in branch_data.items()}
            total_branch_area = sum(branch_areas.values())

            self.log.info(f"  Branch distribution by AREA ratio (MATLAB method):")
            for name in branch_outlets:
                # Fraction within branches group
                branch_fraction = branch_areas[name] / total_branch_area
                # Scale to overall branches allocation
                flow_split_ratios[name] = branch_fraction * branches_fraction
                A_mm2 = branch_areas[name] * 1e6
                self.log.info(f"    {name}: A={A_mm2:.2f}mm² → {flow_split_ratios[name]*100:.1f}%")
        else:
            # Murray's law (r³) distribution among branches
            r_cubed = {name: r**3 for name, r in branch_data.items()}
            total_r_cubed = sum(r_cubed.values())

            self.log.info(f"  Branch distribution by Murray's law (r³):")
            for name in branch_outlets:
                # Fraction within branches group
                branch_fraction = r_cubed[name] / total_r_cubed
                # Scale to overall branches allocation
                flow_split_ratios[name] = branch_fraction * branches_fraction
                r_mm = geometry_data[name] * 1000
                self.log.info(f"    {name}: r={r_mm:.2f}mm → {flow_split_ratios[name]*100:.1f}%")

        # Main outlet (last) gets specified percentage
        flow_split_ratios[main_outlet] = main_outlet_fraction

        return flow_split_ratios

    def _normalize_data_type(self, data_type):
        """
        Normalize data type string to lowercase standard format.

        Accepts: flowRate, flowrate, FLOWRATE, velocity, Velocity, VELOCITY, etc.
        Returns: 'flowrate', 'velocity', or 'pressure'
        """
        if not data_type:
            return None

        normalized = data_type.lower().strip()

        # Handle common variations
        if normalized in ['flowrate', 'flow_rate', 'flow', 'q']:
            return 'flowrate'
        elif normalized in ['velocity', 'vel', 'u', 'v']:
            return 'velocity'
        elif normalized in ['pressure', 'p', 'press']:
            return 'pressure'
        else:
            # Return as-is if not recognized (will trigger error downstream)
            return normalized

    def _read_inlet_flow(self, file_path, data_type, inlet_area):
        """Reads the inlet flow CSV and converts to flow rate if necessary."""
        if not os.path.isfile(file_path):
            self.log.error(f"Could not find inlet data file: {file_path}")
            raise FileNotFoundError(f"Could not find inlet data file: {file_path}")

        # Normalize data type for case-insensitive comparison
        data_type_norm = self._normalize_data_type(data_type)

        with open(file_path, 'r') as f:
            first_line = f.readline()
            if "time" in first_line.lower() or "flow" in first_line.lower() or "velocity" in first_line.lower():
                Q_data = np.loadtxt(file_path, delimiter=",", skiprows=1)
            else:
                Q_data = np.loadtxt(file_path, delimiter=",")

        if data_type_norm == "flowrate":
            times = Q_data[:, 0]
            flow_inlet = Q_data[:, 1]
        elif data_type_norm == "velocity":
            times = Q_data[:, 0]
            flow_inlet = Q_data[:, 1] * inlet_area
        else:
            self.log.error(f"Unknown data type: {data_type} (normalized: {data_type_norm}). Use 'flowrate' or 'velocity'.")
            raise ValueError(f"Unknown data type: {data_type}. Use 'flowrate' or 'velocity'.")

        return times, flow_inlet

    def plot_flow_distribution(self, times, flow_inlet, flow_splits, output_path):
        """
        Plot inlet and outlet flow rates over one cardiac cycle.

        Args:
            times: Time array (s)
            flow_inlet: Inlet flow rate array (m³/s)
            flow_splits: Dict of outlet flow fractions
            output_path: Path to save PNG file
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            self.log.warning("matplotlib not available, skipping flow plot")
            return

        # Calculate outlet flows
        outlet_flows = {}
        for outlet, fraction in flow_splits.items():
            outlet_flows[outlet] = flow_inlet * fraction

        # Create plot
        fig, ax = plt.subplots(figsize=(10, 6))

        # Plot inlet
        ax.plot(times * 1000, flow_inlet * 1e6, 'k-', linewidth=2, label='Inlet')

        # Plot outlets
        colors = plt.cm.tab10(np.linspace(0, 1, len(outlet_flows)))
        for (outlet, flow), color in zip(outlet_flows.items(), colors):
            fraction = flow_splits[outlet]
            ax.plot(times * 1000, flow * 1e6, '--', linewidth=1.5,
                   label=f'{outlet} ({fraction*100:.1f}%)', color=color)

        ax.set_xlabel('Time (ms)', fontsize=12)
        ax.set_ylabel('Flow Rate (mL/s)', fontsize=12)
        ax.set_title('Inlet and Outlet Flow Rates (One Cardiac Cycle)', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best', fontsize=10)

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

        self.log.info(f"Flow distribution plot saved to: {output_path}")
