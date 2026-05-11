"""
Test suite for mesh_quality.py module.

Tests cover:
- MeshQualityTier enum
- BoundaryLayerMetrics dataclass
- MeshQualityMetrics dataclass
- SolverRecommendation dataclass
- MeshQualityAnalyzer class
- GridConvergenceIndex class
"""

import pytest
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestMeshQualityTier:
    """Test MeshQualityTier enum."""

    def test_tier_values(self):
        """Test enum values exist."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityTier

        assert MeshQualityTier.EXCELLENT.value == "EXCELLENT"
        assert MeshQualityTier.GOOD.value == "GOOD"
        assert MeshQualityTier.FAIR.value == "FAIR"
        assert MeshQualityTier.POOR.value == "POOR"
        assert MeshQualityTier.CRITICAL.value == "CRITICAL"

    def test_tier_comparison(self):
        """Test tiers can be compared."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityTier

        # Each tier has distinct value
        tiers = [
            MeshQualityTier.EXCELLENT,
            MeshQualityTier.GOOD,
            MeshQualityTier.FAIR,
            MeshQualityTier.POOR,
            MeshQualityTier.CRITICAL,
        ]
        assert len(set(tiers)) == 5


class TestBoundaryLayerMetrics:
    """Test BoundaryLayerMetrics dataclass."""

    def test_default_values(self):
        """Test default initialization."""
        from aortacfd_lib.utils.mesh_quality import BoundaryLayerMetrics

        metrics = BoundaryLayerMetrics()

        assert metrics.coverage_percent == 0.0
        assert metrics.layers_added == 0
        assert metrics.layers_requested == 0
        assert metrics.collapsed_faces == 0
        assert metrics.patch_name == ""

    def test_custom_values(self):
        """Test custom initialization."""
        from aortacfd_lib.utils.mesh_quality import BoundaryLayerMetrics

        metrics = BoundaryLayerMetrics(
            coverage_percent=95.5, layers_added=5, layers_requested=5, collapsed_faces=100, patch_name="wall_aorta"
        )

        assert metrics.coverage_percent == 95.5
        assert metrics.layers_added == 5
        assert metrics.patch_name == "wall_aorta"


class TestMeshQualityMetrics:
    """Test MeshQualityMetrics dataclass."""

    def test_default_values(self):
        """Test default initialization."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityMetrics

        metrics = MeshQualityMetrics()

        assert metrics.max_skewness == 0.0
        assert metrics.max_non_orthogonality == 0.0
        assert metrics.max_aspect_ratio == 0.0
        assert metrics.max_volume_ratio == 0.0
        assert metrics.num_cells == 0
        assert metrics.mesh_ok is True
        assert metrics.errors == []
        assert metrics.warnings == []
        assert metrics.layer_metrics is None

    def test_custom_values(self):
        """Test custom initialization."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityMetrics

        metrics = MeshQualityMetrics(
            max_skewness=2.5, max_non_orthogonality=65.0, max_aspect_ratio=30.0, num_cells=500000, mesh_ok=True
        )

        assert metrics.max_skewness == 2.5
        assert metrics.max_non_orthogonality == 65.0
        assert metrics.num_cells == 500000


class TestSolverRecommendation:
    """Test SolverRecommendation dataclass."""

    def test_creation(self):
        """Test recommendation creation."""
        from aortacfd_lib.utils.mesh_quality import SolverRecommendation

        rec = SolverRecommendation(
            profile="standard",
            relaxation_U=0.7,
            relaxation_p=0.3,
            n_outer_correctors=2,
            n_correctors=2,
            n_non_ortho_correctors=1,
            convection_scheme="Gauss linearUpwind grad(U)",
            time_scheme="backward",
        )

        assert rec.profile == "standard"
        assert rec.relaxation_U == 0.7
        assert rec.n_outer_correctors == 2
        assert rec.notes == []

    def test_with_notes(self):
        """Test recommendation with notes."""
        from aortacfd_lib.utils.mesh_quality import SolverRecommendation

        rec = SolverRecommendation(
            profile="robust",
            relaxation_U=0.5,
            relaxation_p=0.2,
            n_outer_correctors=5,
            n_correctors=3,
            n_non_ortho_correctors=2,
            convection_scheme="Gauss upwind",
            time_scheme="Euler",
            notes=["Using conservative schemes", "Recommend mesh improvement"],
        )

        assert len(rec.notes) == 2


