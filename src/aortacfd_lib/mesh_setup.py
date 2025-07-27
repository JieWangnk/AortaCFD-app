import os
import numpy as np
from stl import mesh as np_stl_mesh
from jinja2 import Environment, FileSystemLoader
from .utils.logger import Logger
from .utils.patch_processing import PatchProcessing
from .murray_calculator import update_config_with_automatic_refinement

class GeometryAnalyzer:
    """
    Analyzes geometry and generates all mesh-related OpenFOAM dictionaries
    using a robust, centerline-path-aligned method to find locationInMesh.
    """
    def __init__(self, config: dict, case_directory: str, enable_automatic_refinement: bool = True):
        self.config = config
        self.case_dir = case_directory
        self.log = Logger("mesh_setup").get_logger()

        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_path), trim_blocks=True, lstrip_blocks=True)

        # Apply automatic refinement if enabled
        if enable_automatic_refinement:
            self.config = self._apply_automatic_refinement()

        self.geom_settings = self.config['geometry']
        self.mesh_settings = self.config['mesh']
        self.snappy_settings = self.mesh_settings['SNAPPY_SETTINGS']
        
        self.wall_patch = self.geom_settings['wall_keywords_ordered']
        self.inlet_patch = self.geom_settings['inlet_keywords_ordered']
        self.outlet_patches = self.geom_settings['outlet_keywords_ordered']
        self.all_patches = [self.wall_patch, self.inlet_patch] + self.outlet_patches
        
        self.tri_surface_path = os.path.join(self.case_dir, "constant", "triSurface")

        self.inlet_centroid = None
        self.inlet_radius = None
        self.inlet_normal = None
        self.outlet_centroids = []
        self._calculate_patch_properties()

    def _apply_automatic_refinement(self) -> dict:
        """
        Apply automatic refinement level calculation if enabled and STL files exist.
        
        Returns:
            Updated configuration with automatic refinement levels
        """
        try:
            # Check if automatic refinement is explicitly disabled
            if not self.config.get('mesh', {}).get('automatic_refinement', {}).get('enabled', True):
                self.log.info("Automatic refinement is disabled in configuration.")
                return self.config
            
            # Check if STL files exist
            tri_surface_path = os.path.join(self.case_dir, "constant", "triSurface")
            if not os.path.exists(tri_surface_path):
                self.log.warning(f"STL directory not found: {tri_surface_path}. Using manual refinement levels.")
                return self.config
            
            # Get cells per patch diameter targets from configuration or use defaults
            cells_per_patch_diameter = self.config.get('mesh', {}).get('cells_per_patch_diameter')
            if cells_per_patch_diameter is None:
                # Use defaults based on profile type if available
                profile_type = self.config.get('geometry', {}).get('refinement_level', 'medium')
                if profile_type == 'coarse':
                    cells_per_patch_diameter = {"coarse": 10, "medium": 15, "fine": 20}
                elif profile_type == 'fine':
                    cells_per_patch_diameter = {"coarse": 15, "medium": 20, "fine": 25}
                else:  # medium or default
                    cells_per_patch_diameter = {"coarse": 10, "medium": 15, "fine": 20}
            
            self.log.info(f"Applying automatic refinement with targets: {cells_per_patch_diameter}")
            
            # Apply automatic refinement
            updated_config = update_config_with_automatic_refinement(
                self.config, self.case_dir, cells_per_patch_diameter
            )
            
            self.log.info("Automatic refinement levels applied successfully.")
            return updated_config
            
        except Exception as e:
            self.log.warning(f"Could not apply automatic refinement: {e}")
            self.log.info("Falling back to manual refinement levels.")
            return self.config

    def _calculate_patch_properties(self):
        """Uses PatchProcessing to find the centroids of all inlet/outlet patches."""
        self.log.info("Analyzing inlet and outlet patch geometries...")
        scale_factor = self.geom_settings.get('scale_factor', 1e-3)
        
        # Process Inlet
        inlet_processor = PatchProcessing(self.tri_surface_path, self.inlet_patch)
        self.inlet_centroid, self.inlet_radius, self.inlet_normal = inlet_processor.calculate_inlet_center_radius()
        self.log.info(f"Inlet properties calculated - Center: {self.inlet_centroid}")
        
        # Process all Outlets in a loop
        for outlet_name in self.outlet_patches:
            outlet_processor = PatchProcessing(self.tri_surface_path, outlet_name)
            centroid, _, _ = outlet_processor.calculate_inlet_center_radius()
            self.outlet_centroids.append(centroid)

    def write_all_mesh_files(self):
        """A single public method to generate all necessary mesh files."""
        self.log.info("Generating all mesh dictionary files...")
        
        all_vertices = self._get_all_vertices()
        blockmesh_bounds = self._get_blockmesh_bounds(all_vertices)
        blockmesh_cells = self._calculate_blockmesh_cells(blockmesh_bounds)
        internal_point = self._get_internal_point_for_snappy()

        self._write_blockmesh_dict(blockmesh_bounds, blockmesh_cells)
        self._write_snappyhexmesh_dict(internal_point)
        self._write_surfacefeatures_dict()
        
        self.log.info("All mesh dictionary files generated successfully.")

    def _get_all_vertices(self) -> np.ndarray:
        """Extracts unique vertices from all STL files defined in the config."""
        all_verts = []
        for patch_name in self.all_patches:
            all_verts.append(self._extract_vertices_from_stl(f"{patch_name}.stl"))
        
        if not all_verts:
             self.log.error("No vertices extracted from any STL files.")
             raise ValueError("No vertices could be extracted.")
        
        return np.vstack(all_verts)

    def _extract_vertices_from_stl(self, stl_file_basename: str) -> np.ndarray:
        """Extracts unique vertices from a single STL file (NO SCALING - keep in mm)."""
        full_path = os.path.join(self.tri_surface_path, stl_file_basename)
        try:
            stl_mesh = np_stl_mesh.Mesh.from_file(full_path)
            
            # Keep vertices in original units (mm) to match STL files
            # Scaling will be applied later with transformPoints
            return np.unique(stl_mesh.vectors.reshape(-1, 3), axis=0)
        except Exception as e:
            raise RuntimeError(f"Error processing STL file {full_path}: {e}") from e

    def _get_blockmesh_bounds(self, all_vertices: np.ndarray) -> dict:
        """Calculates the expanded bounding box for blockMesh."""
        min_coords = np.min(all_vertices, axis=0)
        max_coords = np.max(all_vertices, axis=0)
        
        expansion_factor = self.snappy_settings.get("expansionFactor", 0.02)
        ranges = max_coords - min_coords
        
        min_expanded = min_coords - (expansion_factor * ranges)
        max_expanded = max_coords + (expansion_factor * ranges)
        
        self.log.info(f"BlockMesh bounds (mm, expanded): min({min_expanded}), max({max_expanded})")
        return {"min": min_expanded, "max": max_expanded}

    def _calculate_blockmesh_cells(self, bounds: dict) -> dict:
        """Calculates number of cells for blockMesh based on target cell size."""
        ref_level_key = self.geom_settings['refinement_level']
        # Cell size is in meters, but bounds are in mm, so convert
        cell_size_meters = self.mesh_settings['refinement_levels'][ref_level_key]
        cell_size_mm = cell_size_meters * 1000  # Convert m to mm
        
        ranges = bounds['max'] - bounds['min']
        num_cells = np.maximum(1, np.round(ranges / cell_size_mm)).astype(int)
        
        self.log.info(f"BlockMesh cells: Nx={num_cells[0]}, Ny={num_cells[1]}, Nz={num_cells[2]}")
        return {"x": num_cells[0], "y": num_cells[1], "z": num_cells[2]}

    def _get_internal_point_for_snappy(self) -> np.ndarray:
        """
        Calculates a point guaranteed to be inside the fluid domain using a
        robust, path-aligned normal vector.
        """
        if self.inlet_centroid is None or not self.outlet_centroids:
            raise ValueError("Inlet or outlet centroids have not been calculated.")
            
        # 1. Calculate the average position of all outlet centers (keep in mm)
        avg_outlet_centroid = np.mean(np.array(self.outlet_centroids), axis=0)
        inlet_centroid = self.inlet_centroid
        
        # 2. Define a vector for the general direction of flow
        path_vector = avg_outlet_centroid - inlet_centroid
        
        # 3. Align the geometric inlet normal with the path vector
        # The dot product tells us if they point in generally the same direction.
        if np.dot(self.inlet_normal, path_vector) < 0:
            # If the dot product is negative, they point opposite ways.
            # We flip the geometric normal to get a guaranteed inward direction.
            inward_normal = -self.inlet_normal
            self.log.info("Inlet normal was flipped to point inward along the aorta's path.")
        else:
            inward_normal = self.inlet_normal
            self.log.info("Inlet normal is already aligned inward along the aorta's path.")
            
        # 4. Move a small distance along this guaranteed inward normal (in mm)
        offset_distance = self.inlet_radius * 0.1  # 10% of the radius
        internal_point = inlet_centroid + (offset_distance * inward_normal)
        
        self.log.info(f"Robust locationInMesh calculated: {internal_point}")
        return internal_point

    def _write_file_from_template(self, template_name: str, output_path: str, context: dict):
        """Helper function to render a Jinja2 template and write the file."""
        template = self.jinja_env.get_template(template_name)
        content = template.render(context)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(content)
        self.log.info(f"Successfully wrote file: {os.path.basename(output_path)}")

    def _write_blockmesh_dict(self, bounds: dict, cells: dict):
        context = {"config": self.config, "bounds": bounds, "cells": cells}
        self._write_file_from_template("blockMeshDict.tpl", os.path.join(self.case_dir, "system", "blockMeshDict"), context)

    def _write_snappyhexmesh_dict(self, internal_point: np.ndarray):
        context = {
            "config": self.config,
            "patches": self.all_patches,
            "wall_patch": self.wall_patch,
            "internal_point": internal_point
        }
        self._write_file_from_template("snappyHexMeshDict.tpl", os.path.join(self.case_dir, "system", "snappyHexMeshDict"), context)
            
    def _write_surfacefeatures_dict(self):
        context = {
            "patches": self.all_patches,
            "snappy_settings": self.snappy_settings,
            "config": self.config
        }
        self._write_file_from_template("surfaceFeaturesDict.tpl", os.path.join(self.case_dir, "system", "surfaceFeaturesDict"), context)