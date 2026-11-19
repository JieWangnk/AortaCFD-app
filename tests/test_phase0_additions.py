"""Regression tests for the v1.5.1 fixes and additions.

Covers: murray_exponent wiring, Windkessel range checks, strict merged-config
schema, the mesh y+ screening estimate, the measured flow split in the
hemodynamics post-processor, the reporter's measured/estimated labelling and
the new controlDict function objects.
"""

import json
from pathlib import Path

import jinja2
import pytest

REPO = Path(__file__).resolve().parents[1]
TEMPLATES = REPO / "src" / "templates"


# ---------------------------------------------------------------------------
# Windkessel setup: murray_exponent and range checks
# ---------------------------------------------------------------------------
def _wk(tmp_path, wk_settings):
    from aortacfd_lib.wk_setup import WkSetup

    config = {
        "geometry": {"inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": ["outlet1", "outlet2"]},
        "boundary_conditions": {
            "inlet": {"type": "CONSTANT", "velocity": 0.3},
            "outlets": {"type": "3EWINDKESSEL", "windkessel_settings": wk_settings},
        },
        "physics": {"rho": 1060},
    }
    return WkSetup(config, [], str(tmp_path), 0.8)


class TestMurrayExponent:
    def test_default_is_constant(self, tmp_path):
        from aortacfd_lib.constants import MURRAY_LAW_EXPONENT

        assert _wk(tmp_path, {}).murray_exponent == MURRAY_LAW_EXPONENT

    def test_config_value_is_used(self, tmp_path):
        wk = _wk(tmp_path, {"murray_exponent": 3.0})
        assert wk.murray_exponent == 3.0
        split = wk._calculate_murray_flow_split({"outlet1": 0.01, "outlet2": 0.005})
        # cubic law: 1 : 1/8
        assert split["outlet1"] == pytest.approx(8 / 9)
        assert split["outlet2"] == pytest.approx(1 / 9)

    def test_exponent_two_is_area_split(self, tmp_path):
        split = _wk(tmp_path, {"murray_exponent": 2})._calculate_murray_flow_split({"outlet1": 0.01, "outlet2": 0.005})
        assert split["outlet1"] == pytest.approx(4 / 5)

    @pytest.mark.parametrize("bad", [1.5, 3.5, "two"])
    def test_invalid_falls_back(self, tmp_path, bad):
        from aortacfd_lib.constants import MURRAY_LAW_EXPONENT

        assert _wk(tmp_path, {"murray_exponent": bad}).murray_exponent == MURRAY_LAW_EXPONENT


class TestBoundsCheck:
    def test_inside_and_outside(self, tmp_path):
        wk = _wk(tmp_path, {})
        assert wk._check_bound("R_total", "outlet1", 1.2, 0.05, 100.0, "mmHg·s/mL") is True
        assert wk._check_bound("PWV", "outlet1", 1.0, 2.0, 20.0, "m/s") is False
        assert [b["ok"] for b in wk.bounds_check] == [True, False]
        rec = wk.bounds_check[1]
        assert rec["quantity"] == "PWV" and rec["low"] == 2.0 and rec["high"] == 20.0 and rec["unit"] == "m/s"


# ---------------------------------------------------------------------------
# Strict merged-config schema
# ---------------------------------------------------------------------------
class TestStrictSchema:
    def _builder(self, monkeypatch):
        import config.builder as builder_mod

        monkeypatch.setattr(builder_mod, "is_pydantic_available", lambda: True)

        def _fail(cfg):
            raise ValueError("bad field")

        monkeypatch.setattr(builder_mod, "validate_config", _fail)
        return builder_mod.ConfigBuilder()

    def test_raises_by_default(self, monkeypatch):
        with pytest.raises(ValueError, match="failed schema validation"):
            self._builder(monkeypatch)._validate_schema({"run_settings": {}})

    def test_opt_out_warns_only(self, monkeypatch):
        self._builder(monkeypatch)._validate_schema({"run_settings": {"strict_schema": False}})


