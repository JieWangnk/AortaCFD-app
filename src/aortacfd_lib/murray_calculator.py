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

        # Murray exponent varies by vessel type and flow conditions:
        # - Aortic bifurcation: ~2.0 (high pulsatility, large vessels)
        # - Coronary arteries: 2.5-3.0 (moderate pulsatility)
        # - Small arteries: ~3.0 (approaches classical Murray's law)
        # Default to 2.39 based on 2024 meta-analysis (PMC11380967)
        self.murray_exponent = self._determine_murray_exponent()

    def _determine_murray_exponent(self) -> float:
        """
        Intelligently determine Murray's law exponent based on vessel characteristics.

        Scientific basis:
        - Aortic arch/thoracic aorta: 2.0-2.2 (high pulsatility, large diameter)
        - Abdominal aorta bifurcation: ~2.0 (Zamir et al.)
        - Coronary arteries: 2.39 (2024 meta-analysis PMC11380967)
        - Peripheral arteries: 2.5-2.7
        - Small arteries/arterioles: 2.7-3.0 (approaches classical Murray)

        Returns:
            Appropriate Murray exponent for the vessel type
        """
        # Check if explicitly set in config
        if 'murray_exponent' in self.config.get('physics', {}):
            exponent = self.config['physics']['murray_exponent']
            logger.info(f"Using configured Murray exponent: {exponent}")
            return exponent

        # Try to determine vessel type from geometry
        try:
            # Get inlet diameter to estimate vessel size
            inlet_name = self.config.get('geometry', {}).get('inlet_keywords_ordered', 'inlet')
            inlet_stl_path = Path(self.case_dir) / "constant" / "triSurface" / f"{inlet_name}.stl"

            if inlet_stl_path.exists():
                inlet_area = self._calculate_stl_area(str(inlet_stl_path))
                inlet_diameter_mm = 2 * math.sqrt(inlet_area / math.pi) * 1000  # Convert to mm

                # Determine exponent based on vessel size
                if inlet_diameter_mm > 25:  # Large vessels (aortic arch)
                    exponent = 2.0
                    vessel_type = "large aortic"
                elif inlet_diameter_mm > 15:  # Medium-large (thoracic/abdominal aorta)
                    exponent = 2.2
                    vessel_type = "thoracic/abdominal aortic"
                elif inlet_diameter_mm > 8:  # Medium vessels (major branches)
                    exponent = 2.39  # Meta-analysis value
                    vessel_type = "major arterial branches"
                elif inlet_diameter_mm > 4:  # Coronary-sized vessels
                    exponent = 2.5
                    vessel_type = "coronary/peripheral arteries"
                else:  # Small vessels
                    exponent = 2.7
                    vessel_type = "small arteries"

                logger.info(f"Auto-detected {vessel_type} (d={inlet_diameter_mm:.1f}mm), using exponent={exponent}")
                return exponent

        except Exception as e:
            logger.warning(f"Could not auto-detect vessel type: {e}")

        # Default to meta-analysis value for general use
        default_exponent = 2.39
        logger.info(f"Using default Murray exponent: {default_exponent} (2024 meta-analysis)")
        return default_exponent

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
                # Parse patch face counts from all patches
                patch_faces = {}
                lines = patch_section.group(1).strip().split('\n')
                for line in lines:
                    if line.strip() and not line.strip().startswith('Patch'):  # Skip header
                        parts = line.split()
                        if len(parts) >= 3:
                            try:
                                patch_name = parts[0]
                                faces = int(parts[1])
                                patch_faces[patch_name] = faces
                            except ValueError:
                                # Skip lines that can't be parsed (like headers)
                                continue

                # Find outlet patches automatically (exclude inlet and wall patches)
                outlet_face_counts = {}
                for patch_name, faces in patch_faces.items():
                    # Include patches that look like outlets (exclude wall, inlet, etc.)
                    if any(keyword in patch_name.lower() for keyword in ['outlet', 'exit', 'out']):
                        outlet_face_counts[patch_name] = faces

                # If no outlets found with keywords, include all non-wall, non-inlet patches
                if not outlet_face_counts:
                    for patch_name, faces in patch_faces.items():
                        if not any(keyword in patch_name.lower() for keyword in ['wall', 'inlet', 'in']):
                            outlet_face_counts[patch_name] = faces

                logger.info(f"Found outlet patches from mesh: {list(outlet_face_counts.keys())}")
                
                if outlet_face_counts:
                    # Hybrid approach: combine face counts with STL file size analysis
                    logger.info("Using hybrid face count + STL size analysis for robust area calculation")

                    # Get STL file sizes for cross-validation
                    stl_sizes = self._get_stl_file_sizes()

                    # Calculate average face area from STL size/face count ratio
                    face_areas = {}
                    total_outlet_faces = sum(outlet_face_counts.values())

                    logger.info("Analyzing STL file size vs face count ratios:")
                    for outlet, faces in outlet_face_counts.items():
                        stl_size = stl_sizes.get(outlet, 0)
                        if stl_size > 0 and faces > 0:
                            # STL size (bytes) roughly correlates with triangle count
                            # Estimate average face area from this ratio
                            bytes_per_face = stl_size / faces
                            face_areas[outlet] = self._estimate_face_area_from_stl_ratio(bytes_per_face)
                            logger.info(f"  {outlet}: {stl_size} bytes ÷ {faces} faces = {bytes_per_face:.1f} bytes/face")
                        else:
                            # Fallback to average if STL data unavailable
                            face_areas[outlet] = 1e-6  # 1 mm² default
                            logger.warning(f"  {outlet}: No STL data, using default face area")

                    logger.info("Final outlet area calculations:")
                    for outlet, faces in outlet_face_counts.items():
                        # Use outlet-specific face area
                        face_area = face_areas[outlet]
                        area = faces * face_area
                        outlet_areas[outlet] = area
                        diameter_mm = 2 * (area / 3.14159) ** 0.5 * 1000
                        proportion = faces / total_outlet_faces
                        logger.info(f"  {outlet}: {area:.6e} m² ({faces} faces × {face_area:.2e} m²/face) → d={diameter_mm:.1f}mm ({proportion:.1%})")
                
        except Exception as e:
            logger.warning(f"Could not extract areas from checkMesh log: {e}")
            
        return outlet_areas

    def _get_stl_file_sizes(self) -> Dict[str, int]:
        """
        Get STL file sizes in bytes for cross-validation with face counts.

        Returns:
            Dictionary mapping outlet names to STL file sizes in bytes
        """
        stl_sizes = {}

        # Look for STL files in the case directory and triSurface
        search_paths = [
            Path(self.case_dir).parent.parent.parent / "cases_input" / "patient1",  # Original STL location
            Path(self.case_dir) / "constant" / "triSurface",  # OpenFOAM mesh location
            Path(self.case_dir).parent / "constant" / "triSurface"  # Alternative location
        ]

        for search_path in search_paths:
            if search_path.exists():
                for stl_file in search_path.glob("outlet*.stl"):
                    outlet_name = stl_file.stem  # Remove .stl extension
                    if stl_file.exists():
                        stl_sizes[outlet_name] = stl_file.stat().st_size
                        logger.debug(f"Found {outlet_name}: {stl_sizes[outlet_name]} bytes")

                # If we found STL files, use this path
                if stl_sizes:
                    logger.info(f"Found STL files in: {search_path}")
                    break

        return stl_sizes

    def _estimate_face_area_from_stl_ratio(self, bytes_per_face: float) -> float:
        """
        Estimate face area based on STL file size per face ratio.

        Larger bytes_per_face typically indicates:
        - Higher precision (more decimal places in STL)
        - Larger triangles
        - More complex geometry

        Args:
            bytes_per_face: STL file size divided by mesh face count

        Returns:
            Estimated face area in m²
        """
        # Empirical relationship between STL bytes/face and actual face area
        # Based on typical cardiovascular mesh characteristics

        if bytes_per_face < 5:
            # Very small bytes/face suggests small, tightly packed faces
            return 5e-7  # 0.5 mm²
        elif bytes_per_face < 10:
            # Moderate bytes/face suggests medium faces
            return 1e-6   # 1 mm²
        elif bytes_per_face < 20:
            # Higher bytes/face suggests larger faces or higher precision
            return 2e-6   # 2 mm²
        else:
            # Very high bytes/face suggests large faces or very high precision
            return 5e-6   # 5 mm²

    def _extract_areas_stl_fallback(self) -> Dict[str, float]:
        """Fallback method using estimated areas."""
        outlet_areas = {}

        # Try to get outlet patches from config, otherwise use defaults
        outlet_patches = []
        if 'geometry' in self.config and 'outlet_keywords_ordered' in self.config['geometry']:
            outlet_patches = self.config['geometry']['outlet_keywords_ordered']
        else:
            # Default outlet naming pattern
            outlet_patches = ['outlet1', 'outlet2', 'outlet3', 'outlet4']
            logger.info(f"Using default outlet patches: {outlet_patches}")

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

        The exponent n varies with vessel type due to pulsatility effects:
        - n ≈ 2.0: Aortic bifurcation (high pulsatility, Zamir et al.)
        - n ≈ 2.39: Meta-analysis value for coronary arteries (PMC11380967)
        - n ≈ 2.5-2.7: Peripheral/smaller arteries
        - n = 3.0: Classical Murray (steady laminar flow, rigid tubes)

        Pulsatility reduces the exponent because:
        1. Wall elasticity absorbs pulsatile energy
        2. Non-Newtonian blood properties become significant
        3. Flow separation and secondary flows occur in large vessels

        Args:
            outlet_areas: Dictionary of outlet areas (if None, will extract from STL)

        Returns:
            Dictionary of normalized flow ratios
        """
        if outlet_areas is None:
            outlet_areas = self.extract_outlet_areas_from_stl()
            
        logger.info(f"Calculating Murray's law flow ratios (exponent={self.murray_exponent})...")

        # Calculate equivalent radii and log details
        outlet_radii = {}
        logger.info("Area to radius conversion:")
        for outlet, area in outlet_areas.items():
            radius = math.sqrt(area / math.pi)
            outlet_radii[outlet] = radius
            diameter_mm = radius * 2 * 1000
            logger.info(f"  {outlet}: {area:.6e} m² → r={radius*1000:.2f}mm → d={diameter_mm:.1f}mm")

        # Calculate relative flows using Murray's law
        relative_flows = {}
        logger.info(f"Murray's law calculation (Q ∝ r^{self.murray_exponent}):")
        for outlet, radius in outlet_radii.items():
            flow_power = radius ** self.murray_exponent
            relative_flows[outlet] = flow_power
            logger.info(f"  {outlet}: r^{self.murray_exponent} = {radius:.6f}^{self.murray_exponent} = {flow_power:.6e}")

        # Normalize to sum to 1.0
        total_flow = sum(relative_flows.values())
        flow_ratios = {outlet: flow/total_flow for outlet, flow in relative_flows.items()}

        logger.info("Final Murray's law flow distribution:")
        for outlet, ratio in flow_ratios.items():
            radius_mm = outlet_radii[outlet] * 1000
            logger.info(f"  {outlet}: {ratio:.4f} ({ratio*100:.1f}%) - r={radius_mm:.1f}mm")
            
        return flow_ratios

    def _calculate_smart_surface_levels(self, min_radius: float) -> list:
        """
        Calculate surface refinement levels intelligently.
        Respects profile settings while applying automatic refinement logic.

        Args:
            min_radius: Minimum patch radius in meters

        Returns:
            List of surface refinement levels [min, max]
        """
        # Get existing profile settings as baseline
        existing_levels = self.config.get('mesh', {}).get('SNAPPY_SETTINGS', {}).get('surfaceRefinementLevels', None)

        # Calculate what automatic refinement would suggest based on patch size
        if min_radius < 0.002:  # Very small patches (<2mm)
            auto_min, auto_max = 2, 3  # Need fine refinement
        elif min_radius < 0.004:  # Small patches (2-4mm)
            auto_min, auto_max = 1, 2  # Medium refinement
        else:  # Larger patches (>4mm)
            auto_min, auto_max = 0, 1  # Coarse refinement acceptable

        # If profile has settings, respect them but ensure minimum quality
        if existing_levels and len(existing_levels) >= 2:
            # Check if this is an explicit coarse profile choice (both levels same and low)
            is_explicit_coarse = (existing_levels[0] == existing_levels[1] and existing_levels[0] <= 1)

            if is_explicit_coarse:
                # Respect explicit coarse profile choice
                logger.info(f"Respecting explicit coarse profile: {existing_levels} "
                           f"(auto would suggest: [{auto_min}, {auto_max}])")
                return existing_levels
            else:
                # Take the maximum of profile and automatic calculation
                # This ensures we never downgrade quality from profile
                min_level = max(existing_levels[0], auto_min)
                max_level = max(existing_levels[1], auto_max)

                # Ensure max is always greater than min
                if max_level <= min_level:
                    max_level = min_level + 1

                logger.info(f"Smart surface levels: [{min_level}, {max_level}] "
                           f"(profile: {existing_levels}, auto: [{auto_min}, {auto_max}])")
                return [min_level, max_level]
        else:
            # No profile settings, use automatic calculation
            logger.info(f"Auto surface levels: [{auto_min}, {auto_max}] based on min radius {min_radius*1000:.1f}mm")
            return [auto_min, auto_max]

    def _calculate_smart_feature_level(self, min_radius: float) -> int:
        """
        Calculate feature extraction level intelligently.
        Ensures it's balanced with surface refinement levels.

        Args:
            min_radius: Minimum patch radius in meters

        Returns:
            Feature extraction level
        """
        # Get existing profile setting
        existing_feature = self.config.get('mesh', {}).get('SNAPPY_SETTINGS', {}).get('featureLevel', None)

        # Get the surface levels we just calculated
        surface_levels = self._calculate_smart_surface_levels(min_radius)
        min_surface_level = surface_levels[0]

        # Feature level should match or be slightly below minimum surface level
        # This prevents imbalanced mesh as you discovered
        balanced_feature = min_surface_level

        # Calculate automatic feature level based on patch size as fallback
        auto_feature = 2 if min_radius < 0.003 else 1

        # If profile has a setting, respect it but ensure balance
        if existing_feature is not None:
            # Use profile setting but ensure it's balanced with surface refinement
            feature_level = max(existing_feature, balanced_feature)
            if feature_level > min_surface_level + 1:
                # Don't let feature level be too far ahead of surface
                feature_level = min_surface_level + 1
                logger.warning(f"Feature level {existing_feature} too high for surface level {min_surface_level}, "
                             f"capping at {feature_level}")
        else:
            # Use the balanced automatic value, but consider geometry-based recommendation
            feature_level = max(balanced_feature, auto_feature)

        logger.info(f"Smart feature level: {feature_level} (balanced with surface min: {min_surface_level})")
        return feature_level

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

        This method now intelligently respects profile settings while calculating
        automatic refinement levels based on minimum patch size.

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

        # Smart surface refinement that respects profile settings
        surface_levels = self._calculate_smart_surface_levels(min_radius)

        # Smart feature level calculation that respects profile
        feature_level = self._calculate_smart_feature_level(min_radius)

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
        # Note: Removed unused max_outlet variable

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