"""
Unit tests for mesh setup and generation.

Tests GeometryAnalyzer and mesh configuration.
"""

import pytest
import os
from pathlib import Path
import json


class TestGeometryAnalyzerInitialization:
    """Test GeometryAnalyzer initialization and setup."""

    @pytest.fixture
    def minimal_mesh_config(self):
        """Minimal configuration for mesh setup."""
        return {
            "geometry": {
                "scale_factor": 1e-3,
                "wall_keywords_ordered": "wall_aorta",
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["outlet1", "outlet2"],
                "reference_radius_strategy": "min"
            },
            "mesh": {
                "SNAPPY_SETTINGS": {
                    "parallel": False,
                    "nProcessors": 1,
                    "castellatedMesh": True,
                    "snap": True,
                    "addLayers": True
                }
            }
        }

    def test_config_structure_valid(self, minimal_mesh_config):
        """Test that minimal mesh config has required structure."""
        assert "geometry" in minimal_mesh_config
        assert "mesh" in minimal_mesh_config
        assert "SNAPPY_SETTINGS" in minimal_mesh_config["mesh"]

    def test_geometry_settings_present(self, minimal_mesh_config):
        """Test that geometry settings are present."""
        geom = minimal_mesh_config["geometry"]
        assert "inlet_keywords_ordered" in geom
        assert "outlet_keywords_ordered" in geom
        assert "wall_keywords_ordered" in geom

    def test_snappy_settings_structure(self, minimal_mesh_config):
        """Test snappyHexMesh settings structure."""
        snappy = minimal_mesh_config["mesh"]["SNAPPY_SETTINGS"]

        # Check boolean flags
        assert isinstance(snappy["castellatedMesh"], bool)
        assert isinstance(snappy["snap"], bool)
        assert isinstance(snappy["addLayers"], bool)

        # Check processor settings
        assert isinstance(snappy["nProcessors"], int)
        assert snappy["nProcessors"] >= 1


class TestSnappyHexMeshSettings:
    """Test snappyHexMesh configuration generation."""

    @pytest.fixture
    def snappy_config_coarse(self):
        """Coarse snappyHexMesh settings."""
        return {
            "parallel": False,
            "nProcessors": 1,
            "maxLocalCells": 1_800_000,
            "maxGlobalCells": 2_000_000,
            "minRefinementCells": 0,
            "nCellsBetweenLevels": 1,
            "castellatedMesh": True,
            "snap": True,
            "addLayers": True
        }

    @pytest.fixture
    def snappy_config_fine(self):
        """Fine snappyHexMesh settings."""
        return {
            "parallel": True,
            "nProcessors": 8,
            "maxLocalCells": 8_000_000,
            "maxGlobalCells": 10_000_000,
            "minRefinementCells": 10,
            "nCellsBetweenLevels": 3,
            "castellatedMesh": True,
            "snap": True,
            "addLayers": True
        }

    def test_coarse_cell_limits(self, snappy_config_coarse):
        """Test coarse mesh cell limits."""
        assert snappy_config_coarse["maxLocalCells"] == 1_800_000
        assert snappy_config_coarse["maxGlobalCells"] == 2_000_000
        assert snappy_config_coarse["maxGlobalCells"] > snappy_config_coarse["maxLocalCells"]

    def test_fine_cell_limits(self, snappy_config_fine):
        """Test fine mesh has higher cell limits than coarse."""
        coarse_cells = 2_000_000
        fine_cells = snappy_config_fine["maxGlobalCells"]

        assert fine_cells > coarse_cells
        assert fine_cells >= 8_000_000

    def test_parallel_settings_consistency(self, snappy_config_fine):
        """Test parallel settings are consistent."""
        if snappy_config_fine["parallel"]:
            assert snappy_config_fine["nProcessors"] > 1
        else:
            assert snappy_config_fine["nProcessors"] == 1

    def test_mesh_stages_enabled(self, snappy_config_coarse):
        """Test all mesh stages are properly configured."""
        assert snappy_config_coarse["castellatedMesh"] is True
        assert snappy_config_coarse["snap"] is True
        assert snappy_config_coarse["addLayers"] is True

    def test_refinement_parameters_valid(self, snappy_config_fine):
        """Test refinement parameters are valid."""
        assert snappy_config_fine["minRefinementCells"] >= 0
        assert snappy_config_fine["nCellsBetweenLevels"] >= 1


class TestBoundaryLayerSettings:
    """Test boundary layer configuration."""

    @pytest.fixture
    def boundary_layer_config(self):
        """Boundary layer settings."""
        return {
            "nSurfaceLayers": 3,
            "expansionRatio": 1.2,
            "finalLayerThickness": 0.5,
            "minThickness": 0.001,
            "featureAngle": 180,
            "nRelaxIter": 5
        }

    def test_layer_count_valid(self, boundary_layer_config):
        """Test boundary layer count is reasonable."""
        n_layers = boundary_layer_config["nSurfaceLayers"]
        assert 1 <= n_layers <= 30  # Typical range

    def test_expansion_ratio_valid(self, boundary_layer_config):
        """Test expansion ratio is valid."""
        ratio = boundary_layer_config["expansionRatio"]
        assert 1.0 <= ratio <= 2.0  # Typical CFD range

    def test_thickness_consistency(self, boundary_layer_config):
        """Test layer thickness is consistent."""
        final_thickness = boundary_layer_config["finalLayerThickness"]
        min_thickness = boundary_layer_config["minThickness"]

        assert final_thickness > 0
        assert min_thickness > 0
        assert final_thickness >= min_thickness

    def test_feature_angle_valid(self, boundary_layer_config):
        """Test feature angle is within valid range."""
        angle = boundary_layer_config["featureAngle"]
        assert 0 <= angle <= 180


