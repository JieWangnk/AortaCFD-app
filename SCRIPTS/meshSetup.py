import os
import re
from stl import mesh
import numpy as np
import logging

logging.basicConfig(level=logging.INFO)

def is_binary_file(file_path):
    """Check if the given file is binary."""
    with open(file_path, 'rb') as file:
        for _ in range(512):  # check first 512 bytes
            chunk = file.read(1)
            if not chunk:
                break
            if b'\x00' in chunk:  # found null byte
                return True
    return False

class GeometryAnalyzer:
    def __init__(self, DIRECTORY, geometry_case, refinement, refinement_levels, snappy_settings, stl_files, geometry_path, expansion_factor=0.02):
        self.directory = DIRECTORY
        self.geometry_case = geometry_case
        self.refinement = refinement
        self.refinement_levels = refinement_levels[refinement]
        self.snappy_settings = snappy_settings
        self.stl_files = stl_files  # Use the rotated STL files
        self.geometry_path = geometry_path  # Path to the directory containing the rotated STL files
        self.expansion_factor = expansion_factor  # Expansion factor for bounding box
        self.feature_level = snappy_settings["featureLevel"]
        self.surface_refinement_levels = snappy_settings["surfaceRefinementLevels"]
        self.region_refinement_level = snappy_settings["regionRefinementLevel"]
        self.region_refinement_box = snappy_settings["regionRefinementBox"]
        self.resloveFeatureAngle = snappy_settings["resolveFeatureAngle"]
        self.nSmoothPatch = snappy_settings["nSmoothPatch"]
        self.addLayers = snappy_settings["addLayer"]

        # Set main_aorta_stl to the correct STL file (e.g., wall_aorta.stl)
        self.main_aorta_stl = next((f for f in stl_files if "wall" in f), stl_files[0])
        

    def sort_stl_files(self, files):
        def sort_key(x):
            if "wall" in x:
                return (0, 0)  # Highest priority
            elif "inlet" in x:
                return (1, 0)  # Second priority
            elif "outlet" in x:
                match = re.findall(r"\d+", x)  # Extract numbers from the file name
                return (2, int(match[0]) if match else 0)  # Sort outlets numerically
            return (3, 0)  # Default priority for non-matching files

        return sorted(files, key=sort_key)

    def extract_vertices_from_stl(self, stl_file):
        try:
            stl_mesh = mesh.Mesh.from_file(stl_file)
            vertices = stl_mesh.vectors.reshape(-1, 3)
            unique_vertices = np.unique(vertices, axis=0)
            return unique_vertices
        except Exception as e:
            raise RuntimeError(f"Error processing STL file {stl_file}: {e}")

    def get_max_vertex(self):
        max_x, max_y, max_z = float('-inf'), float('-inf'), float('-inf')
        min_x, min_y, min_z = float('inf'), float('inf'), float('inf')

        for stl_file in self.stl_files:
            full_path = os.path.join(self.geometry_path, stl_file)  # Use geometry_path
            vertices = self.extract_vertices_from_stl(full_path)
            for vertex in vertices:
                x, y, z = vertex
                max_x = max(max_x, x)
                max_y = max(max_y, y)
                max_z = max(max_z, z)
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                min_z = min(min_z, z)

        # Expand bounding box by the expansion factor
        x_range = max_x - min_x
        y_range = max_y - min_y
        z_range = max_z - min_z

        min_x -= self.expansion_factor * x_range
        min_y -= self.expansion_factor * y_range
        min_z -= self.expansion_factor * z_range

        max_x += self.expansion_factor * x_range
        max_y += self.expansion_factor * y_range
        max_z += self.expansion_factor * z_range

        return (min_x, min_y, min_z), (max_x, max_y, max_z)

    def calculate_cells(self, min_vertex, max_vertex):
        x_cells = int((max_vertex[0] - min_vertex[0]) / self.refinement_levels)
        y_cells = int((max_vertex[1] - min_vertex[1]) / self.refinement_levels)
        z_cells = int((max_vertex[2] - min_vertex[2]) / self.refinement_levels)
        return x_cells, y_cells, z_cells

    def load_mesh_points(self):
        all_points = []
        for stl_file in self.stl_files:
            full_path = os.path.join(self.geometry_path, stl_file)
            logging.info(f"Loading STL file: {full_path}")
            vertices = self.extract_vertices_from_stl(full_path)
            all_points.append(vertices)
        all_points = np.vstack(all_points)
        centroid = np.mean(all_points, axis=0)
        return all_points, centroid

    def get_internal_point(self, offset_factor=0.2):
        """
        Calculate an internal point within the geometry by moving inward
        from the farthest vertex toward the centroid.

        Args:
            offset_factor (float): Factor to scale the inward movement.

        Returns:
            str: Internal point formatted as "(x y z)".
        """
        # Load the STL file and compute the centroid
        all_points, centroid = self.load_mesh_points()

        # Find the farthest vertex from the centroid
        distances = np.linalg.norm(all_points - centroid, axis=1)
        farthest_point = all_points[np.argmax(distances)]

        # Move inward from the farthest point toward the centroid
        direction_vector = centroid - farthest_point
        internal_point = farthest_point + direction_vector * offset_factor
        internal_point2 = "({:.5f}  {:.5f}  {:.5f})".format(*internal_point)

        return internal_point2

    def generate_blockMeshDict_bounds(self):
        min_vertex, max_vertex = self.get_max_vertex()
        x_cells, y_cells, z_cells = self.calculate_cells(min_vertex, max_vertex)
        return f"""
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      blockMeshDict;
}}
convertToMeters 1;

vertices
(
    ({min_vertex[0]} {min_vertex[1]} {min_vertex[2]})
    ({max_vertex[0]} {min_vertex[1]} {min_vertex[2]})
    ({max_vertex[0]} {max_vertex[1]} {min_vertex[2]})
    ({min_vertex[0]} {max_vertex[1]} {min_vertex[2]})
    ({min_vertex[0]} {min_vertex[1]} {max_vertex[2]})
    ({max_vertex[0]} {min_vertex[1]} {max_vertex[2]})
    ({max_vertex[0]} {max_vertex[1]} {max_vertex[2]})
    ({min_vertex[0]} {max_vertex[1]} {max_vertex[2]})
);

blocks
(
    hex (0 1 2 3 4 5 6 7) ({x_cells} {y_cells} {z_cells}) simpleGrading (1 1 1)
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
            (3 7 6 2)
            (0 4 7 3)
            (2 6 5 1)
            (1 5 4 0)
            (0 3 2 1)
            (4 5 6 7)
        );
    }}
);

"""

    def generate_snappyHexMeshDict(self):
        min_vertex, max_vertex = self.get_max_vertex()
        # Template for the snappyHexMeshDict
        template = """
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      snappyHexMeshDict;
}}

castellatedMesh true;
snap            true;
addLayers       true;

geometry
{{
    {stl_block}
    region_refinement_box 
    {{ 
        type searchableBox; 
        min ({region_refinement_box[0]} {region_refinement_box[1]} {region_refinement_box[2]}); 
        max ({region_refinement_box[3]} {region_refinement_box[4]} {region_refinement_box[5]}); 
    }}
}};

castellatedMeshControls
{{
    maxLocalCells 10000000;
    maxGlobalCells 20000000;
    minRefinementCells 10;
    maxLoadUnbalance 0.10;
    nCellsBetweenLevels 3;

    features
    (
        {features_block}
    );

    refinementSurfaces
    {{
        {refinementSurface_block}
    }};

    {region_refinement_block}

    locationInMesh {internal_point2};
    allowFreeStandingZoneFaces true;
    resolveFeatureAngle {resloveFeatureAngle};
}};

snapControls
{{
    nSmoothPatch {nSmoothPatch};
    tolerance 2.0;
    nSolveIter 10;
    nRelaxIter 3;
    nFeatureSnapIter 3;
    implicitFeatureSnap false;
    explicitFeatureSnap true;
    multiRegionFeatureSnap false;
}};

addLayersControls
{{
    relativeSizes true;
    layers
    {{
        "{main_aorta_stl}"
        {{  
            nSurfaceLayers {addLayers};
        }}    
    }}
    expansionRatio 1.1;
    finalLayerThickness 0.2;
    minThickness 0.001;
    nGrow 0;
    featureAngle 180;
    slipFeatureAngle 90;
    nRelaxIter 30;
    nSmoothSurfaceNormals 1;
    nSmoothNormals 3;
    nSmoothThickness 10;
    maxFaceThicknessRatio 0.5;
    maxThicknessToMedialRatio 0.3;
    minMedianAxisAngle 90;
    nBufferCellsNoExtrude 0;
    nLayerIter 80;
}};
meshQualityControls
{{
    maxNonOrtho 65;
    maxBoundarySkewness 20;
    maxInternalSkewness 4;
    maxConcave 80;
    minFlatness 0.5;
    minVol 1e-13;
    minTetQuality 1e-30;
    minArea -1;
    minTwist 0.02;
    minDeterminant 0.001;
    minFaceWeight 0.02;
    minVolRatio 0.01;
    minTriangleTwist -1;
    nSmoothScale 4;
    errorReduction 0.75;
}};
writeFlags
(
    scalarLevels
    layerSets
    layerFields
);
mergeTolerance 1E-6;
"""
        stl_block = ""
        features_block = ""
        refinementSurface_block = ""

        # Sort STL files before processing
        sorted_stl_files = self.sort_stl_files(self.stl_files)

        for stl_file in sorted_stl_files:
            stl_file_name = os.path.basename(stl_file).split(".")[0]  # Extract file name without extension
            eMesh_file = os.path.basename(stl_file).replace(".stl", ".eMesh")  # Extract eMesh file name

            # Default feature/refinement levels
            current_feature_level = self.feature_level
            min_ref, max_ref = self.surface_refinement_levels

            # If it's outlet1, outlet2, or outlet3, increment levels
            if any(sub in stl_file_name for sub in ["outlet1", "outlet2", "outlet3"]):
                current_feature_level += 1
                max_ref += 1

            # Build geometry block
            stl_block += self.build_geometry_block(stl_file, stl_file_name)

            # Build features block
            features_block += f"""
        {{file "{eMesh_file}"; level {current_feature_level};}}   
        """

            # Build refinementSurfaces block
            refinementSurface_block += f"""
        {stl_file_name}
        {{
            level ({min_ref} {max_ref});
        }}
        """

        # Region-based refinement block
        if self.region_refinement_level is not None:
            region_refinement_block = f"""
        refinementRegions
        {{
            region_refinement_box
            {{
                mode inside;
                levels ((1E15 {self.region_refinement_level}));
            }}
        }};
        """
        else:
            region_refinement_block = """
        refinementRegions
        {};
        """

        # If user hasn't defined a region_refinement_box, use bounding box
        if self.region_refinement_box is None:
            self.region_refinement_box = (
                min_vertex[0], min_vertex[1], min_vertex[2],
                max_vertex[0], max_vertex[1], max_vertex[2]
            )

        # Fill template
        snappy_hex_mesh_dict_content = template.format(
            stl_block=stl_block,
            features_block=features_block,
            refinementSurface_block=refinementSurface_block,
            region_refinement_block=region_refinement_block,
            resloveFeatureAngle=self.resloveFeatureAngle,
            nSmoothPatch=self.nSmoothPatch,
            region_refinement_box=self.region_refinement_box,
            main_aorta_stl=os.path.basename(self.main_aorta_stl).split(".")[0],
            addLayers=self.addLayers,
            internal_point2=self.get_internal_point(offset_factor=0.2)
        )
        return snappy_hex_mesh_dict_content

    def generate_surfaceFeaturesDict(self):
        # Sort STL files before processing
        sorted_stl_files = self.sort_stl_files(self.stl_files)

        surfaces_block = ""
        for stl_file in sorted_stl_files:
            stl_file_name = os.path.basename(stl_file)  # Extract only the file name
            surfaces_block += f'    "{stl_file_name}"\n'

        content = f"""
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      surfaceFeaturesDict;
}}
surfaces ( 
{surfaces_block} );
includedAngle 150;
"""
        return content

    def write_surfaceFeaturesDict(self):
        content = self.generate_surfaceFeaturesDict()
        output_dir = os.path.join(self.directory, "system")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "surfaceFeaturesDict")

        with open(output_path, 'w') as f:
            f.write(content)
        print(f"surfaceFeaturesDict written to {output_path}")

    def write_blockMeshDict(self):
        content = self.generate_blockMeshDict_bounds()
        output_dir = os.path.join(self.directory, "system")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "blockMeshDict")

        with open(output_path, 'w') as f:
            f.write(content)
        logging.info(f"blockMeshDict written to {output_path}")

    def write_snappyHexMeshDict(self):
        content = self.generate_snappyHexMeshDict()
        output_dir = os.path.join(self.directory, "system")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "snappyHexMeshDict")

        with open(output_path, 'w') as f:
            f.write(content)
        print(f"snappyHexMeshDict written to {output_path}")

    def build_geometry_block(self, stl_file, stl_file_name):
        stl_file_name_only = os.path.basename(stl_file)  # Extract only the file name
        return f"""
        {stl_file_name_only}
        {{
            type triSurfaceMesh;
            name {stl_file_name};
        }}
    """
