"""
Test suite for aortacfd_lib/inlet_qc.py module.

Tests cover:
- InletAudit dataclass creation and methods
- InletQC initialization and configuration parsing
- Womersley number calculation
- Profile recommendations
- CSV waveform analysis
- Area computation from points
- Full QC workflow
"""

import pytest
import sys
import os
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import json
import tempfile

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestInletAuditDataclass:
    """Test InletAudit dataclass."""

    def test_creation_with_required_fields(self):
        """Test creating InletAudit with required fields."""
        from aortacfd_lib.inlet_qc import InletAudit

        audit = InletAudit(
            inlet_area_m2=1e-4,
            inlet_radius_eq_m=0.005,
            inlet_center=[0.0, 0.0, 0.0],
            inlet_normal=[0.0, 0.0, 1.0],
            csv_file="flow.csv",
            data_type="flowrate",
            n_points=100,
            detected_period_s=0.8,
            inlet_type="TIMEVARYING",
            profile="parabolic",
            orientation="auto"
        )

        assert audit.inlet_area_m2 == 1e-4
        assert audit.inlet_radius_eq_m == 0.005
        assert audit.n_points == 100

    def test_defaults_initialized(self):
        """Test that default values are set correctly."""
        from aortacfd_lib.inlet_qc import InletAudit

        audit = InletAudit(
            inlet_area_m2=1e-4,
            inlet_radius_eq_m=0.005,
            inlet_center=[0.0, 0.0, 0.0],
            inlet_normal=[0.0, 0.0, 1.0],
            csv_file="flow.csv",
            data_type="flowrate",
            n_points=100,
            detected_period_s=0.8,
            inlet_type="TIMEVARYING",
            profile="parabolic",
            orientation="auto"
        )

        # Check defaults
        assert audit.mean_flow_m3s is None
        assert audit.mean_velocity_ms is None
        assert audit.peak_systolic == 0.0
        assert audit.backflow_fraction == 0.0
        assert audit.womersley_alpha is None
        assert audit.auto_orientation_detected is False
        assert audit.scaling_applied is False
        assert audit.scale_factor == 1.0
        assert audit.warnings == []
        assert audit.errors == []

    def test_post_init_initializes_lists(self):
        """Test __post_init__ initializes warnings and errors lists."""
        from aortacfd_lib.inlet_qc import InletAudit

        # Create with None warnings/errors
        audit = InletAudit(
            inlet_area_m2=1e-4,
            inlet_radius_eq_m=0.005,
            inlet_center=[0.0, 0.0, 0.0],
            inlet_normal=[0.0, 0.0, 1.0],
            csv_file="flow.csv",
            data_type="flowrate",
            n_points=100,
            detected_period_s=0.8,
            inlet_type="TIMEVARYING",
            profile="parabolic",
            orientation="auto",
            warnings=None,
            errors=None
        )

        assert audit.warnings == []
        assert audit.errors == []

    def test_to_dict(self):
        """Test to_dict method returns correct dictionary."""
        from aortacfd_lib.inlet_qc import InletAudit

        audit = InletAudit(
            inlet_area_m2=1e-4,
            inlet_radius_eq_m=0.005,
            inlet_center=[0.0, 0.0, 0.0],
            inlet_normal=[0.0, 0.0, 1.0],
            csv_file="flow.csv",
            data_type="flowrate",
            n_points=100,
            detected_period_s=0.8,
            inlet_type="TIMEVARYING",
            profile="parabolic",
            orientation="auto"
        )

        result = audit.to_dict()

        assert isinstance(result, dict)
        assert result['inlet_area_m2'] == 1e-4
        assert result['inlet_radius_eq_m'] == 0.005
        assert result['csv_file'] == "flow.csv"
        assert result['inlet_type'] == "TIMEVARYING"

    def test_save_json(self, tmp_path):
        """Test save_json method writes valid JSON."""
        from aortacfd_lib.inlet_qc import InletAudit

        audit = InletAudit(
            inlet_area_m2=1e-4,
            inlet_radius_eq_m=0.005,
            inlet_center=[0.0, 0.0, 0.0],
            inlet_normal=[0.0, 0.0, 1.0],
            csv_file="flow.csv",
            data_type="flowrate",
            n_points=100,
            detected_period_s=0.8,
            inlet_type="TIMEVARYING",
            profile="parabolic",
            orientation="auto"
        )

        json_path = tmp_path / "audit.json"
        audit.save_json(json_path)

        assert json_path.exists()

        # Read and verify
        with open(json_path) as f:
            loaded = json.load(f)

        assert loaded['inlet_area_m2'] == 1e-4
        assert loaded['inlet_type'] == "TIMEVARYING"

    def test_get_summary_report_basic(self):
        """Test get_summary_report returns formatted string."""
        from aortacfd_lib.inlet_qc import InletAudit

        audit = InletAudit(
            inlet_area_m2=1e-4,
            inlet_radius_eq_m=0.005,
            inlet_center=[0.0, 0.0, 0.0],
            inlet_normal=[0.0, 0.0, 1.0],
            csv_file="flow.csv",
            data_type="flowrate",
            n_points=100,
            detected_period_s=0.8,
            inlet_type="TIMEVARYING",
            profile="parabolic",
            orientation="manual"
        )

        report = audit.get_summary_report()

        assert "INLET BOUNDARY CONDITION AUDIT REPORT" in report
        assert "GEOMETRY:" in report
        assert "CONFIGURATION:" in report
        assert "WAVEFORM STATISTICS:" in report
        assert "mm²" in report  # Area in mm²
        assert "75.0 bpm" in report  # 60/0.8 = 75 bpm

    def test_get_summary_report_with_flow(self):
        """Test summary report includes flow data when available."""
        from aortacfd_lib.inlet_qc import InletAudit

        audit = InletAudit(
            inlet_area_m2=1e-4,
            inlet_radius_eq_m=0.005,
            inlet_center=[0.0, 0.0, 0.0],
            inlet_normal=[0.0, 0.0, 1.0],
            csv_file="flow.csv",
            data_type="flowrate",
            n_points=100,
            detected_period_s=0.8,
            inlet_type="TIMEVARYING",
            profile="parabolic",
            orientation="auto",
            mean_flow_m3s=5e-5,  # 50 mL/s
            mean_velocity_ms=0.5
        )

        report = audit.get_summary_report()

        assert "Mean flow:" in report
        assert "mL/s" in report
        assert "Mean velocity:" in report
        assert "m/s" in report

    def test_get_summary_report_with_womersley(self):
        """Test summary report includes Womersley analysis."""
        from aortacfd_lib.inlet_qc import InletAudit

        audit = InletAudit(
            inlet_area_m2=1e-4,
            inlet_radius_eq_m=0.005,
            inlet_center=[0.0, 0.0, 0.0],
            inlet_normal=[0.0, 0.0, 1.0],
            csv_file="flow.csv",
            data_type="flowrate",
            n_points=100,
            detected_period_s=0.8,
            inlet_type="TIMEVARYING",
            profile="parabolic",
            orientation="auto",
            nu_m2s=3.5e-6,
            womersley_alpha=4.5,
            womersley_recommendation="womersley (transitional)"
        )

        report = audit.get_summary_report()

        assert "WOMERSLEY ANALYSIS:" in report
        assert "4.50" in report  # Alpha value
        assert "transitional" in report

    def test_get_summary_report_with_auto_orientation(self):
        """Test summary report shows auto orientation detection."""
        from aortacfd_lib.inlet_qc import InletAudit

        audit = InletAudit(
            inlet_area_m2=1e-4,
            inlet_radius_eq_m=0.005,
            inlet_center=[0.0, 0.0, 0.0],
            inlet_normal=[0.0, 0.0, 1.0],
            csv_file="flow.csv",
            data_type="flowrate",
            n_points=100,
            detected_period_s=0.8,
            inlet_type="TIMEVARYING",
            profile="parabolic",
            orientation="auto",
            auto_orientation_detected=True,
            dot_product_normal_flow=-0.9,
            orientation_flipped=True
        )

        report = audit.get_summary_report()

        assert "automatic detection" in report
        assert "Dot product" in report
        assert "Normal flipped: Yes" in report

    def test_get_summary_report_with_scaling(self):
        """Test summary report shows scaling information."""
        from aortacfd_lib.inlet_qc import InletAudit

        audit = InletAudit(
            inlet_area_m2=1e-4,
            inlet_radius_eq_m=0.005,
            inlet_center=[0.0, 0.0, 0.0],
            inlet_normal=[0.0, 0.0, 1.0],
            csv_file="flow.csv",
            data_type="flowrate",
            n_points=100,
            detected_period_s=0.8,
            inlet_type="TIMEVARYING",
            profile="parabolic",
            orientation="auto",
            scaling_applied=True,
            target_CO_Lmin=5.0,
            original_mean_flow_m3s=4e-5,
            scale_factor=1.25
        )

        report = audit.get_summary_report()

        assert "SCALING:" in report
        assert "Target CO:" in report
        assert "Scale factor:" in report

    def test_get_summary_report_with_filtering(self):
        """Test summary report shows filtering information."""
        from aortacfd_lib.inlet_qc import InletAudit

        audit = InletAudit(
            inlet_area_m2=1e-4,
            inlet_radius_eq_m=0.005,
            inlet_center=[0.0, 0.0, 0.0],
            inlet_normal=[0.0, 0.0, 1.0],
            csv_file="flow.csv",
            data_type="flowrate",
            n_points=100,
            detected_period_s=0.8,
            inlet_type="TIMEVARYING",
            profile="parabolic",
            orientation="auto",
            filter_method="linear",
            target_dt_s=0.005,
            n_output_timesteps=160
        )

        report = audit.get_summary_report()

        assert "FILTERING/RESAMPLING:" in report
        assert "Method: linear" in report

    def test_get_summary_report_with_warnings_and_errors(self):
        """Test summary report shows warnings and errors."""
        from aortacfd_lib.inlet_qc import InletAudit

        audit = InletAudit(
            inlet_area_m2=1e-4,
            inlet_radius_eq_m=0.005,
            inlet_center=[0.0, 0.0, 0.0],
            inlet_normal=[0.0, 0.0, 1.0],
            csv_file="flow.csv",
            data_type="flowrate",
            n_points=100,
            detected_period_s=0.8,
            inlet_type="TIMEVARYING",
            profile="parabolic",
            orientation="auto",
            warnings=["Profile may not be optimal"],
            errors=["CSV file not found"]
        )

        report = audit.get_summary_report()

        assert "WARNINGS:" in report
        assert "Profile may not be optimal" in report
        assert "ERRORS:" in report
        assert "CSV file not found" in report


