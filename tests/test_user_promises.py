"""
Tests organised by user promises, not code structure.

Layer B (integration) and Layer C (workflow) tests that verify
AortaCFD-app delivers on its five promises to users.

Promise 1: Automation — case generation without manual editing
Promise 2: Efficient default mesh — adaptive span by default
Promise 3: QC exists — audit report with clear verdict
Promise 4: Reproducibility — same input → same choices
Promise 5: Useful outputs — reports and metrics always produced

These tests do NOT require OpenFOAM. They test the Python pipeline
through to file generation and verify output structure.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def minimal_config():
    """Minimal valid config — no mesh resolution, no explicit strategy."""
    return {
        "geometry": {
            "case_name": "test_case",
            "wall_keywords_ordered": "wall",
            "inlet_keywords_ordered": "inlet",
            "outlet_keywords_ordered": ["outlet1", "outlet2"],
        },
        "mesh": {
            "SNAPPY_SETTINGS": {
                "mesh_strategy": "adaptive_span",
                "default_cells_across_span": 12,
                "castellatedMesh": True, "snap": True, "addLayers": True,
                "maxLocalCells": 10000000, "maxGlobalCells": 20000000,
                "minRefinementCells": 10, "maxLoadUnbalance": 0.10,
                "nCellsBetweenLevels": 3, "includedAngle": 170,
                "resolveFeatureAngle": 30,
                "nSmoothPatch": 5, "nSmoothInternal": 5,
                "snapTolerance": 2.0, "nSolveIter": 100,
                "nRelaxIter": 10, "nFeatureSnapIter": 10,
                "implicitFeatureSnap": False, "explicitFeatureSnap": True,
                "multiRegionFeatureSnap": False,
                "relativeSizes": True, "addLayer": 10,
                "expansionRatio": 1.1, "finalLayerThickness": 0.4,
                "minThickness": 0.15, "featureAngle": 150,
                "slipFeatureAngle": 30, "layerTerminationAngle": -180,
                "nGrow": 0, "nBufferCellsNoExtrude": 0,
                "nSmoothNormals": 5, "nSmoothSurfaceNormals": 30,
                "nSmoothThickness": 15, "nSmoothDisplacement": 15,
                "maxFaceThicknessRatio": 0.4, "maxThicknessToMedialRatio": 0.25,
                "minMedianAxisAngle": 90, "nLayerIter": 100, "nRelaxedIter": 50,
                "maxNonOrtho": 60, "maxBoundarySkewness": 4,
                "maxInternalSkewness": 4, "maxConcave": 80,
                "minVol": 1e-18, "minTetQuality": 1e-30, "minArea": 1e-20,
                "minTwist": 0.01, "minDeterminant": 0.01,
                "minFaceWeight": 0.02, "minVolRatio": 0.01,
                "minTriangleTwist": -1, "nSmoothScale": 6,
                "errorReduction": 0.75,
                "relaxed_maxNonOrtho": 70, "relaxed_maxBoundarySkewness": 10,
                "relaxed_maxInternalSkewness": 6, "relaxed_minDeterminant": 0.001,
                "relaxed_minVol": 1e-20,
            },
        },
        "openfoam_version": "12",
        "template_vars": {"openfoam_version": "12"},
        "physics": {
            "simulation_type": "laminar",
            "transport_properties": {"nu": 3.77e-06, "rho": 1060},
        },
        "boundary_conditions": {},
    }


@pytest.fixture
def legacy_config():
    """Config with explicit cpd — should use legacy path regardless of strategy."""
    return {
        "geometry": {
            "case_name": "test_legacy",
            "wall_keywords_ordered": "wall",
            "inlet_keywords_ordered": "inlet",
            "outlet_keywords_ordered": ["outlet1"],
        },
        "mesh": {
            "cells_per_diameter": 20,
            "SNAPPY_SETTINGS": {
                "mesh_strategy": "legacy_surface",
                "surfaceRefinementLevels": [1, 2],
            },
        },
        "physics": {
            "simulation_type": "laminar",
            "transport_properties": {"nu": 3.77e-06, "rho": 1060},
        },
        "boundary_conditions": {},
    }


@pytest.fixture
def mock_geometry():
    """Mock PatchProcessing to return realistic aortic geometry.
    Does NOT mock Jinja2 — templates must render to real strings."""
    with patch("aortacfd_lib.mesh_setup.PatchProcessing") as mock_pp, \
         patch("aortacfd_lib.mesh_setup.Logger"):

        mock_instance = MagicMock()
        # 12mm radius inlet (24mm diameter aorta)
        mock_instance.calculate_inlet_center_radius.return_value = (
            np.array([0.0, 0.0, 0.0]), 0.012, np.array([0.0, 0.0, 1.0])
        )
        mock_pp.return_value = mock_instance

        yield mock_pp


# ============================================================================
# Promise 1: Automation — case generation without manual editing
# ============================================================================


class TestPromise1_Automation:
    """A user can generate a case without manual OpenFOAM editing."""

    def test_mesh_files_generated_from_config(self, minimal_config, mock_geometry):
        """Given valid config, all mesh dictionaries are created."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)
            sys_path = Path(tmpdir) / "system"
            sys_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(minimal_config, tmpdir)

            # Mock STL vertex extraction since no real STL files
            with patch.object(analyzer, '_get_all_vertices',
                            return_value=np.array([[0, 0, 0], [0.05, 0.04, 0.1]])):
                analyzer.write_all_mesh_files()

            # Verify all three dictionaries exist
            assert (sys_path / "blockMeshDict").exists()
            assert (sys_path / "snappyHexMeshDict").exists()
            assert (sys_path / "surfaceFeaturesDict").exists()

    def test_blockmesh_dict_has_valid_structure(self, minimal_config, mock_geometry):
        """blockMeshDict contains vertices, blocks, and cell counts."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)
            sys_path = Path(tmpdir) / "system"
            sys_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(minimal_config, tmpdir)

            with patch.object(analyzer, '_get_all_vertices',
                            return_value=np.array([[0, 0, 0], [0.05, 0.04, 0.1]])):
                analyzer.write_all_mesh_files()

            content = (sys_path / "blockMeshDict").read_text()
            assert "vertices" in content
            assert "blocks" in content
            assert "hex" in content
            assert "simpleGrading" in content

    def test_snappy_dict_has_required_sections(self, minimal_config, mock_geometry):
        """snappyHexMeshDict has geometry, castellated, snap, and layer sections."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)
            sys_path = Path(tmpdir) / "system"
            sys_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(minimal_config, tmpdir)

            with patch.object(analyzer, '_get_all_vertices',
                            return_value=np.array([[0, 0, 0], [0.05, 0.04, 0.1]])):
                analyzer.write_all_mesh_files()

            content = (sys_path / "snappyHexMeshDict").read_text()
            assert "castellatedMeshControls" in content
            assert "snapControls" in content
            assert "addLayersControls" in content
            assert "meshQualityControls" in content


