"""
Murray's Law Calculator for Automatic Flow Distribution

Automatically calculates outlet flow ratios based on Murray's law (Q ∝ r^n)
when flow_split is not defined in the configuration.
"""

import os
import math
import subprocess
import tempfile
from typing import Dict, List, Tuple
from .utils.logger import Logger

logger = Logger("MurrayCalculator").get_logger()

class MurrayCalculator:
    """
    Calculates flow distribution using Murray's law from actual geometry.
    """
    
    def __init__(self, case_directory: str, config: dict):
        self.case_dir = case_directory
        self.config = config
        self.murray_exponent = 2.7  # Realistic exponent for blood flow
        
    def extract_outlet_areas_from_stl(self) -> Dict[str, float]:
        """
        Extract outlet areas from STL files using OpenFOAM utilities.
        
        Returns:
            Dictionary mapping outlet names to areas in m²
        """
        logger.info("Extracting outlet areas from STL geometry...")
        
        tri_surface_dir = os.path.join(self.case_dir, "constant", "triSurface")
        outlet_areas = {}
        
        # Get outlet patches from configuration
        outlet_patches = self.config['geometry']['outlet_keywords_ordered']
        
        for outlet in outlet_patches:
            stl_file = os.path.join(tri_surface_dir, f"{outlet}.stl")
            
            if os.path.exists(stl_file):
                try:
                    area = self._calculate_stl_area(stl_file)
                    outlet_areas[outlet] = area
                    logger.info(f"Extracted area for {outlet}: {area:.6e} m²")
                except Exception as e:
                    logger.warning(f"Could not extract area for {outlet}: {e}")
                    # Fallback to estimated area based on typical aortic branch sizes
                    outlet_areas[outlet] = self._estimate_outlet_area(outlet)
            else:
                logger.warning(f"STL file not found for {outlet}: {stl_file}")
                outlet_areas[outlet] = self._estimate_outlet_area(outlet)
                
        return outlet_areas
    
    def _calculate_stl_area(self, stl_file: str) -> float:
        """
        Calculate surface area of STL file using surfaceArea utility.
        
        Args:
            stl_file: Path to STL file
            
        Returns:
            Surface area in m²
        """
        try:
            # Use OpenFOAM surfaceArea utility
            of_env_path = self.config.get("openfoam_env_path")
            if not of_env_path:
                raise ValueError("OpenFOAM environment path not configured")
                
            # Create temporary directory for calculation
            with tempfile.TemporaryDirectory() as temp_dir:
                # Copy STL file to temp directory
                temp_stl = os.path.join(temp_dir, "surface.stl")
                subprocess.run(["cp", stl_file, temp_stl], check=True)
                
                # Run surfaceArea utility
                cmd = f"source {of_env_path} && surfaceArea {temp_stl}"
                result = subprocess.run(
                    ["bash", "-c", cmd],
                    capture_output=True,
                    text=True,
                    cwd=temp_dir
                )
                
                if result.returncode == 0:
                    # Parse output to extract area
                    for line in result.stdout.split('\n'):
                        if 'Area' in line and '=' in line:
                            area_str = line.split('=')[1].strip()
                            return float(area_str)
                    
                logger.warning(f"Could not parse area from surfaceArea output: {result.stdout}")
                
        except Exception as e:
            logger.warning(f"surfaceArea utility failed: {e}")
            
        # Fallback: estimate from STL triangles (simple approximation)
        return self._estimate_area_from_stl_triangles(stl_file)
    
    def _estimate_area_from_stl_triangles(self, stl_file: str) -> float:
        """
        Simple estimation of STL area by reading triangle data.
        
        Args:
            stl_file: Path to STL file
            
        Returns:
            Estimated area in m²
        """
        try:
            with open(stl_file, 'r') as f:
                lines = f.readlines()
                
            total_area = 0.0
            vertices = []
            
            for line in lines:
                line = line.strip()
                if line.startswith('vertex'):
                    coords = [float(x) for x in line.split()[1:4]]
                    vertices.append(coords)
                    
                    if len(vertices) == 3:
                        # Calculate triangle area using cross product
                        v1 = [vertices[1][i] - vertices[0][i] for i in range(3)]
                        v2 = [vertices[2][i] - vertices[0][i] for i in range(3)]
                        
                        # Cross product
                        cross = [
                            v1[1]*v2[2] - v1[2]*v2[1],
                            v1[2]*v2[0] - v1[0]*v2[2], 
                            v1[0]*v2[1] - v1[1]*v2[0]
                        ]
                        
                        # Triangle area = 0.5 * |cross product|
                        area = 0.5 * math.sqrt(sum(c*c for c in cross))
                        total_area += area
                        vertices = []
                        
            # Apply scale factor if geometry was scaled
            scale_factor = self.config.get('geometry', {}).get('scale_factor', 1.0)
            total_area *= (scale_factor ** 2)
            
            return total_area
            
        except Exception as e:
            logger.warning(f"Could not estimate area from STL triangles: {e}")
            return 1e-4  # Default fallback area
    
    def _estimate_outlet_area(self, outlet_name: str) -> float:
        """
        Provide fallback area estimates based on typical aortic anatomy.
        
        Args:
            outlet_name: Name of the outlet
            
        Returns:
            Estimated area in m²
        """
        # Typical aortic branch diameters (in mm) after scaling
        typical_diameters = {
            'outlet1': 12,  # Main branch (e.g., descending aorta)
            'outlet2': 8,   # Large branch
            'outlet3': 6,   # Medium branch  
            'outlet4': 4    # Small branch
        }
        
        # Get diameter or use default based on outlet index
        if outlet_name in typical_diameters:
            diameter_mm = typical_diameters[outlet_name]
        else:
            # Extract number from outlet name if possible
            outlet_num = ''.join(filter(str.isdigit, outlet_name))
            if outlet_num:
                diameter_mm = max(4, 14 - 2*int(outlet_num))  # Decreasing size
            else:
                diameter_mm = 6  # Default
        
        # Convert to area in m²
        radius_m = (diameter_mm / 1000) / 2  # mm to m, then radius
        area = math.pi * radius_m**2
        
        logger.info(f"Estimated area for {outlet_name}: {area:.6e} m² (d={diameter_mm}mm)")
        return area
    
    def calculate_murray_flow_ratios(self, outlet_areas: Dict[str, float] = None) -> Dict[str, float]:
        """
        Calculate flow ratios using Murray's law: Q ∝ r^n
        
        Args:
            outlet_areas: Dictionary of outlet areas (if None, will extract from STL)
            
        Returns:
            Dictionary of normalized flow ratios
        """
        if outlet_areas is None:
            outlet_areas = self.extract_outlet_areas_from_stl()
            
        logger.info(f"Calculating Murray's law flow ratios (exponent={self.murray_exponent})...")
        
        # Calculate equivalent radii
        outlet_radii = {}
        for outlet, area in outlet_areas.items():
            outlet_radii[outlet] = math.sqrt(area / math.pi)
            
        # Calculate relative flows using Murray's law
        relative_flows = {}
        for outlet, radius in outlet_radii.items():
            relative_flows[outlet] = radius ** self.murray_exponent
            
        # Normalize to sum to 1.0
        total_flow = sum(relative_flows.values())
        flow_ratios = {outlet: flow/total_flow for outlet, flow in relative_flows.items()}
        
        logger.info("Calculated Murray's law flow ratios:")
        for outlet, ratio in flow_ratios.items():
            radius_mm = outlet_radii[outlet] * 1000
            logger.info(f"  {outlet}: {ratio:.3f} ({ratio*100:.1f}%) - r={radius_mm:.1f}mm")
            
        return flow_ratios
    
    def update_windkessel_coefficients(self, flow_ratios: Dict[str, float]) -> Dict:
        """
        Update Windkessel coefficients based on Murray's law flow ratios.
        
        Args:
            flow_ratios: Flow ratios from Murray's law
            
        Returns:
            Updated windkessel configuration
        """
        logger.info("Updating Windkessel coefficients based on Murray's law...")
        
        # Import here to avoid circular imports
        from .windkessel_calculator import WindkesselCalculator
        
        # Create calculator with current configuration
        fluid_properties = {
            'dynamic_viscosity': self.config.get('physics', {}).get('kinematicViscosity', 4e-6) * 1060,  # Convert to dynamic
            'density': 1060
        }
        
        calculator = WindkesselCalculator(self.config['geometry'], fluid_properties)
        
        # Generate outlet areas from flow ratios (reverse calculation)
        # Assume largest outlet has area 1.2e-4 m² and scale others
        max_flow_ratio = max(flow_ratios.values())
        max_outlet = max(flow_ratios.items(), key=lambda x: x[1])[0]
        
        outlet_areas = {}
        for outlet, ratio in flow_ratios.items():
            # Scale area based on flow ratio and Murray's law: A ∝ Q^(2/n)
            area_ratio = (ratio / max_flow_ratio) ** (2.0 / self.murray_exponent)
            outlet_areas[outlet] = 1.2e-4 * area_ratio
            
        # Calculate equivalent radii
        radii = calculator.calculate_equivalent_radii(outlet_areas)
        
        # Estimate vessel resistances
        vessel_resistances = calculator.estimate_vessel_resistance(radii)
        
        # Calculate Windkessel resistances with conservative multiplier
        resistances = calculator.calculate_windkessel_resistances(
            flow_ratios, vessel_resistances, r_multiplier=20.0  # More conservative
        )
        
        # Calculate capacitances for stability
        capacitances = calculator.calculate_capacitances(resistances, rc_multiplier=0.05)  # Faster decay
        
        # Calculate peripheral resistances
        peripheral_resistances = calculator.calculate_peripheral_resistances(resistances)
        
        # Create outlet parameters
        outlet_parameters = {}
        for outlet in flow_ratios.keys():
            outlet_parameters[outlet] = {
                "R": resistances[outlet],
                "C": capacitances[outlet],
                "Z": peripheral_resistances[outlet],
                "radius": radii[outlet],
                "area": outlet_areas[outlet],
                "flow_ratio": flow_ratios[outlet]
            }
            
        logger.info("Updated Windkessel coefficients:")
        for outlet, params in outlet_parameters.items():
            logger.info(f"  {outlet}: R={params['R']:.0f}, C={params['C']:.2e}, Z={params['Z']:.0f}")
            
        return {
            "flow_split": flow_ratios,
            "outlet_parameters": outlet_parameters,
            "methodology": "murray_law_automatic",
            "murray_exponent": self.murray_exponent
        }

def get_murray_based_flow_split(config: dict, case_directory: str) -> Dict[str, float]:
    """
    Convenience function to get Murray's law flow split.
    
    Args:
        config: Full configuration dictionary
        case_directory: Path to case directory
        
    Returns:
        Dictionary of flow ratios
    """
    calculator = MurrayCalculator(case_directory, config)
    return calculator.calculate_murray_flow_ratios()

def update_config_with_murray_law(config: dict, case_directory: str) -> dict:
    """
    Update configuration with Murray's law based Windkessel coefficients.
    
    Args:
        config: Original configuration
        case_directory: Path to case directory
        
    Returns:
        Updated configuration with Murray's law coefficients
    """
    calculator = MurrayCalculator(case_directory, config)
    
    # Calculate flow ratios from geometry
    flow_ratios = calculator.calculate_murray_flow_ratios()
    
    # Update Windkessel coefficients
    windkessel_config = calculator.update_windkessel_coefficients(flow_ratios)
    
    # Update the configuration
    if 'outlets' not in config:
        config['outlets'] = {}
    if 'windkessel_settings' not in config['outlets']:
        config['outlets']['windkessel_settings'] = {}
        
    config['outlets']['windkessel_settings'].update(windkessel_config)
    
    return config