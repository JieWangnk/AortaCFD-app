"""
Test suite for patch_processing utilities.

Tests cover:
- PatchProcessing class
- STL mesh loading
- Bounding box calculations
- Surface area calculations
- Inlet center and radius calculations
- Normal vector computations
- Rotation vector calculations
"""

import pytest
import sys
import tempfile
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestPatchProcessingInit:
    """Test PatchProcessing initialization."""

    @patch("aortacfd_lib.utils.patch_processing.Logger")
    @patch("aortacfd_lib.utils.patch_processing.mesh.Mesh")
    def test_init_with_valid_stl(self, mock_mesh_class, mock_logger):
        """Test initialization with valid STL file."""
        from aortacfd_lib.utils.patch_processing import PatchProcessing

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock STL file
            stl_path = Path(tmpdir) / "inlet.stl"
            stl_path.touch()

            # Mock mesh loading
            mock_mesh = MagicMock()
            mock_mesh.vectors = np.array(
                [
                    [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                    [[0, 0, 0], [1, 0, 0], [0, 0, 1]],
                ]
                * 10
            )  # At least 10 triangles
            mock_mesh.v0 = mock_mesh.vectors[:, 0]
            mock_mesh.v1 = mock_mesh.vectors[:, 1]
            mock_mesh.v2 = mock_mesh.vectors[:, 2]
            mock_mesh_class.from_file.return_value = mock_mesh

            processor = PatchProcessing(tmpdir, "inlet")

            assert processor.patch_name == "inlet"
            assert processor.mesh_data is not None

    @patch("aortacfd_lib.utils.patch_processing.Logger")
    def test_init_with_missing_stl(self, mock_logger):
        """Test initialization with missing STL file."""
        from aortacfd_lib.utils.patch_processing import PatchProcessing

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FileNotFoundError):
                PatchProcessing(tmpdir, "nonexistent")


class TestExtractPoints:
    """Test extract_points method."""

    @patch("aortacfd_lib.utils.patch_processing.Logger")
    @patch("aortacfd_lib.utils.patch_processing.mesh.Mesh")
    def test_extract_points(self, mock_mesh_class, mock_logger):
        """Test point extraction from mesh."""
        from aortacfd_lib.utils.patch_processing import PatchProcessing

        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "test.stl"
            stl_path.touch()

            # Create mock mesh with known vertices
            mock_mesh = MagicMock()
            mock_mesh.vectors = np.array(
                [
                    [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                ]
                * 20
            )
            mock_mesh.v0 = np.array([[0, 0, 0]] * 20)
            mock_mesh.v1 = np.array([[1, 0, 0]] * 20)
            mock_mesh.v2 = np.array([[0, 1, 0]] * 20)
            mock_mesh_class.from_file.return_value = mock_mesh

            processor = PatchProcessing(tmpdir, "test")

            # extract_points concatenates v0, v1, v2
            assert processor.all_points.shape == (60, 3)


class TestGetBoundingBox:
    """Test get_bounding_box method."""

    @patch("aortacfd_lib.utils.patch_processing.Logger")
    @patch("aortacfd_lib.utils.patch_processing.mesh.Mesh")
    def test_bounding_box(self, mock_mesh_class, mock_logger):
        """Test bounding box calculation."""
        from aortacfd_lib.utils.patch_processing import PatchProcessing

        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "test.stl"
            stl_path.touch()

            # Create mesh with known bounds
            mock_mesh = MagicMock()
            mock_mesh.vectors = np.array(
                [
                    [[0, 0, 0], [10, 0, 0], [0, 5, 0]],
                    [[0, 0, 0], [0, 0, 8], [10, 5, 8]],
                ]
                * 10
            )
            mock_mesh.v0 = mock_mesh.vectors[:, 0]
            mock_mesh.v1 = mock_mesh.vectors[:, 1]
            mock_mesh.v2 = mock_mesh.vectors[:, 2]
            mock_mesh_class.from_file.return_value = mock_mesh

            processor = PatchProcessing(tmpdir, "test")
            min_coords, max_coords = processor.get_bounding_box()

            assert min_coords[0] == 0
            assert max_coords[0] == 10
            assert max_coords[1] == 5
            assert max_coords[2] == 8


class TestComputeAverageNormal:
    """Test compute_average_normal method."""

    @patch("aortacfd_lib.utils.patch_processing.Logger")
    @patch("aortacfd_lib.utils.patch_processing.mesh.Mesh")
    def test_average_normal_xy_plane(self, mock_mesh_class, mock_logger):
        """Test average normal for triangles in XY plane."""
        from aortacfd_lib.utils.patch_processing import PatchProcessing

        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "test.stl"
            stl_path.touch()

            # Triangles in XY plane (normal should be +Z or -Z)
            # Use float dtype to avoid casting issues
            mock_mesh = MagicMock()
            mock_mesh.vectors = np.array(
                [
                    [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                    [[1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]],
                ]
                * 10,
                dtype=np.float64,
            )
            mock_mesh.v0 = mock_mesh.vectors[:, 0]
            mock_mesh.v1 = mock_mesh.vectors[:, 1]
            mock_mesh.v2 = mock_mesh.vectors[:, 2]
            mock_mesh_class.from_file.return_value = mock_mesh

            processor = PatchProcessing(tmpdir, "test")
            normal = processor.compute_average_normal()

            # Normal should be primarily in Z direction
            assert abs(normal[2]) > 0.9

    @patch("aortacfd_lib.utils.patch_processing.Logger")
    @patch("aortacfd_lib.utils.patch_processing.mesh.Mesh")
    def test_average_normal_empty_mesh(self, mock_mesh_class, mock_logger):
        """Test error handling for empty mesh."""
        from aortacfd_lib.utils.patch_processing import PatchProcessing

        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "test.stl"
            stl_path.touch()

            mock_mesh = MagicMock()
            mock_mesh.vectors = np.array([])  # Empty
            mock_mesh.v0 = np.array([])
            mock_mesh.v1 = np.array([])
            mock_mesh.v2 = np.array([])
            mock_mesh_class.from_file.return_value = mock_mesh

            processor = PatchProcessing(tmpdir, "test")

            with pytest.raises(ValueError):
                processor.compute_average_normal()


class TestProjectPointsOntoPlane:
    """Test project_points_onto_plane method."""

    @patch("aortacfd_lib.utils.patch_processing.Logger")
    @patch("aortacfd_lib.utils.patch_processing.mesh.Mesh")
    def test_projection(self, mock_mesh_class, mock_logger):
        """Test 2D projection of 3D points."""
        from aortacfd_lib.utils.patch_processing import PatchProcessing

        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "test.stl"
            stl_path.touch()

            mock_mesh = MagicMock()
            mock_mesh.vectors = np.array(
                [
                    [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                ]
                * 20
            )
            mock_mesh.v0 = mock_mesh.vectors[:, 0]
            mock_mesh.v1 = mock_mesh.vectors[:, 1]
            mock_mesh.v2 = mock_mesh.vectors[:, 2]
            mock_mesh_class.from_file.return_value = mock_mesh

            processor = PatchProcessing(tmpdir, "test")

            points_3d = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]])
            normal_vec = np.array([0, 0, 1])

            translated, points_2d, centroid = processor.project_points_onto_plane(points_3d, normal_vec)

            # 2D projection should have 2 columns
            assert points_2d.shape[1] == 2

            # Centroid should be mean of points
            np.testing.assert_array_almost_equal(centroid, np.mean(points_3d, axis=0))


