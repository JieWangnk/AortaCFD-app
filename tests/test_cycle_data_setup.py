"""
Test suite for cycle_data_setup.py module.

Tests cover:
- CycleDataSetup initialization
- execute() method for creating symbolic links
- Error handling for missing directories
"""

import pytest
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestCycleDataSetupInit:
    """Test CycleDataSetup initialization."""

    def test_init_with_valid_config(self, tmp_path):
        """Test initialization with valid config."""
        from aortacfd_lib.cycle_data_setup import CycleDataSetup

        config = {"geometry": {"inlet_keywords_ordered": "inlet"}, "simulation_control": {"number_of_cycles": 3}}

        with patch("aortacfd_lib.cycle_data_setup.Logger"):
            setup = CycleDataSetup(config, str(tmp_path), cardiac_cycle=0.8)

        assert setup.cardiac_period == 0.8
        assert setup.number_of_cycles == 3
        assert "inlet" in setup.data_directory

    def test_init_with_nested_inlet_config(self, tmp_path):
        """Test initialization with nested boundary_conditions.inlet config."""
        from aortacfd_lib.cycle_data_setup import CycleDataSetup

        config = {
            "geometry": {"inlet_keywords_ordered": "inlet_patch"},
            "boundary_conditions": {"inlet": {"type": "TIMEVARYING"}},
            "simulation_control": {"number_of_cycles": 2},
        }

        with patch("aortacfd_lib.cycle_data_setup.Logger"):
            setup = CycleDataSetup(config, str(tmp_path), cardiac_cycle=1.0)

        assert setup.cardiac_period == 1.0
        assert setup.number_of_cycles == 2

    def test_init_default_number_of_cycles(self, tmp_path):
        """Test initialization uses default number_of_cycles=1."""
        from aortacfd_lib.cycle_data_setup import CycleDataSetup

        config = {
            "geometry": {"inlet_keywords_ordered": "inlet"},
            # No simulation_control
        }

        with patch("aortacfd_lib.cycle_data_setup.Logger"):
            setup = CycleDataSetup(config, str(tmp_path), cardiac_cycle=0.9)

        assert setup.number_of_cycles == 1


