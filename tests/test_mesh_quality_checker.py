"""
Test suite for MeshQualityChecker module.

Tests the mesh quality analysis and recommendation functionality.
"""

import pytest
import sys
import tempfile
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aortacfd_lib.mesh_quality_checker import MeshQualityChecker


class TestMeshQualityCheckerInit:
    """Test MeshQualityChecker initialization."""

    def test_init_creates_instance(self):
        """Test that MeshQualityChecker can be instantiated."""
        checker = MeshQualityChecker()
        assert checker is not None


class TestAnalyzeMeshQuality:
    """Test the main analyze_mesh_quality method."""

    def test_missing_log_file(self):
        """Test analysis with missing checkMesh log."""
        checker = MeshQualityChecker()

        with tempfile.TemporaryDirectory() as tmpdir:
            result = checker.analyze_mesh_quality(tmpdir)

            assert result["status"] == "error"
            assert "checkMesh log file not found" in result["message"]
            assert len(result["alerts"]) > 0

    def test_unreadable_log_file(self):
        """Test analysis with unreadable log file."""
        checker = MeshQualityChecker()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create logs directory and an unreadable file
            logs_dir = Path(tmpdir) / "logs"
            logs_dir.mkdir()
            log_file = logs_dir / "log.checkMesh"
            log_file.touch()
            os.chmod(log_file, 0o000)  # Remove all permissions

            result = checker.analyze_mesh_quality(tmpdir)

            # Restore permissions for cleanup
            os.chmod(log_file, 0o644)

            # Should handle gracefully
            assert "status" in result

    def test_good_quality_mesh(self):
        """Test analysis with good quality mesh output."""
        checker = MeshQualityChecker()

        good_mesh_log = """
Checking geometry...
    Overall domain bounding box (0 0 0) (0.1 0.1 0.1)
    Mesh has 3 geometric (non-empty/wedge) directions (1 1 1)
    Mesh has 3 solution (non-empty) directions (1 1 1)
    All edges aligned with or perpendicular to non-empty directions.
    Boundary openness (-1.2e-16 5.3e-17 -8.4e-17) OK.
    Max cell openness = 2.5e-16 OK.
    Max aspect ratio = 3.5 OK.
    Mesh non-orthogonality Max: 45.2 average: 8.5
    Max skewness = 1.5 OK.
    Coupled point location match (average 0) OK.

Mesh OK.
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "logs"
            logs_dir.mkdir()
            log_file = logs_dir / "log.checkMesh"
            with open(log_file, "w") as f:
                f.write(good_mesh_log)

            result = checker.analyze_mesh_quality(tmpdir)

            assert result["status"] == "good"
            assert len(result["alerts"]) == 0
            assert result["metrics"]["max_skewness"] == pytest.approx(1.5, rel=1e-3)
            assert result["metrics"]["max_aspect_ratio"] == pytest.approx(3.5, rel=1e-3)
            assert result["metrics"]["max_non_orthogonality"] == pytest.approx(45.2, rel=1e-3)

    def test_warning_quality_mesh(self):
        """Test analysis with warning-level mesh quality."""
        checker = MeshQualityChecker()

        warning_mesh_log = """
Checking geometry...
    Max aspect ratio = 7.2 OK.
    Mesh non-orthogonality Max: 65.5 average: 15.2
    Max skewness = 2.8 OK.

Mesh OK.
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "logs"
            logs_dir.mkdir()
            with open(logs_dir / "log.checkMesh", "w") as f:
                f.write(warning_mesh_log)

            result = checker.analyze_mesh_quality(tmpdir)

            assert result["status"] == "warning"
            assert len(result["warnings"]) > 0
            # Should have warnings for skewness and non-orthogonality
            warnings_text = " ".join(result["warnings"])
            assert "skewness" in warnings_text.lower() or "non-orthogonality" in warnings_text.lower()

    def test_poor_quality_mesh(self):
        """Test analysis with poor quality mesh."""
        checker = MeshQualityChecker()

        poor_mesh_log = """
Checking geometry...
    Max aspect ratio = 12.5 OK.
    Mesh non-orthogonality Max: 75.8 average: 25.3
    Max skewness = 5.2 OK.
    15 highly skew faces detected

Mesh OK.
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "logs"
            logs_dir.mkdir()
            with open(logs_dir / "log.checkMesh", "w") as f:
                f.write(poor_mesh_log)

            result = checker.analyze_mesh_quality(tmpdir)

            assert result["status"] == "poor"
            assert len(result["alerts"]) > 0
            assert len(result["recommendations"]) > 0
            assert result["metrics"]["max_skewness"] == pytest.approx(5.2, rel=1e-3)
            assert result["metrics"]["highly_skew_faces"] == 15

    def test_failed_mesh_checks(self):
        """Test analysis detects failed mesh checks count."""
        checker = MeshQualityChecker()

        failed_mesh_log = """
