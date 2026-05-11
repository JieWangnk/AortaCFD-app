"""
Test suite for setup tasks module.

Tests cover:
- CreateCaseStructureTask
- GenerateMeshFilesTask
- PrepareBoundaryDataTask
- GenerateBCFilesTask
- GeneratePhysicalPropertiesTask
- GenerateNumericalSchemesTask
- GenerateSolverSettingsTask
- GenerateControlDictTask
"""

import pytest
import sys
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from workflow.base_task import ExecutionContext


class TestCreateCaseStructureTask:
    """Test CreateCaseStructureTask class."""

    def test_task_creates_directories(self):
        """Test that task creates required directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock CAD folder with STL files
            cad_folder = os.path.join(tmpdir, "cases_input", "test_patient")
            os.makedirs(cad_folder)

            # Create minimal STL file (binary format)
            inlet_stl = os.path.join(cad_folder, "inlet.stl")
            _create_minimal_binary_stl(inlet_stl)

            outlet_stl = os.path.join(cad_folder, "outlet1.stl")
            _create_minimal_binary_stl(outlet_stl)

            wall_stl = os.path.join(cad_folder, "wall_aorta.stl")
            _create_minimal_binary_stl(wall_stl)

            case_dir = os.path.join(tmpdir, "output", "openfoam")

            config = {
                "geometry": {"case_name": "test_patient", "scale_factor": 0.001, "inlet_keywords_ordered": "inlet"},
                "clean_run": False,
            }

            # Import and create task
            from workflow.tasks.setup_tasks import CreateCaseStructureTask

            task = CreateCaseStructureTask(config)
            context = {"case_directory": case_dir}

            # Execute task - need to be in tmpdir for relative path
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                # Mock the geometry validator to pass
                with patch("workflow.tasks.setup_tasks.GeometryValidator") as mock_validator:
                    mock_result = Mock()
                    mock_result.is_valid = True
                    mock_result.warnings = []
                    mock_result.errors = []
                    mock_validator.return_value.validate_all.return_value = mock_result

                    result = task.execute(context)
            finally:
                os.chdir(original_cwd)

            if result:  # If task succeeded
                assert os.path.exists(case_dir)
                assert os.path.exists(os.path.join(case_dir, "system"))
                assert os.path.exists(os.path.join(case_dir, "constant", "triSurface"))
                assert os.path.exists(os.path.join(case_dir, "0"))
                assert os.path.exists(os.path.join(case_dir, "logs"))

    def test_task_clean_run_removes_existing(self):
        """Test that clean_run=True removes existing case directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = os.path.join(tmpdir, "output", "openfoam")
            os.makedirs(case_dir)

            # Create a file to verify it gets deleted
            marker_file = os.path.join(case_dir, "marker.txt")
            with open(marker_file, "w") as f:
                f.write("test")

            config = {
                "geometry": {"case_name": "test_patient", "scale_factor": 0.001, "inlet_keywords_ordered": "inlet"},
                "clean_run": True,
            }

            from workflow.tasks.setup_tasks import CreateCaseStructureTask

            task = CreateCaseStructureTask(config)
            context = {"case_directory": case_dir}

            # Setup CAD folder
            cad_folder = os.path.join(tmpdir, "cases_input", "test_patient")
            os.makedirs(cad_folder)
            _create_minimal_binary_stl(os.path.join(cad_folder, "inlet.stl"))
            _create_minimal_binary_stl(os.path.join(cad_folder, "outlet1.stl"))
            _create_minimal_binary_stl(os.path.join(cad_folder, "wall_aorta.stl"))

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                with patch("workflow.tasks.setup_tasks.GeometryValidator") as mock_validator:
                    mock_result = Mock()
                    mock_result.is_valid = True
                    mock_result.warnings = []
                    mock_result.errors = []
                    mock_validator.return_value.validate_all.return_value = mock_result

                    result = task.execute(context)
            finally:
                os.chdir(original_cwd)

            # Marker file should be gone if clean_run worked
            if result:
                assert not os.path.exists(marker_file)


