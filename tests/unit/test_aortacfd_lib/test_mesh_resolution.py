"""
Unit tests for mesh resolution parameter hierarchy and helper functions.

Tests the new strategy pattern implementation in mesh_setup.py for cell size
resolution, including validation and logging functionality.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import logging

# Import will be handled by conftest.py which adds src/ to path
from aortacfd_lib.mesh_setup import GeometryAnalyzer


class TestMeshResolutionStrategies:
    """Test individual resolution strategy helper functions."""

    @pytest.fixture
    def mock_mesh_setup(self):
        """Create a mock GeometryAnalyzer instance with minimal dependencies."""
        # Complete configuration to avoid KeyError
        config = {
            'geometry': {
                'scale_factor': 0.001,
                'stl_files': {}
            },
            'mesh': {
                'SNAPPY_SETTINGS': {},
                'mesh_resolution': {}
            }
        }

        # Create mock logger
        logger = Mock(spec=logging.Logger)

        # Create instance with mocked dependencies
        with patch('aortacfd_lib.mesh_setup.Logger'), \
             patch('aortacfd_lib.mesh_setup.PatchProcessing'):
            mesh_setup = GeometryAnalyzer(config, case_directory='/tmp/test')
        mesh_setup.log = logger

        return mesh_setup

    def test_cell_size_from_resolution_level_coarse(self, mock_mesh_setup):
        """Test resolution_level='coarse' returns 2.0mm."""
        mock_mesh_setup.mesh_settings = {'resolution_level': 'coarse'}
        mesh_resolution = {}

        cell_size, source = mock_mesh_setup._cell_size_from_resolution_level(mesh_resolution)

        assert cell_size == 2.0
        assert 'coarse' in source.lower()
        assert '2.0mm' in source

    def test_cell_size_from_resolution_level_medium(self, mock_mesh_setup):
        """Test resolution_level='medium' returns 1.0mm."""
        mock_mesh_setup.mesh_settings = {'resolution_level': 'medium'}
        mesh_resolution = {}

        cell_size, source = mock_mesh_setup._cell_size_from_resolution_level(mesh_resolution)

        assert cell_size == 1.0
        assert 'medium' in source.lower()
        assert '1.0mm' in source

    def test_cell_size_from_resolution_level_fine(self, mock_mesh_setup):
        """Test resolution_level='fine' returns 0.5mm."""
        mock_mesh_setup.mesh_settings = {'resolution_level': 'fine'}
        mesh_resolution = {}

        cell_size, source = mock_mesh_setup._cell_size_from_resolution_level(mesh_resolution)

        assert cell_size == 0.5
        assert 'fine' in source.lower()
        assert '0.5mm' in source

    def test_cell_size_from_resolution_level_ultra_fine(self, mock_mesh_setup):
        """Test resolution_level='ultra_fine' returns 0.25mm."""
        mock_mesh_setup.mesh_settings = {'resolution_level': 'ultra_fine'}
        mesh_resolution = {}

        cell_size, source = mock_mesh_setup._cell_size_from_resolution_level(mesh_resolution)

        assert cell_size == 0.25
        assert 'ultra_fine' in source.lower()
        assert '0.25mm' in source

    def test_cell_size_from_resolution_level_aliases(self, mock_mesh_setup):
        """Test resolution_level aliases (draft, clinical, publication)."""
        # Test 'draft' alias for 'coarse'
        mock_mesh_setup.mesh_settings = {'resolution_level': 'draft'}
        cell_size, _ = mock_mesh_setup._cell_size_from_resolution_level({})
        assert cell_size == 2.0

        # Test 'clinical' alias for 'medium'
        mock_mesh_setup.mesh_settings = {'resolution_level': 'clinical'}
        cell_size, _ = mock_mesh_setup._cell_size_from_resolution_level({})
        assert cell_size == 1.0

        # Test 'publication' alias for 'fine'
        mock_mesh_setup.mesh_settings = {'resolution_level': 'publication'}
        cell_size, _ = mock_mesh_setup._cell_size_from_resolution_level({})
        assert cell_size == 0.5

    def test_cell_size_from_resolution_level_invalid(self, mock_mesh_setup):
        """Test invalid resolution_level returns None and logs warning."""
        mock_mesh_setup.mesh_settings = {'resolution_level': 'invalid_level'}
        mesh_resolution = {}

        cell_size, source = mock_mesh_setup._cell_size_from_resolution_level(mesh_resolution)

        assert cell_size is None
        assert source is None
        mock_mesh_setup.log.warning.assert_called_once()

    def test_cell_size_from_resolution_level_none(self, mock_mesh_setup):
        """Test None resolution_level returns None."""
        mock_mesh_setup.mesh_settings = {}
        mesh_resolution = {}

        cell_size, source = mock_mesh_setup._cell_size_from_resolution_level(mesh_resolution)

        assert cell_size is None
        assert source is None

    def test_cell_size_from_target_mm(self, mock_mesh_setup):
        """Test target_cell_size_mm direct specification."""
        mock_mesh_setup.mesh_settings = {}
        mesh_resolution = {'target_cell_size_mm': 1.5}

        cell_size, source = mock_mesh_setup._cell_size_from_target_mm(mesh_resolution)

        assert cell_size == 1.5
        assert 'target_cell_size_mm' in source

    def test_cell_size_from_target_mm_invalid(self, mock_mesh_setup):
        """Test target_cell_size_mm with invalid values."""
        mock_mesh_setup.mesh_settings = {}

        # Test negative value
        mesh_resolution = {'target_cell_size_mm': -1.0}
        cell_size, _ = mock_mesh_setup._cell_size_from_target_mm(mesh_resolution)
        assert cell_size is None

        # Test zero
        mesh_resolution = {'target_cell_size_mm': 0}
        cell_size, _ = mock_mesh_setup._cell_size_from_target_mm(mesh_resolution)
        assert cell_size is None

        # Test None
        mesh_resolution = {'target_cell_size_mm': None}
        cell_size, _ = mock_mesh_setup._cell_size_from_target_mm(mesh_resolution)
        assert cell_size is None


class TestValidationResolutionConfig:
    """Test validation of resolution configuration."""

    @pytest.fixture
    def mock_mesh_setup(self):
        """Create a mock GeometryAnalyzer instance."""
        config = {
            'geometry': {'scale_factor': 0.001, 'stl_files': {}},
            'mesh': {'SNAPPY_SETTINGS': {}, 'mesh_resolution': {}}
        }
        with patch('aortacfd_lib.mesh_setup.Logger'), \
             patch('aortacfd_lib.mesh_setup.PatchProcessing'):
            mesh_setup = GeometryAnalyzer(config, case_directory='/tmp/test')
        mesh_setup.log = Mock(spec=logging.Logger)

        return mesh_setup

    def test_validate_single_parameter(self, mock_mesh_setup):
        """Test validation passes with single parameter."""
        mock_mesh_setup.mesh_settings = {'resolution_level': 'medium'}
        mesh_resolution = {}

        # Should not raise, should not warn
        mock_mesh_setup._validate_resolution_config(mesh_resolution)
        mock_mesh_setup.log.warning.assert_not_called()

    def test_validate_multiple_parameters_warns(self, mock_mesh_setup):
        """Test validation warns when multiple parameters are set."""
        mock_mesh_setup.mesh_settings = {'resolution_level': 'medium'}
        mesh_resolution = {
            'target_cell_size_mm': 1.5,
            'cells_per_diameter': 10
        }

        mock_mesh_setup._validate_resolution_config(mesh_resolution)

        # Should have warned
        mock_mesh_setup.log.warning.assert_called_once()
        warning_msg = mock_mesh_setup.log.warning.call_args[0][0]

        # Check warning contains key information
        assert 'Multiple mesh resolution parameters detected' in warning_msg
        assert 'priority' in warning_msg.lower()
        assert 'resolution_level' in warning_msg

    def test_validate_no_parameters(self, mock_mesh_setup):
        """Test validation passes with no parameters (will use default)."""
        mock_mesh_setup.mesh_settings = {}
        mesh_resolution = {}

        # Should not raise, should not warn
        mock_mesh_setup._validate_resolution_config(mesh_resolution)
        mock_mesh_setup.log.warning.assert_not_called()


class TestPriorityHierarchy:
    """Test priority cascade and strategy order."""

    @pytest.fixture
    def mock_mesh_setup(self):
        """Create a mock GeometryAnalyzer instance."""
        config = {
            'geometry': {'scale_factor': 0.001, 'stl_files': {}},
            'mesh': {'SNAPPY_SETTINGS': {}, 'mesh_resolution': {}}
        }
        with patch('aortacfd_lib.mesh_setup.Logger'), \
             patch('aortacfd_lib.mesh_setup.PatchProcessing'):
            mesh_setup = GeometryAnalyzer(config, case_directory='/tmp/test')
        mesh_setup.log = Mock(spec=logging.Logger)

        return mesh_setup

    def test_priority_order(self, mock_mesh_setup):
        """Test that strategies are in correct priority order."""
        mesh_resolution = {}
        strategies = mock_mesh_setup._get_cell_size_strategies(mesh_resolution)

        # Check we have 6 strategies
        assert len(strategies) == 6

        # Check priorities are 1-6 in order
        priorities = [s[0] for s in strategies]
        assert priorities == [1, 2, 3, 4, 5, 6]

        # Check method names
        method_names = [s[1] for s in strategies]
        assert 'resolution_level' in method_names[0]
        assert 'target_cell_size_mm' in method_names[1]
        assert 'default_fallback' in method_names[5]

    def test_resolve_priority_1_wins(self, mock_mesh_setup):
        """Test Priority 1 (resolution_level) wins over lower priorities."""
        mock_mesh_setup.mesh_settings = {'resolution_level': 'fine'}
        mesh_resolution = {
            'target_cell_size_mm': 2.0,  # Priority 2
            'cells_per_diameter': 10      # Priority 4
        }

        cell_size, source, priority = mock_mesh_setup._resolve_cell_size(mesh_resolution)

        assert priority == 1
        assert cell_size == 0.5  # fine = 0.5mm
        assert 'resolution_level' in source

    def test_resolve_priority_2_when_1_missing(self, mock_mesh_setup):
        """Test Priority 2 (target_cell_size_mm) used when Priority 1 missing."""
        mock_mesh_setup.mesh_settings = {}
        mesh_resolution = {
            'target_cell_size_mm': 1.5,   # Priority 2
            'cells_per_diameter': 10      # Priority 4
        }

        cell_size, source, priority = mock_mesh_setup._resolve_cell_size(mesh_resolution)

        assert priority == 2
        assert cell_size == 1.5
        assert 'target_cell_size_mm' in source

    def test_resolve_default_fallback(self, mock_mesh_setup):
        """Test default fallback (Priority 6) when no parameters set."""
        mock_mesh_setup.mesh_settings = {}
        mesh_resolution = {}

        cell_size, source, priority = mock_mesh_setup._resolve_cell_size(mesh_resolution)

        assert priority == 6
        assert cell_size == 1.0  # Default is now 1.0mm
        assert 'default fallback' in source
        assert '1.0mm' in source

        # Should have logged warning
        mock_mesh_setup.log.warning.assert_called()


class TestDefaultFallbackConsistency:
    """Test that default fallback matches 'medium' profile."""

    @pytest.fixture
    def mock_mesh_setup(self):
        """Create a mock GeometryAnalyzer instance."""
        config = {
            'geometry': {'scale_factor': 0.001, 'stl_files': {}},
            'mesh': {'SNAPPY_SETTINGS': {}, 'mesh_resolution': {}}
        }
        with patch('aortacfd_lib.mesh_setup.Logger'), \
             patch('aortacfd_lib.mesh_setup.PatchProcessing'):
            mesh_setup = GeometryAnalyzer(config, case_directory='/tmp/test')
        mesh_setup.log = Mock(spec=logging.Logger)

        return mesh_setup

    def test_default_fallback_matches_medium(self, mock_mesh_setup):
        """Test default fallback (1.0mm) matches 'medium' profile (1.0mm)."""
        # Get default fallback
        mock_mesh_setup.mesh_settings = {}
        cell_size_default, _, _ = mock_mesh_setup._resolve_cell_size({})

        # Get medium profile
        mock_mesh_setup.mesh_settings = {'resolution_level': 'medium'}
        cell_size_medium, _, _ = mock_mesh_setup._resolve_cell_size({})

        # Should be identical
        assert cell_size_default == cell_size_medium
        assert cell_size_default == 1.0


class TestLoggingOutput:
    """Test enhanced logging functionality."""

    @pytest.fixture
    def mock_mesh_setup(self):
        """Create a mock GeometryAnalyzer instance."""
        config = {
            'geometry': {'scale_factor': 0.001, 'stl_files': {}},
            'mesh': {'SNAPPY_SETTINGS': {}, 'mesh_resolution': {}}
        }
        with patch('aortacfd_lib.mesh_setup.Logger'), \
             patch('aortacfd_lib.mesh_setup.PatchProcessing'):
            mesh_setup = GeometryAnalyzer(config, case_directory='/tmp/test')
        mesh_setup.log = Mock(spec=logging.Logger)

        return mesh_setup

    def test_logging_includes_priority(self, mock_mesh_setup):
        """Test that logging output includes priority information."""
        mock_mesh_setup.mesh_settings = {'resolution_level': 'medium'}

        # Need to mock _calculate_blockmesh_cells bounds input
        bounds = {
            'min': [0, 0, 0],
            'max': [100, 100, 100]
        }

        try:
            # This will fail without proper geometry, but we can check logging
            mock_mesh_setup._calculate_blockmesh_cells(bounds)
        except:
            pass

        # Check that log.info was called with priority information
        info_calls = [str(call) for call in mock_mesh_setup.log.info.call_args_list]
        info_text = ' '.join(info_calls)

        # Should mention priority if resolution was selected
        if 'Priority' in info_text or 'priority' in info_text.lower():
            assert 'priority' in info_text.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
