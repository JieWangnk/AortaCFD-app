import os
import re
from stl import mesh
import numpy as np
from userParameter_LL import *

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
    def __init__(self, DIRECTORY, geometry_case, refinement="coarse"):
        self.DIRECTORY = DIRECTORY
        self.geometry_case = geometry_case
        self.geometry_path = os.path.join("CAD", geometry_case)

        # Gather all .stl files in the geometry path
        all_stl_files = [f for f in os.listdir(self.geometry_path) if f.endswith('.stl')]

        # Sort them so that 'wall' -> 'inlet' -> 'outletN' in ascending numeric order
        self.stl_files = sorted(
            all_stl_files,
            key=lambda x: (
                0 if "wall" in x else (1 if "inlet" in x else 2),
                int(re.findall(r"\d+", x)[0]) if "outlet" in x else 0
            )
        )

        # Read refinement and snappy parameters from userParameter_LL
        self.refinement = REFINEMENT_LEVELS[refinement]
        self.expansion_factor = SNAPPY_SETTINGS["expansionFactor"]
        self.feature_level = SNAPPY_SETTINGS["featureLevel"]
        self.surface_refinement_levels = SNAPPY_SETTINGS["surfaceRefinementLevels"]
        self.addLayers = SNAPPY_SETTINGS["addLayer"]
        self.nCellsBetweenLevels = SNAPPY_SETTINGS["nCellsBetweenLevels"]
        self.resloveFeatureAngle = SNAPPY_SETTINGS["resloveFeatureAngle"]
        self.nSmoothPatch = SNAPPY_SETTINGS["nSmoothPatch"]
        self.region_refinement_level = SNAPPY_SETTINGS["regionRefinementLevel"]
        self.region_refinement_box = SNAPPY_SETTINGS["regionRefinementBox"]

        # The folder name is the geometry name
        self.geometry_name = os.path.basename(self.geometry_path)

        # Find the main aorta STL file (the one containing "wall")
        self.main_aorta_stl = [f for f in self.stl_files if "wall" in f][0]

    def extract_vertices_from_stl(self, stl_file):
        stl_mesh = mesh.Mesh.from_file(stl_file)
        vertices = stl_mesh.vectors.reshape(-1, 3)
        # Get unique vertices to avoid duplicates
        unique_vertices = np.unique(vertices, axis=0)
        return unique_vertices

    def get_max_vertex(self):
        max_x, max_y, max_z = float('-inf'), float('-inf'), float('-inf')
        min_x, min_y, min_z = float('inf'), float('inf'), float('inf')

        for stl_file in self.stl_files:
            full_path = os.path.join(self.geometry_path, stl_file)
            vertices = self.extract_vertices_from_stl(full_path)

            for vertex in vertices:
                x, y, z = vertex
                max_x = max(max_x, x)
                max_y = max(max_y, y)
                max_z = max(max_z, z)
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                min_z = min(min_z, z)

        # Expand bounding box by a factor (2% default in your code)
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
        x_cells = int((max_vertex[0] - min_vertex[0]) / self.refinement)
        y_cells = int((max_vertex[1] - min_vertex[1]) / self.refinement)
        z_cells = int((max_vertex[2] - min_vertex[2]) / self.refinement)
        return x_cells, y_cells, z_cells

    def load_mesh_points(self):
        all_points = np.empty((0, 3))
        for stl_file in self.stl_files:
            full_path = os.path.join(self.geometry_path, stl_file)
            vertices = self.extract_vertices_from_stl(full_path)
            all_points = np.concatenate([all_points, vertices])
        centroid = np.mean(all_points, axis=0)
        return all_points, centroid

    def get_internal_point(self, offset_factor=0.2):
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

        for stl_file in self.stl_files:
            stl_file_name = stl_file.split(".")[0]
            eMesh_file = stl_file.replace(".stl", ".eMesh")

            # Default feature/refinement levels
            current_feature_level = self.feature_level
            min_ref, max_ref = self.surface_refinement_levels

            # If it's outlet1, outlet2, or outlet3, increment levels
            if any(sub in stl_file_name for sub in ["outlet1", "outlet2", "outlet3"]):
                current_feature_level += 1
                max_ref += 1

            # Build geometry block
            stl_block += f"""
        {stl_file}
        {{
            type triSurfaceMesh;
            name {stl_file_name};
        }}
        """

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
            main_aorta_stl=self.main_aorta_stl.split(".")[0],
            addLayers=self.addLayers,
            internal_point2=self.get_internal_point(offset_factor=0.2)
        )
        return snappy_hex_mesh_dict_content

    def generate_surfaceFeaturesDict(self):
        surfaces_block = ""
        for stl_file in self.stl_files:
            surfaces_block += f"""
        "{stl_file}"
    """
        content = """
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      surfaceFeaturesDict;
}}
surfaces ( {surfaces_block} );
includedAngle 150;
"""
        content = content.format(surfaces_block=surfaces_block)
        return content

    def write_surfaceFeaturesDict(self):
        content = self.generate_surfaceFeaturesDict()
        output_dir = os.path.join(self.DIRECTORY, "system")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "surfaceFeaturesDict")

        with open(output_path, 'w') as f:
            f.write(content)
        print(f"surfaceFeaturesDict written to {output_path}")

    def write_blockMeshDict(self):
        content = self.generate_blockMeshDict_bounds()
        output_dir = os.path.join(self.DIRECTORY, "system")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "blockMeshDict")

        with open(output_path, 'w') as f:
            f.write(content)
        print(f"blockMeshDict written to {output_path}")

    def write_snappyHexMeshDict(self):
        content = self.generate_snappyHexMeshDict()
        output_dir = os.path.join(self.DIRECTORY, "system")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "snappyHexMeshDict")

        with open(output_path, 'w') as f:
            f.write(content)
        print(f"snappyHexMeshDict written to {output_path}")
