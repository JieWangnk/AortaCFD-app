import os
from collections import defaultdict

import numpy as np
from stl import mesh
from scipy.spatial import ConvexHull
from .logger import Logger


def compute_inward_normal(tri_surface_dir: str, inlet_name: str, wall_name: str = "wall",
                          log=None) -> np.ndarray:
    """Compute the inward-pointing unit normal of an inlet patch.

    Uses a purely local geometric signal: the first ring of wall
    triangles adjacent to the inlet boundary edges.  Their centroids
    are always offset from the inlet plane toward the tube interior,
    so the vector from inlet centroid → ring centroid gives a reliable
    inward direction independent of outlet positions or downstream
    geometry.

    Parameters
    ----------
    tri_surface_dir : str
        Path to ``constant/triSurface/`` (STLs already in metres).
    inlet_name : str
        Patch name (e.g. ``"inlet"``).
    wall_name : str
        Wall patch name (default ``"wall"``).
    log : logger, optional
        Logger instance.

    Returns
    -------
    np.ndarray
        Unit vector pointing into the tube from the inlet centre.
    """
    inlet_path = os.path.join(tri_surface_dir, f"{inlet_name}.stl")
    wall_path = os.path.join(tri_surface_dir, f"{wall_name}.stl")

    inlet_mesh = mesh.Mesh.from_file(inlet_path)
    wall_mesh = mesh.Mesh.from_file(wall_path)

    # --- Inlet centroid and face normal ---
    inlet_verts = inlet_mesh.vectors  # (N, 3, 3)
    inlet_centroid = np.mean(inlet_verts.reshape(-1, 3), axis=0)

    # Area-weighted average normal
    cross = np.cross(inlet_verts[:, 1] - inlet_verts[:, 0],
                     inlet_verts[:, 2] - inlet_verts[:, 0])
    avg_normal = cross.sum(axis=0)
    avg_normal = avg_normal / np.linalg.norm(avg_normal)

    # --- Find shared edges between inlet and wall ---
    # Round coordinates to merge coincident vertices (STL duplication)
    decimals = 8

    def _edge_set(vectors):
        """Return a set of canonical edge keys from triangle vertices."""
        edges = set()
        for tri in vectors:
            pts = [tuple(np.round(tri[i], decimals)) for i in range(3)]
            for i in range(3):
                edge = tuple(sorted([pts[i], pts[(i + 1) % 3]]))
                edges.add(edge)
        return edges

    inlet_edges = _edge_set(inlet_verts)

    # Build wall edge → triangle-index map
    wall_verts = wall_mesh.vectors
    wall_edge_to_tri = defaultdict(list)
    for ti, tri in enumerate(wall_verts):
        pts = [tuple(np.round(tri[i], decimals)) for i in range(3)]
        for i in range(3):
            edge = tuple(sorted([pts[i], pts[(i + 1) % 3]]))
            wall_edge_to_tri[edge].append(ti)

    # Wall triangles that share an edge with the inlet patch
    ring_tri_indices = set()
    shared_edge_count = 0
    for edge in inlet_edges:
        if edge in wall_edge_to_tri:
            shared_edge_count += 1
            ring_tri_indices.update(wall_edge_to_tri[edge])

    if log:
        log.info(f"Inlet inward detection: {shared_edge_count} shared edges, "
                 f"{len(ring_tri_indices)} adjacent wall triangles")

    if not ring_tri_indices:
        # Fallback: use wall centroid (less local but still inside tube)
        if log:
            log.warning("No shared edges found between inlet and wall — "
                        "falling back to wall centroid")
        wall_centroid = np.mean(wall_verts.reshape(-1, 3), axis=0)
        direction = wall_centroid - inlet_centroid
        direction = direction / np.linalg.norm(direction)
        if np.dot(avg_normal, direction) < 0:
            return -avg_normal
        return avg_normal

    # Centroid of the adjacent wall ring
    ring_tris = wall_verts[list(ring_tri_indices)]  # (M, 3, 3)
    ring_centroid = np.mean(ring_tris.reshape(-1, 3), axis=0)

    # Inward direction = from inlet centre toward the wall ring
    inward_vec = ring_centroid - inlet_centroid
    inward_vec = inward_vec / np.linalg.norm(inward_vec)

    # Orient the face normal to align with the inward direction
    if np.dot(avg_normal, inward_vec) < 0:
        inward_normal = -avg_normal
    else:
        inward_normal = avg_normal

    if log:
        log.info(f"Inlet inward normal: [{inward_normal[0]:.4f}, "
                 f"{inward_normal[1]:.4f}, {inward_normal[2]:.4f}]")

    return inward_normal

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

    def calculate_inlet_center_radius(self):
        """
        Computes center and an equivalent radius for the patch.

        NOTE: STL files in constant/triSurface/ are PRE-SCALED to meters
        during case setup. No scale_factor needed - values returned in meters.

        Returns:
            tuple: (centroid, radius, normal) all in meters
        """
        unique_patch_points = np.unique(self.mesh_data.vectors.reshape(-1, 3), axis=0)
        # Check for sufficient points for analysis
        if len(unique_patch_points) < 3:
            raise ValueError(f"Insufficient points ({len(unique_patch_points)}) for geometry analysis")

        avg_normal = self.compute_average_normal()
        # centroid is in mesh units (meters, since STLs are pre-scaled)
        _, points_2d, centroid = self.project_points_onto_plane(unique_patch_points, avg_normal)

        hull = ConvexHull(points_2d)
        area_2d = hull.volume
        perimeter_2d = hull.area

        # Equivalent radius from hydraulic diameter concept
        radius = 2.0 * area_2d / perimeter_2d

        return centroid, radius, avg_normal

    def calculate_surface_area(self):
        """
        Computes the total surface area of the patch by summing triangle areas.

        NOTE: STL files in constant/triSurface/ are PRE-SCALED to meters
        during case setup. No scale_factor needed - area returned in m².

        Returns:
            float: Surface area in m²
        """
        vectors = self.mesh_data.vectors
        cross_products = np.cross(vectors[:, 1] - vectors[:, 0], vectors[:, 2] - vectors[:, 0])
        triangle_areas = 0.5 * np.linalg.norm(cross_products, axis=1)
        total_area = np.sum(triangle_areas)
        return total_area

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


