"""
Test suite for mesh_adaptive_solver.py module.

Tests cover:
- MeshAdaptiveSolverSettings class
- checkMesh log parsing
- Quality tier determination
- fvSolution adjustments
- fvSchemes adjustments
- Quality report generation
"""

import pytest
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestMeshAdaptiveSolverSettingsInit:
    """Test MeshAdaptiveSolverSettings initialization."""

    def test_init(self):
        """Test basic initialization."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()

        assert adapter.mesh_quality_tier is None
        assert adapter.metrics == {}


class TestAnalyzeCheckmeshLog:
    """Test analyze_checkmesh_log method."""

    def test_parse_complete_log(self):
        """Test parsing complete checkMesh log."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            log_content = """
Checking geometry...
    Mesh non-orthogonality Max: 65.5 average: 12.3
    Max skewness = 2.45 OK
    Max aspect ratio = 25.3 OK
"""
            log_path = Path(tmpdir) / "log.checkMesh"
            log_path.write_text(log_content)

            adapter = MeshAdaptiveSolverSettings()
            metrics = adapter.analyze_checkmesh_log(str(log_path))

            assert abs(metrics["max_skewness"] - 2.45) < 0.01
            assert abs(metrics["max_non_orthogonality"] - 65.5) < 0.1
            assert abs(metrics["max_aspect_ratio"] - 25.3) < 0.1

    def test_parse_partial_log(self):
        """Test parsing log with missing metrics."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            log_content = """
Checking geometry...
    Max skewness = 3.5 OK
"""
            log_path = Path(tmpdir) / "log.checkMesh"
            log_path.write_text(log_content)

            adapter = MeshAdaptiveSolverSettings()
            metrics = adapter.analyze_checkmesh_log(str(log_path))

            assert abs(metrics["max_skewness"] - 3.5) < 0.01
            # Other metrics should not be present
            assert "max_non_orthogonality" not in metrics or metrics.get("max_non_orthogonality") is None

    def test_parse_missing_log_returns_defaults(self):
        """Test that missing log returns conservative defaults."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()
        metrics = adapter.analyze_checkmesh_log("/nonexistent/path")

        # Should return default conservative values
        assert metrics["max_skewness"] == 4.0
        assert metrics["max_non_orthogonality"] == 65.0
        assert metrics["max_aspect_ratio"] == 30.0


class TestDetermineQualityTier:
    """Test _determine_quality_tier method."""

    def test_excellent_quality(self):
        """Test EXCELLENT tier detection."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()

        metrics = {"max_skewness": 1.0, "max_non_orthogonality": 50.0, "max_aspect_ratio": 15.0}

        tier = adapter._determine_quality_tier(metrics)

        assert tier == "EXCELLENT"

    def test_good_quality(self):
        """Test GOOD tier detection."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()

        metrics = {"max_skewness": 2.0, "max_non_orthogonality": 60.0, "max_aspect_ratio": 25.0}

        tier = adapter._determine_quality_tier(metrics)

        assert tier == "GOOD"

    def test_fair_quality(self):
        """Test FAIR tier detection."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()

        metrics = {"max_skewness": 3.0, "max_non_orthogonality": 66.0, "max_aspect_ratio": 35.0}

        tier = adapter._determine_quality_tier(metrics)

        assert tier == "FAIR"

    def test_poor_quality(self):
        """Test POOR tier detection."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()

        metrics = {"max_skewness": 5.0, "max_non_orthogonality": 72.0, "max_aspect_ratio": 60.0}

        tier = adapter._determine_quality_tier(metrics)

        assert tier == "POOR"

    def test_critical_quality(self):
        """Test CRITICAL tier detection."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()

        metrics = {"max_skewness": 7.0, "max_non_orthogonality": 80.0, "max_aspect_ratio": 150.0}

        tier = adapter._determine_quality_tier(metrics)

        assert tier == "CRITICAL"

    def test_critical_by_skewness_alone(self):
        """Test CRITICAL tier triggered by high skewness alone."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()

        metrics = {
            "max_skewness": 6.5,  # Critical threshold
            "max_non_orthogonality": 50.0,  # Excellent
            "max_aspect_ratio": 10.0,  # Excellent
        }

        tier = adapter._determine_quality_tier(metrics)

        assert tier == "CRITICAL"