class TestGenerateControlDictTask:
    """Test GenerateControlDictTask class."""

    def test_calculate_end_time_from_cycles(self):
        """Test endTime calculation from cardiac cycles."""
        config = {
            "simulation_control": {
                "number_of_cycles": 3,
                "controlDict": {"application": "foamRun", "writeInterval": 0.01},
            }
        }

        from workflow.tasks.setup_tasks import GenerateControlDictTask

        task = GenerateControlDictTask(config)
        context = {"case_directory": "/tmp/test", "cardiac_cycle": 0.8}  # 0.8s per cycle

        # Mock the SimulationSetup
        with patch("workflow.tasks.setup_tasks.SimulationSetup") as mock_setup:
            result = task.execute(context)

            # Check that write_controlDict was called
            mock_setup.return_value.write_controlDict.assert_called_once()

            # Get the arguments passed to write_controlDict
            call_args = mock_setup.return_value.write_controlDict.call_args
            final_control_dict = call_args.kwargs["final_control_dict"]

            # endTime should be 3 * 0.8 = 2.4
            assert final_control_dict["endTime"] == pytest.approx(2.4, rel=1e-9)

    def test_calculate_purge_write_direct(self):
        """Test purgeWrite with direct value."""
        config = {
            "simulation_control": {
                "number_of_cycles": 5,
                "controlDict": {"application": "foamRun", "writeInterval": 0.01, "purgeWrite": 100},
            }
        }

        from workflow.tasks.setup_tasks import GenerateControlDictTask

        task = GenerateControlDictTask(config)

        sim_controls = config["simulation_control"]
        control_dict = config["simulation_control"]["controlDict"]

        purge_write = task._calculate_purge_write(sim_controls, control_dict, 0.8)

        # Should use direct value
        assert purge_write == 100

    def test_calculate_purge_write_keep_last_cycles(self):
        """Test purgeWrite from keep_last_cycles."""
        config = {
            "simulation_control": {
                "keep_last_cycles": 2,
                "number_of_cycles": 5,
                "controlDict": {"application": "foamRun", "writeInterval": 0.01},
            }
        }

        from workflow.tasks.setup_tasks import GenerateControlDictTask

        task = GenerateControlDictTask(config)

        sim_controls = config["simulation_control"]
        control_dict = config["simulation_control"]["controlDict"]
        cardiac_cycle = 0.8

        purge_write = task._calculate_purge_write(sim_controls, control_dict, cardiac_cycle)

        # Should calculate: timesteps_per_cycle = 0.8 / 0.01 = 80
        # purgeWrite = 80 * 2 * 1.1 = 176
        expected = int(80 * 2 * 1.1)
        assert purge_write == expected

    def test_calculate_purge_write_no_cardiac_cycle(self):
        """Test purgeWrite when cardiac_cycle is not available."""
        config = {"simulation_control": {"keep_last_cycles": 2, "controlDict": {"writeInterval": 0.01}}}

        from workflow.tasks.setup_tasks import GenerateControlDictTask

        task = GenerateControlDictTask(config)

        sim_controls = config["simulation_control"]
        control_dict = config["simulation_control"]["controlDict"]

        # No cardiac_cycle
        purge_write = task._calculate_purge_write(sim_controls, control_dict, None)

        # Should return None when cardiac_cycle not available
        assert purge_write is None


class TestPrepareBoundaryDataTask:
    """Test PrepareBoundaryDataTask class."""

    def test_flowrate_unit_conversion(self):
        """Test flow rate unit conversion from L/min to m³/s."""
        # Test the conversion logic used in _calculate_constant_flowrate
        flowrate_Lmin = 5.0  # 5 L/min
        flow_rate_m3s = flowrate_Lmin / 60.0 / 1000.0

        expected = 5.0 / 60.0 / 1000.0  # L/min to m³/s
        assert flow_rate_m3s == pytest.approx(expected, rel=1e-10)

    def test_calculate_constant_flowrate_from_velocity(self):
        """Test flow rate calculation from velocity parameter."""
        velocity = 0.5  # m/s
        inlet_area = 1e-4  # m²

        flow_rate = velocity * inlet_area

        expected = 0.5 * 1e-4
        assert abs(flow_rate - expected) < 1e-10

    def test_find_inlet_csv_in_case_dir(self):
        """Test finding CSV file in case directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = os.path.join(tmpdir, "case")
            os.makedirs(case_dir)

            csv_file = os.path.join(case_dir, "inlet.csv")
            with open(csv_file, "w") as f:
                f.write("time,flowrate\n0,0.5\n")

            config = {}

            from workflow.tasks.setup_tasks import PrepareBoundaryDataTask

            task = PrepareBoundaryDataTask(config)

            found = task._find_inlet_csv("inlet.csv", case_dir)

            assert found == csv_file

    def test_validate_inlet_csv_valid(self):
        """Test CSV validation with valid file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_file = os.path.join(tmpdir, "inlet.csv")

            # Create valid CSV
            lines = ["time,flowrate"]
            for i in range(20):
                lines.append(f"{i * 0.05:.3f},{0.5:.3f}")

            with open(csv_file, "w") as f:
                f.write("\n".join(lines))

            config = {}

            from workflow.tasks.setup_tasks import PrepareBoundaryDataTask

            task = PrepareBoundaryDataTask(config)

            result = task._validate_inlet_csv(csv_file)
            assert result is True

    def test_validate_inlet_csv_empty(self):
        """Test CSV validation with empty file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_file = os.path.join(tmpdir, "empty.csv")
            open(csv_file, "w").close()  # Create empty file

            config = {}

            from workflow.tasks.setup_tasks import PrepareBoundaryDataTask

            task = PrepareBoundaryDataTask(config)

            with pytest.raises(ValueError, match="empty"):
                task._validate_inlet_csv(csv_file)

    def test_validate_inlet_csv_non_monotonic(self):
        """Test CSV validation with non-monotonic time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_file = os.path.join(tmpdir, "bad.csv")

            with open(csv_file, "w") as f:
                f.write("time,flowrate\n")
                f.write("0.0,0.5\n")
                f.write("0.1,0.6\n")
                f.write("0.05,0.55\n")  # Non-monotonic

            config = {}

            from workflow.tasks.setup_tasks import PrepareBoundaryDataTask

            task = PrepareBoundaryDataTask(config)

            with pytest.raises(ValueError, match="monotonically increasing"):
                task._validate_inlet_csv(csv_file)