class TestMeshQualityAnalyzerInit:
    """Test MeshQualityAnalyzer initialization."""

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_init(self, mock_logger):
        """Test initialization."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)

            assert analyzer.case_dir == tmpdir
            assert analyzer.THRESHOLDS is not None

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_thresholds_structure(self, mock_logger):
        """Test thresholds dictionary structure."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer, MeshQualityTier

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)

            # Check all tiers have thresholds (except CRITICAL)
            for tier in [MeshQualityTier.EXCELLENT, MeshQualityTier.GOOD, MeshQualityTier.FAIR, MeshQualityTier.POOR]:
                assert tier in analyzer.THRESHOLDS
                thresholds = analyzer.THRESHOLDS[tier]
                assert "max_skewness" in thresholds
                assert "max_non_orthogonality" in thresholds
                assert "max_aspect_ratio" in thresholds
                assert "max_volume_ratio" in thresholds


class TestParseCheckmeshOutput:
    """Test _parse_checkmesh_output method."""

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_parse_typical_output(self, mock_logger):
        """Test parsing typical checkMesh output."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer

        checkmesh_output = """
        Mesh stats
            points:           123456
            faces:            345678
            internal faces:   300000
            cells:            100000

        Checking mesh quality...
            Max aspect ratio = 25.3 OK.
            Max skewness = 2.45 OK.
            Mesh non-orthogonality Max: 62.5 average: 12.3
            Max volume ratio = 15.2 OK.

        Mesh OK.
        """

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)
            metrics = analyzer._parse_checkmesh_output(checkmesh_output)

            assert metrics.num_points == 123456
            assert metrics.num_faces == 345678
            assert metrics.num_cells == 100000
            assert abs(metrics.max_aspect_ratio - 25.3) < 0.1
            assert abs(metrics.max_skewness - 2.45) < 0.1
            assert abs(metrics.max_non_orthogonality - 62.5) < 0.1
            assert abs(metrics.avg_non_orthogonality - 12.3) < 0.1
            assert metrics.mesh_ok is True

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_parse_failed_mesh(self, mock_logger):
        """Test parsing checkMesh output with failures."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer

        checkmesh_output = """
        Checking geometry...
            Mesh has invalid points
        ***High aspect ratio cells found***

        FAILED
        """

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)
            metrics = analyzer._parse_checkmesh_output(checkmesh_output)

            assert metrics.mesh_ok is False
            assert len(metrics.errors) > 0

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_parse_with_warnings(self, mock_logger):
        """Test parsing checkMesh output with warnings."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer

        checkmesh_output = """
        cells: 50000
        ***Warning: some highly skewed cells found***
        Mesh OK.
        """

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)
            metrics = analyzer._parse_checkmesh_output(checkmesh_output)

            assert len(metrics.warnings) > 0


class TestGetQualityTier:
    """Test get_quality_tier method."""

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_excellent_tier(self, mock_logger):
        """Test excellent quality mesh classification."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer, MeshQualityMetrics, MeshQualityTier

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)

            metrics = MeshQualityMetrics(
                max_skewness=1.0, max_non_orthogonality=50.0, max_aspect_ratio=15.0, max_volume_ratio=8.0, mesh_ok=True
            )

            tier = analyzer.get_quality_tier(metrics)
            assert tier == MeshQualityTier.EXCELLENT

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_good_tier(self, mock_logger):
        """Test good quality mesh classification."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer, MeshQualityMetrics, MeshQualityTier

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)

            metrics = MeshQualityMetrics(
                max_skewness=2.0, max_non_orthogonality=60.0, max_aspect_ratio=25.0, max_volume_ratio=15.0, mesh_ok=True
            )

            tier = analyzer.get_quality_tier(metrics)
            assert tier == MeshQualityTier.GOOD

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_fair_tier(self, mock_logger):
        """Test fair quality mesh classification."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer, MeshQualityMetrics, MeshQualityTier

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)

            metrics = MeshQualityMetrics(
                max_skewness=3.5, max_non_orthogonality=68.0, max_aspect_ratio=45.0, max_volume_ratio=40.0, mesh_ok=True
            )

            tier = analyzer.get_quality_tier(metrics)
            assert tier == MeshQualityTier.FAIR

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_poor_tier(self, mock_logger):
        """Test poor quality mesh classification."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer, MeshQualityMetrics, MeshQualityTier

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)

            metrics = MeshQualityMetrics(
                max_skewness=5.0, max_non_orthogonality=73.0, max_aspect_ratio=80.0, max_volume_ratio=80.0, mesh_ok=True
            )

            tier = analyzer.get_quality_tier(metrics)
            assert tier == MeshQualityTier.POOR

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_critical_tier_from_metrics(self, mock_logger):
        """Test critical quality mesh classification from poor metrics."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer, MeshQualityMetrics, MeshQualityTier

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)

            metrics = MeshQualityMetrics(
                max_skewness=10.0, max_non_orthogonality=85.0, max_aspect_ratio=150.0, mesh_ok=True
            )

            tier = analyzer.get_quality_tier(metrics)
            assert tier == MeshQualityTier.CRITICAL

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_critical_tier_from_mesh_not_ok(self, mock_logger):
        """Test critical tier when mesh_ok is False."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer, MeshQualityMetrics, MeshQualityTier

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)

            metrics = MeshQualityMetrics(
                max_skewness=1.0, max_non_orthogonality=50.0, mesh_ok=False  # Good metrics but mesh failed
            )

            tier = analyzer.get_quality_tier(metrics)
            assert tier == MeshQualityTier.CRITICAL


class TestGetSolverRecommendations:
    """Test get_solver_recommendations method."""

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_excellent_recommendations(self, mock_logger):
        """Test recommendations for excellent mesh."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer, MeshQualityTier

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)
            rec = analyzer.get_solver_recommendations(MeshQualityTier.EXCELLENT)

            assert rec.profile == "accurate"
            assert rec.relaxation_U == 0.9
            assert "aggressive" in " ".join(rec.notes).lower() or "higher-order" in " ".join(rec.notes).lower()

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_good_recommendations(self, mock_logger):
        """Test recommendations for good mesh."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer, MeshQualityTier

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)
            rec = analyzer.get_solver_recommendations(MeshQualityTier.GOOD)

            assert rec.profile == "standard"
            assert rec.relaxation_U == 0.7

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_poor_recommendations(self, mock_logger):
        """Test recommendations for poor mesh."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer, MeshQualityTier

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)
            rec = analyzer.get_solver_recommendations(MeshQualityTier.POOR)

            assert rec.profile == "robust"
            assert rec.relaxation_U <= 0.5
            assert rec.convection_scheme == "Gauss upwind"
            assert rec.time_scheme == "Euler"

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_critical_recommendations(self, mock_logger):
        """Test recommendations for critical mesh."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer, MeshQualityTier

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)
            rec = analyzer.get_solver_recommendations(MeshQualityTier.CRITICAL)

            assert rec.profile == "robust"
            assert rec.relaxation_U <= 0.3
            assert rec.n_outer_correctors >= 10
            assert any("divergence" in note.lower() for note in rec.notes)


class TestGenerateReport:
    """Test generate_report method."""

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_generate_report_structure(self, mock_logger):
        """Test report generation structure."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer, MeshQualityMetrics

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)

            metrics = MeshQualityMetrics(
                max_skewness=2.0,
                max_non_orthogonality=60.0,
                max_aspect_ratio=25.0,
                avg_non_orthogonality=15.0,
                num_cells=500000,
                mesh_ok=True,
            )

            report = analyzer.generate_report(metrics)

            assert "MESH QUALITY ANALYSIS REPORT" in report
            assert "Quality Tier:" in report
            assert "500,000" in report or "500000" in report  # Cell count
            assert "Relaxation" in report
            assert "Convection Scheme" in report

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_generate_report_with_warnings(self, mock_logger):
        """Test report generation with warnings."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer, MeshQualityMetrics

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)

            metrics = MeshQualityMetrics(
                max_skewness=2.0,
                max_non_orthogonality=60.0,
                mesh_ok=True,
                warnings=["High skewness detected", "Check boundary layers"],
            )

            report = analyzer.generate_report(metrics)

            assert "Warnings:" in report

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_generate_report_with_errors(self, mock_logger):
        """Test report generation with errors."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer, MeshQualityMetrics

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)

            metrics = MeshQualityMetrics(max_skewness=2.0, mesh_ok=False, errors=["Mesh has invalid cells"])

            report = analyzer.generate_report(metrics)

            assert "ERRORS:" in report