class TestGetCorrectorsForQuality:
    """Test _get_correctors_for_quality method."""

    def test_excellent_standard_correctors(self):
        """Test correctors for excellent mesh with standard profile."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()

        result = adapter._get_correctors_for_quality("EXCELLENT", "standard", 50.0)

        nOuter, nCorrect, nNonOrtho = result
        assert nOuter == 2
        assert nCorrect == 2
        assert nNonOrtho == 1  # Low ortho angle needs only 1 correction

    def test_critical_robust_correctors(self):
        """Test correctors for critical mesh with robust profile."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()

        result = adapter._get_correctors_for_quality("CRITICAL", "robust", 78.0)

        nOuter, nCorrect, nNonOrtho = result
        assert nOuter == 5  # High for critical
        assert nCorrect == 4
        assert nNonOrtho == 5  # High ortho needs max corrections

    def test_non_orthogonal_correctors_scale(self):
        """Test that non-orthogonal correctors scale with angle."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()

        # Low ortho angle
        _, _, nNonOrtho_low = adapter._get_correctors_for_quality("GOOD", "standard", 50.0)
        # High ortho angle
        _, _, nNonOrtho_high = adapter._get_correctors_for_quality("GOOD", "standard", 72.0)

        assert nNonOrtho_high > nNonOrtho_low


class TestGetRelaxationForQuality:
    """Test _get_relaxation_for_quality method."""

    def test_excellent_relaxation(self):
        """Test relaxation for excellent mesh."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()

        p_relax, u_relax = adapter._get_relaxation_for_quality("EXCELLENT", "standard")

        # Excellent mesh allows higher relaxation
        assert p_relax >= 0.3
        assert u_relax >= 0.7

    def test_critical_relaxation(self):
        """Test relaxation for critical mesh."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()

        p_relax, u_relax = adapter._get_relaxation_for_quality("CRITICAL", "robust")

        # Critical mesh needs strong relaxation (smaller values)
        assert p_relax <= 0.15
        assert u_relax <= 0.4

    def test_relaxation_decreases_with_quality(self):
        """Test that relaxation decreases as quality worsens."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()

        p_excellent, u_excellent = adapter._get_relaxation_for_quality("EXCELLENT", "standard")
        p_critical, u_critical = adapter._get_relaxation_for_quality("CRITICAL", "standard")

        assert p_excellent > p_critical
        assert u_excellent > u_critical


class TestGetTolerancesForQuality:
    """Test _get_tolerances_for_quality method."""

    def test_excellent_tolerances(self):
        """Test tolerances for excellent mesh."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()

        p_tol, u_tol = adapter._get_tolerances_for_quality("EXCELLENT", "accurate")

        # Excellent mesh can achieve tight tolerances
        assert p_tol <= 1e-7
        assert u_tol <= 1e-7

    def test_critical_tolerances(self):
        """Test tolerances for critical mesh."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()

        p_tol, u_tol = adapter._get_tolerances_for_quality("CRITICAL", "robust")

        # Critical mesh needs relaxed tolerances
        assert p_tol >= 1e-4
        assert u_tol >= 1e-4