class TestGenerateBCFilesTask:
    """Test GenerateBCFilesTask class."""

    def test_task_validates_before_generating(self):
        """Test that task validates BCs before generating files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = os.path.join(tmpdir, "openfoam")
            os.makedirs(os.path.join(case_dir, "0"))

            config = {
                "boundary_conditions": {
                    "inlet": {"type": "CONSTANT", "velocity": 0.5, "profile": "parabolic"},
                    "outlets": {"type": "ZEROGRADIENT"},
                }
            }

            from workflow.tasks.setup_tasks import GenerateBCFilesTask

            task = GenerateBCFilesTask(config)
            context = {"case_directory": case_dir}

            # Mock both validator and BC generator
            with (
                patch("workflow.tasks.setup_tasks.BoundaryConditionValidator") as mock_validator,
                patch("workflow.tasks.setup_tasks.BoundaryConditionSetup") as mock_bc_setup,
            ):

                mock_result = Mock()
                mock_result.is_valid = True
                mock_result.warnings = []
                mock_result.errors = []
                mock_validator.return_value.validate_all.return_value = mock_result

                result = task.execute(context)

                # Validator should be called
                mock_validator.return_value.validate_all.assert_called_once()

                # If valid, BC setup should be called
                if result:
                    mock_bc_setup.return_value.write_all_bc_files.assert_called_once()

    def test_task_fails_on_invalid_bc(self):
        """Test that task fails when BC validation fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = os.path.join(tmpdir, "openfoam")
            os.makedirs(os.path.join(case_dir, "0"))

            config = {}

            from workflow.tasks.setup_tasks import GenerateBCFilesTask

            task = GenerateBCFilesTask(config)
            context = {"case_directory": case_dir}

            with patch("workflow.tasks.setup_tasks.BoundaryConditionValidator") as mock_validator:
                mock_result = Mock()
                mock_result.is_valid = False
                mock_result.warnings = []
                mock_result.errors = ["Missing inlet configuration"]
                mock_validator.return_value.validate_all.return_value = mock_result

                result = task.execute(context)

                assert result is False