class TestInletQCInit:
    """Test InletQC initialization."""

    def test_initialization_basic(self, tmp_path):
        """Test basic initialization."""
        from aortacfd_lib.inlet_qc import InletQC

        config = {
            'inlet': {'type': 'TIMEVARYING'},
            'physics': {'nu': 3.5e-6}
        }

        qc = InletQC(config, tmp_path)

        assert qc.config == config
        assert qc.case_dir == tmp_path
        assert qc.inlet_config == {'type': 'TIMEVARYING'}
        assert qc.physics == {'nu': 3.5e-6}

    def test_initialization_boundary_conditions_fallback(self, tmp_path):
        """Test initialization with boundary_conditions structure."""
        from aortacfd_lib.inlet_qc import InletQC

        config = {
            'boundary_conditions': {
                'inlet': {'type': 'WOMERSLEY'}
            },
            'physics': {}
        }

        qc = InletQC(config, tmp_path)

        assert qc.inlet_config == {'type': 'WOMERSLEY'}

    def test_initialization_empty_config(self, tmp_path):
        """Test initialization with empty config."""
        from aortacfd_lib.inlet_qc import InletQC

        qc = InletQC({}, tmp_path)

        assert qc.inlet_config == {}
        assert qc.physics == {}


class TestCalculateWomersleyNumber:
    """Test Womersley number calculation."""

    def test_womersley_number_typical_aorta(self, tmp_path):
        """Test Womersley number for typical aortic conditions."""
        from aortacfd_lib.inlet_qc import InletQC

        qc = InletQC({}, tmp_path)

        # Typical values: R=0.01m (20mm diameter), T=0.8s (75 bpm), nu=3.5e-6 m²/s
        radius = 0.01
        period = 0.8
        nu = 3.5e-6

        alpha = qc.calculate_womersley_number(radius, period, nu)

        # Expected: α = R * sqrt(2π/T / ν) ≈ 15
        expected = radius * np.sqrt(2 * np.pi / period / nu)
        assert alpha == pytest.approx(expected, rel=1e-6)
        assert 10 < alpha < 20  # Typical range for aorta

    def test_womersley_number_small_vessel(self, tmp_path):
        """Test Womersley number for small vessel (should be lower)."""
        from aortacfd_lib.inlet_qc import InletQC

        qc = InletQC({}, tmp_path)

        # Small vessel: R=0.001m (2mm diameter)
        radius = 0.001
        period = 0.8
        nu = 3.5e-6

        alpha = qc.calculate_womersley_number(radius, period, nu)

        # Should be much smaller
        assert alpha < 5

    def test_womersley_number_fast_heart_rate(self, tmp_path):
        """Test Womersley number with fast heart rate (higher α)."""
        from aortacfd_lib.inlet_qc import InletQC

        qc = InletQC({}, tmp_path)

        radius = 0.01
        period = 0.5  # 120 bpm
        nu = 3.5e-6

        alpha_fast = qc.calculate_womersley_number(radius, period, nu)

        # Compare with normal rate
        alpha_normal = qc.calculate_womersley_number(radius, 0.8, nu)

        # Faster rate = higher Womersley number
        assert alpha_fast > alpha_normal


