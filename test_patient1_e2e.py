#!/usr/bin/env python3
"""
End-to-end test for patient1 simulation workflow.
Tests the complete CFD pipeline step by step.
"""

import pytest
import sys
from pathlib import Path
import shutil
import tempfile

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from config.builder import ConfigBuilder
from workflow.tasks.setup_tasks import (
    CreateCaseStructureTask,
    GenerateMeshFilesTask,
    PrepareBoundaryDataTask
)
from aortacfd_lib.mesh_setup import GeometryAnalyzer
from aortacfd_lib.wk_setup import WkSetup
from aortacfd_lib.murray_calculator import MurrayCalculator
from aortacfd_lib.inlet_mapping import InletMapping


class TestPatient1EndToEnd:
    """End-to-end workflow test for patient1."""

    def setup_method(self):
        """Setup test environment."""
        self.patient_name = "patient1"
        self.patient_dir = Path("cases_input") / self.patient_name
        self.test_output_dir = Path(tempfile.mkdtemp(prefix="patient1_e2e_"))

    def teardown_method(self):
        """Cleanup test environment."""
        if self.test_output_dir.exists():
            shutil.rmtree(self.test_output_dir)

    def test_patient1_config_loading(self):
        """Test that patient1 config can be loaded and validated."""
        import json

        config_path = self.patient_dir / "config.json"
        assert config_path.exists(), f"Config file not found: {config_path}"

        with open(config_path) as f:
            config = json.load(f)

        # Validate required sections
        assert "case_info" in config
        assert "simulation_settings" in config
        assert "physics" in config
        assert "geometry" in config
        assert "boundary_conditions" in config

        print(f"✅ Patient1 config loaded successfully")
        print(f"   Patient ID: {config['case_info']['patient_id']}")
        print(f"   Analysis type: {config['simulation_settings']['analysis_type']}")

    def test_patient1_geometry_files_exist(self):
        """Test that all geometry files exist."""
        required_files = [
            "inlet.stl",
            "outlet1.stl",
            "outlet2.stl",
            "outlet3.stl",
            "outlet4.stl",
            "wall_aorta.stl",
            "test_cardio_profile.csv"
        ]

        for filename in required_files:
            filepath = self.patient_dir / filename
            assert filepath.exists(), f"Missing file: {filepath}"
            assert filepath.stat().st_size > 0, f"Empty file: {filepath}"

        print(f"✅ All patient1 geometry files exist")

    def test_patient1_case_structure_creation(self):
        """Test creating case directory structure."""
        # Build full config using ConfigBuilder
        builder = ConfigBuilder()
        full_config = builder.build(case_name=self.patient_name, sim_profile_name="sim_les_medium")

        # Create case structure
        task = CreateCaseStructureTask(full_config)
        context = {"case_directory": str(self.test_output_dir)}

        result = task.execute(context)

        # Verify structure created
        assert (self.test_output_dir / "system").exists()
        assert (self.test_output_dir / "constant").exists()
        assert (self.test_output_dir / "0").exists()
        assert (self.test_output_dir / "constant" / "triSurface").exists()

        print(f"✅ Patient1 case structure created at: {self.test_output_dir}")

    def test_patient1_geometry_analysis(self):
        """Test geometry analysis for patient1."""
        # Build full config
        builder = ConfigBuilder()
        full_config = builder.build(case_name=self.patient_name, sim_profile_name="sim_les_medium")

        # Create case and copy geometry
        (self.test_output_dir / "constant" / "triSurface").mkdir(parents=True, exist_ok=True)

        for stl_file in self.patient_dir.glob("*.stl"):
            shutil.copy(stl_file, self.test_output_dir / "constant" / "triSurface" / stl_file.name)

        # Analyze geometry
        analyzer = GeometryAnalyzer(
            config=full_config,
            case_directory=str(self.test_output_dir)
        )

        # Verify analysis results
        assert analyzer.inlet_radius > 0, "Inlet radius should be positive"
        assert analyzer.reference_radius_mm > 0, "Reference radius should be positive"

        print(f"✅ Patient1 geometry analyzed:")
        print(f"   Inlet radius: {analyzer.inlet_radius*1000:.2f} mm")
        print(f"   Reference radius: {analyzer.reference_radius_mm:.2f} mm")

    def test_patient1_mesh_generation_files(self):
        """Test mesh file generation for patient1."""
        from src.workflow.tasks.setup_tasks import GenerateMeshFilesTask
        from src.config.builder import ConfigBuilder

        # Build full config
        builder = ConfigBuilder()
        full_config = builder.build(case_name=self.patient_name, sim_profile_name="sim_les_medium")

        # Create case structure first
        case_dir = self.test_output_dir / "mesh_test"
        case_dir.mkdir(parents=True, exist_ok=True)

        # Copy geometry files
        tri_surface = case_dir / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)

        for stl_file in self.patient_dir.glob("*.stl"):
            shutil.copy(stl_file, tri_surface / stl_file.name)

        # Create system directory for output files
        system_dir = case_dir / "system"
        system_dir.mkdir(parents=True, exist_ok=True)

        # Generate mesh files
        task = GenerateMeshFilesTask(full_config)
        context = {"case_directory": str(case_dir)}

        result = task.execute(context)

        # Verify mesh files were generated
        assert result == True, "Mesh file generation should succeed"
        assert (system_dir / "blockMeshDict").exists(), "blockMeshDict should be created"
        assert (system_dir / "snappyHexMeshDict").exists(), "snappyHexMeshDict should be created"
        assert (system_dir / "surfaceFeaturesDict").exists(), "surfaceFeaturesDict should be created"

        print(f"✅ Patient1 mesh files generated:")
        print(f"   blockMeshDict: {(system_dir / 'blockMeshDict').stat().st_size} bytes")
        print(f"   snappyHexMeshDict: {(system_dir / 'snappyHexMeshDict').stat().st_size} bytes")
        print(f"   surfaceFeaturesDict: {(system_dir / 'surfaceFeaturesDict').stat().st_size} bytes")

    def test_patient1_boundary_setup_workflow(self):
        """Test boundary condition setup for patient1."""
        from src.workflow.tasks.setup_tasks import PrepareBoundaryDataTask
        from src.config.builder import ConfigBuilder
        from unittest.mock import patch

        # Build full config
        builder = ConfigBuilder()
        full_config = builder.build(case_name=self.patient_name, sim_profile_name="sim_les_medium")

        # Create case structure
        case_dir = self.test_output_dir / "boundary_test"
        case_dir.mkdir(parents=True, exist_ok=True)

        # Create required directories
        (case_dir / "constant" / "triSurface").mkdir(parents=True, exist_ok=True)
        (case_dir / "constant" / "boundaryData" / "inlet").mkdir(parents=True, exist_ok=True)
        (case_dir / "system").mkdir(parents=True, exist_ok=True)
        (case_dir / "0").mkdir(parents=True, exist_ok=True)

        # Copy geometry files
        for stl_file in self.patient_dir.glob("*.stl"):
            shutil.copy(stl_file, case_dir / "constant" / "triSurface" / stl_file.name)

        # Copy inlet CSV file
        inlet_csv = self.patient_dir / "test_cardio_profile.csv"
        if inlet_csv.exists():
            shutil.copy(inlet_csv, case_dir / "constant" / "boundaryData" / "inlet" / "test_cardio_profile.csv")

        # Prepare boundary data task
        task = PrepareBoundaryDataTask(full_config)
        context = {"case_directory": str(case_dir)}

        # Mock OpenFOAM commands that might be called
        with patch('src.aortacfd_lib.utils.runner.run_command') as mock_run:
            mock_run.return_value = True

            # This may fail if it requires actual OpenFOAM execution
            # We're mainly testing that it can initialize and attempt setup
            try:
                result = task.execute(context)
                print(f"✅ Patient1 boundary setup completed successfully")
            except Exception as e:
                # If it fails due to OpenFOAM not being available, that's expected
                error_msg = str(e)
                if "writeMeshObj" in error_msg or "checkMesh" in error_msg or "OpenFOAM" in error_msg:
                    print(f"⚠️  Patient1 boundary setup requires OpenFOAM (expected in CI): {error_msg}")
                    pytest.skip("OpenFOAM not available - skipping boundary setup test")
                else:
                    raise

    def test_patient1_murray_flow_distribution(self):
        """Test Murray's Law flow distribution with real patient1 geometry."""
        # Build full config
        builder = ConfigBuilder()
        full_config = builder.build(case_name=self.patient_name, sim_profile_name="sim_les_medium")

        # Create case structure and copy geometry
        case_dir = self.test_output_dir / "murray_test"
        tri_surface = case_dir / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)

        # Copy all STL files
        for stl_file in self.patient_dir.glob("*.stl"):
            shutil.copy(stl_file, tri_surface / stl_file.name)

        # Create Murray calculator
        calculator = MurrayCalculator(str(case_dir), full_config)

        # Test automatic exponent detection
        assert calculator.murray_exponent > 0, "Murray exponent should be determined"
        print(f"✅ Murray exponent auto-detected: {calculator.murray_exponent}")

        # Test outlet area extraction (mocked since we don't have checkMesh log)
        # This will use STL fallback method
        outlet_areas = calculator._extract_areas_stl_fallback()

        assert len(outlet_areas) > 0, "Should find outlet areas"
        print(f"✅ Found {len(outlet_areas)} outlets")

        # Test flow ratio calculation
        flow_ratios = calculator.calculate_murray_flow_ratios(outlet_areas)

        # Validate flow conservation
        total_flow = sum(flow_ratios.values())
        assert abs(total_flow - 1.0) < 1e-6, f"Flow conservation violated: {total_flow}"
        print(f"✅ Flow conservation validated: ∑Q_i = {total_flow:.10f}")

        # Validate all outlets have positive flow
        for outlet, ratio in flow_ratios.items():
            assert ratio > 0, f"Outlet {outlet} has non-positive flow: {ratio}"
            assert ratio < 1.0, f"Outlet {outlet} has flow > 100%: {ratio}"

        # Print flow distribution
        print(f"✅ Patient1 Murray flow distribution:")
        for outlet, ratio in sorted(flow_ratios.items(), key=lambda x: -x[1]):
            print(f"   {outlet}: {ratio:.4f} ({ratio*100:.1f}%)")

    def test_patient1_windkessel_parameters(self):
        """Test Windkessel parameter calculation with real patient1 geometry."""
        # Build full config
        builder = ConfigBuilder()
        full_config = builder.build(case_name=self.patient_name, sim_profile_name="sim_les_medium")

        # Create case structure and copy geometry
        case_dir = self.test_output_dir / "windkessel_test"
        tri_surface = case_dir / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)

        # Copy all STL files
        for stl_file in self.patient_dir.glob("*.stl"):
            shutil.copy(stl_file, tri_surface / stl_file.name)

        # Create Murray calculator
        calculator = MurrayCalculator(str(case_dir), full_config)

        # Get flow ratios
        outlet_areas = calculator._extract_areas_stl_fallback()
        flow_ratios = calculator.calculate_murray_flow_ratios(outlet_areas)

        # Calculate Windkessel coefficients
        wk_config = calculator.update_windkessel_coefficients(flow_ratios)

        # Validate Windkessel configuration structure
        assert "flow_split" in wk_config, "Should have flow_split"
        assert "outlet_parameters" in wk_config, "Should have outlet_parameters"
        assert "murray_exponent" in wk_config, "Should have murray_exponent"

        # Validate outlet parameters
        for outlet, params in wk_config["outlet_parameters"].items():
            assert "R" in params, f"{outlet} missing resistance R"
            assert "C" in params, f"{outlet} missing capacitance C"
            assert "Z" in params, f"{outlet} missing peripheral resistance Z"
            assert "radius" in params, f"{outlet} missing radius"
            assert "area" in params, f"{outlet} missing area"
            assert "flow_ratio" in params, f"{outlet} missing flow_ratio"

            # Validate parameter values are physical
            assert params["R"] > 0, f"{outlet} resistance R must be positive"
            assert params["C"] > 0, f"{outlet} capacitance C must be positive"
            assert params["Z"] > 0, f"{outlet} peripheral resistance Z must be positive"
            assert params["radius"] > 0, f"{outlet} radius must be positive"
            assert params["area"] > 0, f"{outlet} area must be positive"

        print(f"✅ Patient1 Windkessel parameters calculated for {len(wk_config['outlet_parameters'])} outlets:")
        for outlet, params in wk_config["outlet_parameters"].items():
            print(f"   {outlet}:")
            print(f"      R={params['R']:.1f} Pa·s/m³, C={params['C']:.2e} m³/Pa, Z={params['Z']:.1f} Pa·s/m³")
            print(f"      radius={params['radius']*1000:.2f}mm, flow={params['flow_ratio']*100:.1f}%")

    def test_patient1_complete_preprocessing(self):
        """Test complete preprocessing workflow from STL to ready-to-run."""
        # Build full config
        builder = ConfigBuilder()
        full_config = builder.build(case_name=self.patient_name, sim_profile_name="sim_les_medium")

        # Create case structure
        case_dir = self.test_output_dir / "complete_test"
        case_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Create case structure
        task1 = CreateCaseStructureTask(full_config)
        context = {"case_directory": str(case_dir)}
        result1 = task1.execute(context)
        assert result1 == True, "Case structure creation should succeed"
        print("✅ Step 1: Case structure created")

        # Step 2: Copy geometry files
        tri_surface = case_dir / "constant" / "triSurface"
        for stl_file in self.patient_dir.glob("*.stl"):
            shutil.copy(stl_file, tri_surface / stl_file.name)
        print("✅ Step 2: Geometry files copied")

        # Step 3: Analyze geometry
        analyzer = GeometryAnalyzer(
            config=full_config,
            case_directory=str(case_dir)
        )
        assert analyzer.inlet_radius > 0, "Geometry analysis should succeed"
        print(f"✅ Step 3: Geometry analyzed (inlet radius: {analyzer.inlet_radius*1000:.2f}mm)")

        # Step 4: Generate mesh files
        task2 = GenerateMeshFilesTask(full_config)
        result2 = task2.execute(context)
        assert result2 == True, "Mesh file generation should succeed"
        assert (case_dir / "system" / "blockMeshDict").exists()
        assert (case_dir / "system" / "snappyHexMeshDict").exists()
        assert (case_dir / "system" / "surfaceFeaturesDict").exists()
        print("✅ Step 4: Mesh files generated")

        # Step 5: Calculate Murray flow distribution
        calculator = MurrayCalculator(str(case_dir), full_config)
        outlet_areas = calculator._extract_areas_stl_fallback()
        flow_ratios = calculator.calculate_murray_flow_ratios(outlet_areas)
        total_flow = sum(flow_ratios.values())
        assert abs(total_flow - 1.0) < 1e-6, "Flow conservation check"
        print(f"✅ Step 5: Murray flow distribution calculated ({len(flow_ratios)} outlets)")

        # Step 6: Calculate Windkessel parameters
        wk_config = calculator.update_windkessel_coefficients(flow_ratios)
        assert len(wk_config["outlet_parameters"]) == len(flow_ratios)
        print(f"✅ Step 6: Windkessel parameters calculated")

        # Verify complete preprocessing succeeded
        print(f"\n✅ Patient1 complete preprocessing workflow validated:")
        print(f"   Case directory: {case_dir}")
        print(f"   Geometry: {len(list(tri_surface.glob('*.stl')))} STL files")
        print(f"   Mesh files: 3 dictionary files")
        print(f"   Flow distribution: {len(flow_ratios)} outlets")
        print(f"   Windkessel: {len(wk_config['outlet_parameters'])} 3EWK models")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