class TestCalculateInletCenterRadius:
    """Test calculate_inlet_center_radius method."""

    @patch("aortacfd_lib.utils.patch_processing.ConvexHull")
    @patch("aortacfd_lib.utils.patch_processing.Logger")
    @patch("aortacfd_lib.utils.patch_processing.mesh.Mesh")
    def test_center_radius(self, mock_mesh_class, mock_logger, mock_hull_class):
        """Test center and radius calculation."""
        from aortacfd_lib.utils.patch_processing import PatchProcessing

        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "inlet.stl"
            stl_path.touch()

            # Create a circular-ish mesh
            mock_mesh = MagicMock()
            # Create a flat disc of triangles
            n_triangles = 20
            mock_mesh.vectors = np.array([[[0, 0, 0], [0.01, 0, 0], [0.005, 0.0087, 0]]] * n_triangles)
            mock_mesh.v0 = mock_mesh.vectors[:, 0]
            mock_mesh.v1 = mock_mesh.vectors[:, 1]
            mock_mesh.v2 = mock_mesh.vectors[:, 2]
            mock_mesh_class.from_file.return_value = mock_mesh

            # Mock convex hull
            mock_hull = MagicMock()
            mock_hull.volume = 0.0001  # Area in 2D
            mock_hull.area = 0.04  # Perimeter in 2D
            mock_hull_class.return_value = mock_hull

            processor = PatchProcessing(tmpdir, "inlet")
            centroid, radius, normal = processor.calculate_inlet_center_radius()

            assert isinstance(centroid, np.ndarray)
            assert isinstance(radius, (float, np.floating))
            assert isinstance(normal, np.ndarray)
            assert radius > 0


