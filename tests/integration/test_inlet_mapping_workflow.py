"""
Integration tests for inlet_mapping.py run() orchestration method.
Tests the complete workflow with mocked dependencies.
"""
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil
import os

from src.aortacfd_lib.inlet_mapping import InletMapping


@pytest.fixture
def inlet_mapping_config():
    """Complete configuration for InletMapping integration test."""
    return {
        "inlet": {
            "type": "TIMEVARYING",
            "csv_file": "flow.csv",
            "data_type": "velocity",
            "profile": "plug",
            "orientation": "in"
        },
        "geometry": {
            "inlet_keywords_ordered": "inlet",
            "scale_factor": 1e-3
        },
        "physics": {
            "nu": 3.5e-6,
            "blood_density": 1060,
            "blood_viscosity": 0.004
        }
    }


@pytest.fixture
def case_dir_with_full_structure():
    """Case directory with complete structure for inlet mapping."""
    temp_dir = tempfile.mkdtemp()

    # Create directory structure
    tri_surface = Path(temp_dir) / "constant" / "triSurface"
    tri_surface.mkdir(parents=True, exist_ok=True)

    boundary_data = Path(temp_dir) / "constant" / "boundaryData" / "inlet"
    boundary_data.mkdir(parents=True, exist_ok=True)

    # Create dummy STL file
    stl_file = tri_surface / "inlet.stl"
    stl_file.write_text("solid inlet\nendsolid inlet\n")

    # Create points file
    points_file = boundary_data / "points"
    points_content = """3
(
(0.0 0.0 0.0)
(0.01 0.0 0.0)
(0.0 0.01 0.0)
"""
    points_file.write_text(points_content)

    # Create CSV file
    csv_file = boundary_data / "flow.csv"
    csv_content = """time,velocity
0.0,0.5
0.1,0.6
0.2,0.7
0.3,0.8
"""
    csv_file.write_text(csv_content)

    yield temp_dir
    shutil.rmtree(temp_dir)


