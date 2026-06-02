"""
Test suite for cycle_data_setup.py module.

Tests cover:
- CycleDataSetup initialization
- execute() method for creating symbolic links
- Error handling for missing directories
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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
        """With neither number_of_cycles nor end_time, falls back to the pipeline default (3)."""
        from aortacfd_lib.constants import DEFAULT_NUMBER_OF_CYCLES
        from aortacfd_lib.cycle_data_setup import CycleDataSetup

        config = {
            "geometry": {"inlet_keywords_ordered": "inlet"},
            # No simulation_control
        }

        with patch("aortacfd_lib.cycle_data_setup.Logger"):
            setup = CycleDataSetup(config, str(tmp_path), cardiac_cycle=0.9)

        assert setup.number_of_cycles == DEFAULT_NUMBER_OF_CYCLES == 3


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


class TestCycleCountFromEndTime:
    """Regression tests for deriving cycle count from end_time.

    Configs that pin ``simulation_control.end_time`` without a
    ``number_of_cycles`` key (e.g. the ub_* batch) previously defaulted to 1
    cycle, so the inlet boundaryData only covered the first cardiac cycle and
    the non-periodic timeVaryingMappedFixedValue BC flat-lined the inflow for
    the rest of the run. The count must now be derived from end_time.
    """

    def _make(self, tmp_path, sim_control, cardiac_cycle):
        from aortacfd_lib.cycle_data_setup import CycleDataSetup

        config = {"geometry": {"inlet_keywords_ordered": "inlet"}, "simulation_control": sim_control}
        with patch("aortacfd_lib.cycle_data_setup.Logger"):
            return CycleDataSetup(config, str(tmp_path), cardiac_cycle=cardiac_cycle)

    def test_end_time_derives_cycle_count(self, tmp_path):
        """end_time=1.5s, cardiac=0.5s, no number_of_cycles -> 3 cycles."""
        setup = self._make(tmp_path, {"end_time": 1.5}, cardiac_cycle=0.5)
        assert setup.number_of_cycles == 3

    def test_exact_multiple_not_rounded_up(self, tmp_path):
        """Exact integer multiples must not be pushed up by float noise (3, not 4)."""
        setup = self._make(tmp_path, {"end_time": 1.5}, cardiac_cycle=0.5)
        assert setup.number_of_cycles == 3

    def test_non_integer_multiple_ceils(self, tmp_path):
        """end_time=1.4s, cardiac=0.5s -> ceil(2.8) = 3 cycles (cover full run)."""
        setup = self._make(tmp_path, {"end_time": 1.4}, cardiac_cycle=0.5)
        assert setup.number_of_cycles == 3

    def test_end_time_overrides_explicit_cycles(self, tmp_path):
        """end_time wins over an inconsistent explicit number_of_cycles, matching the
        solver endTime (GenerateControlDictTask also prefers end_time). 1.5/0.5 -> 3."""
        setup = self._make(tmp_path, {"end_time": 1.5, "number_of_cycles": 2}, cardiac_cycle=0.5)
        assert setup.number_of_cycles == 3

    def test_explicit_cycles_used_when_no_end_time(self, tmp_path):
        """Explicit number_of_cycles is used when no usable end_time is given."""
        setup = self._make(tmp_path, {"number_of_cycles": 2}, cardiac_cycle=0.5)
        assert setup.number_of_cycles == 2

    def test_end_time_auto_falls_back(self, tmp_path):
        """end_time='auto' is not a usable number -> fall back to the pipeline default (3)."""
        setup = self._make(tmp_path, {"end_time": "auto"}, cardiac_cycle=0.5)
        assert setup.number_of_cycles == 3

    def test_zero_cardiac_cycle_falls_back(self, tmp_path):
        """A zero/invalid cardiac cycle must not divide-by-zero; fall back to the default (3)."""
        setup = self._make(tmp_path, {"end_time": 1.5}, cardiac_cycle=0.0)
        assert setup.number_of_cycles == 3

    def test_derived_cycles_tile_boundary_data(self, tmp_path):
        """End-to-end: end_time-derived count actually lays down covering symlinks."""
        boundary_data_dir = tmp_path / "constant" / "boundaryData" / "inlet"
        boundary_data_dir.mkdir(parents=True)
        for t in (0.0, 0.25, 0.5):  # one cardiac cycle of 0.5s
            (boundary_data_dir / f"{t:.6f}").mkdir()

        setup = self._make(tmp_path, {"end_time": 1.5}, cardiac_cycle=0.5)
        setup.execute()

        # Cycle 2 (offset 0.5) and cycle 3 (offset 1.0) must exist as symlinks,
        # so inflow data covers the full 1.5s run instead of flat-lining at 0.5s.
        assert (boundary_data_dir / f"{1.0:.6f}").is_symlink()
        assert (boundary_data_dir / f"{1.25:.6f}").is_symlink()
        assert (boundary_data_dir / f"{1.5:.6f}").is_symlink()


class TestCoverageGuard:
    """The static coverage guard: fail at setup if inlet data does not reach end_time.

    This is the cheap, no-solve version of a dead-inflow pre-flight check. It
    catches a config whose laid-down boundaryData stops short of end_time, so
    the non-periodic BC would hold its last value for the remainder of the run.
    """

    def _make_with_one_cycle(self, tmp_path, sim_control, cardiac_cycle=0.5):
        from aortacfd_lib.cycle_data_setup import CycleDataSetup

        boundary_data_dir = tmp_path / "constant" / "boundaryData" / "inlet"
        boundary_data_dir.mkdir(parents=True)
        for t in (0.0, 0.25, 0.5):  # one cardiac cycle of 0.5s
            (boundary_data_dir / f"{t:.6f}").mkdir()

        config = {"geometry": {"inlet_keywords_ordered": "inlet"}, "simulation_control": sim_control}
        with patch("aortacfd_lib.cycle_data_setup.Logger"):
            setup = CycleDataSetup(config, str(tmp_path), cardiac_cycle=cardiac_cycle)
        return setup, boundary_data_dir

    def test_undercoverage_raises_when_derivation_unavailable(self, tmp_path):
        """Defense-in-depth: if the cardiac cycle can't be used to derive coverage
        (e.g. detection failed -> cardiac_cycle=0) and the explicit cycle count
        under-covers end_time, the guard fails fast instead of flat-lining."""
        # cardiac_cycle=0 skips end_time-derivation, so explicit number_of_cycles=1 is used;
        # one cycle of data (max 0.5s) cannot cover end_time=1.5s.
        setup, _ = self._make_with_one_cycle(tmp_path, {"end_time": 1.5, "number_of_cycles": 1}, cardiac_cycle=0.0)
        with pytest.raises(ValueError) as exc_info:
            setup.execute()
        assert "flat-line" in str(exc_info.value)

    def test_end_time_overrides_explicit_so_coverage_holds(self, tmp_path):
        """With a valid cardiac cycle, end_time wins over a too-small explicit count,
        so coverage is satisfied and the guard does not raise."""
        setup, _ = self._make_with_one_cycle(tmp_path, {"end_time": 1.5, "number_of_cycles": 2})
        setup.execute()  # resolves to 3 cycles (end_time/cardiac), covers 1.5s

    def test_full_coverage_passes(self, tmp_path):
        """Derived count covers end_time exactly -> no raise."""
        setup, _ = self._make_with_one_cycle(tmp_path, {"end_time": 1.5})
        setup.execute()  # 3 cycles derived; max time 1.5 covers end_time

    def test_no_end_time_skips_guard(self, tmp_path):
        """No end_time (cycle-count style config) -> guard is a no-op, no raise."""
        setup, _ = self._make_with_one_cycle(tmp_path, {"number_of_cycles": 1})
        setup.execute()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