class TestAdjustFvSolutionForMesh:
    """Test adjust_fvsolution_for_mesh method."""

    def test_adjust_creates_pimple_section(self):
        """Test that adjustment creates PIMPLE section if missing."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()
        adapter.mesh_quality_tier = "GOOD"
        adapter.metrics = {"max_skewness": 2.0, "max_non_orthogonality": 60.0}

        base_fvsolution = {}  # Empty

        result = adapter.adjust_fvsolution_for_mesh(base_fvsolution, "standard")

        assert "PIMPLE" in result
        assert "nOuterCorrectors" in result["PIMPLE"]
        assert "nCorrectors" in result["PIMPLE"]
        assert "nNonOrthogonalCorrectors" in result["PIMPLE"]

    def test_adjust_creates_relaxation_factors(self):
        """Test that adjustment creates relaxation factors."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()
        adapter.mesh_quality_tier = "FAIR"
        adapter.metrics = {"max_skewness": 3.0, "max_non_orthogonality": 66.0}

        base_fvsolution = {}

        result = adapter.adjust_fvsolution_for_mesh(base_fvsolution, "standard")

        assert "relaxationFactors" in result
        assert "fields" in result["relaxationFactors"]
        assert "equations" in result["relaxationFactors"]
        assert "p" in result["relaxationFactors"]["fields"]
        assert "U" in result["relaxationFactors"]["equations"]

    def test_adjust_creates_residual_control(self):
        """Test that adjustment creates residual control."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()
        adapter.mesh_quality_tier = "GOOD"
        adapter.metrics = {"max_skewness": 2.0, "max_non_orthogonality": 60.0}

        base_fvsolution = {}

        result = adapter.adjust_fvsolution_for_mesh(base_fvsolution, "standard")

        assert "residualControl" in result
        assert "p" in result["residualControl"]
        assert "U" in result["residualControl"]

    def test_adjust_adds_corrector_control_for_poor_mesh(self):
        """Test that poor mesh gets corrector residual control."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()
        adapter.mesh_quality_tier = "POOR"
        adapter.metrics = {"max_skewness": 5.0, "max_non_orthogonality": 72.0}

        base_fvsolution = {}

        result = adapter.adjust_fvsolution_for_mesh(base_fvsolution, "robust")

        assert "correctorResidualControl" in result["PIMPLE"]
        assert "outerCorrectorResidualControl" in result["PIMPLE"]

    def test_adjust_defaults_to_fair_if_not_analyzed(self):
        """Test that unanalyzed mesh defaults to FAIR tier."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()
        # Don't analyze - tier should be None

        base_fvsolution = {}

        result = adapter.adjust_fvsolution_for_mesh(base_fvsolution, "standard")

        # Should have set tier to FAIR
        assert adapter.mesh_quality_tier == "FAIR"


class TestAdjustFvSchemesForMesh:
    """Test adjust_fvschemes_for_mesh method."""

    def test_adjust_laplacian_good_mesh(self):
        """Test laplacian scheme for good quality mesh."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()
        adapter.mesh_quality_tier = "GOOD"
        adapter.metrics = {"max_skewness": 1.5, "max_non_orthogonality": 55.0}

        base_fvschemes = {}

        result = adapter.adjust_fvschemes_for_mesh(base_fvschemes, "standard")

        assert "laplacianSchemes" in result
        assert "corrected" in result["laplacianSchemes"]["default"]

    def test_adjust_laplacian_poor_mesh(self):
        """Test laplacian scheme for poor quality mesh."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()
        adapter.mesh_quality_tier = "POOR"
        adapter.metrics = {"max_skewness": 5.0, "max_non_orthogonality": 72.0}

        base_fvschemes = {}

        result = adapter.adjust_fvschemes_for_mesh(base_fvschemes, "robust")

        assert "laplacianSchemes" in result
        # Poor mesh should use limited correction
        assert "limited" in result["laplacianSchemes"]["default"]

    def test_adjust_gradients_for_high_skewness(self):
        """Test gradient scheme limiting for high skewness."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()
        adapter.mesh_quality_tier = "POOR"
        adapter.metrics = {"max_skewness": 5.0, "max_non_orthogonality": 65.0}

        base_fvschemes = {}

        result = adapter.adjust_fvschemes_for_mesh(base_fvschemes, "robust")

        assert "gradSchemes" in result
        # High skewness should use limited gradients
        assert "Limited" in result["gradSchemes"]["default"] or "limited" in result["gradSchemes"]["default"]


