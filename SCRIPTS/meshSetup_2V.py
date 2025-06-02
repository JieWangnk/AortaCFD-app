import os
import re
from stl import mesh as np_stl_mesh # Using an alias for clarity
import numpy as np
from SCRIPTS.logger import Logger
from SCRIPTS.patchProcessing import PatchProcessing 
from SCRIPTS.aorticAxisEstimator import AorticAxisEstimator 

class GeometryAnalyzer:
    def __init__(self, DIRECTORY, geometry_case_name_from_config, refinement_level_key,
                 refinement_levels_dict, snappy_settings_dict,
                 rotated_stl_basenames, path_to_trisurface_dir,
                 expansion_factor=0.02, log_file="meshSetup.log",
                 global_config=None): # Pass the whole CONFIG dictionary

        self.case_dir = DIRECTORY  # Main case directory (e.g., OPENFOAM/PATIENT1_coarse)
        self.geometry_case_name = geometry_case_name_from_config
        self.refinement_level_key = refinement_level_key # e.g., "coarse"
        
        # Actual numerical refinement level (e.g., target cell size)
        if self.refinement_level_key not in refinement_levels_dict:
            raise ValueError(f"Refinement key '{self.refinement_level_key}' not found in refinement_levels_dict.")
        self.base_cell_size_target = refinement_levels_dict[self.refinement_level_key]
        if self.base_cell_size_target <= 0:
            raise ValueError(f"Invalid base_cell_size_target: {self.base_cell_size_target}. Must be positive.")

        self.snappy_settings = snappy_settings_dict
        self.stl_filenames = [os.path.basename(f) for f in rotated_stl_basenames]  # Extract basenames
        self.tri_surface_path = path_to_trisurface_dir # e.g., ".../constant/triSurface"

        self.expansion_factor = expansion_factor
        self.logger = Logger(log_file).get_logger() # Or better, pass a shared logger instance

        if global_config is None:
            self.logger.error("Global CONFIG not passed to GeometryAnalyzer. Cannot proceed.")
            raise ValueError("Global CONFIG instance is required.")
        self.config = global_config
        
        self.scale_factor = self.config["geometry"]["scale_factor"]

        # Identify main wall, inlet, and outlet STL basenames
        self.main_wall_stl_filename = self._find_stl_by_keyword("wall", default_to_first=True)
        if not self.main_wall_stl_filename:
             raise ValueError("Critical error: Main wall STL file (containing 'wall') not found.")

        self.inlet_patch_keyword = self.config["geometry"].get("inlet_keyword", "inlet")
        self.outlet_patch_keywords = self.config["geometry"].get("outlet_keywords_ordered",
                                                                 self._derive_outlet_keywords())

        self.logger.info(f"GeometryAnalyzer initialized for case: {self.geometry_case_name}")
        self.logger.info(f"Using triSurface path: {self.tri_surface_path}")
        self.logger.info(f"STL files to process: {self.stl_filenames}")
        self.logger.info(f"Main wall STL identified as: {self.main_wall_stl_filename}")
        self.logger.info(f"Inlet keyword: {self.inlet_patch_keyword}")
        self.logger.info(f"Outlet keywords: {self.outlet_patch_keywords}")

        self.principal_aortic_axis = None
        self._calculate_principal_axis()

        # Store min/max vertices and cell counts for blockMesh
        self.min_vertex_bm, self.max_vertex_bm = self.get_blockmesh_bounds()
        self.x_cells_bm, self.y_cells_bm, self.z_cells_bm = self.calculate_blockmesh_cells(
            self.min_vertex_bm, self.max_vertex_bm
        )
        self.internal_point_sHM = self.get_internal_point_for_snappy(offset_factor=0.2)

    def _find_stl_by_keyword(self, keyword, default_to_first=False):
        """Finds an STL filename in self.stl_filenames containing the keyword."""
        keyword_lower = keyword.lower()
        found_files = [f for f in self.stl_filenames if keyword_lower in f.lower()]
        print(f"!!!Searching for STL files with keyword '{keyword}': Found {len(found_files)} files.")
        if found_files:
            if len(found_files) > 1:
                self.logger.warning(f"Multiple STL files found for keyword '{keyword}': {found_files}. Using first one: {found_files[0]}")
            return found_files[0]
        if default_to_first and self.stl_filenames:
            self.logger.warning(f"No STL file found for keyword '{keyword}'. Defaulting to first STL: {self.stl_filenames[0]}")
            return self.stl_filenames[0]
        return None

    def _derive_outlet_keywords(self):
        """Derives sorted outlet keywords from STL filenames."""
        outlet_files = [f for f in self.stl_filenames if "outlet" in f.lower()]
        # Sort by number in filename, e.g., outlet1, outlet2
        def sort_key(filename):
            matches = re.findall(r'\d+', filename)
            return int(matches[-1]) if matches else float('inf')

        outlet_files.sort(key=sort_key)
        keywords = [os.path.splitext(f)[0] for f in outlet_files] # Use basename without ext as keyword
        if not keywords:
            self.logger.warning("No outlet STL files found to derive keywords automatically.")
        return keywords

    def _calculate_principal_axis(self):
        """Calculates and stores the principal aortic axis."""
        self.logger.info("Attempting to calculate principal aortic axis...")
        wall_stl_full_path = os.path.join(self.tri_surface_path, self.main_wall_stl_filename)

        if not os.path.exists(wall_stl_full_path):
            self.logger.error(f"Wall STL for axis estimation not found: {wall_stl_full_path}")
            return

        # Ensure inlet and all specified outlets exist for robust axis estimation
        # This relies on PatchProcessing to handle FileNotFoundError if a specific keyword doesn't match a file
        try:
            axis_estimator = AorticAxisEstimator(
                wall_stl_full_path=wall_stl_full_path,
                inlet_patch_keyword=self.inlet_patch_keyword,
                outlet_patch_keywords=self.outlet_patch_keywords,
                tri_surface_dir=self.tri_surface_path,
                all_stl_filenames_in_trisurface=self.stl_filenames, # Pass basenames
                patch_processing_class_ref=PatchProcessing, # Pass the actual class [cite: 1]
                scale_factor=self.scale_factor,
                logger_instance=self.logger
            )
            self.principal_aortic_axis = axis_estimator.get_combined_axis() # [cite: 1]
            if self.principal_aortic_axis is not None:
                self.logger.info(f"Successfully calculated principal aortic axis: {self.principal_aortic_axis}")
            else:
                self.logger.warning("Principal aortic axis calculation failed or returned None. Slicing may be affected.")
        except Exception as e:
            self.logger.error(f"Error during AorticAxisEstimator initialization or use: {e}")
            self.principal_aortic_axis = None

    def extract_vertices_from_stl(self, stl_file_basename):
        """Extracts unique vertices from a given STL file basename located in tri_surface_path."""
        full_path = os.path.join(self.tri_surface_path, stl_file_basename)
        try:
            # The 'mesh' alias here is for 'numpy-stl's mesh object
            stl_mesh_obj = np_stl_mesh.Mesh.from_file(full_path) # [cite: 2] (example from axisEstimator)
            vertices = stl_mesh_obj.vectors.reshape(-1, 3) # [cite: 2] (example from axisEstimator)
            unique_vertices = np.unique(vertices, axis=0) # [cite: 2] (example from axisEstimator)
            return unique_vertices
        except Exception as e:
            self.logger.error(f"Error processing STL file {full_path}: {e}")
            # Re-raise as a different error or return None, depending on desired handling
            raise RuntimeError(f"Error processing STL file {full_path}: {e}") from e

    def get_blockmesh_bounds(self):
        """Calculates the expanded bounding box for blockMesh using all STLs."""
        max_x, max_y, max_z = float('-inf'), float('-inf'), float('-inf')
        min_x, min_y, min_z = float('inf'), float('inf'), float('inf')

        if not self.stl_filenames:
            self.logger.error("No STL files available to determine bounding box.")
            raise ValueError("STL file list is empty.")

        all_scaled_vertices = []
        for stl_file_bn in self.stl_filenames:
            vertices = self.extract_vertices_from_stl(stl_file_bn)
            all_scaled_vertices.append(vertices * self.scale_factor) # Scale vertices here

        if not all_scaled_vertices:
             self.logger.error("No vertices extracted from any STL files.")
             raise ValueError("No vertices could be extracted.")

        all_scaled_vertices_np = np.vstack(all_scaled_vertices)

        min_x, min_y, min_z = np.min(all_scaled_vertices_np, axis=0)
        max_x, max_y, max_z = np.max(all_scaled_vertices_np, axis=0)

        # Expand bounding box by the expansion factor
        x_range = max_x - min_x
        y_range = max_y - min_y
        z_range = max_z - min_z

        # Handle cases where a dimension might be zero (e.g., planar geometry for some reason)
        min_x -= self.expansion_factor * x_range if x_range > 1e-9 else self.expansion_factor
        min_y -= self.expansion_factor * y_range if y_range > 1e-9 else self.expansion_factor
        min_z -= self.expansion_factor * z_range if z_range > 1e-9 else self.expansion_factor

        max_x += self.expansion_factor * x_range if x_range > 1e-9 else self.expansion_factor
        max_y += self.expansion_factor * y_range if y_range > 1e-9 else self.expansion_factor
        max_z += self.expansion_factor * z_range if z_range > 1e-9 else self.expansion_factor
        
        self.logger.info(f"BlockMesh bounds (scaled, expanded): min({min_x:.4f}, {min_y:.4f}, {min_z:.4f}), max({max_x:.4f}, {max_y:.4f}, {max_z:.4f})")
        return (min_x, min_y, min_z), (max_x, max_y, max_z)

    def calculate_blockmesh_cells(self, min_vertex, max_vertex):
        """Calculates number of cells for blockMesh based on target base_cell_size."""
        # self.base_cell_size_target is the SCALED target cell size
        x_cells = max(1, int(round((max_vertex[0] - min_vertex[0]) / self.base_cell_size_target)))
        y_cells = max(1, int(round((max_vertex[1] - min_vertex[1]) / self.base_cell_size_target)))
        z_cells = max(1, int(round((max_vertex[2] - min_vertex[2]) / self.base_cell_size_target)))
        self.logger.info(f"BlockMesh cells: Nx={x_cells}, Ny={y_cells}, Nz={z_cells} (target cell size: {self.base_cell_size_target:.2e})")
        return x_cells, y_cells, z_cells

    def get_internal_point_for_snappy(self, offset_factor=0.2):
        """
        Calculates an internal point for snappyHexMesh, ensuring it's within the blockMesh bounds.
        Uses scaled coordinates.
        """
        all_points_scaled_list = []
        for stl_file_bn in self.stl_filenames:
            vertices = self.extract_vertices_from_stl(stl_file_bn)
            all_points_scaled_list.append(vertices * self.scale_factor) # Scale vertices

        if not all_points_scaled_list:
            self.logger.error("No points loaded to calculate centroid for internal point.")
            # Fallback to center of blockMesh if STLs fail (less ideal)
            bm_min, bm_max = self.min_vertex_bm, self.max_vertex_bm
            fallback_point = ((bm_min[0]+bm_max[0])/2, (bm_min[1]+bm_max[1])/2, (bm_min[2]+bm_max[2])/2)
            self.logger.warning(f"Using fallback internal point (center of blockMesh): {fallback_point}")
            return f"({fallback_point[0]:.5f} {fallback_point[1]:.5f} {fallback_point[2]:.5f})"

        all_points_np_scaled = np.vstack(all_points_scaled_list)
        centroid_scaled = np.mean(all_points_np_scaled, axis=0)

        distances = np.linalg.norm(all_points_np_scaled - centroid_scaled, axis=1)
        farthest_point_scaled = all_points_np_scaled[np.argmax(distances)]

        direction_vector = centroid_scaled - farthest_point_scaled
        internal_point_candidate = farthest_point_scaled + direction_vector * offset_factor

        # Validate if the point is within the blockMesh domain (already scaled)
        bm_min, bm_max = self.min_vertex_bm, self.max_vertex_bm
        if not (bm_min[0] <= internal_point_candidate[0] <= bm_max[0] and
                bm_min[1] <= internal_point_candidate[1] <= bm_max[1] and
                bm_min[2] <= internal_point_candidate[2] <= bm_max[2]):
            self.logger.warning(f"Calculated internal point {internal_point_candidate} is outside blockMesh. Defaulting to centroid: {centroid_scaled}")
            internal_point_candidate = centroid_scaled # Fallback to centroid if offset point is outside blockmesh

        # Final check against blockMesh bounds again
        internal_point_final_x = np.clip(internal_point_candidate[0], bm_min[0] + 1e-6, bm_max[0] - 1e-6)
        internal_point_final_y = np.clip(internal_point_candidate[1], bm_min[1] + 1e-6, bm_max[1] - 1e-6)
        internal_point_final_z = np.clip(internal_point_candidate[2], bm_min[2] + 1e-6, bm_max[2] - 1e-6)
        internal_point_final = (internal_point_final_x, internal_point_final_y, internal_point_final_z)

        self.logger.info(f"Internal point for snappyHexMesh (scaled): {internal_point_final}")
        return f"({internal_point_final[0]:.5f} {internal_point_final[1]:.5f} {internal_point_final[2]:.5f})"

    def generate_blockMeshDict_bounds(self): # Renamed from your previous version
        # Uses self.min_vertex_bm, self.max_vertex_bm, self.x_cells_bm etc. calculated in __init__
        content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
