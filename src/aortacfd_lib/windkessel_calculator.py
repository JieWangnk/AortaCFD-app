"""
Windkessel Coefficient Calculator based on research paper methodology.

This module implements the scientific approach for calculating optimal
3-element Windkessel boundary condition parameters as described in:
"A strategy for the simulation of complex physiological flows"

Key improvements:
1. Murray's law for physiological flow distribution
2. Conservative estimation of resistance lower bounds
3. Proper capacitance selection for stability
4. Geometry-based parameter calculation
"""

import math
from typing import Dict, List
from .utils.logger import Logger

logger = Logger("WindkesselCalculator").get_logger()

class WindkesselCalculator:
    """
    Calculates physiologically realistic Windkessel parameters.
    """
    
    def __init__(self, geometry_config: dict, fluid_properties: dict):
        """
        Initialize calculator with geometry and fluid properties.
        
        Args:
            geometry_config: Geometry configuration including outlet areas
            fluid_properties: Fluid properties (viscosity, density)
        """
        self.geometry = geometry_config
        self.fluid = fluid_properties
        
        # Default fluid properties for blood
        self.mu = fluid_properties.get('dynamic_viscosity', 0.004)  # Pa·s (blood viscosity)
        self.rho = fluid_properties.get('density', 1060)  # kg/m³ (blood density)
        
        # Physiological parameters
        self.systolic_pressure = 120 * 133.322  # mmHg to Pa
        self.diastolic_pressure = 80 * 133.322   # mmHg to Pa
        self.cardiac_period = 0.8  # seconds (75 BPM)
        
    def calculate_outlet_areas(self, stl_files: List[str], case_directory: str) -> Dict[str, float]:
        """
        Extract outlet areas from STL files using the Murray calculator.
        """
        from .murray_calculator import MurrayCalculator
        
        # Use the MurrayCalculator for accurate area calculation
        murray_calc = MurrayCalculator(case_directory, {'geometry': self.geometry_config})
        outlet_areas = murray_calc.extract_outlet_areas_from_stl()
        
        logger.info(f"Calculated outlet areas from STL files: {outlet_areas}")
        return outlet_areas
    
    def calculate_equivalent_radii(self, outlet_areas: Dict[str, float]) -> Dict[str, float]:
        """
        Calculate equivalent radius for each outlet (r = sqrt(A/π)).
        
        Args:
            outlet_areas: Dictionary of outlet names to areas
            
        Returns:
            Dictionary of outlet names to equivalent radii
        """
        radii = {}
        for outlet, area in outlet_areas.items():
            radii[outlet] = math.sqrt(area / math.pi)
            
        logger.info(f"Equivalent radii: {radii}")
        return radii
    
    def calculate_murray_flow_ratios(self, radii: Dict[str, float], exponent: float = 3.0) -> Dict[str, float]:
        """
        Calculate flow ratios using Murray's law: Q ∝ r^n
        
        Args:
            radii: Dictionary of outlet equivalent radii
            exponent: Murray's law exponent (3.0 for minimum work, 2.5-2.7 more realistic)
            
        Returns:
            Dictionary of flow ratios normalized to sum to 1.0
        """
        # Calculate relative flows using Murray's law
        relative_flows = {}
        for outlet, radius in radii.items():
            relative_flows[outlet] = radius ** exponent
            
        # Normalize to sum to 1.0
        total_flow = sum(relative_flows.values())
        flow_ratios = {outlet: flow/total_flow for outlet, flow in relative_flows.items()}
        
        logger.info(f"Murray's law flow ratios (exponent={exponent}): {flow_ratios}")
        return flow_ratios
    
    def estimate_vessel_resistance(self, radii: Dict[str, float], vessel_lengths: Dict[str, float] = None) -> Dict[str, float]:
        """
        Estimate vessel resistance K*L for each outlet using Poiseuille flow.
        K = 8μ/(πr⁴), total resistance = K*L
        
        Args:
            radii: Dictionary of outlet equivalent radii
            vessel_lengths: Dictionary of estimated vessel lengths (if None, use conservative estimates)
            
        Returns:
            Dictionary of vessel resistances (K*L values)
        """
        if vessel_lengths is None:
            # Conservative estimate: use 2-5 diameters as length
            vessel_lengths = {outlet: 4 * radius for outlet, radius in radii.items()}
            
        vessel_resistances = {}
        for outlet, radius in radii.items():
            K = 8 * self.mu / (math.pi * radius**4)  # Resistance per unit length
            L = vessel_lengths[outlet]
            vessel_resistances[outlet] = K * L
            
        logger.info(f"Estimated vessel resistances (K*L): {vessel_resistances}")
        return vessel_resistances
    
    def calculate_windkessel_resistances(self, 
                                       flow_ratios: Dict[str, float], 
                                       vessel_resistances: Dict[str, float],
                                       r_multiplier: float = 10.0) -> Dict[str, float]:
        """
        Calculate Windkessel resistances using the paper's methodology.
        
        The key condition is R >> max(K*L) for all outlets to ensure
        the Q-R relation holds: Q_j/Q_ref = R_ref/R_j
        
        Args:
            flow_ratios: Desired flow ratios from Murray's law
            vessel_resistances: Estimated vessel resistances (K*L)
            r_multiplier: Safety factor for R >> K*L condition
            
        Returns:
            Dictionary of Windkessel resistances
        """
        # Find the outlet with largest K*L (most restrictive)
        max_vessel_resistance = max(vessel_resistances.values())
        
        # Set minimum R based on condition R >> max(K*L)
        R_min = r_multiplier * max_vessel_resistance
        
        # Find reference outlet (largest flow rate)
        ref_outlet = max(flow_ratios.items(), key=lambda x: x[1])[0]
        ref_flow_ratio = flow_ratios[ref_outlet]
        
        # Calculate resistances using Q-R relation: Q_j/Q_ref = R_ref/R_j
        # Therefore: R_j = R_ref * Q_ref/Q_j
        windkessel_resistances = {}
        R_ref = R_min  # Start with minimum safe value for reference
        
        for outlet, flow_ratio in flow_ratios.items():
            if outlet == ref_outlet:
                windkessel_resistances[outlet] = R_ref
            else:
                # R_j = R_ref * Q_ref/Q_j
                windkessel_resistances[outlet] = R_ref * ref_flow_ratio / flow_ratio
                
        logger.info(f"Calculated Windkessel resistances (R_multiplier={r_multiplier}): {windkessel_resistances}")
        return windkessel_resistances
    
    def calculate_capacitances(self, 
                             resistances: Dict[str, float],
                             rc_multiplier: float = 0.1) -> Dict[str, float]:
        """
        Calculate capacitances based on RC time constant methodology.
        
        The paper recommends: 1/ω₀ >> RC >> 0
        Where ω₀ is the fundamental frequency of cardiac cycle.
        
        Args:
            resistances: Windkessel resistances
            rc_multiplier: Multiplier for cardiac period to set RC
            
        Returns:
            Dictionary of capacitances
        """
        # Fundamental frequency of cardiac cycle
        omega_0 = 2 * math.pi / self.cardiac_period
        
        # RC should be much smaller than 1/ω₀ but not too small
        # Paper suggests RC ~ 0.1 * T_cardiac for stability
        target_rc = rc_multiplier * self.cardiac_period
        
        capacitances = {}
        for outlet, resistance in resistances.items():
            # C = RC/R
            capacitances[outlet] = target_rc / resistance
            
        logger.info(f"Calculated capacitances (RC={target_rc:.3f}s): {capacitances}")
        return capacitances
    
    def calculate_peripheral_resistances(self, 
                                       resistances: Dict[str, float],
                                       pressure_drop_factor: float = 0.9) -> Dict[str, float]:
        """
        Calculate peripheral resistances (Z) to achieve desired pressure drop.
        
        Args:
            resistances: Windkessel resistances (R)
            pressure_drop_factor: Fraction of total pressure drop across Z
            
        Returns:
            Dictionary of peripheral resistances
        """
        total_pressure_drop = self.systolic_pressure - self.diastolic_pressure
        target_pressure_drop = pressure_drop_factor * total_pressure_drop
        
        # For simplicity, use same Z/R ratio for all outlets
        # In practice, this could be tuned per outlet
        z_to_r_ratio = 0.1  # Z = 10% of R (adjustable parameter)
        
        peripheral_resistances = {}
        for outlet, resistance in resistances.items():
            peripheral_resistances[outlet] = z_to_r_ratio * resistance
            
        logger.info(f"Calculated peripheral resistances: {peripheral_resistances}")
        return peripheral_resistances
    
    def generate_windkessel_config(self, 
                                 case_directory: str,
                                 stl_files: List[str] = None,
                                 murray_exponent: float = 2.7,
                                 r_multiplier: float = 10.0,
                                 rc_multiplier: float = 0.1) -> Dict:
        """
        Generate complete Windkessel configuration using paper methodology.
        
        Args:
            case_directory: Path to case directory
            stl_files: List of STL files for area calculation
            murray_exponent: Exponent for Murray's law (2.5-3.0, realistic ~2.7)
            r_multiplier: Safety factor for R >> K*L condition
            rc_multiplier: RC time constant as fraction of cardiac period
            
        Returns:
            Complete Windkessel configuration dictionary
        """
        logger.info("Generating Windkessel configuration using research methodology...")
        
        # Step 1: Calculate outlet areas and equivalent radii
        outlet_areas = self.calculate_outlet_areas(stl_files or [], case_directory)
        radii = self.calculate_equivalent_radii(outlet_areas)
        
        # Step 2: Calculate physiological flow ratios using Murray's law
        flow_ratios = self.calculate_murray_flow_ratios(radii, murray_exponent)
        
        # Step 3: Estimate vessel resistances for R >> K*L condition
        vessel_resistances = self.estimate_vessel_resistance(radii)
        
        # Step 4: Calculate Windkessel resistances
        resistances = self.calculate_windkessel_resistances(
            flow_ratios, vessel_resistances, r_multiplier
        )
        
        # Step 5: Calculate capacitances for stability
        capacitances = self.calculate_capacitances(resistances, rc_multiplier)
        
        # Step 6: Calculate peripheral resistances
        peripheral_resistances = self.calculate_peripheral_resistances(resistances)
        
        # Create configuration
        config = {
            "flow_ratios": flow_ratios,
            "outlet_parameters": {}
        }
        
        for outlet in radii.keys():
            config["outlet_parameters"][outlet] = {
                "R": resistances[outlet],
                "C": capacitances[outlet], 
                "Z": peripheral_resistances[outlet],
                "radius": radii[outlet],
                "area": outlet_areas[outlet],
                "flow_ratio": flow_ratios[outlet]
            }
            
        # Add summary statistics
        config["summary"] = {
            "total_resistance_range": f"{min(resistances.values()):.0f} - {max(resistances.values()):.0f} Pa·s/m³",
            "total_capacitance_range": f"{min(capacitances.values()):.2e} - {max(capacitances.values()):.2e} m³/Pa",
            "rc_time_constants": {outlet: resistances[outlet] * capacitances[outlet] 
                                for outlet in resistances.keys()},
            "murray_exponent": murray_exponent,
            "r_multiplier": r_multiplier,
            "rc_multiplier": rc_multiplier
        }
        
        logger.info("Windkessel configuration generated successfully")
        return config

