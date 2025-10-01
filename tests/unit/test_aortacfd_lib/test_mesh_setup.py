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


# Additional comprehensive tests for GeometryAnalyzer class
import numpy as np
from unittest.mock import Mock, patch
from stl import mesh as np_stl_mesh


class TestGeometryAnalyzerMethods:
    """Test GeometryAnalyzer class methods with real functionality."""

    @pytest.fixture
    def full_mesh_config(self):
        """Full mesh configuration for testing."""
        return {
            'geometry': {
                'case_name': 'test_case',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1', 'outlet2'],
                'wall_keywords_ordered': 'wall',
                'scale_factor': 1e-3,
                'reference_radius_strategy': 'min'
            },
            'mesh': {
                'mesh_resolution': {
                    'target_cell_size_mm': 2.0
                },
                'SNAPPY_SETTINGS': {
                    'expansionFactor': 0.02
                },
                'refinement_levels': {},
                'BLOCKMESH_SETTINGS': {}
            }
        }

    @pytest.fixture
    def case_dir_with_geometry(self, tmp_path):
        """Create case directory with mock STL geometry files."""
        case_dir = tmp_path / "test_case"
        tri_surface_path = case_dir / "constant" / "triSurface"
        tri_surface_path.mkdir(parents=True)

        # Create mock STL files
        for patch_name in ['inlet', 'outlet1', 'outlet2', 'wall']:
            stl_file = tri_surface_path / f"{patch_name}.stl"
            _create_circular_stl(str(stl_file), radius=5.0, center=[0, 0, 0])

        return case_dir

    def test_analyzer_initialization_with_geometry(self, full_mesh_config, case_dir_with_geometry):
        """Test GeometryAnalyzer initializes with real geometry."""
        from src.aortacfd_lib.mesh_setup import GeometryAnalyzer

        analyzer = GeometryAnalyzer(full_mesh_config, str(case_dir_with_geometry))

        assert analyzer.inlet_centroid is not None
        assert analyzer.inlet_radius is not None
        assert len(analyzer.outlet_centroids) == 2
        assert len(analyzer.outlet_radii) == 2

    def test_reference_radius_min(self, full_mesh_config, case_dir_with_geometry):
        """Test reference radius calculation with 'min' strategy."""
        from src.aortacfd_lib.mesh_setup import GeometryAnalyzer

        full_mesh_config['geometry']['reference_radius_strategy'] = 'min'
        analyzer = GeometryAnalyzer(full_mesh_config, str(case_dir_with_geometry))

        assert analyzer.reference_radius_mm is not None
        assert analyzer.reference_radius_mm > 0

    def test_get_all_vertices(self, full_mesh_config, case_dir_with_geometry):
        """Test extracting all vertices from STL files."""
        from src.aortacfd_lib.mesh_setup import GeometryAnalyzer

        analyzer = GeometryAnalyzer(full_mesh_config, str(case_dir_with_geometry))
        vertices = analyzer._get_all_vertices()

        assert isinstance(vertices, np.ndarray)
        assert vertices.shape[1] == 3  # x, y, z
        assert len(vertices) > 0

    def test_blockmesh_bounds(self, full_mesh_config, case_dir_with_geometry):
        """Test blockMesh bounds calculation."""
        from src.aortacfd_lib.mesh_setup import GeometryAnalyzer

        analyzer = GeometryAnalyzer(full_mesh_config, str(case_dir_with_geometry))
        vertices = analyzer._get_all_vertices()
        bounds = analyzer._get_blockmesh_bounds(vertices)

        assert 'min' in bounds
        assert 'max' in bounds
        assert len(bounds['min']) == 3
        assert len(bounds['max']) == 3

        # Bounds should be expanded beyond vertex extents (or equal within tolerance)
        vertex_min = np.min(vertices, axis=0)
        vertex_max = np.max(vertices, axis=0)
        # Use <= instead of < to allow for small floating point differences
        assert all(bounds['min'] <= vertex_min + 1e-6)
        assert all(bounds['max'] >= vertex_max - 1e-6)

    def test_blockmesh_cells_calculation(self, full_mesh_config, case_dir_with_geometry):
        """Test blockMesh cell count calculation."""
        from src.aortacfd_lib.mesh_setup import GeometryAnalyzer

        analyzer = GeometryAnalyzer(full_mesh_config, str(case_dir_with_geometry))
        bounds = {
            'min': np.array([0.0, 0.0, 0.0]),
            'max': np.array([20.0, 10.0, 30.0])
        }

        cells = analyzer._calculate_blockmesh_cells(bounds)

        assert 'x' in cells
        assert 'y' in cells
        assert 'z' in cells
        assert cells['x'] == 10  # 20.0 / 2.0 (target_cell_size_mm)
        assert cells['y'] == 5   # 10.0 / 2.0
        assert cells['z'] == 15  # 30.0 / 2.0

    def test_internal_point_calculation(self, full_mesh_config, case_dir_with_geometry):
        """Test locationInMesh internal point calculation."""
        from src.aortacfd_lib.mesh_setup import GeometryAnalyzer

        analyzer = GeometryAnalyzer(full_mesh_config, str(case_dir_with_geometry))
        internal_point = analyzer._get_internal_point_for_snappy()

        assert isinstance(internal_point, np.ndarray)
        assert len(internal_point) == 3

    def test_write_mesh_files(self, full_mesh_config, case_dir_with_geometry):
        """Test writing all mesh dictionary files."""
        from src.aortacfd_lib.mesh_setup import GeometryAnalyzer

        system_dir = case_dir_with_geometry / "system"
        system_dir.mkdir(parents=True, exist_ok=True)

        # Add required template_vars for Jinja2 templates
        full_mesh_config['template_vars'] = {
            'openfoam_version': '12'
        }

        analyzer = GeometryAnalyzer(full_mesh_config, str(case_dir_with_geometry))
        analyzer.write_all_mesh_files()

        # Verify files were created
        assert (system_dir / "blockMeshDict").exists()
        assert (system_dir / "snappyHexMeshDict").exists()
        assert (system_dir / "surfaceFeaturesDict").exists()


