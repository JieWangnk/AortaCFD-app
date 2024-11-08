import os
import numpy as np
from stl import mesh
from scipy.spatial import ConvexHull
from userParameter_HL import GEOMETRY_CASE

class PatchProcessing:
    def __init__(self, DIRECTORY, STL_FILES, PATH_NAME):
        self.DIRECTORY = DIRECTORY
        self.STL_FILES = STL_FILES
        self.geometry_case = GEOMETRY_CASE

        # Construct the path to the CAD folder
        self.CAD_FOLDER = os.path.join("constant","triSurface")

        # Find the inlet stl file 
        self.STL = [f for f in self.STL_FILES if PATH_NAME in f][0]
        self.STL_PATH = os.path.join(self.CAD_FOLDER, self.STL)
        
        self.mesh_data = self.load_mesh(self.STL_PATH)
        self.all_points = self.extract_points()
      
    def load_mesh(self,path):
        # Load the STL file
        return mesh.Mesh.from_file(path)

    def extract_points(self):
        # Extract all points in the mesh
        return np.concatenate([self.mesh_data.v0, self.mesh_data.v1, self.mesh_data.v2])

    def get_bounding_box(self):
        # Calculate minimum and maximum bounds
        min_coords = self.all_points.min(axis=0)
        max_coords = self.all_points.max(axis=0)
        return min_coords, max_coords

    def calculate_inlet_center_radius(self):
        # Initialize variables for normal accumulation
        normal_sum = np.zeros(3)
        num_triangles = self.mesh_data.v0.shape[0]

        # Calculate averaged normal
        for i in range(num_triangles):
            p1, p2, p3 = self.mesh_data.v0[i], self.mesh_data.v1[i], self.mesh_data.v2[i]
            normal = np.cross(p2 - p1, p3 - p1)
            normal = normal / np.linalg.norm(normal)
            normal_sum += normal

        average_normal = normal_sum / num_triangles
        average_normal = average_normal / np.linalg.norm(average_normal)

        # Calculate centroid and project onto plane
        centroid = np.mean(self.all_points, axis=0)
        distance_to_plane = np.dot(centroid - centroid, average_normal)
        projected_centroid = centroid - distance_to_plane * average_normal

        # Project points onto inlet plane
        points_2d = self.all_points[:, :2]

        # Calculate area and perimeter using a convex hull
        hull = ConvexHull(points_2d)
        area = hull.volume
        perimeter = hull.area

        # Calculate hydraulic radius
        hydraulic_radius = (2 * area) / perimeter  # assuming a scaling factor of 10^-3

        return projected_centroid, hydraulic_radius, average_normal

    def calculate_surface_area(self):
        total_area = 0.0
        for i in range(len(self.mesh_data.vectors)):
            p0, p1, p2 = self.mesh_data.vectors[i]
            triangle_area = 0.5 * np.linalg.norm(np.cross(p1 - p0, p2 - p0))
            total_area += triangle_area
        return total_area


