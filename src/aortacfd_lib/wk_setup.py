import os
import sys
import math
import numpy as np

from .utils.patch_processing import PatchProcessing
from .utils.logger import Logger
from .constants import (
    MMHG_TO_PA, ML_TO_M3,
    TAU_RC_DEFAULT, TAU_RC_MIN, TAU_RC_MAX,
    MURRAY_LAW_EXPONENT, VENOUS_PRESSURE_DEFAULT,
)

class WkSetup:
    """
    Computes Windkessel coefficients for all outlets using clinical MAP-based methodology.

    Supports both 2-element and 3-element Windkessel models:

    2-ELEMENT WINDKESSEL (R-C model, Z=0):
        - Appropriate for CONSTANT inlet (steady flow, no wave propagation)
        - R = R_total = (MAP - P_venous) / mean_flow
        - C = tau / R (compliance from decay time)
        - Z = 0 (no characteristic impedance)

    3-ELEMENT WINDKESSEL (R-C-Z model):
        - Appropriate for TIMEVARYING inlet (pulsatile flow with wave reflection)
        - R1 (proximal) = ρ·c/A (characteristic impedance from PWV)
        - R2 (distal) = R_total - R1
        - C = tau / R2 (compliance from diastolic decay)

    Method: Clinical Windkessel (Westerhof et al. 2009)
    1. MAP = DP + (SP-DP)/3
    2. Flow distribution: Murray's law (r³) with optional main outlet percentage
    3. R_total = (MAP - P_venous) / mean_flow
    4. For 3-element: R1 = ρ·c/A, R2 = R_total - R1, C = tau/R2
    5. For 2-element: R = R_total, C = tau/R, Z = 0

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
        - Dict: User-specified ratios for each outlet (can mix fixed % and "murray")

    Direct RCZ Mode:
        - If outlet_parameters contains direct R, C, Z values for all outlets,
          skip coefficient calculation entirely and use those values directly.
        - This allows users to specify Windkessel parameters from literature
          or external calibration without needing clinical pressure data.

    References:
        - Westerhof et al., Med Biol Eng Comput 2009 (DC allocation)
        - Nichols & O'Rourke, McDonald's Blood Flow in Arteries (MAP formula)
        - Stergiopulos et al., J Biomech 1992 (tau=R2·C)
        - Reymond et al., J Biomech 2009 (lumped parameter models)
    """

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
        self.log.info("Windkessel Boundary Condition Setup")
        self.log.info("=" * 80)

        outlet_patches = self.geom_settings['outlet_keywords_ordered']

        # Check for direct RCZ mode first
        if self._check_direct_rcz_mode(outlet_patches):
            self.log.info("Using DIRECT RCZ mode - skipping coefficient calculation")
            self._inject_q_init_for_direct_rcz(outlet_patches)
            return

        # Determine whether to use 2-element or 3-element Windkessel
        inlet_type = self.inlet_settings.get('type', 'TIMEVARYING').upper()
        outlet_type = self.outlet_settings.get('type', '3EWINDKESSEL').upper()

        # Auto-select 2-element for CONSTANT inlet if user hasn't explicitly chosen
        auto_select = self.wk_model_settings.get('auto_select_model', True)
        if outlet_type == '2EWINDKESSEL':
            use_2element = True
        elif inlet_type in ['CONSTANT', 'PARABOLIC'] and outlet_type == '3EWINDKESSEL' and auto_select:
            use_2element = True
            self.log.warning(
                "CONSTANT/PARABOLIC inlet detected: Auto-selecting 2-element Windkessel (Z=0). "
                "Characteristic impedance (Z) models wave propagation, which is less relevant "
                "for steady-state flow. Note: This is an approximation — reflected waves and "
                "impedance mismatch can still affect outlet pressure even with constant inlet. "
                "To force 3-element model, set 'auto_select_model': false in windkessel_settings."
            )
        else:
            use_2element = False

        if use_2element:
            self.log.info("Calculating 2-Element Windkessel Coefficients (R-C Model, Z=0)")
        else:
            self.log.info("Calculating 3-Element Windkessel Coefficients (Clinical Method)")
        self.log.info("-" * 80)

        area_inlet, outlet_areas, outlet_radii = self._compute_patch_geometry(outlet_patches)
        mean_Q_inlet, times, flow_inlet = self._compute_mean_inlet_flow(area_inlet)

        # Step 1: Calculate MAP from cuff pressures
        SP = self.wk_model_settings.get("systolic_pressure", 120)  # mmHg
        DP = self.wk_model_settings.get("diastolic_pressure", 80)  # mmHg
        # Venous pressure: physiological default is 5 mmHg (central venous pressure).
        # Historical CFD convention used 0 mmHg for numerical stability.
        # Trade-off: P_venous=0 gives slightly higher R_total (conservative),
        # while P_venous=5 is physiologically correct but reduces driving pressure gradient.
        P_venous = self.wk_model_settings.get("venous_pressure", VENOUS_PRESSURE_DEFAULT)
        if P_venous < 0 or P_venous > 10:
            self.log.warning(
                f"Venous pressure P_v={P_venous:.1f} mmHg outside typical range [0, 10] mmHg. "
                f"Normal central venous pressure: 2-8 mmHg. Default: {VENOUS_PRESSURE_DEFAULT} mmHg."
            )

        # Physiological MAP formula: MAP = DP + (SP-DP)/3 = (2*DP + SP)/3
        # Accounts for diastole being ~2/3 of cardiac cycle
        # Reference: Klabunde (2011) Cardiovascular Physiology Concepts
        pulse_pressure = SP - DP
        MAP = DP + (1.0 / 3.0) * pulse_pressure  # Mean arterial pressure (mmHg)
        MAP_Pa = MAP * MMHG_TO_PA  # Convert to Pa
        P_venous_Pa = P_venous * MMHG_TO_PA

        self.log.info(f"Step 1: Pressure targets")
        self.log.info(f"  Systolic pressure (SP): {SP} mmHg")
        self.log.info(f"  Diastolic pressure (DP): {DP} mmHg")
        self.log.info(f"  Pulse pressure (PP): {pulse_pressure} mmHg")
        self.log.info(f"  Mean arterial pressure (MAP): {MAP:.1f} mmHg ({MAP_Pa:.0f} Pa) [MAP = DP + PP/3]")
        self.log.info(f"  Venous pressure (P_v): {P_venous} mmHg")
        self.log.info(f"  Driving pressure (MAP - P_v): {MAP - P_venous:.1f} mmHg")

        # Step 2: Flow distribution
        flow_split_ratios = self.wk_model_settings.get('flow_split')

        if flow_split_ratios is None:
            # Auto-calculate using Murray's law (default)
            self.log.info(f"\nStep 2: Flow distribution (Murray's law: f_i = r³/Σr³)")
            flow_split_ratios = self._calculate_murray_flow_split(outlet_radii)
            self.wk_model_settings['flow_split'] = flow_split_ratios
        elif isinstance(flow_split_ratios, dict):
            # User provided dictionary - could be:
            # 1. Complete ratios: {"outlet1": 0.2, "outlet2": 0.3, "outlet3": 0.5}
            # 2. Percentages with murray: {"outlet1": 20, "outlet4": 50, "_rest": "murray"}
            # 3. Mixed: {"outlet1": 20, "outlet4": 50} - remaining auto-distributed
            self.log.info(f"\nStep 2: Flow distribution (Custom per-outlet specification)")
            flow_split_ratios = self._parse_custom_flow_split(
                flow_split_ratios,
                outlet_patches,
                outlet_radii
            )
            self.wk_model_settings['flow_split'] = flow_split_ratios
        else:
            # Flow split is a percentage for branches (MATLAB method)
            self.log.info(f"\nStep 2: Flow distribution (Branch percentage + area-based distribution - MATLAB method)")
            flow_split_ratios = self._parse_flow_split_percentage(
                flow_split_ratios,
                outlet_patches,
                'area',  # MATLAB uses area-based, not Murray's law
                outlet_radii
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
            R_total_mmHg = R_total[i] / (MMHG_TO_PA * 1e6)
            self.log.info(f"  {outlet}: R_total = {R_total[i]:.2e} Pa·s/m³ ({R_total_mmHg:.1f} mmHg·s/mL)")

        # Initialize R1 (proximal/characteristic impedance) and R2 (distal resistance)
        R1 = np.zeros(num_outlets)
        R2 = np.zeros(num_outlets)

        if use_2element:
            # 2-ELEMENT WINDKESSEL: R = R_total, Z = 0
            self.log.info(f"\nStep 4: 2-Element Model - R = R_total, Z = 0 (no characteristic impedance)")
            for i, outlet in enumerate(outlet_patches):
                R1[i] = 0.0  # No proximal impedance for 2-element
                R2[i] = R_total[i]  # Full resistance
                R_mmHg = R2[i] / (MMHG_TO_PA * 1e6)
                self.log.info(f"  {outlet}: R = {R2[i]:.2e} Pa·s/m³ ({R_mmHg:.1f} mmHg·s/mL), Z = 0")

            self.log.info(f"\nStep 5: Skipped (2-element model has no R1/R2 split)")
        else:
            # 3-ELEMENT WINDKESSEL: Calculate R1 from characteristic impedance
            # Step 4: Proximal resistance R1 (characteristic impedance)
            self.log.info(f"\nStep 4: Proximal resistance R1 = ρ·c/A (characteristic impedance)")

            # Get density - support both 'blood_density' and 'rho' keys
            rho = self.config['physics'].get('blood_density', self.config['physics'].get('rho', 1060))  # kg/m³
            pwv_method = self.wk_model_settings.get('pwv_method', 'matlab')  # Default to MATLAB formula
            pwv_value = self.wk_model_settings.get('pwv', None)  # m/s, if specified

            # PWV Methods:
            #   'matlab': c = a / (2*sqrt(A/pi))^b  (default a=13.3, b=0.3)
            #       Ref: Olufsen MS. Structured tree outflow condition for blood flow
            #       in larger systemic arteries. Am J Physiol. 1999;276(1):H257-H268.
            #   'empirical': Diameter-based tiers (5/6/7 m/s for large/medium/small)
            #       Limitation: Coarse approximation; ignores age, stiffness, pathology.
            #   'physiological': Moens-Korteweg equation c = sqrt(E*h / (2*rho*R))
            #       Ref: Moens AI (1878), Korteweg DJ (1878).
            #       Requires wall_elastic_modulus (Pa) and wall_thickness (m).
            pwv_a = self.wk_model_settings.get('pwv_a', 13.3)
            pwv_b = self.wk_model_settings.get('pwv_b', 0.3)

            for i, outlet in enumerate(outlet_patches):
                A_i = outlet_areas[outlet]
                A_mm2 = A_i * 1e6  # Convert m² to mm²

                # Determine pulse wave velocity (PWV)
                if pwv_value is not None:
                    # User-specified PWV
                    c_i = pwv_value
                    method = "user-specified"
                elif pwv_method == 'matlab':
                    # Olufsen (1999) empirical formula: c = a / (2*sqrt(A_mm²/π))^b
                    # Limitation: Empirical fit to structured tree data; may not generalize
                    # to pathological vessels (coarctation, aneurysm, calcification).
                    c_i = pwv_a / (2 * np.sqrt(A_mm2 / np.pi)) ** pwv_b
                    method = f"Olufsen formula: {pwv_a}/(2√(A/π))^{pwv_b}"
                elif pwv_method == 'empirical':
                    # Diameter-based tiers (typical healthy adult aortic values)
                    # Limitation: Coarse 3-tier approximation; ignores vessel wall
                    # properties, patient age, and pathology (stiffening, stenosis).
                    diameter_mm = 2 * outlet_radii[outlet] * 1000
                    if diameter_mm > 15:
                        c_i = 5.0  # Large vessels (arch/thoracic)
                    elif diameter_mm > 8:
                        c_i = 6.0  # Medium vessels (abdominal)
                    else:
                        c_i = 7.0  # Smaller vessels (branches)
                    method = "empirical"
                elif pwv_method == 'physiological':
                    # Moens-Korteweg equation: c = sqrt(E * h / (2 * rho * R))
                    # More physically grounded but requires vessel wall properties.
                    # Limitation: Assumes thin-walled elastic tube; does not account
                    # for viscoelasticity or non-uniform wall thickness.
                    E_wall = self.wk_model_settings.get('wall_elastic_modulus', 500e3)  # Pa (default: 500 kPa, typical aorta)
                    h_wall = self.wk_model_settings.get('wall_thickness', 0.002)  # m (default: 2mm)
                    R_i_radius = outlet_radii[outlet]
                    c_i = np.sqrt(E_wall * h_wall / (2.0 * rho * R_i_radius))
                    method = f"Moens-Korteweg: E={E_wall/1e3:.0f}kPa, h={h_wall*1e3:.1f}mm"
                else:
                    # Fallback: use fraction of R_total
                    R1[i] = 0.15 * R_total[i]
                    self.log.info(f"  {outlet}: R1 = {R1[i]:.2e} Pa·s/m³ (15% of R_total)")
                    continue

                # Calculate characteristic impedance
                R1[i] = rho * c_i / A_i

                R1_mmHg = R1[i] / (MMHG_TO_PA * 1e6)
                self.log.info(f"  {outlet}: A={A_mm2:.2f}mm², PWV = {c_i:.2f} m/s ({method}) → R1 = {R1[i]:.2e} Pa·s/m³ ({R1_mmHg:.1f} mmHg·s/mL)")

            # Step 5: Distal resistance R2
            self.log.info(f"\nStep 5: Distal resistance R2 = R_total - R1")

            for i, outlet in enumerate(outlet_patches):
                R2[i] = R_total[i] - R1[i]
                if R2[i] < 0:
                    self.log.warning(f"  {outlet}: R2 < 0, setting R1 = 0.1*R_total")
                    R1[i] = 0.1 * R_total[i]
                    R2[i] = 0.9 * R_total[i]

                R2_mmHg = R2[i] / (MMHG_TO_PA * 1e6)
                self.log.info(f"  {outlet}: R2 = {R2[i]:.2e} Pa·s/m³ ({R2_mmHg:.1f} mmHg·s/mL)")

        # Step 6: Compliance C
        if use_2element:
            self.log.info(f"\nStep 6: Compliance C = tau / R (2-element formula)")
        else:
            self.log.info(f"\nStep 6: Compliance C = tau / R2 (3-element formula)")

        # RC time constant: controls diastolic pressure decay rate.
        # Physiological default from constants.py. Historical MATLAB default was 1.92s.
        # For pediatric patients, tau is typically shorter (0.5-1.0s) due to higher heart rate.
        tau_systemic = self.wk_model_settings.get('tau', TAU_RC_DEFAULT)
        if tau_systemic < TAU_RC_MIN or tau_systemic > TAU_RC_MAX:
            self.log.warning(
                f"RC time constant tau={tau_systemic:.2f}s outside physiological range "
                f"[{TAU_RC_MIN}, {TAU_RC_MAX}]s. Typical adult: 1.0-2.0s, pediatric: 0.5-1.0s."
            )
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
                C_mmHg = C[i] / (ML_TO_M3 / MMHG_TO_PA)
                self.log.info(f"  {outlet}: C = {C[i]:.2e} m³/Pa ({C_mmHg:.2e} mL/mmHg), RC = {RC_i:.2f} s")
        else:
            # Uniform tau for all outlets, C = tau / R2 (correct 3-element WK formula)
            self.log.info(f"  Systemic tau: {tau_systemic:.2f} s")
            for i, outlet in enumerate(outlet_patches):
                C[i] = tau_systemic / R2[i]  # Correct: C = tau / R2 (distal resistance only)
                RC_i = R2[i] * C[i]
                C_mmHg = C[i] / (ML_TO_M3 / MMHG_TO_PA)
                self.log.info(f"  {outlet}: C = {C[i]:.2e} m³/Pa ({C_mmHg:.2e} mL/mmHg), RC = {RC_i:.2f} s")

        # Store calculated WK coefficients
        self.log.info(f"\n" + "=" * 80)
        model_name = "2-Element (R-C, Z=0)" if use_2element else "3-Element (R-C-Z)"
        self.log.info(f"SUMMARY: {model_name} Windkessel Parameters (OpenFOAM units: Pa·s/m³, m³/Pa)")
        self.log.info("=" * 80)

        outlet_parameters = {}
        for i, name in enumerate(outlet_patches):
            # Calculate initial flow for this outlet (prevents startup divergence)
            # q_init = expected steady-state flow based on Murray's law split
            q_init = mean_Q_outlets[i]  # m³/s

            outlet_parameters[name] = {
                "R": float(R2[i]),      # For 2E: R_total; For 3E: R2 (distal resistance)
                "C": float(C[i]),       # Compliance
                "Z": float(R1[i]),      # For 2E: 0; For 3E: R1 (characteristic impedance)
                "q_init": float(q_init) # Initial flow for WK state variables (prevents startup spike)
            }
            if use_2element:
                self.log.info(f"{name:15s}: R={R2[i]:12.2e}  C={C[i]:12.2e}  Z=0  q_init={q_init*1e6:.2f} mL/s")
            else:
                self.log.info(f"{name:15s}: R(R2)={R2[i]:12.2e}  C={C[i]:12.2e}  Z(R1)={R1[i]:12.2e}  q_init={q_init*1e6:.2f} mL/s")

        self.wk_model_settings['outlet_parameters'] = outlet_parameters
        self.log.info("=" * 80)
        self.log.info("Windkessel calculation complete - coefficients stored in config")
        self.log.info("=" * 80)

        # Generate flow distribution plot
        reports_dir = os.path.join(os.path.dirname(self.case_dir), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        plot_path = os.path.join(reports_dir, "flow_distribution.png")

        if inlet_type in ['TIMEVARYING', 'WOMERSLEY']:
            # Time-varying plot with flow waveforms, pie/bar charts, and WK table
            self.plot_flow_distribution(times, flow_inlet, flow_split_ratios, plot_path, outlet_parameters)
        else:
            # Steady-state plot with pie chart, bar chart, and WK parameters table
            self.plot_flow_distribution_steady(mean_Q_inlet, flow_split_ratios, outlet_parameters, plot_path)

    def _compute_patch_geometry(self, outlet_patches: list) -> tuple[float, dict, dict]:
        """Compute inlet area, outlet areas, and outlet radii from the generated triSurface."""
        tri_surface_dir = os.path.join(self.case_dir, "constant", "triSurface")

        # STL files in constant/triSurface/ are pre-scaled to meters during case setup.
        inlet_patch_name = self.geom_settings['inlet_keywords_ordered']
        area_inlet = PatchProcessing(tri_surface_dir, inlet_patch_name).calculate_surface_area()
        outlet_areas = {
            name: PatchProcessing(tri_surface_dir, name).calculate_surface_area()
            for name in outlet_patches
        }
        outlet_radii = {name: math.sqrt(area / math.pi) for name, area in outlet_areas.items()}
        return area_inlet, outlet_areas, outlet_radii

    def _compute_mean_inlet_flow(self, area_inlet: float):
        """Compute mean inlet flow in m^3/s from the configured inlet boundary condition."""
        inlet_type = self.inlet_settings.get('type', 'TIMEVARYING').upper()

        if inlet_type in ['TIMEVARYING', 'WOMERSLEY']:
            inlet_csv_path = os.path.join("cases_input", self.geom_settings['case_name'], self.inlet_settings['csv_file'])
            times, flow_inlet = self._read_inlet_flow(inlet_csv_path, self.inlet_settings['data_type'], area_inlet)
            return float(np.mean(flow_inlet)), times, flow_inlet

        if inlet_type == 'MRI':
            mean_q_inlet = self._compute_mri_mean_inlet_flow(area_inlet)
            return mean_q_inlet, None, None

        if inlet_type in ['CONSTANT', 'PARABOLIC']:
            if 'flowrate' in self.inlet_settings and 'cardiac_output' not in self.inlet_settings:
                self.inlet_settings['cardiac_output'] = self.inlet_settings['flowrate']

            if 'cardiac_output' in self.inlet_settings:
                cardiac_output_lmin = self.inlet_settings['cardiac_output']
                mean_q_inlet = cardiac_output_lmin / 60.0 / 1000.0
                mean_velocity = mean_q_inlet / area_inlet
                self.log.info(
                    f"Constant inlet: cardiac_output = {cardiac_output_lmin:.2f} L/min → "
                    f"velocity = {mean_velocity:.3f} m/s, mean flow Q = {mean_q_inlet*1e6:.2f} mL/s"
                )
                if 'velocity' in self.inlet_settings:
                    self.log.warning("Both 'velocity' and 'cardiac_output' specified. Using cardiac_output.")
                return float(mean_q_inlet), None, None

            if 'velocity' in self.inlet_settings:
                velocity = self.inlet_settings['velocity']
                mean_velocity = velocity / 2.0 if inlet_type == 'PARABOLIC' else velocity
                mean_q_inlet = mean_velocity * area_inlet
                self.log.info(
                    f"Constant inlet: velocity = {velocity:.3f} m/s, mean flow Q = {mean_q_inlet*1e6:.2f} mL/s"
                )
                return float(mean_q_inlet), None, None

            raise ValueError(
                "CONSTANT/PARABOLIC inlet requires either 'velocity' (m/s), "
                "'flowrate' (L/min), or 'cardiac_output' (L/min) parameter"
            )

        raise ValueError(f"Unknown inlet type: {inlet_type}")

    def _compute_mri_mean_inlet_flow(self, area_inlet: float) -> float:
        """Compute mean inlet flow from prepared MRI boundaryData velocity fields."""
        mri_velocity_dir = self._resolve_mri_velocity_directory()
        flow_direction = self._compute_inlet_flow_direction()
        time_dirs = [
            entry for entry in os.listdir(mri_velocity_dir)
            if os.path.isdir(os.path.join(mri_velocity_dir, entry)) and entry.replace('.', '', 1).isdigit()
        ]

        if not time_dirs:
            raise ValueError(f"No MRI time directories found in {mri_velocity_dir}")

        flow_samples = []
        for time_dir in sorted(time_dirs, key=float):
            velocity_file = os.path.join(mri_velocity_dir, time_dir, 'U')
            if not os.path.exists(velocity_file):
                continue

            velocities = self._read_openfoam_vectors(velocity_file)
            if velocities.size == 0:
                continue

            normal_velocity = velocities @ flow_direction
            flow_samples.append(float(np.mean(normal_velocity) * area_inlet))

        if not flow_samples:
            raise ValueError(f"No MRI velocity samples found in {mri_velocity_dir}")

        mean_q_inlet = float(np.mean(flow_samples))
        if mean_q_inlet < 0:
            self.log.warning(
                f"MRI inlet mean flow projected negative ({mean_q_inlet*1e6:.2f} mL/s); using magnitude for q_init"
            )
            mean_q_inlet = abs(mean_q_inlet)

        self.log.info(
            f"MRI inlet: mean flow Q = {mean_q_inlet*1e6:.2f} mL/s from {len(flow_samples)} time steps"
        )
        return mean_q_inlet

    def _resolve_mri_velocity_directory(self) -> str:
        """Resolve the MRI velocity directory, preferring prepared boundaryData in the case directory."""
        inlet_patch_name = self.geom_settings['inlet_keywords_ordered']
        boundary_data_dir = os.path.join(self.case_dir, 'constant', 'boundaryData', inlet_patch_name)
        if os.path.isdir(boundary_data_dir):
            return boundary_data_dir

        mri_source_dir = self.inlet_settings.get('file', self.inlet_settings.get('source_dir', ''))
        if not mri_source_dir:
            raise ValueError("MRI inlet type requires 'file' or 'source_dir' to locate velocity data")

        if os.path.isabs(mri_source_dir) and os.path.isdir(mri_source_dir):
            return mri_source_dir

        patient_case_dir = self.config.get('patient_case_directory', '')
        if patient_case_dir:
            candidate = os.path.join(patient_case_dir, mri_source_dir)
            if os.path.isdir(candidate):
                return candidate

        candidate = os.path.join('cases_input', self.geom_settings['case_name'], mri_source_dir)
        if os.path.isdir(candidate):
            return candidate

        if os.path.isdir(mri_source_dir):
            return mri_source_dir

        raise FileNotFoundError(f"MRI inlet source directory not found: {mri_source_dir}")

    def _compute_inlet_flow_direction(self) -> np.ndarray:
        """Compute the positive inlet flow direction based on orientation settings and outlet geometry."""
        tri_surface_dir = os.path.join(self.case_dir, 'constant', 'triSurface')
        inlet_name = self.geom_settings['inlet_keywords_ordered']
        inlet_center, _, inlet_normal = PatchProcessing(tri_surface_dir, inlet_name).calculate_inlet_center_radius()
        orientation = self.inlet_settings.get('orientation', 'auto').lower()

        if orientation == 'out':
            return inlet_normal
        if orientation == 'in':
            return -inlet_normal

        outlet_centers = []
        for outlet_name in self.geom_settings['outlet_keywords_ordered']:
            outlet_center, _, _ = PatchProcessing(tri_surface_dir, outlet_name).calculate_inlet_center_radius()
            outlet_centers.append(outlet_center)

        if not outlet_centers:
            self.log.warning("MRI inlet flow direction: no outlet centers found, using inlet normal as-is")
            return inlet_normal

        flow_direction = np.mean(outlet_centers, axis=0) - inlet_center
        flow_direction = flow_direction / np.linalg.norm(flow_direction)
        if np.dot(inlet_normal, flow_direction) < 0:
            return -inlet_normal
        return inlet_normal

    @staticmethod
    def _read_openfoam_vectors(filepath: str) -> np.ndarray:
        """Read a bare OpenFOAM vector field file and return an Nx3 array."""
        with open(filepath) as handle:
            lines = handle.readlines()

        count_index = None
        for index, line in enumerate(lines):
            if line.strip().isdigit():
                count_index = index
                break

        if count_index is None:
            raise ValueError(f"Could not find vector count in OpenFOAM file: {filepath}")

        n_vectors = int(lines[count_index].strip())
        vectors = []
        for line in lines[count_index + 2:count_index + 2 + n_vectors]:
            values = line.strip().strip('()').split()
            vectors.append([float(value) for value in values])

        return np.array(vectors)

    def _inject_q_init_for_direct_rcz(self, outlet_patches: list) -> None:
        """Populate missing q_init values for direct RCZ cases to stabilize WK startup."""
        outlet_params = self.wk_model_settings.get('outlet_parameters', {})
        missing_q_init = [
            outlet for outlet in outlet_patches
            if outlet in outlet_params and 'q_init' not in outlet_params[outlet]
        ]

        if not missing_q_init:
            self.log.info("Direct RCZ mode: all outlets already define q_init; preserving configured values")
            return

        try:
            area_inlet, _, outlet_radii = self._compute_patch_geometry(outlet_patches)
            mean_q_inlet, _, _ = self._compute_mean_inlet_flow(area_inlet)
            flow_split_ratios = self._calculate_murray_flow_split(outlet_radii)
            split_method = "Murray's law"
        except Exception as exc:
            self.log.warning(
                f"Direct RCZ mode: failed to compute geometry-based q_init ({exc}); using equal outlet split"
            )
            mean_q_inlet, _, _ = self._compute_mean_inlet_flow(1.0)
            equal_fraction = 1.0 / len(outlet_patches)
            flow_split_ratios = {outlet: equal_fraction for outlet in outlet_patches}
            split_method = "equal split"

        self.log.info(
            f"Direct RCZ mode: injecting q_init from mean inlet flow {mean_q_inlet*1e6:.2f} mL/s "
            f"using {split_method}"
        )
        for outlet in outlet_patches:
            params = outlet_params[outlet]
            if 'q_init' in params:
                self.log.info(f"  {outlet}: preserving configured q_init = {params['q_init']*1e6:.2f} mL/s")
                continue

            q_init = float(mean_q_inlet * flow_split_ratios[outlet])
            params['q_init'] = q_init
            self.log.info(f"  {outlet}: q_init = {q_init*1e6:.2f} mL/s")

    def _check_direct_rcz_mode(self, outlet_patches: list) -> bool:
        """
        Check if user provided direct R, C, Z values for all outlets.

        Direct RCZ mode is enabled when:
        1. outlet_parameters contains entries for ALL outlets
        2. Each entry has 'R', 'C', and 'Z' keys with numeric values

        Example config for direct mode:
            windkessel_settings:
                outlet_parameters:
                    outlet1:
                        R: 1.5e9
                        C: 1.0e-9
                        Z: 1.5e8
                    outlet2:
                        R: 2.0e9
                        C: 0.8e-9
                        Z: 2.0e8

        Returns:
            True if direct RCZ mode should be used, False otherwise
        """
        outlet_params = self.wk_model_settings.get('outlet_parameters', {})

        if not outlet_params:
            return False

        # Check if ALL outlets have R, C, Z specified
        for outlet in outlet_patches:
            if outlet not in outlet_params:
                self.log.debug(f"Direct RCZ mode: missing outlet '{outlet}'")
                return False

            params = outlet_params[outlet]
            if not isinstance(params, dict):
                return False

            # Check for required keys
            for key in ['R', 'C', 'Z']:
                if key not in params:
                    self.log.debug(f"Direct RCZ mode: '{outlet}' missing '{key}'")
                    return False

                # Verify numeric value
                try:
                    float(params[key])
                except (TypeError, ValueError):
                    self.log.warning(f"Direct RCZ mode: '{outlet}.{key}' is not numeric")
                    return False

        # All outlets have valid R, C, Z - use direct mode
        self.log.info("-" * 80)
        self.log.info("Direct RCZ mode: Using user-specified Windkessel parameters")
        self.log.info("-" * 80)

        for outlet in outlet_patches:
            params = outlet_params[outlet]
            self.log.info(f"  {outlet}: R={params['R']:.2e}  C={params['C']:.2e}  Z={params['Z']:.2e}")

        self.log.info("=" * 80)
        return True

    def _calculate_murray_flow_split(self, outlet_radii: dict) -> dict:
        """
        Calculate flow split using Murray's law: f_i = r^n / Σr^n

        The exponent n=3.0 corresponds to classical Murray's law for laminar flow.
        For pulsatile arterial flow, n=2.6 is more appropriate (MURRAY_LAW_EXPONENT).

        Args:
            outlet_radii: Dictionary of outlet names to radii (m)

        Returns:
            Dictionary of flow split ratios (sum to 1.0)
        """
        r_powered = {name: r**MURRAY_LAW_EXPONENT for name, r in outlet_radii.items()}
        total_r_powered = sum(r_powered.values())

        flow_split = {name: rp / total_r_powered for name, rp in r_powered.items()}

        self.log.info(f"  Murray's law (r^{MURRAY_LAW_EXPONENT}) distribution:")
        for name, ratio in flow_split.items():
            r_mm = outlet_radii[name] * 1000
            self.log.info(f"    {name}: r={r_mm:.2f} mm → {ratio*100:.1f}%")

        return flow_split

    def _parse_custom_flow_split(self, flow_split_config: dict, outlet_patches: list, outlet_radii: dict) -> dict:
        """
        Parse custom flow split configuration with flexible options.

        Supports three modes:
        1. Complete ratios (values sum to ~1.0):
           {"outlet1": 0.2, "outlet2": 0.3, "outlet3": 0.5}

        2. Percentages with Murray's law for remaining (values are %):
           {"outlet1": 20, "outlet4": 50, "_rest": "murray"}
           → outlet1 gets 20%, outlet4 gets 50%, outlets 2&3 share 30% by Murray's law

        3. Fixed percentages only (values are %):
           {"outlet1": 20, "outlet2": 20, "outlet3": 20, "outlet4": 40}
           → Each outlet gets specified percentage

        Detection logic:
        - If all values are <= 1.0 and sum ≈ 1.0: treat as ratios (mode 1)
        - If "_rest" key present: treat as percentages with Murray (mode 2)
        - Otherwise: treat as percentages (mode 3)

        Args:
            flow_split_config: User-provided flow split dictionary
            outlet_patches: List of outlet patch names
            outlet_radii: Dictionary of outlet radii (m)

        Returns:
            Dictionary of flow split ratios (sum to 1.0)
        """
        result = {}

        # Remove special keys
        rest_mode = flow_split_config.pop('_rest', None)
        distribution_method = flow_split_config.pop('_method', 'murray')  # 'murray' or 'area'

        # Check if values look like ratios (all <= 1.0 and sum ≈ 1.0)
        numeric_values = [v for v in flow_split_config.values() if isinstance(v, (int, float))]
        all_small = all(v <= 1.0 for v in numeric_values)
        sum_approx_one = abs(sum(numeric_values) - 1.0) < 0.01

        if all_small and sum_approx_one and rest_mode is None:
            # Mode 1: Complete ratios
            self.log.info(f"  Mode: Complete flow ratios (sum ≈ 1.0)")
            for outlet in outlet_patches:
                if outlet in flow_split_config:
                    result[outlet] = float(flow_split_config[outlet])
                else:
                    self.log.warning(f"  {outlet} not in flow_split, using 0")
                    result[outlet] = 0.0

            # Normalize to exactly 1.0
            total = sum(result.values())
            if total > 0:
                result = {k: v / total for k, v in result.items()}

        else:
            # Mode 2 or 3: Percentages
            fixed_outlets = {}
            remaining_outlets = []
            total_fixed_pct = 0.0

            for outlet in outlet_patches:
                if outlet in flow_split_config:
                    pct = float(flow_split_config[outlet])
                    fixed_outlets[outlet] = pct / 100.0  # Convert % to ratio
                    total_fixed_pct += pct
                else:
                    remaining_outlets.append(outlet)

            remaining_pct = 100.0 - total_fixed_pct

            if remaining_pct < 0:
                self.log.warning(f"  Total fixed percentages ({total_fixed_pct}%) > 100%. Normalizing.")
                # Normalize fixed outlets
                for outlet in fixed_outlets:
                    fixed_outlets[outlet] = fixed_outlets[outlet] / (total_fixed_pct / 100.0)
                remaining_pct = 0.0

            # Add fixed outlets to result
            result.update(fixed_outlets)

            if remaining_outlets:
                if rest_mode == 'murray' or (rest_mode is None and distribution_method == 'murray'):
                    # Distribute remaining using Murray's law
                    self.log.info(f"  Fixed outlets: {list(fixed_outlets.keys())} ({total_fixed_pct:.1f}%)")
                    self.log.info(f"  Remaining outlets: {remaining_outlets} ({remaining_pct:.1f}%) - Murray's law")

                    # Calculate Murray distribution for remaining outlets only
                    remaining_radii = {name: outlet_radii[name] for name in remaining_outlets}
                    r_powered = {name: r**MURRAY_LAW_EXPONENT for name, r in remaining_radii.items()}
                    total_r_powered = sum(r_powered.values())

                    for outlet in remaining_outlets:
                        murray_fraction = r_powered[outlet] / total_r_powered
                        result[outlet] = murray_fraction * (remaining_pct / 100.0)
                        r_mm = outlet_radii[outlet] * 1000
                        self.log.info(f"    {outlet}: r={r_mm:.2f}mm → {result[outlet]*100:.1f}%")

                elif rest_mode == 'area':
                    # Distribute remaining by area
                    self.log.info(f"  Fixed outlets: {list(fixed_outlets.keys())} ({total_fixed_pct:.1f}%)")
                    self.log.info(f"  Remaining outlets: {remaining_outlets} ({remaining_pct:.1f}%) - Area ratio")

                    remaining_areas = {name: np.pi * outlet_radii[name]**2 for name in remaining_outlets}
                    total_area = sum(remaining_areas.values())

                    for outlet in remaining_outlets:
                        area_fraction = remaining_areas[outlet] / total_area
                        result[outlet] = area_fraction * (remaining_pct / 100.0)
                        A_mm2 = remaining_areas[outlet] * 1e6
                        self.log.info(f"    {outlet}: A={A_mm2:.2f}mm² → {result[outlet]*100:.1f}%")

                else:
                    # Equal distribution (fallback)
                    self.log.info(f"  Remaining outlets equally distributed")
                    equal_share = (remaining_pct / 100.0) / len(remaining_outlets)
                    for outlet in remaining_outlets:
                        result[outlet] = equal_share

        # Log final distribution
        self.log.info(f"  Final flow distribution:")
        for outlet in outlet_patches:
            self.log.info(f"    {outlet}: {result[outlet]*100:.1f}%")

        return result

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
            # Murray's law (r^n) distribution among branches
            r_powered = {name: r**MURRAY_LAW_EXPONENT for name, r in branch_data.items()}
            total_r_powered = sum(r_powered.values())

            self.log.info(f"  Branch distribution by Murray's law (r^{MURRAY_LAW_EXPONENT}):")
            for name in branch_outlets:
                # Fraction within branches group
                branch_fraction = r_powered[name] / total_r_powered
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

        # Count comment/empty lines and detect header
        # skiprows in loadtxt skips from beginning BEFORE comment processing
        comment_lines = 0
        header_line = 0

        with open(file_path, 'r') as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith('#'):
                    comment_lines += 1
                else:
                    # First non-comment line - check if it's a header
                    if ("time" in stripped.lower() or
                        "flow" in stripped.lower() or
                        "velocity" in stripped.lower()):
                        header_line = 1
                    break

        # Total lines to skip = comment lines + header (if present)
        skiprows = comment_lines + header_line

        Q_data = np.loadtxt(file_path, delimiter=",", skiprows=skiprows)

        if data_type_norm == "flowrate":
            times = Q_data[:, 0]
            flow_inlet = Q_data[:, 1]

            # Auto-detect L/min vs m³/s: clinical flowrate data is typically in L/min
            # (values > 1.0), while m³/s values for aortic flows are O(1e-5) to O(1e-4).
            # This matches the same logic used in inlet_mapping.py.
            max_abs_flow = np.max(np.abs(flow_inlet))
            if max_abs_flow > 1.0:
                self.log.info(
                    f"Flowrate CSV auto-detected as L/min (max={max_abs_flow:.2f}). "
                    f"Converting to m³/s."
                )
                flow_inlet = flow_inlet * 1e-3 / 60.0  # L/min -> m³/s
            else:
                self.log.info(
                    f"Flowrate CSV auto-detected as m³/s (max={max_abs_flow:.2e})"
                )

        elif data_type_norm == "velocity":
            times = Q_data[:, 0]
            flow_inlet = Q_data[:, 1] * inlet_area
        else:
            self.log.error(f"Unknown data type: {data_type} (normalized: {data_type_norm}). Use 'flowrate' or 'velocity'.")
            raise ValueError(f"Unknown data type: {data_type}. Use 'flowrate' or 'velocity'.")

        return times, flow_inlet

    def plot_flow_distribution(self, times, flow_inlet, flow_splits, output_path, outlet_parameters=None):
        """
        Plot inlet and outlet flow rates over one cardiac cycle with comprehensive analysis.

        Creates a combined figure showing:
        1. Time-series flow waveforms (top)
        2. Mean flow pie chart and bar chart (middle)
        3. Windkessel parameters table (bottom)

        Args:
            times: Time array (s)
            flow_inlet: Inlet flow rate array (m³/s)
            flow_splits: Dict of outlet flow fractions
            output_path: Path to save PNG file
            outlet_parameters: Dict of WK parameters {outlet: {R, C, Z}} (optional)
        """
        try:
            import matplotlib.pyplot as plt
            from matplotlib.gridspec import GridSpec
        except ImportError:
            self.log.warning("matplotlib not available, skipping flow plot")
            return

        # Calculate outlet flows
        outlet_flows = {}
        for outlet, fraction in flow_splits.items():
            outlet_flows[outlet] = flow_inlet * fraction

        # Mean values
        mean_inlet_mL_s = np.mean(flow_inlet) * 1e6
        mean_outlet_flows_mL_s = {outlet: np.mean(flow) * 1e6 for outlet, flow in outlet_flows.items()}

        # Calculate cardiac cycle duration
        cardiac_cycle_ms = (times[-1] - times[0]) * 1000

        # Create figure with GridSpec for flexible layout
        fig = plt.figure(figsize=(14, 14))
        gs = GridSpec(3, 2, figure=fig, height_ratios=[1.2, 1, 1.2], hspace=0.35, wspace=0.3)

        # Title
        fig.suptitle('Windkessel Flow Distribution and Parameters\n(Time-Varying Analysis)',
                     fontsize=16, fontweight='bold', y=0.98)

        # === Subplot 1: Time-series flow waveforms (top, spans both columns) ===
        ax1 = fig.add_subplot(gs[0, :])

        # Plot inlet
        ax1.plot(times * 1000, flow_inlet * 1e6, 'k-', linewidth=2.5, label='Inlet')

        # Plot outlets with distinct colors
        colors = plt.cm.Set2(np.linspace(0, 1, len(outlet_flows)))
        for (outlet, flow), color in zip(outlet_flows.items(), colors):
            fraction = flow_splits[outlet]
            ax1.plot(times * 1000, flow * 1e6, '--', linewidth=1.8,
                    label=f'{outlet} ({fraction*100:.1f}%)', color=color)

        ax1.set_xlabel('Time (ms)', fontsize=11)
        ax1.set_ylabel('Flow Rate (mL/s)', fontsize=11)
        ax1.set_title(f'Flow Waveforms Over One Cardiac Cycle ({cardiac_cycle_ms:.0f} ms)',
                     fontsize=12, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='upper right', fontsize=9, ncol=2)
        ax1.set_xlim([times[0]*1000, times[-1]*1000])

        # Add mean flow annotation
        ax1.axhline(y=mean_inlet_mL_s, color='gray', linestyle=':', alpha=0.7)
        ax1.text(times[-1]*1000*0.02, mean_inlet_mL_s*1.05, f'Mean: {mean_inlet_mL_s:.1f} mL/s',
                fontsize=9, color='gray')

        # === Subplot 2: Pie chart (middle left) ===
        ax2 = fig.add_subplot(gs[1, 0])
        labels = list(flow_splits.keys())
        sizes = [flow_splits[o] * 100 for o in labels]
        pie_colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))

        wedges, texts, autotexts = ax2.pie(sizes, labels=labels, autopct='%1.1f%%',
                                           colors=pie_colors, startangle=90,
                                           textprops={'fontsize': 10})
        ax2.set_title('Mean Flow Distribution (%)', fontsize=12, fontweight='bold')

        # === Subplot 3: Bar chart (middle right) ===
        ax3 = fig.add_subplot(gs[1, 1])
        x_pos = np.arange(len(labels))
        flows = [mean_outlet_flows_mL_s[o] for o in labels]

        bars = ax3.bar(x_pos, flows, color=pie_colors, edgecolor='black', linewidth=1.2)

        # Add value labels on bars
        for bar, flow in zip(bars, flows):
            height = bar.get_height()
            ax3.annotate(f'{flow:.2f}\nmL/s',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha='center', va='bottom', fontsize=9)

        ax3.set_xticks(x_pos)
        ax3.set_xticklabels(labels, rotation=45, ha='right')
        ax3.set_ylabel('Mean Flow Rate (mL/s)', fontsize=11)
        ax3.set_title('Mean Outlet Flow Rates', fontsize=12, fontweight='bold')
        ax3.axhline(y=mean_inlet_mL_s, color='red', linestyle='--', linewidth=2,
                   label=f'Inlet: {mean_inlet_mL_s:.2f} mL/s')
        ax3.legend(loc='upper right')
        ax3.grid(True, axis='y', alpha=0.3)

        # === Subplot 4: Windkessel parameters table (bottom, spans both columns) ===
        ax4 = fig.add_subplot(gs[2, :])
        ax4.axis('off')

        # Build table data (uses module-level MMHG_TO_PA and ML_TO_M3 constants)
        table_data = []
        headers = ['Outlet', 'Mean Flow\n(mL/s)', 'Flow\n(%)',
                   'R (Pa·s/m³)', 'C (m³/Pa)', 'Z (Pa·s/m³)',
                   'R\n(mmHg·s/mL)', 'C\n(mL/mmHg)', 'τ=RC\n(s)']

        for outlet in labels:
            params = outlet_parameters.get(outlet, {}) if outlet_parameters else {}
            R = params.get('R', 0)
            C = params.get('C', 0)
            Z = params.get('Z', 0)

            # Clinical units conversion
            R_clinical = R / (MMHG_TO_PA / ML_TO_M3) if R else 0
            C_clinical = C * (MMHG_TO_PA / ML_TO_M3) if C else 0
            tau = R * C if R and C else 0

            table_data.append([
                outlet,
                f'{mean_outlet_flows_mL_s[outlet]:.2f}',
                f'{flow_splits[outlet]*100:.1f}',
                f'{R:.2e}',
                f'{C:.2e}',
                f'{Z:.2e}',
                f'{R_clinical:.3f}',
                f'{C_clinical:.4f}',
                f'{tau:.2f}'
            ])

        # Create table
        table = ax4.table(cellText=table_data,
                         colLabels=headers,
                         cellLoc='center',
                         loc='center',
                         colColours=['lightblue'] * len(headers))

        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1.2, 1.5)

        # Style header row
        for j in range(len(headers)):
            table[(0, j)].set_fontsize(9)
            table[(0, j)].set_text_props(weight='bold')

        ax4.set_title('Windkessel Parameters Summary', fontsize=12, fontweight='bold', pad=20)

        # Add summary text
        total_mean_flow = sum(flows)
        summary_text = (f'Mean Inlet Flow: {mean_inlet_mL_s:.2f} mL/s ({mean_inlet_mL_s*60/1000:.2f} L/min)\n'
                       f'Mean Outlet Flow: {total_mean_flow:.2f} mL/s (Mass conservation: {total_mean_flow/mean_inlet_mL_s*100:.1f}%)\n'
                       f'Cardiac Cycle: {cardiac_cycle_ms:.0f} ms')
        fig.text(0.5, 0.02, summary_text, ha='center', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))

        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

        self.log.info(f"Flow distribution plot (time-varying) saved to: {output_path}")

    def plot_flow_distribution_steady(self, mean_Q_inlet, flow_splits, outlet_parameters, output_path):
        """
        Plot flow distribution for steady-state (constant inlet) simulations.

        Creates a combined figure showing:
        1. Pie chart of flow distribution
        2. Bar chart of flow rates
        3. Table of Windkessel parameters

        Args:
            mean_Q_inlet: Mean inlet flow rate (m³/s)
            flow_splits: Dict of outlet flow fractions
            outlet_parameters: Dict of WK parameters {outlet: {R, C, Z}}
            output_path: Path to save PNG file
        """
        try:
            import matplotlib.pyplot as plt
            from matplotlib.patches import FancyBboxPatch
        except ImportError:
            self.log.warning("matplotlib not available, skipping flow distribution plot")
            return

        # Calculate outlet flows in mL/s
        outlet_flows_mL_s = {outlet: mean_Q_inlet * fraction * 1e6
                            for outlet, fraction in flow_splits.items()}
        inlet_flow_mL_s = mean_Q_inlet * 1e6

        # Create figure with subplots
        fig = plt.figure(figsize=(14, 10))

        # Title
        fig.suptitle('Windkessel Flow Distribution and Parameters\n(Steady-State Analysis)',
                     fontsize=16, fontweight='bold', y=0.98)

        # Subplot 1: Pie chart (top left)
        ax1 = fig.add_subplot(2, 2, 1)
        labels = list(flow_splits.keys())
        sizes = [flow_splits[o] * 100 for o in labels]
        colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))

        wedges, texts, autotexts = ax1.pie(sizes, labels=labels, autopct='%1.1f%%',
                                           colors=colors, startangle=90,
                                           textprops={'fontsize': 10})
        ax1.set_title('Flow Distribution (%)', fontsize=12, fontweight='bold')

        # Subplot 2: Bar chart (top right)
        ax2 = fig.add_subplot(2, 2, 2)
        x_pos = np.arange(len(labels))
        flows = [outlet_flows_mL_s[o] for o in labels]

        bars = ax2.bar(x_pos, flows, color=colors, edgecolor='black', linewidth=1.2)

        # Add value labels on bars
        for bar, flow, frac in zip(bars, flows, sizes):
            height = bar.get_height()
            ax2.annotate(f'{flow:.2f}\nmL/s',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha='center', va='bottom', fontsize=9)

        ax2.set_xticks(x_pos)
        ax2.set_xticklabels(labels, rotation=45, ha='right')
        ax2.set_ylabel('Flow Rate (mL/s)', fontsize=11)
        ax2.set_title('Outlet Flow Rates', fontsize=12, fontweight='bold')
        ax2.axhline(y=inlet_flow_mL_s, color='red', linestyle='--', linewidth=2,
                   label=f'Inlet: {inlet_flow_mL_s:.2f} mL/s')
        ax2.legend(loc='upper right')
        ax2.grid(True, axis='y', alpha=0.3)

        # Subplot 3: Windkessel parameters table (bottom)
        ax3 = fig.add_subplot(2, 1, 2)
        ax3.axis('off')

        # Build table data (uses module-level MMHG_TO_PA and ML_TO_M3 constants)
        table_data = []
        headers = ['Outlet', 'Flow\n(mL/s)', 'Flow\n(%)',
                   'R (Pa·s/m³)', 'C (m³/Pa)', 'Z (Pa·s/m³)',
                   'R\n(mmHg·s/mL)', 'C\n(mL/mmHg)', 'τ=RC\n(s)']

        for outlet in labels:
            params = outlet_parameters.get(outlet, {})
            R = params.get('R', 0)
            C = params.get('C', 0)
            Z = params.get('Z', 0)

            # Clinical units conversion
            R_clinical = R / (MMHG_TO_PA / ML_TO_M3) if R else 0
            C_clinical = C * (MMHG_TO_PA / ML_TO_M3) if C else 0
            tau = R * C if R and C else 0

            table_data.append([
                outlet,
                f'{outlet_flows_mL_s[outlet]:.2f}',
                f'{flow_splits[outlet]*100:.1f}',
                f'{R:.2e}',
                f'{C:.2e}',
                f'{Z:.2e}',
                f'{R_clinical:.3f}',
                f'{C_clinical:.4f}',
                f'{tau:.2f}'
            ])

        # Create table
        table = ax3.table(cellText=table_data,
                         colLabels=headers,
                         cellLoc='center',
                         loc='center',
                         colColours=['lightblue'] * len(headers))

        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1.2, 1.5)

        # Style header row
        for j in range(len(headers)):
            table[(0, j)].set_fontsize(9)
            table[(0, j)].set_text_props(weight='bold')

        ax3.set_title('Windkessel Parameters Summary', fontsize=12, fontweight='bold', pad=20)

        # Add summary text
        total_flow = sum(flows)
        summary_text = (f'Total Inlet Flow: {inlet_flow_mL_s:.2f} mL/s ({inlet_flow_mL_s*60/1000:.2f} L/min)\n'
                       f'Total Outlet Flow: {total_flow:.2f} mL/s (Mass conservation: {total_flow/inlet_flow_mL_s*100:.1f}%)')
        fig.text(0.5, 0.02, summary_text, ha='center', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))

        plt.tight_layout(rect=[0, 0.05, 1, 0.95])
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

        self.log.info(f"Flow distribution plot (steady-state) saved to: {output_path}")