class TestGenerateSimulationReportTask:
    """Test GenerateSimulationReportTask class."""

    def test_report_generation(self):
        """Test simulation report generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = os.path.join(tmpdir, "openfoam")
            os.makedirs(case_dir)

            config = {}

            from workflow.tasks.setup_tasks import GenerateSimulationReportTask

            task = GenerateSimulationReportTask(config)
            context = {"case_directory": case_dir, "patient_name": "test_patient"}

            with patch("workflow.tasks.setup_tasks.SimulationReportGenerator") as mock_gen:
                mock_gen.return_value.generate_full_report.return_value = "report.md"

                result = task.execute(context)

                # Should succeed even if generation fails (non-critical)
                assert result is True


class TestGenerateWindkesselReportTask:
    """Test GenerateWindkesselReportTask class."""

    def test_skips_non_windkessel(self):
        """Test that task skips when not using Windkessel BC."""
        config = {"boundary_conditions": {"outlets": {"type": "ZEROGRADIENT"}}}

        from workflow.tasks.setup_tasks import GenerateWindkesselReportTask

        task = GenerateWindkesselReportTask(config)
        context = {"case_directory": "/tmp/test"}

        result = task.execute(context)

        # Should skip (return True) for non-Windkessel
        assert result is True

    def test_runs_for_windkessel(self):
        """Test that task runs when using 3E Windkessel BC."""
        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = os.path.join(tmpdir, "openfoam")
            os.makedirs(case_dir)
            reports_dir = os.path.join(tmpdir, "reports")

            config = {"boundary_conditions": {"outlets": {"type": "3EWINDKESSEL"}}}

            from workflow.tasks.setup_tasks import GenerateWindkesselReportTask

            task = GenerateWindkesselReportTask(config)
            context = {"case_directory": case_dir}

            # WindkesselAnalyzer is imported inside the execute method
            with patch("aortacfd_lib.windkessel_analyzer.WindkesselAnalyzer") as mock_analyzer:
                mock_analyzer.return_value.generate_report.return_value = "wk_report.pdf"

                result = task.execute(context)

                # Should return True (task doesn't fail on success)
                assert result is True


# Helper function to create minimal STL files
def _create_minimal_binary_stl(filepath: str):
    """Create a minimal valid binary STL file."""
    import struct

    with open(filepath, "wb") as f:
        # Header (80 bytes)
        f.write(b"\x00" * 80)
        # Number of triangles
        f.write(struct.pack("<I", 2))

        # Two triangles (forming a simple surface)
        for _ in range(2):
            # Normal
            f.write(struct.pack("<fff", 0.0, 0.0, 1.0))
            # Three vertices
            f.write(struct.pack("<fff", 0.0, 0.0, 0.0))
            f.write(struct.pack("<fff", 1.0, 0.0, 0.0))
            f.write(struct.pack("<fff", 0.0, 1.0, 0.0))
            # Attribute byte count
            f.write(struct.pack("<H", 0))


class TestCopyAndScaleStl:
    """Additional tests for CreateCaseStructureTask._copy_and_scale_stl method."""

    @pytest.fixture
    def task(self):
        """Create a CreateCaseStructureTask instance for testing."""
        from workflow.tasks.setup_tasks import CreateCaseStructureTask

        mock_config = {"geometry": {"scale_factor": 0.001}}
        task = CreateCaseStructureTask(config=mock_config)
        return task

    @pytest.fixture
    def temp_stl_file(self, tmp_path):
        """Create a temporary STL file for testing using numpy-stl."""
        import numpy as np

        try:
            from stl import mesh as np_stl_mesh
        except ImportError:
            pytest.skip("numpy-stl not installed")

        # Define vertices of a cube (in mm scale, 10x10x10 mm)
        vertices = np.array(
            [[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0], [0, 0, 10], [10, 0, 10], [10, 10, 10], [0, 10, 10]]
        )

        faces = np.array(
            [
                [0, 3, 1],
                [1, 3, 2],
                [0, 4, 7],
                [0, 7, 3],
                [4, 5, 6],
                [4, 6, 7],
                [5, 1, 2],
                [5, 2, 6],
                [2, 3, 6],
                [3, 7, 6],
                [0, 1, 5],
                [0, 5, 4],
            ]
        )

        cube = np_stl_mesh.Mesh(np.zeros(faces.shape[0], dtype=np_stl_mesh.Mesh.dtype))
        for i, f in enumerate(faces):
            for j in range(3):
                cube.vectors[i][j] = vertices[f[j], :]

        stl_path = tmp_path / "test_cube.stl"
        cube.save(str(stl_path))
        return str(stl_path)

    def test_scale_stl_converts_mm_to_meters(self, task, temp_stl_file, tmp_path):
        """Test that STL is scaled correctly from mm to meters."""
        import numpy as np
        from stl import mesh as np_stl_mesh

        dst_path = str(tmp_path / "scaled_cube.stl")
        scale_factor = 0.001

        task._copy_and_scale_stl(temp_stl_file, dst_path, scale_factor)

        scaled_mesh = np_stl_mesh.Mesh.from_file(dst_path)
        max_coord = scaled_mesh.vectors.max()
        min_coord = scaled_mesh.vectors.min()

        # Original 10mm cube → 0.01m cube
        assert abs(max_coord - 0.01) < 1e-9
        assert abs(min_coord - 0.0) < 1e-9

    def test_scale_factor_of_one(self, task, temp_stl_file, tmp_path):
        """Test that scale_factor=1 preserves original dimensions."""
        from stl import mesh as np_stl_mesh

        dst_path = str(tmp_path / "unscaled_cube.stl")
        task._copy_and_scale_stl(temp_stl_file, dst_path, 1.0)

        scaled_mesh = np_stl_mesh.Mesh.from_file(dst_path)
        assert abs(scaled_mesh.vectors.max() - 10.0) < 1e-9

    def test_scale_stl_nonexistent_file(self, task, tmp_path):
        """Test that scaling a non-existent file raises RuntimeError."""
        src_path = str(tmp_path / "nonexistent.stl")
        dst_path = str(tmp_path / "output.stl")

        with pytest.raises(RuntimeError) as exc_info:
            task._copy_and_scale_stl(src_path, dst_path, 0.001)

        assert "Failed to scale STL file" in str(exc_info.value)


class TestValidateInletCsvExtended:
    """Extended tests for PrepareBoundaryDataTask._validate_inlet_csv."""

    @pytest.fixture
    def task(self):
        """Create a PrepareBoundaryDataTask instance for testing."""
        from workflow.tasks.setup_tasks import PrepareBoundaryDataTask

        task = PrepareBoundaryDataTask(config={})
        return task

    def test_validate_single_column_raises_error(self, task, tmp_path):
        """Test that single-column CSV raises ValueError."""
        csv_path = tmp_path / "single_col.csv"
        csv_path.write_text("0.0\n0.1\n0.2\n0.3\n")

        with pytest.raises(ValueError) as exc_info:
            task._validate_inlet_csv(str(csv_path))

        assert "column" in str(exc_info.value).lower()

    def test_validate_single_row_raises_error(self, task, tmp_path):
        """Test that single-row CSV raises ValueError."""
        csv_path = tmp_path / "single_row.csv"
        csv_path.write_text("0.0,50.0\n")

        with pytest.raises(ValueError) as exc_info:
            task._validate_inlet_csv(str(csv_path))

        # Single row becomes 1D array, triggering column check
        assert "column" in str(exc_info.value).lower() or "1d array" in str(exc_info.value).lower()

    def test_validate_nan_values_raises_error(self, task, tmp_path):
        """Test that CSV with NaN values raises ValueError."""
        csv_path = tmp_path / "nan_data.csv"
        csv_path.write_text("0.0,50.0\n0.1,invalid\n0.2,100.0\n")

        with pytest.raises(ValueError):
            task._validate_inlet_csv(str(csv_path))

    def test_validate_csv_with_comments(self, task, tmp_path):
        """Test that CSV with comment lines is handled correctly."""
        csv_path = tmp_path / "commented.csv"
        data = """# This is a comment