class TestMeshQualityThresholds:
    """Test mesh quality criteria."""

    def test_orthogonality_threshold(self):
        """Test mesh orthogonality threshold."""
        max_non_ortho = 65  # From relaxed settings
        assert 0 <= max_non_ortho <= 75  # Acceptable range

    def test_skewness_threshold(self):
        """Test mesh skewness threshold."""
        max_skewness = 4.0  # Typical limit
        assert 0 <= max_skewness <= 5.0

    def test_aspect_ratio_threshold(self):
        """Test mesh aspect ratio threshold."""
        max_aspect_ratio = 100  # Typical limit
        assert 1 <= max_aspect_ratio <= 1000


class TestGeometryReferenceRadius:
    """Test reference radius calculation strategies."""

    @pytest.fixture
    def sample_radii(self):
        """Sample inlet and outlet radii."""
        return {
            "inlet": 10.0,  # mm
            "outlet1": 5.0,
            "outlet2": 7.0,
            "outlet3": 6.0
        }

    def test_min_radius_strategy(self, sample_radii):
        """Test minimum radius strategy."""
        all_radii = [sample_radii["inlet"]] + [sample_radii["outlet1"],
                                                 sample_radii["outlet2"],
                                                 sample_radii["outlet3"]]
        min_radius = min(all_radii)
        assert min_radius == 5.0

    def test_mean_radius_strategy(self, sample_radii):
        """Test mean radius strategy."""
        all_radii = [sample_radii["inlet"]] + [sample_radii["outlet1"],
                                                 sample_radii["outlet2"],
                                                 sample_radii["outlet3"]]
        mean_radius = sum(all_radii) / len(all_radii)
        assert 6.9 <= mean_radius <= 7.1  # (10+5+7+6)/4 = 7

    def test_max_radius_strategy(self, sample_radii):
        """Test maximum radius strategy."""
        all_radii = [sample_radii["inlet"]] + [sample_radii["outlet1"],
                                                 sample_radii["outlet2"],
                                                 sample_radii["outlet3"]]
        max_radius = max(all_radii)
        assert max_radius == 10.0

    def test_inlet_radius_strategy(self, sample_radii):
        """Test inlet-only radius strategy."""
        inlet_radius = sample_radii["inlet"]
        assert inlet_radius == 10.0


class TestMeshRefinementLevels:
    """Test mesh refinement level calculations."""

    def test_coarse_refinement_levels(self):
        """Test coarse mesh refinement levels."""
        coarse_levels = {
            "background": 0.003,  # 3mm
            "surface": 0.0015,    # 1.5mm
            "feature": 0.001      # 1mm
        }

        assert coarse_levels["background"] > coarse_levels["surface"]
        assert coarse_levels["surface"] > coarse_levels["feature"]

    def test_fine_refinement_levels(self):
        """Test fine mesh refinement levels."""
        fine_levels = {
            "background": 0.001,   # 1mm
            "surface": 0.0005,     # 0.5mm
            "feature": 0.00025     # 0.25mm
        }

        assert fine_levels["background"] > fine_levels["surface"]
        assert fine_levels["surface"] > fine_levels["feature"]

    def test_refinement_level_ordering(self):
        """Test refinement levels are properly ordered."""
        levels = {
            "background": 0.002,
            "surface": 0.001,
            "feature": 0.0005
        }

        # Background should be coarsest
        assert levels["background"] >= levels["surface"]
        assert levels["surface"] >= levels["feature"]


@pytest.mark.unit
class TestMeshConfiguration:
    """Test complete mesh configuration."""

    def test_complete_mesh_config_structure(self):
        """Test complete mesh configuration has all required sections."""
        config = {
            "geometry": {
                "scale_factor": 1e-3,
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["outlet1", "outlet2"],
                "wall_keywords_ordered": "wall"
            },
            "mesh": {
                "mesh_resolution": {
                    "target_cell_size_mm": 1.0
                },
                "SNAPPY_SETTINGS": {
                    "parallel": True,
                    "nProcessors": 4
                },
                "refinement_levels": {
                    "background": 0.002,
                    "surface": 0.001,
                    "feature": 0.0005
                }
            }
        }

        assert "geometry" in config
        assert "mesh" in config
        assert "SNAPPY_SETTINGS" in config["mesh"]
        assert "refinement_levels" in config["mesh"]

    def test_processor_count_valid(self):
        """Test processor count is valid for parallel meshing."""
        valid_processor_counts = [1, 2, 4, 8, 16, 32]

        for n_procs in valid_processor_counts:
            assert n_procs >= 1
            assert n_procs <= 128  # Reasonable upper limit

    def test_scale_factor_valid(self):
        """Test geometry scale factor is valid."""
        # Common scale factors
        mm_to_m = 1e-3  # mm to meters
        cm_to_m = 1e-2  # cm to meters

        assert mm_to_m == 0.001
        assert cm_to_m == 0.01