class TestCalculateSurfaceArea:
    """Test calculate_surface_area method."""

    @patch("aortacfd_lib.utils.patch_processing.Logger")
    @patch("aortacfd_lib.utils.patch_processing.mesh.Mesh")
    def test_surface_area(self, mock_mesh_class, mock_logger):
        """Test surface area calculation."""
        from aortacfd_lib.utils.patch_processing import PatchProcessing

        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "test.stl"
            stl_path.touch()

            # Create two triangles forming a 1x1 square
            mock_mesh = MagicMock()
            mock_mesh.vectors = np.array(
                [
                    [[0, 0, 0], [1, 0, 0], [0, 1, 0]],  # Area = 0.5
                    [[1, 0, 0], [1, 1, 0], [0, 1, 0]],  # Area = 0.5
                ]
                * 10
            )  # Total 20 triangles, each pair = 1 sq unit
            mock_mesh.v0 = mock_mesh.vectors[:, 0]
            mock_mesh.v1 = mock_mesh.vectors[:, 1]
            mock_mesh.v2 = mock_mesh.vectors[:, 2]
            mock_mesh_class.from_file.return_value = mock_mesh

            processor = PatchProcessing(tmpdir, "test")
            area = processor.calculate_surface_area()

            # Total area should be 10 square units (10 pairs * 1 sq unit)
            assert abs(area - 10.0) < 1e-10


class TestComputeRotationVector:
    """Test compute_rotation_vector method."""

    @patch("aortacfd_lib.utils.patch_processing.Logger")
    @patch("aortacfd_lib.utils.patch_processing.mesh.Mesh")
    def test_no_rotation_needed(self, mock_mesh_class, mock_logger):
        """Test when vectors are already aligned."""
        from aortacfd_lib.utils.patch_processing import PatchProcessing

        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "test.stl"
            stl_path.touch()

            mock_mesh = MagicMock()
            mock_mesh.vectors = np.array([[[0, 0, 0], [1, 0, 0], [0, 1, 0]]] * 20)
            mock_mesh.v0 = mock_mesh.vectors[:, 0]
            mock_mesh.v1 = mock_mesh.vectors[:, 1]
            mock_mesh.v2 = mock_mesh.vectors[:, 2]
            mock_mesh_class.from_file.return_value = mock_mesh

            processor = PatchProcessing(tmpdir, "test")

            v1 = np.array([1, 0, 0])
            v2 = np.array([1, 0, 0])

            axis, angle = processor.compute_rotation_vector(v1, v2)

            # No rotation needed
            assert angle == 0.0

    @patch("aortacfd_lib.utils.patch_processing.Logger")
    @patch("aortacfd_lib.utils.patch_processing.mesh.Mesh")
    def test_180_degree_rotation(self, mock_mesh_class, mock_logger):
        """Test 180-degree rotation between opposite vectors."""
        from aortacfd_lib.utils.patch_processing import PatchProcessing

        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "test.stl"
            stl_path.touch()

            mock_mesh = MagicMock()
            mock_mesh.vectors = np.array([[[0, 0, 0], [1, 0, 0], [0, 1, 0]]] * 20)
            mock_mesh.v0 = mock_mesh.vectors[:, 0]
            mock_mesh.v1 = mock_mesh.vectors[:, 1]
            mock_mesh.v2 = mock_mesh.vectors[:, 2]
            mock_mesh_class.from_file.return_value = mock_mesh

            processor = PatchProcessing(tmpdir, "test")

            v1 = np.array([1, 0, 0])
            v2 = np.array([-1, 0, 0])

            axis, angle = processor.compute_rotation_vector(v1, v2)

            # Should be 180 degrees (π radians)
            assert abs(angle - np.pi) < 1e-10

    @patch("aortacfd_lib.utils.patch_processing.Logger")
    @patch("aortacfd_lib.utils.patch_processing.mesh.Mesh")
    def test_90_degree_rotation(self, mock_mesh_class, mock_logger):
        """Test 90-degree rotation."""
        from aortacfd_lib.utils.patch_processing import PatchProcessing

        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "test.stl"
            stl_path.touch()

            mock_mesh = MagicMock()
            mock_mesh.vectors = np.array([[[0, 0, 0], [1, 0, 0], [0, 1, 0]]] * 20)
            mock_mesh.v0 = mock_mesh.vectors[:, 0]
            mock_mesh.v1 = mock_mesh.vectors[:, 1]
            mock_mesh.v2 = mock_mesh.vectors[:, 2]
            mock_mesh_class.from_file.return_value = mock_mesh

            processor = PatchProcessing(tmpdir, "test")

            v1 = np.array([1, 0, 0])
            v2 = np.array([0, 1, 0])

            axis, angle = processor.compute_rotation_vector(v1, v2)

            # Should be 90 degrees (π/2 radians)
            assert abs(angle - np.pi / 2) < 1e-10

            # Rotation axis should be Z
            assert abs(axis[2]) > 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