# ============================================================================
# Promise 2: Efficient default mesh — adaptive span by default
# ============================================================================


class TestPromise2_EfficientMesh:
    """The default mesh is efficient and good enough for routine runs."""

    def test_default_strategy_is_adaptive_span(self):
        """Out of the box, mesh_strategy is adaptive_span."""
        from config.base import config as base_config

        snappy = base_config["mesh"]["SNAPPY_SETTINGS"]
        assert snappy["mesh_strategy"] == "adaptive_span"

    def test_default_span_target_is_conservative(self):
        """Default cells_across_span is a conservative value."""
        from config.base import config as base_config

        snappy = base_config["mesh"]["SNAPPY_SETTINGS"]
        target = snappy["default_cells_across_span"]
        assert 8 <= target <= 20, f"Default span target {target} outside sensible range"

    def test_adaptive_span_produces_coarse_blockmesh(self, minimal_config, mock_geometry):
        """With no explicit resolution, adaptive_span uses coarse blockMesh."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer
        from aortacfd_lib.utils.mesh_constants import MAX_BLOCKMESH_CPD

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(minimal_config, tmpdir)

            # Trigger the fallback path
            mesh_resolution = {}
            cell_size, source, priority = analyzer._resolve_cell_size(mesh_resolution)

            # Should use span path, not legacy
            assert "SPAN_REFINEMENT" in source
            assert analyzer.snappy_settings["span_refinement_enabled"] is True

            # BlockMesh should be capped
            # cell_size = D_ref / bg_cpd, so bg_cpd = D_ref / cell_size
            D_ref = 2 * 0.012  # 24mm
            bg_cpd = D_ref / cell_size
            assert bg_cpd <= MAX_BLOCKMESH_CPD + 0.1, f"Background cpd {bg_cpd:.1f} exceeds max {MAX_BLOCKMESH_CPD}"

    def test_adaptive_span_enables_insidespan_in_template(self, minimal_config, mock_geometry):
        """Adaptive span writes insideSpan refinement region to snappyHexMeshDict."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)
            sys_path = Path(tmpdir) / "system"
            sys_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(minimal_config, tmpdir)

            with patch.object(analyzer, '_get_all_vertices',
                            return_value=np.array([[0, 0, 0], [0.05, 0.04, 0.1]])):
                analyzer.write_all_mesh_files()

            snappy = (sys_path / "snappyHexMeshDict").read_text()
            assert "insideSpan" in snappy
            assert "cellsAcrossSpan" in snappy

    def test_adaptive_span_enables_closeness_in_surfacefeatures(self, minimal_config, mock_geometry):
        """Adaptive span writes closeness generation to surfaceFeaturesDict."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)
            sys_path = Path(tmpdir) / "system"
            sys_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(minimal_config, tmpdir)

            with patch.object(analyzer, '_get_all_vertices',
                            return_value=np.array([[0, 0, 0], [0.05, 0.04, 0.1]])):
                analyzer.write_all_mesh_files()

            sf = (sys_path / "surfaceFeaturesDict").read_text()
            assert "closeness" in sf
            assert "pointCloseness" in sf

    def test_planner_always_returns_valid_result(self):
        """Shared planner never fails, even on extreme inputs."""
        from aortacfd_lib.utils.mesh_constants import plan_span_background

        for target in [4, 8, 12, 16, 20, 30, 50, 100, 200]:
            plan = plan_span_background(target)
            assert 4 <= plan["background_cpd"] <= 8
            assert 1 <= plan["span_level"] <= 4
            assert plan["theoretical_cells_across"] > 0


# ============================================================================
# Promise 3: QC exists — audit report with clear verdict
# ============================================================================


class TestPromise3_QCExists:
    """The app gives QC, not just files."""

    def test_audit_parses_checkmesh(self):
        """Audit extracts quality metrics from a real checkMesh log."""
        from aortacfd_lib.mesh_audit import _extract_cell_counts

        with tempfile.TemporaryDirectory() as tmpdir:
            logs = Path(tmpdir) / "logs"
            logs.mkdir()
            (logs / "log.checkMesh").write_text(
                "    cells:            250000\n"
                "Mesh non-orthogonality Max: 58.3 average: 8.2\n"
                "Max skewness = 2.45 OK.\n"
                "Mesh OK.\n"
            )
            (logs / "log.blockMesh").write_text("  nCells: 100000\n")

            counts = _extract_cell_counts(tmpdir)
            assert counts["blockmesh_cells"] == 100000
            assert counts["final_cells"] == 250000
            assert counts["retained_fraction"] > 0  # ratio exists and is positive

    def test_verdict_pass_for_good_mesh(self):
        """Good quality metrics produce PASS verdict."""
        from aortacfd_lib.mesh_audit import _determine_verdict

        report = {
            "quality": {"status": "good", "metrics": {"max_non_orthogonality": 55, "max_skewness": 2.0}},
            "resolution_proxy": {},
            "requested_cells_across_span": None,
        }
        verdict, _ = _determine_verdict(report)
        assert verdict == "pass"

    def test_verdict_warn_for_marginal_mesh(self):
        """Marginal quality produces WARN, not silent pass."""
        from aortacfd_lib.mesh_audit import _determine_verdict

        report = {
            "quality": {"status": "good", "metrics": {"max_non_orthogonality": 67, "max_skewness": 2.0}},
            "resolution_proxy": {},
            "requested_cells_across_span": None,
        }
        verdict, warnings = _determine_verdict(report)
        assert verdict == "warn"
        assert len(warnings) > 0

    def test_verdict_fail_for_bad_mesh(self):
        """Bad quality produces FAIL with explanation."""
        from aortacfd_lib.mesh_audit import _determine_verdict

        report = {
            "quality": {"status": "failed", "metrics": {"max_non_orthogonality": 75, "max_skewness": 8.0}},
            "resolution_proxy": {},
            "requested_cells_across_span": None,
        }
        verdict, warnings = _determine_verdict(report)
        assert verdict == "fail"
        assert any("70" in w or "fail" in w.lower() for w in warnings)

    def test_verdict_warns_on_underresolved_outlet(self):
        """Under-resolved patch triggers WARN, not silent pass."""
        from aortacfd_lib.mesh_audit import _determine_verdict

        report = {
            "quality": {"status": "good", "metrics": {"max_non_orthogonality": 50, "max_skewness": 1.5}},
            "resolution_proxy": {"outlet1": {"cells_across_proxy": 5.0}},
            "requested_cells_across_span": 16,
        }
        verdict, warnings = _determine_verdict(report)
        assert verdict == "warn"
        assert any("outlet1" in w for w in warnings)

    def test_thresholds_match_openfoam_defaults(self):
        """Audit thresholds align with OpenFOAM meshQualityDict standards."""
        from aortacfd_lib.mesh_audit import THRESHOLDS

        assert THRESHOLDS["pass"]["max_non_ortho"] == 65
        assert THRESHOLDS["pass"]["max_internal_skewness"] == 4
        assert THRESHOLDS["pass"]["min_determinant"] == 0.001
        assert THRESHOLDS["hard_fail"]["max_non_ortho"] == 70


# ============================================================================
# Promise 4: Reproducibility — same input → same choices
# ============================================================================


class TestPromise4_Reproducibility:
    """Same input produces the same configuration choices."""

    def test_planner_is_deterministic(self):
        """Same span target always gives same planner output."""
        from aortacfd_lib.utils.mesh_constants import plan_span_background

        result1 = plan_span_background(16)
        result2 = plan_span_background(16)
        assert result1 == result2

    def test_strategy_routing_is_deterministic(self, minimal_config, mock_geometry):
        """Same config always produces same strategy choices."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        results = []
        for _ in range(3):
            with tempfile.TemporaryDirectory() as tmpdir:
                tri_path = Path(tmpdir) / "constant" / "triSurface"
                tri_path.mkdir(parents=True)

                analyzer = GeometryAnalyzer(minimal_config, tmpdir)
                mesh_resolution = {}
                cell_size, source, priority = analyzer._resolve_cell_size(mesh_resolution)
                results.append((cell_size, source, priority))

        assert results[0] == results[1] == results[2]

    def test_legacy_mode_matches_old_behaviour(self, legacy_config, mock_geometry):
        """Legacy strategy with explicit cpd uses priority 2, not span."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            tri_path = Path(tmpdir) / "constant" / "triSurface"
            tri_path.mkdir(parents=True)

            analyzer = GeometryAnalyzer(legacy_config, tmpdir)
            mesh_resolution = {"cells_per_diameter": 20}
            cell_size, source, priority = analyzer._resolve_cell_size(mesh_resolution)

            assert priority == 2
            assert "cells_per_diameter" in source
            assert analyzer.snappy_settings.get("span_refinement_enabled", False) is False

    def test_user_surface_levels_preserved(self, mock_geometry):
        """User-specified surfaceRefinementLevels are not overridden."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        config = {
            "geometry": {"wall_keywords_ordered": "wall", "inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": []},
            "mesh": {"SNAPPY_SETTINGS": {
                "mesh_strategy": "adaptive_span",
                "surfaceRefinementLevels": [2, 3],
                "_user_provided_keys": ["surfaceRefinementLevels"],
            }},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "constant" / "triSurface").mkdir(parents=True)
            analyzer = GeometryAnalyzer(config, tmpdir)
            assert analyzer.snappy_settings["surfaceRefinementLevels"] == [2, 3]


