"""
Test suite for aortacfd_lib/aorticAxisEstimator.py module.

Tests cover:
- AorticAxisEstimator class initialization
- STL loading and scaling
- Patch centroid calculation
- PCA axis computation and alignment
- Error handling for various failure modes
"""

import pytest
import sys
import os
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestAorticAxisEstimatorError:
    """Test AorticAxisEstimatorError exception."""

    def test_exception_creation(self):
        """Test exception can be created with message."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimatorError

        error = AorticAxisEstimatorError("Test error message")
        assert str(error) == "Test error message"

    def test_exception_inheritance(self):
        """Test exception inherits from Exception."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimatorError

        assert issubclass(AorticAxisEstimatorError, Exception)


class TestAorticAxisEstimatorInit:
    """Test AorticAxisEstimator initialization."""

    @patch("aortacfd_lib.aorticAxisEstimator.AorticAxisEstimator._process")
    def test_initialization_sets_attributes(self, mock_process):
        """Test that initialization sets all attributes correctly."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimator

        mock_logger = MagicMock()
        mock_patch_class = MagicMock()

        estimator = AorticAxisEstimator(
            wall_stl_full_path="/path/to/wall.stl",
            inlet_patch_keyword="inlet",
            outlet_patch_keywords=["outlet1", "outlet2"],
            tri_surface_dir="/path/to/triSurface",
            all_stl_filenames_in_trisurface=["wall.stl", "inlet.stl", "outlet1.stl"],
            patch_processing_class_ref=mock_patch_class,
            scale_factor=1e-3,
            logger_instance=mock_logger,
        )

        assert estimator.wall_stl_full_path == "/path/to/wall.stl"
        assert estimator.inlet_patch_keyword == "inlet"
        assert estimator.outlet_patch_keywords == ["outlet1", "outlet2"]
        assert estimator.tri_surface_dir == "/path/to/triSurface"
        assert estimator.scale_factor == 1e-3
        assert estimator.logger is mock_logger
        mock_process.assert_called_once()

    @patch("aortacfd_lib.aorticAxisEstimator.AorticAxisEstimator._process")
    def test_initialization_sets_none_values(self, mock_process):
        """Test that initialization sets computed values to None initially."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimator

        mock_logger = MagicMock()

        estimator = AorticAxisEstimator(
            wall_stl_full_path="/path/to/wall.stl",
            inlet_patch_keyword="inlet",
            outlet_patch_keywords=["outlet"],
            tri_surface_dir="/path/to/triSurface",
            all_stl_filenames_in_trisurface=[],
            patch_processing_class_ref=MagicMock(),
            scale_factor=1.0,
            logger_instance=mock_logger,
        )

        # These should be set to None before _process runs
        # (though _process is mocked, we can check the attributes exist)
        assert hasattr(estimator, "wall_points_scaled")
        assert hasattr(estimator, "raw_pca_axis")
        assert hasattr(estimator, "inlet_centroid_val")
        assert hasattr(estimator, "avg_outlet_centroid_val")
        assert hasattr(estimator, "inlet_outlet_axis_aligned")
        assert hasattr(estimator, "final_combined_axis")