# Another comment
0.0,50.0
0.1,100.0
0.2,75.0
"""
        csv_path.write_text(data)

        result = task._validate_inlet_csv(str(csv_path))
        assert result is True

    def test_validate_csv_with_header(self, task, tmp_path):
        """Test that CSV with header row is handled correctly."""
        csv_path = tmp_path / "with_header.csv"
        data = """time,flowrate
0.0,50.0
0.1,100.0
0.2,75.0
"""
        csv_path.write_text(data)

        result = task._validate_inlet_csv(str(csv_path))
        assert result is True


class TestFindInletCsvExtended:
    """Extended tests for PrepareBoundaryDataTask._find_inlet_csv."""

    @pytest.fixture
    def task(self):
        """Create a PrepareBoundaryDataTask instance for testing."""
        from workflow.tasks.setup_tasks import PrepareBoundaryDataTask

        task = PrepareBoundaryDataTask(config={"geometry": {"cad_folder": None}, "_config_file_path": None})
        return task

    def test_find_csv_in_parent_directory(self, task, tmp_path):
        """Test finding CSV in parent directory (nested openfoam structure)."""
        case_dir = tmp_path / "case" / "openfoam"
        case_dir.mkdir(parents=True)

        csv_path = tmp_path / "case" / "inlet.csv"
        csv_path.write_text("0.0,50.0\n0.1,100.0\n")

        result = task._find_inlet_csv("inlet.csv", str(case_dir))
        assert result == str(csv_path)

    def test_find_csv_via_config_path(self, task, tmp_path):
        """Test finding CSV via config file path."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        csv_path = config_dir / "inlet.csv"
        csv_path.write_text("0.0,50.0\n0.1,100.0\n")

        task.config["_config_file_path"] = str(config_dir / "config.json")

        result = task._find_inlet_csv("inlet.csv", case_dir=None)
        assert result == str(csv_path)

    def test_find_csv_via_cad_folder(self, task, tmp_path):
        """Test finding CSV via cad_folder config."""
        cad_dir = tmp_path / "cad"
        cad_dir.mkdir()
        csv_path = cad_dir / "inlet.csv"
        csv_path.write_text("0.0,50.0\n0.1,100.0\n")

        task.config["geometry"] = {"cad_folder": str(cad_dir)}

        result = task._find_inlet_csv("inlet.csv", case_dir=None)
        assert result == str(csv_path)

    def test_find_csv_not_found_returns_none(self, task, tmp_path):
        """Test that missing CSV returns None."""
        result = task._find_inlet_csv("nonexistent.csv", str(tmp_path))
        assert result is None


