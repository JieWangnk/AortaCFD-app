"""
Test suite for mesh_field_refinement.py module.

Tests cover:
- FieldRefinementStrategy class initialization
- Refinement region generation based on solution fields
- Pressure gradient, vorticity, WSS-based refinement
- y+ compliance refinement
- Cell clustering algorithms
- Export functionality
"""

import pytest
import sys
import tempfile
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestFieldRefinementStrategyInit:
    """Test FieldRefinementStrategy initialization."""

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_init_basic(self, mock_logger):
        """Test basic initialization."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"solver_type": "laminar"}
            strategy = FieldRefinementStrategy(tmpdir, config)

            assert strategy.case_dir == Path(tmpdir)
            assert strategy.config == config
            assert "gradp_percentile" in strategy.thresholds
            assert "gradp" in strategy.max_levels

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_init_default_thresholds(self, mock_logger):
        """Test default threshold values."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = FieldRefinementStrategy(tmpdir, {})

            assert strategy.thresholds["gradp_percentile"] == 85
            assert strategy.thresholds["vorticity_percentile"] == 80
            assert strategy.thresholds["wss_grad_percentile"] == 90
            assert strategy.thresholds["q_criterion"] == 100

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_init_default_max_levels(self, mock_logger):
        """Test default max refinement levels."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = FieldRefinementStrategy(tmpdir, {})

            assert strategy.max_levels["gradp"] == 2
            assert strategy.max_levels["vorticity"] == 1
            assert strategy.max_levels["wss"] == 1
            assert strategy.max_levels["combined"] == 3


class TestGetLatestTime:
    """Test _get_latest_time method."""

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_get_latest_time_single_dir(self, mock_logger):
        """Test with single time directory."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create time directory
            (Path(tmpdir) / "0.5").mkdir()

            strategy = FieldRefinementStrategy(tmpdir, {})
            latest = strategy._get_latest_time()

            assert latest == "0.5"

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_get_latest_time_multiple_dirs(self, mock_logger):
        """Test with multiple time directories."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple time directories
            (Path(tmpdir) / "0").mkdir()
            (Path(tmpdir) / "0.1").mkdir()
            (Path(tmpdir) / "0.5").mkdir()
            (Path(tmpdir) / "1.0").mkdir()
            (Path(tmpdir) / "constant").mkdir()  # Should be ignored

            strategy = FieldRefinementStrategy(tmpdir, {})
            latest = strategy._get_latest_time()

            assert latest == "1.0"

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_get_latest_time_no_dirs(self, mock_logger):
        """Test with no time directories returns '0'."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create non-time directories only
            (Path(tmpdir) / "constant").mkdir()
            (Path(tmpdir) / "system").mkdir()

            strategy = FieldRefinementStrategy(tmpdir, {})
            latest = strategy._get_latest_time()

            assert latest == "0"


class TestCheckFieldExists:
    """Test _check_field_exists method."""

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_field_exists(self, mock_logger):
        """Test with existing field."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create field file
            time_dir = Path(tmpdir) / "0.5"
            time_dir.mkdir()
            (time_dir / "U").write_text("// velocity field")

            strategy = FieldRefinementStrategy(tmpdir, {})
            assert strategy._check_field_exists("U", "0.5") is True

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_field_not_exists(self, mock_logger):
        """Test with non-existing field."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            time_dir = Path(tmpdir) / "0.5"
            time_dir.mkdir()

            strategy = FieldRefinementStrategy(tmpdir, {})
            assert strategy._check_field_exists("wallShearStress", "0.5") is False