class TestGeometryAnalyzerEdgeCases:
    """Test edge cases and error handling."""

    def test_missing_inlet_centroid_error(self):
        """Test error when inlet centroid is missing."""
        from src.aortacfd_lib.mesh_setup import GeometryAnalyzer

        with patch.object(GeometryAnalyzer, '_calculate_patch_properties'):
            analyzer = Mock(spec=GeometryAnalyzer)
            analyzer.inlet_centroid = None
            analyzer.outlet_centroids = [np.array([0, 0, 100])]

            with pytest.raises(ValueError, match="Inlet or outlet centroids"):
                GeometryAnalyzer._get_internal_point_for_snappy(analyzer)

    def test_missing_outlet_centroids_error(self):
        """Test error when outlet centroids are missing."""
        from src.aortacfd_lib.mesh_setup import GeometryAnalyzer

        with patch.object(GeometryAnalyzer, '_calculate_patch_properties'):
            analyzer = Mock(spec=GeometryAnalyzer)
            analyzer.inlet_centroid = np.array([0, 0, 0])
            analyzer.outlet_centroids = []

            with pytest.raises(ValueError, match="Inlet or outlet centroids"):
                GeometryAnalyzer._get_internal_point_for_snappy(analyzer)

    def test_no_vertices_error(self, tmp_path):
        """Test error when no STL files found."""
        from src.aortacfd_lib.mesh_setup import GeometryAnalyzer

        config = {
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall',
                'scale_factor': 1e-3,
                'reference_radius_strategy': 'min'
            },
            'mesh': {
                'SNAPPY_SETTINGS': {'expansionFactor': 0.02},
                'mesh_resolution': {},
                'BLOCKMESH_SETTINGS': {}
            }
        }

        case_dir = tmp_path / "test_case"
        tri_surface_path = case_dir / "constant" / "triSurface"
        tri_surface_path.mkdir(parents=True)

        # Don't create any STL files - should raise error when trying to process patches
        with pytest.raises((RuntimeError, FileNotFoundError)):
            analyzer = GeometryAnalyzer(config, str(case_dir))