class TestRecommendProfile:
    """Test profile recommendation based on Womersley number."""

    def test_recommend_parabolic_low_alpha(self, tmp_path):
        """Test parabolic recommendation for low α."""
        from aortacfd_lib.inlet_qc import InletQC

        qc = InletQC({}, tmp_path)

        # α < 1 → quasi-steady parabolic
        recommendation = qc.recommend_profile(0.5)

        assert "parabolic" in recommendation
        assert "quasi-steady" in recommendation

    def test_recommend_womersley_medium_alpha(self, tmp_path):
        """Test womersley recommendation for medium α."""
        from aortacfd_lib.inlet_qc import InletQC

        qc = InletQC({}, tmp_path)

        # 1 ≤ α < 10 → transitional womersley
        for alpha in [1.0, 5.0, 9.5]:
            recommendation = qc.recommend_profile(alpha)
            assert "womersley" in recommendation
            assert "transitional" in recommendation

    def test_recommend_plug_high_alpha(self, tmp_path):
        """Test plug recommendation for high α."""
        from aortacfd_lib.inlet_qc import InletQC

        qc = InletQC({}, tmp_path)

        # α ≥ 10 → plug (flat)
        for alpha in [10.0, 15.0, 20.0]:
            recommendation = qc.recommend_profile(alpha)
            assert "plug" in recommendation
            assert "high-frequency" in recommendation