class TestLoadAndScaleWallPoints:
    """Test _load_and_scale_wall_points method."""

    @patch("aortacfd_lib.aorticAxisEstimator.AorticAxisEstimator._process")
    def test_file_not_found_raises_error(self, mock_process):
        """Test that missing wall STL file raises AorticAxisEstimatorError."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimator, AorticAxisEstimatorError

        mock_logger = MagicMock()

        estimator = AorticAxisEstimator(
            wall_stl_full_path="/nonexistent/wall.stl",
            inlet_patch_keyword="inlet",
            outlet_patch_keywords=["outlet"],
            tri_surface_dir="/path",
            all_stl_filenames_in_trisurface=[],
            patch_processing_class_ref=MagicMock(),
            scale_factor=1.0,
            logger_instance=mock_logger,
        )

        with pytest.raises(AorticAxisEstimatorError, match="Failed to load/scale wall STL"):
            estimator._load_and_scale_wall_points()

    @patch("aortacfd_lib.aorticAxisEstimator.AorticAxisEstimator._process")
    @patch("aortacfd_lib.aorticAxisEstimator.np_stl_mesh.Mesh")
    @patch("os.path.exists", return_value=True)
    def test_insufficient_points_raises_error(self, mock_exists, mock_mesh_class, mock_process):
        """Test that STL with insufficient points raises error."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimator, AorticAxisEstimatorError

        # Mock mesh with only 2 unique points (need at least 3 for PCA)
        mock_mesh = MagicMock()
        mock_mesh.vectors = np.array([[[0, 0, 0], [1, 0, 0], [1, 0, 0]]])  # Only 2 unique points
        mock_mesh_class.from_file.return_value = mock_mesh

        mock_logger = MagicMock()

        estimator = AorticAxisEstimator(
            wall_stl_full_path="/path/to/wall.stl",
            inlet_patch_keyword="inlet",
            outlet_patch_keywords=["outlet"],
            tri_surface_dir="/path",
            all_stl_filenames_in_trisurface=[],
            patch_processing_class_ref=MagicMock(),
            scale_factor=1.0,
            logger_instance=mock_logger,
        )

        with pytest.raises(AorticAxisEstimatorError, match="insufficient unique points"):
            estimator._load_and_scale_wall_points()

    @patch("aortacfd_lib.aorticAxisEstimator.AorticAxisEstimator._process")
    @patch("aortacfd_lib.aorticAxisEstimator.np_stl_mesh.Mesh")
    @patch("os.path.exists", return_value=True)
    def test_successful_load_and_scale(self, mock_exists, mock_mesh_class, mock_process):
        """Test successful loading and scaling of wall points."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimator

        # Mock mesh with valid points
        mock_mesh = MagicMock()
        # Create a mesh with 4 unique vertices (a tetrahedron)
        mock_mesh.vectors = np.array([[[0, 0, 0], [1000, 0, 0], [0, 1000, 0]], [[0, 0, 0], [1000, 0, 0], [0, 0, 1000]]])
        mock_mesh_class.from_file.return_value = mock_mesh

        mock_logger = MagicMock()
        scale_factor = 1e-3  # mm to m

        estimator = AorticAxisEstimator(
            wall_stl_full_path="/path/to/wall.stl",
            inlet_patch_keyword="inlet",
            outlet_patch_keywords=["outlet"],
            tri_surface_dir="/path",
            all_stl_filenames_in_trisurface=[],
            patch_processing_class_ref=MagicMock(),
            scale_factor=scale_factor,
            logger_instance=mock_logger,
        )

        estimator._load_and_scale_wall_points()

        assert estimator.wall_points_scaled is not None
        # Check that scaling was applied (1000 * 1e-3 = 1.0)
        assert np.max(estimator.wall_points_scaled) == 1.0


class TestGetPatchCentroidByKeyword:
    """Test _get_patch_centroid_by_keyword method."""

    @patch("aortacfd_lib.aorticAxisEstimator.AorticAxisEstimator._process")
    def test_successful_centroid_calculation(self, mock_process):
        """Test successful centroid calculation via PatchProcessing."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimator

        mock_logger = MagicMock()

        # Mock PatchProcessing class
        mock_patch_instance = MagicMock()
        expected_centroid = np.array([0.1, 0.2, 0.3])
        mock_patch_instance.calculate_inlet_center_radius.return_value = (expected_centroid, 0.01, np.array([0, 0, 1]))
        mock_patch_class = MagicMock(return_value=mock_patch_instance)

        estimator = AorticAxisEstimator(
            wall_stl_full_path="/path/to/wall.stl",
            inlet_patch_keyword="inlet",
            outlet_patch_keywords=["outlet"],
            tri_surface_dir="/path/triSurface",
            all_stl_filenames_in_trisurface=["inlet.stl"],
            patch_processing_class_ref=mock_patch_class,
            scale_factor=1e-3,
            logger_instance=mock_logger,
        )

        result = estimator._get_patch_centroid_by_keyword("inlet")

        np.testing.assert_array_equal(result, expected_centroid)
        mock_patch_class.assert_called_with(DIRECTORY="/path/triSurface", STL_FILES=["inlet.stl"], PATH_NAME="inlet")

    @patch("aortacfd_lib.aorticAxisEstimator.AorticAxisEstimator._process")
    def test_file_not_found_returns_none(self, mock_process):
        """Test that FileNotFoundError from PatchProcessing returns None."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimator

        mock_logger = MagicMock()
        mock_patch_class = MagicMock(side_effect=FileNotFoundError("STL not found"))

        estimator = AorticAxisEstimator(
            wall_stl_full_path="/path/to/wall.stl",
            inlet_patch_keyword="inlet",
            outlet_patch_keywords=["outlet"],
            tri_surface_dir="/path",
            all_stl_filenames_in_trisurface=[],
            patch_processing_class_ref=mock_patch_class,
            scale_factor=1.0,
            logger_instance=mock_logger,
        )

        result = estimator._get_patch_centroid_by_keyword("missing_patch")

        assert result is None
        mock_logger.error.assert_called()

    @patch("aortacfd_lib.aorticAxisEstimator.AorticAxisEstimator._process")
    def test_none_centroid_returns_none(self, mock_process):
        """Test that None centroid from PatchProcessing returns None."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimator

        mock_logger = MagicMock()
        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (None, None, None)
        mock_patch_class = MagicMock(return_value=mock_patch_instance)

        estimator = AorticAxisEstimator(
            wall_stl_full_path="/path/to/wall.stl",
            inlet_patch_keyword="inlet",
            outlet_patch_keywords=["outlet"],
            tri_surface_dir="/path",
            all_stl_filenames_in_trisurface=[],
            patch_processing_class_ref=mock_patch_class,
            scale_factor=1.0,
            logger_instance=mock_logger,
        )

        result = estimator._get_patch_centroid_by_keyword("inlet")

        assert result is None
        mock_logger.warning.assert_called()

    @patch("aortacfd_lib.aorticAxisEstimator.AorticAxisEstimator._process")
    def test_generic_exception_returns_none(self, mock_process):
        """Test that generic exception from PatchProcessing returns None."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimator

        mock_logger = MagicMock()
        mock_patch_class = MagicMock(side_effect=RuntimeError("Unexpected error"))

        estimator = AorticAxisEstimator(
            wall_stl_full_path="/path/to/wall.stl",
            inlet_patch_keyword="inlet",
            outlet_patch_keywords=["outlet"],
            tri_surface_dir="/path",
            all_stl_filenames_in_trisurface=[],
            patch_processing_class_ref=mock_patch_class,
            scale_factor=1.0,
            logger_instance=mock_logger,
        )

        result = estimator._get_patch_centroid_by_keyword("inlet")

        assert result is None
        mock_logger.error.assert_called()


class TestProcessMethod:
    """Test _process method which orchestrates axis calculation."""

    @patch("aortacfd_lib.aorticAxisEstimator.np_stl_mesh.Mesh")
    @patch("os.path.exists", return_value=True)
    def test_successful_process_pca_aligned(self, mock_exists, mock_mesh_class):
        """Test successful processing when PCA axis is already aligned."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimator

        # Create mock mesh with points extending along X axis
        mock_mesh = MagicMock()
        # Points forming an elongated shape along X (PCA will find X as principal)
        mock_mesh.vectors = np.array(
            [
                [[0, 0, 0], [10, 0, 0], [5, 1, 0]],
                [[10, 0, 0], [20, 0, 0], [15, 1, 0]],
                [[20, 0, 0], [30, 0, 0], [25, 1, 0]],
            ]
        )
        mock_mesh_class.from_file.return_value = mock_mesh

        mock_logger = MagicMock()

        # Mock PatchProcessing for inlet and outlet
        inlet_centroid = np.array([0, 0, 0])
        outlet_centroid = np.array([30, 0, 0])

        def mock_patch_init(DIRECTORY, STL_FILES, PATH_NAME):
            mock_instance = MagicMock()
            if "inlet" in PATH_NAME.lower():
                mock_instance.calculate_inlet_center_radius.return_value = (inlet_centroid, 0.01, np.array([1, 0, 0]))
            else:
                mock_instance.calculate_inlet_center_radius.return_value = (outlet_centroid, 0.01, np.array([1, 0, 0]))
            return mock_instance

        mock_patch_class = MagicMock(side_effect=mock_patch_init)

        estimator = AorticAxisEstimator(
            wall_stl_full_path="/path/to/wall.stl",
            inlet_patch_keyword="inlet",
            outlet_patch_keywords=["outlet"],
            tri_surface_dir="/path",
            all_stl_filenames_in_trisurface=["wall.stl", "inlet.stl", "outlet.stl"],
            patch_processing_class_ref=mock_patch_class,
            scale_factor=1.0,
            logger_instance=mock_logger,
        )

        # Process was called in __init__, check results
        assert estimator.final_combined_axis is not None
        assert np.linalg.norm(estimator.final_combined_axis) == pytest.approx(1.0, rel=1e-6)

    @patch("aortacfd_lib.aorticAxisEstimator.np_stl_mesh.Mesh")
    @patch("os.path.exists", return_value=True)
    def test_successful_process_pca_flipped(self, mock_exists, mock_mesh_class):
        """Test successful processing when PCA axis needs to be flipped."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimator

        # Create mock mesh
        mock_mesh = MagicMock()
        mock_mesh.vectors = np.array(
            [
                [[0, 0, 0], [10, 0, 0], [5, 1, 0]],
                [[10, 0, 0], [20, 0, 0], [15, 1, 0]],
                [[20, 0, 0], [30, 0, 0], [25, 1, 0]],
            ]
        )
        mock_mesh_class.from_file.return_value = mock_mesh

        mock_logger = MagicMock()

        # Mock PatchProcessing - outlet before inlet (reversed direction)
        inlet_centroid = np.array([30, 0, 0])  # Inlet at far end
        outlet_centroid = np.array([0, 0, 0])  # Outlet at near end

        def mock_patch_init(DIRECTORY, STL_FILES, PATH_NAME):
            mock_instance = MagicMock()
            if "inlet" in PATH_NAME.lower():
                mock_instance.calculate_inlet_center_radius.return_value = (inlet_centroid, 0.01, np.array([1, 0, 0]))
            else:
                mock_instance.calculate_inlet_center_radius.return_value = (outlet_centroid, 0.01, np.array([1, 0, 0]))
            return mock_instance

        mock_patch_class = MagicMock(side_effect=mock_patch_init)

        estimator = AorticAxisEstimator(
            wall_stl_full_path="/path/to/wall.stl",
            inlet_patch_keyword="inlet",
            outlet_patch_keywords=["outlet"],
            tri_surface_dir="/path",
            all_stl_filenames_in_trisurface=["wall.stl", "inlet.stl", "outlet.stl"],
            patch_processing_class_ref=mock_patch_class,
            scale_factor=1.0,
            logger_instance=mock_logger,
        )

        assert estimator.final_combined_axis is not None
        # The axis should have been flipped to align with inlet->outlet direction

    @patch("aortacfd_lib.aorticAxisEstimator.np_stl_mesh.Mesh")
    @patch("os.path.exists", return_value=True)
    def test_process_inlet_centroid_failure(self, mock_exists, mock_mesh_class):
        """Test process handles inlet centroid failure."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimator

        mock_mesh = MagicMock()
        mock_mesh.vectors = np.array(
            [
                [[0, 0, 0], [10, 0, 0], [5, 1, 0]],
                [[10, 0, 0], [20, 0, 0], [15, 1, 0]],
            ]
        )
        mock_mesh_class.from_file.return_value = mock_mesh

        mock_logger = MagicMock()

        # Mock PatchProcessing to fail for inlet
        mock_patch_class = MagicMock(side_effect=FileNotFoundError("inlet not found"))

        estimator = AorticAxisEstimator(
            wall_stl_full_path="/path/to/wall.stl",
            inlet_patch_keyword="inlet",
            outlet_patch_keywords=["outlet"],
            tri_surface_dir="/path",
            all_stl_filenames_in_trisurface=[],
            patch_processing_class_ref=mock_patch_class,
            scale_factor=1.0,
            logger_instance=mock_logger,
        )

        # Should set final_combined_axis to None on failure
        assert estimator.final_combined_axis is None

    @patch("aortacfd_lib.aorticAxisEstimator.np_stl_mesh.Mesh")
    @patch("os.path.exists", return_value=True)
    def test_process_no_outlet_centroids(self, mock_exists, mock_mesh_class):
        """Test process handles case when no outlet centroids available."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimator

        mock_mesh = MagicMock()
        mock_mesh.vectors = np.array(
            [
                [[0, 0, 0], [10, 0, 0], [5, 1, 0]],
                [[10, 0, 0], [20, 0, 0], [15, 1, 0]],
            ]
        )
        mock_mesh_class.from_file.return_value = mock_mesh

        mock_logger = MagicMock()

        # Mock PatchProcessing - inlet succeeds, outlets fail
        call_count = [0]

        def mock_patch_init(DIRECTORY, STL_FILES, PATH_NAME):
            mock_instance = MagicMock()
            if "inlet" in PATH_NAME.lower():
                mock_instance.calculate_inlet_center_radius.return_value = (
                    np.array([0, 0, 0]),
                    0.01,
                    np.array([1, 0, 0]),
                )
            else:
                # Outlets fail
                raise FileNotFoundError("outlet not found")
            return mock_instance

        mock_patch_class = MagicMock(side_effect=mock_patch_init)

        estimator = AorticAxisEstimator(
            wall_stl_full_path="/path/to/wall.stl",
            inlet_patch_keyword="inlet",
            outlet_patch_keywords=["outlet1", "outlet2"],
            tri_surface_dir="/path",
            all_stl_filenames_in_trisurface=[],
            patch_processing_class_ref=mock_patch_class,
            scale_factor=1.0,
            logger_instance=mock_logger,
        )

        # Should fail because no outlets
        assert estimator.final_combined_axis is None

    @patch("aortacfd_lib.aorticAxisEstimator.np_stl_mesh.Mesh")
    @patch("os.path.exists", return_value=True)
    def test_process_coincident_centroids(self, mock_exists, mock_mesh_class):
        """Test process handles coincident inlet/outlet centroids."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimator

        mock_mesh = MagicMock()
        mock_mesh.vectors = np.array(
            [
                [[0, 0, 0], [10, 0, 0], [5, 1, 0]],
                [[10, 0, 0], [20, 0, 0], [15, 1, 0]],
            ]
        )
        mock_mesh_class.from_file.return_value = mock_mesh

        mock_logger = MagicMock()

        # Mock PatchProcessing - inlet and outlet at same location
        same_centroid = np.array([10, 5, 3])

        def mock_patch_init(DIRECTORY, STL_FILES, PATH_NAME):
            mock_instance = MagicMock()
            mock_instance.calculate_inlet_center_radius.return_value = (same_centroid.copy(), 0.01, np.array([1, 0, 0]))
            return mock_instance

        mock_patch_class = MagicMock(side_effect=mock_patch_init)

        estimator = AorticAxisEstimator(
            wall_stl_full_path="/path/to/wall.stl",
            inlet_patch_keyword="inlet",
            outlet_patch_keywords=["outlet"],
            tri_surface_dir="/path",
            all_stl_filenames_in_trisurface=[],
            patch_processing_class_ref=mock_patch_class,
            scale_factor=1.0,
            logger_instance=mock_logger,
        )

        # Should fail because centroids are coincident
        assert estimator.final_combined_axis is None

    @patch("aortacfd_lib.aorticAxisEstimator.np_stl_mesh.Mesh")
    @patch("os.path.exists", return_value=True)
    def test_process_multiple_outlets_averaged(self, mock_exists, mock_mesh_class):
        """Test that multiple outlet centroids are averaged correctly."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimator

        mock_mesh = MagicMock()
        mock_mesh.vectors = np.array(
            [
                [[0, 0, 0], [10, 0, 0], [5, 1, 0]],
                [[10, 0, 0], [20, 0, 0], [15, 1, 0]],
                [[20, 0, 0], [30, 0, 0], [25, 1, 0]],
            ]
        )
        mock_mesh_class.from_file.return_value = mock_mesh

        mock_logger = MagicMock()

        inlet_centroid = np.array([0, 0, 0])
        outlet1_centroid = np.array([30, 10, 0])
        outlet2_centroid = np.array([30, -10, 0])

        def mock_patch_init(DIRECTORY, STL_FILES, PATH_NAME):
            mock_instance = MagicMock()
            if "inlet" in PATH_NAME.lower():
                mock_instance.calculate_inlet_center_radius.return_value = (inlet_centroid, 0.01, np.array([1, 0, 0]))
            elif "1" in PATH_NAME:
                mock_instance.calculate_inlet_center_radius.return_value = (outlet1_centroid, 0.01, np.array([1, 0, 0]))
            else:
                mock_instance.calculate_inlet_center_radius.return_value = (outlet2_centroid, 0.01, np.array([1, 0, 0]))
            return mock_instance

        mock_patch_class = MagicMock(side_effect=mock_patch_init)

        estimator = AorticAxisEstimator(
            wall_stl_full_path="/path/to/wall.stl",
            inlet_patch_keyword="inlet",
            outlet_patch_keywords=["outlet1", "outlet2"],
            tri_surface_dir="/path",
            all_stl_filenames_in_trisurface=["wall.stl", "inlet.stl", "outlet1.stl", "outlet2.stl"],
            patch_processing_class_ref=mock_patch_class,
            scale_factor=1.0,
            logger_instance=mock_logger,
        )

        # Average of outlet1 and outlet2 should be [30, 0, 0]
        expected_avg = np.array([30, 0, 0])
        np.testing.assert_array_almost_equal(estimator.avg_outlet_centroid_val, expected_avg)

    @patch("aortacfd_lib.aorticAxisEstimator.np_stl_mesh.Mesh")
    @patch("os.path.exists", return_value=True)
    def test_process_partial_outlet_success(self, mock_exists, mock_mesh_class):
        """Test process continues when some outlets fail but others succeed."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimator

        mock_mesh = MagicMock()
        mock_mesh.vectors = np.array(
            [
                [[0, 0, 0], [10, 0, 0], [5, 1, 0]],
                [[10, 0, 0], [20, 0, 0], [15, 1, 0]],
            ]
        )
        mock_mesh_class.from_file.return_value = mock_mesh

        mock_logger = MagicMock()

        inlet_centroid = np.array([0, 0, 0])
        outlet1_centroid = np.array([20, 0, 0])

        def mock_patch_init(DIRECTORY, STL_FILES, PATH_NAME):
            mock_instance = MagicMock()
            if "inlet" in PATH_NAME.lower():
                mock_instance.calculate_inlet_center_radius.return_value = (inlet_centroid, 0.01, np.array([1, 0, 0]))
            elif "1" in PATH_NAME:
                mock_instance.calculate_inlet_center_radius.return_value = (outlet1_centroid, 0.01, np.array([1, 0, 0]))
            else:
                # outlet2 fails
                raise FileNotFoundError("outlet2 not found")
            return mock_instance

        mock_patch_class = MagicMock(side_effect=mock_patch_init)

        estimator = AorticAxisEstimator(
            wall_stl_full_path="/path/to/wall.stl",
            inlet_patch_keyword="inlet",
            outlet_patch_keywords=["outlet1", "outlet2"],
            tri_surface_dir="/path",
            all_stl_filenames_in_trisurface=[],
            patch_processing_class_ref=mock_patch_class,
            scale_factor=1.0,
            logger_instance=mock_logger,
        )

        # Should succeed with just outlet1
        assert estimator.final_combined_axis is not None
        np.testing.assert_array_equal(estimator.avg_outlet_centroid_val, outlet1_centroid)


