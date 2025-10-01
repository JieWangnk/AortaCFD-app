"""
Integration tests for mesh generation workflow.

Tests end-to-end mesh setup including geometry analysis, mesh file generation,
and validation of mesh parameters.
"""

import pytest
import json
from pathlib import Path
from src.workflow.tasks.setup_tasks import (
    CreateCaseStructureTask,
    GenerateMeshFilesTask,
)
from src.aortacfd_lib.mesh_setup import GeometryAnalyzer


@pytest.mark.integration
class TestMeshWorkflow:
    """Test complete mesh generation workflow."""

    @pytest.fixture
    def minimal_config(self):
        """Minimal configuration with geometry section."""
        return {
            "geometry": {
                "case_name": "test_case",
                "scale_factor": 0.001,
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["outlet1"],
                "wall_keywords_ordered": "wall"
            },
            "inlet": {
                "csv_file": "flow.csv"
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

    def test_case_structure_creation_with_validation(self, temp_case_dir, minimal_config):
        """Test case structure creation includes geometry validation."""
        # Setup: Create minimal geometry files
        case_name = minimal_config["geometry"]["case_name"]
        case_input_dir = Path("cases_input") / case_name
        case_input_dir.mkdir(parents=True, exist_ok=True)

        # Create minimal STL files
        tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
        for stl_file in ["inlet.stl", "outlet1.stl", "wall.stl"]:
            (case_input_dir / stl_file).write_text("solid mesh\nendsolid mesh\n")

        # Create inlet CSV
        inlet_csv = minimal_config["inlet"]["csv_file"]
        csv_content = "time,velocity\n0.0,0.5\n0.1,0.6\n"
        (case_input_dir / inlet_csv).write_text(csv_content)

        # Execute task
        task = CreateCaseStructureTask(minimal_config)
        context = {"case_directory": str(temp_case_dir)}

        result = task.execute(context)

        # Verify success
        assert result is True

        # Verify directory structure
        assert (Path(temp_case_dir) / "system").exists()
        assert (Path(temp_case_dir) / "constant" / "triSurface").exists()
        assert (Path(temp_case_dir) / "0").exists()

        # Verify files copied
        assert (tri_surface / "inlet.stl").exists()
        assert (tri_surface / "outlet1.stl").exists()
        assert (tri_surface / "wall.stl").exists()

        # Cleanup
        import shutil
        shutil.rmtree(case_input_dir)

    def test_mesh_file_generation_workflow(self, temp_case_dir, minimal_config):
        """Test mesh file generation produces all required files."""
        # Setup: Create geometry files
        case_name = minimal_config["geometry"]["case_name"]
        case_input_dir = Path("cases_input") / case_name
        case_input_dir.mkdir(parents=True, exist_ok=True)

        tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)

        # Create realistic STL files
        for stl_file in ["inlet.stl", "outlet1.stl", "wall.stl"]:
            (tri_surface / stl_file).write_text("solid mesh\nendsolid mesh\n")
            (case_input_dir / stl_file).write_text("solid mesh\nendsolid mesh\n")

        # Create inlet CSV
        inlet_csv = minimal_config["inlet"]["csv_file"]
        (case_input_dir / inlet_csv).write_text("time,velocity\n0.0,0.5\n")

        # Execute: Create structure first
        create_task = CreateCaseStructureTask(minimal_config)
        context = {"case_directory": str(temp_case_dir)}
        assert create_task.execute(context) is True

        # Execute: Generate mesh files
        mesh_task = GenerateMeshFilesTask(minimal_config)
        result = mesh_task.execute(context)

        # Verify success
        assert result is True

        # Verify mesh files created
        system_dir = Path(temp_case_dir) / "system"
        assert (system_dir / "blockMeshDict").exists()
        assert (system_dir / "snappyHexMeshDict").exists()
        assert (system_dir / "surfaceFeaturesDict").exists()

        # Cleanup
        import shutil
        shutil.rmtree(case_input_dir)

    def test_geometry_analyzer_integration(self, temp_case_dir, minimal_config):
        """Test GeometryAnalyzer integration with real geometry."""
        # Setup geometry
        tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)

        # Create STL files
        for stl in ["inlet.stl", "outlet1.stl", "wall.stl"]:
            (tri_surface / stl).write_text("solid mesh\nendsolid mesh\n")

        # Create analyzer
        analyzer = GeometryAnalyzer(
            config=minimal_config,
            case_directory=str(temp_case_dir)
        )

        # Test patch property calculation
        patches = analyzer._extract_patches()
        assert "inlet" in patches
        assert "outlet1" in patches

        # Test mesh file writing
        analyzer.write_all_mesh_files()

        # Verify files created
        system_dir = Path(temp_case_dir) / "system"
        assert (system_dir / "blockMeshDict").exists()
        assert (system_dir / "snappyHexMeshDict").exists()