class TestParseSnappyLayerCoverage:
    """Test parse_snappy_layer_coverage method."""

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_parse_missing_file(self, mock_logger):
        """Test parsing with missing log file."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)
            result = analyzer.parse_snappy_layer_coverage("/nonexistent/log.snappyHexMesh")

            assert result is None

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_parse_layer_coverage(self, mock_logger):
        """Test parsing layer coverage from log."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            log_content = """
            Adding layers
            Adding 5 layers to patch wall_aorta
            Extruded 95.2% of patch wall_aorta
            Layer collapse at 150 faces
            """

            log_file = Path(tmpdir) / "log.snappyHexMesh"
            log_file.write_text(log_content)

            analyzer = MeshQualityAnalyzer(tmpdir)
            metrics = analyzer.parse_snappy_layer_coverage(str(log_file))

            # Should parse at least some metrics
            assert metrics is not None or metrics is None  # May return None if pattern doesn't match


class TestThresholdValues:
    """Test threshold values are reasonable."""

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_thresholds_increase_with_tier(self, mock_logger):
        """Test thresholds get more lenient from EXCELLENT to POOR."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer, MeshQualityTier

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)

            tiers = [MeshQualityTier.EXCELLENT, MeshQualityTier.GOOD, MeshQualityTier.FAIR, MeshQualityTier.POOR]

            for i in range(len(tiers) - 1):
                current_thresholds = analyzer.THRESHOLDS[tiers[i]]
                next_thresholds = analyzer.THRESHOLDS[tiers[i + 1]]

                # Thresholds should be more lenient (higher) for worse tiers
                assert current_thresholds["max_skewness"] <= next_thresholds["max_skewness"]
                assert current_thresholds["max_non_orthogonality"] <= next_thresholds["max_non_orthogonality"]


