"""Mesh setup and geometry analysis for OpenFOAM CFD simulations.

This module provides the GeometryAnalyzer class for analyzing patient-specific
aortic geometry and generating OpenFOAM mesh dictionaries (blockMeshDict,
snappyHexMeshDict, surfaceFeaturesDict).
"""

import os
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
from numpy.typing import NDArray
from stl import mesh as np_stl_mesh
from jinja2 import Environment, FileSystemLoader

from .utils.logger import Logger
from .utils.patch_processing import PatchProcessing
from .utils.mesh_constants import (
    DEFAULT_CELLS_PER_DIAMETER,
    MIN_CELLS_PER_DIAMETER,
    DEFAULT_SURFACE_REFINEMENT_LEVELS,
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
        IMPORTANT: STL files in constant/triSurface/ are PRE-SCALED to meters.
        Scaling happens during case setup (CreateCaseStructureTask), NOT here.
        All geometry values (centroids, radii, areas) are in SI units (meters).

        User-facing resolution parameters (target_cell_size_mm, cells_per_diameter)
        are still in mm for convenience - internally converted to meters.

    Mesh Sizing Strategy (3-Priority Hierarchy):
        1. target_cell_size_mm: Direct specification in mm (absolute control)
        2. cells_per_diameter: Cells across reference diameter (geometry-adaptive)
        3. Fallback: 10 cells/diameter (triggers warning)

    RECOMMENDED WORKFLOW:
        Use mesh.mesh_resolution.cells_per_diameter = 20 for geometry-adaptive sizing.
        Or mesh.mesh_resolution.target_cell_size_mm for absolute size control.

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
        self.inlet_radius = None  # in meters (STLs are pre-scaled)
        self.inlet_normal = None
        self.outlet_centroids = []
        self.outlet_radii = []  # in meters (STLs are pre-scaled)
        self.reference_radius_m = None  # in meters

        # Track if deprecation warning has been shown (prevent spam)
        self._deprecated_warning_shown = False

        # Resolve public mesh API (goal, span_target, layers, mode) into SNAPPY_SETTINGS
        from .utils.mesh_constants import resolve_mesh_config
        mesh_overrides = resolve_mesh_config(self.mesh_settings)
        if mesh_overrides:
            # Apply resolved values only where user hasn't explicitly set them
            for k, v in mesh_overrides.items():
                if k not in self.snappy_settings or k not in self.snappy_settings.get('_user_provided_keys', []):
                    self.snappy_settings[k] = v

        # Mesh strategy: 'adaptive_span' or 'legacy_surface'
        self.mesh_strategy = self.snappy_settings.get('mesh_strategy', 'legacy_surface')

        # Track whether user explicitly set surfaceRefinementLevels
        # (_user_provided_keys is tagged by ConfigBuilder before deep merge)
        user_keys = self.snappy_settings.get('_user_provided_keys', [])
        self._surface_levels_user_set = 'surfaceRefinementLevels' in user_keys

        # Process user-friendly config options into SNAPPY_SETTINGS
        self._process_mesh_config_options()
        self._calculate_patch_properties()

    def _process_mesh_config_options(self):
        """
        Process user-friendly mesh config options and merge into SNAPPY_SETTINGS.

        Handles:
        - surfaceRefinementLevels: [min, max] direct snappy levels
        - boundary_layers.* → addLayer, expansionRatio, finalLayerThickness, etc.

        This ensures the simplified config API works regardless of how the case is run.
        """
        # Set default surfaceRefinementLevels if not specified
        if 'surfaceRefinementLevels' not in self.snappy_settings:
            self.snappy_settings['surfaceRefinementLevels'] = DEFAULT_SURFACE_REFINEMENT_LEVELS
            self.log.info(f"Using default surfaceRefinementLevels: {DEFAULT_SURFACE_REFINEMENT_LEVELS}")
        else:
            levels = self.snappy_settings['surfaceRefinementLevels']
            self.log.info(f"surfaceRefinementLevels: {levels}")

        # Adaptive span: reduce surface refinement to support role (snapping only)
        # unless user explicitly set their own levels
        if self.mesh_strategy == 'adaptive_span' and not self._surface_levels_user_set:
            self.snappy_settings['surfaceRefinementLevels'] = [0, 1]
            self.log.info("adaptive_span: surface refinement reduced to [0, 1] (support role)")

        # Process boundary_layers config (accept both snake_case and camelCase)
        boundary_layers = self.mesh_settings.get('boundary_layers', {})

        if 'enabled' in boundary_layers:
            self.snappy_settings['addLayers'] = boundary_layers['enabled']

        num_layers = boundary_layers.get('num_layers') or boundary_layers.get('nSurfaceLayers')
        if num_layers is not None:
            self.snappy_settings['addLayer'] = num_layers

        expansion_ratio = boundary_layers.get('expansion_ratio') or boundary_layers.get('expansionRatio')
        if expansion_ratio is not None:
            self.snappy_settings['expansionRatio'] = expansion_ratio

        final_layer_thickness = boundary_layers.get('final_layer_thickness') or boundary_layers.get('finalLayerThickness')
        if final_layer_thickness is not None:
            self.snappy_settings['finalLayerThickness'] = final_layer_thickness

        min_thickness = boundary_layers.get('min_thickness') or boundary_layers.get('minThickness')
        if min_thickness is not None:
            self.snappy_settings['minThickness'] = min_thickness

        # Handle relativeSizes option (default: true)
        relative_sizes = boundary_layers.get('relativeSizes')
        if relative_sizes is not None:
            self.snappy_settings['relativeSizes'] = relative_sizes

        # Adapt nCellsBetweenLevels and layer thickness based on refinement level jump
        self._adapt_mesh_transitions()

    def _adapt_mesh_transitions(self):
        """
        Adapt nCellsBetweenLevels and layer thickness based on refinement level jump.

        Prevents the common failure mode where large refinement jumps create
        polyhedral transition cells with extreme volume ratios (8:1 per level,
        compounding to 64:1 or worse). Also adjusts boundary layer thickness
        so the last layer cell is not too small relative to the volume mesh.

        Rules:
        - nCellsBetweenLevels scales with refinement level jump (each level is 8:1 volume)
        - finalLayerThickness increases with max refinement to avoid layer-to-volume mismatch
        - Only applies if the user has NOT explicitly set these values
        """
        levels = self.snappy_settings.get('surfaceRefinementLevels', [1, 2])
        if not levels or len(levels) < 2:
            return

        level_jump = levels[1] - levels[0]
        max_level = levels[1]

        # --- nCellsBetweenLevels: scale with level jump ---
        # User explicitly set in mesh.SNAPPY_SETTINGS → respect it
        user_ncbl = self.mesh_settings.get('SNAPPY_SETTINGS', {}).get('nCellsBetweenLevels')
        if user_ncbl is None:
            # Auto-adapt: base 3, add 2 per extra level of jump
            recommended = 3 + max(0, level_jump - 1) * 2
            current = self.snappy_settings.get('nCellsBetweenLevels', 3)
            if recommended > current:
                self.snappy_settings['nCellsBetweenLevels'] = recommended
                self.log.info(
                    f"Auto-adapted nCellsBetweenLevels: {current} -> {recommended} "
                    f"(refinement jump {levels[0]}->{levels[1]}, volume ratio {8**level_jump}:1)"
                )

        # --- finalLayerThickness: increase with max refinement ---
        # Higher refinement = smaller surface cells = layers need to be thicker
        # relative to cell size so the last layer connects smoothly to volume mesh
        user_flt = (
            self.mesh_settings.get('boundary_layers', {}).get('final_layer_thickness')
            or self.mesh_settings.get('boundary_layers', {}).get('finalLayerThickness')
        )
        if user_flt is None:
            # Auto-adapt: base 0.4, add 0.1 per refinement level above 1
            base_flt = 0.4
            recommended_flt = min(0.8, base_flt + max(0, max_level - 1) * 0.1)
            current_flt = self.snappy_settings.get('finalLayerThickness', base_flt)
            if recommended_flt > current_flt:
                self.snappy_settings['finalLayerThickness'] = recommended_flt
                self.log.info(
                    f"Auto-adapted finalLayerThickness: {current_flt} -> {recommended_flt} "
                    f"(max refinement level {max_level})"
                )

    def _calculate_patch_properties(self):
        """
        Calculate geometric properties of inlet/outlet patches from STL files.

        Computes:
            - Centroid coordinates (m): geometric center of each patch
            - Equivalent radius (m): sqrt(area/π) for circular cross-section approximation
            - Normal vector (unit): surface normal direction for flow orientation

        Units: All values in meters (STLs are pre-scaled during case setup)
        """
        self.log.info("Analyzing inlet and outlet patch geometries...")

        # Process Inlet - STLs are already in meters, no scale_factor needed
        inlet_processor = PatchProcessing(self.tri_surface_path, self.inlet_patch)
        self.inlet_centroid, self.inlet_radius, self.inlet_normal = inlet_processor.calculate_inlet_center_radius()
        self.log.info(f"Inlet properties calculated - Center: {self.inlet_centroid}, Radius: {self.inlet_radius:.6f} m")

        # Process all Outlets in a loop
        for outlet_name in self.outlet_patches:
            outlet_processor = PatchProcessing(self.tri_surface_path, outlet_name)
            centroid, radius, _ = outlet_processor.calculate_inlet_center_radius()
            self.outlet_centroids.append(centroid)
            self.outlet_radii.append(radius)

        self.reference_radius_m = self._determine_reference_radius()
        if self.reference_radius_m is not None:
            # Display in mm for user convenience
            self.log.info(f"Reference branch radius for meshing: {self.reference_radius_m*1000:.3f} mm ({self.reference_radius_m:.6f} m)")
        else:
            self.log.warning("Could not determine reference radius from geometry; falling back to default cell sizing.")

    def _determine_reference_radius(self) -> Optional[float]:
        """
        Determine reference radius for mesh sizing from vessel geometry.

        Strategy Options (config: geometry.reference_radius_strategy):
            - 'max' (default): Largest vessel - uses main aorta diameter as reference
            - 'inlet': Inlet radius only - for inlet-dominated flows
            - 'mean': Average of all vessels - balanced approach
            - 'min': Smallest vessel radius - ensures adequate resolution everywhere

        Rationale for 'max' default:
            Uses the largest vessel (typically main aorta) as the reference diameter.
            This provides intuitive mesh sizing relative to the primary vessel.
            Small branches get refined via snappyHexMesh surface refinement.

        Returns:
            Reference radius in meters, or None if no valid geometry.
        """
        radii = []
        if self.inlet_radius and self.inlet_radius > 0:
            radii.append(self.inlet_radius)
        radii.extend([r for r in self.outlet_radii if r and r > 0])
        if not radii:
            return None

        strategy = self.geom_settings.get('reference_radius_strategy', 'max').lower()
        if strategy == 'inlet':
            return self.inlet_radius
        if strategy == 'mean':
            return float(np.mean(radii))
        if strategy == 'min':
            return min(radii)
        return max(radii)  # Default: use largest vessel diameter

    def write_all_mesh_files(self) -> None:
        """Generate all necessary mesh dictionary files for OpenFOAM."""
        self.log.info("Generating all mesh dictionary files...")

        all_vertices = self._get_all_vertices()
        blockmesh_bounds = self._get_blockmesh_bounds(all_vertices)
        blockmesh_cells = self._calculate_blockmesh_cells(blockmesh_bounds)
        internal_point = self._get_internal_point_for_snappy()

        self._write_blockmesh_dict(blockmesh_bounds, blockmesh_cells)
        self._write_snappyhexmesh_dict(internal_point)
        self._write_surfacefeatures_dict()

        self.log.info("All mesh dictionary files generated successfully.")

    def _get_all_vertices(self) -> NDArray[np.float64]:
        """Extract unique vertices from all STL files defined in the config."""
        all_verts = []
        for patch_name in self.all_patches:
            all_verts.append(self._extract_vertices_from_stl(f"{patch_name}.stl"))
        
        if not all_verts:
             self.log.error("No vertices extracted from any STL files.")
             raise ValueError("No vertices could be extracted.")
        
        return np.vstack(all_verts)

    def _extract_vertices_from_stl(self, stl_file_basename: str) -> NDArray[np.float64]:
        """Extract unique vertices from a single STL file (already in meters)."""
        full_path = os.path.join(self.tri_surface_path, stl_file_basename)
        try:
            stl_mesh = np_stl_mesh.Mesh.from_file(full_path)

            # STL files in constant/triSurface/ are PRE-SCALED to meters
            # during case setup (CreateCaseStructureTask)
            return np.unique(stl_mesh.vectors.reshape(-1, 3), axis=0)
        except Exception as e:
            raise RuntimeError(f"Error processing STL file {full_path}: {e}") from e

    def _get_blockmesh_bounds(self, all_vertices: NDArray[np.float64]) -> Dict[str, NDArray[np.float64]]:
        """Calculate the expanded bounding box for blockMesh (in meters)."""
        min_coords = np.min(all_vertices, axis=0)
        max_coords = np.max(all_vertices, axis=0)

        expansion_factor = self.snappy_settings.get("expansionFactor", 0.01)
        ranges = max_coords - min_coords

        min_expanded = min_coords - (expansion_factor * ranges)
        max_expanded = max_coords + (expansion_factor * ranges)

        # Display in both meters and mm for user clarity
        self.log.info(f"BlockMesh bounds (m, expanded): min({min_expanded}), max({max_expanded})")
        self.log.info(f"BlockMesh bounds (mm): min({min_expanded*1000}), max({max_expanded*1000})")
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
            (cell_size_m, source_description) or (None, None)
            Note: User specifies in mm, returned in meters for internal use
        """
        target_mm = mesh_resolution.get('target_cell_size_mm')
        validated = self._coerce_positive(target_mm, "mesh.mesh_resolution.target_cell_size_mm")

        if validated is not None:
            # Convert mm to meters for internal use
            cell_size_m = validated / 1000.0
            return cell_size_m, f"target_cell_size_mm={validated:.3f}mm (absolute, uniform background grid)"
        return None, None

    def _cell_size_from_cells_per_diameter(self, mesh_resolution: dict) -> tuple:
        """
        Priority 2: Geometry-adaptive cells-per-diameter specification.

        Config: mesh.mesh_resolution.cells_per_diameter

        Formula: cell_size = reference_diameter / cells_per_diameter

        Recommended values:
        - 10-12: Initial exploration, fast iteration
        - 15-20: Standard simulation, balanced accuracy/cost
        - 25-30: High resolution, mesh-independent solutions

        Use for:
        - Patient-specific simulations (auto-adapts to anatomy)
        - Consistent resolution across pediatric/adult cases
        - Flow-driven specifications (e.g., 10-15 cells for laminar)

        Requires: Valid reference geometry from STL analysis

        Returns:
            (cell_size_m, source_description) or (None, None)
        """
        cells_per_diam_cfg = mesh_resolution.get('cells_per_diameter')
        cells_val = self._coerce_positive(cells_per_diam_cfg, "mesh.mesh_resolution.cells_per_diameter")

        if cells_val is not None:
            # Validate minimum cells per diameter
            if cells_val < MIN_CELLS_PER_DIAMETER:
                self.log.warning(
                    f"cells_per_diameter={cells_val:.0f} is below minimum ({MIN_CELLS_PER_DIAMETER}). "
                    f"Results may be unreliable. Consider using at least {MIN_CELLS_PER_DIAMETER} cells/diameter."
                )

            if self.reference_radius_m is not None and self.reference_radius_m > 0:
                D_ref_m = 2.0 * self.reference_radius_m
                D_ref_mm = D_ref_m * 1000  # For display
                cell_size_m = D_ref_m / cells_val
                cell_size_mm = cell_size_m * 1000  # For display
                return cell_size_m, f"cells_per_diameter={cells_val:.0f} (D_ref={D_ref_mm:.2f}mm → {cell_size_mm:.3f}mm)"
            else:
                self.log.error(
                    "cells_per_diameter requires valid reference geometry. "
                    "STL analysis failed to compute reference diameter. "
                    "Falling back to next priority."
                )
        return None, None

    def _cell_size_from_default_fallback(self) -> tuple:
        """
        Priority 3: Conservative fallback OR span-based auto-calculation.

        For SPAN REFINEMENT (v2.0):
            CORRECTED calculation based on how snappyHexMesh actually works:

            Key insight (from systematic testing and OpenFOAM docs):
            - insideSpan mode uses ONLY span_level for internal volume refinement
            - Surface refinement is INDEPENDENT and only affects near-surface cells
            - cellsAcrossSpan is the TARGET, span_level LIMITS max refinement

            The correct formula is:
              achievable_cells = blockMesh_cells × 2^span_level
              blockMesh_cells = cells_across_span / 2^span_level

            NOT the old (incorrect) formula that combined surface + span levels.

            This ensures cellsAcrossSpan actually achieves the target resolution.

        For LEGACY (no span refinement):
            Uses DEFAULT_CELLS_PER_DIAMETER (10 cells/D) - triggers warning.

        Returns:
            (cell_size_m, source_description)
        """
        # Check if span refinement is enabled (v2.0 primary method)
        span_refinement_enabled = self.snappy_settings.get('span_refinement_enabled', False)
        cells_across_span = self.snappy_settings.get('cells_across_span', 0)

        # Strategy-driven: adaptive_span auto-enables span when no explicit resolution given
        if self.mesh_strategy == 'adaptive_span' and not span_refinement_enabled and cells_across_span <= 0:
            span_refinement_enabled = True
            cells_across_span = self.snappy_settings.get('default_cells_across_span', 12)
            self.snappy_settings['span_refinement_enabled'] = True
            self.snappy_settings['cells_across_span'] = cells_across_span
            self.log.info(f"adaptive_span: auto-enabled span refinement with target={cells_across_span}")

        if self.reference_radius_m is not None and self.reference_radius_m > 0:
            D_ref_m = 2.0 * self.reference_radius_m
            D_ref_mm = D_ref_m * 1000  # For display

            if span_refinement_enabled and cells_across_span > 0:
                # Get refinement levels from config (surface is logged but NOT used for blockMesh calc)
                surface_levels = self.snappy_settings.get('surfaceRefinementLevels', [1, 2])
                surface_level = surface_levels[1] if len(surface_levels) > 1 else surface_levels[0]

                # span_refinement_level: if not set, auto-calculate
                span_level = self.snappy_settings.get('span_refinement_level', None)

                # CORRECTED calculation:
                # - insideSpan mode uses ONLY span_level for internal refinement
                # - achievable = blockMesh × 2^span_level
                # - Surface refinement is SEPARATE (affects near-surface cells only)
                #
                # Reference: OpenFOAM User Guide & systematic parameter study

                # Minimum blockMesh = 4 cells/D (practical limit for quality mesh)
                MIN_BLOCKMESH = 4

                if span_level is not None:
                    # User specified span_refinement_level - calculate blockMesh directly
                    # ONLY use span_level (NOT surface_level) for insideSpan calculation
                    span_multiplier = 2 ** span_level
                    blockmesh_cells_per_d = max(MIN_BLOCKMESH, int(np.ceil(cells_across_span / span_multiplier)))
                    achievable_cells = blockmesh_cells_per_d * span_multiplier

                    self.log.info(
                        f"SPAN REFINEMENT: Corrected blockMesh calculation\n"
                        f"  Target: {cells_across_span} cells across span\n"
                        f"  Span refinement level: {span_level} (2^{span_level} = {span_multiplier}x)\n"
                        f"  Surface refinement level: {surface_level} (separate, near-surface only)\n"
                        f"  BlockMesh: {blockmesh_cells_per_d} cells/D\n"
                        f"  Achievable: {blockmesh_cells_per_d} × {span_multiplier} = {achievable_cells} cells across span"
                    )

                    # Warn if target cannot be achieved
                    if achievable_cells < cells_across_span:
                        self.log.warning(
                            f"  ⚠️  Target {cells_across_span} not fully achievable with span_level={span_level}\n"
                            f"      Maximum achievable: {achievable_cells} cells\n"
                            f"      Consider increasing span_refinement_level to {span_level + 1}"
                        )
                else:
                    # Auto-calculate optimal span_level using shared planner
                    from .utils.mesh_constants import plan_span_background

                    plan = plan_span_background(cells_across_span)
                    blockmesh_cells_per_d = plan['background_cpd']
                    span_level = plan['span_level']
                    span_multiplier = 2 ** span_level
                    achievable_cells = plan['theoretical_cells_across']

                    if plan['warning']:
                        self.log.warning(plan['warning'])

                    self.log.info(
                        f"SPAN REFINEMENT: Planner output\n"
                        f"  Target: {cells_across_span} cells across span\n"
                        f"  Background: {blockmesh_cells_per_d} cells/D\n"
                        f"  Span level: {span_level} (2^{span_level} = {span_multiplier}x)\n"
                        f"  Surface refinement level: {surface_level} (separate, near-surface only)\n"
                        f"  Theoretical: {achievable_cells} cells across span"
                    )

                cell_size_m = D_ref_m / blockmesh_cells_per_d
                cell_size_mm = cell_size_m * 1000

                return cell_size_m, f"SPAN_REFINEMENT: blockMesh={blockmesh_cells_per_d} cells/D, span_level={span_level}, target={cells_across_span}, achievable={achievable_cells}"
            else:
                # Legacy warning for when span refinement is NOT used
                cell_size_m = D_ref_m / DEFAULT_CELLS_PER_DIAMETER
                cell_size_mm = cell_size_m * 1000
                # Print warning as separate lines to avoid logging issues
                self.log.warning("=" * 70)
                self.log.warning("NO MESH RESOLUTION SPECIFIED - Using conservative fallback")
                self.log.warning("=" * 70)
                self.log.warning(f"Defaulting to {DEFAULT_CELLS_PER_DIAMETER} cells/diameter -> {cell_size_mm:.3f}mm")
                self.log.warning("")
                self.log.warning("This is suitable for INITIAL GEOMETRY CHECK only.")
                self.log.warning("")
                self.log.warning("For production simulations, explicitly specify in config:")
                self.log.warning("  Option 1 (RECOMMENDED v2.0 - span-based):")
                self.log.warning("    mesh.SNAPPY_SETTINGS.span_refinement_enabled = true")
                self.log.warning("    mesh.SNAPPY_SETTINGS.cells_across_span = 20  # or 15, 25, 30")
                self.log.warning("")
                self.log.warning("  Option 2 (legacy - geometry-adaptive):")
                self.log.warning("    mesh.mesh_resolution.cells_per_diameter = 20")
                self.log.warning("")
                self.log.warning("  Option 3 (legacy - absolute control):")
                self.log.warning("    mesh.mesh_resolution.target_cell_size_mm = 0.8")
                self.log.warning("=" * 70)
                return cell_size_m, f"FALLBACK: {DEFAULT_CELLS_PER_DIAMETER} cells/D (D={D_ref_mm:.2f}mm -> {cell_size_mm:.3f}mm)"
        else:
            # Last resort if geometry completely unavailable
            fallback_mm = 2.0
            fallback_m = fallback_mm / 1000.0
            self.log.error(
                "CRITICAL: Cannot compute resolution - no geometry and no user specification.\n"
                f"Using arbitrary fallback: {fallback_mm}mm. Results are NOT reliable."
            )
            return fallback_m, f"CRITICAL FALLBACK: {fallback_mm}mm (no geometry, no user spec)"

    def _validate_resolution_config(self, mesh_resolution: dict) -> None:
        """
        Validate mesh resolution configuration.

        v2.0: Warns about deprecated legacy methods.
        Recommends cells_across_span as primary method.
        """
        has_target_mm = mesh_resolution.get('target_cell_size_mm') is not None
        has_cells_per_d = mesh_resolution.get('cells_per_diameter') is not None
        has_span_refinement = self.snappy_settings.get('span_refinement_enabled', False)

        # v2.0: Deprecation warning for legacy methods (show once only)
        if (has_target_mm or has_cells_per_d) and not self._deprecated_warning_shown:
            self._deprecated_warning_shown = True
            legacy_method = "target_cell_size_mm" if has_target_mm else "cells_per_diameter"
            self.log.warning("=" * 70)
            self.log.warning("DEPRECATED MESH RESOLUTION METHOD (v1.0)")
            self.log.warning("=" * 70)
            self.log.warning(f"Using legacy method: {legacy_method}")
            self.log.warning("")
            self.log.warning("v2.0 RECOMMENDED: Use cells_across_span instead:")
            self.log.warning('  "mesh": {')
            self.log.warning('    "SNAPPY_SETTINGS": {')
            self.log.warning('      "span_refinement_enabled": true,')
            self.log.warning('      "cells_across_span": 20')
            self.log.warning('    }')
            self.log.warning('  }')
            self.log.warning("")
            self.log.warning("Advantages of cells_across_span:")
            self.log.warning("  - Guarantees minimum cells across diameter everywhere")
            self.log.warning("  - Automatically handles coarctations and small branches")
            self.log.warning("  - More robust for complex geometries")
            self.log.warning("=" * 70)

        # Warn if both legacy parameters are set (conflict)
        if has_target_mm and has_cells_per_d:
            self.log.warning("=" * 70)
            self.log.warning("CONFLICTING MESH RESOLUTION PARAMETERS")
            self.log.warning("=" * 70)
            self.log.warning("Both target_cell_size_mm and cells_per_diameter are set.")
            self.log.warning(f"Using target_cell_size_mm={mesh_resolution['target_cell_size_mm']}mm (Priority 1)")
            self.log.warning(f"Ignoring cells_per_diameter={mesh_resolution['cells_per_diameter']}")
            self.log.warning("=" * 70)

    def _get_cell_size_strategies(self, mesh_resolution: dict):
        """
        Define cell size computation strategies in priority order.

        3-PRIORITY SYSTEM:
            1. target_cell_size_mm: Absolute size in mm (user-specified)
            2. cells_per_diameter: Geometry-adaptive (RECOMMENDED)
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
        Resolve cell size using 3-priority cascade.

        Priority order:
            1. target_cell_size_mm (explicit absolute)
            2. cells_per_diameter (geometry-adaptive, RECOMMENDED)
            3. default_fallback (10 cells/D, triggers warning)

        Returns:
            (cell_size_m: float, source: str, priority: int)
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

        RESOLUTION SPECIFICATION (3 priorities):

        1. target_cell_size_mm (Priority 1)
           - Absolute control: mesh.mesh_resolution.target_cell_size_mm = 0.8
           - Use for: mesh independence studies, matching literature
           - Does NOT adapt to geometry

        2. cells_per_diameter (Priority 2, RECOMMENDED)
           - Geometry-adaptive: mesh.mesh_resolution.cells_per_diameter = 20
           - Guidelines: 10-12 (coarse), 15-20 (standard), 25-30 (fine)
           - Adapts to patient anatomy automatically

        3. Default fallback (Priority 3)
           - Conservative: 10 cells/diameter
           - Triggers WARNING - not suitable for production
           - User should explicitly specify one of above

        RECOMMENDATION: Use cells_per_diameter for geometry-adaptive sizing.

        Args:
            bounds: BlockMesh bounding box {min: ndarray, max: ndarray} in meters

        Returns:
            dict: Cell counts {x: int, y: int, z: int}
        """
        raw_mesh_resolution = self.mesh_settings.get('mesh_resolution', {})
        mesh_resolution = raw_mesh_resolution if isinstance(raw_mesh_resolution, dict) else {}

        # Migration: support top-level cells_per_diameter (common in user configs)
        if 'cells_per_diameter' not in mesh_resolution:
            top_level_cpd = self.mesh_settings.get('cells_per_diameter')
            if top_level_cpd is not None:
                mesh_resolution['cells_per_diameter'] = top_level_cpd

        # Validate configuration (warn if multiple parameters set)
        self._validate_resolution_config(mesh_resolution)

        # Resolve cell size using strategy cascade (returns meters)
        cell_size_m, source, priority = self._resolve_cell_size(mesh_resolution)
        cell_size_mm = cell_size_m * 1000  # For display

        # Validate result
        if cell_size_m <= 0:
            raise ValueError(
                f"Computed cell size must be positive, got {cell_size_mm}mm. "
                f"Source: {source} (priority {priority})"
            )

        # Calculate cell counts from resolved cell size (both in meters)
        ranges = bounds['max'] - bounds['min']
        ranges_mm = ranges * 1000  # For display
        bbox_volume_mm3 = ranges_mm[0] * ranges_mm[1] * ranges_mm[2]

        # Check if blockMesh will be too large (warn user, but proceed)
        size_check = check_blockmesh_size(cell_size_mm, bbox_volume_mm3)

        # Always use target resolution (no automatic changes)
        num_cells = np.maximum(1, np.round(ranges / cell_size_m)).astype(int)
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
        if self.reference_radius_m:
            D_ref_mm = 2.0 * self.reference_radius_m * 1000
            actual_cpd = D_ref_mm / cell_size_mm
            ref_strategy = self.geom_settings.get('reference_radius_strategy', 'min')
            self.log.info(f"Reference diameter: {D_ref_mm:.2f} mm ({ref_strategy} vessel)")
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
        self.log.info(f"Domain bbox: {ranges_mm[0]:.1f} × {ranges_mm[1]:.1f} × {ranges_mm[2]:.1f} mm")
        self.log.info(f"Background grid: {num_cells[0]} × {num_cells[1]} × {num_cells[2]} = {total_bg_cells:,} cells")

        # Branch resolution validation
        if self.outlet_radii and len(self.outlet_radii) > 0:
            valid_radii = [r for r in self.outlet_radii if r and r > 0]
            if valid_radii:
                min_branch_D_mm = 2.0 * min(valid_radii) * 1000
                max_branch_D_mm = 2.0 * max(valid_radii) * 1000
                cells_min = min_branch_D_mm / cell_size_mm
                cells_max = max_branch_D_mm / cell_size_mm

                self.log.info(f"Branch resolution range:")
                self.log.info(f"  Smallest: D={min_branch_D_mm:.2f}mm → {cells_min:.1f} cells")
                self.log.info(f"  Largest:  D={max_branch_D_mm:.2f}mm → {cells_max:.1f} cells")

                # Validation
                if cells_min < 6:
                    self.log.warning(
                        f"⚠️  Small branches under-resolved ({cells_min:.1f} < 6 cells)\n"
                        f"   Recommendation: Use cells_per_diameter={int(min_branch_D_mm/cell_size_mm * 6/cells_min)} "
                        f"or target_cell_size_mm={min_branch_D_mm/6:.3f}"
                    )

        # Surface refinement level info
        snappy_levels = self.snappy_settings.get('surfaceRefinementLevels', DEFAULT_SURFACE_REFINEMENT_LEVELS)
        surface_cell_size_mm = cell_size_mm / (2 ** snappy_levels[1])  # After max refinement
        self.log.info("")
        self.log.info(f"surfaceRefinementLevels: {snappy_levels}")
        self.log.info(f"  Base cell size: {cell_size_mm:.3f} mm")
        self.log.info(f"  Surface cell size: {surface_cell_size_mm:.3f} mm (after {snappy_levels[1]}× subdivision)")

        # Expected final mesh (geometry-aware estimation)
        max_ref_level = max(snappy_levels) if snappy_levels else 1
        fluid_fraction = self._estimate_fluid_fraction()
        n_bl_layers = self.snappy_settings.get('addLayer', 5)
        bl_enabled = self.snappy_settings.get('addLayers', True)

        # Interior cells: background cells inside geometry
        interior_cells = total_bg_cells * fluid_fraction
        # Surface refinement adds cells in a shell around walls
        # Each refinement level doubles resolution; refined region ~2 cell layers deep
        surface_multiplier = 1.0 + 0.15 * (4**max_ref_level - 1)
        refined_cells = interior_cells * surface_multiplier
        # Boundary layers add prismatic cells proportional to existing surface cells
        bl_multiplier = 1.0 + (0.08 * n_bl_layers if bl_enabled else 0)
        estimated_final = int(refined_cells * bl_multiplier)

        self.log.info(f"Fluid fraction of bounding box: ~{fluid_fraction:.0%}")
        self.log.info(f"Expected final mesh: ~{estimated_final/1e6:.1f}M cells")
        if self.reference_radius_m:
            self._log_cpd_suggestions(cell_size_m, fluid_fraction, n_bl_layers,
                                      bl_enabled, max_ref_level, ranges)

        self.log.info("="*70)

        return {"x": num_cells[0], "y": num_cells[1], "z": num_cells[2]}

    def _estimate_fluid_fraction(self) -> float:
        """Estimate the fraction of the bounding box occupied by the fluid domain.

        Tries to compute the enclosed volume of the wall STL using trimesh.
        Falls back to a conservative empirical estimate if that fails.

        Returns:
            float: Estimated ratio of fluid volume to bounding box volume (0.05 - 0.50).
        """
        wall_stl = os.path.join(self.tri_surface_path, f"{self.wall_patch}.stl")
        if os.path.exists(wall_stl):
            try:
                import trimesh
                mesh = trimesh.load(wall_stl)
                if mesh.is_watertight:
                    # Combine wall + inlet/outlet caps for a closed volume
                    all_stls = [wall_stl]
                    for patch in [self.inlet_patch] + self.outlet_patches:
                        p = os.path.join(self.tri_surface_path, f"{patch}.stl")
                        if os.path.exists(p):
                            all_stls.append(p)
                    combined = trimesh.util.concatenate([trimesh.load(s) for s in all_stls])
                    if combined.is_watertight and combined.volume > 0:
                        bbox = combined.bounding_box.volume
                        fraction = combined.volume / bbox if bbox > 0 else 0.20
                        fraction = max(0.05, min(0.50, fraction))
                        self.log.info(f"Geometry volume: {combined.volume * 1e9:.1f} mL (from STL)")
                        return fraction
                    # Non-watertight combined; try wall alone as approximation
                    if mesh.volume > 0:
                        bbox_vol = np.prod(mesh.bounding_box.extents)
                        fraction = abs(mesh.volume) / bbox_vol if bbox_vol > 0 else 0.20
                        return max(0.05, min(0.50, fraction))
            except Exception as e:
                self.log.debug(f"trimesh volume estimation failed: {e}")

        # Fallback: empirical estimate for tubular vascular geometries
        # Typical aortic anatomy occupies 15-25% of its bounding box
        self.log.debug("Using empirical fluid fraction estimate (0.20)")
        return 0.20

    def _log_cpd_suggestions(self, current_cell_size_m: float, fluid_fraction: float,
                             n_bl_layers: int, bl_enabled: bool,
                             max_ref_level: int, bbox_ranges_m: np.ndarray) -> None:
        """Log a quick-reference table: cpd -> estimated cell count."""
        D_ref = 2.0 * self.reference_radius_m
        bbox_vol = bbox_ranges_m[0] * bbox_ranges_m[1] * bbox_ranges_m[2]
        surface_mult = 1.0 + 0.15 * (4**max_ref_level - 1)
        bl_mult = 1.0 + (0.08 * n_bl_layers if bl_enabled else 0)

        self.log.info("")
        self.log.info("CPD quick-reference (estimated final cells):")
        self.log.info(f"  {'cpd':>5}  {'cell size':>10}  {'est. cells':>12}")
        for cpd in [8, 10, 12, 15, 20, 25, 30]:
            h = D_ref / cpd
            bg = bbox_vol / (h ** 3)
            est = int(bg * fluid_fraction * surface_mult * bl_mult)
            marker = " <-- current" if abs(h - current_cell_size_m) / max(h, 1e-9) < 0.05 else ""
            self.log.info(f"  {cpd:>5}  {h*1000:>8.2f} mm  {est/1e6:>10.1f}M{marker}")

    def _get_internal_point_for_snappy(self) -> np.ndarray:
        """
        Calculates a point guaranteed to be inside the fluid domain using a
        robust, path-aligned normal vector. Returns point in meters.
        """
        if self.inlet_centroid is None or not self.outlet_centroids:
            raise ValueError("Inlet or outlet centroids have not been calculated.")

        # 1. Calculate the average position of all outlet centers (in meters)
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

        # 4. Move a small distance along this guaranteed inward normal (in meters)
        offset_distance = self.inlet_radius * 0.1  # 10% of the radius
        internal_point = inlet_centroid + (offset_distance * inward_normal)

        self.log.info(f"Robust locationInMesh calculated: {internal_point} (m)")
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
        Generate snappyHexMeshDict with boundary layer settings.

        For span refinement mode, auto-calculates the required refinement level
        based on cells_across_span and blockMesh resolution.
        """
        # Calculate auto refinement level for span mode
        span_refinement_level = self._calculate_span_refinement_level()

        context = {
            "config": self.config,
            "patches": self.all_patches,
            "wall_patch": self.wall_patch,
            "internal_point": internal_point,
            "span_refinement_level": span_refinement_level
        }
        self._write_file_from_template("snappyHexMeshDict.tpl", os.path.join(self.case_dir, "system", "snappyHexMeshDict"), context)

    def _calculate_span_refinement_level(self) -> int:
        """
        Calculate the required refinement level for span-based refinement.

        CORRECTED calculation (matches _cell_size_from_default_fallback):
        - insideSpan mode uses ONLY span_level for internal refinement
        - achievable_cells = blockMesh × 2^span_level
        - Surface refinement is SEPARATE (near-surface cells only)

        If span_refinement_level is explicitly set in config, use that value.
        Otherwise, auto-calculate based on cells_across_span.

        Returns:
            int: Required refinement level (default 2 if span refinement not enabled)
        """
        span_refinement_enabled = self.snappy_settings.get('span_refinement_enabled', False)
        cells_across_span = self.snappy_settings.get('cells_across_span', 0)

        if not span_refinement_enabled or cells_across_span <= 0:
            # Return default if span refinement not used
            return self.snappy_settings.get('span_refinement_level', 2)

        # If user explicitly set span_refinement_level, use it
        user_span_level = self.snappy_settings.get('span_refinement_level', None)
        if user_span_level is not None:
            self.log.info(f"Using user-specified span refinement level: {user_span_level}")
            return user_span_level

        # Auto-calculate using shared planner (same logic as _cell_size_from_default_fallback)
        from .utils.mesh_constants import plan_span_background

        plan = plan_span_background(cells_across_span)
        self.log.info(
            f"Auto-calculated span refinement level: {plan['span_level']}\n"
            f"  (blockMesh={plan['background_cpd']} cells/D × 2^{plan['span_level']} = {plan['theoretical_cells_across']} cells across span)"
        )
        return plan['span_level']

    def _write_surfacefeatures_dict(self):
        context = {
            "patches": self.all_patches,
            "wall_patch": self.wall_patch,
            "snappy_settings": self.snappy_settings,
            "config": self.config
        }
        self._write_file_from_template("surfaceFeaturesDict.tpl", os.path.join(self.case_dir, "system", "surfaceFeaturesDict"), context)