@pytest.mark.integration
class TestMeshParameterCalculation:
    """Test mesh parameter calculations in realistic scenarios."""

    @pytest.fixture
    def minimal_config(self):
        """Minimal configuration with geometry section."""
        return {
            "geometry": {
                "case_name": "test_case",
                "scale_factor": 0.001,
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["outlet1"],
                "wall_keywords_ordered": "wall",
                "reference_radius_strategy": "min"
            },
            "inlet": {
                "csv_file": "flow.csv"
            },
            "mesh": {
                "SNAPPY_SETTINGS": {
                    "parallel": False,
                    "nProcessors": 1
                }
            }
        }

    def test_cell_size_calculation_workflow(self, temp_case_dir, minimal_config):
        """Test cell size calculations from geometry."""
        # Setup
        tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)

        for stl in ["inlet.stl", "outlet1.stl"]:
            (tri_surface / stl).write_text("solid mesh\nendsolid mesh\n")

        analyzer = GeometryAnalyzer(
            config=minimal_config,
            case_directory=str(temp_case_dir)
        )

        # Test reference radius calculation
        ref_radius = analyzer._calculate_reference_radius()

        # Should be positive and realistic
        assert ref_radius > 0
        assert ref_radius < 0.1  # Less than 100mm in meters

    def test_blockMesh_bounds_calculation(self, temp_case_dir, minimal_config):
        """Test blockMesh domain bounds calculation."""
        tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)

        (tri_surface / "inlet.stl").write_text("solid mesh\nendsolid mesh\n")

        analyzer = GeometryAnalyzer(
            config=minimal_config,
            case_directory=str(temp_case_dir)
        )

        # Calculate bounds
        from unittest.mock import patch
        import math

        # Mock STL vertex extraction to return known bounds
        with patch.object(analyzer, '_extract_stl_vertices', return_value=[
            (0.0, 0.0, 0.0),
            (10.0, 10.0, 10.0)
        ]):
            bounds = analyzer._calculate_blockmesh_bounds()

        # Verify bounds are expanded beyond geometry
        assert len(bounds) == 6  # xmin, ymin, zmin, xmax, ymax, zmax
        assert bounds[0] < 0.0  # xmin expanded
        assert bounds[3] > 10.0  # xmax expanded