# ---------------------------------------------------------------------------
# Mesh y+ screening estimate
# ---------------------------------------------------------------------------
class TestYplusScreening:
    def _task(self):
        from workflow.tasks.execution_tasks import ExecuteMeshingTask

        config = {
            "physics": {"transport_properties": {"rho": 1060, "nu": 3.7736e-6}},
            "boundary_conditions": {"inlet": {"type": "CONSTANT", "cardiac_output": 5.0}},
            "mesh": {"boundary_layers": {"num_layers": 3, "expansion_ratio": 1.2}},
        }
        return ExecuteMeshingTask(config)

    def test_estimate_from_layer_report(self):
        task = self._task()
        coverage = {"wall_aorta": {"faces": 100, "layers": 3.0, "thickness_m": 0.0006, "coverage_pct": 90.0}}
        out = task._estimate_wall_yplus(0.0125, coverage)
        assert out["status"] == "ok"
        assert out["peak_velocity_m_s"] > 0
        patch = out["patches"]["wall_aorta"]
        # geometric series: first = T (r-1)/(r^n - 1)
        assert patch["first_layer_m"] == pytest.approx(0.0006 * 0.2 / (1.2**3 - 1))
        assert patch["yplus_peak"] == pytest.approx(patch["first_layer_m"] / out["first_layer_for_yplus_1_m"])
        assert 0.1 < patch["yplus_peak"] < 100

    def test_not_available_without_inputs(self):
        task = self._task()
        assert task._estimate_wall_yplus(None, {})["status"] == "not_available"
        assert task._estimate_wall_yplus(0.0125, {})["status"] == "not_available"


# ---------------------------------------------------------------------------
# Measured flow split (hemodynamics post-processor)
# ---------------------------------------------------------------------------
def _write_monitor(case_dir: Path, name: str, rows):
    d = case_dir / "postProcessing" / name / "0"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "surfaceFieldValue.dat", "w") as f:
        f.write("# Source : patch\n# Time\tsum(phi)\n")
        for t, v in rows:
            f.write(f"{t}\t{v}\n")


class TestMeasuredFlowSplit:
    def _processor(self, case_dir, inlet_type="TIMEVARYING"):
        from aortacfd_lib.hemodynamics_postprocessor import HemodynamicsPostProcessor

        config = {
            "inlet": {"type": inlet_type},
            "geometry": {"inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": ["outlet1", "outlet2"]},
            "cardiac_cycle": 1.0,
            "hemodynamics": {"tawss_settings": {"skip_cycles": 1}},
        }
        return HemodynamicsPostProcessor(str(case_dir), config)

    def test_split_and_balance(self, tmp_path):
        times = [i * 0.1 for i in range(1, 21)]  # two cycles of 1 s
        # first cycle is transient (half flow); settled cycle: inlet -100e-6, outlets 70e-6 + 29e-6
        _write_monitor(tmp_path, "inletFlow", [(t, -50e-6 if t < 1.0 else -100e-6) for t in times])
        _write_monitor(tmp_path, "outlet1Flow", [(t, 35e-6 if t < 1.0 else 70e-6) for t in times])
        _write_monitor(tmp_path, "outlet2Flow", [(t, 14.5e-6 if t < 1.0 else 29e-6) for t in times])
        from aortacfd_lib.hemodynamics_postprocessor import HemodynamicsResults

        proc = self._processor(tmp_path)
        results = HemodynamicsResults()
        proc._compute_measured_flow_split(results)
        assert results.flow_source == "measured"
        assert results.flow_inlet_m3s == pytest.approx(100e-6)
        assert results.flow_outlets_m3s["outlet1"] == pytest.approx(70e-6)
        assert results.flow_fraction_outlets["outlet1"] == pytest.approx(70 / 99)
        assert results.flow_balance_error == pytest.approx(-0.01)

    def test_short_run_uses_last_cycle(self, tmp_path):
        # 1.5 s run with skip_cycles=1: fewer than skip + half a cycle -> last full cycle (0.5..1.5)
        times = [i * 0.1 for i in range(1, 16)]
        _write_monitor(tmp_path, "inletFlow", [(t, -10e-6 if t < 0.5 else -20e-6) for t in times])
        from aortacfd_lib.hemodynamics_postprocessor import HemodynamicsResults

        results = HemodynamicsResults()
        self._processor(tmp_path)._compute_measured_flow_split(results)
        assert results.flow_inlet_m3s == pytest.approx(20e-6)

    def test_steady_uses_tail(self, tmp_path):
        times = [i * 0.01 for i in range(1, 101)]
        _write_monitor(tmp_path, "outlet1Flow", [(t, 1e-6 if t < 0.9 else 5e-6) for t in times])
        from aortacfd_lib.hemodynamics_postprocessor import HemodynamicsResults

        results = HemodynamicsResults()
        self._processor(tmp_path, "CONSTANT")._compute_measured_flow_split(results)
        assert results.flow_outlets_m3s["outlet1"] == pytest.approx(5e-6)
        assert results.flow_balance_error is None  # no inlet monitor

    def test_no_monitors_is_silent(self, tmp_path):
        from aortacfd_lib.hemodynamics_postprocessor import HemodynamicsResults

        results = HemodynamicsResults()
        self._processor(tmp_path)._compute_measured_flow_split(results)
        assert results.flow_source == "none" and not results.flow_outlets_m3s

    def test_qoi_export_includes_flow(self, tmp_path):
        from aortacfd_lib.hemodynamics_postprocessor import HemodynamicsResults

        results = HemodynamicsResults(flow_fraction_outlets={"outlet1": 0.7}, flow_balance_error=0.01)
        results.flow_source = "measured"
        out = tmp_path / "out"
        out.mkdir()
        json_path, csv_path = self._processor(tmp_path).export_qoi(results, str(out))
        data = json.loads(Path(json_path).read_text())
        assert data["per_outlet_flow_fraction_measured"] == {"outlet1": 0.7}
        assert data["flow_source"] == "measured"
        assert "flow_fraction_outlet1" in Path(csv_path).read_text()


