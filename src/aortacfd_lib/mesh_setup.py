import os
import numpy as np
from stl import mesh as np_stl_mesh
from jinja2 import Environment, FileSystemLoader
from .utils.logger import Logger
from .utils.patch_processing import PatchProcessing
from .utils.mesh_constants import (
    DEFAULT_CELLS_PER_DIAMETER,
    compute_cell_size,
    check_blockmesh_size
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
    """
    def __init__(self, config: dict, case_directory: str):
        self.config = config
        self.case_dir = case_directory
        self.log = Logger("mesh_setup").get_logger()

        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_path), trim_blocks=True, lstrip_blocks=True)

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

        IMPORTANT: This is an ABSOLUTE size applied uniformly to the background grid.
        It is NOT relative to any vessel diameter. The blockMesh will use this exact
        size in all three dimensions (x, y, z).

        This means:
        - A 20mm vessel gets: 20mm / target_mm cells across
        - A 5mm branch gets: 5mm / target_mm cells across

        Example: target_cell_size_mm = 1.0
        - 20mm aorta → 20 cells
        - 10mm branch → 10 cells
        - 5mm small branch → 5 cells

        Use for:
        - Mesh independence studies (vary by fixed ratios: 0.5mm, 0.7mm, 1.0mm, 1.4mm)
        - Matching literature: "0.8mm elements" → target_cell_size_mm = 0.8
        - When you know the exact element size requirement from prior validation

        Returns:
            (cell_size_mm, source_description) or (None, None)
        """
        target_mm = mesh_resolution.get('target_cell_size_mm')
        validated = self._coerce_positive(target_mm, "mesh.mesh_resolution.target_cell_size_mm")

        if validated is not None:
            return validated, f"target_cell_size_mm={validated:.3f}mm (absolute, uniform background grid)"
        return None, None

    def _cell_size_from_cells_per_diameter(self, mesh_resolution: dict) -> tuple:
        """
        Priority 2: Geometry-adaptive cells-per-diameter specification.

        Config: mesh.mesh_resolution.cells_per_diameter

        Formula: cell_size = reference_diameter / cells_per_diameter

        Use for:
        - Patient-specific simulations (auto-adapts to anatomy)
        - Consistent resolution across pediatric/adult cases
        - Flow-driven specifications (e.g., 10-15 cells for laminar)

        Requires: Valid reference geometry from STL analysis

        Returns:
            (cell_size_mm, source_description) or (None, None)
        """
        cells_per_diam_cfg = mesh_resolution.get('cells_per_diameter')
        cells_val = self._coerce_positive(cells_per_diam_cfg, "mesh.mesh_resolution.cells_per_diameter")

        if cells_val is not None:
            if self.reference_radius_mm is not None and self.reference_radius_mm > 0:
                D_ref = 2.0 * self.reference_radius_mm
                cell_size = compute_cell_size(cells_val, D_ref)
                return cell_size, f"cells_per_diameter={cells_val:.0f} (D_ref={D_ref:.2f}mm → {cell_size:.3f}mm)"
            else:
                self.log.error(
                    "cells_per_diameter requires valid reference geometry. "
                    "STL analysis failed to compute reference diameter. "
                    "Falling back to next priority."
                )
        return None, None

    def _cell_size_from_default_fallback(self) -> tuple:
        """
        Priority 3: Conservative fallback (only if user provides no specification).

        Uses DEFAULT_CELLS_PER_DIAMETER (10 cells/D) - conservative for initial
        exploration but NOT suitable for production simulations.

        IMPORTANT: This triggers a warning. Users should explicitly specify
        target_cell_size_mm OR cells_per_diameter for any real simulation.

        Returns:
            (cell_size_mm, source_description)
        """
        if self.reference_radius_mm is not None and self.reference_radius_mm > 0:
            D_ref = 2.0 * self.reference_radius_mm
            cell_size = compute_cell_size(DEFAULT_CELLS_PER_DIAMETER, D_ref)
            self.log.warning(
                "="*70 + "\n"
                "⚠️  NO MESH RESOLUTION SPECIFIED - Using conservative fallback\n"
                "="*70 + "\n"
                f"Defaulting to {DEFAULT_CELLS_PER_DIAMETER} cells/diameter → {cell_size:.3f}mm\n\n"
                "This is suitable for INITIAL GEOMETRY CHECK only.\n\n"
                "For production simulations, explicitly specify in config:\n"
                "  Option 1 (geometry-adaptive):\n"
                "    mesh.mesh_resolution.cells_per_diameter = 12  # or 15, 20, etc.\n\n"
                "  Option 2 (absolute control):\n"
                "    mesh.mesh_resolution.target_cell_size_mm = 0.8  # or other value\n\n"
                "Choose based on your mesh independence study requirements.\n"
                "="*70
            )
            return cell_size, f"FALLBACK: {DEFAULT_CELLS_PER_DIAMETER} cells/D (D={D_ref:.2f}mm → {cell_size:.3f}mm)"
        else:
            # Last resort if geometry completely unavailable
            fallback_mm = 2.0
            self.log.error(
                "CRITICAL: Cannot compute resolution - no geometry and no user specification.\n"
                f"Using arbitrary fallback: {fallback_mm}mm. Results are NOT reliable."
            )
            return fallback_mm, f"CRITICAL FALLBACK: {fallback_mm}mm (no geometry, no user spec)"

    def _validate_resolution_config(self, mesh_resolution: dict) -> None:
        """
        Validate that only one resolution parameter is set.

        Warns if multiple parameters detected, as this indicates configuration
        confusion about which value will be used.

        Also warns about deprecated parameters.
        """
        import warnings

        set_params = []

        # Check what parameters are set
        if mesh_resolution.get('target_cell_size_mm') is not None:
            set_params.append(('target_cell_size_mm', 1))

        if mesh_resolution.get('cells_per_diameter') is not None:
            set_params.append(('cells_per_diameter', 2))

        # Check for DEPRECATED parameters
        deprecated_params = []
        if mesh_resolution.get('resolution_level') is not None:
            deprecated_params.append('resolution_level')
        if mesh_resolution.get('blockmesh_resolution') is not None or mesh_resolution.get('blockMesh_resolution') is not None:
            deprecated_params.append('blockmesh_resolution / blockMesh_resolution')

        if deprecated_params:
            self.log.warning(
                f"\n"
                f"⚠️  DEPRECATION WARNING: Old mesh resolution parameters detected\n"
                f"─────────────────────────────────────────────────────────────────\n"
                f"The following parameters are DEPRECATED and will be IGNORED:\n"
                f"  {', '.join(deprecated_params)}\n"
                f"\n"
                f"These were removed in the new config system.\n"
                f"Please use ONE of the following instead:\n"
                f"  - 'cells_per_diameter' (recommended for patient-specific)\n"
                f"  - 'target_cell_size_mm' (for mesh independence studies)\n"
                f"\n"
                f"Example:\n"
                f'  "mesh": {{\n'
                f'    "mesh_resolution": {{\n'
                f'      "cells_per_diameter": 15\n'
                f'    }}\n'
                f'  }}\n'
            )
            warnings.warn(
                f"Mesh resolution parameters {deprecated_params} are deprecated. "
                f"Use 'cells_per_diameter' or 'target_cell_size_mm' instead.",
                DeprecationWarning,
                stacklevel=4
            )

        # Warn if multiple parameters set
        if len(set_params) > 1:
            params_str = ', '.join([f"{name} (priority {p})" for name, p in set_params])
            highest_priority = min(set_params, key=lambda x: x[1])

            self.log.warning(
                f"Multiple mesh resolution parameters detected: {params_str}\n"
                f"Only '{highest_priority[0]}' (priority {highest_priority[1]}) will be used.\n"
                f"Recommendation: Set only ONE parameter:\n"
                f"  - target_cell_size_mm (absolute control), OR\n"
                f"  - cells_per_diameter (geometry-adaptive)"
            )

    def _get_cell_size_strategies(self, mesh_resolution: dict):
        """
        Define cell size computation strategies in priority order.

        SIMPLIFIED 3-PRIORITY SYSTEM:
            1. target_cell_size_mm: Absolute size in mm (user-specified)
            2. cells_per_diameter: Geometry-adaptive (user-specified)
            3. default_fallback: Conservative 10 cells/D (triggers warning)

        Returns list of (priority, method_name, method_function) tuples.
        """
        return [
            (1, "target_cell_size_mm", lambda: self._cell_size_from_target_mm(mesh_resolution)),
            (2, "cells_per_diameter", lambda: self._cell_size_from_cells_per_diameter(mesh_resolution)),
            (3, "default_fallback", lambda: self._cell_size_from_default_fallback())
        ]

    def _resolve_cell_size(self, mesh_resolution: dict) -> tuple:
        """
        Resolve cell size using simplified 3-priority cascade.

        Priority order:
            1. target_cell_size_mm (explicit absolute)
            2. cells_per_diameter (geometry-adaptive)
            3. default_fallback (10 cells/D, triggers warning)

        Returns:
            (cell_size_mm: float, source: str, priority: int)
        """
        strategies = self._get_cell_size_strategies(mesh_resolution)

        for priority, method_name, method_func in strategies:
            cell_size, source = method_func()

            if cell_size is not None:
                return cell_size, source, priority

        # This should never happen (priority 3 fallback always returns a value)
        raise RuntimeError(
            "Cell size resolution failed - default fallback did not return value. "
            "This indicates a code bug."
        )

    def _calculate_blockmesh_cells(self, bounds: dict) -> dict:
        """
        Calculate blockMesh cell counts from user-specified resolution.

        SIMPLIFIED RESOLUTION SPECIFICATION (3 priorities):

        1. target_cell_size_mm (Priority 1)
           - Absolute control: mesh.mesh_resolution.target_cell_size_mm = 0.8
           - Use for: mesh independence studies, matching literature
           - Does NOT adapt to geometry

        2. cells_per_diameter (Priority 2)
           - Geometry-adaptive: mesh.mesh_resolution.cells_per_diameter = 12
           - Use for: patient-specific simulations, consistent resolution
           - Adapts to patient anatomy automatically

        3. Default fallback (Priority 3)
           - Conservative: 10 cells/diameter
           - Triggers WARNING - not suitable for production
           - User should explicitly specify one of above

        RECOMMENDATION: Always specify cells_per_diameter OR target_cell_size_mm.
        Do NOT rely on fallback for any real simulation.

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

        # Calculate cell counts from resolved cell size
        ranges = bounds['max'] - bounds['min']
        bbox_volume_mm3 = ranges[0] * ranges[1] * ranges[2]

        # Check if blockMesh will be too large (warn user, but proceed)
        size_check = check_blockmesh_size(cell_size_mm, bbox_volume_mm3)

        # Always use target resolution (no automatic changes)
        num_cells = np.maximum(1, np.round(ranges / cell_size_mm)).astype(int)
        total_bg_cells = num_cells[0] * num_cells[1] * num_cells[2]

        # ======================================================================
        # MESH SPECIFICATION REPORT (Publication-ready)
        # ======================================================================
        self.log.info("="*70)
        self.log.info("MESH SPECIFICATION")
        self.log.info("="*70)

        # Resolution source and priority
        self.log.info(f"Method: {source}")
        self.log.info(f"Priority: {priority}/3")

        # Geometry and cell size
        if self.reference_radius_mm:
            D_ref = 2.0 * self.reference_radius_mm
            actual_cpd = D_ref / cell_size_mm
            ref_strategy = self.geom_settings.get('reference_radius_strategy', 'min')
            self.log.info(f"Reference diameter: {D_ref:.2f} mm ({ref_strategy} vessel)")
            self.log.info(f"Cell size: {cell_size_mm:.3f} mm = {actual_cpd:.1f} cells/D")
        else:
            self.log.info(f"Cell size: {cell_size_mm:.3f} mm")
            self.log.warning("  No reference geometry available (cannot compute cells/diameter)")

        # BlockMesh size warning (if large)
        self.log.info("")
        if size_check['warning_level'] != 'ok':
            self.log.warning("="*70)
            self.log.warning("BLOCKMESH SIZE WARNING")
            self.log.warning("="*70)
            self.log.warning(size_check['message'])
            self.log.warning("="*70)
            self.log.info("")

        # Domain and grid
        self.log.info("")
        self.log.info(f"Domain bbox: {ranges[0]:.1f} × {ranges[1]:.1f} × {ranges[2]:.1f} mm")
        self.log.info(f"Background grid: {num_cells[0]} × {num_cells[1]} × {num_cells[2]} = {total_bg_cells:,} cells")

        # Branch resolution validation
        if self.outlet_radii and len(self.outlet_radii) > 0:
            valid_radii = [r for r in self.outlet_radii if r and r > 0]
            if valid_radii:
                min_branch_D = 2.0 * min(valid_radii)
                max_branch_D = 2.0 * max(valid_radii)
                cells_min = min_branch_D / cell_size_mm
                cells_max = max_branch_D / cell_size_mm

                self.log.info(f"Branch resolution range:")
                self.log.info(f"  Smallest: D={min_branch_D:.2f}mm → {cells_min:.1f} cells")
                self.log.info(f"  Largest:  D={max_branch_D:.2f}mm → {cells_max:.1f} cells")

                # Validation
                if cells_min < 6:
                    self.log.warning(
                        f"⚠️  Small branches under-resolved ({cells_min:.1f} < 6 cells)\n"
                        f"   Recommendation: Use cells_per_diameter={int(min_branch_D/cell_size_mm * 6/cells_min)} "
                        f"or target_cell_size_mm={min_branch_D/6:.3f}"
                    )

        # Expected final mesh
        refinement_levels = self.mesh_settings.get('SNAPPY_SETTINGS', {}).get('surfaceRefinementLevels', [1, 1])
        max_ref_level = max(refinement_levels) if refinement_levels else 1
        estimated_final = int(total_bg_cells * 0.25 * (1 + 0.3 * (8**max_ref_level - 1)))
        self.log.info(f"Expected final mesh: ~{estimated_final/1e6:.2f}M cells")

        self.log.info("="*70)

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
        """
        Generate snappyHexMeshDict with optional y+ based boundary layer calculation.

        If mesh.boundary_layers.target_yplus is specified in config, this will
        automatically calculate the appropriate finalLayerThickness to achieve
        the target y+ value using flow correlations.
        """
        # Check if y+ based layer sizing is requested
        boundary_layer_config = self.mesh_settings.get('boundary_layers', {})
        target_yplus = boundary_layer_config.get('target_yplus')

        # Make a mutable copy of snappy_settings for potential y+ override
        snappy_settings_with_yplus = dict(self.snappy_settings)

        if target_yplus is not None:
            self._apply_yplus_layer_sizing(target_yplus, boundary_layer_config, snappy_settings_with_yplus)
            # Override the config with calculated values
            modified_config = dict(self.config)
            modified_config['mesh'] = dict(self.config['mesh'])
            modified_config['mesh']['SNAPPY_SETTINGS'] = snappy_settings_with_yplus
        else:
            modified_config = self.config

        context = {
            "config": modified_config,
            "patches": self.all_patches,
            "wall_patch": self.wall_patch,
            "internal_point": internal_point
        }
        self._write_file_from_template("snappyHexMeshDict.tpl", os.path.join(self.case_dir, "system", "snappyHexMeshDict"), context)

    def _apply_yplus_layer_sizing(self, target_yplus: float, boundary_layer_config: dict, snappy_settings: dict):
        """
        Calculate and apply finalLayerThickness based on target y+ value.

        OVERRIDE BEHAVIOR:
        - If finalLayerThickness is explicitly set in boundary_layers or SNAPPY_SETTINGS,
          y+ estimation is SKIPPED and the user value is used directly.
        - If expansionRatio is explicitly set, it overrides the y+ calculation input.
        - This allows manual control when y+ estimation is not desired.

        Args:
            target_yplus: Target y+ value (e.g., 1.0 for RANS)
            boundary_layer_config: mesh.boundary_layers configuration
            snappy_settings: SNAPPY_SETTINGS dict to modify (in-place)
        """
        from .yplus_estimator import YPlusEstimator

        # CHECK FOR EXPLICIT OVERRIDES
        # If user provides layer thickness explicitly in boundary_layers config,
        # skip y+ calculation entirely and use their value.
        # NOTE: We only check boundary_layer_config (user's explicit input),
        # NOT snappy_settings (which may contain base config defaults)
        #
        # Support both OpenFOAM keywords:
        # - firstLayerThickness (wall-adjacent layer, CORRECT for y+ control)
        # - finalLayerThickness (outermost layer, legacy/compatibility)
        explicit_first_thickness = boundary_layer_config.get('firstLayerThickness')
        explicit_final_thickness = boundary_layer_config.get('finalLayerThickness')

        if explicit_first_thickness is not None:
            self.log.info("="*60)
            self.log.info("MANUAL BOUNDARY LAYER CONTROL (Y+ Estimation SKIPPED)")
            self.log.info("="*60)
            self.log.info(f"Using explicit firstLayerThickness: {explicit_first_thickness} mm")
            self.log.info(f"Target y+ ({target_yplus}) is for REFERENCE only - actual y+ will vary")
            self.log.info(f"Note: firstLayerThickness = wall-adjacent layer (correct for y+ control)")
            self.log.info("="*60)
            snappy_settings['firstLayerThickness'] = explicit_first_thickness
            snappy_settings['relativeSizes'] = False  # Assume absolute units
            return  # Skip y+ calculation
        elif explicit_final_thickness is not None:
            self.log.info("="*60)
            self.log.info("MANUAL BOUNDARY LAYER CONTROL (Y+ Estimation SKIPPED)")
            self.log.info("="*60)
            self.log.info(f"Using explicit finalLayerThickness: {explicit_final_thickness} mm")
            self.log.info(f"Target y+ ({target_yplus}) is for REFERENCE only - actual y+ will vary")
            self.log.warning(f"⚠️  finalLayerThickness = OUTERMOST layer (not wall-adjacent)")
            self.log.warning(f"⚠️  For y+ control, use firstLayerThickness instead!")
            self.log.info("="*60)
            snappy_settings['finalLayerThickness'] = explicit_final_thickness
            snappy_settings['relativeSizes'] = False  # Assume absolute units
            return  # Skip y+ calculation

        # Get fluid properties with defaults
        physics = self.config.get('physics', {})

        # Try blood_density first, fallback to defaults
        density = physics.get('blood_density')
        if density is None:
            density = 1060.0
            self.log.warning(
                "physics.blood_density not found in config, using default: 1060 kg/m³"
            )

        # Try blood_viscosity first, fallback to defaults
        viscosity = physics.get('blood_viscosity')
        if viscosity is None:
            viscosity = 0.004
            self.log.warning(
                "physics.blood_viscosity not found in config, using default: 0.004 Pa·s"
            )

        self.log.info(
            f"Y+ calculator using fluid properties: "
            f"ρ={density} kg/m³, μ={viscosity} Pa·s, ν={viscosity/density:.6e} m²/s"
        )

        # Get or estimate flow parameters
        estimation_method = boundary_layer_config.get('estimation_method', 'auto')

        # Use user-provided values if available, otherwise estimate
        if estimation_method == 'user_provided':
            char_velocity = boundary_layer_config.get('characteristic_velocity')
            char_length = boundary_layer_config.get('characteristic_length')

            if char_velocity is None or char_length is None:
                self.log.error(
                    "estimation_method='user_provided' requires both characteristic_velocity "
                    "and characteristic_length. Falling back to auto estimation."
                )
                estimation_method = 'auto'

        if estimation_method == 'auto':
            # Use typical aortic values or geometry-based estimates
            # Default: Use inlet diameter as characteristic length
            char_length = (2.0 * self.inlet_radius / 1000.0) if self.inlet_radius else 0.025  # Convert mm to m

            # Estimate velocity from typical cardiac output
            # Typical: ~5 L/min = 8.33e-5 m³/s, inlet area = π*r²
            if self.inlet_radius:
                inlet_area_m2 = np.pi * (self.inlet_radius / 1000.0) ** 2
                typical_flow_m3s = 8.33e-5  # 5 L/min
                char_velocity = typical_flow_m3s / inlet_area_m2
                self.log.info(
                    f"Auto-estimated characteristic velocity: {char_velocity:.3f} m/s "
                    f"(based on 5 L/min cardiac output and inlet radius {self.inlet_radius:.2f} mm)"
                )
            else:
                char_velocity = 0.5  # Fallback: typical aortic velocity
                self.log.warning("Using fallback velocity of 0.5 m/s (inlet radius unavailable)")

            # Allow user override
            if boundary_layer_config.get('characteristic_velocity') is not None:
                char_velocity = boundary_layer_config['characteristic_velocity']
                self.log.info(f"Using user-specified characteristic_velocity: {char_velocity} m/s")

            if boundary_layer_config.get('characteristic_length') is not None:
                char_length = boundary_layer_config['characteristic_length']
                self.log.info(f"Using user-specified characteristic_length: {char_length} m")

        # Get layer parameters
        n_layers = snappy_settings.get('addLayer', 5)
        expansion_ratio = snappy_settings.get('expansionRatio', 1.2)

        # Create estimator
        estimator = YPlusEstimator(
            density=density,
            viscosity=viscosity,
            flow_regime='auto'
        )

        # Calculate first layer thickness
        results = estimator.estimate_first_layer_thickness(
            target_yplus=target_yplus,
            mean_velocity=char_velocity,
            characteristic_length=char_length,
            n_layers=n_layers,
            expansion_ratio=expansion_ratio
        )

        # CRITICAL UNIT CONVERSION:
        # Y+ calculator returns thickness in METERS
        # BUT the mesh is in MILLIMETERS during generation (STL in mm, blockMesh in mm)
        # When relativeSizes=false, snappyHexMesh expects values in MESH UNITS (mm)
        # Therefore: convert meters to millimeters

        # IMPORTANT: Use firstLayerThickness (wall-adjacent layer) for y+ control
        # NOT finalLayerThickness (outermost layer)
        firstLayerThickness_meters = results['firstLayerThickness']
        firstLayerThickness_mm = firstLayerThickness_meters * 1000.0

        snappy_settings['firstLayerThickness'] = firstLayerThickness_mm

        # CRITICAL: Y+ calculator returns ABSOLUTE thickness
        # Must override relativeSizes to false so snappyHexMesh treats values as absolute (in mm)
        if snappy_settings.get('relativeSizes', True):
            self.log.warning(
                "Overriding relativeSizes from 'true' to 'false' - "
                "Y+ calculator provides absolute layer thickness (converted to mm for mesh units)"
            )
        snappy_settings['relativeSizes'] = False

        # Also adjust minThickness to absolute units in millimeters if needed
        min_thick = snappy_settings.get('minThickness', 0.1)
        if min_thick > 0.01:  # Likely relative (e.g., 0.1 = 10%)
            # Convert to small absolute value in millimeters (1 micron = 0.001 mm)
            snappy_settings['minThickness'] = 0.001  # 1 micron in mm
            self.log.warning(
                f"Adjusted minThickness from {min_thick} (relative) to {0.001:.3f} mm (absolute, 1 micron)"
            )

        # Print detailed report
        self.log.info("="*60)
        self.log.info("Y+ BASED BOUNDARY LAYER CALCULATION")
        self.log.info("="*60)
        self.log.info(f"Target y+:                  {target_yplus:.2f}")
        self.log.info(f"Characteristic velocity:    {char_velocity:.3f} m/s")
        self.log.info(f"Characteristic length:      {char_length*1000:.2f} mm")
        self.log.info(f"Reynolds number:            {results['reynolds_number']:.0f} ({results['flow_regime'].capitalize()})")
        self.log.info(f"Friction velocity (u_τ):    {results['friction_velocity']:.4f} m/s")
        self.log.info("-"*60)
        self.log.info(f"Calculated firstLayerThickness: {firstLayerThickness_mm:.6f} mm (converted from {firstLayerThickness_meters:.6e} m)")
        self.log.info(f"Number of layers:               {n_layers}")
        self.log.info(f"Expansion ratio:                {expansion_ratio}")
        self.log.info(f"Total BL thickness:             {results['total_layer_thickness']*1000:.4f} mm")
        self.log.info(f"Estimated y+:                   {results['estimated_yplus']:.2f}")
        self.log.info(f"Note: firstLayerThickness = wall-adjacent layer for y+ control")
        self.log.info(f"      Values in mm (mesh units) for snappyHexMesh with relativeSizes=false")
        self.log.info("="*60)

        # Validate settings
        solver_type = self.config.get('simulation_settings', {}).get('solver_type', 'laminar')
        validation = estimator.validate_settings(
            results['firstLayerThickness'],
            results['total_layer_thickness'],
            char_length,
            solver_type,
            results['reynolds_number']
        )

        if validation['warnings']:
            self.log.warning("⚠️  Y+ Estimation Warnings:")
            for warning in validation['warnings']:
                self.log.warning(f"  - {warning}")

        if validation['recommendations']:
            self.log.info("💡 Recommendations:")
            for rec in validation['recommendations']:
                self.log.info(f"  - {rec}")

        self.log.info("-"*60)
        self.log.info("Note: Verify actual y+ using post-processing after simulation.")
        self.log.info("="*60)
            
    def _write_surfacefeatures_dict(self):
        context = {
            "patches": self.all_patches,
            "snappy_settings": self.snappy_settings,
            "config": self.config
        }
        self._write_file_from_template("surfaceFeaturesDict.tpl", os.path.join(self.case_dir, "system", "surfaceFeaturesDict"), context)