# ============================================================================
# Promise 5: Useful outputs
# ============================================================================


class TestPromise5_UsefulOutputs:
    """Final outputs are useful for interpretation."""

    def test_audit_report_has_structured_format(self):
        """Audit report contains all required top-level keys."""
        from aortacfd_lib.mesh_audit import audit_mesh

        # Minimal mocked case with no real files
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "logs").mkdir()

            report = audit_mesh(
                tmpdir,
                geometry_info={"inlet_radius_m": 0.012, "outlet_radii_m": [], "outlet_names": [], "inlet_name": "inlet"},
                config={"mesh": {"SNAPPY_SETTINGS": {}}},
            )

            # Required keys
            assert "strategy" in report
            assert "quality" in report
            assert "resolution_proxy" in report
            assert "cell_counts" in report
            assert "verdict" in report
            assert "warnings" in report

    def test_resolution_proxy_gives_useful_numbers(self):
        """Resolution proxy returns meaningful cells-across estimate."""
        from aortacfd_lib.mesh_audit import estimate_patch_resolution

        with tempfile.TemporaryDirectory() as tmpdir:
            poly_dir = Path(tmpdir) / "constant" / "polyMesh"
            poly_dir.mkdir(parents=True)

            # Write synthetic polyMesh: 4 square faces of 1mm x 1mm
            cell_size = 0.001
            pts = []
            for j in range(3):
                for i in range(3):
                    pts.append(f"({i * cell_size} {j * cell_size} 0)")

            (poly_dir / "points").write_text(
                f"FoamFile\n{{\n    class vectorField;\n    object points;\n}}\n9\n(\n" +
                "\n".join(pts) + "\n)\n"
            )
            (poly_dir / "faces").write_text(
                "FoamFile\n{\n    class faceList;\n    object faces;\n}\n4\n(\n"
                "4(0 1 4 3)\n4(1 2 5 4)\n4(3 4 7 6)\n4(4 5 8 7)\n)\n"
            )
            (poly_dir / "boundary").write_text(
                "FoamFile\n{\n    class polyBoundaryMesh;\n    object boundary;\n}\n1\n(\n"
                "    inlet\n    {\n        type patch;\n        nFaces 4;\n        startFace 0;\n    }\n)\n"
            )

            result = estimate_patch_resolution(tmpdir, "inlet", 0.002)

            assert result is not None
            assert "cells_across_proxy" in result
            assert result["cells_across_proxy"] > 0
            assert result["method"] == "boundary_face_area"