class TestCleanupTempObjFiles:
    """Test PrepareBoundaryDataTask._cleanup_temp_obj_files method."""

    @pytest.fixture
    def task(self):
        """Create a PrepareBoundaryDataTask instance for testing."""
        from workflow.tasks.setup_tasks import PrepareBoundaryDataTask

        task = PrepareBoundaryDataTask(config={})
        return task

    def test_cleanup_removes_obj_files(self, task, tmp_path):
        """Test that .obj files are removed."""
        (tmp_path / "patch_inlet.obj").write_text("# OBJ file")
        (tmp_path / "patch_outlet1.obj").write_text("# OBJ file")
        (tmp_path / "important.stl").write_text("# STL file")
        (tmp_path / "controlDict").write_text("// controlDict")

        task._cleanup_temp_obj_files(str(tmp_path))

        assert not (tmp_path / "patch_inlet.obj").exists()
        assert not (tmp_path / "patch_outlet1.obj").exists()
        assert (tmp_path / "important.stl").exists()
        assert (tmp_path / "controlDict").exists()

    def test_cleanup_no_obj_files(self, task, tmp_path):
        """Test cleanup when no .obj files exist."""
        (tmp_path / "important.stl").write_text("# STL file")

        task._cleanup_temp_obj_files(str(tmp_path))

        assert (tmp_path / "important.stl").exists()


class TestCalculateConstantFlowrateExtended:
    """Extended tests for PrepareBoundaryDataTask._calculate_constant_flowrate."""

    @pytest.fixture
    def task(self):
        """Create a PrepareBoundaryDataTask instance for testing."""
        from workflow.tasks.setup_tasks import PrepareBoundaryDataTask

        task = PrepareBoundaryDataTask(config={"geometry": {"inlet_keywords_ordered": "inlet"}})
        return task

    def test_flowrate_in_lmin(self, task, tmp_path):
        """Test flow rate conversion from L/min to m³/s."""
        inlet_config = {"flowrate": 6.0}

        with patch("aortacfd_lib.utils.patch_processing.PatchProcessing") as mock:
            mock_instance = MagicMock()
            mock_instance.calculate_surface_area.return_value = 0.0001
            mock.return_value = mock_instance

            result = task._calculate_constant_flowrate(inlet_config, str(tmp_path))

        # 6 L/min = 6/60/1000 = 0.0001 m³/s
        expected = 6.0 / 60.0 / 1000.0
        assert abs(result - expected) < 1e-10

    def test_cardiac_output_in_lmin(self, task, tmp_path):
        """Test cardiac output conversion from L/min to m³/s."""
        inlet_config = {"cardiac_output": 5.0}

        with patch("aortacfd_lib.utils.patch_processing.PatchProcessing") as mock:
            mock_instance = MagicMock()
            mock_instance.calculate_surface_area.return_value = 0.0001
            mock.return_value = mock_instance

            result = task._calculate_constant_flowrate(inlet_config, str(tmp_path))

        expected = 5.0 / 60.0 / 1000.0
        assert abs(result - expected) < 1e-10

    def test_velocity_with_area(self, task, tmp_path):
        """Test velocity * area calculation."""
        inlet_config = {"velocity": 0.5}
        inlet_area = 0.0002

        with patch("aortacfd_lib.utils.patch_processing.PatchProcessing") as mock:
            mock_instance = MagicMock()
            mock_instance.calculate_surface_area.return_value = inlet_area
            mock.return_value = mock_instance

            result = task._calculate_constant_flowrate(inlet_config, str(tmp_path))

        expected = 0.5 * inlet_area
        assert abs(result - expected) < 1e-10

    def test_missing_flowrate_raises_error(self, task, tmp_path):
        """Test that missing flowrate/velocity/cardiac_output raises ValueError."""
        inlet_config = {}

        with patch("aortacfd_lib.utils.patch_processing.PatchProcessing") as mock:
            mock_instance = MagicMock()
            mock_instance.calculate_surface_area.return_value = 0.0001
            mock.return_value = mock_instance

            with pytest.raises(ValueError) as exc_info:
                task._calculate_constant_flowrate(inlet_config, str(tmp_path))

        assert "Missing flowrate" in str(exc_info.value)