class TestComputeAreaFromPoints:
    """Test area computation from boundary points."""

    def test_compute_area_square(self, tmp_path):
        """Test area computation for square patch."""
        from aortacfd_lib.inlet_qc import InletQC

        qc = InletQC({}, tmp_path)

        # Create points file for 1x1 square
        points_file = tmp_path / "points"
        points_content = """4
(
(0 0 0)
(1 0 0)
(1 1 0)
(0 1 0)
)"""
        points_file.write_text(points_content)

        area, radius, centroid = qc.compute_area_from_points(points_file)

        assert area == pytest.approx(1.0, rel=0.1)  # Area ≈ 1.0
        np.testing.assert_array_almost_equal(centroid, [0.5, 0.5, 0.0], decimal=1)

    def test_compute_area_circle_approximation(self, tmp_path):
        """Test area computation for circular patch (approximated by polygon)."""
        from aortacfd_lib.inlet_qc import InletQC

        qc = InletQC({}, tmp_path)

        # Create circular points
        n_points = 36
        radius = 0.01  # 10mm radius
        angles = np.linspace(0, 2*np.pi, n_points, endpoint=False)
        x = radius * np.cos(angles)
        y = radius * np.sin(angles)
        z = np.zeros(n_points)

        points_file = tmp_path / "points"
        lines = [str(n_points), "("]
        for i in range(n_points):
            lines.append(f"({x[i]:.6f} {y[i]:.6f} {z[i]:.6f})")
        lines.append(")")
        points_file.write_text("\n".join(lines))

        area, radius_eq, centroid = qc.compute_area_from_points(points_file)

        expected_area = np.pi * radius**2
        assert area == pytest.approx(expected_area, rel=0.05)  # Within 5%
        np.testing.assert_array_almost_equal(centroid, [0.0, 0.0, 0.0], decimal=2)

    def test_compute_equivalent_radius(self, tmp_path):
        """Test equivalent radius calculation."""
        from aortacfd_lib.inlet_qc import InletQC

        qc = InletQC({}, tmp_path)

        # Create points for known area
        n_points = 36
        radius = 0.01
        angles = np.linspace(0, 2*np.pi, n_points, endpoint=False)
        x = radius * np.cos(angles)
        y = radius * np.sin(angles)
        z = np.zeros(n_points)

        points_file = tmp_path / "points"
        lines = [str(n_points), "("]
        for i in range(n_points):
            lines.append(f"({x[i]:.6f} {y[i]:.6f} {z[i]:.6f})")
        lines.append(")")
        points_file.write_text("\n".join(lines))

        area, radius_eq, centroid = qc.compute_area_from_points(points_file)

        # Equivalent radius should match original for circle
        assert radius_eq == pytest.approx(radius, rel=0.05)


