"""
Test suite for utils/patch_utils.py module.

Tests cover:
- detect_world_patch_mode function
- get_murray_law_cache_key function
"""

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestDetectWorldPatchMode:
    """Test detect_world_patch_mode function."""

    @pytest.fixture
    def mock_log(self):
        """Create a mock logger."""
        return MagicMock()

    def test_returns_false_when_boundary_file_missing(self, tmp_path, mock_log):
        """Test that False is returned when boundary file doesn't exist."""
        from aortacfd_lib.utils.patch_utils import detect_world_patch_mode

        result = detect_world_patch_mode(str(tmp_path), mock_log)

        assert result is False
        mock_log.warning.assert_called()

    def test_detects_world_patch(self, tmp_path, mock_log):
        """Test detection of world patch in boundary file."""
        from aortacfd_lib.utils.patch_utils import detect_world_patch_mode

        # Create boundary file with world patch
        poly_mesh = tmp_path / "constant" / "polyMesh"
        poly_mesh.mkdir(parents=True)

        boundary_content = """
FoamFile
{
    version     2.0;
    format      ascii;
    class       polyBoundaryMesh;
    object      boundary;
}
1
(
    world
    {
        type            patch;
        nFaces          1000;
        startFace       50000;
    }
)
"""
        (poly_mesh / "boundary").write_text(boundary_content)

        result = detect_world_patch_mode(str(tmp_path), mock_log)

        assert result is True
        mock_log.info.assert_called()

    def test_single_real_patch_is_world_mode(self, tmp_path, mock_log):
        """A boundary with a single real patch (FoamFile/defaultFaces excluded)
        is world-patch mode — the short-circuit branch for pre-snappy blockMesh
        output."""
        from aortacfd_lib.utils.patch_utils import detect_world_patch_mode

        poly_mesh = tmp_path / "constant" / "polyMesh"
        poly_mesh.mkdir(parents=True)

        boundary_content = """FoamFile
{
    version     2.0;
    format      ascii;
    class       polyBoundaryMesh;
    object      boundary;
}
1
(
    walls
    {
        type            wall;
        nFaces          5000;
        startFace       10000;
    }
)
"""
        (poly_mesh / "boundary").write_text(boundary_content)

        result = detect_world_patch_mode(str(tmp_path), mock_log)

        assert result is True

    def test_returns_false_for_multiple_patches(self, tmp_path, mock_log):
        """Test that False is returned for multiple patches."""
        from aortacfd_lib.utils.patch_utils import detect_world_patch_mode

        poly_mesh = tmp_path / "constant" / "polyMesh"
        poly_mesh.mkdir(parents=True)

        # Multiple patches - not world patch mode
        boundary_content = """
FoamFile
{
    version     2.0;
    format      ascii;
    class       polyBoundaryMesh;
    object      boundary;
}
3
(
    inlet
    {
        type            patch;
        nFaces          100;
        startFace       50000;
    }
    outlet
    {
        type            patch;
        nFaces          100;
        startFace       50100;
    }
    walls
    {
        type            wall;
        nFaces          5000;
        startFace       50200;
    }
)
"""
        (poly_mesh / "boundary").write_text(boundary_content)

        result = detect_world_patch_mode(str(tmp_path), mock_log)

        assert result is False

    def test_ignores_default_faces_patch(self, tmp_path, mock_log):
        """defaultFaces and FoamFile are excluded from the patch count, so a
        single real patch alongside them is still world-patch mode."""
        from aortacfd_lib.utils.patch_utils import detect_world_patch_mode

        poly_mesh = tmp_path / "constant" / "polyMesh"
        poly_mesh.mkdir(parents=True)

        boundary_content = """FoamFile
{
    version     2.0;
    format      ascii;
    class       polyBoundaryMesh;
    object      boundary;
}
2
(
    walls
    {
        type            wall;
        nFaces          5000;
        startFace       10000;
    }
    defaultFaces
    {
        type            empty;
        nFaces          0;
        startFace       15000;
    }
)
"""
        (poly_mesh / "boundary").write_text(boundary_content)

        result = detect_world_patch_mode(str(tmp_path), mock_log)

        assert result is True

    def test_handles_file_read_error(self, tmp_path, mock_log):
        """Test graceful handling of file read errors."""
        from aortacfd_lib.utils.patch_utils import detect_world_patch_mode

        poly_mesh = tmp_path / "constant" / "polyMesh"
        poly_mesh.mkdir(parents=True)

        # Create a directory instead of a file to cause read error
        boundary_path = poly_mesh / "boundary"
        boundary_path.mkdir()

        result = detect_world_patch_mode(str(tmp_path), mock_log)

        assert result is False
        mock_log.warning.assert_called()


class TestGetMurrayLawCacheKey:
    """Test get_murray_law_cache_key function."""

    def test_returns_consistent_key(self):
        """Test that function returns a consistent cache key."""
        from aortacfd_lib.utils.patch_utils import get_murray_law_cache_key

        key1 = get_murray_law_cache_key()
        key2 = get_murray_law_cache_key()

        assert key1 == key2
        assert key1 == "murray_law_results"

    def test_returns_string(self):
        """Test that function returns a string."""
        from aortacfd_lib.utils.patch_utils import get_murray_law_cache_key

        key = get_murray_law_cache_key()

        assert isinstance(key, str)
        assert len(key) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