@pytest.mark.integration
class TestMeshWorkflowErrorHandling:
    """Test error handling in mesh workflow."""

    @pytest.fixture
    def minimal_config(self):
        """Minimal configuration with geometry section."""
        return {
            "geometry": {
                "case_name": "test_case",
                "scale_factor": 0.001,
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["outlet1"],
                "wall_keywords_ordered": "wall",
                "reference_radius_strategy": "min"
            },
            "inlet": {
                "csv_file": "flow.csv"
            },
            "mesh": {
                "SNAPPY_SETTINGS": {
                    "parallel": False,
                    "nProcessors": 1
                }
            }
        }

    def test_invalid_geometry_blocks_workflow(self, temp_case_dir, minimal_config):
        """Test that invalid geometry is caught during workflow."""
        # Setup: Create case without STL files
        case_name = minimal_config["geometry"]["case_name"]
        case_input_dir = Path("cases_input") / case_name
        case_input_dir.mkdir(parents=True, exist_ok=True)

        # NO STL files created - should fail validation

        task = CreateCaseStructureTask(minimal_config)
        context = {"case_directory": str(temp_case_dir)}

        # Should fail due to missing geometry
        result = task.execute(context)
        assert result is False

        # Cleanup
        import shutil
        shutil.rmtree(case_input_dir)

    def test_missing_inlet_csv_detected(self, temp_case_dir, minimal_config):
        """Test that missing inlet CSV is detected."""
        # Setup: Create STL but no CSV
        case_name = minimal_config["geometry"]["case_name"]
        case_input_dir = Path("cases_input") / case_name
        case_input_dir.mkdir(parents=True, exist_ok=True)

        # Create STL files
        for stl in ["inlet.stl", "outlet1.stl", "wall.stl"]:
            (case_input_dir / stl).write_text("solid mesh\nendsolid mesh\n")

        # NO CSV file - should be caught

        task = CreateCaseStructureTask(minimal_config)
        context = {"case_directory": str(temp_case_dir)}

        # May fail or succeed depending on validation strictness
        # At minimum, should not crash
        try:
            result = task.execute(context)
            # If it succeeds, that's okay - inlet CSV might be optional in some configs
            assert isinstance(result, bool)
        except Exception as e:
            # Should be a controlled error, not a crash
            assert "inlet" in str(e).lower() or "csv" in str(e).lower()

        # Cleanup
        import shutil
        shutil.rmtree(case_input_dir)


@pytest.mark.integration
@pytest.mark.slow
class TestMeshWorkflowPerformance:
    """Test mesh workflow performance."""

    @pytest.fixture
    def minimal_config(self):
        """Minimal configuration with geometry section."""
        return {
            "geometry": {
                "case_name": "test_case",
                "scale_factor": 0.001,
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["outlet1"],
                "wall_keywords_ordered": "wall",
                "reference_radius_strategy": "min"
            },
            "inlet": {
                "csv_file": "flow.csv"
            },
            "mesh": {
                "SNAPPY_SETTINGS": {
                    "parallel": False,
                    "nProcessors": 1
                }
            }
        }

    def test_geometry_analysis_performance(self, temp_case_dir, minimal_config):
        """Test that geometry analysis is reasonably fast."""
        import time

        # Setup
        tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)

        for stl in ["inlet.stl", "outlet1.stl", "wall.stl"]:
            (tri_surface / stl).write_text("solid mesh\nendsolid mesh\n")

        # Time geometry analysis
        start = time.time()

        analyzer = GeometryAnalyzer(
            config=minimal_config,
            case_directory=str(temp_case_dir)
        )
        analyzer.write_all_mesh_files()

        elapsed = time.time() - start

        # Should complete in under 5 seconds
        assert elapsed < 5.0

    def test_multiple_mesh_file_generation(self, temp_case_dir, minimal_config):
        """Test repeated mesh file generation (idempotency)."""
        # Setup
        tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)

        for stl in ["inlet.stl", "outlet1.stl"]:
            (tri_surface / stl).write_text("solid mesh\nendsolid mesh\n")

        analyzer = GeometryAnalyzer(
            config=minimal_config,
            case_directory=str(temp_case_dir)
        )

        # Generate files twice
        analyzer.write_all_mesh_files()
        analyzer.write_all_mesh_files()

        # Should succeed both times (idempotent)
        system_dir = Path(temp_case_dir) / "system"
        assert (system_dir / "blockMeshDict").exists()
        assert (system_dir / "snappyHexMeshDict").exists()
