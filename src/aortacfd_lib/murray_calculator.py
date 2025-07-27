"""
Murray's Law Calculator for Automatic Flow Distribution

Automatically calculates outlet flow ratios based on Murray's law (Q ∝ r^n)
when flow_split is not defined in the configuration.
"""

import os
import math
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict
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
        Extract outlet areas from mesh geometry using checkMesh data.
        
        Returns:
            Dictionary mapping outlet names to areas in m²
        """
        logger.info("Extracting outlet areas from mesh geometry...")
        
        # First try to extract from checkMesh log
        outlet_areas = self._extract_areas_from_checkmesh()
        
        if outlet_areas:
            logger.info("Successfully extracted areas from mesh data")
            return outlet_areas
            
        # Fallback to default STL-based method
        logger.warning("Could not extract areas from mesh, using STL fallback")
        return self._extract_areas_stl_fallback()
    
    def _extract_areas_from_checkmesh(self) -> Dict[str, float]:
        """Extract outlet areas from checkMesh log using face counts."""
        outlet_areas = {}
        
        try:
            checkmesh_log = Path(self.case_dir) / "logs" / "log.checkMesh"
            if not checkmesh_log.exists():
                logger.debug("checkMesh log not found")
                return outlet_areas
                
            with open(checkmesh_log, 'r') as f:
                content = f.read()
            
            # Find patch topology section
            patch_section = re.search(
                r'Checking patch topology.*?\n(.*?)(?=\n\n|\nChecking)', 
                content, re.DOTALL
            )
            
            if patch_section:
                # Get outlet patches from configuration
                outlet_patches = self.config['geometry']['outlet_keywords_ordered']
                
                # Parse patch face counts
                patch_faces = {}
                for line in patch_section.group(1).strip().split('\n'):
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 3:
                            patch_name = parts[0]
                            faces = int(parts[1])
                            patch_faces[patch_name] = faces
                
                # Calculate areas using face counts as relative proportions
                outlet_face_counts = {patch: patch_faces.get(patch, 0) for patch in outlet_patches if patch in patch_faces}
                
                if outlet_face_counts:
                    total_outlet_faces = sum(outlet_face_counts.values())
                    
                    # Estimate areas from face proportions
                    # Use typical aortic outlet areas as reference scale
                    total_ref_area = 2e-4  # Total reference area for all outlets (2 cm²)
                    
                    for outlet, faces in outlet_face_counts.items():
                        # Area proportional to face count
                        area = (faces / total_outlet_faces) * total_ref_area
                        outlet_areas[outlet] = area
                        logger.info(f"Estimated area for {outlet}: {area:.6e} m² (from {faces} faces, {faces/total_outlet_faces*100:.1f}%)")
                
        except Exception as e:
            logger.warning(f"Could not extract areas from checkMesh log: {e}")
            
        return outlet_areas
    
    def _extract_areas_stl_fallback(self) -> Dict[str, float]:
        """Fallback method using estimated areas."""
        outlet_areas = {}
        outlet_patches = self.config['geometry']['outlet_keywords_ordered']
        
        for outlet in outlet_patches:
            # Use estimated area based on typical aortic branch sizes
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

    def find_minimum_patch_radius(self, include_inlet: bool = True) -> float:
        """
        Find the minimum radius among all patches (outlets and optionally inlet).
        
        Args:
            include_inlet: Whether to include inlet in the minimum calculation
            
        Returns:
            Minimum patch radius in meters
        """
        logger.info("Finding minimum patch radius for mesh refinement calculation...")
        
        # Get outlet areas and calculate radii
        outlet_areas = self.extract_outlet_areas_from_stl()
        all_radii = {}
        
        # Add outlet radii
        for outlet, area in outlet_areas.items():
            all_radii[outlet] = math.sqrt(area / math.pi)
            
        # Add inlet radius if requested
        if include_inlet:
            tri_surface_dir = os.path.join(self.case_dir, "constant", "triSurface")
            inlet_patch = self.config['geometry']['inlet_keywords_ordered']
            inlet_stl = os.path.join(tri_surface_dir, f"{inlet_patch}.stl")
            
            if os.path.exists(inlet_stl):
                try:
                    inlet_area = self._calculate_stl_area(inlet_stl)
                    all_radii[inlet_patch] = math.sqrt(inlet_area / math.pi)
                except Exception as e:
                    logger.warning(f"Could not calculate inlet area: {e}")
                    # Use typical inlet size estimate
                    all_radii[inlet_patch] = 0.012  # 12mm radius typical for aortic root
            else:
                logger.warning(f"Inlet STL not found: {inlet_stl}")
                all_radii[inlet_patch] = 0.012  # Default inlet radius
                
        # Find minimum radius
        min_radius = min(all_radii.values())
        min_patch = min(all_radii.items(), key=lambda x: x[1])[0]
        
        logger.info(f"Minimum patch radius found: {min_radius:.6f} m ({min_radius*1000:.2f} mm) from {min_patch}")
        for patch, radius in all_radii.items():
            logger.info(f"  {patch}: {radius:.6f} m ({radius*1000:.2f} mm)")
            
        return min_radius

    def calculate_automatic_refinement_levels(self, cells_per_patch_diameter: Dict[str, int]) -> Dict[str, float]:
        """
        Calculate refinement levels automatically based on minimum patch radius and desired cells per diameter.
        
        Args:
            cells_per_patch_diameter: Dictionary mapping refinement level names to desired cells per diameter
                Example: {"coarse": 10, "medium": 15, "fine": 20}
                
        Returns:
            Dictionary of refinement levels with cell sizes in meters
        """
        logger.info("Calculating automatic refinement levels based on minimum patch radius...")
        
        # Find minimum patch radius
        min_radius = self.find_minimum_patch_radius(include_inlet=False)  # Use outlet patches only
        min_diameter = 2 * min_radius
        
        logger.info(f"Minimum patch diameter: {min_diameter:.6f} m ({min_diameter*1000:.2f} mm)")
        
        # Calculate cell sizes for each refinement level
        refinement_levels = {}
        for level_name, cells_per_diameter in cells_per_patch_diameter.items():
            cell_size = min_diameter / cells_per_diameter
            refinement_levels[level_name] = cell_size
            
            logger.info(f"  {level_name}: {cell_size:.6f} m ({cell_size*1000:.3f} mm) "
                       f"- {cells_per_diameter} cells across minimum diameter")
        
        return refinement_levels

    def calculate_mesh_refinement_config(self, cells_per_patch_diameter: Dict[str, int]) -> Dict:
        """
        Calculate complete mesh refinement configuration with automatic cell sizes.
        
        Args:
            cells_per_patch_diameter: Dictionary mapping refinement level names to desired cells per diameter
                
        Returns:
            Dictionary containing mesh configuration with automatic refinement levels
        """
        logger.info("Generating automatic mesh refinement configuration...")
        
        # Calculate automatic refinement levels
        refinement_levels = self.calculate_automatic_refinement_levels(cells_per_patch_diameter)
        
        # Find minimum patch radius for additional calculations
        min_radius = self.find_minimum_patch_radius(include_inlet=False)
        
        # Calculate suggested snappyHexMesh parameters based on cell sizes
        coarse_cell_size = refinement_levels.get('coarse', 0.002)
        
        # Surface refinement levels based on cell size ratios
        # Level 0: coarse cell size
        # Level 1: coarse/2 cell size  
        # Level 2: coarse/4 cell size
        surface_levels = [0, 1, 2]  # Typically use 0-2 for surface refinement
        
        # Feature level should be high enough to capture small features
        feature_level = 2 if min_radius < 0.003 else 1  # Higher for very small patches
        
        # Region refinement level for volume refinement
        region_level = 2 if min_radius < 0.005 else 1
        
        mesh_config = {
            "refinement_levels": refinement_levels,
            "minimum_patch_radius": min_radius,
            "minimum_patch_diameter": 2 * min_radius,
            "suggested_snappy_settings": {
                "surfaceRefinementLevels": surface_levels,
                "featureLevel": feature_level,
                "regionRefinementLevel": region_level,
                "nCellsBetweenLevels": 3,
                "resolveFeatureAngle": 30
            },
            "methodology": "automatic_murray_based",
            "cells_per_patch_diameter": cells_per_patch_diameter
        }
        
        logger.info("Generated automatic mesh refinement configuration:")
        logger.info(f"  Minimum patch radius: {min_radius:.6f} m ({min_radius*1000:.2f} mm)")
        logger.info(f"  Suggested surface refinement levels: {surface_levels}")
        logger.info(f"  Suggested feature level: {feature_level}")
        logger.info(f"  Suggested region refinement level: {region_level}")
        
        return mesh_config
    
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

def calculate_automatic_mesh_refinement(config: dict, case_directory: str, 
                                        cells_per_patch_diameter: Dict[str, int] = None) -> Dict:
    """
    Calculate automatic mesh refinement configuration based on geometry.
    
    Args:
        config: Full configuration dictionary
        case_directory: Path to case directory
        cells_per_patch_diameter: Dictionary mapping refinement level names to desired cells per diameter
                                 If None, uses defaults: {"coarse": 10, "medium": 15, "fine": 20}
                                 
    Returns:
        Dictionary containing mesh configuration with automatic refinement levels
    """
    if cells_per_patch_diameter is None:
        cells_per_patch_diameter = {
            "coarse": 10,   # 10 cells across minimum patch diameter
            "medium": 15,   # 15 cells across minimum patch diameter  
            "fine": 20      # 20 cells across minimum patch diameter
        }
    
    calculator = MurrayCalculator(case_directory, config)
    return calculator.calculate_mesh_refinement_config(cells_per_patch_diameter)

def update_config_with_automatic_refinement(config: dict, case_directory: str,
                                           cells_per_patch_diameter: Dict[str, int] = None) -> dict:
    """
    Update configuration with automatic refinement levels based on geometry.
    
    Args:
        config: Original configuration
        case_directory: Path to case directory
        cells_per_patch_diameter: Dictionary mapping refinement level names to desired cells per diameter
                                 If None, uses defaults: {"coarse": 10, "medium": 15, "fine": 20}
                                 
    Returns:
        Updated configuration with automatic refinement levels
    """
    # Calculate automatic mesh refinement configuration
    mesh_config = calculate_automatic_mesh_refinement(config, case_directory, cells_per_patch_diameter)
    
    # Update the mesh configuration
    if 'mesh' not in config:
        config['mesh'] = {}
    
    # Update refinement levels with automatic calculation
    config['mesh']['refinement_levels'] = mesh_config['refinement_levels']
    
    # Add metadata about automatic calculation
    config['mesh']['automatic_refinement'] = {
        'enabled': True,
        'minimum_patch_radius': mesh_config['minimum_patch_radius'],
        'minimum_patch_diameter': mesh_config['minimum_patch_diameter'],
        'cells_per_patch_diameter': mesh_config['cells_per_patch_diameter'],
        'methodology': mesh_config['methodology']
    }
    
    # Update snappyHexMesh settings if they exist
    if 'SNAPPY_SETTINGS' in config.get('mesh', {}):
        suggested_settings = mesh_config['suggested_snappy_settings']
        config['mesh']['SNAPPY_SETTINGS'].update({
            'surfaceRefinementLevels': suggested_settings['surfaceRefinementLevels'],
            'featureLevel': suggested_settings['featureLevel'],
            'regionRefinementLevel': suggested_settings['regionRefinementLevel'],
            'nCellsBetweenLevels': suggested_settings['nCellsBetweenLevels'],
            'resolveFeatureAngle': suggested_settings['resolveFeatureAngle']
        })
    
    return config