# ---------------------------------------------------------------------------
# Reporter: measured monitors preferred over the 1/R estimate
# ---------------------------------------------------------------------------
class TestReporterFlowSource:
    def test_reads_monitors(self, tmp_path):
        from aortacfd_lib.simulation_reporter import SimulationReporter

        _write_monitor(tmp_path, "inletFlow", [(0.1, -1e-4), (0.2, -2e-4)])
        _write_monitor(tmp_path, "outlet1Flow", [(0.1, 1e-4), (0.2, 2e-4)])
        rep = SimulationReporter(str(tmp_path))
        inlet_df, outlets = rep._read_flow_monitors()
        assert list(inlet_df["flow_rate"]) == pytest.approx([1e-4, 2e-4])  # inflow positive
        assert list(outlets) == ["outlet1"]

    def test_extract_flow_rates_labels_measured(self, tmp_path):
        from aortacfd_lib.simulation_reporter import SimulationReporter

        _write_monitor(tmp_path, "inletFlow", [(0.1, -1e-4), (0.2, -2e-4)])
        _write_monitor(tmp_path, "outlet1Flow", [(0.1, 1e-4), (0.2, 2e-4)])
        rep = SimulationReporter(str(tmp_path))
        inlet_df, outlets = rep.extract_flow_rates()
        assert rep.flow_source == "measured"
        assert inlet_df is not None and "outlet1" in outlets

    def test_no_data_keeps_unknown(self, tmp_path):
        from aortacfd_lib.simulation_reporter import SimulationReporter

        rep = SimulationReporter(str(tmp_path))
        inlet_df, outlets = rep.extract_flow_rates()
        assert inlet_df is None and outlets == {}
        assert rep.flow_source == "unknown"


# ---------------------------------------------------------------------------
# controlDict function objects
# ---------------------------------------------------------------------------
def _render_control_dict(config, **extra):
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATES)), undefined=jinja2.ChainableUndefined)
    ctx = {"config": config, "controlDict": {"deltaT": 1e-4, "endTime": 0.8}, "cardiac_cycle": 0.8}
    ctx.update(extra)
    return env.get_template("controlDict.tpl").render(**ctx)


class TestControlDictMonitors:
    base = {
        "geometry": {"inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": ["outlet1", "outlet2"]},
        "boundary_conditions": {"inlet": {"type": "TIMEVARYING"}, "outlets": {"type": "fixedPressure"}},
    }

    def test_flow_and_yplus_default_on(self):
        text = _render_control_dict(self.base, inlet_type="TIMEVARYING", is_pulsatile=True)
        for name in ["inletFlow", "outlet1Flow", "outlet2Flow", "yPlus"]:
            assert f"\n    {name}\n" in text, name
        start = text.index("outlet1Flow")
        block = text[start:]
        assert "operation       sum;" in block and "fields          (phi);" in block

    def test_monitors_can_be_disabled(self):
        config = dict(self.base)
        config["hemodynamics"] = {"runtime_functions": {"flowMonitoring": False, "yPlus": False}}
        text = _render_control_dict(config, inlet_type="TIMEVARYING", is_pulsatile=True)
        assert "outlet1Flow" not in text and "yPlus" not in text
        assert "outlet1Pressure" in text  # pressure monitors untouched

    def test_mapped_profile_enables_field_average(self):
        config = dict(self.base)
        config["boundary_conditions"] = {"inlet": {"type": "MAPPED_PROFILE"}, "outlets": {"type": "fixedPressure"}}
        text = _render_control_dict(config)  # no is_pulsatile passed: template decides from inlet type
        assert "fieldAverageWSS" in text