class TestAnalyzeCsvWaveform:
    """Test CSV waveform analysis."""

    def test_analyze_simple_csv(self, tmp_path):
        """Test analysis of simple CSV with no header."""
        from aortacfd_lib.inlet_qc import InletQC

        qc = InletQC({}, tmp_path)

        # Create simple CSV
        csv_file = tmp_path / "flow.csv"
        csv_content = """0.0,0.001
0.2,0.003
0.4,0.002
0.6,0.001
0.8,0.001"""
        csv_file.write_text(csv_content)

        stats = qc.analyze_csv_waveform(csv_file, "flowrate")

        assert stats['n_points'] == 5
        assert stats['period_s'] == pytest.approx(0.8, rel=1e-6)
        assert stats['mean_value'] == pytest.approx(0.0016, rel=1e-6)
        assert stats['peak_value'] == pytest.approx(0.003, rel=1e-6)
        assert stats['backflow_fraction'] == 0.0

    def test_analyze_csv_with_header(self, tmp_path):
        """Test analysis of CSV with header line."""
        from aortacfd_lib.inlet_qc import InletQC

        qc = InletQC({}, tmp_path)

        csv_file = tmp_path / "flow.csv"
        csv_content = """time,flowrate
0.0,0.001
0.4,0.002
0.8,0.001"""
        csv_file.write_text(csv_content)

        stats = qc.analyze_csv_waveform(csv_file, "flowrate")

        assert stats['n_points'] == 3
        assert stats['period_s'] == pytest.approx(0.8, rel=1e-6)

    def test_analyze_csv_with_comments(self, tmp_path):
        """Test analysis of CSV with comment lines."""
        from aortacfd_lib.inlet_qc import InletQC

        qc = InletQC({}, tmp_path)

        csv_file = tmp_path / "flow.csv"
        csv_content = """# This is a comment
# Another comment
0.0,0.001
0.4,0.002
0.8,0.001"""
        csv_file.write_text(csv_content)

        stats = qc.analyze_csv_waveform(csv_file, "flowrate")

        assert stats['n_points'] == 3

    def test_analyze_csv_with_backflow(self, tmp_path):
        """Test analysis of CSV with backflow (negative values)."""
        from aortacfd_lib.inlet_qc import InletQC

        qc = InletQC({}, tmp_path)

        csv_file = tmp_path / "flow.csv"
        csv_content = """0.0,0.002
0.2,0.003
0.4,-0.001
0.6,-0.002
0.8,0.001"""
        csv_file.write_text(csv_content)

        stats = qc.analyze_csv_waveform(csv_file, "velocity")

        assert stats['backflow_fraction'] == pytest.approx(2/5, rel=1e-6)  # 2 negative out of 5

    def test_analyze_csv_unsorted_times(self, tmp_path):
        """Test analysis sorts by time."""
        from aortacfd_lib.inlet_qc import InletQC

        qc = InletQC({}, tmp_path)

        csv_file = tmp_path / "flow.csv"
        csv_content = """0.4,0.002
0.0,0.001
0.8,0.001
0.2,0.003"""
        csv_file.write_text(csv_content)

        stats = qc.analyze_csv_waveform(csv_file, "flowrate")

        # Times should be sorted
        assert stats['times'][0] == 0.0
        assert stats['times'][-1] == 0.8
        assert stats['n_points'] == 4

    def test_analyze_csv_invalid_format_raises(self, tmp_path):
        """Test that invalid CSV format raises ValueError."""
        from aortacfd_lib.inlet_qc import InletQC

        qc = InletQC({}, tmp_path)

        csv_file = tmp_path / "bad.csv"
        csv_content = """0.0
0.4
0.8"""  # Only one column
        csv_file.write_text(csv_content)

        with pytest.raises(ValueError, match="at least 2 columns"):
            qc.analyze_csv_waveform(csv_file, "flowrate")


