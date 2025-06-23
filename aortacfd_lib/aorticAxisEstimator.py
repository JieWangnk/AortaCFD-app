import os
import numpy as np
from sklearn.decomposition import PCA
from stl import mesh as np_stl_mesh # Using an alias for clarity
from .utils.logger import Logger # Will be passed in
from .utils.patch_processing import PatchProcessing # Will be passed in

class AorticAxisEstimatorError(Exception):
    """Custom exception for AorticAxisEstimator errors."""
    pass

class AorticAxisEstimator:
    """
    Estimates a robust principal orientation axis for an aorta by combining
    Principal Component Analysis (PCA) of the aortic wall with a vector
    derived from inlet and outlet centroids.
    """
    def __init__(self,
                 wall_stl_full_path: str,
                 inlet_patch_keyword: str,
                 outlet_patch_keywords: list,
                 tri_surface_dir: str,
                 all_stl_filenames_in_trisurface: list,
                 patch_processing_class_ref: type,
                 scale_factor: float,
                 logger_instance):
        """
        Initializes the AorticAxisEstimator.

        Args:
            wall_stl_full_path (str): Full path to the main aortic wall STL file.
            inlet_patch_keyword (str): Keyword to identify the inlet STL (e.g., "inlet").
            outlet_patch_keywords (list): List of keywords for outlet STLs (e.g., ["outlet1", "outlet2"]).
            tri_surface_dir (str): Path to the 'constant/triSurface' directory.
            all_stl_filenames_in_trisurface (list): List of all STL filenames (basenames)
                                                   present in tri_surface_dir.
            patch_processing_class_ref (type): The PatchProcessing class itself.
            scale_factor (float): Factor to scale STL coordinates (e.g., 1e-3 for mm to m).
            logger_instance: An instance of your Logger class.
        """
        self.wall_stl_full_path = wall_stl_full_path
        self.inlet_patch_keyword = inlet_patch_keyword
        self.outlet_patch_keywords = outlet_patch_keywords
        self.tri_surface_dir = tri_surface_dir
        self.all_stl_filenames_in_trisurface = all_stl_filenames_in_trisurface
        self.patch_processing_class_ref = patch_processing_class_ref
        self.scale_factor = scale_factor
        self.logger = logger_instance

        self.wall_points_scaled = None
        self.raw_pca_axis = None
        self.inlet_centroid_val = None
        self.avg_outlet_centroid_val = None
        self.inlet_outlet_axis_aligned = None
        self.final_combined_axis = None

        self.logger.info("AorticAxisEstimator initialized.")
        self._process()

    def _load_and_scale_wall_points(self):
        """Loads the wall STL, extracts unique vertices, and scales them."""
        try:
            self.logger.info(f"Loading wall STL for PCA: {self.wall_stl_full_path}")
            if not os.path.exists(self.wall_stl_full_path):
                raise FileNotFoundError(f"Wall STL file not found: {self.wall_stl_full_path}")

            wall_mesh = np_stl_mesh.Mesh.from_file(self.wall_stl_full_path)
            unique_vertices = np.unique(wall_mesh.vectors.reshape(-1, 3), axis=0)

            if unique_vertices.shape[0] < 3:
                self.logger.error("Wall STL has insufficient unique points for PCA.")
                raise AorticAxisEstimatorError("Wall STL insufficient unique points for PCA.")

            self.wall_points_scaled = unique_vertices * self.scale_factor
            self.logger.info(f"Wall STL loaded: {self.wall_points_scaled.shape[0]} unique scaled points.")
        except Exception as e:
            self.logger.error(f"Error loading or scaling wall STL {self.wall_stl_full_path}: {e}")
            raise AorticAxisEstimatorError(f"Failed to load/scale wall STL: {e}")

    def _get_patch_centroid_by_keyword(self, patch_keyword: str) -> np.ndarray | None:
        """
        Calculates the centroid of a specific patch using the PatchProcessing class.
        """
        self.logger.info(f"Calculating centroid for patch with keyword: '{patch_keyword}'")
        try:
            # Instantiate the user's PatchProcessing class
            patch_processor = self.patch_processing_class_ref(
                DIRECTORY=self.tri_surface_dir,
                STL_FILES=self.all_stl_filenames_in_trisurface,
                PATH_NAME=patch_keyword,
                # log_file can be defaulted by PatchProcessing or passed if needed
            )
            # calculate_inlet_center_radius returns (centroid, radius, normal)
            centroid, _, _ = patch_processor.calculate_inlet_center_radius(
                scale_factor=self.scale_factor
            )
            if centroid is None: # Should be handled by PatchProcessing raising an error
                self.logger.warning(f"PatchProcessing returned None centroid for {patch_keyword}.")
                return None
            self.logger.info(f"Centroid for '{patch_keyword}': {centroid}")
            return centroid
        except FileNotFoundError as e: # If PatchProcessing can't find the STL by keyword
            self.logger.error(f"STL file for patch keyword '{patch_keyword}' not found by PatchProcessing: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting centroid for patch '{patch_keyword}' via PatchProcessing: {e}")
            return None

    def _process(self):
        """Orchestrates the steps to calculate the combined aortic axis."""
        try:
            self._load_and_scale_wall_points()

            # Get inlet centroid
            self.inlet_centroid_val = self._get_patch_centroid_by_keyword(self.inlet_patch_keyword)
            if self.inlet_centroid_val is None:
                raise AorticAxisEstimatorError(f"Failed to get inlet centroid for keyword '{self.inlet_patch_keyword}'.")

            # Get outlet centroids and calculate average
            outlet_centroids = []
            for keyword in self.outlet_patch_keywords:
                centroid = self._get_patch_centroid_by_keyword(keyword)
                if centroid is not None:
                    outlet_centroids.append(centroid)
                else:
                    self.logger.warning(f"Could not get centroid for outlet keyword '{keyword}', skipping.")

            if not outlet_centroids:
                raise AorticAxisEstimatorError("No outlet centroids could be calculated.")
            self.avg_outlet_centroid_val = np.mean(np.array(outlet_centroids), axis=0)
            self.logger.info(f"Average outlet centroid: {self.avg_outlet_centroid_val}")

            # Calculate PCA axis
            pca = PCA(n_components=1)
            pca.fit(self.wall_points_scaled)
            self.raw_pca_axis = pca.components_[0]
            self.raw_pca_axis = self.raw_pca_axis / np.linalg.norm(self.raw_pca_axis) # Ensure unit vector
            self.logger.info(f"Raw PCA primary axis: {self.raw_pca_axis}")

            # Calculate Inlet-Outlet axis
            inlet_outlet_vector = self.avg_outlet_centroid_val - self.inlet_centroid_val
            norm_io_vector = np.linalg.norm(inlet_outlet_vector)
            if norm_io_vector < 1e-9: # Threshold for zero vector
                raise AorticAxisEstimatorError("Inlet and average outlet centroids are coincident or too close.")
            self.inlet_outlet_axis_aligned = inlet_outlet_vector / norm_io_vector
            self.logger.info(f"Inlet-Outlet aligned axis: {self.inlet_outlet_axis_aligned}")

            # Align PCA Axis using Inlet-Outlet Vector
            if np.dot(self.raw_pca_axis, self.inlet_outlet_axis_aligned) < 0:
                self.final_combined_axis = -self.raw_pca_axis
                self.logger.info(f"PCA axis flipped. Aligned PCA axis: {self.final_combined_axis}")
            else:
                self.final_combined_axis = self.raw_pca_axis
                self.logger.info(f"PCA axis already aligned. Final combined axis: {self.final_combined_axis}")

        except AorticAxisEstimatorError as e: # Catch custom errors from this class
            self.logger.error(f"Error during AorticAxisEstimator processing: {e}")
            self.final_combined_axis = None # Ensure it's None on failure
        except Exception as e:
            self.logger.error(f"Unexpected error during AorticAxisEstimator processing: {e}")
            self.final_combined_axis = None # Ensure it's None on failure

    def get_combined_axis(self) -> np.ndarray | None:
        """
        Returns the calculated combined aortic axis.

        Returns:
            np.ndarray: A 3D numpy array representing the normalized combined axis,
                        or None if calculation failed or was not performed.
        """
        if self.final_combined_axis is None:
            self.logger.warning("Combined axis requested but not successfully calculated or process not run.")
        return self.final_combined_axis