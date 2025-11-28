"""
Field-Driven Mesh Refinement Strategy
=====================================

Implements solution-based adaptive refinement for CoA cases.
Uses pressure gradients, vorticity, and WSS as indicators.
"""

import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import subprocess
import json

from aortacfd_lib.utils.logger import Logger


class FieldRefinementStrategy:
    """
    Generate refinement regions based on solution fields.
    
    Primary indicators:
    - |∇p| for stenotic jet and reattachment
    - Vorticity for shear layers
    - WSS gradients for near-wall regions
    """
    
    def __init__(self, case_dir: str, config: Dict):
        """
        Initialize field refinement strategy.
        
        Args:
            case_dir: OpenFOAM case directory
            config: Mesh configuration dictionary
        """
        self.case_dir = Path(case_dir)
        self.config = config
        self.logger = Logger("FieldRefinement").get_logger()
        
        # Refinement thresholds (percentiles)
        self.thresholds = {
            'gradp_percentile': 85,      # Top 15% of |∇p|
            'vorticity_percentile': 80,   # Top 20% of vorticity
            'wss_grad_percentile': 90,    # Top 10% of WSS gradient
            'q_criterion': 100            # Q-criterion threshold for LES
        }
        
        # Maximum refinement levels
        self.max_levels = {
            'gradp': 2,
            'vorticity': 1,
            'wss': 1,
            'combined': 3
        }
    
    def generate_refinement_regions(self, iteration: int = 1) -> Dict:
        """
        Generate all refinement regions based on current solution.
        
        Args:
            iteration: Current optimization iteration
            
        Returns:
            Dictionary of refinement regions for snappyHexMeshDict
        """
        self.logger.info(f"Generating field-based refinement regions (iteration {iteration})")
        
        regions = {}
        
        # Calculate field indicators
        self._calculate_field_indicators()
        
        # Generate pressure gradient refinement
        gradp_regions = self._generate_gradp_refinement()
        regions.update(gradp_regions)
        
        # Generate vorticity refinement
        vort_regions = self._generate_vorticity_refinement()
        regions.update(vort_regions)
        
        # Generate WSS-based refinement
        wss_regions = self._generate_wss_refinement()
        regions.update(wss_regions)
        
        # Add y+ non-compliance regions
        yplus_regions = self._generate_yplus_refinement()
        regions.update(yplus_regions)
        
        # Combine and limit total refinement
        regions = self._combine_and_limit_regions(regions)
        
        self.logger.info(f"Generated {len(regions)} refinement regions")
        
        return regions
    
    def _calculate_field_indicators(self):
        """Calculate all field indicators from current solution."""
        self.logger.info("Calculating field indicators")
        
        # Get latest time directory
        latest_time = self._get_latest_time()
        
        # Calculate pressure gradient
        self._run_postprocess('grad(p)', 'gradP')
        
        # Calculate velocity gradient and vorticity
        self._run_postprocess('grad(U)', 'gradU')
        self._run_postprocess('vorticity', 'vorticity')
        
        # Calculate wall shear stress if available
        if self._check_field_exists('wallShearStress', latest_time):
            self._run_postprocess('grad(wallShearStress)', 'gradWSS')
        
        # Calculate Q-criterion for LES
        if 'LES' in self.config.get('solver_type', ''):
            self._run_postprocess('Q', 'QCriterion')
    
    def _generate_gradp_refinement(self) -> Dict:
        """
        Generate refinement regions based on pressure gradient.
        
        Returns:
            Dictionary of gradP-based refinement regions
        """
        self.logger.info("Generating pressure gradient refinement regions")
        
        latest_time = self._get_latest_time()
        gradp_file = self.case_dir / latest_time / 'grad(p)'
        
        if not gradp_file.exists():
            self.logger.warning("No pressure gradient field found")
            return {}
        
        # Read and analyze gradient field
        gradp_data = self._read_vector_field(gradp_file)
        gradp_mag = np.linalg.norm(gradp_data, axis=1)
        
        # Calculate threshold
        threshold = np.percentile(gradp_mag, self.thresholds['gradp_percentile'])
        
        # Find regions above threshold
        high_gradp_cells = np.where(gradp_mag > threshold)[0]
        
        # Cluster cells into regions
        regions = self._cluster_cells_to_regions(high_gradp_cells, 'gradP')
        
        return regions
    
    def _generate_vorticity_refinement(self) -> Dict:
        """
        Generate refinement regions based on vorticity.
        
        Returns:
            Dictionary of vorticity-based refinement regions
        """
        self.logger.info("Generating vorticity refinement regions")
        
        latest_time = self._get_latest_time()
        vort_file = self.case_dir / latest_time / 'vorticity'
        
        if not vort_file.exists():
            self.logger.warning("No vorticity field found")
            return {}
        
        # Read and analyze vorticity field
        vort_data = self._read_vector_field(vort_file)
        vort_mag = np.linalg.norm(vort_data, axis=1)
        
        # Calculate threshold
        threshold = np.percentile(vort_mag, self.thresholds['vorticity_percentile'])
        
        # Find regions above threshold
        high_vort_cells = np.where(vort_mag > threshold)[0]
        
        # Cluster cells into regions
        regions = self._cluster_cells_to_regions(high_vort_cells, 'vorticity')
        
        return regions
    
    def _generate_wss_refinement(self) -> Dict:
        """
        Generate refinement regions based on WSS gradients.
        
        Returns:
            Dictionary of WSS-based refinement regions
        """
        self.logger.info("Generating WSS gradient refinement regions")
        
        latest_time = self._get_latest_time()
        wss_grad_file = self.case_dir / latest_time / 'grad(wallShearStress)'
        
        if not wss_grad_file.exists():
            self.logger.warning("No WSS gradient field found")
            return {}
        
        # Read and analyze WSS gradient field
        wss_grad_data = self._read_tensor_field(wss_grad_file)
        
        # Calculate magnitude of gradient
        wss_grad_mag = self._tensor_magnitude(wss_grad_data)
        
        # Calculate threshold
        threshold = np.percentile(wss_grad_mag, self.thresholds['wss_grad_percentile'])
        
        # Find regions above threshold
        high_wss_cells = np.where(wss_grad_mag > threshold)[0]
        
        # Create near-wall refinement regions
        regions = self._create_nearwall_regions(high_wss_cells)
        
        return regions
    
    def _generate_yplus_refinement(self) -> Dict:
        """
        Generate refinement for y+ non-compliance regions.
        
        Returns:
            Dictionary of y+ based refinement regions
        """
        self.logger.info("Generating y+ compliance refinement regions")
        
        # Read y+ field if available
        yplus_file = self.case_dir / 'postProcessing' / 'yPlus' / '0' / 'yPlus.dat'
        
        if not yplus_file.exists():
            return {}
        
        regions = {}
        
        # Parse y+ data
        with open(yplus_file, 'r') as f:
            lines = f.readlines()
        
        # Identify patches with non-compliant y+
        target_min = self.config.get('yplus_target_min', 1.0)
        target_max = self.config.get('yplus_target_max', 5.0)
        
        non_compliant_patches = []
        
        for line in lines:
            if 'Patch:' in line:
                parts = line.split()
                patch_name = parts[1]
                yplus_avg = float(parts[-1])
                
                if yplus_avg < target_min or yplus_avg > target_max:
                    non_compliant_patches.append(patch_name)
        
        # Create refinement regions near non-compliant patches
        for patch in non_compliant_patches:
            region_name = f'yplus_refinement_{patch}'
            regions[region_name] = self._create_patch_proximity_region(patch)
        
        return regions
    
    def _cluster_cells_to_regions(self, cell_indices: np.ndarray, 
                                 prefix: str) -> Dict:
        """
        Cluster cells into coherent refinement regions.
        
        Args:
            cell_indices: Indices of cells to refine
            prefix: Prefix for region names
            
        Returns:
            Dictionary of refinement regions
        """
        if len(cell_indices) == 0:
            return {}
        
        # Get cell centers
        cell_centers = self._read_cell_centers()
        selected_centers = cell_centers[cell_indices]
        
        # Use simple distance-based clustering
        try:
            from sklearn.cluster import DBSCAN
            # Cluster with DBSCAN
            clustering = DBSCAN(eps=0.005, min_samples=10)  # 5mm proximity
            labels = clustering.fit_predict(selected_centers)
        except ImportError:
            # Fallback to simple grid-based clustering
            labels = self._simple_grid_clustering(selected_centers)
        
        regions = {}
        unique_labels = set(labels)
        
        for label in unique_labels:
            if label == -1:  # Noise points
                continue
            
            # Get points in this cluster
            cluster_points = selected_centers[labels == label]
            
            # Create bounding box for cluster
            min_point = np.min(cluster_points, axis=0)
            max_point = np.max(cluster_points, axis=0)
            
            # Add some padding
            padding = 0.002  # 2mm
            min_point -= padding
            max_point += padding
            
            region_name = f'{prefix}_region_{label}'
            regions[region_name] = {
                'type': 'box',
                'min': min_point.tolist(),
                'max': max_point.tolist(),
                'mode': 'inside',
                'levels': [[1e15, self.max_levels.get(prefix, 1)]]
            }
        
        return regions
    
    def _create_nearwall_regions(self, cell_indices: np.ndarray) -> Dict:
        """
        Create near-wall refinement regions.
        
        Args:
            cell_indices: Indices of cells near wall
            
        Returns:
            Dictionary of near-wall refinement regions
        """
        regions = {}
        
        # Group by proximity to wall patches
        wall_patches = ['wall_aorta']  # Add other wall patches as needed
        
        for patch in wall_patches:
            region_name = f'nearwall_{patch}'
            regions[region_name] = {
                'type': 'distance',
                'mode': 'inside',
                'levels': [[0.002, 1], [0.005, 0]],  # Refine within 2mm of wall
                'surfaceName': patch
            }
        
        return regions
    
    def _create_patch_proximity_region(self, patch_name: str) -> Dict:
        """
        Create refinement region near a patch.
        
        Args:
            patch_name: Name of the patch
            
        Returns:
            Refinement region dictionary
        """
        return {
            'type': 'distance',
            'mode': 'inside',
            'levels': [[0.001, 2], [0.003, 1], [0.005, 0]],  # Multi-level refinement
            'surfaceName': patch_name
        }
    
    def _combine_and_limit_regions(self, regions: Dict) -> Dict:
        """
        Combine overlapping regions and limit total refinement.
        
        Args:
            regions: Dictionary of all refinement regions
            
        Returns:
            Optimized dictionary of refinement regions
        """
        # Estimate cell count impact
        estimated_cells = self._estimate_refined_cell_count(regions)
        
        max_cells = self.config.get('max_cells', 10000000)  # 10M default
        
        if estimated_cells > max_cells:
            self.logger.warning(f"Estimated cells ({estimated_cells}) exceeds limit ({max_cells})")
            
            # Prioritize regions by importance
            priority_order = ['gradP', 'yplus', 'vorticity', 'nearwall']
            
            filtered_regions = {}
            current_cells = self._get_current_cell_count()
            
            for priority in priority_order:
                for name, region in regions.items():
                    if priority in name:
                        filtered_regions[name] = region
                        current_cells *= 1.5  # Rough estimate
                        
                        if current_cells > max_cells * 0.9:
                            break
                
                if current_cells > max_cells * 0.9:
                    break
            
            regions = filtered_regions
        
        return regions
    
    def _run_postprocess(self, function: str, output_name: str):
        """
        Run OpenFOAM postProcess utility.
        
        Args:
            function: Function to calculate
            output_name: Output field name
        """
        cmd = ['postProcess', '-func', function, '-case', str(self.case_dir)]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.logger.info(f"Calculated {output_name}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to calculate {output_name}: {e.stderr}")
    
    def _get_latest_time(self) -> str:
        """Get latest time directory."""
        time_dirs = []
        
        for item in self.case_dir.iterdir():
            if item.is_dir():
                try:
                    time_val = float(item.name)
                    time_dirs.append((time_val, item.name))
                except ValueError:
                    continue
        
        if time_dirs:
            time_dirs.sort()
            return time_dirs[-1][1]
        
        return '0'
    
    def _check_field_exists(self, field_name: str, time_dir: str) -> bool:
        """Check if a field exists in the time directory."""
        field_path = self.case_dir / time_dir / field_name
        return field_path.exists()
    
    def _read_vector_field(self, field_path: Path) -> np.ndarray:
        """
        Read OpenFOAM vector field.
        
        Args:
            field_path: Path to field file
            
        Returns:
            Numpy array of vectors
        """
        # Simplified parser - in practice would use PyFoam or similar
        vectors = []
        
        with open(field_path, 'r') as f:
            lines = f.readlines()
        
        in_data = False
        for line in lines:
            if line.strip() == '(':
                in_data = True
                continue
            elif line.strip() == ')':
                break
            elif in_data and line.strip().startswith('('):
                # Parse vector (x y z)
                vec_str = line.strip()[1:-1]  # Remove parentheses
                vec = [float(x) for x in vec_str.split()]
                vectors.append(vec)
        
        return np.array(vectors)
    
    def _read_tensor_field(self, field_path: Path) -> np.ndarray:
        """
        Read OpenFOAM tensor field.
        
        Args:
            field_path: Path to field file
            
        Returns:
            Numpy array of tensors
        """
        # Simplified - would parse symmetric tensor (xx xy xz yy yz zz)
        tensors = []
        
        with open(field_path, 'r') as f:
            lines = f.readlines()
        
        in_data = False
        for line in lines:
            if line.strip() == '(':
                in_data = True
                continue
            elif line.strip() == ')':
                break
            elif in_data and line.strip().startswith('('):
                # Parse tensor components
                tensor_str = line.strip()[1:-1]
                components = [float(x) for x in tensor_str.split()]
                tensors.append(components)
        
        return np.array(tensors)
    
    def _tensor_magnitude(self, tensors: np.ndarray) -> np.ndarray:
        """
        Calculate magnitude of tensor field.
        
        Args:
            tensors: Array of tensors
            
        Returns:
            Array of magnitudes
        """
        # For symmetric tensor, compute Frobenius norm
        if tensors.shape[1] == 6:  # Symmetric tensor
            # xx, xy, xz, yy, yz, zz
            mag_sq = (tensors[:, 0]**2 + tensors[:, 3]**2 + tensors[:, 5]**2 +
                     2*(tensors[:, 1]**2 + tensors[:, 2]**2 + tensors[:, 4]**2))
            return np.sqrt(mag_sq)
        else:
            # Full tensor - use Frobenius norm
            return np.linalg.norm(tensors, axis=1)
    
    def _read_cell_centers(self) -> np.ndarray:
        """
        Read cell center coordinates.
        
        Returns:
            Array of cell center coordinates
        """
        # Use writeCellCentres utility or parse from mesh
        cmd = ['postProcess', '-func', 'writeCellCentres', '-case', str(self.case_dir)]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError:
            pass
        
        # Read cell centers
        latest_time = self._get_latest_time()
        cc_file = self.case_dir / latest_time / 'C'
        
        if cc_file.exists():
            return self._read_vector_field(cc_file)
        else:
            # Fallback - estimate from mesh
            return np.array([[0, 0, 0]])  # Placeholder
    
    def _get_current_cell_count(self) -> int:
        """Get current mesh cell count."""
        # Parse from checkMesh or constant/polyMesh
        return 100000  # Placeholder
    
    def _estimate_refined_cell_count(self, regions: Dict) -> int:
        """
        Estimate cell count after refinement.
        
        Args:
            regions: Refinement regions
            
        Returns:
            Estimated total cell count
        """
        current_cells = self._get_current_cell_count()
        
        # Rough estimate based on refinement levels
        multiplier = 1.0
        for region in regions.values():
            if 'levels' in region:
                max_level = max(level[1] for level in region['levels'])
                multiplier += 0.5 * (2**max_level - 1)  # Assume 50% of region gets refined
        
        return int(current_cells * multiplier)
    
    def export_refinement_dict(self, regions: Dict, output_file: str):
        """
        Export refinement regions to snappyHexMeshDict format.
        
        Args:
            regions: Dictionary of refinement regions
            output_file: Output file path
        """
        with open(output_file, 'w') as f:
            f.write("// Field-based refinement regions\n")
            f.write("refinementRegions\n")
            f.write("{\n")
            
            for name, region in regions.items():
                f.write(f"    {name}\n")
                f.write("    {\n")
                f.write(f"        mode {region['mode']};\n")
                
                if region['type'] == 'box':
                    f.write(f"        min ({' '.join(map(str, region['min']))});\n")
                    f.write(f"        max ({' '.join(map(str, region['max']))});\n")
                elif region['type'] == 'distance':
                    f.write(f"        surfaceName {region['surfaceName']};\n")
                
                f.write("        levels (\n")
                for level in region['levels']:
                    f.write(f"            ({level[0]} {level[1]})\n")
                f.write("        );\n")
                f.write("    }\n")
            
            f.write("}\n")
        
        self.logger.info(f"Exported refinement regions to {output_file}")
    
    def _simple_grid_clustering(self, points: np.ndarray) -> np.ndarray:
        """
        Simple grid-based clustering fallback when sklearn is not available.
        
        Args:
            points: Array of 3D points
            
        Returns:
            Array of cluster labels
        """
        if len(points) == 0:
            return np.array([])
        
        # Create a simple grid-based clustering
        grid_size = 0.005  # 5mm grid
        
        # Quantize points to grid
        grid_coords = np.floor(points / grid_size).astype(int)
        
        # Create unique labels for each grid cell
        labels = np.zeros(len(points), dtype=int)
        unique_grids = {}
        label_counter = 0
        
        for i, coord in enumerate(grid_coords):
            key = tuple(coord)
            if key not in unique_grids:
                unique_grids[key] = label_counter
                label_counter += 1
            labels[i] = unique_grids[key]
        
        return labels