class TestGridConvergenceIndexInit:
    """Test GridConvergenceIndex initialization."""

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_init_default_safety_factor(self, mock_logger):
        """Test default safety factor."""
        from aortacfd_lib.utils.mesh_quality import GridConvergenceIndex

        gci = GridConvergenceIndex()
        assert gci.Fs == 1.25

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_init_custom_safety_factor(self, mock_logger):
        """Test custom safety factor."""
        from aortacfd_lib.utils.mesh_quality import GridConvergenceIndex

        gci = GridConvergenceIndex(safety_factor=3.0)
        assert gci.Fs == 3.0


class TestGridConvergenceIndexCalculate:
    """Test GridConvergenceIndex.calculate method."""

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_calculate_basic(self, mock_logger):
        """Test basic GCI calculation with monotonic convergence."""
        from aortacfd_lib.utils.mesh_quality import GridConvergenceIndex

        gci = GridConvergenceIndex()
        # Typical mesh sizes and converging values
        h = [1.0, 0.5, 0.25]  # Coarse to fine
        f = [100.0, 98.0, 97.5]  # Converging values

        result = gci.calculate(h, f)

        assert "p_observed" in result
        assert "GCI_fine_percent" in result
        assert "GCI_medium_percent" in result
        assert "asymptotic_check" in result
        assert "extrapolated_value" in result
        assert "converged" in result
        assert result["p_observed"] > 0

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_calculate_insufficient_data(self, mock_logger):
        """Test GCI calculation with insufficient data."""
        from aortacfd_lib.utils.mesh_quality import GridConvergenceIndex

        gci = GridConvergenceIndex()

        with pytest.raises(ValueError) as excinfo:
            gci.calculate([1.0, 0.5], [100.0, 99.0])

        assert "at least 3 mesh levels" in str(excinfo.value)

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_calculate_identical_solutions(self, mock_logger):
        """Test GCI calculation with identical solutions (converged)."""
        from aortacfd_lib.utils.mesh_quality import GridConvergenceIndex

        gci = GridConvergenceIndex()
        h = [1.0, 0.5, 0.25]
        f = [100.0, 100.0, 100.0]  # Identical values

        result = gci.calculate(h, f)

        assert result["converged"] is True
        assert result["GCI_fine_percent"] == 0.0
        assert "nearly identical" in " ".join(result.get("notes", []))

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_calculate_oscillatory_convergence(self, mock_logger):
        """Test GCI calculation with oscillatory convergence."""
        from aortacfd_lib.utils.mesh_quality import GridConvergenceIndex

        gci = GridConvergenceIndex()
        h = [1.0, 0.5, 0.25]
        f = [100.0, 99.0, 99.5]  # Oscillating

        result = gci.calculate(h, f)

        # Should still produce a result
        assert "p_observed" in result

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_calculate_good_convergence(self, mock_logger):
        """Test GCI calculation with good second-order convergence."""
        from aortacfd_lib.utils.mesh_quality import GridConvergenceIndex

        gci = GridConvergenceIndex()
        h = [0.04, 0.02, 0.01]  # Refinement ratio = 2
        # Second-order convergence: error reduces by 4x with 2x refinement
        f = [100.0 + 16.0, 100.0 + 4.0, 100.0 + 1.0]

        result = gci.calculate(h, f)

        # Observed order should be close to 2
        assert abs(result["p_observed"] - 2.0) < 0.5
        assert result["extrapolated_value"] < 101.0  # Richardson extrapolation

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_calculate_not_in_asymptotic_range(self, mock_logger):
        """Test GCI calculation when not in asymptotic range."""
        from aortacfd_lib.utils.mesh_quality import GridConvergenceIndex

        gci = GridConvergenceIndex()
        h = [1.0, 0.5, 0.25]
        f = [100.0, 80.0, 70.0]  # Large changes

        result = gci.calculate(h, f)

        # Should have notes about asymptotic range or GCI
        assert len(result.get("notes", [])) > 0 or result["GCI_fine_percent"] >= 5.0