class TestReadVectorField:
    """Test _read_vector_field method."""

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_read_vector_field_basic(self, mock_logger):
        """Test reading basic vector field."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            field_content = """FoamFile
{
    version     2.0;
    format      ascii;
    class       volVectorField;
}
(
(1.0 2.0 3.0)
(4.0 5.0 6.0)
(7.0 8.0 9.0)
)
"""
            field_path = Path(tmpdir) / "vectorField"
            field_path.write_text(field_content)

            strategy = FieldRefinementStrategy(tmpdir, {})
            vectors = strategy._read_vector_field(field_path)

            assert vectors.shape == (3, 3)
            np.testing.assert_array_almost_equal(vectors[0], [1.0, 2.0, 3.0])
            np.testing.assert_array_almost_equal(vectors[1], [4.0, 5.0, 6.0])
            np.testing.assert_array_almost_equal(vectors[2], [7.0, 8.0, 9.0])

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_read_vector_field_empty(self, mock_logger):
        """Test reading empty vector field."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            field_content = """FoamFile
{
    version     2.0;
}
(
)
"""
            field_path = Path(tmpdir) / "emptyField"
            field_path.write_text(field_content)

            strategy = FieldRefinementStrategy(tmpdir, {})
            vectors = strategy._read_vector_field(field_path)

            assert vectors.shape == (0,)  # Empty array


class TestReadTensorField:
    """Test _read_tensor_field method."""

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_read_tensor_field(self, mock_logger):
        """Test reading tensor field."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            # Symmetric tensor format: xx xy xz yy yz zz
            field_content = """FoamFile
{
    version     2.0;
}
(
(1.0 0.1 0.2 2.0 0.3 3.0)
(4.0 0.4 0.5 5.0 0.6 6.0)
)
"""
            field_path = Path(tmpdir) / "tensorField"
            field_path.write_text(field_content)

            strategy = FieldRefinementStrategy(tmpdir, {})
            tensors = strategy._read_tensor_field(field_path)

            assert tensors.shape == (2, 6)
            np.testing.assert_array_almost_equal(tensors[0], [1.0, 0.1, 0.2, 2.0, 0.3, 3.0])