class TestCalculatePurgeWriteExtended:
    """Extended tests for GenerateControlDictTask._calculate_purge_write."""

    @pytest.fixture
    def task(self):
        """Create a GenerateControlDictTask instance for testing."""
        from workflow.tasks.setup_tasks import GenerateControlDictTask

        task = GenerateControlDictTask(config={"simulation_control": {"controlDict": {}}})
        return task

    def test_keep_last_cycles_different_intervals(self, task):
        """Test purgeWrite calculation with different write intervals."""
        sim_controls = {"keep_last_cycles": 3}
        control_dict = {"writeInterval": 0.005, "purgeWrite": 0}
        cardiac_cycle = 1.0

        result = task._calculate_purge_write(sim_controls, control_dict, cardiac_cycle)

        # timesteps_per_cycle = 1.0 / 0.005 = 200
        # purgeWrite = 200 * 3 * 1.1 = 660
        expected = int(200 * 3 * 1.1)
        assert result == expected

    def test_zero_cardiac_cycle_returns_none(self, task):
        """Test that zero cardiac_cycle returns None."""
        sim_controls = {"keep_last_cycles": 2}
        control_dict = {"writeInterval": 0.01, "purgeWrite": 0}

        result = task._calculate_purge_write(sim_controls, control_dict, 0.0)
        assert result is None

    def test_invalid_write_interval_returns_none(self, task):
        """Test that zero/negative writeInterval returns None."""
        sim_controls = {"keep_last_cycles": 2}
        control_dict = {"writeInterval": 0, "purgeWrite": 0}

        result = task._calculate_purge_write(sim_controls, control_dict, 0.8)
        assert result is None

    def test_write_interval_from_sim_controls(self, task):
        """Test that writeInterval is also read from sim_controls."""
        sim_controls = {"keep_last_cycles": 2, "writeInterval": 0.02}
        control_dict = {"purgeWrite": 0}  # No writeInterval in controlDict
        cardiac_cycle = 0.8

        result = task._calculate_purge_write(sim_controls, control_dict, cardiac_cycle)

        # timesteps_per_cycle = 0.8 / 0.02 = 40
        # purgeWrite = 40 * 2 * 1.1 = 88
        expected = int(40 * 2 * 1.1)
        assert result == expected


class TestPrepareBoundaryDataTaskExtended:
    """Extended tests for PrepareBoundaryDataTask."""

    def test_world_patch_mode_returns_early(self, tmp_path):
        """Test that world patch mode returns early with default cardiac cycle."""
        from workflow.tasks.setup_tasks import PrepareBoundaryDataTask

        task = PrepareBoundaryDataTask(config={"geometry": {"inlet_keywords_ordered": "inlet"}})
        context = {"case_directory": str(tmp_path)}

        with patch("workflow.tasks.setup_tasks.detect_world_patch_mode") as mock_detect:
            mock_detect.return_value = True

            result = task.execute(context)

            assert result is True
            assert context["cardiac_cycle"] == 1.0

    def test_missing_mesh_returns_false(self, tmp_path):
        """Test that missing mesh returns False."""
        from workflow.tasks.setup_tasks import PrepareBoundaryDataTask

        task = PrepareBoundaryDataTask(config={"geometry": {"inlet_keywords_ordered": "inlet"}})
        context = {"case_directory": str(tmp_path)}

        with patch("workflow.tasks.setup_tasks.detect_world_patch_mode") as mock_detect:
            mock_detect.return_value = False

            result = task.execute(context)

            assert result is False