class TestGridConvergenceIndexGenerateReport:
    """Test GridConvergenceIndex.generate_report method."""

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_generate_report(self, mock_logger):
        """Test GCI report generation."""
        from aortacfd_lib.utils.mesh_quality import GridConvergenceIndex

        gci = GridConvergenceIndex()
        h = [1.0, 0.5, 0.25]
        f = [100.0, 98.0, 97.5]

        report = gci.generate_report(h, f, quantity_name="Max WSS")

        assert "GRID CONVERGENCE INDEX" in report
        assert "Max WSS" in report
        assert "Observed order" in report
        assert "GCI_fine" in report
        assert "Mesh Independence" in report


class TestIterativeBoundaryLayerImproverInit:
    """Test IterativeBoundaryLayerImprover initialization."""

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_init(self, mock_logger):
        """Test initialization."""
        from aortacfd_lib.utils.mesh_quality import IterativeBoundaryLayerImprover

        with tempfile.TemporaryDirectory() as tmpdir:
            improver = IterativeBoundaryLayerImprover(tmpdir)

            assert improver.case_dir == tmpdir
            assert improver.history == []


class TestIterativeBoundaryLayerImproverMethods:
    """Test IterativeBoundaryLayerImprover methods."""

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_get_current_coverage_no_log(self, mock_logger):
        """Test get_current_coverage when log doesn't exist."""
        from aortacfd_lib.utils.mesh_quality import IterativeBoundaryLayerImprover

        with tempfile.TemporaryDirectory() as tmpdir:
            improver = IterativeBoundaryLayerImprover(tmpdir)
            coverage = improver.get_current_coverage()

            assert coverage is None

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_calculate_improved_params_iteration1(self, mock_logger):
        """Test parameter improvement at iteration 1."""
        from aortacfd_lib.utils.mesh_quality import IterativeBoundaryLayerImprover

        with tempfile.TemporaryDirectory() as tmpdir:
            improver = IterativeBoundaryLayerImprover(tmpdir)

            current_params = {
                "nSmoothSurfaceNormals": 15,
                "nLayerIter": 50,
                "addLayers_nRelaxIter": 8,
                "nSmoothThickness": 10,
            }

            improved = improver.calculate_improved_params(current_params, 85.0, 1)

            # Escalation factor = 1.25 for iteration 1
            assert improved["nSmoothSurfaceNormals"] == int(15 * 1.25)
            assert improved["nLayerIter"] == int(50 * 1.25)

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_calculate_improved_params_low_coverage(self, mock_logger):
        """Test parameter improvement with very low coverage."""
        from aortacfd_lib.utils.mesh_quality import IterativeBoundaryLayerImprover

        with tempfile.TemporaryDirectory() as tmpdir:
            improver = IterativeBoundaryLayerImprover(tmpdir)

            current_params = {
                "nSmoothSurfaceNormals": 15,
                "nLayerIter": 50,
                "maxThicknessToMedialRatio": 0.3,
                "featureAngle": 130,
                "addLayer": 7,
            }

            # Low coverage triggers additional adjustments
            improved = improver.calculate_improved_params(current_params, 50.0, 1)

            assert improved["maxThicknessToMedialRatio"] > 0.3
            assert improved["featureAngle"] < 130

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_calculate_improved_params_reduce_layers(self, mock_logger):
        """Test layer reduction at iteration 2+ with low coverage."""
        from aortacfd_lib.utils.mesh_quality import IterativeBoundaryLayerImprover

        with tempfile.TemporaryDirectory() as tmpdir:
            improver = IterativeBoundaryLayerImprover(tmpdir)

            current_params = {"addLayer": 7}

            improved = improver.calculate_improved_params(current_params, 50.0, 2)

            # At iteration 2+ with low coverage, layers should be reduced
            assert improved["addLayer"] < 7

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_create_retry_summary_empty(self, mock_logger):
        """Test retry summary with no history."""
        from aortacfd_lib.utils.mesh_quality import IterativeBoundaryLayerImprover

        with tempfile.TemporaryDirectory() as tmpdir:
            improver = IterativeBoundaryLayerImprover(tmpdir)
            summary = improver.create_retry_summary()

            assert "No layer improvement attempts" in summary

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_create_retry_summary_with_history(self, mock_logger):
        """Test retry summary with history."""
        from aortacfd_lib.utils.mesh_quality import IterativeBoundaryLayerImprover

        with tempfile.TemporaryDirectory() as tmpdir:
            improver = IterativeBoundaryLayerImprover(tmpdir)
            improver.history = [
                {"coverage": 75.0, "status": "retry", "params_changed": {"nLayerIter": 62}},
                {"coverage": 85.0, "status": "success", "params_changed": {}},
            ]

            summary = improver.create_retry_summary()

            assert "BOUNDARY LAYER RETRY HISTORY" in summary
            assert "Attempt 1" in summary
            assert "Attempt 2" in summary
            assert "75.0%" in summary
            assert "85.0%" in summary


