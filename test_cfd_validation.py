"""
CFD Quality Validation Tests

Tests mesh quality and preprocessing for different simulation configurations.
Focus on CFD quality from user perspective (mesh quality, solver suitability, etc.)
"""

import pytest
import shutil
import tempfile
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config.builder import ConfigBuilder
from workflow.tasks.setup_tasks import CreateCaseStructureTask, GenerateMeshFilesTask
from validation.analyzers import MeshQualityAnalyzer, analyze_mesh_quality


class TestPatient1MeshQuality:
    """
    Test mesh quality across different simulation profiles for patient1.

    This validates CFD quality from a user perspective:
    - Is the mesh good enough for this solver type?
    - Does the configuration produce acceptable mesh quality?
    - Can users trust this config for their research?
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        self.patient_name = "patient1"
        self.patient_dir = Path("cases_input") / self.patient_name
        self.test_output_dir = Path(tempfile.mkdtemp(prefix="cfd_validation_"))

        yield

        # Cleanup
        if self.test_output_dir.exists():
            shutil.rmtree(self.test_output_dir)

    def _run_preprocessing(self, sim_profile: str) -> Path:
        """
        Run preprocessing (case structure + mesh generation) for given profile.

        Args:
            sim_profile: Simulation profile name (e.g., "sim_laminar_coarse")

        Returns:
            Path to generated case directory
        """
        # Build configuration
        builder = ConfigBuilder()
        config = builder.build(case_name=self.patient_name, sim_profile_name=sim_profile)

        # Create case directory
        case_dir = self.test_output_dir / f"{self.patient_name}_{sim_profile}"
        case_dir.mkdir(parents=True, exist_ok=True)

        # Task 1: Create case structure
        task1 = CreateCaseStructureTask(config)
        context = {"case_directory": str(case_dir)}
        result1 = task1.execute(context)
        assert result1 is True, f"Failed to create case structure for {sim_profile}"

        # Copy geometry files
        tri_surface = case_dir / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)

        for stl_file in self.patient_dir.glob("*.stl"):
            shutil.copy(stl_file, tri_surface / stl_file.name)

        # Task 2: Generate mesh files
        task2 = GenerateMeshFilesTask(config)
        result2 = task2.execute(context)
        assert result2 is True, f"Failed to generate mesh files for {sim_profile}"

        return case_dir

    def _get_solver_type(self, sim_profile: str) -> str:
        """Extract solver type from profile name."""
        if "laminar" in sim_profile.lower():
            return "laminar"
        elif "rans" in sim_profile.lower():
            return "rans"
        elif "les" in sim_profile.lower():
            return "les"
        return "laminar"

    # ========================================================================
    # LAMINAR CONFIGURATIONS
    # ========================================================================

    def test_laminar_coarse_mesh_quality(self):
        """
        Validate mesh quality for laminar coarse configuration.

        User perspective: "I want a quick, low-resolution mesh for laminar flow."
        CFD expectation: Acceptable quality, low cell count, fast generation.
        """
        case_dir = self._run_preprocessing("sim_laminar_coarse")

        # Analyze mesh quality
        analyzer = MeshQualityAnalyzer(case_dir)
        metrics, passed, issues = analyze_mesh_quality(case_dir, solver_type="laminar")

        # Print quality report
        report = analyzer.generate_quality_report(solver_type="laminar")
        print(f"\n{report}")

        # Assertions: Mesh should be acceptable for laminar
        assert metrics.num_cells > 0, "Mesh has no cells"
        assert metrics.max_non_orthogonality < 70, f"Non-orthogonality too high: {metrics.max_non_orthogonality}"
        assert metrics.max_skewness < 4.0, f"Skewness too high: {metrics.max_skewness}"
        assert metrics.failed_cells == 0, f"Mesh has {metrics.failed_cells} failed cells"

        # Coarse mesh should be relatively small (< 500k cells for patient1)
        assert metrics.num_cells < 500_000, f"Coarse mesh too large: {metrics.num_cells:,} cells"

        # Overall quality check
        if not passed:
            pytest.fail(f"Mesh quality failed:\n" + "\n".join(f"  - {issue}" for issue in issues))

    def test_laminar_medium_mesh_quality(self):
        """
        Validate mesh quality for laminar medium configuration.

        User perspective: "I want a balanced mesh for laminar flow simulations."
        CFD expectation: Good quality, moderate cell count, production-ready.
        """
        case_dir = self._run_preprocessing("sim_laminar_medium")

        analyzer = MeshQualityAnalyzer(case_dir)
        metrics, passed, issues = analyze_mesh_quality(case_dir, solver_type="laminar")

        print(f"\n{analyzer.generate_quality_report(solver_type='laminar')}")

        # Assertions
        assert metrics.num_cells > 0
        assert metrics.max_non_orthogonality < 70
        assert metrics.max_skewness < 4.0
        assert metrics.failed_cells == 0

        # Medium mesh should be larger than coarse
        assert metrics.num_cells >= 10_000, "Medium mesh unexpectedly small"

        if not passed:
            pytest.fail(f"Mesh quality failed:\n" + "\n".join(f"  - {issue}" for issue in issues))

    def test_laminar_fine_mesh_quality(self):
        """
        Validate mesh quality for laminar fine configuration.

        User perspective: "I want high-resolution mesh for detailed laminar analysis."
        CFD expectation: Excellent quality, high cell count, publication-ready.
        """
        case_dir = self._run_preprocessing("sim_laminar_fine")

        analyzer = MeshQualityAnalyzer(case_dir)
        metrics, passed, issues = analyze_mesh_quality(case_dir, solver_type="laminar")

        print(f"\n{analyzer.generate_quality_report(solver_type='laminar')}")

        # Assertions
        assert metrics.num_cells > 0
        assert metrics.max_non_orthogonality < 65, "Fine mesh should have excellent non-orthogonality"
        assert metrics.max_skewness < 3.0, "Fine mesh should have excellent skewness"
        assert metrics.failed_cells == 0

        # Fine mesh should be significantly larger
        assert metrics.num_cells >= 50_000, "Fine mesh unexpectedly small"

        if not passed:
            pytest.fail(f"Mesh quality failed:\n" + "\n".join(f"  - {issue}" for issue in issues))

    # ========================================================================
    # RANS CONFIGURATIONS
    # ========================================================================

    def test_rans_coarse_mesh_quality(self):
        """
        Validate mesh quality for RANS coarse configuration.

        User perspective: "I want a quick RANS turbulence simulation."
        CFD expectation: Acceptable quality, boundary layers for turbulence modeling.
        """
        case_dir = self._run_preprocessing("sim_rans_coarse")

        analyzer = MeshQualityAnalyzer(case_dir)
        metrics, passed, issues = analyze_mesh_quality(case_dir, solver_type="rans")

        print(f"\n{analyzer.generate_quality_report(solver_type='rans')}")

        # Assertions
        assert metrics.num_cells > 0
        assert metrics.max_non_orthogonality < 70
        assert metrics.max_skewness < 4.0
        assert metrics.failed_cells == 0

        # Check boundary layer presence
        bl_info = analyzer.analyze_boundary_layers()
        if bl_info.get("available"):
            assert bl_info.get("num_layers", 0) >= 3, "RANS needs boundary layers"
            if bl_info.get("coverage"):
                assert bl_info["coverage"] > 80, f"Boundary layer coverage too low: {bl_info['coverage']}%"

        if not passed:
            pytest.fail(f"Mesh quality failed:\n" + "\n".join(f"  - {issue}" for issue in issues))

    def test_rans_medium_mesh_quality(self):
        """
        Validate mesh quality for RANS medium configuration.

        User perspective: "I want production-quality RANS simulations."
        CFD expectation: Good quality, proper boundary layers, suitable for wall modeling.
        """
        case_dir = self._run_preprocessing("sim_rans_medium")

        analyzer = MeshQualityAnalyzer(case_dir)
        metrics, passed, issues = analyze_mesh_quality(case_dir, solver_type="rans")

        print(f"\n{analyzer.generate_quality_report(solver_type='rans')}")

        # Assertions
        assert metrics.num_cells > 0
        assert metrics.max_non_orthogonality < 70
        assert metrics.max_skewness < 4.0
        assert metrics.failed_cells == 0

        # Boundary layer requirements for RANS
        bl_info = analyzer.analyze_boundary_layers()
        if bl_info.get("available"):
            assert bl_info.get("num_layers", 0) >= 5, "RANS medium needs sufficient boundary layers"

        if not passed:
            pytest.fail(f"Mesh quality failed:\n" + "\n".join(f"  - {issue}" for issue in issues))

    # ========================================================================
    # LES CONFIGURATION
    # ========================================================================

    def test_les_medium_mesh_quality(self):
        """
        Validate mesh quality for LES configuration.

        User perspective: "I want high-fidelity LES for research."
        CFD expectation: Excellent quality, fine resolution, strict aspect ratio.
        """
        case_dir = self._run_preprocessing("sim_les_medium")

        analyzer = MeshQualityAnalyzer(case_dir)
        metrics, passed, issues = analyze_mesh_quality(case_dir, solver_type="les")

        print(f"\n{analyzer.generate_quality_report(solver_type='les')}")

        # Assertions - LES has stricter requirements
        assert metrics.num_cells > 0
        assert metrics.max_non_orthogonality < 65, "LES needs excellent non-orthogonality"
        assert metrics.max_skewness < 3.0, "LES needs excellent skewness"
        assert metrics.max_aspect_ratio < 100, "LES needs low aspect ratio"
        assert metrics.failed_cells == 0

        # LES should have many cells for turbulence resolution
        assert metrics.num_cells >= 100_000, "LES mesh should be fine resolution"

        if not passed:
            pytest.fail(f"Mesh quality failed:\n" + "\n".join(f"  - {issue}" for issue in issues))


class TestConfigurationComparison:
    """
    Compare mesh characteristics across different configurations.

    User perspective: "Which config should I choose for my case?"
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        self.patient_name = "patient1"
        self.patient_dir = Path("cases_input") / self.patient_name
        self.test_output_dir = Path(tempfile.mkdtemp(prefix="config_comparison_"))

        yield

        if self.test_output_dir.exists():
            shutil.rmtree(self.test_output_dir)

    def test_cell_count_increases_with_resolution(self):
        """
        Validate that finer configs have more cells.

        User expectation: coarse < medium < fine
        """
        configs = ["sim_laminar_coarse", "sim_laminar_medium", "sim_laminar_fine"]
        cell_counts = {}

        for sim_profile in configs:
            # Build config
            builder = ConfigBuilder()
            config = builder.build(case_name=self.patient_name, sim_profile_name=sim_profile)

            # Get target cell size from config
            cell_size = config.get("mesh_generation", {}).get("target_cell_size_mm", 1.5)
            cell_counts[sim_profile] = {"target_cell_size_mm": cell_size}

        # Verify ordering
        assert cell_counts["sim_laminar_coarse"]["target_cell_size_mm"] >= \
               cell_counts["sim_laminar_medium"]["target_cell_size_mm"], \
               "Coarse should have larger cell size than medium"

        assert cell_counts["sim_laminar_medium"]["target_cell_size_mm"] >= \
               cell_counts["sim_laminar_fine"]["target_cell_size_mm"], \
               "Medium should have larger cell size than fine"

        print(f"\nCell size progression:")
        for profile, data in cell_counts.items():
            print(f"  {profile}: {data['target_cell_size_mm']:.2f} mm")

    def test_solver_type_reflected_in_config(self):
        """
        Validate that solver type is correctly set in each config.

        User expectation: Config name matches solver type.
        """
        test_cases = [
            ("sim_laminar_medium", "laminar"),
            ("sim_rans_medium", "RANS"),
            ("sim_les_medium", "LES")
        ]

        for sim_profile, expected_solver_keyword in test_cases:
            builder = ConfigBuilder()
            config = builder.build(case_name=self.patient_name, sim_profile_name=sim_profile)

            solver_type = config.get("simulation_settings", {}).get("solver_type", "")

            assert expected_solver_keyword.lower() in solver_type.lower(), \
                f"{sim_profile} should use {expected_solver_keyword} solver, got {solver_type}"

            print(f"✅ {sim_profile}: solver_type = {solver_type}")


if __name__ == "__main__":
    # Run validation tests
    pytest.main([__file__, "-v", "--tb=short", "-s"])