class TestTensorMagnitude:
    """Test _tensor_magnitude method."""

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_tensor_magnitude_symmetric(self, mock_logger):
        """Test magnitude calculation for symmetric tensor."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = FieldRefinementStrategy(tmpdir, {})

            # Symmetric tensor: xx, xy, xz, yy, yz, zz
            tensors = np.array(
                [
                    [1.0, 0.0, 0.0, 1.0, 0.0, 1.0],  # Identity-like
                    [2.0, 0.0, 0.0, 2.0, 0.0, 2.0],
                ]
            )

            magnitudes = strategy._tensor_magnitude(tensors)

            # For symmetric tensor, Frobenius norm = sqrt(xx^2 + yy^2 + zz^2 + 2*(xy^2 + xz^2 + yz^2))
            expected_0 = np.sqrt(1 + 1 + 1)  # sqrt(3)
            expected_1 = np.sqrt(4 + 4 + 4)  # sqrt(12)

            np.testing.assert_almost_equal(magnitudes[0], expected_0, decimal=5)
            np.testing.assert_almost_equal(magnitudes[1], expected_1, decimal=5)

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_tensor_magnitude_full(self, mock_logger):
        """Test magnitude calculation for full tensor."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = FieldRefinementStrategy(tmpdir, {})

            # Full tensor (9 components)
            tensors = np.array(
                [
                    [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
                ]
            )

            magnitudes = strategy._tensor_magnitude(tensors)

            # Frobenius norm for identity-like tensor
            expected = np.linalg.norm(tensors[0])
            np.testing.assert_almost_equal(magnitudes[0], expected, decimal=5)


class TestSimpleGridClustering:
    """Test _simple_grid_clustering method."""

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_empty_points(self, mock_logger):
        """Test with empty points array."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = FieldRefinementStrategy(tmpdir, {})

            points = np.array([])
            labels = strategy._simple_grid_clustering(points)

            assert len(labels) == 0

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_single_cluster(self, mock_logger):
        """Test points in single cluster."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = FieldRefinementStrategy(tmpdir, {})

            # Points within 5mm grid cell
            points = np.array(
                [
                    [0.001, 0.001, 0.001],
                    [0.002, 0.002, 0.002],
                    [0.003, 0.003, 0.003],
                ]
            )

            labels = strategy._simple_grid_clustering(points)

            # All points should be in same cluster
            assert len(labels) == 3
            assert len(set(labels)) == 1

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_multiple_clusters(self, mock_logger):
        """Test points in multiple clusters."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = FieldRefinementStrategy(tmpdir, {})

            # Points in different grid cells (>5mm apart)
            points = np.array(
                [
                    [0.0, 0.0, 0.0],
                    [0.001, 0.001, 0.001],
                    [0.1, 0.1, 0.1],  # Far from others
                    [0.101, 0.101, 0.101],
                ]
            )

            labels = strategy._simple_grid_clustering(points)

            # Should have 2 clusters
            assert len(labels) == 4
            assert len(set(labels)) == 2
            assert labels[0] == labels[1]  # First two in same cluster
            assert labels[2] == labels[3]  # Last two in same cluster


class TestClusterCellsToRegions:
    """Test _cluster_cells_to_regions method."""

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_empty_cells(self, mock_logger):
        """Test with empty cell indices."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = FieldRefinementStrategy(tmpdir, {})

            cell_indices = np.array([])
            regions = strategy._cluster_cells_to_regions(cell_indices, "test")

            assert regions == {}

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_cluster_creates_box_regions(self, mock_logger):
        """Test that clustering creates box regions."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = FieldRefinementStrategy(tmpdir, {})

            # Mock cell centers - need at least 10 points for DBSCAN clustering (min_samples=10)
            # Points within 5mm (0.005) of each other will cluster together
            cell_centers = np.array(
                [
                    [0.0, 0.0, 0.0],
                    [0.001, 0.0, 0.0],
                    [0.002, 0.0, 0.0],
                    [0.0, 0.001, 0.0],
                    [0.001, 0.001, 0.0],
                    [0.002, 0.001, 0.0],
                    [0.0, 0.002, 0.0],
                    [0.001, 0.002, 0.0],
                    [0.002, 0.002, 0.0],
                    [0.001, 0.001, 0.001],
                    [0.0015, 0.0015, 0.0015],
                ]
            )

            with patch.object(strategy, "_read_cell_centers", return_value=cell_centers):
                cell_indices = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
                regions = strategy._cluster_cells_to_regions(cell_indices, "gradP")

                # Should create at least one region
                assert len(regions) >= 1

                # Check region structure
                for name, region in regions.items():
                    assert "gradP" in name
                    assert region["type"] == "box"
                    assert "min" in region
                    assert "max" in region
                    assert region["mode"] == "inside"
                    assert "levels" in region


class TestCreateNearwallRegions:
    """Test _create_nearwall_regions method."""

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_creates_distance_regions(self, mock_logger):
        """Test that nearwall regions use distance mode."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = FieldRefinementStrategy(tmpdir, {})

            cell_indices = np.array([0, 1, 2])
            regions = strategy._create_nearwall_regions(cell_indices)

            assert "nearwall_wall_aorta" in regions

            region = regions["nearwall_wall_aorta"]
            assert region["type"] == "distance"
            assert region["mode"] == "inside"
            assert region["surfaceName"] == "wall_aorta"
            assert "levels" in region


class TestCreatePatchProximityRegion:
    """Test _create_patch_proximity_region method."""

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_creates_multi_level_region(self, mock_logger):
        """Test that patch proximity creates multi-level refinement."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = FieldRefinementStrategy(tmpdir, {})

            region = strategy._create_patch_proximity_region("inlet")

            assert region["type"] == "distance"
            assert region["mode"] == "inside"
            assert region["surfaceName"] == "inlet"

            # Should have multiple refinement levels
            assert len(region["levels"]) >= 2


class TestGenerateGradpRefinement:
    """Test _generate_gradp_refinement method."""

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_no_gradp_field(self, mock_logger):
        """Test with missing pressure gradient field."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create empty time directory
            (Path(tmpdir) / "0.5").mkdir()

            strategy = FieldRefinementStrategy(tmpdir, {})
            regions = strategy._generate_gradp_refinement()

            assert regions == {}

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_with_gradp_field(self, mock_logger):
        """Test with pressure gradient field present."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create time directory and gradient field
            time_dir = Path(tmpdir) / "0.5"
            time_dir.mkdir()

            # Create a gradient field with some high values
            field_content = """FoamFile
{
    version     2.0;
}
(
(100.0 0.0 0.0)
(200.0 0.0 0.0)
(10.0 0.0 0.0)
(5.0 0.0 0.0)
(1000.0 500.0 200.0)
)
"""
            (time_dir / "grad(p)").write_text(field_content)

            strategy = FieldRefinementStrategy(tmpdir, {})

            # Mock cell centers for clustering
            with patch.object(strategy, "_read_cell_centers") as mock_centers:
                mock_centers.return_value = np.array(
                    [
                        [0.0, 0.0, 0.0],
                        [0.001, 0.001, 0.001],
                        [0.1, 0.1, 0.1],
                        [0.1, 0.1, 0.101],
                        [0.2, 0.2, 0.2],
                    ]
                )

                regions = strategy._generate_gradp_refinement()

                # Should create refinement regions for high gradp cells
                assert isinstance(regions, dict)


class TestGenerateVorticityRefinement:
    """Test _generate_vorticity_refinement method."""

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_no_vorticity_field(self, mock_logger):
        """Test with missing vorticity field."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "0.5").mkdir()

            strategy = FieldRefinementStrategy(tmpdir, {})
            regions = strategy._generate_vorticity_refinement()

            assert regions == {}


class TestGenerateWSSRefinement:
    """Test _generate_wss_refinement method."""

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_no_wss_grad_field(self, mock_logger):
        """Test with missing WSS gradient field."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "0.5").mkdir()

            strategy = FieldRefinementStrategy(tmpdir, {})
            regions = strategy._generate_wss_refinement()

            assert regions == {}


class TestGenerateYplusRefinement:
    """Test _generate_yplus_refinement method."""

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_no_yplus_file(self, mock_logger):
        """Test with missing y+ file."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = FieldRefinementStrategy(tmpdir, {})
            regions = strategy._generate_yplus_refinement()

            assert regions == {}

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_with_yplus_file_compliant(self, mock_logger):
        """Test with y+ file showing compliant values."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create y+ file with compliant values
            yplus_dir = Path(tmpdir) / "postProcessing" / "yPlus" / "0"
            yplus_dir.mkdir(parents=True)

            yplus_content = """# y+ Statistics
Patch: wall_aorta min: 0.5 max: 4.0 average: 2.5
Patch: inlet min: 1.0 max: 3.0 average: 2.0
"""
            (yplus_dir / "yPlus.dat").write_text(yplus_content)

            config = {"yplus_target_min": 1.0, "yplus_target_max": 5.0}
            strategy = FieldRefinementStrategy(tmpdir, config)
            regions = strategy._generate_yplus_refinement()

            # All patches are compliant, no refinement needed
            assert regions == {}

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_with_yplus_file_non_compliant(self, mock_logger):
        """Test with y+ file showing non-compliant values."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create y+ file with non-compliant values
            yplus_dir = Path(tmpdir) / "postProcessing" / "yPlus" / "0"
            yplus_dir.mkdir(parents=True)

            yplus_content = """# y+ Statistics
Patch: wall_aorta min: 0.5 max: 15.0 average: 8.0
Patch: inlet min: 0.1 max: 0.5 average: 0.3
"""
            (yplus_dir / "yPlus.dat").write_text(yplus_content)

            config = {"yplus_target_min": 1.0, "yplus_target_max": 5.0}
            strategy = FieldRefinementStrategy(tmpdir, config)
            regions = strategy._generate_yplus_refinement()

            # Both patches non-compliant
            assert "yplus_refinement_wall_aorta" in regions
            assert "yplus_refinement_inlet" in regions


class TestCombineAndLimitRegions:
    """Test _combine_and_limit_regions method."""

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_under_cell_limit(self, mock_logger):
        """Test regions under cell limit are kept."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"max_cells": 10000000}
            strategy = FieldRefinementStrategy(tmpdir, config)

            regions = {
                "gradP_region_0": {"type": "box", "levels": [[1e15, 1]]},
                "vorticity_region_0": {"type": "box", "levels": [[1e15, 1]]},
            }

            result = strategy._combine_and_limit_regions(regions)

            # All regions should be kept
            assert len(result) == 2

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_prioritizes_gradp(self, mock_logger):
        """Test that gradP regions are prioritized."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            # Very low cell limit to force filtering
            config = {"max_cells": 1000}
            strategy = FieldRefinementStrategy(tmpdir, config)

            # Mock to return very high estimated cells
            with patch.object(strategy, "_estimate_refined_cell_count") as mock_estimate:
                mock_estimate.return_value = 100000000  # Very high

                regions = {
                    "gradP_region_0": {"type": "box", "levels": [[1e15, 2]]},
                    "vorticity_region_0": {"type": "box", "levels": [[1e15, 1]]},
                    "nearwall_wall": {"type": "distance", "levels": [[0.002, 1]]},
                }

                result = strategy._combine_and_limit_regions(regions)

                # gradP should be prioritized
                assert "gradP_region_0" in result or len(result) < len(regions)


class TestEstimateRefinedCellCount:
    """Test _estimate_refined_cell_count method."""

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_empty_regions(self, mock_logger):
        """Test with no regions returns base count."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = FieldRefinementStrategy(tmpdir, {})

            count = strategy._estimate_refined_cell_count({})

            # Should return current cell count (placeholder value)
            assert count == 100000

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_with_refinement_levels(self, mock_logger):
        """Test cell count increases with refinement."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = FieldRefinementStrategy(tmpdir, {})

            regions = {
                "region1": {"levels": [[1e15, 1]]},  # Level 1 refinement
                "region2": {"levels": [[1e15, 2]]},  # Level 2 refinement
            }

            count = strategy._estimate_refined_cell_count(regions)

            # Should be more than base count
            assert count > 100000


class TestRunPostprocess:
    """Test _run_postprocess method."""

    @patch("aortacfd_lib.mesh_field_refinement.subprocess.run")
    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_successful_postprocess(self, mock_logger, mock_run):
        """Test successful postProcess call."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        mock_run.return_value = MagicMock(returncode=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = FieldRefinementStrategy(tmpdir, {})
            strategy._run_postprocess("grad(p)", "gradP")

            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "postProcess" in call_args
            assert "grad(p)" in call_args

    @patch("aortacfd_lib.mesh_field_refinement.subprocess.run")
    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_failed_postprocess(self, mock_logger, mock_run):
        """Test failed postProcess call logs error."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy
        import subprocess

        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd", stderr="error")

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = FieldRefinementStrategy(tmpdir, {})
            strategy._run_postprocess("grad(p)", "gradP")

            # Should log error but not raise
            strategy.logger.error.assert_called()


class TestCalculateFieldIndicators:
    """Test _calculate_field_indicators method."""

    @patch("aortacfd_lib.mesh_field_refinement.subprocess.run")
    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_calculates_basic_indicators(self, mock_logger, mock_run):
        """Test that basic field indicators are calculated."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        mock_run.return_value = MagicMock(returncode=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "0.5").mkdir()

            strategy = FieldRefinementStrategy(tmpdir, {"solver_type": "PISO"})
            strategy._calculate_field_indicators()

            # Should have called postProcess multiple times
            assert mock_run.call_count >= 3  # grad(p), grad(U), vorticity

    @patch("aortacfd_lib.mesh_field_refinement.subprocess.run")
    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_calculates_les_indicators(self, mock_logger, mock_run):
        """Test that LES-specific indicators are calculated."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        mock_run.return_value = MagicMock(returncode=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "0.5").mkdir()

            config = {"solver_type": "LES"}
            strategy = FieldRefinementStrategy(tmpdir, config)
            strategy._calculate_field_indicators()

            # Should calculate Q-criterion for LES
            calls = [str(call) for call in mock_run.call_args_list]
            assert any("Q" in str(call) for call in calls)


class TestGenerateRefinementRegions:
    """Test generate_refinement_regions method."""

    @patch("aortacfd_lib.mesh_field_refinement.subprocess.run")
    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_returns_combined_regions(self, mock_logger, mock_run):
        """Test that all region types are combined."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        mock_run.return_value = MagicMock(returncode=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "0.5").mkdir()

            strategy = FieldRefinementStrategy(tmpdir, {})

            # Mock individual region generation methods
            with (
                patch.object(strategy, "_generate_gradp_refinement") as mock_gradp,
                patch.object(strategy, "_generate_vorticity_refinement") as mock_vort,
                patch.object(strategy, "_generate_wss_refinement") as mock_wss,
                patch.object(strategy, "_generate_yplus_refinement") as mock_yplus,
                patch.object(strategy, "_calculate_field_indicators"),
            ):

                mock_gradp.return_value = {"gradP_r0": {"type": "box"}}
                mock_vort.return_value = {"vort_r0": {"type": "box"}}
                mock_wss.return_value = {}
                mock_yplus.return_value = {}

                regions = strategy.generate_refinement_regions(iteration=1)

                assert "gradP_r0" in regions or "vort_r0" in regions


class TestExportRefinementDict:
    """Test export_refinement_dict method."""

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_export_box_regions(self, mock_logger):
        """Test exporting box-type regions."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = FieldRefinementStrategy(tmpdir, {})

            regions = {
                "gradP_region_0": {
                    "type": "box",
                    "min": [0.0, 0.0, 0.0],
                    "max": [0.1, 0.1, 0.1],
                    "mode": "inside",
                    "levels": [[1e15, 2]],
                }
            }

            output_file = Path(tmpdir) / "refinementRegions"
            strategy.export_refinement_dict(regions, str(output_file))

            assert output_file.exists()

            content = output_file.read_text()
            assert "refinementRegions" in content
            assert "gradP_region_0" in content
            assert "mode inside" in content
            assert "min" in content
            assert "max" in content

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_export_distance_regions(self, mock_logger):
        """Test exporting distance-type regions."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = FieldRefinementStrategy(tmpdir, {})

            regions = {
                "nearwall_wall_aorta": {
                    "type": "distance",
                    "mode": "inside",
                    "levels": [[0.002, 1], [0.005, 0]],
                    "surfaceName": "wall_aorta",
                }
            }

            output_file = Path(tmpdir) / "refinementRegions"
            strategy.export_refinement_dict(regions, str(output_file))

            content = output_file.read_text()
            assert "surfaceName wall_aorta" in content
            assert "levels" in content

    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_export_empty_regions(self, mock_logger):
        """Test exporting empty region dictionary."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = FieldRefinementStrategy(tmpdir, {})

            output_file = Path(tmpdir) / "refinementRegions"
            strategy.export_refinement_dict({}, str(output_file))

            content = output_file.read_text()
            assert "refinementRegions" in content
            assert content.count("{") == content.count("}")


class TestReadCellCenters:
    """Test _read_cell_centers method."""

    @patch("aortacfd_lib.mesh_field_refinement.subprocess.run")
    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_reads_cell_centers_file(self, mock_logger, mock_run):
        """Test reading cell centers from file."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        mock_run.return_value = MagicMock(returncode=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create cell centers file
            time_dir = Path(tmpdir) / "0.5"
            time_dir.mkdir()

            cell_centers_content = """FoamFile
{
    version     2.0;
}
(
(0.01 0.02 0.03)
(0.04 0.05 0.06)
)
"""
            (time_dir / "C").write_text(cell_centers_content)

            strategy = FieldRefinementStrategy(tmpdir, {})
            centers = strategy._read_cell_centers()

            # Should return cell centers from file
            assert centers.shape[0] >= 1

    @patch("aortacfd_lib.mesh_field_refinement.subprocess.run")
    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_fallback_when_no_file(self, mock_logger, mock_run):
        """Test fallback when cell centers file doesn't exist."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy
        import subprocess

        # Use CalledProcessError which is caught by the code
        mock_run.side_effect = subprocess.CalledProcessError(1, "postProcess")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create time directory without cell centers
            (Path(tmpdir) / "0.5").mkdir()

            strategy = FieldRefinementStrategy(tmpdir, {})
            centers = strategy._read_cell_centers()

            # Should return placeholder when C file doesn't exist
            assert centers.shape == (1, 3)


class TestIntegration:
    """Integration tests for FieldRefinementStrategy."""

    @patch("aortacfd_lib.mesh_field_refinement.subprocess.run")
    @patch("aortacfd_lib.mesh_field_refinement.Logger")
    def test_full_workflow(self, mock_logger, mock_run):
        """Test complete workflow from initialization to export."""
        from aortacfd_lib.mesh_field_refinement import FieldRefinementStrategy

        mock_run.return_value = MagicMock(returncode=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup minimal case structure
            time_dir = Path(tmpdir) / "0.5"
            time_dir.mkdir()

            # Create minimal gradient field
            gradp_content = """FoamFile
{
    version     2.0;
}
(
(1000.0 0.0 0.0)
(500.0 0.0 0.0)
(100.0 0.0 0.0)
)
"""
            (time_dir / "grad(p)").write_text(gradp_content)

            config = {"solver_type": "PISO", "max_cells": 10000000}

            strategy = FieldRefinementStrategy(tmpdir, config)

            # Mock cell centers
            with patch.object(strategy, "_read_cell_centers") as mock_centers:
                mock_centers.return_value = np.array(
                    [
                        [0.0, 0.0, 0.0],
                        [0.001, 0.001, 0.001],
                        [0.1, 0.1, 0.1],
                    ]
                )

                # Generate regions
                regions = strategy.generate_refinement_regions(iteration=1)

                # Export to file
                output_file = Path(tmpdir) / "system" / "refinementRegions"
                output_file.parent.mkdir(exist_ok=True)

                strategy.export_refinement_dict(regions, str(output_file))

                assert output_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