# ============================================================================
# Failure cases — bad inputs should fail clearly
# ============================================================================


class TestFailureCases:
    """App fails clearly on bad input, not silently."""

    def test_extreme_span_target_warns(self):
        """Unreasonably high span target produces warning."""
        from aortacfd_lib.utils.mesh_constants import plan_span_background

        result = plan_span_background(500)
        assert result["warning"] is not None

    def test_missing_geometry_in_config(self, mock_geometry):
        """Missing geometry config raises error, not silent failure."""
        from aortacfd_lib.mesh_setup import GeometryAnalyzer

        bad_config = {"mesh": {"SNAPPY_SETTINGS": {}}}

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "constant" / "triSurface").mkdir(parents=True)
            with pytest.raises((KeyError, TypeError)):
                GeometryAnalyzer(bad_config, tmpdir)

    def test_audit_handles_missing_logs_gracefully(self):
        """Audit doesn't crash if checkMesh log is missing."""
        from aortacfd_lib.mesh_audit import _extract_cell_counts

        with tempfile.TemporaryDirectory() as tmpdir:
            # No logs directory at all
            result = _extract_cell_counts(tmpdir)
            assert result == {}

    def test_resolution_proxy_handles_missing_polymesh(self):
        """Resolution proxy returns None if polyMesh doesn't exist."""
        from aortacfd_lib.mesh_audit import estimate_patch_resolution

        with tempfile.TemporaryDirectory() as tmpdir:
            result = estimate_patch_resolution(tmpdir, "inlet", 0.01)
            assert result is None

    def test_resolution_proxy_handles_missing_patch(self):
        """Resolution proxy returns None for non-existent patch."""
        from aortacfd_lib.mesh_audit import estimate_patch_resolution

        with tempfile.TemporaryDirectory() as tmpdir:
            poly_dir = Path(tmpdir) / "constant" / "polyMesh"
            poly_dir.mkdir(parents=True)
            (poly_dir / "points").write_text("FoamFile\n{}\n0\n(\n)\n")
            (poly_dir / "faces").write_text("FoamFile\n{}\n0\n(\n)\n")
            (poly_dir / "boundary").write_text("FoamFile\n{}\n0\n(\n)\n")

            result = estimate_patch_resolution(tmpdir, "nonexistent", 0.01)
            assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
