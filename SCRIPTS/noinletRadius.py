import os
import numpy as np
from stl import mesh
from scipy.spatial import ConvexHull
from numpy.linalg import norm
from SCRIPTS.logger import Logger

class InletRadiusCalculator:
    def __init__(self, log_file="noinletRadius.log"):
        self.logger = Logger(log_file).get_logger()

    def load_stl_points(self, stl_path):
        """
        Loads an STL file using numpy-stl, returns all triangle vertices as an Nx3 numpy array.
        """
        try:
            stl_mesh = mesh.Mesh.from_file(stl_path)
        except Exception as e:
            self.logger.error(f"Error loading STL file {stl_path}: {e}")
            raise RuntimeError(f"Error loading STL file {stl_path}: {e}")
        
        all_points = np.concatenate([stl_mesh.v0, stl_mesh.v1, stl_mesh.v2], axis=0)
        return all_points

    def compute_average_normal(self, stl_points):
        """
        Computes the average normal by summing face normals for each triangle,
        then normalizing.
        """
        if len(stl_points) % 3 != 0:
            self.logger.error("The STL points array should be a multiple of 3 in size.")
            raise ValueError("The STL points array should be a multiple of 3 in size.")

        # Reshape points into triangles
        triangles = stl_points.reshape(-1, 3, 3)
        v1 = triangles[:, 1] - triangles[:, 0]
        v2 = triangles[:, 2] - triangles[:, 0]
        face_normals = np.cross(v1, v2)

        # Normalize face normals
        face_lengths = np.linalg.norm(face_normals, axis=1)
        valid_faces = face_lengths > 1e-15
        face_normals[valid_faces] /= face_lengths[valid_faces][:, np.newaxis]

        # Compute average normal
        avg_normal = np.mean(face_normals[valid_faces], axis=0)
        if np.linalg.norm(avg_normal) < 1e-15:
            self.logger.error("Average normal is near zero; check geometry.")
            raise ValueError("Average normal is near zero; check geometry.")

        return avg_normal / np.linalg.norm(avg_normal)

    def project_points_onto_plane(self, points_3d, normal_vec):
        """
        Projects a set of 3D points into a 2D plane orthonormal to 'normal_vec'.
        """
        # 1) Centroid
        centroid = np.mean(points_3d, axis=0)
        translated_3d = points_3d - centroid

        # 2) Orthonormal basis in plane
        normal_vec = normal_vec / norm(normal_vec)
        arbitrary_axis = np.array([1, 0, 0])
        if abs(np.dot(normal_vec, arbitrary_axis)) > 0.9:
            arbitrary_axis = np.array([0, 1, 0])

        u = np.cross(normal_vec, arbitrary_axis)
        u /= norm(u)
        v = np.cross(normal_vec, u)
        v /= norm(v)

        # 3) Dot each point with u & v => 2D coords
        n_points = translated_3d.shape[0]
        points_2d = np.zeros((n_points, 2))

        for i in range(n_points):
            points_2d[i, 0] = np.dot(translated_3d[i], u)
            points_2d[i, 1] = np.dot(translated_3d[i], v)

        return translated_3d, points_2d, centroid

    def compute_inlet_radius(self, stl_points, scale_factor=1.0):
        """
        Main driver for computing an inlet radius for an arbitrarily oriented patch.
        """
        if (len(stl_points) % 3) != 0:
            self.logger.error("STL points not a multiple of 3. Check data integrity.")
            raise ValueError("STL points not a multiple of 3. Check data integrity.")

        # 1) Compute average normal
        avg_normal = self.compute_average_normal(stl_points)

        # 2) Project 3D points to 2D plane
        translated_3d, points_2d, centroid = self.project_points_onto_plane(stl_points, avg_normal)

        # 3) Convex hull in 2D
        if len(points_2d) < 3:
            self.logger.error("Not enough points to compute a hull. Check geometry.")
            raise ValueError("Not enough points to compute a hull. Check geometry.")
        hull = ConvexHull(points_2d)
        area_2d = hull.volume     # polygon area in 2D
        perimeter_2d = hull.area  # polygon perimeter in 2D

        # 4) Hydraulic or "equivalent" radius
        radius = (2.0 * area_2d / perimeter_2d) * scale_factor

        return centroid, radius, avg_normal

# ----------------- Example usage -----------------
if __name__ == "__main__":
    calculator = InletRadiusCalculator(log_file="noinletRadius.log")

    # Suppose your STL is 'inlet.stl' in 'CAD/geometry1/inlet.stl'
    stl_path = "/home/jie/AortaCFD-app/CAD/VOL04/inlet.stl"
    if not os.path.isfile(stl_path):
        calculator.logger.error(f"Could not find STL at {stl_path}")
        raise FileNotFoundError(f"Could not find STL at {stl_path}")

    # 1) Load STL and get points
    all_points = calculator.load_stl_points(stl_path)

    # 2) Possibly your STL is in mm, and you want radius in m => scale_factor=1e-3
    scale_factor = 1e-3

    # 3) Compute the radius
    centroid, inlet_radius, inlet_normal = calculator.compute_inlet_radius(all_points, scale_factor)

    calculator.logger.info(f"Inlet Centroid: {centroid}")
    calculator.logger.info(f"Inlet Radius: {inlet_radius}")
    calculator.logger.info(f"Inlet Normal: {inlet_normal}")