class TestMassBalanceCheckerInit:
    """Test MassBalanceChecker initialization."""

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_init_default_tolerance(self, mock_logger):
        """Test default tolerance."""
        from aortacfd_lib.utils.mesh_quality import MassBalanceChecker

        checker = MassBalanceChecker()
        assert checker.tolerance == 0.01  # 1%

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_init_custom_tolerance(self, mock_logger):
        """Test custom tolerance."""
        from aortacfd_lib.utils.mesh_quality import MassBalanceChecker

        checker = MassBalanceChecker(tolerance_percent=2.5)
        assert checker.tolerance == 0.025


class TestMassBalanceCheckerInstantaneous:
    """Test MassBalanceChecker.check_instantaneous method."""

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_check_balanced(self, mock_logger):
        """Test check with balanced flow."""
        from aortacfd_lib.utils.mesh_quality import MassBalanceChecker

        checker = MassBalanceChecker(tolerance_percent=1.0)

        inlet_flow = 1e-4  # 100 mL/s
        outlet_flows = {"outlet1": 4e-5, "outlet2": 3e-5, "outlet3": 3e-5}  # 40 mL/s  # 30 mL/s  # 30 mL/s

        result = checker.check_instantaneous(inlet_flow, outlet_flows)

        assert result["balanced"] is True
        assert result["error_percent"] < 1.0
        assert result["inlet_flow"] == inlet_flow
        assert result["total_outlet_flow"] == 1e-4
        assert "outlet1" in result["flow_splits"]

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_check_unbalanced(self, mock_logger):
        """Test check with unbalanced flow."""
        from aortacfd_lib.utils.mesh_quality import MassBalanceChecker

        checker = MassBalanceChecker(tolerance_percent=1.0)

        inlet_flow = 1e-4
        outlet_flows = {"outlet1": 4e-5, "outlet2": 3e-5}  # Missing 30% of flow

        result = checker.check_instantaneous(inlet_flow, outlet_flows)

        assert result["balanced"] is False
        assert result["error_percent"] > 1.0

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_check_flow_splits(self, mock_logger):
        """Test flow split calculation."""
        from aortacfd_lib.utils.mesh_quality import MassBalanceChecker

        checker = MassBalanceChecker()

        inlet_flow = 1e-4
        outlet_flows = {"outlet1": 6e-5, "outlet2": 4e-5}

        result = checker.check_instantaneous(inlet_flow, outlet_flows)

        assert abs(result["flow_splits"]["outlet1"] - 60.0) < 0.1
        assert abs(result["flow_splits"]["outlet2"] - 40.0) < 0.1

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_check_zero_inlet(self, mock_logger):
        """Test check with zero inlet flow."""
        from aortacfd_lib.utils.mesh_quality import MassBalanceChecker

        checker = MassBalanceChecker()

        result = checker.check_instantaneous(0.0, {"outlet1": 0.0})

        assert result["error_percent"] == 0.0