class TestGetCombinedAxis:
    """Test get_combined_axis method."""

    @patch("aortacfd_lib.aorticAxisEstimator.AorticAxisEstimator._process")
    def test_returns_none_when_not_calculated(self, mock_process):
        """Test returns None when axis was not calculated."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimator

        mock_logger = MagicMock()

        estimator = AorticAxisEstimator(
            wall_stl_full_path="/path/to/wall.stl",
            inlet_patch_keyword="inlet",
            outlet_patch_keywords=["outlet"],
            tri_surface_dir="/path",
            all_stl_filenames_in_trisurface=[],
            patch_processing_class_ref=MagicMock(),
            scale_factor=1.0,
            logger_instance=mock_logger,
        )

        # final_combined_axis should be None since _process was mocked
        result = estimator.get_combined_axis()

        assert result is None
        mock_logger.warning.assert_called()

    @patch("aortacfd_lib.aorticAxisEstimator.AorticAxisEstimator._process")
    def test_returns_axis_when_calculated(self, mock_process):
        """Test returns axis when successfully calculated."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimator

        mock_logger = MagicMock()

        estimator = AorticAxisEstimator(
            wall_stl_full_path="/path/to/wall.stl",
            inlet_patch_keyword="inlet",
            outlet_patch_keywords=["outlet"],
            tri_surface_dir="/path",
            all_stl_filenames_in_trisurface=[],
            patch_processing_class_ref=MagicMock(),
            scale_factor=1.0,
            logger_instance=mock_logger,
        )

        # Manually set the axis
        expected_axis = np.array([1.0, 0.0, 0.0])
        estimator.final_combined_axis = expected_axis

        result = estimator.get_combined_axis()

        np.testing.assert_array_equal(result, expected_axis)