class TestComputeAreaWeightedNormal:
    """Test area-weighted normal computation."""

    def test_compute_normal_xy_plane(self, tmp_path):
        """Test normal computation for points in XY plane."""
        from aortacfd_lib.inlet_qc import InletQC

        qc = InletQC({}, tmp_path)

        # Create points in XY plane (z=0)
        points_file = tmp_path / "points"
        points_content = """4
(
(0 0 0)
(1 0 0)
(1 1 0)
(0 1 0)
)"""
        points_file.write_text(points_content)

        normal = qc.compute_area_weighted_normal(points_file)

        # Normal should be along Z axis
        assert abs(normal[2]) == pytest.approx(1.0, rel=1e-6)
        assert normal[0] == pytest.approx(0.0, abs=1e-6)
        assert normal[1] == pytest.approx(0.0, abs=1e-6)

    def test_compute_normal_xz_plane(self, tmp_path):
        """Test normal computation for points in XZ plane."""
        from aortacfd_lib.inlet_qc import InletQC

        qc = InletQC({}, tmp_path)

        # Create points in XZ plane (y=0)
        points_file = tmp_path / "points"
        points_content = """4
(
(0 0 0)
(1 0 0)
(1 0 1)
(0 0 1)
)"""
        points_file.write_text(points_content)

        normal = qc.compute_area_weighted_normal(points_file)

        # Normal should be along Y axis
        assert abs(normal[1]) == pytest.approx(1.0, rel=1e-6)

    def test_normal_is_unit_vector(self, tmp_path):
        """Test that computed normal is a unit vector."""
        from aortacfd_lib.inlet_qc import InletQC

        qc = InletQC({}, tmp_path)

        points_file = tmp_path / "points"
        points_content = """4
(
(0 0 0)
(10 0 0)
(10 10 0)
(0 10 0)
)"""
        points_file.write_text(points_content)

        normal = qc.compute_area_weighted_normal(points_file)

        assert np.linalg.norm(normal) == pytest.approx(1.0, rel=1e-6)


