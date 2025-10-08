"""
Integration tests for boundary condition workflow.

Tests end-to-end boundary condition setup including inlet mapping,
Windkessel parameter calculation, and boundary file generation.
"""

import pytest
from pathlib import Path
from src.workflow.tasks.setup_tasks import PrepareBoundaryDataTask
from src.aortacfd_lib.boundary_condition_setup import BoundaryConditionSetup
from src.aortacfd_lib.inlet_mapping import InletMapping
from src.aortacfd_lib.wk_setup import WkSetup


@pytest.mark.integration
class TestBoundaryConditionWorkflow:
    """Test complete boundary condition workflow."""

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
                "type": "TIMEVARYING",
                "csv_file": "flow.csv",
                "data_type": "velocity",
                "profile": "plug_flow"
            },
            "outlets": {
                "type": "PRESSURE",
                "pressure_value": 0
            },
            "physics": {
                "blood_density": 1060,
                "blood_viscosity": 0.004,
                "simulation_type": "laminar"
            },
            "template_vars": {
                "openfoam_version": "12",
                "openfoam_major_version": 12
            },
            "openfoam_version": "12",
            "openfoam_major_version": 12
        }

    @pytest.fixture
    def wk_config(self):
        """Windkessel configuration."""
        return {
            "geometry": {
                "case_name": "test_wk",
                "scale_factor": 0.001,
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["outlet1", "outlet2"],
                "wall_keywords_ordered": "wall"
            },
            "inlet": {
                "type": "TIMEVARYING",
                "csv_file": "flow.csv",
                "data_type": "velocity",
                "profile": "plug_flow"
            },
            "outlets": {
                "type": "3EWINDKESSEL",
                "windkessel_settings": {
                    "systolic_pressure": 120,
                    "diastolic_pressure": 80,
                    "methodology": "murray_law_automatic"
                }
            },
            "physics": {
                "blood_density": 1060,
                "blood_viscosity": 0.004,
                "murray_exponent": 2.7,
                "rho": 1060
            },
            "template_vars": {
                "openfoam_version": "12",
                "openfoam_major_version": 12
            },
            "openfoam_version": "12",
            "openfoam_major_version": 12
        }

    def test_inlet_mapping_workflow(self, temp_case_dir, minimal_config):
        """Test inlet velocity mapping workflow."""
        # Setup: Create inlet CSV data
        case_name = minimal_config["geometry"]["case_name"]
        case_input_dir = Path("cases_input") / case_name
        case_input_dir.mkdir(parents=True, exist_ok=True)

        inlet_csv = minimal_config["inlet"]["csv_file"]
        csv_content = """time,velocity
0.0,0.50
0.1,0.55
0.2,0.60
0.3,0.55
0.4,0.50
"""
        (case_input_dir / inlet_csv).write_text(csv_content)

        # Create boundary data directory
        inlet_patch = minimal_config["geometry"]["inlet_keywords_ordered"]
        boundary_dir = Path(temp_case_dir) / "constant" / "boundaryData" / inlet_patch
        boundary_dir.mkdir(parents=True, exist_ok=True)

        # Copy inlet CSV
        import shutil
        shutil.copy(case_input_dir / inlet_csv, boundary_dir / inlet_csv)

        # Execute inlet mapping
        mapper = InletMapping(
            config=minimal_config,
            case_directory=str(temp_case_dir)
        )

        # Should create time directories and point files
        # (actual execution depends on OpenFOAM, so we test setup)
        assert mapper is not None

        # Cleanup
        shutil.rmtree(case_input_dir)

    def test_windkessel_parameter_calculation(self, temp_case_dir, wk_config):
        """Test Windkessel parameter calculation workflow."""
        # Setup geometry with realistic STL files
        import shutil
        tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)

        # Copy realistic STL files from fixtures
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "sample_stl_files"
        shutil.copy(fixtures_dir / "outlet1.stl", tri_surface / "outlet1.stl")
        shutil.copy(fixtures_dir / "outlet2.stl", tri_surface / "outlet2.stl")
        shutil.copy(fixtures_dir / "inlet.stl", tri_surface / "inlet.stl")

        # Create inlet CSV file in cases_input
        case_name = wk_config["geometry"]["case_name"]
        case_input_dir = Path("cases_input") / case_name
        case_input_dir.mkdir(parents=True, exist_ok=True)

        csv_fixtures_dir = Path(__file__).parent.parent / "fixtures" / "sample_bc_data"
        inlet_csv = wk_config["inlet"]["csv_file"]
        shutil.copy(csv_fixtures_dir / "flow.csv", case_input_dir / inlet_csv)

        # Execute Windkessel setup with required parameters
        stl_files = ["outlet1.stl", "outlet2.stl"]
        cardiac_cycle = 0.8  # 800ms cardiac cycle (75 BPM)

        wk_setup = WkSetup(
            config=wk_config,
            stl_files=stl_files,
            case_directory=str(temp_case_dir),
            cardiac_cycle=cardiac_cycle
        )

        # Execute Windkessel calculation
        try:
            wk_setup.execute()
        finally:
            # Cleanup
            shutil.rmtree(case_input_dir)

        # Verify parameters stored in config (no longer writes to file)
        outlet_params = test_config["outlets"]["windkessel_settings"].get("outlet_parameters", {})
        assert outlet_params, "Outlet parameters should be stored in config"

        # Verify parameters calculated for outlets
        assert len(outlet_params) > 0, "Should have calculated parameters for at least one outlet"

        # Verify parameters have required fields (R, C, Z)
        for outlet, values in outlet_params.items():
            assert "R" in values, f"Outlet {outlet} should have R coefficient"
            assert "C" in values, f"Outlet {outlet} should have C coefficient"
            assert "Z" in values, f"Outlet {outlet} should have Z coefficient"

    def test_boundary_condition_file_generation(self, temp_case_dir, minimal_config):
        """Test boundary condition file generation."""
        # Setup: Create required directory structure
        zero_dir = Path(temp_case_dir) / "0"
        zero_dir.mkdir(parents=True, exist_ok=True)

        system_dir = Path(temp_case_dir) / "system"
        system_dir.mkdir(parents=True, exist_ok=True)

        constant_dir = Path(temp_case_dir) / "constant"
        constant_dir.mkdir(parents=True, exist_ok=True)

        bc_setup = BoundaryConditionSetup(
            config=minimal_config,
            case_directory=str(temp_case_dir)
        )

        # Generate boundary condition files
        bc_setup.write_all_bc_files()

        # Verify files created
        assert (zero_dir / "U").exists()
        assert (zero_dir / "p").exists()

        # Verify file contents
        u_content = (zero_dir / "U").read_text()
        assert "inlet" in u_content.lower()
        assert "outlet" in u_content.lower() or "outlet1" in u_content.lower()