// =========                 |
// \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
//  \\\\    /   O peration     | Website:  www.OpenFOAM.org
//   \\\\  /    A nd           | Version:  {self.config["openfoam_version"]}
//    \\\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      blockMeshDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

convertToMeters 1; // Assuming scaled coordinates are in meters

vertices
(
    ({self.min_vertex_bm[0]:.6g} {self.min_vertex_bm[1]:.6g} {self.min_vertex_bm[2]:.6g}) //0
    ({self.max_vertex_bm[0]:.6g} {self.min_vertex_bm[1]:.6g} {self.min_vertex_bm[2]:.6g}) //1
    ({self.max_vertex_bm[0]:.6g} {self.max_vertex_bm[1]:.6g} {self.min_vertex_bm[2]:.6g}) //2
    ({self.min_vertex_bm[0]:.6g} {self.max_vertex_bm[1]:.6g} {self.min_vertex_bm[2]:.6g}) //3
    ({self.min_vertex_bm[0]:.6g} {self.min_vertex_bm[1]:.6g} {self.max_vertex_bm[2]:.6g}) //4
    ({self.max_vertex_bm[0]:.6g} {self.min_vertex_bm[1]:.6g} {self.max_vertex_bm[2]:.6g}) //5
    ({self.max_vertex_bm[0]:.6g} {self.max_vertex_bm[1]:.6g} {self.max_vertex_bm[2]:.6g}) //6
    ({self.min_vertex_bm[0]:.6g} {self.max_vertex_bm[1]:.6g} {self.max_vertex_bm[2]:.6g}) //7
);

