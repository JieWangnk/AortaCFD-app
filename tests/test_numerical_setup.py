"""
Test suite for numerical_setup.py module.

Tests cover:
- FvSchemesWriter initialization
- write_fvSchemes_file method
- _apply_mesh_adaptive_schemes method
"""

import pytest
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestFvSchemesWriterInit:
    """Test FvSchemesWriter initialization."""

    def test_init_creates_instance(self, tmp_path):
        """Test that initialization creates a valid instance."""
        from aortacfd_lib.numerical_setup import FvSchemesWriter

        config = {
            'openfoam_version': '12',
            'physics': {'model': 'laminar'}
        }

        with patch('aortacfd_lib.numerical_setup.Logger'):
            writer = FvSchemesWriter(config, str(tmp_path))

        assert writer.config == config
        assert writer.case_dir == str(tmp_path)
        assert writer.jinja_env is not None

    def test_init_creates_version_adapter(self, tmp_path):
        """Test that initialization creates OFVersionAdapter."""
        from aortacfd_lib.numerical_setup import FvSchemesWriter

        config = {
            'openfoam_version': '8',
            'physics': {'model': 'rans'}
        }

        with patch('aortacfd_lib.numerical_setup.Logger'):
            writer = FvSchemesWriter(config, str(tmp_path))

        assert writer.version_adapter is not None


class TestWriteFvSchemesFile:
    """Test FvSchemesWriter.write_fvSchemes_file method."""

    @pytest.fixture
    def writer(self, tmp_path):
        """Create a FvSchemesWriter instance for testing."""
        from aortacfd_lib.numerical_setup import FvSchemesWriter

        # Create system directory
        (tmp_path / "system").mkdir()

        config = {
            'openfoam_version': '12',
            'openfoam_major_version': 12,
            'physics': {
                'model': 'laminar',
                'simulation_type': 'transient'
            },
            'numerics': {
                'profile': 'standard',
                'mesh_adaptive': False
            },
            'schemes': {
                'ddtSchemes': {'default': 'backward'},
                'gradSchemes': {'default': 'Gauss linear'},
                'divSchemes': {},
                'laplacianSchemes': {'default': 'Gauss linear corrected'},
                'interpolationSchemes': {'default': 'linear'},
                'snGradSchemes': {'default': 'corrected'}
            }
        }

        with patch('aortacfd_lib.numerical_setup.Logger'):
            writer = FvSchemesWriter(config, str(tmp_path))

        return writer

    def test_write_creates_file(self, writer, tmp_path):
        """Test that write_fvSchemes_file creates the file."""
        with patch.object(writer, 'jinja_env') as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "// fvSchemes content"
            mock_env.get_template.return_value = mock_template

            with patch('aortacfd_lib.numerical_setup.prepare_fv_schemes_context') as mock_context:
                mock_context.return_value = {
                    'is_steady': False,
                    'simulation_type': 'transient',
                    'profile': 'standard',
                    'ddt_scheme': 'backward',
                    'div_scheme_U': 'Gauss linear',
                    'div_scheme_k': 'Gauss linear',
                    'grad_limiter': 1.0
                }

                writer.write_fvSchemes_file()

        output_file = tmp_path / "system" / "fvSchemes"
        assert output_file.exists()

    def test_write_disables_mesh_adaptive_when_false(self, tmp_path):
        """Test that mesh_adaptive=False skips adaptive adjustments."""
        from aortacfd_lib.numerical_setup import FvSchemesWriter

        (tmp_path / "system").mkdir()

        config = {
            'openfoam_version': '12',
            'openfoam_major_version': 12,
            'physics': {'model': 'laminar', 'simulation_type': 'transient'},
            'numerics': {'profile': 'standard', 'mesh_adaptive': False},
            'schemes': {'ddtSchemes': {'default': 'Euler'}}
        }

        with patch('aortacfd_lib.numerical_setup.Logger'):
            writer = FvSchemesWriter(config, str(tmp_path))

        with patch.object(writer, '_apply_mesh_adaptive_schemes') as mock_adaptive:
            with patch.object(writer, 'jinja_env') as mock_env:
                mock_template = MagicMock()
                mock_template.render.return_value = "// content"
                mock_env.get_template.return_value = mock_template

                with patch('aortacfd_lib.numerical_setup.prepare_fv_schemes_context') as mock_context:
                    mock_context.return_value = {
                        'is_steady': False, 'simulation_type': 'transient',
                        'profile': 'standard', 'ddt_scheme': 'Euler',
                        'div_scheme_U': '', 'div_scheme_k': '', 'grad_limiter': 1.0
                    }

                    writer.write_fvSchemes_file()

        # Should not call mesh adaptive when disabled
        mock_adaptive.assert_not_called()