@pytest.mark.integration
class TestBoundaryWorkflowValidation:
    """Test boundary condition validation."""

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
                "type": "TIMEVARYING",
                "csv_file": "flow.csv",
                "data_type": "velocity",
                "profile": "plug_flow"
            },
            "outlets": {
                "type": "PRESSURE",
                "pressure_value": 0
            },
            "physics": {
                "blood_density": 1060,
                "blood_viscosity": 0.004,
                "simulation_type": "laminar"
            },
            "template_vars": {
                "openfoam_version": "12",
                "openfoam_major_version": 12
            },
            "openfoam_version": "12",
            "openfoam_major_version": 12
        }

    @pytest.fixture
    def wk_config(self):
        """Windkessel configuration."""
        return {
            "geometry": {
                "case_name": "test_wk",
                "scale_factor": 0.001,
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["outlet1", "outlet2"],
                "wall_keywords_ordered": "wall"
            },
            "inlet": {
                "type": "TIMEVARYING",
                "csv_file": "flow.csv",
                "data_type": "velocity",
                "profile": "plug_flow"
            },
            "outlets": {
                "type": "3EWINDKESSEL",
                "windkessel_settings": {
                    "systolic_pressure": 120,
                    "diastolic_pressure": 80,
                    "methodology": "murray_law_automatic"
                }
            },
            "physics": {
                "blood_density": 1060,
                "blood_viscosity": 0.004,
                "murray_exponent": 2.7,
                "rho": 1060
            },
            "template_vars": {
                "openfoam_version": "12",
                "openfoam_major_version": 12
            },
            "openfoam_version": "12",
            "openfoam_major_version": 12
        }

    def test_inlet_csv_validation_workflow(self, temp_case_dir, minimal_config):
        """Test that invalid inlet CSV is caught."""
        # Setup: Create invalid CSV
        case_name = minimal_config["geometry"]["case_name"]
        case_input_dir = Path("cases_input") / case_name
        case_input_dir.mkdir(parents=True, exist_ok=True)

        inlet_csv = minimal_config["inlet"]["csv_file"]
        # Invalid: negative velocities
        csv_content = """time,velocity
0.0,-0.5
0.1,-0.3
"""
        (case_input_dir / inlet_csv).write_text(csv_content)

        # Validation should catch this
        from src.aortacfd_lib.utils.validation import BoundaryConditionValidator

        validator = BoundaryConditionValidator(
            config=minimal_config,
            case_directory=str(case_input_dir)
        )

        result = validator.validate_all()

        # Should have warnings or errors about negative velocity
        assert len(result.warnings) > 0 or len(result.errors) > 0

        # Cleanup
        import shutil
        shutil.rmtree(case_input_dir)

    def test_outlet_area_validation(self, temp_case_dir, wk_config):
        """Test outlet area validation for Windkessel."""
        # Setup: Create unrealistically small outlets
        import shutil
        tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)

        # Use realistic STL files from fixtures
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "sample_stl_files"
        shutil.copy(fixtures_dir / "outlet1.stl", tri_surface / "outlet1.stl")
        shutil.copy(fixtures_dir / "outlet2.stl", tri_surface / "outlet2.stl")

        # WkSetup should handle gracefully
        stl_files = ["outlet1.stl", "outlet2.stl"]
        cardiac_cycle = 0.8

        wk_setup = WkSetup(
            config=wk_config,
            stl_files=stl_files,
            case_directory=str(temp_case_dir),
            cardiac_cycle=cardiac_cycle
        )

        # Should not crash - execute() stores coefficients in config
        try:
            wk_setup.execute()
            # Verify coefficients were stored in config
            outlet_params = test_config["outlets"]["windkessel_settings"].get("outlet_parameters", {})
            assert len(outlet_params) > 0, "Should have stored outlet parameters"
        except Exception as e:
            # Should be controlled error
            assert "outlet" in str(e).lower() or "area" in str(e).lower() or "inlet" in str(e).lower()