class TestCycleDataSetupExecute:
    """Test CycleDataSetup.execute method."""

    @pytest.fixture
    def setup_with_data(self, tmp_path):
        """Create CycleDataSetup with mock boundary data directory."""
        from aortacfd_lib.cycle_data_setup import CycleDataSetup

        config = {"geometry": {"inlet_keywords_ordered": "inlet"}, "simulation_control": {"number_of_cycles": 3}}

        # Create the boundary data directory structure
        boundary_data_dir = tmp_path / "constant" / "boundaryData" / "inlet"
        boundary_data_dir.mkdir(parents=True)

        # Create first cycle time directories
        (boundary_data_dir / "0.000000").mkdir()
        (boundary_data_dir / "0.000000" / "U").write_text("velocity data")
        (boundary_data_dir / "0.100000").mkdir()
        (boundary_data_dir / "0.100000" / "U").write_text("velocity data")
        (boundary_data_dir / "0.200000").mkdir()
        (boundary_data_dir / "0.200000" / "U").write_text("velocity data")

        with patch("aortacfd_lib.cycle_data_setup.Logger"):
            setup = CycleDataSetup(config, str(tmp_path), cardiac_cycle=0.5)

        return setup, boundary_data_dir

    def test_execute_creates_symlinks(self, setup_with_data):
        """Test that execute creates symbolic links for additional cycles."""
        setup, boundary_data_dir = setup_with_data

        setup.execute()

        # Check that symlinks were created for cycle 2 (offset by 0.5s)
        assert (boundary_data_dir / "0.500000").is_symlink()
        assert (boundary_data_dir / "0.600000").is_symlink()
        assert (boundary_data_dir / "0.700000").is_symlink()

        # Check that symlinks were created for cycle 3 (offset by 1.0s)
        assert (boundary_data_dir / "1.000000").is_symlink()
        assert (boundary_data_dir / "1.100000").is_symlink()
        assert (boundary_data_dir / "1.200000").is_symlink()

    def test_execute_symlinks_point_to_correct_source(self, setup_with_data):
        """Test that symlinks point to correct source directories."""
        setup, boundary_data_dir = setup_with_data

        setup.execute()

        # Check symlink targets
        link_path = boundary_data_dir / "0.500000"
        assert os.readlink(str(link_path)) == "0.000000"

        link_path = boundary_data_dir / "0.600000"
        assert os.readlink(str(link_path)) == "0.100000"

    def test_execute_removes_old_symlinks(self, setup_with_data):
        """Test that execute removes old symlinks before creating new ones."""
        setup, boundary_data_dir = setup_with_data

        # Create an old symlink
        old_link = boundary_data_dir / "0.999999"
        os.symlink("0.000000", str(old_link))
        assert old_link.is_symlink()

        setup.execute()

        # Old symlink should be removed
        assert not old_link.exists()

    def test_execute_preserves_original_directories(self, setup_with_data):
        """Test that execute preserves original time directories."""
        setup, boundary_data_dir = setup_with_data

        setup.execute()

        # Original directories should still exist
        assert (boundary_data_dir / "0.000000").is_dir()
        assert not (boundary_data_dir / "0.000000").is_symlink()
        assert (boundary_data_dir / "0.100000").is_dir()

    def test_execute_missing_directory_raises_error(self, tmp_path):
        """Test that execute raises FileNotFoundError for missing directory."""
        from aortacfd_lib.cycle_data_setup import CycleDataSetup

        config = {"geometry": {"inlet_keywords_ordered": "inlet"}, "simulation_control": {"number_of_cycles": 2}}

        # Don't create the boundary data directory

        with patch("aortacfd_lib.cycle_data_setup.Logger"):
            setup = CycleDataSetup(config, str(tmp_path), cardiac_cycle=0.8)

        with pytest.raises(FileNotFoundError) as exc_info:
            setup.execute()

        assert "Source data directory not found" in str(exc_info.value)

    def test_execute_empty_directory_raises_error(self, tmp_path):
        """Test that execute raises ValueError for empty time directory."""
        from aortacfd_lib.cycle_data_setup import CycleDataSetup

        config = {"geometry": {"inlet_keywords_ordered": "inlet"}, "simulation_control": {"number_of_cycles": 2}}

        # Create directory but with no time directories
        boundary_data_dir = tmp_path / "constant" / "boundaryData" / "inlet"
        boundary_data_dir.mkdir(parents=True)
        # Create a non-time file/directory
        (boundary_data_dir / "points").write_text("points file")

        with patch("aortacfd_lib.cycle_data_setup.Logger"):
            setup = CycleDataSetup(config, str(tmp_path), cardiac_cycle=0.8)

        with pytest.raises(ValueError) as exc_info:
            setup.execute()

        assert "No time step directories found" in str(exc_info.value)

    def test_execute_single_cycle_no_symlinks(self, tmp_path):
        """Test that execute with number_of_cycles=1 creates no symlinks."""
        from aortacfd_lib.cycle_data_setup import CycleDataSetup

        config = {
            "geometry": {"inlet_keywords_ordered": "inlet"},
            "simulation_control": {"number_of_cycles": 1},  # Single cycle
        }

        boundary_data_dir = tmp_path / "constant" / "boundaryData" / "inlet"
        boundary_data_dir.mkdir(parents=True)
        (boundary_data_dir / "0.000000").mkdir()
        (boundary_data_dir / "0.100000").mkdir()

        with patch("aortacfd_lib.cycle_data_setup.Logger"):
            setup = CycleDataSetup(config, str(tmp_path), cardiac_cycle=0.5)

        setup.execute()

        # Count symlinks - should be 0
        symlinks = [f for f in boundary_data_dir.iterdir() if f.is_symlink()]
        assert len(symlinks) == 0

    def test_execute_skips_existing_links(self, setup_with_data):
        """Test that execute skips creating links that already exist."""
        setup, boundary_data_dir = setup_with_data

        # Create a symlink that will conflict
        existing_link = boundary_data_dir / "0.500000"
        os.symlink("0.000000", str(existing_link))

        # Should not raise, just skip
        setup.execute()

        # Link should still exist
        assert existing_link.is_symlink()


class TestCycleDataSetupIntegration:
    """Integration tests for CycleDataSetup."""

    def test_full_cycle_setup(self, tmp_path):
        """Test complete cycle setup with realistic data."""
        from aortacfd_lib.cycle_data_setup import CycleDataSetup

        config = {"geometry": {"inlet_keywords_ordered": "inlet"}, "simulation_control": {"number_of_cycles": 4}}

        cardiac_cycle = 0.8  # 800ms cardiac cycle

        # Create boundary data directory
        boundary_data_dir = tmp_path / "constant" / "boundaryData" / "inlet"
        boundary_data_dir.mkdir(parents=True)

        # Create time points for first cardiac cycle (0 to 0.8s)
        time_points = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
        for t in time_points:
            time_dir = boundary_data_dir / f"{t:.6f}"
            time_dir.mkdir()
            (time_dir / "U").write_text(f"velocity at t={t}")

        with patch("aortacfd_lib.cycle_data_setup.Logger"):
            setup = CycleDataSetup(config, str(tmp_path), cardiac_cycle=cardiac_cycle)

        setup.execute()

        # Verify total time directories + symlinks
        all_items = list(boundary_data_dir.iterdir())
        dirs = [d for d in all_items if d.is_dir() and not d.is_symlink()]
        symlinks = [d for d in all_items if d.is_symlink()]

        # Original 8 directories
        assert len(dirs) == 8

        # 3 additional cycles * 8 time points = 24 symlinks
        assert len(symlinks) == 24

        # Verify a few specific symlinks
        assert (boundary_data_dir / f"{0.8:.6f}").is_symlink()  # Cycle 2, t=0
        assert (boundary_data_dir / f"{1.6:.6f}").is_symlink()  # Cycle 3, t=0
        assert (boundary_data_dir / f"{2.4:.6f}").is_symlink()  # Cycle 4, t=0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