class TestApplyMeshAdaptiveSchemes:
    """Test FvSchemesWriter._apply_mesh_adaptive_schemes method."""

    @pytest.fixture
    def writer(self, tmp_path):
        """Create a FvSchemesWriter instance for testing."""
        from aortacfd_lib.numerical_setup import FvSchemesWriter

        config = {
            'openfoam_version': '12',
            'physics': {'model': 'laminar'},
            'numerics': {'profile': 'standard'}
        }

        with patch('aortacfd_lib.numerical_setup.Logger'):
            writer = FvSchemesWriter(config, str(tmp_path))

        return writer

    def test_returns_base_schemes_when_no_log(self, writer, tmp_path):
        """Test that base schemes are returned when checkMesh log doesn't exist."""
        base_schemes = {'ddtSchemes': {'default': 'Euler'}}

        result = writer._apply_mesh_adaptive_schemes(base_schemes)

        assert result == base_schemes

    def test_applies_mesh_adaptive_with_log(self, writer, tmp_path):
        """Test that schemes are adjusted when checkMesh log exists."""
        # Create logs directory and checkMesh log
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        checkmesh_log = logs_dir / "log.checkMesh"
        checkmesh_log.write_text("""
    Max skewness = 3.5 OK.
    Mesh non-orthogonality Max: 65.0 average: 10
    Max aspect ratio = 25.0 OK.
    Mesh OK.
        """)

        base_schemes = {
            'laplacianSchemes': {'default': 'Gauss linear corrected'}
        }

        # Patch at the config module level since it's imported inside the method
        with patch('config.mesh_adaptive_solver.MeshAdaptiveSolverSettings') as mock_adapter:
            mock_instance = MagicMock()
            mock_instance.mesh_quality_tier = 'FAIR'
            mock_instance.adjust_fvschemes_for_mesh.return_value = {
                'laplacianSchemes': {'default': 'Gauss linear limited corrected 0.5'}
            }
            mock_adapter.return_value = mock_instance

            result = writer._apply_mesh_adaptive_schemes(base_schemes)

            mock_instance.analyze_checkmesh_log.assert_called_once()
            mock_instance.adjust_fvschemes_for_mesh.assert_called_once()

    def test_returns_base_schemes_on_import_error(self, writer, tmp_path):
        """Test that base schemes are returned when import fails."""
        base_schemes = {'ddtSchemes': {'default': 'Euler'}}

        # The method catches ImportError when config.mesh_adaptive_solver import fails
        # Since no log exists, it returns base_schemes before import
        result = writer._apply_mesh_adaptive_schemes(base_schemes)

        assert result == base_schemes

    def test_returns_base_schemes_on_exception(self, writer, tmp_path):
        """Test that base schemes are returned on any exception."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "log.checkMesh").write_text("corrupted content")

        base_schemes = {'ddtSchemes': {'default': 'Euler'}}

        with patch('config.mesh_adaptive_solver.MeshAdaptiveSolverSettings') as mock_adapter:
            mock_adapter.return_value.analyze_checkmesh_log.side_effect = ValueError("Parse error")

            result = writer._apply_mesh_adaptive_schemes(base_schemes)

        assert result == base_schemes


class TestFvSchemesWriterIntegration:
    """Integration tests for FvSchemesWriter."""

    def test_full_write_workflow(self, tmp_path):
        """Test the complete workflow of writing fvSchemes."""
        from aortacfd_lib.numerical_setup import FvSchemesWriter

        # Create necessary directories
        (tmp_path / "system").mkdir()

        config = {
            'openfoam_version': '12',
            'openfoam_major_version': 12,
            'physics': {
                'model': 'laminar',
                'simulation_type': 'transient'
            },
            'numerics': {
                'profile': 'standard',
                'mesh_adaptive': False
            },
            'schemes': {
                'ddtSchemes': {'default': 'backward'},
                'gradSchemes': {'default': 'Gauss linear'},
                'divSchemes': {'default': 'none'},
                'laplacianSchemes': {'default': 'Gauss linear corrected'},
                'interpolationSchemes': {'default': 'linear'},
                'snGradSchemes': {'default': 'corrected'}
            }
        }

        with patch('aortacfd_lib.numerical_setup.Logger'):
            writer = FvSchemesWriter(config, str(tmp_path))

        # Mock the template rendering
        with patch.object(writer.jinja_env, 'get_template') as mock_get_template:
            mock_template = MagicMock()
            mock_template.render.return_value = """FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      fvSchemes;
}

