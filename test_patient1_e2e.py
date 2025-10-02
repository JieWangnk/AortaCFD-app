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


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