class TestGetQualityReport:
    """Test get_quality_report method."""

    def test_report_not_analyzed(self):
        """Test report when mesh not analyzed."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()

        report = adapter.get_quality_report()

        assert report["status"] == "not_analyzed"

    def test_report_critical_mesh(self):
        """Test report for critical mesh."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()
        adapter.mesh_quality_tier = "CRITICAL"
        adapter.metrics = {"max_skewness": 7.0, "max_non_orthogonality": 78.0, "max_aspect_ratio": 120.0}

        report = adapter.get_quality_report()

        assert report["tier"] == "CRITICAL"
        assert report["metrics"] == adapter.metrics
        assert len(report["recommendations"]) > 0
        assert any("CRITICAL" in rec for rec in report["recommendations"])

    def test_report_excellent_mesh(self):
        """Test report for excellent mesh."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        adapter = MeshAdaptiveSolverSettings()
        adapter.mesh_quality_tier = "EXCELLENT"
        adapter.metrics = {"max_skewness": 1.0, "max_non_orthogonality": 50.0, "max_aspect_ratio": 15.0}

        report = adapter.get_quality_report()

        assert report["tier"] == "EXCELLENT"
        assert any("Excellent" in rec or "EXCELLENT" in rec for rec in report["recommendations"])


class TestApplyMeshAdaptiveSettings:
    """Test apply_mesh_adaptive_settings convenience function."""

    def test_apply_with_checkmesh_log(self):
        """Test applying settings when checkMesh log exists."""
        from config.mesh_adaptive_solver import apply_mesh_adaptive_settings

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create logs directory with checkMesh log
            logs_dir = Path(tmpdir) / "logs"
            logs_dir.mkdir()

            log_content = """
Checking geometry...
    Mesh non-orthogonality Max: 60.0 average: 10.0
    Max skewness = 2.0 OK
    Max aspect ratio = 20.0 OK
"""
            (logs_dir / "log.checkMesh").write_text(log_content)

            base_fvsolution = {}
            base_fvschemes = {}

            adjusted_fvsolution, adjusted_fvschemes, report = apply_mesh_adaptive_settings(
                tmpdir, "standard", base_fvsolution, base_fvschemes
            )

            assert "PIMPLE" in adjusted_fvsolution
            assert "laplacianSchemes" in adjusted_fvschemes
            assert report["tier"] == "GOOD"

    def test_apply_without_checkmesh_log(self):
        """Test applying settings when checkMesh log doesn't exist."""
        from config.mesh_adaptive_solver import apply_mesh_adaptive_settings

        with tempfile.TemporaryDirectory() as tmpdir:
            # No log file created

            base_fvsolution = {}
            base_fvschemes = {}

            adjusted_fvsolution, adjusted_fvschemes, report = apply_mesh_adaptive_settings(
                tmpdir, "standard", base_fvsolution, base_fvschemes
            )

            # Should still work with defaults
            assert "PIMPLE" in adjusted_fvsolution
            assert "laplacianSchemes" in adjusted_fvschemes


class TestIntegration:
    """Integration tests for MeshAdaptiveSolverSettings."""

    def test_full_workflow(self):
        """Test complete workflow from log parsing to adjusted settings."""
        from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create checkMesh log
            log_content = """
Checking geometry...
    Overall domain bounding box (-0.05 -0.05 -0.1) (0.05 0.05 0.1)
    Mesh has 3 geometric regions
    Checking face-face connectivity...OK
    Checking cell-face connectivity...OK
    Mesh non-orthogonality Max: 68.5 average: 15.2
    Max skewness = 3.2 OK
    Max aspect ratio = 45.0 OK
    Mesh geometry appears OK.
"""
            log_path = Path(tmpdir) / "log.checkMesh"
            log_path.write_text(log_content)

            adapter = MeshAdaptiveSolverSettings()

            # Analyze
            metrics = adapter.analyze_checkmesh_log(str(log_path))

            assert metrics["max_skewness"] == 3.2
            assert metrics["max_non_orthogonality"] == 68.5
            assert metrics["max_aspect_ratio"] == 45.0
            assert adapter.mesh_quality_tier == "FAIR"

            # Adjust fvSolution
            base_fvsolution = {"solvers": {"p": {"solver": "GAMG"}, "U": {"solver": "smoothSolver"}}}

            adjusted_solution = adapter.adjust_fvsolution_for_mesh(base_fvsolution, "standard")

            # Should have added PIMPLE settings
            assert "nOuterCorrectors" in adjusted_solution["PIMPLE"]

            # Adjust fvSchemes
            base_fvschemes = {"divSchemes": {"default": "none"}}

            adjusted_schemes = adapter.adjust_fvschemes_for_mesh(base_fvschemes, "standard")

            # Should have added laplacian with limited correction
            assert "limited" in adjusted_schemes["laplacianSchemes"]["default"]

            # Get report
            report = adapter.get_quality_report()

            assert report["tier"] == "FAIR"
            assert len(report["recommendations"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
