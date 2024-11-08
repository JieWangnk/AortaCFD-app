import os
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
    def __init__(self,DIRECTORY, geometry_case,refinement="coarse",expansion_factor = 0.02,feature_level=2,surface_refinement_levels=(1,2),region_refinement =(-8,190,-61,1.8,209,-42),addLayers = 5):
        self.DIRECTORY = DIRECTORY
        self.geometry_case = geometry_case
        self.geometry_path = os.path.join("CAD",geometry_case)
        self.stl_files = [f for f in os.listdir(self.geometry_path) if f.endswith('.stl')]
        self.refinement = REFINEMENT_LEVELS[refinement]
        self.expansion_factor = expansion_factor
        self.feature_level = feature_level
        self.surface_refinement_levels = surface_refinement_levels
        self.region_refinement = region_refinement
        self.addLayers = addLayers
        # The name of the geometry is the name of the folder containing the STL files
        self.geometry_name = os.path.basename(self.geometry_path)
        # find the main aorta stl file and rest are inlet and outlet patch
        self.main_aorta_stl = [f for f in self.stl_files if "wall" in f][0]


    def extract_vertices_from_stl(self, stl_file):
        stl_mesh = mesh.Mesh.from_file(stl_file)
        vertices = stl_mesh.vectors.reshape(-1, 3)
        
        # Get unique vertices
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
                
        # Expanding the bounding box vertices by 2%
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

    def calculate_cells(self,min_vertex,max_vertex):
        x_cells = int((max_vertex[0]-min_vertex[0]) / self.refinement)
        y_cells = int((max_vertex[1]-min_vertex[1]) / self.refinement)
        z_cells = int((max_vertex[2]-min_vertex[2]) / self.refinement)
        return x_cells,y_cells,z_cells
    
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
    region_refinement_box {{ type searchableBox; min ({region_refinement[0]} {region_refinement[1]} {region_refinement[2]}); max ({region_refinement[3]} {region_refinement[4]} {region_refinement[5]}); }}
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

    locationInMesh (0 0 0);
    allowFreeStandingZoneFaces true;
    resolveFeatureAngle 30;
}};

snapControls
{{
    nSmoothPatch 3;
    tolerance 4.0;
    nSolveIter 30;
    nRelaxIter 5;
    nFeatureSnapIter 10;
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
    expansionRatio 1.0;
    finalLayerThickness 0.3;
    minThickness 0.1;
    nGrow 0;
    featureAngle 30;
    slipFeatureAngle 80;
    nRelaxIter 3;
    nSmoothSurfaceNormals 1;
    nSmoothNormals 3;
    nSmoothThickness 10;
    maxFaceThicknessRatio 0.5;
    maxThicknessToMedialRatio 0.3;
    minMedianAxisAngle 90;
    nBufferCellsNoExtrude 0;
    nLayerIter 50;
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
        # Generate the stl block
        stl_block = ""
        features_block = ""
        refinementSurface_block = ""
        for i in range(len(self.stl_files)):
            stl_file = self.stl_files[i]
            stl_file_name = stl_file.split(".")[0]
            # replace the ".stl" with "eMesh" to get the name of the STL file without the extension
            eMesh_file = stl_file.replace(".stl", ".eMesh")
            stl_block += f"""
        {stl_file}
        {{
            type triSurfaceMesh;
            name {stl_file_name};
        }}
        """
            features_block += f"""
        {{file "{eMesh_file}"; level {self.feature_level};}}   
        """
            refinementSurface_block += f"""
        {stl_file_name}
        {{
        level ({self.surface_refinement_levels[0]} {self.surface_refinement_levels[1]});
        }}
        """

        # Region-based refinement block. Add or exclude based on the user's choice
        if self.region_refinement is not None:
            region_refinement_block = """
    refinementRegions
    {
        region_refinement_box
        {
            mode inside;
            levels ((1E15 2));  // Adjust as needed
        }
    };
    """
        else:
            region_refinement_block = "refinementRegions{{}}"

        # Fill in the template with the provided parameters
        snappy_hex_mesh_dict_content = template.format(
            geometry_name= self.geometry_name,
            feature_level= self.feature_level,
            surface_refinement_levels= self.surface_refinement_levels,
            region_refinement =self.region_refinement,
            addLayers = self.addLayers,
            stl_block=stl_block,
            features_block=features_block,
            refinementSurface_block=refinementSurface_block,
            region_refinement_block=region_refinement_block,
            main_aorta_stl=self.main_aorta_stl
        )
        return snappy_hex_mesh_dict_content

    def generate_surfaceFeaturesDict(self):
        surfaces_block = ""
        for i in range(len(self.stl_files)):
            stl_file = self.stl_files[i]
            surfaces_block += f"""
        "{stl_file}"
    """
        content =  """
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
        # Ensure directory structure exists
        output_dir = os.path.join(self.DIRECTORY,"system")
        os.makedirs(output_dir, exist_ok=True)
        
        # Path to the output surfaceFeatureExtractDict file
        output_path = os.path.join(output_dir, "surfaceFeaturesDict")

        with open(output_path, 'w') as f:
            f.write(content)
        print(f"surfaceFeaturesDict written to {output_path}")


    def write_blockMeshDict(self):
        content = self.generate_blockMeshDict_bounds()
        
        # Ensure directory structure exists
        output_dir = os.path.join(self.DIRECTORY,"system")
        os.makedirs(output_dir, exist_ok=True)

        # Path to the output blockMeshDict file
        output_path = os.path.join(output_dir, "blockMeshDict")
        
        with open(output_path, 'w') as f:
            f.write(content)
        
        print(f"blockMeshDict written to {output_path}")

    def write_snappyHexMeshDict(self):
        content = self.generate_snappyHexMeshDict()
        
        # Ensure directory structure exists
        output_dir = os.path.join(self.DIRECTORY,"system")
        os.makedirs(output_dir, exist_ok=True)

        # Path to the output blockMeshDict file
        output_path = os.path.join(output_dir, "snappyHexMeshDict")
        
        with open(output_path, 'w') as f:
            f.write(content)
        
        print(f"snappyHexMeshDict written to {output_path}")


