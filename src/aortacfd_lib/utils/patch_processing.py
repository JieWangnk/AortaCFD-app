import os
import numpy as np
from stl import mesh
from scipy.spatial import ConvexHull
from .logger import Logger

class PatchProcessing:
    """
    A class that loads a specified patch (e.g., inlet/outlet) from an STL file
    and can compute properties like bounding box, surface area, or an "equivalent
    inlet radius" for an arbitrarily oriented patch.
    """
    def __init__(self, tri_surface_dir: str, patch_name_to_load: str):
        """
        The constructor is now simple. It just needs the path to the
        directory containing all STLs and the name of the specific patch to load.
        """
        self.tri_surface_dir = tri_surface_dir #
        self.patch_name = patch_name_to_load #
        self.log = Logger("patch_processing").get_logger() #

        self.stl_path = os.path.join(self.tri_surface_dir, f"{self.patch_name}.stl") #

        if not os.path.exists(self.stl_path): #
            self.log.error(f"STL file not found: {self.stl_path}") #
            raise FileNotFoundError(f"STL file not found: {self.stl_path}") #

        self.mesh_data = self.load_mesh(self.stl_path) #
        self.all_points = self.extract_points() #

        # --- Robustness checks ---
        num_triangles = len(self.mesh_data.vectors) #
        if num_triangles < 10: #
            # CORRECTED: Use self.patch_name instead of the old self.STL variable
            self.log.warning(
                f"STL patch '{self.patch_name}' contains very few triangles ({num_triangles}). " #
                "Results may be unreliable or indicate a degenerate or incomplete patch."
            )

    def load_mesh(self, path): #
        """Loads an STL file using numpy-stl."""
        try:
            return mesh.Mesh.from_file(path) #
        except Exception as e:
            self.log.error(f"Error loading STL file {path}: {e}") #
            raise RuntimeError(f"Error loading STL file {path}: {e}") #

    def extract_points(self): #
        """
        Extracts all triangle vertices from the loaded mesh into
        a single Nx3 NumPy array.
        """
        return np.concatenate([self.mesh_data.v0, self.mesh_data.v1, self.mesh_data.v2], axis=0) #

    def get_bounding_box(self): #
        """
        Returns the axis-aligned bounding box for the patch as (min_coords, max_coords).
        """
        min_coords = self.all_points.min(axis=0) #
        max_coords = self.all_points.max(axis=0) #
        return min_coords, max_coords #

    def compute_average_normal(self): #
        """
        Computes the average normal by summing face normals for each triangle.
        """
        if self.mesh_data.vectors is None or len(self.mesh_data.vectors) == 0: #
            self.log.error("Mesh data contains no vectors (triangles).") #
            raise ValueError("Mesh data contains no vectors (triangles).") #

        normal_sum = np.zeros(3) #
        num_triangles = len(self.mesh_data.vectors) #

        for i in range(num_triangles): #
            p1, p2, p3 = self.mesh_data.vectors[i] #
            v1 = p2 - p1 #
            v2 = p3 - p1 #
            face_normal = np.cross(v1, v2) #
            norm_len = np.linalg.norm(face_normal) #
            if norm_len > 1e-15: #
                face_normal /= norm_len #
            normal_sum += face_normal #

        avg_normal = normal_sum / num_triangles #
        norm_avg = np.linalg.norm(avg_normal) #
        if norm_avg < 1e-15: #
            self.log.error("Average normal is near zero; check STL geometry.") #
            raise ValueError("Average normal is near zero; check STL geometry.") #
        return avg_normal / norm_avg #

    def project_points_onto_plane(self, points_3d, normal_vec): #
        """
        Projects an Nx3 array of points into a 2D plane orthonormal to 'normal_vec'.
        """
        centroid = np.mean(points_3d, axis=0) #
        translated_3d = points_3d - centroid #

        normal_vec = normal_vec / np.linalg.norm(normal_vec) #
        ref_axis = np.array([1, 0, 0]) #
        if abs(np.dot(normal_vec, ref_axis)) > 0.9: #
            ref_axis = np.array([0, 1, 0]) #

        u = np.cross(normal_vec, ref_axis) #
        u /= np.linalg.norm(u) #
        v = np.cross(normal_vec, u) #
        v /= np.linalg.norm(v) #

        points_2d = np.zeros((len(translated_3d), 2)) #
        for i in range(len(translated_3d)): #
            points_2d[i, 0] = np.dot(translated_3d[i], u) #
            points_2d[i, 1] = np.dot(translated_3d[i], v) #

        return translated_3d, points_2d, centroid #

    def calculate_inlet_center_radius(self, scale_factor=1.0): # scale_factor is now optional
        """
        Computes center and an equivalent radius for the patch in its
        original, unscaled units.
        """
        unique_patch_points = np.unique(self.mesh_data.vectors.reshape(-1, 3), axis=0) #
        # Check for sufficient points for analysis
        if len(unique_patch_points) < 3:
            raise ValueError(f"Insufficient points ({len(unique_patch_points)}) for geometry analysis")

        avg_normal = self.compute_average_normal() #
        # centroid is now in raw units (mm)
        _, points_2d, centroid = self.project_points_onto_plane(unique_patch_points, avg_normal) #
        
        hull = ConvexHull(points_2d) #
        area_2d = hull.volume #
        perimeter_2d = hull.area #

        final_centroid = centroid * scale_factor # This is now in mm
        final_radius = (2.0 * area_2d / perimeter_2d) * scale_factor# This is now in mm

        return final_centroid, final_radius, avg_normal #

    def calculate_surface_area(self, scale_factor=1e-3): #
        """
        Computes the total surface area of the patch by summing triangle areas.
        """
        vectors = self.mesh_data.vectors #
        cross_products = np.cross(vectors[:, 1] - vectors[:, 0], vectors[:, 2] - vectors[:, 0]) #
        triangle_areas = 0.5 * np.linalg.norm(cross_products, axis=1) #
        total_area = np.sum(triangle_areas) * scale_factor**2 #
        return total_area #

    def compute_rotation_vector(self, vector1, vector2):
        """
        Computes the rotation vector (axis and angle) required to rotate from vector1 to vector2.
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