ddtSchemes
{
    default backward;
}
"""
            mock_get_template.return_value = mock_template

            with patch('aortacfd_lib.numerical_setup.prepare_fv_schemes_context') as mock_context:
                mock_context.return_value = {
                    'is_steady': False,
                    'simulation_type': 'transient',
                    'profile': 'standard',
                    'ddt_scheme': 'backward',
                    'div_scheme_U': 'Gauss linear',
                    'div_scheme_k': 'Gauss linear',
                    'grad_limiter': 1.0
                }

                writer.write_fvSchemes_file()

        # Verify file was created with content
        output_file = tmp_path / "system" / "fvSchemes"
        assert output_file.exists()
        content = output_file.read_text()
        assert "FoamFile" in content
        assert "fvSchemes" in content


class TestWriteFvSchemesWithMeshAdaptive:
    """Test write_fvSchemes_file with mesh_adaptive enabled."""

    def test_write_with_mesh_adaptive_enabled(self, tmp_path):
        """Test fvSchemes writing with mesh adaptive enabled."""
        from aortacfd_lib.numerical_setup import FvSchemesWriter

        (tmp_path / "system").mkdir()
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "log.checkMesh").write_text("Max skewness = 2.5\n")

        config = {
            'openfoam_version': '12',
            'openfoam_major_version': 12,
            'physics': {'model': 'laminar', 'simulation_type': 'transient'},
            'numerics': {'profile': 'standard', 'mesh_adaptive': True},
            'schemes': {
                'ddtSchemes': {'default': 'backward'},
                'laplacianSchemes': {'default': 'Gauss linear corrected'}
            }
        }

        with patch('aortacfd_lib.numerical_setup.Logger'):
            writer = FvSchemesWriter(config, str(tmp_path))

        # Mock the adaptive mesh method to verify it's called
        with patch.object(writer, '_apply_mesh_adaptive_schemes') as mock_adaptive:
            mock_adaptive.return_value = config['schemes']

            with patch.object(writer, 'jinja_env') as mock_env:
                mock_template = MagicMock()
                mock_template.render.return_value = "// content"
                mock_env.get_template.return_value = mock_template

                with patch('aortacfd_lib.numerical_setup.prepare_fv_schemes_context') as mock_context:
                    mock_context.return_value = {
                        'is_steady': False, 'simulation_type': 'transient',
                        'profile': 'standard', 'ddt_scheme': 'backward',
                        'div_scheme_U': '', 'div_scheme_k': '', 'grad_limiter': 1.0
                    }

                    writer.write_fvSchemes_file()

        # mesh_adaptive=True AND 'schemes' in config, so should call
        mock_adaptive.assert_called_once()


class TestApplyMeshAdaptiveSchemesSuccess:
    """Test _apply_mesh_adaptive_schemes when it successfully adjusts schemes."""

    def test_applies_and_logs_adjustments(self, tmp_path):
        """Test that scheme adjustments are logged when different."""
        from aortacfd_lib.numerical_setup import FvSchemesWriter

        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "log.checkMesh").write_text("Max skewness = 4.5\n")

        config = {
            'openfoam_version': '12',
            'physics': {'model': 'laminar'},
            'numerics': {'profile': 'standard', 'mesh_adaptive': True}
        }

        mock_log_instance = MagicMock()

        with patch('aortacfd_lib.numerical_setup.Logger') as mock_logger:
            mock_logger.return_value.get_logger.return_value = mock_log_instance
            writer = FvSchemesWriter(config, str(tmp_path))
            writer.log = mock_log_instance

        base_schemes = {
            'laplacianSchemes': {'default': 'Gauss linear corrected'}
        }

        adjusted_schemes = {
            'laplacianSchemes': {'default': 'Gauss linear limited corrected 0.5'}
        }

        # Mock successful import and adjustment
        mock_mesh_adaptive = MagicMock()
        mock_mesh_adaptive.analyze_checkmesh_log = MagicMock()
        mock_mesh_adaptive.adjust_fvschemes_for_mesh.return_value = adjusted_schemes
        mock_mesh_adaptive.mesh_quality_tier = 'POOR'

        mock_module = MagicMock()
        mock_module.MeshAdaptiveSolverSettings = lambda: mock_mesh_adaptive

        with patch.dict('sys.modules', {'config.mesh_adaptive_solver': mock_module}):
            result = writer._apply_mesh_adaptive_schemes(base_schemes)

        # Should return adjusted schemes
        assert result == adjusted_schemes
        # Should log the tier
        assert mock_log_instance.info.called

    def test_returns_unchanged_when_no_adjustments_needed(self, tmp_path):
        """Test that unchanged schemes don't log adjustment messages."""
        from aortacfd_lib.numerical_setup import FvSchemesWriter

        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "log.checkMesh").write_text("Max skewness = 1.0\n")

        config = {
            'openfoam_version': '12',
            'physics': {'model': 'laminar'},
            'numerics': {'profile': 'standard', 'mesh_adaptive': True}
        }

        with patch('aortacfd_lib.numerical_setup.Logger'):
            writer = FvSchemesWriter(config, str(tmp_path))

        base_schemes = {
            'laplacianSchemes': {'default': 'Gauss linear corrected'}
        }

        # Mock to return same schemes (no adjustment needed)
        mock_mesh_adaptive = MagicMock()
        mock_mesh_adaptive.analyze_checkmesh_log = MagicMock()
        mock_mesh_adaptive.adjust_fvschemes_for_mesh.return_value = base_schemes
        mock_mesh_adaptive.mesh_quality_tier = 'GOOD'

        mock_module = MagicMock()
        mock_module.MeshAdaptiveSolverSettings = lambda: mock_mesh_adaptive

        with patch.dict('sys.modules', {'config.mesh_adaptive_solver': mock_module}):
            result = writer._apply_mesh_adaptive_schemes(base_schemes)

        # Should return same schemes
        assert result == base_schemes

    def test_logs_laplacian_scheme_changes(self, tmp_path):
        """Test that laplacian scheme changes are specifically logged."""
        from aortacfd_lib.numerical_setup import FvSchemesWriter

        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "log.checkMesh").write_text("Max skewness = 5.0\n")

        config = {
            'openfoam_version': '12',
            'physics': {'model': 'laminar'},
            'numerics': {'profile': 'standard', 'mesh_adaptive': True}
        }

        mock_log_instance = MagicMock()

        with patch('aortacfd_lib.numerical_setup.Logger') as mock_logger:
            mock_logger.return_value.get_logger.return_value = mock_log_instance
            writer = FvSchemesWriter(config, str(tmp_path))
            writer.log = mock_log_instance

        base_schemes = {
            'laplacianSchemes': {'default': 'Gauss linear corrected'}
        }

        adjusted_schemes = {
            'laplacianSchemes': {'default': 'Gauss linear limited corrected 0.33'}
        }

        mock_mesh_adaptive = MagicMock()
        mock_mesh_adaptive.analyze_checkmesh_log = MagicMock()
        mock_mesh_adaptive.adjust_fvschemes_for_mesh.return_value = adjusted_schemes
        mock_mesh_adaptive.mesh_quality_tier = 'CRITICAL'

        mock_module = MagicMock()
        mock_module.MeshAdaptiveSolverSettings = lambda: mock_mesh_adaptive

        with patch.dict('sys.modules', {'config.mesh_adaptive_solver': mock_module}):
            result = writer._apply_mesh_adaptive_schemes(base_schemes)

        # Should log laplacian change
        info_calls = [str(call) for call in mock_log_instance.info.call_args_list]
        assert any('Laplacian' in str(call) for call in info_calls)