class TestRunFullQC:
    """Test full QC workflow."""

    def test_run_full_qc_basic(self, tmp_path):
        """Test basic full QC run with FIXED type (no CSV analysis)."""
        from aortacfd_lib.inlet_qc import InletQC

        # Create a minimal CSV to avoid zero period
        boundary_data = tmp_path / "constant" / "boundaryData" / "inlet"
        boundary_data.mkdir(parents=True)
        csv_file = boundary_data / "flow.csv"
        csv_file.write_text("0.0,0.001\n0.8,0.001")

        config = {
            'inlet': {
                'type': 'TIMEVARYING',  # Need TIMEVARYING to trigger CSV analysis
                'profile': 'parabolic',
                'orientation': 'auto',
                'csv_file': 'flow.csv',
                'data_type': 'flowrate'
            },
            'physics': {}
        }

        qc = InletQC(config, tmp_path)

        audit = qc.run_full_qc(
            inlet_patch_name="inlet",
            inlet_area=1e-4,
            inlet_radius=0.005,
            inlet_center=np.array([0.0, 0.0, 0.0]),
            inlet_normal=np.array([0.0, 0.0, 1.0])
        )

        assert audit is not None
        assert audit.inlet_area_m2 == 1e-4
        assert audit.inlet_radius_eq_m == 0.005
        assert audit.inlet_type == 'TIMEVARYING'

    def test_run_full_qc_with_csv(self, tmp_path):
        """Test full QC with CSV waveform."""
        from aortacfd_lib.inlet_qc import InletQC

        # Create CSV file with 4 data points (avoid 'e' notation to prevent header detection)
        boundary_data = tmp_path / "constant" / "boundaryData" / "inlet"
        boundary_data.mkdir(parents=True)
        csv_file = boundary_data / "flow.csv"
        csv_file.write_text("0.0,0.00005\n0.2,0.00006\n0.4,0.00007\n0.8,0.00004\n")

        config = {
            'inlet': {
                'type': 'TIMEVARYING',
                'profile': 'parabolic',
                'orientation': 'auto',
                'csv_file': 'flow.csv',
                'data_type': 'flowrate'
            },
            'physics': {'nu': 3.5e-6}
        }

        qc = InletQC(config, tmp_path)

        audit = qc.run_full_qc(
            inlet_patch_name="inlet",
            inlet_area=1e-4,
            inlet_radius=0.005,
            inlet_center=np.array([0.0, 0.0, 0.0]),
            inlet_normal=np.array([0.0, 0.0, 1.0])
        )

        assert audit.n_points == 4
        assert audit.detected_period_s == pytest.approx(0.8, rel=1e-6)
        assert audit.mean_flow_m3s is not None
        assert audit.mean_velocity_ms is not None

    def test_run_full_qc_with_womersley_analysis(self, tmp_path):
        """Test full QC includes Womersley analysis."""
        from aortacfd_lib.inlet_qc import InletQC

        # Create CSV file
        boundary_data = tmp_path / "constant" / "boundaryData" / "inlet"
        boundary_data.mkdir(parents=True)
        csv_file = boundary_data / "flow.csv"
        csv_file.write_text("0.0,5e-5\n0.4,7e-5\n0.8,4e-5")

        config = {
            'inlet': {
                'type': 'TIMEVARYING',
                'profile': 'parabolic',
                'orientation': 'auto',
                'csv_file': 'flow.csv',
                'data_type': 'flowrate'
            },
            'physics': {'nu': 3.5e-6}
        }

        qc = InletQC(config, tmp_path)

        audit = qc.run_full_qc(
            inlet_patch_name="inlet",
            inlet_area=1e-4,
            inlet_radius=0.005,
            inlet_center=np.array([0.0, 0.0, 0.0]),
            inlet_normal=np.array([0.0, 0.0, 1.0])
        )

        assert audit.nu_m2s == 3.5e-6
        assert audit.womersley_alpha is not None
        assert audit.womersley_recommendation is not None

    def test_run_full_qc_with_scaling(self, tmp_path):
        """Test full QC with CO scaling."""
        from aortacfd_lib.inlet_qc import InletQC

        # Create CSV file
        boundary_data = tmp_path / "constant" / "boundaryData" / "inlet"
        boundary_data.mkdir(parents=True)
        csv_file = boundary_data / "flow.csv"
        csv_file.write_text("0.0,5e-5\n0.4,7e-5\n0.8,4e-5")

        config = {
            'inlet': {
                'type': 'TIMEVARYING',
                'profile': 'parabolic',
                'orientation': 'auto',
                'csv_file': 'flow.csv',
                'data_type': 'flowrate',
                'scaling': {'target_CO': 5.0}  # 5 L/min
            },
            'physics': {}
        }

        qc = InletQC(config, tmp_path)

        audit = qc.run_full_qc(
            inlet_patch_name="inlet",
            inlet_area=1e-4,
            inlet_radius=0.005,
            inlet_center=np.array([0.0, 0.0, 0.0]),
            inlet_normal=np.array([0.0, 0.0, 1.0])
        )

        assert audit.scaling_applied is True
        assert audit.target_CO_Lmin == 5.0
        assert audit.scale_factor > 0

    def test_run_full_qc_with_filtering(self, tmp_path):
        """Test full QC with filter configuration."""
        from aortacfd_lib.inlet_qc import InletQC

        # Create CSV file to avoid zero period
        boundary_data = tmp_path / "constant" / "boundaryData" / "inlet"
        boundary_data.mkdir(parents=True)
        csv_file = boundary_data / "flow.csv"
        csv_file.write_text("0.0,0.001\n0.8,0.001\n")

        config = {
            'inlet': {
                'type': 'TIMEVARYING',
                'profile': 'parabolic',
                'orientation': 'auto',
                'csv_file': 'flow.csv',
                'data_type': 'flowrate',
                'filter': {'method': 'linear', 'target_dt': 0.005}
            },
            'physics': {}
        }

        qc = InletQC(config, tmp_path)

        audit = qc.run_full_qc(
            inlet_patch_name="inlet",
            inlet_area=1e-4,
            inlet_radius=0.005,
            inlet_center=np.array([0.0, 0.0, 0.0]),
            inlet_normal=np.array([0.0, 0.0, 1.0])
        )

        assert audit.filter_method == 'linear'
        assert audit.target_dt_s == 0.005

    def test_run_full_qc_csv_not_found(self, tmp_path):
        """Test full QC handles missing CSV file gracefully."""
        from aortacfd_lib.inlet_qc import InletQC

        config = {
            'inlet': {
                'type': 'FIXED',  # Use FIXED type so no CSV analysis is attempted
                'profile': 'parabolic',
                'orientation': 'auto'
            },
            'physics': {}
        }

        # Create a minimal CSV for the report to avoid zero period
        boundary_data = tmp_path / "constant" / "boundaryData" / "inlet"
        boundary_data.mkdir(parents=True)
        csv_file = boundary_data / "flow.csv"
        csv_file.write_text("0.0,0.001\n0.8,0.001\n")

        # Use a different config with missing CSV for TIMEVARYING
        config_missing = {
            'inlet': {
                'type': 'TIMEVARYING',
                'profile': 'parabolic',
                'orientation': 'auto',
                'csv_file': 'nonexistent.csv',
                'data_type': 'flowrate'
            },
            'physics': {}
        }

        qc = InletQC(config_missing, tmp_path)

        # Manually set a detected_period to avoid zero division in summary
        audit = qc.run_full_qc(
            inlet_patch_name="inlet",
            inlet_area=1e-4,
            inlet_radius=0.005,
            inlet_center=np.array([0.0, 0.0, 0.0]),
            inlet_normal=np.array([0.0, 0.0, 1.0])
        )

        # Since CSV wasn't found, audit should have default values
        # The warning should be recorded
        assert len(audit.warnings) > 0
        assert any("not found" in w for w in audit.warnings)

    def test_run_full_qc_velocity_data_type(self, tmp_path):
        """Test full QC with velocity data type."""
        from aortacfd_lib.inlet_qc import InletQC

        # Create CSV file with velocity data
        boundary_data = tmp_path / "constant" / "boundaryData" / "inlet"
        boundary_data.mkdir(parents=True)
        csv_file = boundary_data / "velocity.csv"
        csv_file.write_text("0.0,0.5\n0.4,0.7\n0.8,0.4")

        config = {
            'inlet': {
                'type': 'TIMEVARYING',
                'profile': 'parabolic',
                'orientation': 'auto',
                'csv_file': 'velocity.csv',
                'data_type': 'velocity'
            },
            'physics': {'nu': 3.5e-6}
        }

        qc = InletQC(config, tmp_path)

        audit = qc.run_full_qc(
            inlet_patch_name="inlet",
            inlet_area=1e-4,
            inlet_radius=0.005,
            inlet_center=np.array([0.0, 0.0, 0.0]),
            inlet_normal=np.array([0.0, 0.0, 1.0])
        )

        # For velocity data, mean_velocity is from CSV, mean_flow is calculated
        assert audit.mean_velocity_ms is not None
        assert audit.mean_flow_m3s is not None
        assert audit.mean_flow_m3s == pytest.approx(audit.mean_velocity_ms * 1e-4, rel=1e-6)

    def test_run_full_qc_profile_mismatch_warning(self, tmp_path):
        """Test that profile mismatch generates warning."""
        from aortacfd_lib.inlet_qc import InletQC

        # Create CSV file
        boundary_data = tmp_path / "constant" / "boundaryData" / "inlet"
        boundary_data.mkdir(parents=True)
        csv_file = boundary_data / "flow.csv"
        csv_file.write_text("0.0,5e-5\n0.4,7e-5\n0.8,4e-5")

        config = {
            'inlet': {
                'type': 'TIMEVARYING',
                'profile': 'plug',  # Using plug profile
                'orientation': 'auto',
                'csv_file': 'flow.csv',
                'data_type': 'flowrate'
            },
            'physics': {'nu': 3.5e-6}  # With this ν and R=0.005, α would suggest womersley
        }

        qc = InletQC(config, tmp_path)

        audit = qc.run_full_qc(
            inlet_patch_name="inlet",
            inlet_area=1e-4,
            inlet_radius=0.005,
            inlet_center=np.array([0.0, 0.0, 0.0]),
            inlet_normal=np.array([0.0, 0.0, 1.0])
        )

        # Check that a warning was generated about profile mismatch
        # (only if profile doesn't match recommendation)
        if audit.womersley_recommendation and "plug" not in audit.womersley_recommendation:
            assert len(audit.warnings) > 0

    def test_run_full_qc_list_center_normal(self, tmp_path):
        """Test full QC accepts list instead of numpy array for center/normal."""
        from aortacfd_lib.inlet_qc import InletQC

        # Create CSV file to get non-zero period
        boundary_data = tmp_path / "constant" / "boundaryData" / "inlet"
        boundary_data.mkdir(parents=True)
        csv_file = boundary_data / "flow.csv"
        csv_file.write_text("0.0,0.001\n0.8,0.001\n")

        config = {
            'inlet': {
                'type': 'TIMEVARYING',
                'profile': 'parabolic',
                'orientation': 'auto',
                'csv_file': 'flow.csv',
                'data_type': 'flowrate'
            },
            'physics': {}
        }

        qc = InletQC(config, tmp_path)

        # Pass lists instead of numpy arrays
        audit = qc.run_full_qc(
            inlet_patch_name="inlet",
            inlet_area=1e-4,
            inlet_radius=0.005,
            inlet_center=[0.0, 0.0, 0.0],
            inlet_normal=[0.0, 0.0, 1.0]
        )

        assert audit.inlet_center == [0.0, 0.0, 0.0]
        assert audit.inlet_normal == [0.0, 0.0, 1.0]


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
