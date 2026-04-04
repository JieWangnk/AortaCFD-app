"""
Test suite for mesh_setup module.

Tests cover:
- GeometryAnalyzer class initialization
- Mesh config option processing
- Reference radius determination
- Cell size calculations
- Bounding box computations
"""

import pytest
import sys
import tempfile
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestGeometryAnalyzerInit:
    """Test GeometryAnalyzer initialization."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_init_basic(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test basic initialization."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        # Mock patch processing
        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]),
            0.015,
            np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {
                'wall_keywords_ordered': 'wall',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1', 'outlet2']
            },
            'mesh': {
                'SNAPPY_SETTINGS': {}
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create required directory structure
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            assert analyzer.case_dir == tmpdir
            assert analyzer.wall_patch == 'wall'
            assert analyzer.inlet_patch == 'inlet'
            assert len(analyzer.outlet_patches) == 2


class TestProcessMeshConfigOptions:
    """Test _process_mesh_config_options method."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_boundary_layer_config(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test boundary layer config processing."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]),
            0.015,
            np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {
                'wall_keywords_ordered': 'wall',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': []
            },
            'mesh': {
                'SNAPPY_SETTINGS': {},
                'boundary_layers': {
                    'enabled': True,
                    'num_layers': 5,
                    'expansion_ratio': 1.3,
                    'final_layer_thickness': 0.3
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            assert analyzer.snappy_settings['addLayers'] is True
            assert analyzer.snappy_settings['addLayer'] == 5
            assert analyzer.snappy_settings['expansionRatio'] == 1.3
            assert analyzer.snappy_settings['finalLayerThickness'] == 0.3

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_surface_refinement_levels(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test surface refinement levels processing."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]),
            0.015,
            np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {
                'wall_keywords_ordered': 'wall',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': []
            },
            'mesh': {
                'SNAPPY_SETTINGS': {
                    'surfaceRefinementLevels': [2, 4]
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            assert analyzer.snappy_settings['surfaceRefinementLevels'] == [2, 4]


class TestDetermineReferenceRadius:
    """Test _determine_reference_radius method."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_max_strategy(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test max reference radius strategy."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.side_effect = [
            (np.array([0.0, 0.0, 0.0]), 0.020, np.array([0.0, 0.0, 1.0])),  # inlet: 20mm
            (np.array([0.0, 0.0, 0.1]), 0.010, np.array([0.0, 0.0, 1.0])),  # outlet1: 10mm
            (np.array([0.0, 0.0, 0.2]), 0.015, np.array([0.0, 0.0, 1.0])),  # outlet2: 15mm
        ]
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {
                'wall_keywords_ordered': 'wall',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1', 'outlet2'],
                'reference_radius_strategy': 'max'
            },
            'mesh': {
                'SNAPPY_SETTINGS': {}
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            # Max of 20, 10, 15 mm = 20mm = 0.020 m
            assert analyzer.reference_radius_m == 0.020

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_inlet_strategy(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test inlet reference radius strategy."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.side_effect = [
            (np.array([0.0, 0.0, 0.0]), 0.018, np.array([0.0, 0.0, 1.0])),  # inlet
            (np.array([0.0, 0.0, 0.1]), 0.025, np.array([0.0, 0.0, 1.0])),  # outlet (larger)
        ]
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {
                'wall_keywords_ordered': 'wall',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'reference_radius_strategy': 'inlet'
            },
            'mesh': {
                'SNAPPY_SETTINGS': {}
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            # Should use inlet radius despite outlet being larger
            assert analyzer.reference_radius_m == 0.018

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_min_strategy(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test min reference radius strategy."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.side_effect = [
            (np.array([0.0, 0.0, 0.0]), 0.020, np.array([0.0, 0.0, 1.0])),
            (np.array([0.0, 0.0, 0.1]), 0.008, np.array([0.0, 0.0, 1.0])),
        ]
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {
                'wall_keywords_ordered': 'wall',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'reference_radius_strategy': 'min'
            },
            'mesh': {
                'SNAPPY_SETTINGS': {}
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            assert analyzer.reference_radius_m == 0.008

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_mean_strategy(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test mean reference radius strategy."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.side_effect = [
            (np.array([0.0, 0.0, 0.0]), 0.020, np.array([0.0, 0.0, 1.0])),
            (np.array([0.0, 0.0, 0.1]), 0.010, np.array([0.0, 0.0, 1.0])),
        ]
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {
                'wall_keywords_ordered': 'wall',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'reference_radius_strategy': 'mean'
            },
            'mesh': {
                'SNAPPY_SETTINGS': {}
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            # Mean of 20mm and 10mm = 15mm = 0.015m
            assert abs(analyzer.reference_radius_m - 0.015) < 1e-10


class TestMeshConstants:
    """Test mesh constants module functions."""

    def test_compute_cell_size_from_diameter(self):
        """Test cell size computation from cells per diameter."""
        from aortacfd_lib.utils.mesh_constants import compute_cell_size

        # 20mm diameter, 10 cells = 2mm cell size
        cell_size = compute_cell_size(
            cells_per_diameter=10,
            reference_diameter_mm=20.0
        )

        assert abs(cell_size - 2.0) < 1e-10  # Result is in mm

    def test_compute_cell_size_fine(self):
        """Test cell size computation for finer mesh."""
        from aortacfd_lib.utils.mesh_constants import compute_cell_size

        # 6.4mm diameter, 20 cells = 0.32mm cell size
        cell_size = compute_cell_size(
            cells_per_diameter=20,
            reference_diameter_mm=6.4
        )

        assert abs(cell_size - 0.32) < 1e-10

    def test_compute_cell_size_invalid_raises(self):
        """Test cell size computation raises for invalid inputs."""
        from aortacfd_lib.utils.mesh_constants import compute_cell_size

        with pytest.raises(ValueError):
            compute_cell_size(cells_per_diameter=0, reference_diameter_mm=10.0)

        with pytest.raises(ValueError):
            compute_cell_size(cells_per_diameter=10, reference_diameter_mm=-5.0)

    def test_check_blockmesh_size_ok(self):
        """Test blockMesh size check for reasonable mesh."""
        from aortacfd_lib.utils.mesh_constants import check_blockmesh_size

        # Small mesh: 100mm x 100mm x 100mm with 1mm cells = 1M cells
        result = check_blockmesh_size(
            target_cell_size_mm=1.0,
            bbox_volume_mm3=100 * 100 * 100  # 1,000,000 mm³
        )

        assert result['warning_level'] == 'ok'
        assert result['message'] is None

    def test_check_blockmesh_size_large(self):
        """Test blockMesh size check warns for large meshes."""
        from aortacfd_lib.utils.mesh_constants import check_blockmesh_size

        # Large mesh: very small cell size
        result = check_blockmesh_size(
            target_cell_size_mm=0.5,
            bbox_volume_mm3=1000 * 1000 * 1000  # 1 billion mm³
        )

        # Should have a warning
        assert result['warning_level'] in ['large', 'very_large', 'huge']
        assert result['message'] is not None


class TestPlanSpanBackground:
    """Test plan_span_background() shared planner function."""

    def test_span_12(self):
        """cells_across_span=12 → bg=6, level=1, theoretical=12."""
        from aortacfd_lib.utils.mesh_constants import plan_span_background

        result = plan_span_background(12)
        assert result['background_cpd'] == 6
        assert result['span_level'] == 1
        assert result['theoretical_cells_across'] == 12
        assert result['warning'] is None

    def test_span_20(self):
        """cells_across_span=20 → bg=5, level=2, theoretical=20."""
        from aortacfd_lib.utils.mesh_constants import plan_span_background

        result = plan_span_background(20)
        assert result['background_cpd'] == 5
        assert result['span_level'] == 2
        assert result['theoretical_cells_across'] == 20
        assert result['warning'] is None

    def test_span_16(self):
        """cells_across_span=16 → bg=8, level=1, theoretical=16."""
        from aortacfd_lib.utils.mesh_constants import plan_span_background

        result = plan_span_background(16)
        assert result['background_cpd'] == 8
        assert result['span_level'] == 1
        assert result['theoretical_cells_across'] == 16
        assert result['warning'] is None

    def test_span_8_low_target(self):
        """cells_across_span=8 → bg=4, level=1, theoretical=8."""
        from aortacfd_lib.utils.mesh_constants import plan_span_background

        result = plan_span_background(8)
        assert result['background_cpd'] == 4
        assert result['span_level'] == 1
        assert result['theoretical_cells_across'] == 8
        assert result['warning'] is None

    def test_span_high_target_capped(self):
        """High target exceeding range produces warning and caps."""
        from aortacfd_lib.utils.mesh_constants import plan_span_background

        result = plan_span_background(200)
        assert result['background_cpd'] >= 4
        assert result['background_cpd'] <= 8
        assert result['span_level'] == 4  # max
        assert result['warning'] is not None
        assert 'exceeds' in result['warning']

    def test_always_returns_valid(self):
        """Planner always returns a valid result regardless of input."""
        from aortacfd_lib.utils.mesh_constants import plan_span_background

        for target in [4, 8, 12, 16, 20, 25, 30, 40, 50, 100]:
            result = plan_span_background(target)
            assert result['background_cpd'] >= 4
            assert result['background_cpd'] <= 8
            assert 1 <= result['span_level'] <= 4
            assert result['theoretical_cells_across'] == result['background_cpd'] * (2 ** result['span_level'])

    def test_theoretical_ge_target_when_possible(self):
        """Theoretical cells should meet or exceed target when within range."""
        from aortacfd_lib.utils.mesh_constants import plan_span_background

        for target in [8, 12, 16, 20]:
            result = plan_span_background(target)
            assert result['theoretical_cells_across'] >= target


class TestPatchProperties:
    """Test patch property calculations."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_inlet_properties_stored(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test inlet properties are correctly stored."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        expected_centroid = np.array([0.01, 0.02, 0.03])
        expected_radius = 0.012
        expected_normal = np.array([0.0, 0.0, 1.0])

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            expected_centroid,
            expected_radius,
            expected_normal
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {
                'wall_keywords_ordered': 'wall',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': []
            },
            'mesh': {
                'SNAPPY_SETTINGS': {}
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            np.testing.assert_array_almost_equal(analyzer.inlet_centroid, expected_centroid)
            assert analyzer.inlet_radius == expected_radius
            np.testing.assert_array_almost_equal(analyzer.inlet_normal, expected_normal)

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_outlet_properties_stored(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test outlet properties are correctly stored."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.side_effect = [
            (np.array([0.0, 0.0, 0.0]), 0.015, np.array([0.0, 0.0, 1.0])),  # inlet
            (np.array([0.1, 0.0, 0.0]), 0.010, np.array([1.0, 0.0, 0.0])),  # outlet1
            (np.array([0.0, 0.1, 0.0]), 0.008, np.array([0.0, 1.0, 0.0])),  # outlet2
        ]
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {
                'wall_keywords_ordered': 'wall',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1', 'outlet2']
            },
            'mesh': {
                'SNAPPY_SETTINGS': {}
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            assert len(analyzer.outlet_centroids) == 2
            assert len(analyzer.outlet_radii) == 2
            assert analyzer.outlet_radii[0] == 0.010
            assert analyzer.outlet_radii[1] == 0.008


class TestAllPatches:
    """Test all_patches property."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_all_patches_construction(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test all_patches list is constructed correctly."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]),
            0.015,
            np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {
                'wall_keywords_ordered': 'wall_aorta',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1', 'outlet2', 'outlet3']
            },
            'mesh': {
                'SNAPPY_SETTINGS': {}
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            assert 'wall_aorta' in analyzer.all_patches
            assert 'inlet' in analyzer.all_patches
            assert 'outlet1' in analyzer.all_patches
            assert 'outlet2' in analyzer.all_patches
            assert 'outlet3' in analyzer.all_patches
            assert len(analyzer.all_patches) == 5


class TestBoundaryLayerCamelCase:
    """Test boundary layer config accepts camelCase keys."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_camelcase_boundary_layer_config(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test camelCase boundary layer config keys."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]),
            0.015,
            np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {
                'wall_keywords_ordered': 'wall',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': []
            },
            'mesh': {
                'SNAPPY_SETTINGS': {},
                'boundary_layers': {
                    'nSurfaceLayers': 6,
                    'expansionRatio': 1.2,
                    'finalLayerThickness': 0.4,
                    'minThickness': 0.001
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            assert analyzer.snappy_settings['addLayer'] == 6
            assert analyzer.snappy_settings['expansionRatio'] == 1.2
            assert analyzer.snappy_settings['finalLayerThickness'] == 0.4
            assert analyzer.snappy_settings['minThickness'] == 0.001


class TestCoercePositive:
    """Test _coerce_positive method."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_coerce_positive_valid(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test coerce_positive with valid positive numbers."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.015, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            assert analyzer._coerce_positive(10, "test") == 10.0
            assert analyzer._coerce_positive(1.5, "test") == 1.5
            assert analyzer._coerce_positive("5.5", "test") == 5.5

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_coerce_positive_none(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test coerce_positive returns None for None input."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.015, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            assert analyzer._coerce_positive(None, "test") is None

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_coerce_positive_boolean(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test coerce_positive returns None for boolean input."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.015, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            assert analyzer._coerce_positive(True, "test") is None
            assert analyzer._coerce_positive(False, "test") is None

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_coerce_positive_negative(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test coerce_positive returns None for negative values."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.015, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            assert analyzer._coerce_positive(-5, "test") is None
            assert analyzer._coerce_positive(0, "test") is None


class TestCellSizeMethods:
    """Test cell size calculation methods."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_cell_size_from_target_mm(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test cell size from target_cell_size_mm."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.015, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            # Test with 1.0 mm target cell size
            cell_size, source = analyzer._cell_size_from_target_mm({'target_cell_size_mm': 1.0})

            assert cell_size == 0.001  # 1 mm = 0.001 m
            assert "target_cell_size_mm" in source

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_cell_size_from_target_mm_none(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test cell size returns None when target_cell_size_mm not set."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.015, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            cell_size, source = analyzer._cell_size_from_target_mm({})

            assert cell_size is None
            assert source is None

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_cell_size_from_cells_per_diameter(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test cell size from cells_per_diameter."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.010, np.array([0.0, 0.0, 1.0])  # 10mm radius
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            # 20mm diameter, 10 cells = 2mm cell size = 0.002m
            cell_size, source = analyzer._cell_size_from_cells_per_diameter({'cells_per_diameter': 10})

            assert abs(cell_size - 0.002) < 1e-10
            assert "cells_per_diameter" in source

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_cell_size_from_cells_per_diameter_no_geometry(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test cell size returns None without reference geometry."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.0, np.array([0.0, 0.0, 1.0])  # Invalid radius
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            cell_size, source = analyzer._cell_size_from_cells_per_diameter({'cells_per_diameter': 10})

            assert cell_size is None
            assert source is None


class TestBlockMeshBounds:
    """Test _get_blockmesh_bounds method."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_bounds_expansion(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test bounding box expansion."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.015, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {'expansionFactor': 0.1}}  # 10% expansion
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            # Create simple vertex set
            vertices = np.array([
                [0.0, 0.0, 0.0],
                [1.0, 1.0, 1.0]
            ])

            bounds = analyzer._get_blockmesh_bounds(vertices)

            # Range is [0,1] for each axis = 1.0
            # With 10% expansion: min = 0 - 0.1*1 = -0.1, max = 1 + 0.1*1 = 1.1
            assert abs(bounds['min'][0] - (-0.1)) < 1e-10
            assert abs(bounds['max'][0] - 1.1) < 1e-10


class TestInternalPoint:
    """Test _get_internal_point_for_snappy method."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_internal_point_aligned_normal(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test internal point calculation with aligned normal."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        # Normal points toward outlets (aligned)
        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.side_effect = [
            (np.array([0.0, 0.0, 0.0]), 0.010, np.array([0.0, 0.0, 1.0])),  # inlet
            (np.array([0.0, 0.0, 0.1]), 0.008, np.array([0.0, 0.0, 1.0])),  # outlet
        ]
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': ['outlet']},
            'mesh': {'SNAPPY_SETTINGS': {}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            internal_point = analyzer._get_internal_point_for_snappy()

            # Should move in +z direction (toward outlet)
            assert internal_point[2] > 0  # z should be positive

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_internal_point_flipped_normal(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test internal point calculation with flipped normal."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        # Normal points away from outlets (needs to be flipped)
        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.side_effect = [
            (np.array([0.0, 0.0, 0.0]), 0.010, np.array([0.0, 0.0, -1.0])),  # inlet normal points -z
            (np.array([0.0, 0.0, 0.1]), 0.008, np.array([0.0, 0.0, 1.0])),  # outlet at +z
        ]
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': ['outlet']},
            'mesh': {'SNAPPY_SETTINGS': {}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            internal_point = analyzer._get_internal_point_for_snappy()

            # Should still move in +z direction (normal was flipped)
            assert internal_point[2] > 0

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_internal_point_no_outlets_raises(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test internal point raises error without outlets."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.010, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            with pytest.raises(ValueError, match="outlet centroids"):
                analyzer._get_internal_point_for_snappy()


class TestSpanRefinementLevel:
    """Test _calculate_span_refinement_level method."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_span_disabled_returns_default(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test returns default when span refinement disabled."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.015, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {'span_refinement_enabled': False}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            level = analyzer._calculate_span_refinement_level()

            assert level == 2  # Default

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_span_user_specified_level(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test returns user-specified span level."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.015, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {
                'span_refinement_enabled': True,
                'cells_across_span': 20,
                'span_refinement_level': 4
            }}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            level = analyzer._calculate_span_refinement_level()

            assert level == 4

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_span_auto_calculated_level(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test auto-calculates span level when not specified."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.015, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {
                'span_refinement_enabled': True,
                'cells_across_span': 16  # Should require level 2 (16/4 = 4 blockMesh cells)
            }}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            level = analyzer._calculate_span_refinement_level()

            # Should auto-calculate a span level (exact value depends on algorithm)
            assert level >= 1 and level <= 4


class TestResolveCellSize:
    """Test _resolve_cell_size method (priority system)."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_priority_1_target_mm(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test priority 1: target_cell_size_mm is used first."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.015, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            # Both target_mm and cells_per_diameter set - target_mm takes priority
            mesh_resolution = {
                'target_cell_size_mm': 0.8,
                'cells_per_diameter': 20
            }

            cell_size, source, priority = analyzer._resolve_cell_size(mesh_resolution)

            assert priority == 1
            assert abs(cell_size - 0.0008) < 1e-10  # 0.8mm
            assert "target_cell_size_mm" in source

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_priority_2_cells_per_diameter(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test priority 2: cells_per_diameter when target_mm not set."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.010, np.array([0.0, 0.0, 1.0])  # 10mm radius
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            mesh_resolution = {'cells_per_diameter': 20}

            cell_size, source, priority = analyzer._resolve_cell_size(mesh_resolution)

            assert priority == 2
            # 20mm diameter / 20 cells = 1mm = 0.001m
            assert abs(cell_size - 0.001) < 1e-10
            assert "cells_per_diameter" in source

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_priority_3_fallback(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test priority 3: fallback when nothing specified."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.010, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            mesh_resolution = {}  # Nothing specified

            cell_size, source, priority = analyzer._resolve_cell_size(mesh_resolution)

            assert priority == 3
            assert cell_size is not None
            assert "FALLBACK" in source or "cells/D" in source


class TestTopLevelCellsPerDiameterMigration:
    """Test that top-level mesh.cells_per_diameter is migrated to mesh_resolution."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    @patch('aortacfd_lib.mesh_setup.check_blockmesh_size')
    def test_top_level_cpd_used(self, mock_check, mock_loader, mock_env, mock_logger, mock_patch):
        """Top-level cells_per_diameter should be picked up by _calculate_blockmesh_cells."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.010, np.array([0.0, 0.0, 1.0])  # 10mm radius = 20mm diameter
        )
        mock_patch.return_value = mock_patch_instance
        mock_check.return_value = {'warning_level': 'ok', 'message': ''}

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {
                'SNAPPY_SETTINGS': {},
                'cells_per_diameter': 15,  # Top-level — this is how JSON configs set it
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)
            bounds = {
                'min': np.array([0.0, 0.0, 0.0]),
                'max': np.array([0.1, 0.05, 0.05]),  # 100x50x50 mm
            }
            result = analyzer._calculate_blockmesh_cells(bounds)

            # 20mm diameter / 15 cells = 1.333mm cell size
            # 100mm / 1.333 = 75 cells in x
            assert result['x'] == 75
            assert result['y'] == 38  # 50/1.333 ≈ 37.5 → round to 38
            assert result['z'] == 38

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    @patch('aortacfd_lib.mesh_setup.check_blockmesh_size')
    def test_nested_cpd_takes_precedence(self, mock_check, mock_loader, mock_env, mock_logger, mock_patch):
        """Nested mesh_resolution.cells_per_diameter should take precedence over top-level."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.010, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance
        mock_check.return_value = {'status': 'ok'}

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {
                'SNAPPY_SETTINGS': {},
                'cells_per_diameter': 15,  # Top-level
                'mesh_resolution': {'cells_per_diameter': 20},  # Nested — should win
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            # Directly test _resolve_cell_size to confirm nested wins
            raw_mr = analyzer.mesh_settings.get('mesh_resolution', {})
            mr = raw_mr if isinstance(raw_mr, dict) else {}
            if 'cells_per_diameter' not in mr:
                top_cpd = analyzer.mesh_settings.get('cells_per_diameter')
                if top_cpd is not None:
                    mr['cells_per_diameter'] = top_cpd

            cell_size, source, priority = analyzer._resolve_cell_size(mr)
            # 20mm diam / 20 cells = 1mm = 0.001m
            assert abs(cell_size - 0.001) < 1e-10
            assert priority == 2


class TestExtractVerticesFromSTL:
    """Test _extract_vertices_from_stl method."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    @patch('aortacfd_lib.mesh_setup.np_stl_mesh.Mesh')
    def test_extract_vertices_success(self, mock_stl_mesh, mock_loader, mock_env, mock_logger, mock_patch):
        """Test successful vertex extraction from STL."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        # Setup mock STL mesh
        mock_mesh_instance = MagicMock()
        mock_mesh_instance.vectors = np.array([
            [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
            [[0, 0, 0], [0, 1, 0], [0, 0, 1]],
        ])
        mock_stl_mesh.from_file.return_value = mock_mesh_instance

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.015, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            vertices = analyzer._extract_vertices_from_stl("test.stl")

            assert vertices is not None
            assert len(vertices) > 0

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    @patch('aortacfd_lib.mesh_setup.np_stl_mesh.Mesh')
    def test_extract_vertices_file_not_found(self, mock_stl_mesh, mock_loader, mock_env, mock_logger, mock_patch):
        """Test vertex extraction raises on missing file."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_stl_mesh.from_file.side_effect = FileNotFoundError("File not found")

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.015, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            with pytest.raises(RuntimeError, match="Error processing STL"):
                analyzer._extract_vertices_from_stl("nonexistent.stl")


class TestCalculateBlockmeshCells:
    """Test _calculate_blockmesh_cells method."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_calculate_cells_target_mm(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test cell calculation with target_cell_size_mm."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.015, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {
                'SNAPPY_SETTINGS': {},
                'mesh_resolution': {'target_cell_size_mm': 1.0}
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            bounds = {
                'min': np.array([0.0, 0.0, 0.0]),
                'max': np.array([0.1, 0.1, 0.1])  # 100mm x 100mm x 100mm
            }

            cells = analyzer._calculate_blockmesh_cells(bounds)

            # With 1mm cell size, 100mm should give ~100 cells
            assert 'x' in cells
            assert 'y' in cells
            assert 'z' in cells
            assert cells['x'] > 50
            assert cells['y'] > 50
            assert cells['z'] > 50


class TestCellSizeFromDefaultFallback:
    """Test _cell_size_from_default_fallback method."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_fallback_with_geometry(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test fallback with valid geometry."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.010, np.array([0.0, 0.0, 1.0])  # 10mm radius
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {}}  # No span refinement
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            cell_size, source = analyzer._cell_size_from_default_fallback()

            assert cell_size is not None
            assert cell_size > 0
            assert "FALLBACK" in source or "cells/D" in source

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_fallback_with_span_refinement(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test fallback with span refinement enabled."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.010, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {
                'span_refinement_enabled': True,
                'cells_across_span': 20
            }}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            cell_size, source = analyzer._cell_size_from_default_fallback()

            assert cell_size is not None
            assert "SPAN_REFINEMENT" in source

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_fallback_no_geometry(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test fallback without valid geometry."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.0, np.array([0.0, 0.0, 1.0])  # Zero radius
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            cell_size, source = analyzer._cell_size_from_default_fallback()

            assert cell_size is not None
            assert "CRITICAL" in source


class TestGetAllVertices:
    """Test _get_all_vertices method."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    @patch('aortacfd_lib.mesh_setup.np_stl_mesh.Mesh')
    def test_get_all_vertices_combines_patches(self, mock_stl_mesh, mock_loader, mock_env, mock_logger, mock_patch):
        """Test all vertices from all patches are combined."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        # Setup mock STL mesh
        mock_mesh_instance = MagicMock()
        mock_mesh_instance.vectors = np.array([
            [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
        ])
        mock_stl_mesh.from_file.return_value = mock_mesh_instance

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.015, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {
                'wall_keywords_ordered': 'wall',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1']
            },
            'mesh': {'SNAPPY_SETTINGS': {}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            vertices = analyzer._get_all_vertices()

            # Should have called from_file for each patch (wall, inlet, outlet1)
            assert mock_stl_mesh.from_file.call_count == 3
            assert vertices is not None


class TestWriteMeshFiles:
    """Test mesh file writing methods."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    @patch('aortacfd_lib.mesh_setup.np_stl_mesh.Mesh')
    def test_write_all_mesh_files_creates_output(self, mock_stl_mesh, mock_loader, mock_logger, mock_patch):
        """Test write_all_mesh_files creates dictionary files."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        # Setup mock STL mesh
        mock_mesh_instance = MagicMock()
        mock_mesh_instance.vectors = np.array([
            [[0, 0, 0], [0.01, 0, 0], [0, 0.01, 0]],
            [[0, 0, 0.01], [0.01, 0, 0.01], [0, 0.01, 0.01]],
        ])
        mock_stl_mesh.from_file.return_value = mock_mesh_instance

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.side_effect = [
            (np.array([0.005, 0.005, 0.0]), 0.005, np.array([0.0, 0.0, 1.0])),
            (np.array([0.005, 0.005, 0.01]), 0.003, np.array([0.0, 0.0, 1.0])),
        ]
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {
                'wall_keywords_ordered': 'wall',
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
            },
            'mesh': {
                'SNAPPY_SETTINGS': {},
                'mesh_resolution': {'target_cell_size_mm': 1.0}
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create required directories
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)
            system_path = Path(tmpdir) / "system"
            system_path.mkdir(parents=True)

            # Mock jinja environment at module level
            mock_env_instance = MagicMock()
            mock_template = MagicMock()
            mock_template.render.return_value = "rendered content"
            mock_env_instance.get_template.return_value = mock_template

            # Patch Environment at the mesh_setup module level (not globally)
            with patch('aortacfd_lib.mesh_setup.Environment', return_value=mock_env_instance):
                analyzer = GeometryAnalyzer(config, tmpdir)

                analyzer.write_all_mesh_files()

                # Should have called get_template for blockMeshDict, snappyHexMeshDict, surfaceFeaturesDict
                assert mock_env_instance.get_template.call_count >= 3


class TestValidateResolutionConfig:
    """Test _validate_resolution_config method."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_conflict_warning_both_set(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test warning when both legacy parameters are set."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.015, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        # Setup mock logger
        mock_log_instance = MagicMock()
        mock_logger_class = MagicMock()
        mock_logger_class.return_value.get_logger.return_value = mock_log_instance
        mock_logger.return_value = mock_logger_class.return_value

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            mesh_resolution = {
                'target_cell_size_mm': 1.0,
                'cells_per_diameter': 20
            }

            analyzer._validate_resolution_config(mesh_resolution)

            # Should have logged a warning about conflict
            # The warning method should have been called


class TestCellSizeStrategies:
    """Test _get_cell_size_strategies method."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_strategies_returns_three_priorities(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test strategies method returns all three priorities."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.015, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            strategies = analyzer._get_cell_size_strategies({})

            assert len(strategies) == 3
            priorities = [s[0] for s in strategies]
            assert priorities == [1, 2, 3]


class TestSpanRefinementWithUserLevel:
    """Test span refinement with user-specified level."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_span_refinement_user_level(self, mock_loader, mock_env, mock_logger, mock_patch):
        """Test span refinement with user-specified span_refinement_level."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.010, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {
                'span_refinement_enabled': True,
                'cells_across_span': 32,
                'span_refinement_level': 3
            }}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(config, tmpdir)

            cell_size, source = analyzer._cell_size_from_default_fallback()

            assert "SPAN_REFINEMENT" in source
            assert "span_level=3" in source


class TestMeshStrategy:
    """Test mesh strategy routing (adaptive_span vs legacy_surface)."""

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_adaptive_span_enables_span_in_fallback(self, mock_loader, mock_env, mock_logger, mock_patch):
        """adaptive_span strategy auto-enables span refinement in the fallback path."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.012, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {'mesh_strategy': 'adaptive_span'}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)
            analyzer = GeometryAnalyzer(config, tmpdir)

            # Fallback path should auto-enable span
            mesh_resolution = {}  # No user resolution → fallback triggers
            cell_size, source, priority = analyzer._resolve_cell_size(mesh_resolution)

            assert analyzer.snappy_settings['span_refinement_enabled'] is True
            assert analyzer.snappy_settings['cells_across_span'] == 12  # default
            assert "SPAN_REFINEMENT" in source

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_legacy_surface_preserves_old_behaviour(self, mock_loader, mock_env, mock_logger, mock_patch):
        """legacy_surface strategy uses old cpd=10 fallback."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.012, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {'mesh_strategy': 'legacy_surface'}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)
            analyzer = GeometryAnalyzer(config, tmpdir)

            mesh_resolution = {}
            cell_size, source, priority = analyzer._resolve_cell_size(mesh_resolution)

            assert priority == 3
            assert "FALLBACK" in source
            assert analyzer.snappy_settings.get('span_refinement_enabled', False) is False

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_explicit_cpd_ignores_strategy(self, mock_loader, mock_env, mock_logger, mock_patch):
        """When user sets cells_per_diameter, strategy doesn't matter — priority 2 fires."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.012, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {'mesh_strategy': 'adaptive_span'}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)
            analyzer = GeometryAnalyzer(config, tmpdir)

            mesh_resolution = {'cells_per_diameter': 20}
            cell_size, source, priority = analyzer._resolve_cell_size(mesh_resolution)

            assert priority == 2
            assert "cells_per_diameter" in source

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_surface_levels_reduced_in_adaptive_span(self, mock_loader, mock_env, mock_logger, mock_patch):
        """adaptive_span reduces surface refinement to [0,1] when not user-set."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.012, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {
                'mesh_strategy': 'adaptive_span',
                'surfaceRefinementLevels': [1, 2],  # base default, not user-set
            }}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)
            analyzer = GeometryAnalyzer(config, tmpdir)

            assert analyzer.snappy_settings['surfaceRefinementLevels'] == [0, 1]

    @patch('aortacfd_lib.mesh_setup.PatchProcessing')
    @patch('aortacfd_lib.mesh_setup.Logger')
    @patch('aortacfd_lib.mesh_setup.Environment')
    @patch('aortacfd_lib.mesh_setup.FileSystemLoader')
    def test_surface_levels_preserved_when_user_set(self, mock_loader, mock_env, mock_logger, mock_patch):
        """User-specified surfaceRefinementLevels are preserved in adaptive_span."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.012, np.array([0.0, 0.0, 1.0])
        )
        mock_patch.return_value = mock_patch_instance

        config = {
            'geometry': {'wall_keywords_ordered': 'wall', 'inlet_keywords_ordered': 'inlet', 'outlet_keywords_ordered': []},
            'mesh': {'SNAPPY_SETTINGS': {
                'mesh_strategy': 'adaptive_span',
                'surfaceRefinementLevels': [2, 3],
                '_user_provided_keys': ['surfaceRefinementLevels'],  # tagged by ConfigBuilder
            }}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)
            analyzer = GeometryAnalyzer(config, tmpdir)

            assert analyzer.snappy_settings['surfaceRefinementLevels'] == [2, 3]


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
