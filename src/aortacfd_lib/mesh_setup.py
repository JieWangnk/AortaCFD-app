import os
import numpy as np
from stl import mesh as np_stl_mesh
from jinja2 import Environment, FileSystemLoader
from .utils.logger import Logger
from .utils.patch_processing import PatchProcessing

class GeometryAnalyzer:
    """
    Analyzes patient-specific aortic geometry and generates OpenFOAM mesh dictionaries.

    This class handles:
    - STL geometry analysis (areas, normals, centroids)
    - Automatic mesh sizing based on vessel dimensions
    - BlockMesh background grid generation
    - SnappyHexMesh refinement configuration
    - Internal point detection for mesh domain

    Physical Units:
        - Geometry: millimeters (mm) - clinical imaging standard
        - OpenFOAM output: meters (m) - SI units for CFD
        - Conversion: scale_factor (default 1e-3 for mm→m)

    Mesh Sizing Strategy:
        1. Reference radius: smallest vessel diameter (default: inlet or min outlet)
        2. Cell size: diameter / cells_per_diameter (profile-dependent)
        3. Fallback: 1.5mm default (validated for adult aorta: 10-30mm diameter)

    Default 1.5mm Rationale:
        - Adult aorta: 20-30mm diameter → 13-20 cells across (adequate for laminar)
        - Small branches: ~5mm diameter → 3-4 cells (minimum for flow capture)
        - Based on mesh independence studies (see docs/MESH_QUALITY_GUIDE.md)

    Args:
        config: Full configuration dictionary with 'geometry', 'mesh', 'physics' sections
        case_directory: OpenFOAM case path (e.g., output/patient1/run_*/openfoam)
        enable_automatic_refinement: If True, attempts Murray's law-based sizing (deprecated)
    """
    def __init__(self, config: dict, case_directory: str, enable_automatic_refinement: bool = True):
        self.config = config
        self.case_dir = case_directory
        self.log = Logger("mesh_setup").get_logger()

        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_path), trim_blocks=True, lstrip_blocks=True)

        # Record user preference but avoid modifying mesh settings automatically
        if enable_automatic_refinement and self.config.get('mesh', {}).get('automatic_refinement', {}).get('enabled', True):
            self.log.info("Automatic refinement request detected but Murray-based updates are disabled; proceeding with profile-defined mesh settings only.")

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
        self.outlet_radii = []
        self.reference_radius_mm = None
        self._calculate_patch_properties()

    def _calculate_patch_properties(self):
        """
        Calculate geometric properties of inlet/outlet patches from STL files.

        Computes:
            - Centroid coordinates (mm): geometric center of each patch
            - Equivalent radius (mm): sqrt(area/π) for circular cross-section approximation
            - Normal vector (unit): surface normal direction for flow orientation

        Units: All calculations in millimeters, converted to meters via scale_factor
        """
        self.log.info("Analyzing inlet and outlet patch geometries...")
        scale_factor = self.geom_settings.get('scale_factor', 1e-3)
        
        # Process Inlet
        inlet_processor = PatchProcessing(self.tri_surface_path, self.inlet_patch)
        self.inlet_centroid, self.inlet_radius, self.inlet_normal = inlet_processor.calculate_inlet_center_radius()
        self.log.info(f"Inlet properties calculated - Center: {self.inlet_centroid}")
        
        # Process all Outlets in a loop
        for outlet_name in self.outlet_patches:
            outlet_processor = PatchProcessing(self.tri_surface_path, outlet_name)
            centroid, radius, _ = outlet_processor.calculate_inlet_center_radius()
            self.outlet_centroids.append(centroid)
            self.outlet_radii.append(radius)

        self.reference_radius_mm = self._determine_reference_radius()
        if self.reference_radius_mm is not None:
            self.log.info(f"Reference branch radius for meshing: {self.reference_radius_mm:.3f} mm")
        else:
            self.log.warning("Could not determine reference radius from geometry; falling back to default cell sizing.")

    def _determine_reference_radius(self):
        """
        Determine reference radius for mesh sizing from vessel geometry.

        Strategy Options (config: geometry.reference_radius_strategy):
            - 'min' (default): Smallest vessel radius - ensures adequate resolution everywhere
            - 'inlet': Inlet radius only - for inlet-dominated flows
            - 'mean': Average of all vessels - balanced approach
            - 'max': Largest vessel - coarser overall mesh

        Rationale for 'min' default:
            Mesh quality is limited by worst-resolved region. Using minimum radius
            ensures small branches have sufficient cells while allowing coarser
            mesh in large vessels (adaptive refinement handles this automatically).

        Returns:
            float: Reference radius in millimeters, or None if no valid geometry
        """
        radii = []
        if self.inlet_radius and self.inlet_radius > 0:
            radii.append(self.inlet_radius)
        radii.extend([r for r in self.outlet_radii if r and r > 0])
        if not radii:
            return None

        strategy = self.geom_settings.get('reference_radius_strategy', 'min').lower()
        if strategy == 'inlet':
            return self.inlet_radius
        if strategy == 'mean':
            return float(np.mean(radii))
        if strategy == 'max':
            return max(radii)
        return min(radii)  # Default: conservative sizing based on smallest vessel

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

    def _coerce_positive(self, value, label: str):
        """
        Validate and coerce a value to positive float.

        Args:
            value: Value to validate (may be None, bool, numeric, or non-numeric)
            label: Parameter name for logging

        Returns:
            float or None: Validated positive float, or None if invalid
        """
        if value is None:
            return None
        if isinstance(value, bool):
            self.log.warning(f"Ignoring boolean {label}: {value}")
            return None
        try:
            coerced = float(value)
        except (TypeError, ValueError):
            self.log.warning(f"Ignoring non-numeric {label}: {value}")
            return None
        if coerced <= 0:
            self.log.warning(f"Ignoring non-positive {label}: {value}")
            return None
        return coerced

    def _cell_size_from_target_mm(self, mesh_resolution: dict) -> tuple:
        """
        Priority 1: Direct cell size specification in millimeters.

        Config: mesh.mesh_resolution.target_cell_size_mm
        Formula: cell_size = target_cell_size_mm

        Returns:
            (cell_size_mm, source_description) or (None, None)
        """
        target_mm = mesh_resolution.get('target_cell_size_mm')
        validated = self._coerce_positive(target_mm, "mesh.mesh_resolution.target_cell_size_mm")

        if validated is not None:
            return validated, "mesh.mesh_resolution.target_cell_size_mm (explicit)"
        return None, None

    def _cell_size_from_blockmesh_resolution(self, mesh_resolution: dict) -> tuple:
        """
        Priority 2: Cell size from blockMesh resolution parameter.

        Config: mesh.mesh_resolution.blockmesh_resolution (or blockMesh_resolution)
        Formula: cell_size = 2 * reference_radius / blockmesh_resolution

        Requires: Reference radius from geometry analysis

        Returns:
            (cell_size_mm, source_description) or (None, None)
        """
        # Try multiple naming conventions
        block_res = mesh_resolution.get('blockmesh_resolution')
        if block_res is None:
            block_res = mesh_resolution.get('blockMesh_resolution')
        if block_res is None:
            block_res = self.mesh_settings.get('BLOCKMESH_SETTINGS', {}).get('resolution')

        block_res_val = self._coerce_positive(block_res, "mesh.mesh_resolution.blockmesh_resolution")

        if block_res_val is not None:
            if self.reference_radius_mm is not None and self.reference_radius_mm > 0:
                cell_size = (2.0 * self.reference_radius_mm) / block_res_val
                return cell_size, f"2*R/{block_res_val:.1f} (ref_radius={self.reference_radius_mm:.2f}mm)"
            else:
                self.log.warning(
                    "blockmesh_resolution provided but reference radius unavailable; "
                    "skipping this method (check STL geometry)"
                )
        return None, None

    def _cell_size_from_cells_per_diameter(self, mesh_resolution: dict) -> tuple:
        """
        Priority 3: Cell size from cells-per-diameter specification.

        Config: mesh.mesh_resolution.cells_per_diameter (dict or scalar)
        Formula: cell_size = 2 * reference_radius / cells_per_diameter

        Supports:
            - cells_per_diameter: 10 (scalar)
            - cells_per_diameter: {branch: 10, inlet: 8} (dict)

        Returns:
            (cell_size_mm, source_description) or (None, None)
        """
        cells_per_diam_cfg = mesh_resolution.get('cells_per_diameter')
        cells_val = None

        if isinstance(cells_per_diam_cfg, dict):
            # Try 'branch' first, then 'inlet'
            for key in ('branch', 'inlet'):
                cells_val = self._coerce_positive(
                    cells_per_diam_cfg.get(key),
                    f"mesh.mesh_resolution.cells_per_diameter.{key}"
                )
                if cells_val is not None:
                    break
        else:
            cells_val = self._coerce_positive(
                cells_per_diam_cfg,
                "mesh.mesh_resolution.cells_per_diameter"
            )

        if cells_val is not None:
            if self.reference_radius_mm is not None and self.reference_radius_mm > 0:
                cell_size = (2.0 * self.reference_radius_mm) / cells_val
                return cell_size, f"2*R/{cells_val:.1f} cells (ref_radius={self.reference_radius_mm:.2f}mm)"
            else:
                self.log.warning(
                    "cells_per_diameter provided but reference radius unavailable; "
                    "skipping this method"
                )
        return None, None

    def _cell_size_from_refinement_level(self) -> tuple:
        """
        Priority 4: Cell size from named refinement level.

        Config:
            - geometry.refinement_level: "coarse" / "medium" / "fine"
            - mesh.refinement_levels: {coarse: 0.002, medium: 0.001, fine: 0.0005}

        Returns:
            (cell_size_mm, source_description) or (None, None)
        """
        ref_level_key = self.geom_settings.get('refinement_level')
        if not ref_level_key:
            return None, None

        refinement_levels = self.mesh_settings.get('refinement_levels', {})
        if not isinstance(refinement_levels, dict):
            return None, None

        level_meters = refinement_levels.get(ref_level_key)
        level_meters = self._coerce_positive(
            level_meters,
            f"mesh.refinement_levels['{ref_level_key}']"
        )

        if level_meters is not None:
            cell_size_mm = level_meters * 1000.0  # Convert m to mm
            return cell_size_mm, f"refinement_levels['{ref_level_key}']={level_meters}m"
        return None, None

    def _calculate_blockmesh_cells(self, bounds: dict) -> dict:
        """
        Calculate blockMesh cell counts based on target cell size.

        MESH RESOLUTION PARAMETER HIERARCHY (checked in order):

        1. target_cell_size_mm (highest priority)
           - Direct specification: mesh.mesh_resolution.target_cell_size_mm = 1.0
           - All other parameters ignored if this is set

        2. blockmesh_resolution
           - Formula: cell_size = 2 * reference_radius / blockmesh_resolution
           - Config: mesh.mesh_resolution.blockmesh_resolution = 10
           - Requires: Valid reference radius from STL geometry

        3. cells_per_diameter
           - Formula: cell_size = 2 * reference_radius / cells_per_diameter
           - Config: mesh.mesh_resolution.cells_per_diameter = 8
           - Supports dict: {branch: 10, inlet: 8}
           - Requires: Valid reference radius

        4. refinement_levels (lowest priority)
           - Lookup: mesh.refinement_levels[geometry.refinement_level]
           - Example: refinement_level="medium" → 0.001m → 1.0mm

        5. Default fallback: 1.5mm
           - Used only if all above methods fail
           - Validated for adult aorta (see REPRODUCIBILITY.md)

        RECOMMENDATION: Set only ONE parameter per simulation to avoid confusion.

        Args:
            bounds: BlockMesh bounding box {min: ndarray, max: ndarray} in mm

        Returns:
            dict: Cell counts {x: int, y: int, z: int}
        """
        raw_mesh_resolution = self.mesh_settings.get('mesh_resolution', {})
        mesh_resolution = raw_mesh_resolution if isinstance(raw_mesh_resolution, dict) else {}

        # Try each method in priority order
        cell_size_mm, source = self._cell_size_from_target_mm(mesh_resolution)

        if cell_size_mm is None:
            cell_size_mm, source = self._cell_size_from_blockmesh_resolution(mesh_resolution)

        if cell_size_mm is None:
            cell_size_mm, source = self._cell_size_from_cells_per_diameter(mesh_resolution)

        if cell_size_mm is None:
            cell_size_mm, source = self._cell_size_from_refinement_level()

        if cell_size_mm is None:
            cell_size_mm = 1.5
            source = "default fallback (no parameters set)"
            self.log.warning(
                "No mesh resolution parameters found; using 1.5mm default. "
                "See docs for available parameters."
            )

        # Validate
        if cell_size_mm <= 0:
            raise ValueError(
                f"Computed cell size must be positive, got {cell_size_mm}mm. "
                f"Check configuration for parameter: {source}"
            )

        # Log with clear source attribution
        self.log.info(f"✓ Target cell size: {cell_size_mm:.3f} mm")
        self.log.info(f"  Source: {source}")
        if self.reference_radius_mm:
            self.log.info(f"  Reference radius: {self.reference_radius_mm:.3f} mm (strategy: {self.geom_settings.get('reference_radius_strategy', 'min')})")

        # Calculate cell counts
        ranges = bounds['max'] - bounds['min']
        num_cells = np.maximum(1, np.round(ranges / cell_size_mm)).astype(int)

        self.log.info(f"✓ BlockMesh grid: {num_cells[0]} × {num_cells[1]} × {num_cells[2]} cells")
        self.log.info(f"  Domain size: {ranges[0]:.1f} × {ranges[1]:.1f} × {ranges[2]:.1f} mm")

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