Checking geometry...
    Max aspect ratio = 8.5 OK.
    Mesh non-orthogonality Max: 55.2 average: 12.5
    Max skewness = 4.5 OK.

Failed 3 mesh checks.
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "logs"
            logs_dir.mkdir()
            with open(logs_dir / "log.checkMesh", "w") as f:
                f.write(failed_mesh_log)

            result = checker.analyze_mesh_quality(tmpdir)

            # Status is 'poor' because skewness > 4.0
            # The failed_checks metric should still be extracted
            assert result["status"] in ["poor", "failed"]
            assert result["metrics"]["failed_checks"] == 3
            assert len(result["alerts"]) > 0  # Should have alert for failed checks


class TestMetricExtraction:
    """Test individual metric extraction methods."""

    def setup_method(self):
        """Setup checker instance."""
        self.checker = MeshQualityChecker()

    def test_extract_skewness(self):
        """Test skewness extraction."""
        content = "Max skewness = 2.35 OK."
        report = {"status": "good", "metrics": {}, "alerts": [], "warnings": []}

        self.checker._extract_skewness(content, report)

        assert report["metrics"]["max_skewness"] == pytest.approx(2.35, rel=1e-3)
        # Should have warning for skewness > 2.0
        assert len(report["warnings"]) > 0

    def test_extract_skewness_with_highly_skew_faces(self):
        """Test skewness extraction with highly skew faces count."""
        content = """Max skewness = 4.5 OK.
23 highly skew faces detected"""
        report = {"status": "good", "metrics": {}, "alerts": [], "warnings": []}

        self.checker._extract_skewness(content, report)

        assert report["metrics"]["max_skewness"] == pytest.approx(4.5, rel=1e-3)
        assert report["metrics"]["highly_skew_faces"] == 23
        assert report["status"] == "poor"

    def test_extract_aspect_ratio(self):
        """Test aspect ratio extraction."""
        content = "Max aspect ratio = 5.75 OK."
        report = {"status": "good", "metrics": {}, "alerts": [], "warnings": []}

        self.checker._extract_aspect_ratio(content, report)

        assert report["metrics"]["max_aspect_ratio"] == pytest.approx(5.75, rel=1e-3)

    def test_extract_aspect_ratio_very_high(self):
        """Test aspect ratio extraction with very high value."""
        content = "Max aspect ratio = 15.5 OK."
        report = {"status": "good", "metrics": {}, "alerts": [], "warnings": []}

        self.checker._extract_aspect_ratio(content, report)

        assert report["metrics"]["max_aspect_ratio"] == pytest.approx(15.5, rel=1e-3)
        assert report["status"] == "poor"
        assert len(report["alerts"]) > 0

    def test_extract_non_orthogonality(self):
        """Test non-orthogonality extraction."""
        content = "Mesh non-orthogonality Max: 52.3 average: 12.5"
        report = {"status": "good", "metrics": {}, "alerts": [], "warnings": []}

        self.checker._extract_non_orthogonality(content, report)

        assert report["metrics"]["max_non_orthogonality"] == pytest.approx(52.3, rel=1e-3)
        assert report["metrics"]["avg_non_orthogonality"] == pytest.approx(12.5, rel=1e-3)

    def test_extract_non_orthogonality_severe(self):
        """Test non-orthogonality with severe angle."""
        content = "Mesh non-orthogonality Max: 78.5 average: 25.3"
        report = {"status": "good", "metrics": {}, "alerts": [], "warnings": []}

        self.checker._extract_non_orthogonality(content, report)

        assert report["status"] == "poor"
        assert len(report["alerts"]) > 0

    def test_extract_face_areas(self):
        """Test face area extraction."""
        # Use exact format from OpenFOAM: "= value. value" pattern
        content = "Minimum face area = 1.5e-08. Maximum face area = 3.2e-05 OK"
        report = {"metrics": {}}

        self.checker._extract_face_areas(content, report)

        assert report["metrics"]["min_face_area"] == pytest.approx(1.5e-08, rel=1e-3)
        assert report["metrics"]["max_face_area"] == pytest.approx(3.2e-05, rel=1e-3)
        assert report["metrics"]["face_area_ratio"] == pytest.approx(3.2e-05 / 1.5e-08, rel=1e-3)

    def test_extract_cell_volumes(self):
        """Test cell volume extraction."""
        # Use exact format from OpenFOAM: "= value. value" pattern
        content = "Min volume = 2.1e-10. Max volume = 5.4e-07 OK"
        report = {"metrics": {}}

        self.checker._extract_cell_volumes(content, report)

        assert report["metrics"]["min_cell_volume"] == pytest.approx(2.1e-10, rel=1e-3)
        assert report["metrics"]["max_cell_volume"] == pytest.approx(5.4e-07, rel=1e-3)
        assert report["metrics"]["volume_ratio"] == pytest.approx(5.4e-07 / 2.1e-10, rel=1e-3)