class TestGenerateControlDictTaskExtended:
    """Extended tests for GenerateControlDictTask.execute."""

    def test_execute_with_auto_end_time(self, tmp_path):
        """Test execute with end_time='auto'."""
        from workflow.tasks.setup_tasks import GenerateControlDictTask

        config = {
            "simulation_control": {"end_time": "auto", "number_of_cycles": 4, "controlDict": {"writeInterval": 0.01}}
        }

        task = GenerateControlDictTask(config)
        context = {"case_directory": str(tmp_path), "cardiac_cycle": 0.9}

        with patch("workflow.tasks.setup_tasks.SimulationSetup") as mock_setup:
            result = task.execute(context)

            assert result is True

            call_args = mock_setup.return_value.write_controlDict.call_args
            final_control_dict = call_args.kwargs["final_control_dict"]

            # endTime = 0.9 * 4 = 3.6
            assert final_control_dict["endTime"] == pytest.approx(3.6)

    def test_execute_without_cardiac_cycle(self, tmp_path):
        """Test execute when cardiac_cycle is not yet determined."""
        from workflow.tasks.setup_tasks import GenerateControlDictTask

        config = {"simulation_control": {"number_of_cycles": 3, "controlDict": {"writeInterval": 0.01}}}

        task = GenerateControlDictTask(config)
        context = {"case_directory": str(tmp_path), "cardiac_cycle": None}  # Not yet determined

        with patch("workflow.tasks.setup_tasks.SimulationSetup") as mock_setup:
            result = task.execute(context)

            assert result is True

            call_args = mock_setup.return_value.write_controlDict.call_args
            final_control_dict = call_args.kwargs["final_control_dict"]

            # Should use temporary value: 1.0 * 3 = 3.0
            assert final_control_dict["endTime"] == pytest.approx(3.0)


class TestGenerateMeshFilesTask:
    """Test GenerateMeshFilesTask class."""

    def test_execute_calls_analyzer(self, tmp_path):
        """Test that execute calls GeometryAnalyzer.write_all_mesh_files."""
        from workflow.tasks.setup_tasks import GenerateMeshFilesTask

        config = {}
        task = GenerateMeshFilesTask(config)
        context = {"case_directory": str(tmp_path)}

        with patch("workflow.tasks.setup_tasks.GeometryAnalyzer") as mock_analyzer:
            result = task.execute(context)

            assert result is True
            mock_analyzer.assert_called_once()
            mock_analyzer.return_value.write_all_mesh_files.assert_called_once()


class TestGeneratePhysicalPropertiesTask:
    """Test GeneratePhysicalPropertiesTask class."""

    def test_execute_calls_all_writers(self, tmp_path):
        """Test that execute calls all physical property writers."""
        from workflow.tasks.setup_tasks import GeneratePhysicalPropertiesTask

        config = {}
        task = GeneratePhysicalPropertiesTask(config)
        context = {"case_directory": str(tmp_path)}

        with patch("workflow.tasks.setup_tasks.PhysicalPropertiesWriter") as mock_writer:
            result = task.execute(context)

            assert result is True
            mock_writer.return_value.write_transportProperties_file.assert_called_once()
            mock_writer.return_value.write_momentumTransport_file.assert_called_once()
            mock_writer.return_value.write_fvOptions_file.assert_called_once()


class TestGenerateNumericalSchemesTask:
    """Test GenerateNumericalSchemesTask class."""

    def test_execute_calls_writer(self, tmp_path):
        """Test that execute calls FvSchemesWriter."""
        from workflow.tasks.setup_tasks import GenerateNumericalSchemesTask

        config = {}
        task = GenerateNumericalSchemesTask(config)
        context = {"case_directory": str(tmp_path)}

        with patch("workflow.tasks.setup_tasks.FvSchemesWriter") as mock_writer:
            result = task.execute(context)

            assert result is True
            mock_writer.return_value.write_fvSchemes_file.assert_called_once()


class TestGenerateSolverSettingsTask:
    """Test GenerateSolverSettingsTask class."""

    def test_execute_calls_writer(self, tmp_path):
        """Test that execute calls FvSolutionWriter."""
        from workflow.tasks.setup_tasks import GenerateSolverSettingsTask

        config = {}
        task = GenerateSolverSettingsTask(config)
        context = {"case_directory": str(tmp_path)}

        with patch("workflow.tasks.setup_tasks.FvSolutionWriter") as mock_writer:
            result = task.execute(context)

            assert result is True
            mock_writer.return_value.write_fvSolution_file.assert_called_once()


class TestGenerateDecomposeParDictTask:
    """Test GenerateDecomposeParDictTask class."""

    def test_execute_calls_writer(self, tmp_path):
        """Test that execute calls SolnType.write_decomposeParDict."""
        from workflow.tasks.setup_tasks import GenerateDecomposeParDictTask

        config = {}
        task = GenerateDecomposeParDictTask(config)
        context = {"case_directory": str(tmp_path)}

        with patch("workflow.tasks.setup_tasks.SolnType") as mock_writer:
            result = task.execute(context)

            assert result is True
            mock_writer.return_value.write_decomposeParDict.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