# ---------------------------------------------------------------------------
# checkMesh parser: OpenFOAM 12 writes a full stop after the face-area and volume numbers
# ---------------------------------------------------------------------------
def test_checkmesh_parser_accepts_trailing_full_stop():
    from aortacfd_lib.mesh_quality_checker import MeshQualityChecker

    content = (
        "Checking geometry...\n"
        "    Minimum face area = 3.11744e-07. Maximum face area = 1.03131e-05.  Face area magnitudes OK.\n"
        "    Min volume = 2.62602e-10. Max volume = 3.24166e-08.  Total volume = 1.2e-05.  Cell volumes OK.\n"
        "    Mesh non-orthogonality Max: 63.2504 average: 10.2209\n"
        "    Max skewness = 2.60319 OK.\n"
        "Mesh OK.\n"
    )
    report = MeshQualityChecker()._parse_checkmesh_output(content)
    m = report["metrics"]
    assert m["max_face_area"] == pytest.approx(1.03131e-05)
    assert m["min_face_area"] == pytest.approx(3.11744e-07)
    assert m["max_cell_volume"] == pytest.approx(3.24166e-08)
    assert m["max_non_orthogonality"] == pytest.approx(63.2504)


# ---------------------------------------------------------------------------
# Mesh summary fallbacks: binary polyMesh (face-count proxy) and CSV-driven inlets (peak velocity)
# ---------------------------------------------------------------------------
BOUNDARY_FILE = """FoamFile
{
    version     2.0;
    format      ascii;
    class       polyBoundaryMesh;
    object      boundary;
}
3
(
    wall_aorta
    {
        type            wall;
        nFaces          1000;
        startFace       5000;
    }
    inlet
    {
        type            patch;
        nFaces          100;
        startFace       6000;
    }
    outlet1
    {
        type            patch;
        nFaces          0;
        startFace       6100;
    }
)
"""


def test_face_count_resolution_proxy(tmp_path):
    from workflow.tasks.execution_tasks import ExecuteMeshingTask

    poly = tmp_path / "constant" / "polyMesh"
    poly.mkdir(parents=True)
    (poly / "boundary").write_text(BOUNDARY_FILE)
    out = ExecuteMeshingTask._face_count_resolution_proxy(
        str(tmp_path), {"inlet": 0.01, "outlet1": 0.005, "none": 0.01}
    )
    # inlet: area pi*1e-4 over 100 faces -> cell 1.772 mm -> 20 mm / 1.772 mm = 11.3 cells across
    assert set(out) == {"inlet"}  # outlet1 has no faces, "none" is not a patch
    assert out["inlet"]["cells_across_proxy"] == pytest.approx(11.3, abs=0.05)
    assert out["inlet"]["method"] == "boundary_face_count"


def test_peak_inlet_velocity_from_csv(tmp_path):
    from workflow.tasks.execution_tasks import ExecuteMeshingTask

    (tmp_path / "flow.csv").write_text("time,flowrate\n0.0,2.0\n0.2,24.0\n0.4,6.0\n")  # L/min
    config = {
        "physics": {"transport_properties": {"rho": 1060, "nu": 3.7736e-6}},
        "boundary_conditions": {"inlet": {"type": "TIMEVARYING", "csv_file": "flow.csv", "data_type": "flowrate"}},
        "patient_case_directory": str(tmp_path),
    }
    u, source = ExecuteMeshingTask(config)._peak_inlet_velocity(0.01, 3.7736e-6)
    assert source == "inlet csv (flow rate)"
    assert u == pytest.approx(24.0 * 1e-3 / 60.0 / (3.141592653589793 * 1e-4))

    config["boundary_conditions"]["inlet"]["data_type"] = "velocity"
    u, source = ExecuteMeshingTask(config)._peak_inlet_velocity(0.01, 3.7736e-6)
    assert source == "inlet csv (velocity)" and u == pytest.approx(24.0)

    config["boundary_conditions"]["inlet"] = {"type": "TIMEVARYING"}
    u, source = ExecuteMeshingTask(config)._peak_inlet_velocity(0.01, 3.7736e-6)
    assert u is None and "csv_file" in source