class TestRecommendations:
    """Test recommendation generation."""

    def setup_method(self):
        """Setup checker instance."""
        self.checker = MeshQualityChecker()

    def test_recommendations_for_poor_mesh(self):
        """Test recommendations are generated for poor mesh."""
        report = {
            "status": "poor",
            "metrics": {"max_skewness": 4.5, "max_aspect_ratio": 12.0, "max_non_orthogonality": 72.0},
            "alerts": [],
            "warnings": [],
            "recommendations": [],
        }

        self.checker._generate_recommendations(report)

        assert len(report["recommendations"]) > 0
        # Should have specific recommendations for all issues
        recs_text = " ".join(report["recommendations"])
        assert "refinement" in recs_text.lower() or "skew" in recs_text.lower()

    def test_recommendations_for_warning_mesh(self):
        """Test recommendations for warning-level mesh."""
        report = {
            "status": "warning",
            "metrics": {"max_skewness": 1.5},
            "alerts": [],
            "warnings": [],
            "recommendations": [],
        }

        self.checker._generate_recommendations(report)

        assert len(report["recommendations"]) > 0
        recs_text = " ".join(report["recommendations"])
        assert "acceptable" in recs_text.lower() or "monitor" in recs_text.lower()

    def test_no_recommendations_for_good_mesh(self):
        """Test no critical recommendations for good mesh."""
        report = {
            "status": "good",
            "metrics": {"max_skewness": 1.2},
            "alerts": [],
            "warnings": [],
            "recommendations": [],
        }

        self.checker._generate_recommendations(report)

        # Should have no critical recommendations
        recs_text = " ".join(report["recommendations"])
        assert "CRITICAL" not in recs_text


class TestShouldAbortSimulation:
    """Test abort decision logic."""

    def setup_method(self):
        """Setup checker instance."""
        self.checker = MeshQualityChecker()

    def test_abort_on_failed_status(self):
        """Test abort when status is failed."""
        report = {"status": "failed", "metrics": {}}
        assert self.checker.should_abort_simulation(report) is True

    def test_abort_on_very_high_skewness(self):
        """Test abort when skewness > 6.0."""
        report = {"status": "poor", "metrics": {"max_skewness": 7.5}}
        assert self.checker.should_abort_simulation(report) is True

    def test_abort_on_extreme_aspect_ratio(self):
        """Test abort when aspect ratio > 15.0."""
        report = {"status": "poor", "metrics": {"max_aspect_ratio": 18.0}}
        assert self.checker.should_abort_simulation(report) is True

    def test_no_abort_for_warning_mesh(self):
        """Test no abort for warning-level mesh."""
        report = {"status": "warning", "metrics": {"max_skewness": 3.0, "max_aspect_ratio": 8.0}}
        assert self.checker.should_abort_simulation(report) is False

    def test_no_abort_for_good_mesh(self):
        """Test no abort for good mesh."""
        report = {"status": "good", "metrics": {"max_skewness": 1.5, "max_aspect_ratio": 4.0}}
        assert self.checker.should_abort_simulation(report) is False