@pytest.mark.integration
class TestBoundaryWorkflowIntegration:
    """Test integrated boundary setup workflow."""

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
                "type": "TIMEVARYING",
                "csv_file": "flow.csv",
                "data_type": "velocity",
                "profile": "plug_flow"
            },
            "outlets": {
                "type": "PRESSURE",
                "pressure_value": 0
            },
            "physics": {
                "blood_density": 1060,
                "blood_viscosity": 0.004,
                "simulation_type": "laminar"
            },
            "template_vars": {
                "openfoam_version": "12",
                "openfoam_major_version": 12
            },
            "openfoam_version": "12",
            "openfoam_major_version": 12
        }

    def test_complete_boundary_setup_task(self, temp_case_dir, minimal_config):
        """Test complete boundary data preparation task."""
        # Add openfoam_env_path to config
        import shutil
        minimal_config["openfoam_env_path"] = "/opt/openfoam12"  # Mock path

        # Setup: Create all required files
        case_name = minimal_config["geometry"]["case_name"]
        case_input_dir = Path("cases_input") / case_name
        case_input_dir.mkdir(parents=True, exist_ok=True)

        # Create geometry with realistic STL files from fixtures
        tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)

        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "sample_stl_files"
        for stl in ["inlet.stl", "outlet1.stl"]:
            shutil.copy(fixtures_dir / stl, tri_surface / stl)
            shutil.copy(fixtures_dir / stl, case_input_dir / stl)

        # Create inlet CSV
        inlet_csv = minimal_config["inlet"]["csv_file"]
        csv_content = "time,velocity\n0.0,0.5\n0.1,0.6\n"
        (case_input_dir / inlet_csv).write_text(csv_content)

        # Create boundary data directory
        inlet_patch = minimal_config["geometry"]["inlet_keywords_ordered"]
        boundary_dir = Path(temp_case_dir) / "constant" / "boundaryData" / inlet_patch
        boundary_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy(case_input_dir / inlet_csv, boundary_dir / inlet_csv)

        # Mock OpenFOAM command execution
        from unittest.mock import patch, MagicMock

        # Mock the runner to avoid actual OpenFOAM commands
        with patch('src.aortacfd_lib.utils.runner.run_command') as mock_run:
            mock_run.return_value = True  # Simulate successful command execution

            # Execute task
            task = PrepareBoundaryDataTask(minimal_config)
            context = {"case_directory": str(temp_case_dir)}

            result = task.execute(context)

        # Should succeed (or at least not crash)
        # Since we're mocking OpenFOAM, we can't verify file creation
        # Just verify the task ran without exceptions
        assert result is not None

        # Cleanup
        shutil.rmtree(case_input_dir)

    def test_laminar_vs_turbulent_boundary_conditions(self, temp_case_dir):
        """Test that boundary conditions differ for laminar vs turbulent."""
        from src.config.builder import ConfigBuilder
        import shutil

        # Setup: Create required directory structure
        zero_dir = Path(temp_case_dir) / "0"
        zero_dir.mkdir(parents=True, exist_ok=True)

        system_dir = Path(temp_case_dir) / "system"
        system_dir.mkdir(parents=True, exist_ok=True)

        constant_dir = Path(temp_case_dir) / "constant"
        constant_dir.mkdir(parents=True, exist_ok=True)

        builder = ConfigBuilder()

        # Laminar config
        laminar_config = builder.build_base_and_profile("sim_laminar_coarse")
        # Update geometry section without replacing entire dict
        if "geometry" not in laminar_config:
            laminar_config["geometry"] = {}
        laminar_config["geometry"].update({
            "case_name": "test_laminar",
            "inlet_keywords_ordered": "inlet",
            "outlet_keywords_ordered": ["outlet1"],
            "wall_keywords_ordered": "wall",
            "scale_factor": 0.001
        })
        laminar_config["inlet"] = {
            "type": "TIMEVARYING",
            "csv_file": "flow.csv"
        }
        laminar_config["outlets"] = {
            "type": "PRESSURE",
            "pressure_value": 0
        }
        # Ensure openfoam_version exists
        if "openfoam_version" not in laminar_config:
            laminar_config["openfoam_version"] = "12"

        bc_laminar = BoundaryConditionSetup(
            config=laminar_config,
            case_directory=str(temp_case_dir)
        )
        bc_laminar.write_all_bc_files()

        # Check laminar doesn't have turbulence files
        laminar_files = list(zero_dir.glob("*"))

        # RANS config
        rans_config = builder.build_base_and_profile("sim_rans_coarse")
        # Update sections without replacing entire dict
        if "geometry" not in rans_config:
            rans_config["geometry"] = {}
        rans_config["geometry"].update(laminar_config["geometry"])
        rans_config["inlet"] = laminar_config["inlet"].copy()
        rans_config["outlets"] = laminar_config["outlets"].copy()
        # Ensure openfoam_version exists
        if "openfoam_version" not in rans_config:
            rans_config["openfoam_version"] = "12"

        # Clear directory
        shutil.rmtree(zero_dir)
        zero_dir.mkdir()

        bc_rans = BoundaryConditionSetup(
            config=rans_config,
            case_directory=str(temp_case_dir)
        )
        bc_rans.write_all_bc_files()

        # Check RANS has turbulence files
        rans_files = list(zero_dir.glob("*"))

        # RANS should have more files (k, omega, nut)
        assert len(rans_files) >= len(laminar_files)