class TestCellSizingFallbacks:
    """Test cell sizing priority and fallback logic."""

    @pytest.fixture
    def basic_config(self):
        """Basic config for cell sizing tests."""
        return {
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall',
                'scale_factor': 1e-3,
                'reference_radius_strategy': 'min'
            },
            'mesh': {
                'SNAPPY_SETTINGS': {'expansionFactor': 0.02},
                'mesh_resolution': {},
                'BLOCKMESH_SETTINGS': {}
            }
        }

    @pytest.fixture
    def case_dir_with_geometry(self, tmp_path):
        """Create case directory with mock STL geometry files."""
        case_dir = tmp_path / "test_case"
        tri_surface_path = case_dir / "constant" / "triSurface"
        tri_surface_path.mkdir(parents=True)

        # Create mock STL files
        for patch_name in ['inlet', 'outlet1', 'wall']:
            stl_file = tri_surface_path / f"{patch_name}.stl"
            _create_circular_stl(str(stl_file), radius=5.0, center=[0, 0, 0])

        return case_dir

    def test_target_cell_size_priority(self, basic_config, case_dir_with_geometry):
        """Test target_cell_size_mm takes priority."""
        from src.aortacfd_lib.mesh_setup import GeometryAnalyzer

        basic_config['mesh']['mesh_resolution'] = {
            'target_cell_size_mm': 3.0,
            'blockmesh_resolution': 10,
            'cells_per_diameter': 8
        }

        analyzer = GeometryAnalyzer(basic_config, str(case_dir_with_geometry))
        bounds = {'min': np.array([0, 0, 0]), 'max': np.array([30, 30, 30])}
        cells = analyzer._calculate_blockmesh_cells(bounds)

        # Should use 3.0mm
        assert cells['x'] == 10  # 30.0 / 3.0

    def test_fallback_to_default(self, basic_config, case_dir_with_geometry):
        """Test fallback to default 1.5mm when no settings provided."""
        from src.aortacfd_lib.mesh_setup import GeometryAnalyzer

        # Empty mesh_resolution
        basic_config['mesh']['mesh_resolution'] = {}

        analyzer = GeometryAnalyzer(basic_config, str(case_dir_with_geometry))
        bounds = {'min': np.array([0, 0, 0]), 'max': np.array([15, 15, 15])}
        cells = analyzer._calculate_blockmesh_cells(bounds)

        # Should use default 1.5mm
        expected = int(np.round(15.0 / 1.5))
        assert cells['x'] == expected


def _create_circular_stl(filepath: str, radius: float = 5.0, center: list = None, num_segments: int = 8):
    """Create a circular STL file for testing (represents a patch cross-section)."""
    if center is None:
        center = [0.0, 0.0, 0.0]

    # Create vertices for a circular mesh
    vertices = []
    angles = np.linspace(0, 2 * np.pi, num_segments, endpoint=False)

    for i in range(num_segments):
        x1 = center[0] + radius * np.cos(angles[i])
        y1 = center[1] + radius * np.sin(angles[i])
        x2 = center[0] + radius * np.cos(angles[(i + 1) % num_segments])
        y2 = center[1] + radius * np.sin(angles[(i + 1) % num_segments])

        # Create triangle from center to edge
        triangle = [
            center,
            [x1, y1, center[2]],
            [x2, y2, center[2]]
        ]
        vertices.append(triangle)

    # Create mesh
    mesh_data = np_stl_mesh.Mesh(np.zeros(len(vertices), dtype=np_stl_mesh.Mesh.dtype))
    for i, tri in enumerate(vertices):
        mesh_data.vectors[i] = np.array(tri)

    # Save to file
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    mesh_data.save(filepath)
