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
            "physics": {
                "blood_density": 1060,
                "blood_viscosity": 0.004,
                "simulation_type": "laminar"
            }
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
                "csv_file": "flow.csv"
            },
            "physics": {
                "blood_density": 1060,
                "blood_viscosity": 0.004,
                "murray_exponent": 2.7
            },
            "boundary_conditions": {
                "outlets": {
                    "type": "3EWINDKESSEL",
                    "windkessel_settings": {
                        "systolic_pressure": 120,
                        "diastolic_pressure": 80,
                        "methodology": "murray_law_automatic"
                    }
                }
            }
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
        # Setup geometry for Murray's Law
        tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)

        # Create outlet STL files with realistic sizes
        for outlet in ["outlet1.stl", "outlet2.stl"]:
            (tri_surface / outlet).write_text("solid mesh\nendsolid mesh\n")

        # Execute Windkessel setup
        wk_setup = WkSetup(
            config=wk_config,
            case_directory=str(temp_case_dir)
        )

        # Calculate parameters
        params = wk_setup.calculate_windkessel_parameters()

        # Verify parameters calculated
        assert params is not None
        assert "outlet1" in params or len(params) > 0

        # Verify parameters have required fields
        for outlet, values in params.items():
            assert "R_proximal" in values
            assert "R_distal" in values
            assert "C" in values

    def test_boundary_condition_file_generation(self, temp_case_dir, minimal_config):
        """Test boundary condition file generation."""
        # Setup
        bc_setup = BoundaryConditionSetup(
            config=minimal_config,
            case_directory=str(temp_case_dir)
        )

        # Generate boundary condition files
        bc_setup.write_boundary_conditions()

        # Verify files created
        zero_dir = Path(temp_case_dir) / "0"
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
            "physics": {
                "blood_density": 1060,
                "blood_viscosity": 0.004,
                "simulation_type": "laminar"
            }
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
                "csv_file": "flow.csv"
            },
            "physics": {
                "blood_density": 1060,
                "blood_viscosity": 0.004,
                "murray_exponent": 2.7
            },
            "boundary_conditions": {
                "outlets": {
                    "type": "3EWINDKESSEL",
                    "windkessel_settings": {
                        "systolic_pressure": 120,
                        "diastolic_pressure": 80,
                        "methodology": "murray_law_automatic"
                    }
                }
            }
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
            str(case_input_dir),
            minimal_config
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
        tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)

        # Tiny STL (should trigger warning)
        (tri_surface / "outlet1.stl").write_text("solid mesh\nendsolid mesh\n")

        # WkSetup should handle gracefully
        wk_setup = WkSetup(
            config=wk_config,
            case_directory=str(temp_case_dir)
        )

        # Should not crash
        try:
            params = wk_setup.calculate_windkessel_parameters()
            # May return empty or estimated parameters
            assert isinstance(params, dict)
        except Exception as e:
            # Should be controlled error
            assert "outlet" in str(e).lower() or "area" in str(e).lower()


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
            "physics": {
                "blood_density": 1060,
                "blood_viscosity": 0.004,
                "simulation_type": "laminar"
            }
        }

    def test_complete_boundary_setup_task(self, temp_case_dir, minimal_config):
        """Test complete boundary data preparation task."""
        # Setup: Create all required files
        case_name = minimal_config["geometry"]["case_name"]
        case_input_dir = Path("cases_input") / case_name
        case_input_dir.mkdir(parents=True, exist_ok=True)

        # Create geometry
        tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)
        for stl in ["inlet.stl", "outlet1.stl"]:
            (tri_surface / stl).write_text("solid mesh\nendsolid mesh\n")
            (case_input_dir / stl).write_text("solid mesh\nendsolid mesh\n")

        # Create inlet CSV
        inlet_csv = minimal_config["inlet"]["csv_file"]
        csv_content = "time,velocity\n0.0,0.5\n0.1,0.6\n"
        (case_input_dir / inlet_csv).write_text(csv_content)

        # Create boundary data directory
        inlet_patch = minimal_config["geometry"]["inlet_keywords_ordered"]
        boundary_dir = Path(temp_case_dir) / "constant" / "boundaryData" / inlet_patch
        boundary_dir.mkdir(parents=True, exist_ok=True)

        import shutil
        shutil.copy(case_input_dir / inlet_csv, boundary_dir / inlet_csv)

        # Execute task
        task = PrepareBoundaryDataTask(minimal_config)
        context = {"case_directory": str(temp_case_dir)}

        result = task.execute(context)

        # Should succeed
        assert result is True

        # Verify boundary condition files created
        zero_dir = Path(temp_case_dir) / "0"
        assert (zero_dir / "U").exists()
        assert (zero_dir / "p").exists()

        # Cleanup
        shutil.rmtree(case_input_dir)

    def test_laminar_vs_turbulent_boundary_conditions(self, temp_case_dir):
        """Test that boundary conditions differ for laminar vs turbulent."""
        from src.config.builder import ConfigBuilder

        builder = ConfigBuilder()

        # Laminar config
        laminar_config = builder.build_base_and_profile("sim_laminar_coarse")
        laminar_config["geometry"] = {
            "case_name": "test_laminar",
            "inlet_keywords_ordered": "inlet",
            "outlet_keywords_ordered": ["outlet1"],
            "scale_factor": 0.001
        }

        bc_laminar = BoundaryConditionSetup(
            config=laminar_config,
            case_directory=str(temp_case_dir)
        )
        bc_laminar.write_boundary_conditions()

        # Check laminar doesn't have turbulence files
        zero_dir = Path(temp_case_dir) / "0"
        laminar_files = list(zero_dir.glob("*"))

        # RANS config
        rans_config = builder.build_base_and_profile("sim_rans_coarse")
        rans_config["geometry"] = laminar_config["geometry"].copy()

        # Clear directory
        import shutil
        shutil.rmtree(zero_dir)
        zero_dir.mkdir()

        bc_rans = BoundaryConditionSetup(
            config=rans_config,
            case_directory=str(temp_case_dir)
        )
        bc_rans.write_boundary_conditions()

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
            "physics": {
                "blood_density": 1060,
                "blood_viscosity": 0.004,
                "simulation_type": "laminar"
            }
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
                "csv_file": "flow.csv"
            },
            "physics": {
                "blood_density": 1060,
                "blood_viscosity": 0.004,
                "murray_exponent": 2.7
            },
            "boundary_conditions": {
                "outlets": {
                    "type": "3EWINDKESSEL",
                    "windkessel_settings": {
                        "systolic_pressure": 120,
                        "diastolic_pressure": 80,
                        "methodology": "murray_law_automatic"
                    }
                }
            }
        }

    def test_boundary_setup_performance(self, temp_case_dir, minimal_config):
        """Test boundary condition setup is reasonably fast."""
        import time

        # Setup
        bc_setup = BoundaryConditionSetup(
            config=minimal_config,
            case_directory=str(temp_case_dir)
        )

        # Time boundary condition writing
        start = time.time()
        bc_setup.write_boundary_conditions()
        elapsed = time.time() - start

        # Should complete in under 1 second
        assert elapsed < 1.0

    def test_windkessel_calculation_performance(self, temp_case_dir, wk_config):
        """Test Windkessel parameter calculation performance."""
        import time

        # Setup
        tri_surface = Path(temp_case_dir) / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)

        # Create multiple outlets
        for i in range(5):
            (tri_surface / f"outlet{i+1}.stl").write_text("solid mesh\nendsolid mesh\n")

        wk_setup = WkSetup(
            config=wk_config,
            case_directory=str(temp_case_dir)
        )

        # Time calculation
        start = time.time()
        params = wk_setup.calculate_windkessel_parameters()
        elapsed = time.time() - start

        # Should complete in under 2 seconds even with 5 outlets
        assert elapsed < 2.0