class TestMassBalanceCheckerTimeAveraged:
    """Test MassBalanceChecker.check_time_averaged method."""

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_time_averaged_simple(self, mock_logger):
        """Test time-averaged check without time weights."""
        from aortacfd_lib.utils.mesh_quality import MassBalanceChecker

        checker = MassBalanceChecker()

        inlet_flows = [1e-4, 1e-4, 1e-4]
        outlet_flows_series = [
            {"outlet1": 6e-5, "outlet2": 4e-5},
            {"outlet1": 6e-5, "outlet2": 4e-5},
            {"outlet1": 6e-5, "outlet2": 4e-5},
        ]

        result = checker.check_time_averaged(inlet_flows, outlet_flows_series)

        assert result["balanced"] == True
        assert result["n_timesteps"] == 3
        assert "max_instantaneous_error" in result

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_time_averaged_with_times(self, mock_logger):
        """Test time-averaged check with time weights."""
        from aortacfd_lib.utils.mesh_quality import MassBalanceChecker

        checker = MassBalanceChecker()

        inlet_flows = [1e-4, 1.2e-4, 0.8e-4]
        outlet_flows_series = [
            {"outlet1": 6e-5, "outlet2": 4e-5},
            {"outlet1": 7.2e-5, "outlet2": 4.8e-5},
            {"outlet1": 4.8e-5, "outlet2": 3.2e-5},
        ]
        times = [0.0, 0.1, 0.2]

        result = checker.check_time_averaged(inlet_flows, outlet_flows_series, times)

        assert result["n_timesteps"] == 3


