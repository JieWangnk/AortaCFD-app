import os
import numpy as np
from stl import mesh as np_stl_mesh
from jinja2 import Environment, FileSystemLoader
from .utils.logger import Logger
from .utils.patch_processing import PatchProcessing
from .utils.mesh_constants import (
    RESOLUTION_PRESETS,
    DEFAULT_CELL_SIZE_MM,
    get_cell_size_from_preset,
    get_profile_info,
    get_available_presets
)

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

    Mesh Sizing Strategy (6-Priority Hierarchy):
        1. resolution_level: Simple presets (coarse/medium/fine) - RECOMMENDED
           - coarse/draft: 2.0mm (~100K-300K cells, 5-15 min)
           - medium/clinical: 1.0mm (~500K-1.5M cells, 30-90 min) ← START HERE
           - fine/publication: 0.5mm (~2M-5M cells, 2-4 hours)
           - ultra_fine: 0.25mm (~10M+ cells, 6-12 hours)
        2. target_cell_size_mm: Direct specification in mm (advanced users)
        3. blockmesh_resolution: Cells across diameter (geometry-based)
        4. cells_per_diameter: Same as #3, different naming
        5. refinement_levels: Legacy lookup table
        6. Fallback: 1.0mm default (only if none of above set)

    RECOMMENDED WORKFLOW:
        Set mesh.resolution_level = "medium" in your config for most cases.
        Only use lower priorities if you need custom values not covered by presets.
        See MESH_RESOLUTION_GUIDE.md for complete documentation.

    Default Fallback (Priority 6):
        - Value: 1.0mm (matches 'medium' profile for consistency)
        - Only used when no resolution parameters are configured
        - Triggers warning recommending explicit resolution_level configuration
        - Adult aorta: 20mm diameter → 20 cells across (adequate for RANS)
        - Small branches: ~5mm diameter → 5 cells (minimum for flow capture)

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

    def _cell_size_from_resolution_level(self, mesh_resolution: dict) -> tuple:
        """
        Priority 1: High-level resolution preset (coarse/medium/fine).

        Config: mesh.resolution_level = "coarse" | "medium" | "fine"
        Maps to predefined cell sizes:
            - coarse: 2.0mm (draft quality, ~100K-300K cells, 5-15 min)
            - medium: 1.0mm (clinical quality, ~500K-1.5M cells, 30-90 min)
            - fine: 0.5mm (publication quality, ~2M-5M cells, 2-4 hours)
            - ultra_fine: 0.25mm (mesh independence studies, ~10M+ cells)

        Aliases: draft=coarse, clinical=medium, publication=fine

        This is the RECOMMENDED method for most users.
        Advanced users can override with target_cell_size_mm.

        Returns:
            (cell_size_mm, source_description) or (None, None)
        """
        # Check both locations for backward compatibility
        level = self.mesh_settings.get('resolution_level')
        if level is None:
            level = mesh_resolution.get('resolution_level')

        if level is None:
            return None, None

        # Use centralized preset mapping from utils.mesh_constants
        cell_size = get_cell_size_from_preset(level)

        if cell_size is not None:
            return cell_size, f"mesh.resolution_level='{level}' → {cell_size}mm"
        else:
            available = ', '.join(get_available_presets())
            self.log.warning(
                f"Unknown resolution_level: '{level}'. "
                f"Available: {available}"
            )
            return None, None

    def _cell_size_from_target_mm(self, mesh_resolution: dict) -> tuple:
        """
        Priority 2: Direct cell size specification in millimeters.

        Config: mesh.mesh_resolution.target_cell_size_mm
        Formula: cell_size = target_cell_size_mm

        Use when you need a specific cell size not covered by presets.

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

    def _validate_resolution_config(self, mesh_resolution: dict) -> None:
        """
        Validate that only one resolution parameter is set.

        Raises warning if multiple parameters detected, as this can lead to confusion
        about which value will actually be used.
        """
        # Check what parameters are set
        set_params = []

        # Priority 1: resolution_level
        if self.mesh_settings.get('resolution_level') or mesh_resolution.get('resolution_level'):
            set_params.append(('resolution_level', 1))

        # Priority 2: target_cell_size_mm
        if mesh_resolution.get('target_cell_size_mm') is not None:
            set_params.append(('target_cell_size_mm', 2))

        # Priority 3: blockmesh_resolution
        if (mesh_resolution.get('blockmesh_resolution') is not None or
            mesh_resolution.get('blockMesh_resolution') is not None or
            self.mesh_settings.get('BLOCKMESH_SETTINGS', {}).get('resolution') is not None):
            set_params.append(('blockmesh_resolution', 3))

        # Priority 4: cells_per_diameter
        if mesh_resolution.get('cells_per_diameter') is not None:
            set_params.append(('cells_per_diameter', 4))

        # Priority 5: refinement_levels
        if (self.geom_settings.get('refinement_level') and
            self.mesh_settings.get('refinement_levels')):
            set_params.append(('refinement_levels', 5))

        # If multiple parameters set, warn user
        if len(set_params) > 1:
            params_str = ', '.join([f"{name} (priority {p})" for name, p in set_params])
            highest_priority = min(set_params, key=lambda x: x[1])

            self.log.warning(
                f"Multiple mesh resolution parameters detected: {params_str}. "
                f"Only '{highest_priority[0]}' (priority {highest_priority[1]}) will be used. "
                f"Recommendation: Set only ONE parameter to avoid confusion. "
                f"See MESH_RESOLUTION_GUIDE.md"
            )

    def _get_cell_size_strategies(self, mesh_resolution: dict):
        """
        Define cell size computation strategies in priority order.

        Returns list of (priority, method_name, method_function) tuples.
        This makes the fallback order explicit and easy to modify.

        Priority Order (highest to lowest):
            1. resolution_level - Simple preset (coarse/medium/fine) [RECOMMENDED]
            2. target_cell_size_mm - Explicit cell size in mm
            3. blockmesh_resolution - Cells across diameter (2*R/N formula)
            4. cells_per_diameter - Same as blockmesh_resolution (different naming)
            5. refinement_levels - Named quality levels with lookup table
            6. default_fallback - 1.0mm (matches 'medium' profile for consistency)
        """
        return [
            (1, "resolution_level", lambda: self._cell_size_from_resolution_level(mesh_resolution)),
            (2, "target_cell_size_mm", lambda: self._cell_size_from_target_mm(mesh_resolution)),
            (3, "blockmesh_resolution", lambda: self._cell_size_from_blockmesh_resolution(mesh_resolution)),
            (4, "cells_per_diameter", lambda: self._cell_size_from_cells_per_diameter(mesh_resolution)),
            (5, "refinement_levels", lambda: self._cell_size_from_refinement_level()),
            (6, "default_fallback", lambda: (DEFAULT_CELL_SIZE_MM, f"default fallback ({DEFAULT_CELL_SIZE_MM}mm, matches 'medium' profile)"))
        ]

    def _resolve_cell_size(self, mesh_resolution: dict) -> tuple:
        """
        Resolve cell size using priority cascade of strategies.

        This method encapsulates the entire fallback logic in one place.
        To change priority order, modify _get_cell_size_strategies().

        Returns:
            (cell_size_mm: float, source: str, priority: int)
        """
        strategies = self._get_cell_size_strategies(mesh_resolution)

        for priority, method_name, method_func in strategies:
            cell_size, source = method_func()

            if cell_size is not None:
                # Log which priority level was used
                if priority == 6:  # Default fallback
                    self.log.warning(
                        f"No mesh resolution parameters found (checked priorities 1-5). "
                        f"Using {cell_size}mm default. "
                        f"Recommendation: Set mesh.resolution_level = 'medium' in config. "
                        f"See MESH_RESOLUTION_GUIDE.md"
                    )
                return cell_size, source, priority

        # This should never happen (priority 6 always returns a value)
        raise RuntimeError(
            "Cell size resolution failed - default fallback did not return value. "
            "This is a code bug, please report."
        )

    def _calculate_blockmesh_cells(self, bounds: dict) -> dict:
        """
        Calculate blockMesh cell counts based on target cell size.

        MESH RESOLUTION PARAMETER HIERARCHY (checked in order):

        1. resolution_level (RECOMMENDED for most users)
           - Simple preset: mesh.resolution_level = "coarse" | "medium" | "fine"
           - Maps to: coarse=2mm, medium=1mm, fine=0.5mm, ultra_fine=0.25mm
           - Aliases: draft, clinical, publication
           - Example: mesh.resolution_level = "medium" → 1.0mm

        2. target_cell_size_mm (for advanced users)
           - Direct specification: mesh.mesh_resolution.target_cell_size_mm = 1.0
           - Use when you need a specific cell size not covered by presets

        3. blockmesh_resolution
           - Formula: cell_size = 2 * reference_radius / blockmesh_resolution
           - Config: mesh.mesh_resolution.blockmesh_resolution = 10
           - Requires: Valid reference radius from STL geometry

        4. cells_per_diameter
           - Formula: cell_size = 2 * reference_radius / cells_per_diameter
           - Config: mesh.mesh_resolution.cells_per_diameter = 8
           - Supports dict: {branch: 10, inlet: 8}
           - Requires: Valid reference radius

        5. refinement_levels (legacy)
           - Lookup: mesh.refinement_levels[geometry.refinement_level]
           - Example: refinement_level="medium" → 0.001m → 1.0mm

        6. Default fallback: 1.0mm
           - Used only if all above methods fail
           - Matches 'medium' profile for consistency

        RECOMMENDATION: Use resolution_level = "medium" for most simulations.
        Only use lower priorities if you need custom values.

        Implementation Notes:
            - Priority order defined in _get_cell_size_strategies()
            - Resolution logic in _resolve_cell_size()
            - Easy to add new strategies or change priority order

        Args:
            bounds: BlockMesh bounding box {min: ndarray, max: ndarray} in mm

        Returns:
            dict: Cell counts {x: int, y: int, z: int}
        """
        raw_mesh_resolution = self.mesh_settings.get('mesh_resolution', {})
        mesh_resolution = raw_mesh_resolution if isinstance(raw_mesh_resolution, dict) else {}

        # Validate configuration (warn if multiple parameters set)
        self._validate_resolution_config(mesh_resolution)

        # Resolve cell size using strategy cascade (encapsulated in separate method)
        cell_size_mm, source, priority = self._resolve_cell_size(mesh_resolution)

        # Validate result
        if cell_size_mm <= 0:
            raise ValueError(
                f"Computed cell size must be positive, got {cell_size_mm}mm. "
                f"Source: {source} (priority {priority})"
            )

        # Enhanced logging with profile information
        self.log.info(f"✓ Mesh Resolution Selected:")
        self.log.info(f"  Cell size: {cell_size_mm:.3f} mm")
        self.log.info(f"  Source: {source}")
        self.log.info(f"  Priority: {priority}/6 (1=highest)")

        # Add profile context if using resolution_level
        if priority == 1:
            level = self.mesh_settings.get('resolution_level') or mesh_resolution.get('resolution_level')
            profile = get_profile_info(level)
            if profile:
                self.log.info(f"  Profile '{level}': {profile['expected_cells']}, {profile['runtime']}")

        if self.reference_radius_mm:
            self.log.info(f"  Reference radius: {self.reference_radius_mm:.3f} mm (strategy: {self.geom_settings.get('reference_radius_strategy', 'min')})")

        # Calculate cell counts from resolved cell size
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