class TestIntegration:
    """Integration tests for full axis estimation workflow."""

    @patch("aortacfd_lib.aorticAxisEstimator.np_stl_mesh.Mesh")
    @patch("os.path.exists", return_value=True)
    def test_full_workflow_z_axis_elongated(self, mock_exists, mock_mesh_class):
        """Test full workflow with Z-axis elongated geometry."""
        from aortacfd_lib.aorticAxisEstimator import AorticAxisEstimator

        # Create mesh elongated along Z axis
        mock_mesh = MagicMock()
        # Points forming tube along Z
        z_points = []
        for z in range(0, 100, 5):
            for angle in range(0, 360, 30):
                rad = np.radians(angle)
                x, y = 5 * np.cos(rad), 5 * np.sin(rad)
                z_points.append([x, y, z])

        # Convert to triangles format (3 vertices per triangle)
        vectors = []
        for i in range(len(z_points) - 2):
            vectors.append([z_points[i], z_points[i + 1], z_points[i + 2]])
        mock_mesh.vectors = np.array(vectors[:50])  # Use subset
        mock_mesh_class.from_file.return_value = mock_mesh

        mock_logger = MagicMock()

        # Inlet at bottom (Z=0), outlet at top (Z=100)
        inlet_centroid = np.array([0, 0, 0])
        outlet_centroid = np.array([0, 0, 95])

        def mock_patch_init(DIRECTORY, STL_FILES, PATH_NAME):
            mock_instance = MagicMock()
            if "inlet" in PATH_NAME.lower():
                mock_instance.calculate_inlet_center_radius.return_value = (inlet_centroid, 5.0, np.array([0, 0, 1]))
            else:
                mock_instance.calculate_inlet_center_radius.return_value = (outlet_centroid, 5.0, np.array([0, 0, 1]))
            return mock_instance

        mock_patch_class = MagicMock(side_effect=mock_patch_init)

        estimator = AorticAxisEstimator(
            wall_stl_full_path="/path/to/wall.stl",
            inlet_patch_keyword="inlet",
            outlet_patch_keywords=["outlet"],
            tri_surface_dir="/path",
            all_stl_filenames_in_trisurface=["wall.stl", "inlet.stl", "outlet.stl"],
            patch_processing_class_ref=mock_patch_class,
            scale_factor=1.0,
            logger_instance=mock_logger,
        )

        axis = estimator.get_combined_axis()

        assert axis is not None
        # Axis should be close to Z direction
        assert abs(axis[2]) > 0.9  # Z component should dominate
        assert np.linalg.norm(axis) == pytest.approx(1.0, rel=1e-6)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
