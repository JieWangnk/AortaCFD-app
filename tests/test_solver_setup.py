"""
Test suite for solver_setup module.

Tests cover:
- FvSolutionWriter class
- Template rendering
- Mesh-adaptive solver adjustments
- pRefPoint computation
- Quality report printing
"""

import pytest
import sys
import tempfile
import re
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestFvSolutionWriterInit:
    """Test FvSolutionWriter initialization."""

    @patch('aortacfd_lib.solver_setup.Logger')
    @patch('aortacfd_lib.solver_setup.Environment')
    @patch('aortacfd_lib.solver_setup.FileSystemLoader')
    @patch('aortacfd_lib.solver_setup.OFVersionAdapter')
    def test_init(self, mock_adapter, mock_loader, mock_env, mock_logger):
        """Test initialization with valid config."""
        from aortacfd_lib.solver_setup import FvSolutionWriter

        config = {
            'openfoam_version': '8',
            'fvSolution': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = FvSolutionWriter(config, tmpdir)

            assert writer.config == config
            assert writer.case_dir == tmpdir
            mock_adapter.assert_called_once_with('8')


class TestComputePRefPointFromMesh:
    """Test _compute_pRefPoint_from_mesh method."""

    @patch('aortacfd_lib.solver_setup.Logger')
    @patch('aortacfd_lib.solver_setup.Environment')
    @patch('aortacfd_lib.solver_setup.FileSystemLoader')
    @patch('aortacfd_lib.solver_setup.OFVersionAdapter')
    def test_compute_from_snappy_dict(self, mock_adapter, mock_loader, mock_env, mock_logger):
        """Test pRefPoint from snappyHexMeshDict."""
        from aortacfd_lib.solver_setup import FvSolutionWriter

        config = {'openfoam_version': '8', 'fvSolution': {}}

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create snappyHexMeshDict
            system_dir = Path(tmpdir) / "system"
            system_dir.mkdir()

            snappy_content = """
            FoamFile
            {
                version     2.0;
                format      ascii;
                class       dictionary;
                object      snappyHexMeshDict;
            }
            castellatedMeshControls
            {
                locationInMesh (0.01 0.02 0.03);
            }
            """

            snappy_file = system_dir / "snappyHexMeshDict"
            snappy_file.write_text(snappy_content)

            writer = FvSolutionWriter(config, tmpdir)
            pref = writer._compute_pRefPoint_from_mesh()

            assert pref is not None
            assert abs(pref[0] - 0.01) < 1e-10
            assert abs(pref[1] - 0.02) < 1e-10
            assert abs(pref[2] - 0.03) < 1e-10

    @patch('aortacfd_lib.solver_setup.Logger')
    @patch('aortacfd_lib.solver_setup.Environment')
    @patch('aortacfd_lib.solver_setup.FileSystemLoader')
    @patch('aortacfd_lib.solver_setup.OFVersionAdapter')
    def test_compute_from_checkmesh_log(self, mock_adapter, mock_loader, mock_env, mock_logger):
        """Test pRefPoint from checkMesh log bounding box."""
        from aortacfd_lib.solver_setup import FvSolutionWriter

        config = {'openfoam_version': '8', 'fvSolution': {}}

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create logs directory
            logs_dir = Path(tmpdir) / "logs"
            logs_dir.mkdir()

            checkmesh_content = """
            Mesh stats
            Overall domain bounding box (0.0 0.0 0.0) (0.1 0.2 0.3)
            Number of cells: 10000
            """

            checkmesh_file = logs_dir / "log.checkMesh"
            checkmesh_file.write_text(checkmesh_content)

            writer = FvSolutionWriter(config, tmpdir)
            pref = writer._compute_pRefPoint_from_mesh()

            assert pref is not None
            # Center of bounding box
            assert abs(pref[0] - 0.05) < 1e-10
            assert abs(pref[1] - 0.1) < 1e-10
            assert abs(pref[2] - 0.15) < 1e-10

    @patch('aortacfd_lib.solver_setup.Logger')
    @patch('aortacfd_lib.solver_setup.Environment')
    @patch('aortacfd_lib.solver_setup.FileSystemLoader')
    @patch('aortacfd_lib.solver_setup.OFVersionAdapter')
    def test_compute_no_mesh_files(self, mock_adapter, mock_loader, mock_env, mock_logger):
        """Test returns None when no mesh files available."""
        from aortacfd_lib.solver_setup import FvSolutionWriter

        config = {'openfoam_version': '8', 'fvSolution': {}}

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = FvSolutionWriter(config, tmpdir)
            pref = writer._compute_pRefPoint_from_mesh()

            assert pref is None


class TestApplyMeshAdaptiveSolver:
    """Test _apply_mesh_adaptive_solver method."""

    @patch('aortacfd_lib.solver_setup.Logger')
    @patch('aortacfd_lib.solver_setup.Environment')
    @patch('aortacfd_lib.solver_setup.FileSystemLoader')
    @patch('aortacfd_lib.solver_setup.OFVersionAdapter')
    def test_no_checkmesh_log(self, mock_adapter, mock_loader, mock_env, mock_logger):
        """Test returns base config when no checkMesh log."""
        from aortacfd_lib.solver_setup import FvSolutionWriter

        config = {
            'openfoam_version': '8',
            'fvSolution': {},
            'numerics': {'mesh_adaptive': True}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = FvSolutionWriter(config, tmpdir)

            base_fvsolution = {'PIMPLE': {'nOuterCorrectors': 3}}
            adjusted, report = writer._apply_mesh_adaptive_solver(base_fvsolution)

            assert adjusted == base_fvsolution
            assert report == {}

    @patch('aortacfd_lib.solver_setup.Logger')
    @patch('aortacfd_lib.solver_setup.Environment')
    @patch('aortacfd_lib.solver_setup.FileSystemLoader')
    @patch('aortacfd_lib.solver_setup.OFVersionAdapter')
    def test_import_error_handling(self, mock_adapter, mock_loader, mock_env, mock_logger):
        """Test handles ImportError gracefully."""
        from aortacfd_lib.solver_setup import FvSolutionWriter

        config = {
            'openfoam_version': '8',
            'fvSolution': {},
            'numerics': {'mesh_adaptive': True}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create logs directory with checkMesh log
            logs_dir = Path(tmpdir) / "logs"
            logs_dir.mkdir()
            (logs_dir / "log.checkMesh").write_text("dummy content")

            writer = FvSolutionWriter(config, tmpdir)

            base_fvsolution = {'PIMPLE': {'nOuterCorrectors': 3}}

            # Mock the import to raise ImportError
            with patch.dict('sys.modules', {'config.mesh_adaptive_solver': None}):
                adjusted, report = writer._apply_mesh_adaptive_solver(base_fvsolution)

            # Should return base config unchanged
            assert adjusted == base_fvsolution


class TestPrintQualityReport:
    """Test _print_quality_report method."""

    @patch('aortacfd_lib.solver_setup.Logger')
    @patch('aortacfd_lib.solver_setup.Environment')
    @patch('aortacfd_lib.solver_setup.FileSystemLoader')
    @patch('aortacfd_lib.solver_setup.OFVersionAdapter')
    def test_print_good_quality_report(self, mock_adapter, mock_loader, mock_env, mock_logger):
        """Test printing quality report for good mesh."""
        from aortacfd_lib.solver_setup import FvSolutionWriter

        # Create mock logger instance
        mock_log_instance = MagicMock()
        mock_logger.return_value.get_logger.return_value = mock_log_instance

        config = {'openfoam_version': '8', 'fvSolution': {}}

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = FvSolutionWriter(config, tmpdir)

            quality_report = {
                'tier': 'GOOD',
                'metrics': {
                    'max_skewness': 1.5,
                    'max_non_orthogonality': 45.0,
                    'max_aspect_ratio': 10.0
                },
                'recommendations': ['Mesh quality is acceptable']
            }

            writer._print_quality_report(quality_report)

            # Verify info was logged (not warning for GOOD quality)
            assert mock_log_instance.info.called

    @patch('aortacfd_lib.solver_setup.Logger')
    @patch('aortacfd_lib.solver_setup.Environment')
    @patch('aortacfd_lib.solver_setup.FileSystemLoader')
    @patch('aortacfd_lib.solver_setup.OFVersionAdapter')
    def test_print_poor_quality_report(self, mock_adapter, mock_loader, mock_env, mock_logger):
        """Test printing quality report for poor mesh triggers warning."""
        from aortacfd_lib.solver_setup import FvSolutionWriter

        mock_log_instance = MagicMock()
        mock_logger.return_value.get_logger.return_value = mock_log_instance

        config = {'openfoam_version': '8', 'fvSolution': {}}

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = FvSolutionWriter(config, tmpdir)

            quality_report = {
                'tier': 'POOR',
                'metrics': {
                    'max_skewness': 5.0,
                    'max_non_orthogonality': 85.0
                },
                'recommendations': ['Consider remeshing']
            }

            writer._print_quality_report(quality_report)

            # Verify warning was logged for POOR quality
            assert mock_log_instance.warning.called

    @patch('aortacfd_lib.solver_setup.Logger')
    @patch('aortacfd_lib.solver_setup.Environment')
    @patch('aortacfd_lib.solver_setup.FileSystemLoader')
    @patch('aortacfd_lib.solver_setup.OFVersionAdapter')
    def test_print_critical_quality_report(self, mock_adapter, mock_loader, mock_env, mock_logger):
        """Test printing quality report for critical mesh."""
        from aortacfd_lib.solver_setup import FvSolutionWriter

        mock_log_instance = MagicMock()
        mock_logger.return_value.get_logger.return_value = mock_log_instance

        config = {'openfoam_version': '8', 'fvSolution': {}}

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = FvSolutionWriter(config, tmpdir)

            quality_report = {
                'tier': 'CRITICAL',
                'metrics': {},
                'recommendations': []
            }

            writer._print_quality_report(quality_report)

            # Verify warning was logged for CRITICAL quality
            assert mock_log_instance.warning.called


class TestWriteFvSolutionFile:
    """Test write_fvSolution_file method."""

    @patch('aortacfd_lib.solver_setup.Logger')
    @patch('aortacfd_lib.solver_setup.prepare_fv_solution_context')
    @patch('aortacfd_lib.solver_setup.OFVersionAdapter')
    def test_write_basic_fvsolution(self, mock_adapter, mock_prepare, mock_logger):
        """Test basic fvSolution file writing."""
        from aortacfd_lib.solver_setup import FvSolutionWriter

        # Mock prepare_fv_solution_context
        mock_prepare.return_value = {
            'profile': 'standard',
            'pimple': {'nOuterCorrectors': 3},
            'relaxation': {'p': 0.5},
            'tolerances': {'p': 1e-5}
        }

        # Mock version adapter
        mock_adapter_instance = MagicMock()
        mock_adapter_instance.get_foam_file_header.return_value = "// Header"
        mock_adapter.return_value = mock_adapter_instance

        config = {
            'openfoam_version': '8',
            'openfoam_major_version': 8,
            'fvSolution': {
                'PIMPLE': {'nOuterCorrectors': 3}
            },
            'numerics': {'mesh_adaptive': False}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create system directory
            system_dir = Path(tmpdir) / "system"
            system_dir.mkdir()

            # Mock jinja template
            mock_template = MagicMock()
            mock_template.render.return_value = "// fvSolution content"

            with patch.object(FvSolutionWriter, '__init__', lambda self, config, case_dir: None):
                writer = FvSolutionWriter.__new__(FvSolutionWriter)
                writer.config = config
                writer.case_dir = tmpdir
                writer.log = MagicMock()
                writer.jinja_env = MagicMock()
                writer.jinja_env.get_template.return_value = mock_template
                writer.version_adapter = mock_adapter_instance

                writer.write_fvSolution_file()

                # Verify file was written
                fvsolution_path = Path(tmpdir) / "system" / "fvSolution"
                assert fvsolution_path.exists()
                assert fvsolution_path.read_text() == "// fvSolution content"


class TestLocationInMeshParsing:
    """Test locationInMesh parsing from snappyHexMeshDict."""

    def test_parse_scientific_notation(self):
        """Test parsing locationInMesh with scientific notation."""
        content = "locationInMesh (1.5e-2 2.0e-3 -3.5e-4)"
        pattern = r'locationInMesh\s*\(\s*([-\d.e+]+)\s+([-\d.e+]+)\s+([-\d.e+]+)\s*\)'
        match = re.search(pattern, content)

        assert match is not None
        x, y, z = float(match.group(1)), float(match.group(2)), float(match.group(3))
        assert abs(x - 0.015) < 1e-10
        assert abs(y - 0.002) < 1e-10
        assert abs(z - (-0.00035)) < 1e-10

    def test_parse_regular_notation(self):
        """Test parsing locationInMesh with regular numbers."""
        content = "locationInMesh (0.1 0.2 0.3)"
        pattern = r'locationInMesh\s*\(\s*([-\d.e+]+)\s+([-\d.e+]+)\s+([-\d.e+]+)\s*\)'
        match = re.search(pattern, content)

        assert match is not None
        x, y, z = float(match.group(1)), float(match.group(2)), float(match.group(3))
        assert x == 0.1
        assert y == 0.2
        assert z == 0.3


class TestBoundingBoxParsing:
    """Test bounding box parsing from checkMesh log."""

    def test_parse_bounding_box(self):
        """Test parsing bounding box coordinates."""
        content = "Overall domain bounding box (-0.1 -0.2 -0.3) (0.4 0.5 0.6)"
        pattern = r'Overall domain bounding box \(([-\d.e+]+)\s+([-\d.e+]+)\s+([-\d.e+]+)\)\s+\(([-\d.e+]+)\s+([-\d.e+]+)\s+([-\d.e+]+)\)'
        match = re.search(pattern, content)

        assert match is not None
        x1, y1, z1 = float(match.group(1)), float(match.group(2)), float(match.group(3))
        x2, y2, z2 = float(match.group(4)), float(match.group(5)), float(match.group(6))

        assert x1 == -0.1
        assert y1 == -0.2
        assert z1 == -0.3
        assert x2 == 0.4
        assert y2 == 0.5
        assert z2 == 0.6


class TestWriteFvSolutionWithMeshAdaptive:
    """Test write_fvSolution_file with mesh-adaptive enabled."""

    @patch('aortacfd_lib.solver_setup.Logger')
    @patch('aortacfd_lib.solver_setup.prepare_fv_solution_context')
    @patch('aortacfd_lib.solver_setup.OFVersionAdapter')
    def test_write_with_mesh_adaptive_enabled(self, mock_adapter, mock_prepare, mock_logger):
        """Test fvSolution writing with mesh adaptive enabled and quality report."""
        from aortacfd_lib.solver_setup import FvSolutionWriter

        # Mock prepare_fv_solution_context
        mock_prepare.return_value = {
            'profile': 'standard',
            'pimple': {'nOuterCorrectors': 3},
            'relaxation': {'p': 0.5},
            'tolerances': {'p': 1e-5}
        }

        # Mock version adapter
        mock_adapter_instance = MagicMock()
        mock_adapter_instance.get_foam_file_header.return_value = "// Header"
        mock_adapter.return_value = mock_adapter_instance

        config = {
            'openfoam_version': '8',
            'openfoam_major_version': 8,
            'fvSolution': {
                'PIMPLE': {'nOuterCorrectors': 3}
            },
            'numerics': {'mesh_adaptive': True, 'profile': 'standard'}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create system directory
            system_dir = Path(tmpdir) / "system"
            system_dir.mkdir()

            # Create logs directory with checkMesh log
            logs_dir = Path(tmpdir) / "logs"
            logs_dir.mkdir()
            (logs_dir / "log.checkMesh").write_text("Max skewness = 2.5\n")

            # Mock jinja template
            mock_template = MagicMock()
            mock_template.render.return_value = "// fvSolution content"

            with patch.object(FvSolutionWriter, '__init__', lambda self, config, case_dir: None):
                writer = FvSolutionWriter.__new__(FvSolutionWriter)
                writer.config = config
                writer.case_dir = tmpdir
                writer.log = MagicMock()
                writer.jinja_env = MagicMock()
                writer.jinja_env.get_template.return_value = mock_template
                writer.version_adapter = mock_adapter_instance

                # Mock mesh adaptive to return quality report with tier
                mock_mesh_adaptive = MagicMock()
                mock_mesh_adaptive.analyze_checkmesh_log = MagicMock()
                mock_mesh_adaptive.adjust_fvsolution_for_mesh.return_value = config['fvSolution']
                mock_mesh_adaptive.get_quality_report.return_value = {
                    'tier': 'GOOD',
                    'metrics': {'max_skewness': 2.5},
                    'recommendations': []
                }
                mock_mesh_adaptive.mesh_quality_tier = 'GOOD'

                with patch.dict('sys.modules', {'config.mesh_adaptive_solver': MagicMock(MeshAdaptiveSolverSettings=lambda: mock_mesh_adaptive)}):
                    writer.write_fvSolution_file()

                # Verify file was written
                fvsolution_path = Path(tmpdir) / "system" / "fvSolution"
                assert fvsolution_path.exists()

    @patch('aortacfd_lib.solver_setup.Logger')
    @patch('aortacfd_lib.solver_setup.prepare_fv_solution_context')
    @patch('aortacfd_lib.solver_setup.OFVersionAdapter')
    def test_write_creates_pimple_if_missing(self, mock_adapter, mock_prepare, mock_logger):
        """Test fvSolution creates PIMPLE dict if missing."""
        from aortacfd_lib.solver_setup import FvSolutionWriter

        mock_prepare.return_value = {
            'profile': 'standard',
            'pimple': {},
            'relaxation': {},
            'tolerances': {}
        }

        mock_adapter_instance = MagicMock()
        mock_adapter_instance.get_foam_file_header.return_value = "// Header"
        mock_adapter.return_value = mock_adapter_instance

        # Config without PIMPLE key
        config = {
            'openfoam_version': '8',
            'openfoam_major_version': 8,
            'fvSolution': {},  # No PIMPLE
            'numerics': {'mesh_adaptive': False}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            system_dir = Path(tmpdir) / "system"
            system_dir.mkdir()

            # Create snappyHexMeshDict for pRefPoint computation
            snappy_content = "locationInMesh (0.01 0.02 0.03);"
            (system_dir / "snappyHexMeshDict").write_text(snappy_content)

            mock_template = MagicMock()
            mock_template.render.return_value = "// fvSolution"

            with patch.object(FvSolutionWriter, '__init__', lambda self, config, case_dir: None):
                writer = FvSolutionWriter.__new__(FvSolutionWriter)
                writer.config = config
                writer.case_dir = tmpdir
                writer.log = MagicMock()
                writer.jinja_env = MagicMock()
                writer.jinja_env.get_template.return_value = mock_template
                writer.version_adapter = mock_adapter_instance

                writer.write_fvSolution_file()

                # PIMPLE should be created and pRefPoint should be set
                fvsolution_path = Path(tmpdir) / "system" / "fvSolution"
                assert fvsolution_path.exists()


class TestApplyMeshAdaptiveSolverSuccess:
    """Test _apply_mesh_adaptive_solver when MeshAdaptiveSolverSettings imports successfully."""

    @patch('aortacfd_lib.solver_setup.Logger')
    @patch('aortacfd_lib.solver_setup.Environment')
    @patch('aortacfd_lib.solver_setup.FileSystemLoader')
    @patch('aortacfd_lib.solver_setup.OFVersionAdapter')
    def test_mesh_adaptive_with_adjustments(self, mock_adapter, mock_loader, mock_env, mock_logger):
        """Test mesh adaptive makes adjustments when mesh quality is detected."""
        from aortacfd_lib.solver_setup import FvSolutionWriter

        config = {
            'openfoam_version': '8',
            'fvSolution': {},
            'numerics': {'mesh_adaptive': True, 'profile': 'standard'}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create logs directory with checkMesh log
            logs_dir = Path(tmpdir) / "logs"
            logs_dir.mkdir()
            (logs_dir / "log.checkMesh").write_text("Max skewness = 4.5\nMax non-orthogonality = 80\n")

            writer = FvSolutionWriter(config, tmpdir)

            base_fvsolution = {
                'PIMPLE': {'nOuterCorrectors': 3, 'nNonOrthogonalCorrectors': 1},
                'relaxationFactors': {'fields': {'p': 0.5}}
            }

            # Create mock for MeshAdaptiveSolverSettings
            mock_mesh_adaptive = MagicMock()
            mock_mesh_adaptive.analyze_checkmesh_log = MagicMock()
            mock_mesh_adaptive.adjust_fvsolution_for_mesh.return_value = {
                'PIMPLE': {'nOuterCorrectors': 5, 'nNonOrthogonalCorrectors': 2},
                'relaxationFactors': {'fields': {'p': 0.3}}
            }
            mock_mesh_adaptive.get_quality_report.return_value = {
                'tier': 'POOR',
                'metrics': {'max_skewness': 4.5},
                'recommendations': ['Remesh recommended']
            }
            mock_mesh_adaptive.mesh_quality_tier = 'POOR'

            # Mock the import
            mock_module = MagicMock()
            mock_module.MeshAdaptiveSolverSettings = lambda: mock_mesh_adaptive

            with patch.dict('sys.modules', {'config.mesh_adaptive_solver': mock_module}):
                adjusted, report = writer._apply_mesh_adaptive_solver(base_fvsolution)

            # Check adjustments were made
            assert adjusted['PIMPLE']['nOuterCorrectors'] == 5
            assert report['tier'] == 'POOR'

    @patch('aortacfd_lib.solver_setup.Logger')
    @patch('aortacfd_lib.solver_setup.Environment')
    @patch('aortacfd_lib.solver_setup.FileSystemLoader')
    @patch('aortacfd_lib.solver_setup.OFVersionAdapter')
    def test_mesh_adaptive_general_exception(self, mock_adapter, mock_loader, mock_env, mock_logger):
        """Test handles general exceptions gracefully."""
        from aortacfd_lib.solver_setup import FvSolutionWriter

        config = {
            'openfoam_version': '8',
            'fvSolution': {},
            'numerics': {'mesh_adaptive': True}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "logs"
            logs_dir.mkdir()
            (logs_dir / "log.checkMesh").write_text("dummy content")

            writer = FvSolutionWriter(config, tmpdir)

            base_fvsolution = {'PIMPLE': {'nOuterCorrectors': 3}}

            # Mock the import to raise a generic exception
            mock_module = MagicMock()
            mock_module.MeshAdaptiveSolverSettings.side_effect = RuntimeError("Unexpected error")

            with patch.dict('sys.modules', {'config.mesh_adaptive_solver': mock_module}):
                adjusted, report = writer._apply_mesh_adaptive_solver(base_fvsolution)

            # Should return base config unchanged
            assert adjusted == base_fvsolution
            assert report == {}


class TestComputePRefPointExceptions:
    """Test _compute_pRefPoint_from_mesh exception handling."""

    @patch('aortacfd_lib.solver_setup.Logger')
    @patch('aortacfd_lib.solver_setup.Environment')
    @patch('aortacfd_lib.solver_setup.FileSystemLoader')
    @patch('aortacfd_lib.solver_setup.OFVersionAdapter')
    def test_snappy_dict_parse_exception(self, mock_adapter, mock_loader, mock_env, mock_logger):
        """Test handles exception when parsing snappyHexMeshDict."""
        from aortacfd_lib.solver_setup import FvSolutionWriter

        config = {'openfoam_version': '8', 'fvSolution': {}}

        with tempfile.TemporaryDirectory() as tmpdir:
            system_dir = Path(tmpdir) / "system"
            system_dir.mkdir()

            # Create an invalid snappyHexMeshDict that will cause parsing to fail
            # But without matching locationInMesh, so regex doesn't match
            (system_dir / "snappyHexMeshDict").write_text("invalid content without locationInMesh")

            writer = FvSolutionWriter(config, tmpdir)

            # Use builtins.open mock to raise exception when reading file
            original_open = open
            def mock_open_raising(*args, **kwargs):
                if 'snappyHexMeshDict' in str(args[0]):
                    raise IOError("Mock read error")
                return original_open(*args, **kwargs)

            with patch('builtins.open', side_effect=mock_open_raising):
                pref = writer._compute_pRefPoint_from_mesh()

            # Should return None (falls through to checkMesh which doesn't exist)
            assert pref is None

    @patch('aortacfd_lib.solver_setup.Logger')
    @patch('aortacfd_lib.solver_setup.Environment')
    @patch('aortacfd_lib.solver_setup.FileSystemLoader')
    @patch('aortacfd_lib.solver_setup.OFVersionAdapter')
    def test_checkmesh_log_parse_exception(self, mock_adapter, mock_loader, mock_env, mock_logger):
        """Test handles exception when parsing checkMesh log."""
        from aortacfd_lib.solver_setup import FvSolutionWriter

        config = {'openfoam_version': '8', 'fvSolution': {}}

        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "logs"
            logs_dir.mkdir()

            # Create checkMesh log
            (logs_dir / "log.checkMesh").write_text("Overall domain bounding box (0 0 0) (1 1 1)")

            writer = FvSolutionWriter(config, tmpdir)

            # Mock open to raise exception only for checkMesh
            original_open = open
            call_count = [0]

            def mock_open_raising(*args, **kwargs):
                path_str = str(args[0])
                # snappyHexMeshDict doesn't exist, so we let file check happen normally
                # For checkMesh, raise exception
                if 'log.checkMesh' in path_str:
                    call_count[0] += 1
                    if call_count[0] > 1:  # Second call (after exists() check)
                        raise IOError("Mock read error")
                return original_open(*args, **kwargs)

            # Simpler approach - just verify no snappyHexMeshDict, checkMesh exists but has error in parsing
            # Create file with content that will cause float() to fail
            (logs_dir / "log.checkMesh").write_text("Overall domain bounding box (invalid) (values)")

            pref = writer._compute_pRefPoint_from_mesh()

            # Should return None due to parse failure
            assert pref is None


class TestPrintQualityReportNoMetrics:
    """Test _print_quality_report with missing metrics."""

    @patch('aortacfd_lib.solver_setup.Logger')
    @patch('aortacfd_lib.solver_setup.Environment')
    @patch('aortacfd_lib.solver_setup.FileSystemLoader')
    @patch('aortacfd_lib.solver_setup.OFVersionAdapter')
    def test_print_report_no_metrics(self, mock_adapter, mock_loader, mock_env, mock_logger):
        """Test printing quality report with no metrics."""
        from aortacfd_lib.solver_setup import FvSolutionWriter

        mock_log_instance = MagicMock()
        mock_logger.return_value.get_logger.return_value = mock_log_instance

        config = {'openfoam_version': '8', 'fvSolution': {}}

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = FvSolutionWriter(config, tmpdir)

            quality_report = {
                'tier': 'UNKNOWN',
                'metrics': {},
                'recommendations': []
            }

            writer._print_quality_report(quality_report)

            # Should still print without errors
            assert mock_log_instance.info.called

    @patch('aortacfd_lib.solver_setup.Logger')
    @patch('aortacfd_lib.solver_setup.Environment')
    @patch('aortacfd_lib.solver_setup.FileSystemLoader')
    @patch('aortacfd_lib.solver_setup.OFVersionAdapter')
    def test_print_report_partial_metrics(self, mock_adapter, mock_loader, mock_env, mock_logger):
        """Test printing quality report with only some metrics."""
        from aortacfd_lib.solver_setup import FvSolutionWriter

        mock_log_instance = MagicMock()
        mock_logger.return_value.get_logger.return_value = mock_log_instance

        config = {'openfoam_version': '8', 'fvSolution': {}}

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = FvSolutionWriter(config, tmpdir)

            # Only skewness, no orthogonality or aspect ratio
            quality_report = {
                'tier': 'FAIR',
                'metrics': {
                    'max_skewness': 2.0
                    # no max_non_orthogonality or max_aspect_ratio
                },
                'recommendations': ['Some recommendation']
            }

            writer._print_quality_report(quality_report)

            assert mock_log_instance.info.called


class TestWriteFvSolutionDisablesMeshAdaptive:
    """Test write_fvSolution_file when mesh_adaptive is disabled."""

    @patch('aortacfd_lib.solver_setup.Logger')
    @patch('aortacfd_lib.solver_setup.prepare_fv_solution_context')
    @patch('aortacfd_lib.solver_setup.OFVersionAdapter')
    def test_write_disables_mesh_adaptive_when_false(self, mock_adapter, mock_prepare, mock_logger):
        """Test mesh adaptive is skipped when config disables it."""
        from aortacfd_lib.solver_setup import FvSolutionWriter

        mock_prepare.return_value = {
            'profile': 'standard',
            'pimple': {},
            'relaxation': {},
            'tolerances': {}
        }

        mock_adapter_instance = MagicMock()
        mock_adapter_instance.get_foam_file_header.return_value = "// Header"
        mock_adapter.return_value = mock_adapter_instance

        config = {
            'openfoam_version': '8',
            'openfoam_major_version': 8,
            'fvSolution': {'PIMPLE': {'nOuterCorrectors': 3}},
            'numerics': {'mesh_adaptive': False}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            system_dir = Path(tmpdir) / "system"
            system_dir.mkdir()

            mock_template = MagicMock()
            mock_template.render.return_value = "// fvSolution"

            with patch.object(FvSolutionWriter, '__init__', lambda self, config, case_dir: None):
                writer = FvSolutionWriter.__new__(FvSolutionWriter)
                writer.config = config
                writer.case_dir = tmpdir
                writer.log = MagicMock()
                writer.jinja_env = MagicMock()
                writer.jinja_env.get_template.return_value = mock_template
                writer.version_adapter = mock_adapter_instance

                # Mock _apply_mesh_adaptive_solver to track if it's called
                writer._apply_mesh_adaptive_solver = MagicMock()

                writer.write_fvSolution_file()

                # _apply_mesh_adaptive_solver should NOT have been called
                writer._apply_mesh_adaptive_solver.assert_not_called()


class TestMeshAdaptiveLoggingPaths:
    """Test various logging paths in mesh adaptive."""

    @patch('aortacfd_lib.solver_setup.Logger')
    @patch('aortacfd_lib.solver_setup.Environment')
    @patch('aortacfd_lib.solver_setup.FileSystemLoader')
    @patch('aortacfd_lib.solver_setup.OFVersionAdapter')
    def test_logs_adjustments_when_different(self, mock_adapter, mock_loader, mock_env, mock_logger):
        """Test logging when mesh adaptive makes actual changes."""
        from aortacfd_lib.solver_setup import FvSolutionWriter

        mock_log_instance = MagicMock()
        mock_logger.return_value.get_logger.return_value = mock_log_instance

        config = {
            'openfoam_version': '8',
            'fvSolution': {},
            'numerics': {'mesh_adaptive': True, 'profile': 'standard'}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "logs"
            logs_dir.mkdir()
            (logs_dir / "log.checkMesh").write_text("test")

            writer = FvSolutionWriter(config, tmpdir)
            # Re-assign log to track calls
            writer.log = mock_log_instance

            base_fvsolution = {
                'PIMPLE': {'nOuterCorrectors': 3, 'nNonOrthogonalCorrectors': 1},
                'relaxationFactors': {'fields': {'p': 0.5}}
            }

            # Create mock with different adjusted values
            mock_mesh_adaptive = MagicMock()
            mock_mesh_adaptive.analyze_checkmesh_log = MagicMock()
            mock_mesh_adaptive.adjust_fvsolution_for_mesh.return_value = {
                'PIMPLE': {'nOuterCorrectors': 5, 'nNonOrthogonalCorrectors': 3},
                'relaxationFactors': {'fields': {'p': 0.3}}
            }
            mock_mesh_adaptive.get_quality_report.return_value = {
                'tier': 'POOR',
                'metrics': {},
                'recommendations': []
            }
            mock_mesh_adaptive.mesh_quality_tier = 'POOR'

            mock_module = MagicMock()
            mock_module.MeshAdaptiveSolverSettings = lambda: mock_mesh_adaptive

            with patch.dict('sys.modules', {'config.mesh_adaptive_solver': mock_module}):
                adjusted, report = writer._apply_mesh_adaptive_solver(base_fvsolution)

            # Verify info logging happened for adjustments
            assert mock_log_instance.info.called


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
