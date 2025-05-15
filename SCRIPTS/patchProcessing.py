import os
import numpy as np
from stl import mesh
from scipy.spatial import ConvexHull
import logging

logging.basicConfig(level=logging.INFO)

class PatchProcessing:
    """
    A class that loads a specified patch (e.g., inlet/outlet) from an STL file 
    and can compute properties like bounding box, surface area, or an "equivalent 
    inlet radius" for an arbitrarily oriented patch.
    """

    def __init__(self, DIRECTORY, STL_FILES, PATH_NAME):
        self.DIRECTORY = DIRECTORY
        self.STL_FILES = STL_FILES

        # Points to constant/triSurface in your OpenFOAM case directory
        #self.CAD_FOLDER = os.path.join("constant", "triSurface")

        # Find the STL file matching PATH_NAME (e.g., "inlet")
        self.STL = [f for f in self.STL_FILES if PATH_NAME in f][0]
        self.STL_PATH = os.path.join(self.DIRECTORY, self.STL)

        if not os.path.exists(self.STL_PATH):
            raise FileNotFoundError(f"STL file not found: {self.STL_PATH}")

        # Load the mesh and store vertices
        self.mesh_data = self.load_mesh(self.STL_PATH)
        self.all_points = self.extract_points()  # Nx3 array

    def load_mesh(self, path):
        """Loads an STL file using numpy-stl."""
        try:
            return mesh.Mesh.from_file(path)
        except Exception as e:
            raise RuntimeError(f"Error loading STL file {path}: {e}")

    def extract_points(self):
        """
        Extracts all triangle vertices from the loaded mesh into 
        a single Nx3 NumPy array.
        """
        return np.concatenate([self.mesh_data.v0, self.mesh_data.v1, self.mesh_data.v2], axis=0)

    def get_bounding_box(self):
        """
        Returns the axis-aligned bounding box for the patch as (min_coords, max_coords).
        """
        min_coords = self.all_points.min(axis=0)
        max_coords = self.all_points.max(axis=0)
        return min_coords, max_coords

    def compute_average_normal(self, points_3n):
        """
        Computes the average normal by summing face normals for each triangle
        (grouped in sets of three points).
        """
        if len(points_3n) % 3 != 0:
            raise ValueError("Points array should be a multiple of 3 in size.")
        num_triangles = len(points_3n) // 3
        normal_sum = np.zeros(3)

        for i in range(num_triangles):
            p1 = points_3n[3*i]
            p2 = points_3n[3*i + 1]
            p3 = points_3n[3*i + 2]
            v1 = p2 - p1
            v2 = p3 - p1
            face_normal = np.cross(v1, v2)
            norm_len = np.linalg.norm(face_normal)
            if norm_len > 1e-15:
                face_normal /= norm_len
            normal_sum += face_normal

        avg_normal = normal_sum / num_triangles
        norm_avg = np.linalg.norm(avg_normal)
        if norm_avg < 1e-15:
            raise ValueError("Average normal is near zero; check STL geometry.")
        return avg_normal / norm_avg

    def project_points_onto_plane(self, points_3d, normal_vec):
        """
        Projects an Nx3 array of points into a 2D plane orthonormal to 'normal_vec'.
        Steps:
          1) Translate to centroid = 0
          2) Create vectors u, v orthonormal to normal_vec
          3) Compute new coords: (x dot u, x dot v)
        Returns:
          - translated_3d (points centered at origin)
          - points_2d (the Nx2 projected coords)
          - centroid (original centroid)
        """
        centroid = np.mean(points_3d, axis=0)
        translated_3d = points_3d - centroid

        normal_vec = normal_vec / np.linalg.norm(normal_vec)
        # pick an arbitrary axis not parallel to normal
        ref_axis = np.array([1, 0, 0])
        if abs(np.dot(normal_vec, ref_axis)) > 0.9:
            ref_axis = np.array([0, 1, 0])

        u = np.cross(normal_vec, ref_axis)
        u /= np.linalg.norm(u)
        v = np.cross(normal_vec, u)
        v /= np.linalg.norm(v)

        points_2d = np.zeros((len(translated_3d), 2))
        for i in range(len(translated_3d)):
            points_2d[i, 0] = np.dot(translated_3d[i], u)
            points_2d[i, 1] = np.dot(translated_3d[i], v)

        return translated_3d, points_2d, centroid

    def calculate_inlet_center_radius(self, scale_factor=1e-3):
        """
        Computes a hydraulic/equivalent radius for an arbitrarily oriented patch:
          1) Average normal via face-based summation.
          2) Project points to plane orthonormal to that normal.
          3) Compute convex hull area => 'volume' in 2D, perimeter => 'area' in 2D.
          4) Radius = 2*area / perimeter, then multiplied by scale_factor.

        Args:
            scale_factor (float): If your STL is in mm and you want radius in meters, 
                                  use 1e-3.

        Returns:
            (centroid, radius, average_normal)
        """
        # 1) Ensure points_3n has sets of 3 points for each triangle
        #    Our self.all_points is Nx3, but each face is repeated. It's okay as is,
        #    or we can unify them. We'll just proceed.
        points_3n = self.all_points
        if len(points_3n) < 9:
            raise ValueError("Not enough points to compute a valid inlet radius.")

        # 2) Compute average normal
        avg_normal = self.compute_average_normal(points_3n)

        # 3) Project to 2D
        translated_3d, points_2d, centroid = self.project_points_onto_plane(points_3n, avg_normal)

        # centroid scaled by scale_factor
        centroid *= scale_factor

        # 4) Use 2D convex hull to find area + perimeter
        if len(points_2d) < 3:
            raise ValueError("Not enough points for a hull. Patch is degenerate.")

        hull = ConvexHull(points_2d)
        area_2d = hull.volume      # polygon area in 2D
        perimeter_2d = hull.area   # polygon perimeter in 2D

        # 5) Hydraulic radius
        radius = 2.0 * area_2d / perimeter_2d
        radius *= scale_factor

        return centroid, radius, avg_normal

    def calculate_surface_area(self, scale_factor=1e-3):
        """
        Computes the total surface area of the patch by summing triangle areas.
        This is a 3D area, not the cross-sectional or projected area.
        """
        vectors = self.mesh_data.vectors
        cross_products = np.cross(vectors[:, 1] - vectors[:, 0], vectors[:, 2] - vectors[:, 0])
        triangle_areas = 0.5 * np.linalg.norm(cross_products, axis=1)
        total_area = np.sum(triangle_areas)

        # scale by scale_factor
        total_area *= scale_factor**2
        return total_area

    def compute_rotation_vector(self, vector1, vector2):
        """
        Computes the rotation vector (axis and angle) required to rotate from vector1 to vector2.

        Args:
            vector1 (np.ndarray): The starting vector (3D).
            vector2 (np.ndarray): The target vector (3D).

        Returns:
            tuple: (rotation_axis, rotation_angle)
                - rotation_axis (np.ndarray): The unit vector representing the axis of rotation.
                - rotation_angle (float): The angle of rotation in radians.
        """
        v1 = vector1 / np.linalg.norm(vector1)
        v2 = vector2 / np.linalg.norm(vector2)
        rotation_axis = np.cross(v1, v2)
        axis_norm = np.linalg.norm(rotation_axis)

        if axis_norm < 1e-15:
            if np.allclose(v1, v2):
                return np.zeros(3), 0.0
            else:
                orthogonal_axis = np.array([1, 0, 0]) if abs(v1[0]) < 0.9 else np.array([0, 1, 0])
                rotation_axis = np.cross(v1, orthogonal_axis)
                rotation_axis /= np.linalg.norm(rotation_axis)
                return rotation_axis, np.pi

        rotation_axis /= axis_norm
        rotation_angle = np.arccos(np.clip(np.dot(v1, v2), -1.0, 1.0))
        return rotation_axis, rotation_angle

# -------------- Example Usage --------------
if __name__ == "__main__":
    directory = "/home/jie/AortaCFD-app/OPENFOAM/VOL04_coarse/"
    stl_files = ["inlet.stl", "outlet1.stl", "outlet2.stl"]

    logging.info("Loading STL file...")
    patch_processor = PatchProcessing(directory, stl_files, "inlet")

    min_coords, max_coords = patch_processor.get_bounding_box()
    logging.info(f"Bounding box: {min_coords}, {max_coords}")

    center, inlet_radius, inlet_normal = patch_processor.calculate_inlet_center_radius(scale_factor=1e-3)
    logging.info(f"Inlet Center: {center}")
    logging.info(f"Inlet Radius (m): {inlet_radius}")
    logging.info(f"Inlet Normal: {inlet_normal}")

    area_3d = patch_processor.calculate_surface_area()
    logging.info(f"3D Surface Area: {area_3d}")