class TestPrintQualityReport:
    """Test report printing functionality."""

    def setup_method(self):
        """Setup checker instance."""
        self.checker = MeshQualityChecker()

    def test_print_report_good(self, capsys):
        """Test printing good quality report."""
        report = {
            "status": "good",
            "metrics": {"max_skewness": 1.2, "max_aspect_ratio": 3.5, "max_non_orthogonality": 45.0},
            "alerts": [],
            "warnings": [],
            "recommendations": [],
        }

        self.checker.print_quality_report(report, "test_case")

        captured = capsys.readouterr()
        assert "GOOD" in captured.out
        assert "test_case" in captured.out

    def test_print_report_with_alerts(self, capsys):
        """Test printing report with alerts."""
        report = {
            "status": "poor",
            "metrics": {"max_skewness": 5.0},
            "alerts": ["High skewness detected"],
            "warnings": [],
            "recommendations": ["Reduce skewness"],
        }

        self.checker.print_quality_report(report)

        captured = capsys.readouterr()
        assert "POOR" in captured.out
        assert "High skewness" in captured.out
        assert "Reduce skewness" in captured.out


class TestThresholdValues:
    """Test that threshold values are reasonable."""

    def test_skewness_threshold_values(self):
        """Test skewness threshold classifications."""
        checker = MeshQualityChecker()

        # Good skewness (< 2.0)
        report1 = {"status": "good", "metrics": {}, "alerts": [], "warnings": []}
        checker._extract_skewness("Max skewness = 1.8 OK.", report1)
        assert report1["status"] == "good"

        # Warning skewness (2.0 - 4.0)
        report2 = {"status": "good", "metrics": {}, "alerts": [], "warnings": []}
        checker._extract_skewness("Max skewness = 3.0 OK.", report2)
        assert report2["status"] == "warning"

        # Poor skewness (> 4.0)
        report3 = {"status": "good", "metrics": {}, "alerts": [], "warnings": []}
        checker._extract_skewness("Max skewness = 4.5 OK.", report3)
        assert report3["status"] == "poor"

    def test_aspect_ratio_threshold_values(self):
        """Test aspect ratio threshold classifications."""
        checker = MeshQualityChecker()

        # Good aspect ratio (< 6.0)
        report1 = {"status": "good", "metrics": {}, "alerts": [], "warnings": []}
        checker._extract_aspect_ratio("Max aspect ratio = 4.0 OK.", report1)
        assert len(report1["alerts"]) == 0
        assert len(report1["warnings"]) == 0

        # Warning aspect ratio (6.0 - 10.0)
        report2 = {"status": "good", "metrics": {}, "alerts": [], "warnings": []}
        checker._extract_aspect_ratio("Max aspect ratio = 8.0 OK.", report2)
        assert report2["status"] == "warning"

        # Poor aspect ratio (> 10.0)
        report3 = {"status": "good", "metrics": {}, "alerts": [], "warnings": []}
        checker._extract_aspect_ratio("Max aspect ratio = 12.0 OK.", report3)
        assert report3["status"] == "poor"

    def test_non_orthogonality_threshold_values(self):
        """Test non-orthogonality threshold classifications."""
        checker = MeshQualityChecker()

        # Good (< 60)
        report1 = {"status": "good", "metrics": {}, "alerts": [], "warnings": []}
        checker._extract_non_orthogonality("Mesh non-orthogonality Max: 50.0 average: 10.0", report1)
        assert report1["status"] == "good"

        # Warning (60 - 70)
        report2 = {"status": "good", "metrics": {}, "alerts": [], "warnings": []}
        checker._extract_non_orthogonality("Mesh non-orthogonality Max: 65.0 average: 15.0", report2)
        assert report2["status"] == "warning"

        # Poor (> 70)
        report3 = {"status": "good", "metrics": {}, "alerts": [], "warnings": []}
        checker._extract_non_orthogonality("Mesh non-orthogonality Max: 75.0 average: 20.0", report3)
        assert report3["status"] == "poor"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