blocks
(
    hex (0 1 2 3 4 5 6 7) ({self.x_cells_bm} {self.y_cells_bm} {self.z_cells_bm}) simpleGrading (1 1 1)
);

edges
(
);

boundary
(
    world
    {{
        type patch;
        faces
        (
            (0 3 2 1) // bottom
            (4 5 6 7) // top
            (0 1 5 4) // front
            (3 7 6 2) // back
            (0 4 7 3) // left
            (1 2 6 5) // right
        );
    }}
);

// ************************************************************************* //
"""
        return content

    def generate_snappyHexMeshDict(self):
        # Uses self.snappy_settings, self.internal_point_sHM, self.main_wall_stl_filename etc.
        # This method will now be more complex with feature-based refinement
        self.logger.info("Generating snappyHexMeshDict with feature-based refinement logic...")

        # --- Start of feature-based refinement logic integration ---
        # This is where you'd call the advanced slicing or use pre-calculated features
        # For now, this part is conceptual for the advanced slicing.
        # stenosis_refinement_regions_str = ""
        # curvature_refinement_regions_str = ""

        # if self.config["mesh"]["advanced_slicing_settings"]["stenosis_refinement_enabled"]:
        #    stenosis_regions = self._analyze_stenosis() # This method would use AdvancedSlicer
        #    for region_name, box_min, box_max, level in stenosis_regions:
        #        stenosis_refinement_regions_str += f"""
        #    {region_name}
        #    {{
        #        mode inside; // or distance, etc.
        #        levels ((1.0 {level})); // Example, level could be relative to distance
        #        type searchableBox;
        #        min ({box_min[0]:.6g} {box_min[1]:.6g} {box_min[2]:.6g});
        #        max ({box_max[0]:.6g} {box_max[1]:.6g} {box_max[2]:.6g});
        #    }}"""
        # Similar logic for curvature refinement regions

        # --- Original STL-based refinement generation (can be combined/adapted) ---
        stl_geometry_entries = ""
        features_entries = ""
        surface_refinement_entries = ""

        sorted_stl_basenames = self._sort_stl_files_for_snappy(self.stl_filenames) # Use basenames

        for stl_basename in sorted_stl_basenames:
            stl_name_for_dict = os.path.splitext(stl_basename)[0] # Name without .stl
            emesh_filename = stl_basename.replace(".stl", ".eMesh")

            # Geometry entry
            stl_geometry_entries += f"""
    {stl_name_for_dict} // Using stl_name_for_dict here
    {{
        type triSurfaceMesh;
        name {stl_name_for_dict}; // And here
        // file "{stl_basename}"; // No, snappyHexMesh expects this to be relative to case/constant/triSurface if not found globally
    }}"""

            # Features entry
            features_entries += f"""
        {{file "{emesh_filename}"; level {self.snappy_settings["featureLevel"]};}}""" # Using config value

            # Surface refinement entry (this is where Phase 1: Diameter-driven refinement would go)
            # For now, using existing logic or default
            min_ref, max_ref = self.snappy_settings["surfaceRefinementLevels"]
            # Placeholder for diameter-driven logic:
            # target_cells = self.config["mesh"]["feature_based_refinement"]["target_cells_across_patch_diameter"]
            # if stl_name_for_dict has diameter data:
            #   calculated_level_for_patch = self._calculate_level_from_diameter(stl_name_for_dict, target_cells)
            #   min_ref, max_ref = calculated_level_for_patch, calculated_level_for_patch + 1

            surface_refinement_entries += f"""
        {stl_name_for_dict}
        {{
            level ({min_ref} {max_ref});
            // patchInfo {{ type wall; }} // Optional: specify patch type if needed by sHM
        }}"""
        
        # Define main region refinement box (overall geometry or user-defined)
        # self.min_vertex_bm and self.max_vertex_bm are for blockMesh, they are expanded.
        # For sHM region refinement, we might want a tighter box around the actual geometry
        # or use the user-defined one from config.
        if self.snappy_settings.get("regionRefinementBox"):
            sHM_ref_box_min = self.snappy_settings["regionRefinementBox"][0:3]
            sHM_ref_box_max = self.snappy_settings["regionRefinementBox"][3:6]
        else:
            # Get tight bounding box of scaled STLs for sHM region refinement if not specified
            # This is different from the expanded blockMesh bounds.
            all_scaled_vertices_list = []
            for stl_file_bn in self.stl_filenames:
                vertices = self.extract_vertices_from_stl(stl_file_bn)
                all_scaled_vertices_list.append(vertices * self.scale_factor)
            all_scaled_vertices_np = np.vstack(all_scaled_vertices_list)
            sHM_ref_box_min = np.min(all_scaled_vertices_np, axis=0)
            sHM_ref_box_max = np.max(all_scaled_vertices_np, axis=0)

        # Build the refinementRegions block string dynamically
        # Includes the main region_refinement_box and potentially stenosis/curvature boxes
        refinement_regions_content = f"""
        refinementRegions
        {{
            // Main bounding box for overall refinement
            "{self.main_wall_stl_filename.split('.')[0]}_refBox" // Example name
            {{
                mode inside; // Or 'distance' for refinement based on distance from this box
                levels ((1.0 {self.snappy_settings["regionRefinementLevel"]})); // Refine all cells inside this box up to this level
                type searchableBox;
                min ({sHM_ref_box_min[0]:.6g} {sHM_ref_box_min[1]:.6g} {sHM_ref_box_min[2]:.6g});
                max ({sHM_ref_box_max[0]:.6g} {sHM_ref_box_max[1]:.6g} {sHM_ref_box_max[2]:.6g});
            }}
        }}"""

        """refinementRegions
        {{
            // Main bounding box for overall refinement
            "{self.main_wall_stl_filename.split('.')[0]}_refBox" // Example name
            {{
                mode inside; // Or 'distance' for refinement based on distance from this box
                levels ((1.0 {self.snappy_settings["regionRefinementLevel"]})); // Refine all cells inside this box up to this level
                type searchableBox;
                min ({sHM_ref_box_min[0]:.6g} {sHM_ref_box_min[1]:.6g} {sHM_ref_box_min[2]:.6g});
                max ({sHM_ref_box_max[0]:.6g} {sHM_ref_box_max[1]:.6g} {sHM_ref_box_max[2]:.6g});
            }}
            // {stenosis_refinement_regions_str} // Add future stenosis regions here
            // {curvature_refinement_regions_str} // Add future curvature regions here
        }}"""


        template = f"""
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      snappyHexMeshDict;
}}

castellatedMesh {str(self.snappy_settings.get("castellatedMesh", "true")).lower()};
snap            {str(self.snappy_settings.get("snap", "true")).lower()};
addLayers       {str(self.snappy_settings.get("addLayers", "true")).lower()};

geometry
{{{stl_geometry_entries}
}};

castellatedMeshControls
{{
    maxLocalCells {self.snappy_settings.get("maxLocalCells", 10000000)};
    maxGlobalCells {self.snappy_settings.get("maxGlobalCells", 20000000)};
    minRefinementCells {self.snappy_settings.get("minRefinementCells", 10)};
    maxLoadUnbalance {self.snappy_settings.get("maxLoadUnbalance", 0.10)};
    nCellsBetweenLevels {self.snappy_settings.get("nCellsBetweenLevels", 3)};

    features
    ({features_entries}
    );

    refinementSurfaces
    {{{surface_refinement_entries}
    }};

    {refinement_regions_content} // Insert dynamically built refinementRegions

    locationInMesh {self.internal_point_sHM};
    allowFreeStandingZoneFaces {str(self.snappy_settings.get("allowFreeStandingZoneFaces", "true")).lower()};
    resolveFeatureAngle {self.snappy_settings.get("resolveFeatureAngle", 30)};
}};

snapControls
{{
    nSmoothPatch {self.snappy_settings.get("nSmoothPatch", 3)};
    tolerance {self.snappy_settings.get("snapTolerance", 2.0)}; // Different key used from config
    nSolveIter {self.snappy_settings.get("nSolveIter", 30)};
    nRelaxIter {self.snappy_settings.get("nRelaxIter", 5)}; // Default: 5
    nFeatureSnapIter {self.snappy_settings.get("nFeatureSnapIter", 10)}; // Default: 10
    
    // Missing: implicitFeatureSnap, explicitFeatureSnap, multiRegionFeatureSnap from your example
    // Add them from self.snappy_settings if they exist or use defaults
    implicitFeatureSnap {str(self.snappy_settings.get("implicitFeatureSnap", "false")).lower()};
    explicitFeatureSnap {str(self.snappy_settings.get("explicitFeatureSnap", "true")).lower()};
    multiRegionFeatureSnap {str(self.snappy_settings.get("multiRegionFeatureSnap", "false")).lower()};
}};

addLayersControls
{{
    relativeSizes {str(self.snappy_settings.get("relativeSizes", "true")).lower()};
    layers
    {{
        // Use the actual main wall stl filename (without .stl) for layers
        "{os.path.splitext(self.main_wall_stl_filename)[0]}" 
        {{
            nSurfaceLayers {self.snappy_settings.get("nSurfaceLayers", self.snappy_settings.get("addLayer", 5))}; // addLayer is old key
        }}
    }}
    expansionRatio {self.snappy_settings.get("expansionRatio", 1.2)}; // Default: 1.2
    finalLayerThickness {self.snappy_settings.get("finalLayerThickness", 0.3)}; // Default: 0.3
    minThickness {self.snappy_settings.get("minThickness", 0.1)}; // Default: 0.1
    nGrow {self.snappy_settings.get("nGrow", 0)};
    
    // Many other addLayersControls parameters - ensure they are taken from self.snappy_settings
    // or have sensible defaults if not present in your config structure.
    // Example for featureAngle:
    featureAngle {self.snappy_settings.get("featureAngle", 60)}; // Default: 60
    slipFeatureAngle {self.snappy_settings.get("slipFeatureAngle", 30)}; // Default: 30
    nRelaxIter {self.snappy_settings.get("addLayers_nRelaxIter", 5)}; // Renamed to avoid clash
    // ... (continue for all addLayersControls from your template, using self.snappy_settings.get())
}};

meshQualityControls
{{ // These are usually standard, but can also be made configurable
    maxNonOrtho {self.snappy_settings.get("maxNonOrtho", 65)};
    maxBoundarySkewness {self.snappy_settings.get("maxBoundarySkewness", 20)};
    maxInternalSkewness {self.snappy_settings.get("maxInternalSkewness", 4)};
    maxConcave {self.snappy_settings.get("maxConcave", 80)};
    minVol {self.snappy_settings.get("minVol", 1e-13)};
    minTetQuality {self.snappy_settings.get("minTetQuality", 1e-30)};
    minArea {self.snappy_settings.get("minArea", -1)}; // Typically -1 (disabled) or small positive
    minTwist {self.snappy_settings.get("minTwist", 0.02)};
    minDeterminant {self.snappy_settings.get("minDeterminant", 0.001)};
    // ... (continue for all meshQualityControls)
}};

writeFlags ( scalarLevels layerSets layerFields ); // Usually not changed often
mergeTolerance {self.snappy_settings.get("mergeTolerance", 1e-6)};

// ************************************************************************* //
"""
        return template

    def _sort_stl_files_for_snappy(self, files_basenames):
        """Sorts STL basenames for consistent snappyHexMeshDict entries."""
        # Example sort key: wall first, then inlet, then outlets numerically
        def sort_key(x_bn): # x_bn is basename
            x_lower = x_bn.lower()
            if "wall" in x_lower: return (0, x_bn)
            if "inlet" in x_lower: return (1, x_bn)
            if "outlet" in x_lower:
                match = re.findall(r"\d+", x_bn)
                return (2, int(match[-1]) if match else float('inf'), x_bn)
            return (3, x_bn) # Other files
        return sorted(files_basenames, key=sort_key)

    def write_blockMeshDict(self):
        content = self.generate_blockMeshDict_bounds()
        output_path = os.path.join(self.case_dir, "system", "blockMeshDict") # Use self.case_dir
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(content)
        self.logger.info(f"blockMeshDict written to {output_path}")

    def write_snappyHexMeshDict(self):
        content = self.generate_snappyHexMeshDict()
        output_path = os.path.join(self.case_dir, "system", "snappyHexMeshDict") # Use self.case_dir
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(content)
        self.logger.info(f"snappyHexMeshDict written to {output_path}")

    def write_surfaceFeaturesDict(self):
        """Generates and writes the surfaceFeaturesDict for OpenFOAM version 8."""
        sorted_stl_basenames = self._sort_stl_files_for_snappy(self.stl_filenames)
        surfaces_block = ""
        for stl_basename in sorted_stl_basenames:
            # surfaceFeaturesDict expects filenames as they are in constant/triSurface
            surfaces_block += f'    "{stl_basename}"\n'

        # Using self.snappy_settings for includedAngle to ensure consistency if defined there
        included_angle = self.snappy_settings.get("resolveFeatureAngle", 150)  # Default if not in sHM settings

        content = f"""
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      surfaceFeaturesDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

surfaces
(
{surfaces_block});

includedAngle   {included_angle};

// ************************************************************************* //
"""
        output_path = os.path.join(self.case_dir, "system", "surfaceFeaturesDict")  # Use self.case_dir
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(content)
        self.logger.info(f"surfaceFeaturesDict written to {output_path}")