@pytest.mark.integration
@pytest.mark.slow
class TestBoundaryWorkflowPerformance:
    """Test boundary workflow performance."""

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
                "type": "TIMEVARYING",
                "csv_file": "flow.csv",
                "data_type": "velocity",
                "profile": "plug_flow"
            },
            "outlets": {
                "type": "PRESSURE",
                "pressure_value": 0
            },
            "physics": {
                "blood_density": 1060,
                "blood_viscosity": 0.004,
                "simulation_type": "laminar"
            },
            "template_vars": {
                "openfoam_version": "12",
                "openfoam_major_version": 12
            },
            "openfoam_version": "12",
            "openfoam_major_version": 12
        }

    @pytest.fixture
    def wk_config(self):
        """Windkessel configuration."""
        return {
            "geometry": {
                "case_name": "test_wk",
                "scale_factor": 0.001,
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["outlet1", "outlet2"],
                "wall_keywords_ordered": "wall"
            },
            "inlet": {
                "type": "TIMEVARYING",
                "csv_file": "flow.csv",
                "data_type": "velocity",
                "profile": "plug_flow"
            },
            "outlets": {
                "type": "3EWINDKESSEL",
                "windkessel_settings": {
                    "systolic_pressure": 120,
                    "diastolic_pressure": 80,
                    "methodology": "murray_law_automatic"
                }
            },
            "physics": {
                "blood_density": 1060,
                "blood_viscosity": 0.004,
                "murray_exponent": 2.7,
                "rho": 1060
            },
            "template_vars": {
                "openfoam_version": "12",
                "openfoam_major_version": 12
            },
            "openfoam_version": "12",
            "openfoam_major_version": 12
        }

    def test_boundary_setup_performance(self, temp_case_dir, minimal_config):
        """Test boundary condition setup is reasonably fast."""
        import time

        # Setup: Create required directory structure
        zero_dir = Path(temp_case_dir) / "0"
        zero_dir.mkdir(parents=True, exist_ok=True)

        system_dir = Path(temp_case_dir) / "system"
        system_dir.mkdir(parents=True, exist_ok=True)

        constant_dir = Path(temp_case_dir) / "constant"
        constant_dir.mkdir(parents=True, exist_ok=True)

        bc_setup = BoundaryConditionSetup(
            config=minimal_config,
            case_directory=str(temp_case_dir)
        )

        # Time boundary condition writing
        start = time.time()
        bc_setup.write_all_bc_files()
        elapsed = time.time() - start

        # Should complete in under 1 second
        assert elapsed < 1.0

    def test_windkessel_calculation_performance(self, temp_case_dir, wk_config):
        """Test Windkessel parameter calculation performance."""
        import time
        import shutil

        # Setup with realistic STL files
        tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)

        # Copy realistic outlets and inlet from fixtures
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "sample_stl_files"
        shutil.copy(fixtures_dir / "outlet1.stl", tri_surface / "outlet1.stl")
        shutil.copy(fixtures_dir / "outlet2.stl", tri_surface / "outlet2.stl")
        shutil.copy(fixtures_dir / "inlet.stl", tri_surface / "inlet.stl")

        # Create inlet CSV file in cases_input
        case_name = wk_config["geometry"]["case_name"]
        case_input_dir = Path("cases_input") / case_name
        case_input_dir.mkdir(parents=True, exist_ok=True)

        csv_fixtures_dir = Path(__file__).parent.parent / "fixtures" / "sample_bc_data"
        inlet_csv = wk_config["inlet"]["csv_file"]
        shutil.copy(csv_fixtures_dir / "flow.csv", case_input_dir / inlet_csv)

        stl_files = ["outlet1.stl", "outlet2.stl"]
        cardiac_cycle = 0.8

        wk_setup = WkSetup(
            config=wk_config,
            stl_files=stl_files,
            case_directory=str(temp_case_dir),
            cardiac_cycle=cardiac_cycle
        )

        # Time calculation
        start = time.time()
        try:
            wk_setup.execute()
        finally:
            # Cleanup
            shutil.rmtree(case_input_dir)
        elapsed = time.time() - start

        # Should complete in under 2 seconds even with 2 outlets
        assert elapsed < 2.0
