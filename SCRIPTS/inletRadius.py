import os
import numpy as np
from stl import mesh
from scipy.spatial import ConvexHull
from userParameter_HL import GEOMETRY_CASE

class InletRadius:
    def __init__(self, DIRECTORY, STL_FILES):
        self.DIRECTORY = DIRECTORY
        self.STL_FILES = STL_FILES
        self.geometry_case = GEOMETRY_CASE

        # Construct the path to the CAD folder
        self.CAD_FOLDER = os.path.join("CAD", self.geometry_case)

        
        # Find the inlet stl file 
        self.INLET_STL = [f for f in self.STL_FILES if "inlet" in f][0]
        self.INLET_STL_PATH = os.path.join(self.CAD_FOLDER, self.INLET_STL)

        # Debugging: Print the inlet STL file path
        #print(f"Inlet STL File Path: {self.INLET_STL_PATH}")

        self.mesh_data = self.load_mesh()
        self.all_points = self.extract_points()

    def load_mesh(self):
        # Load the STL file
        return mesh.Mesh.from_file(self.INLET_STL_PATH)

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
        hydraulic_radius = (2 * area) / perimeter * 0.001 #assuming a scaling factor of 10^-3

        return projected_centroid, hydraulic_radius, average_normal

# Example of how to use the InletRadius class
if __name__ == "__main__":
    # Define the directory and STL files
    directory = "/home/y95228da/Desktop/Cardio-app-Dania/Cardio-app-Dania"
    stl_files = ["inlet.stl", "outlet1.stl", "outlet2.stl", "wall.stl"]

    # Create an instance of InletRadius
    inlet_radius_calculator = InletRadius(directory, stl_files)

    # Call the method to calculate inlet center, radius, and normal
    inlet_center, inlet_radius, inlet_normal = inlet_radius_calculator.calculate_inlet_center_radius()

    # Print the results
    #print("Inlet Center:", inlet_center)
    #print("Inlet Radius:", inlet_radius)
    #print("Inlet Normal:", inlet_normal)