class TestInletMappingRunMethod:
    """Integration tests for InletMapping.run() orchestration."""

    def test_run_complete_workflow_plug_profile(self, inlet_mapping_config, case_dir_with_full_structure):
        """Test complete run() workflow with plug profile."""
        inlet_mapper = InletMapping(inlet_mapping_config, case_dir_with_full_structure)

        # Mock PatchProcessing
        with patch('src.aortacfd_lib.inlet_mapping.PatchProcessing') as MockPatchProc:
            mock_processor = Mock()
            mock_processor.calculate_inlet_center_radius.return_value = (
                np.array([0.0, 0.0, 0.0]),  # center
                0.01,  # radius (10mm in meters)
                np.array([0.0, 0.0, 1.0])  # normal
            )
            MockPatchProc.return_value = mock_processor

            # Run the workflow
            inlet_mapper.run()

            # Verify that geometry was calculated
            assert inlet_mapper.center is not None
            assert inlet_mapper.radius is not None
            assert inlet_mapper.cardiac_cycle is not None

            # Verify geometry values
            assert np.allclose(inlet_mapper.center, [0.0, 0.0, 0.0])
            assert inlet_mapper.radius == 0.01
            assert inlet_mapper.cardiac_cycle == 0.3  # Last time - first time

            # Verify time directories were created
            parent_dir = Path(case_dir_with_full_structure) / "constant" / "boundaryData" / "inlet"
            time_dirs = [d for d in parent_dir.iterdir() if d.is_dir() and d.name.replace('.', '', 1).replace('-', '').isdigit()]
            assert len(time_dirs) == 4  # 4 time steps from CSV

    def test_run_with_auto_orientation(self, inlet_mapping_config, case_dir_with_full_structure):
        """Test run() with automatic orientation detection."""
        # Modify config for auto orientation
        inlet_mapping_config["inlet"]["orientation"] = "auto"
        inlet_mapper = InletMapping(inlet_mapping_config, case_dir_with_full_structure)

        # Mock PatchProcessing
        with patch('src.aortacfd_lib.inlet_mapping.PatchProcessing') as MockPatchProc:
            mock_processor = Mock()
            mock_processor.calculate_inlet_center_radius.return_value = (
                np.array([0.0, 0.0, 0.0]),
                0.01,
                np.array([1.0, 0.0, 0.0])  # Normal pointing in +x direction
            )
            MockPatchProc.return_value = mock_processor

            # Mock _determine_inward_direction
            with patch.object(inlet_mapper, '_determine_inward_direction', return_value=True) as mock_determine:
                inlet_mapper.run()

                # Verify auto-detection was called
                mock_determine.assert_called_once()
                assert inlet_mapper.auto_flip_normal == True

    def test_run_missing_points_file(self, inlet_mapping_config, case_dir_with_full_structure):
        """Test run() raises error when points file is missing."""
        inlet_mapper = InletMapping(inlet_mapping_config, case_dir_with_full_structure)

        # Remove points file
        points_file = Path(case_dir_with_full_structure) / "constant" / "boundaryData" / "inlet" / "points"
        points_file.unlink()

        # Mock PatchProcessing
        with patch('src.aortacfd_lib.inlet_mapping.PatchProcessing') as MockPatchProc:
            mock_processor = Mock()
            mock_processor.calculate_inlet_center_radius.return_value = (
                np.array([0.0, 0.0, 0.0]),
                0.01,
                np.array([0.0, 0.0, 1.0])
            )
            MockPatchProc.return_value = mock_processor

            # Should raise FileNotFoundError
            with pytest.raises(FileNotFoundError, match="Points file not found"):
                inlet_mapper.run()

    def test_run_missing_csv_file(self, inlet_mapping_config, case_dir_with_full_structure):
        """Test run() raises error when CSV file is missing."""
        inlet_mapper = InletMapping(inlet_mapping_config, case_dir_with_full_structure)

        # Remove CSV file
        csv_file = Path(case_dir_with_full_structure) / "constant" / "boundaryData" / "inlet" / "flow.csv"
        csv_file.unlink()

        # Mock PatchProcessing
        with patch('src.aortacfd_lib.inlet_mapping.PatchProcessing') as MockPatchProc:
            mock_processor = Mock()
            mock_processor.calculate_inlet_center_radius.return_value = (
                np.array([0.0, 0.0, 0.0]),
                0.01,
                np.array([0.0, 0.0, 1.0])
            )
            MockPatchProc.return_value = mock_processor

            # Should raise FileNotFoundError
            with pytest.raises(FileNotFoundError, match="Inlet data CSV not found"):
                inlet_mapper.run()

    def test_run_cleans_old_time_directories(self, inlet_mapping_config, case_dir_with_full_structure):
        """Test run() cleans old time directories before generating new ones."""
        inlet_mapper = InletMapping(inlet_mapping_config, case_dir_with_full_structure)

        # Create old time directories
        parent_dir = Path(case_dir_with_full_structure) / "constant" / "boundaryData" / "inlet"
        old_time_dir = parent_dir / "0.12345"
        old_time_dir.mkdir()
        (old_time_dir / "U").write_text("dummy")

        # Mock PatchProcessing
        with patch('src.aortacfd_lib.inlet_mapping.PatchProcessing') as MockPatchProc:
            mock_processor = Mock()
            mock_processor.calculate_inlet_center_radius.return_value = (
                np.array([0.0, 0.0, 0.0]),
                0.01,
                np.array([0.0, 0.0, 1.0])
            )
            MockPatchProc.return_value = mock_processor

            # Run workflow
            inlet_mapper.run()

            # Verify old time directory was removed
            assert not old_time_dir.exists()

    def test_run_with_parabolic_profile(self, inlet_mapping_config, case_dir_with_full_structure):
        """Test run() workflow with parabolic velocity profile."""
        # Modify config for parabolic profile
        inlet_mapping_config["inlet"]["profile"] = "parabolic"
        inlet_mapper = InletMapping(inlet_mapping_config, case_dir_with_full_structure)

        # Mock PatchProcessing
        with patch('src.aortacfd_lib.inlet_mapping.PatchProcessing') as MockPatchProc:
            mock_processor = Mock()
            mock_processor.calculate_inlet_center_radius.return_value = (
                np.array([0.0, 0.0, 0.0]),
                0.01,
                np.array([0.0, 0.0, 1.0])
            )
            MockPatchProc.return_value = mock_processor

            # Run the workflow
            inlet_mapper.run()

            # Verify workflow completed
            assert inlet_mapper.center is not None
            assert inlet_mapper.radius is not None

            # Verify time directories were created
            parent_dir = Path(case_dir_with_full_structure) / "constant" / "boundaryData" / "inlet"
            time_dirs = [d for d in parent_dir.iterdir() if d.is_dir() and d.name.replace('.', '', 1).replace('-', '').isdigit()]
            assert len(time_dirs) == 4  # 4 time steps

    def test_run_with_womersley_profile(self, inlet_mapping_config, case_dir_with_full_structure):
        """Test run() workflow with Womersley velocity profile."""
        # Modify config for Womersley profile
        inlet_mapping_config["inlet"]["profile"] = "womersley"
        inlet_mapper = InletMapping(inlet_mapping_config, case_dir_with_full_structure)

        # Mock PatchProcessing
        with patch('src.aortacfd_lib.inlet_mapping.PatchProcessing') as MockPatchProc:
            mock_processor = Mock()
            mock_processor.calculate_inlet_center_radius.return_value = (
                np.array([0.0, 0.0, 0.0]),
                0.01,
                np.array([0.0, 0.0, 1.0])
            )
            MockPatchProc.return_value = mock_processor

            # Run the workflow
            inlet_mapper.run()

            # Verify workflow completed
            assert inlet_mapper.center is not None
            assert inlet_mapper.radius is not None
            assert inlet_mapper.cardiac_cycle is not None

            # Verify time directories were created
            parent_dir = Path(case_dir_with_full_structure) / "constant" / "boundaryData" / "inlet"
            time_dirs = [d for d in parent_dir.iterdir() if d.is_dir() and d.name.replace('.', '', 1).replace('-', '').isdigit()]
            assert len(time_dirs) == 4


# Integration test summary
"""
Integration Test Coverage for run() method:
- test_run_complete_workflow_plug_profile: Full workflow execution
- test_run_with_auto_orientation: Auto-detection path
- test_run_missing_points_file: Error handling (points)
- test_run_missing_csv_file: Error handling (CSV)
- test_run_cleans_old_time_directories: Cleanup logic
- test_run_with_parabolic_profile: Parabolic profile workflow
- test_run_with_womersley_profile: Womersley profile workflow

Total: 7 integration tests for run() orchestration
Expected coverage improvement: 58% → 75%+ for inlet_mapping.py
"""