class TestApplyMeshAdaptiveImportError:
    """Test _apply_mesh_adaptive_schemes when import fails."""

    def test_general_exception_with_checkmesh_log(self, tmp_path):
        """Test handles general exception when checkMesh log exists."""
        from aortacfd_lib.numerical_setup import FvSchemesWriter

        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "log.checkMesh").write_text("Max skewness = 2.0\n")

        config = {
            'openfoam_version': '12',
            'physics': {'model': 'laminar'},
            'numerics': {'profile': 'standard'}
        }

        mock_log_instance = MagicMock()

        with patch('aortacfd_lib.numerical_setup.Logger') as mock_logger:
            mock_logger.return_value.get_logger.return_value = mock_log_instance
            writer = FvSchemesWriter(config, str(tmp_path))
            writer.log = mock_log_instance

        base_schemes = {'ddtSchemes': {'default': 'Euler'}}

        # Create a mock module that raises RuntimeError when used
        mock_mesh_adaptive = MagicMock()
        mock_mesh_adaptive.analyze_checkmesh_log.side_effect = RuntimeError("Unexpected error")

        mock_module = MagicMock()
        mock_module.MeshAdaptiveSolverSettings.return_value = mock_mesh_adaptive

        # Use patch.dict to temporarily modify sys.modules
        with patch.dict('sys.modules', {'config.mesh_adaptive_solver': mock_module}):
            result = writer._apply_mesh_adaptive_schemes(base_schemes)

        # Should return base schemes on error
        assert result == base_schemes
        # Should log warning
        assert mock_log_instance.warning.called


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