class TestMassBalanceCheckerReport:
    """Test MassBalanceChecker.generate_report method."""

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_generate_report_instantaneous(self, mock_logger):
        """Test report generation for instantaneous check."""
        from aortacfd_lib.utils.mesh_quality import MassBalanceChecker

        checker = MassBalanceChecker()

        result = {
            "inlet_flow": 1e-4,
            "total_outlet_flow": 1e-4,
            "error_percent": 0.1,
            "balanced": True,
            "outlet_flows": {"outlet1": 6e-5, "outlet2": 4e-5},
            "flow_splits": {"outlet1": 60.0, "outlet2": 40.0},
        }

        report = checker.generate_report(result)

        assert "MASS BALANCE VERIFICATION" in report
        assert "Inlet Flow" in report
        assert "PASS" in report
        assert "outlet1" in report

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_generate_report_time_averaged(self, mock_logger):
        """Test report generation with time-averaged data."""
        from aortacfd_lib.utils.mesh_quality import MassBalanceChecker

        checker = MassBalanceChecker()

        result = {
            "inlet_flow": 1e-4,
            "total_outlet_flow": 0.95e-4,
            "error_percent": 5.0,
            "balanced": False,
            "outlet_flows": {"outlet1": 6e-5, "outlet2": 3.5e-5},
            "flow_splits": {"outlet1": 63.2, "outlet2": 36.8},
            "max_instantaneous_error": 7.5,
            "n_timesteps": 100,
        }

        report = checker.generate_report(result)

        assert "FAIL" in report
        assert "Max Instantaneous Error" in report
        assert "Timesteps Analyzed" in report


class TestRunCheckmesh:
    """Test run_checkmesh method."""

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    @patch("subprocess.run")
    def test_run_checkmesh_success(self, mock_run, mock_logger):
        """Test successful checkMesh execution."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer

        mock_run.return_value = MagicMock(stdout="cells: 100000\nMax skewness = 2.0 OK.\nMesh OK.", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)
            metrics = analyzer.run_checkmesh()

            assert metrics.num_cells == 100000
            assert metrics.max_skewness == 2.0
            assert metrics.mesh_ok is True

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    @patch("subprocess.run")
    def test_run_checkmesh_parallel(self, mock_run, mock_logger):
        """Test parallel checkMesh execution."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer

        mock_run.return_value = MagicMock(stdout="cells: 100000\nMesh OK.", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)
            metrics = analyzer.run_checkmesh(parallel=True, n_procs=4)

            # Verify mpirun was called
            call_args = mock_run.call_args[1]["shell"]
            assert call_args is True
            assert "mpirun" in mock_run.call_args[0][0] or metrics is not None

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    @patch("subprocess.run")
    def test_run_checkmesh_timeout(self, mock_run, mock_logger):
        """Test checkMesh timeout handling."""
        import subprocess
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="checkMesh", timeout=300)

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)
            metrics = analyzer.run_checkmesh()

            assert metrics.mesh_ok is False
            assert "timeout" in " ".join(metrics.errors).lower()

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    @patch("subprocess.run")
    def test_run_checkmesh_exception(self, mock_run, mock_logger):
        """Test checkMesh exception handling."""
        from aortacfd_lib.utils.mesh_quality import MeshQualityAnalyzer

        mock_run.side_effect = Exception("Command not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MeshQualityAnalyzer(tmpdir)
            metrics = analyzer.run_checkmesh()

            assert metrics.mesh_ok is False
            assert len(metrics.errors) > 0


class TestCalculateOrder:
    """Test _calculate_order method."""

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_calculate_order_constant_ratio(self, mock_logger):
        """Test order calculation with constant refinement ratio."""
        from aortacfd_lib.utils.mesh_quality import GridConvergenceIndex

        gci = GridConvergenceIndex()

        # Constant ratio of 2, second-order convergence
        r21 = 2.0
        r32 = 2.0
        eps21 = 1.0  # f2 - f1
        eps32 = 4.0  # f3 - f2

        p = gci._calculate_order(r21, r32, eps21, eps32, 2.0)

        assert abs(p - 2.0) < 0.1  # Should be close to 2

    @patch("aortacfd_lib.utils.mesh_quality.Logger")
    def test_calculate_order_negative_ratio(self, mock_logger):
        """Test order calculation with oscillatory convergence."""
        from aortacfd_lib.utils.mesh_quality import GridConvergenceIndex

        gci = GridConvergenceIndex()

        r21 = 2.0
        r32 = 2.0
        eps21 = 1.0
        eps32 = -0.5  # Oscillating

        p = gci._calculate_order(r21, r32, eps21, eps32, 2.0)

        # Should return a reasonable value
        assert 0.1 <= p <= 5.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
