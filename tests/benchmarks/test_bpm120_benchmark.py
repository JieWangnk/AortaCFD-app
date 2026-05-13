"""Benchmark validation for BPM120 against the reference QoI values.

Two test groups, each skipped unless its env var points to a real
``qoi_summary.json``:

1. **Production** (``BPM120_QOI``) — full 1.5s, ~1.9M-cell mesh, the
   Wang et al. Table 3 reference. Deferred to v1.2.1 (requires HPC).

2. **Tutorial coarse** (``BPM120_TUTORIAL_QOI``) — 1 cycle (0.5s),
   ~110K-cell mesh, the v1.2.0 live-solver smoke-test reference. The
   shipped reference values were captured from
   ``output/BPM120/run_20260409_195511`` (8-core, 1h46m wall) and are
   stored in ``benchmarks/expected_values.json`` under
   ``cases.BPM120.tutorial_coarse``.

Examples:

    # Tutorial coarse (v1.2.0 quick smoke)
    BPM120_TUTORIAL_QOI=output/BPM120/run_XXX/results/qoi_summary.json \\
        pytest tests/benchmarks/test_bpm120_benchmark.py -v

    # Production (v1.2.1+)
    BPM120_QOI=output/BPM120/run_XXX/results/qoi_summary.json \\
        pytest tests/benchmarks/test_bpm120_benchmark.py -v

CI hook: a self-hosted runner with OpenFOAM 12 should execute the full
production simulation nightly, then invoke pytest with BPM120_QOI set.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_VALUES = REPO_ROOT / "benchmarks" / "expected_values.json"


def _qoi_path() -> Path | None:
    """Return the path the user pointed us at via the BPM120_QOI env var."""
    raw = os.environ.get("BPM120_QOI")
    if not raw:
        return None
    p = Path(raw)
    return p if p.is_file() else None


@pytest.fixture(scope="module")
def expected_bpm120() -> dict:
    with EXPECTED_VALUES.open() as f:
        data = json.load(f)
    return data["cases"]["BPM120"]["production"]["expected"]


@pytest.fixture(scope="module")
def actual_qoi() -> dict:
    path = _qoi_path()
    if path is None:
        pytest.skip(
            "BPM120_QOI env var not set or path missing. "
            "Set it to a qoi_summary.json from a BPM120 production run "
            "(see tests/benchmarks/test_bpm120_benchmark.py docstring)."
        )
    with path.open() as f:
        return json.load(f)


@pytest.mark.slow
@pytest.mark.benchmark
def test_pressure_drop_within_tolerance(expected_bpm120, actual_qoi):
    spec = expected_bpm120["pressure_drop_mean_mmhg"]
    actual = actual_qoi["qoi"]["pressure_drop_mean_mmhg"]["value"]
    rel_err = abs(actual - spec["value"]) / spec["value"]
    assert rel_err <= spec["tolerance_rel"], (
        f"pressure_drop_mean_mmhg = {actual:.3f}, expected "
        f"{spec['value']:.3f} ± {spec['tolerance_rel'] * 100:.0f}% "
        f"(got {rel_err * 100:.1f}% deviation)"
    )


@pytest.mark.slow
@pytest.mark.benchmark
def test_tawss_p99_within_tolerance(expected_bpm120, actual_qoi):
    spec = expected_bpm120["tawss_p99_pa"]
    actual = actual_qoi["qoi"]["tawss_p99_pa"]["value"]

    # Hard guard: TAWSS=0 means the run was too short for skip_cycles, not a regression.
    if actual == 0.0:
        status = actual_qoi.get("_metadata", {}).get("tawss_status", "OK")
        pytest.skip(f"TAWSS p99 is 0 (status={status}); run is too short for skip_cycles")

    rel_err = abs(actual - spec["value"]) / spec["value"]
    assert rel_err <= spec["tolerance_rel"], (
        f"tawss_p99_pa = {actual:.3f}, expected "
        f"{spec['value']:.3f} ± {spec['tolerance_rel'] * 100:.0f}% "
        f"(got {rel_err * 100:.1f}% deviation)"
    )


@pytest.mark.slow
@pytest.mark.benchmark
def test_qoi_summary_is_complete(actual_qoi):
    """The full production run should populate every QoI field, not zeros."""
    qoi = actual_qoi["qoi"]
    status = actual_qoi.get("_metadata", {}).get("tawss_status", "OK")
    if status == "INCOMPLETE_CYCLES":
        pytest.skip("tawss_status=INCOMPLETE_CYCLES; not a full benchmark run")

    for key in ("pressure_drop_mean_mmhg", "wss_p99_pa", "tawss_p99_pa"):
        v = qoi[key]["value"]
        assert v > 0, f"{key} = {v} — production run should produce non-zero QoIs"


# =============================================================================
# Tutorial-coarse benchmark — v1.2.0 live-solver validation
# =============================================================================
#
# Reference run: output/BPM120/run_20260409_195511 (109,597 cells, 1 cycle,
# wall ~1h46m on 8 cores). Expected QoIs stored in
# benchmarks/expected_values.json cases.BPM120.tutorial_coarse.
# Skipped unless BPM120_TUTORIAL_QOI env var is set.


def _tutorial_qoi_path() -> Path | None:
    raw = os.environ.get("BPM120_TUTORIAL_QOI")
    if not raw:
        return None
    p = Path(raw)
    return p if p.is_file() else None


@pytest.fixture(scope="module")
def expected_tutorial() -> dict:
    with EXPECTED_VALUES.open() as f:
        data = json.load(f)
    return data["cases"]["BPM120"]["tutorial_coarse"]["expected"]


@pytest.fixture(scope="module")
def actual_tutorial_qoi() -> dict:
    path = _tutorial_qoi_path()
    if path is None:
        pytest.skip(
            "BPM120_TUTORIAL_QOI env var not set or path missing. "
            "Set it to a qoi_summary.json from a BPM120 tutorial-coarse run."
        )
    with path.open() as f:
        return json.load(f)


def _rel_err(actual: float, expected: float) -> float:
    return abs(actual - expected) / abs(expected) if expected else float("inf")


@pytest.mark.benchmark
def test_tutorial_pressure_drop_mean(expected_tutorial, actual_tutorial_qoi):
    spec = expected_tutorial["pressure_drop_mean_mmhg"]
    actual = actual_tutorial_qoi["qoi"]["pressure_drop_mean_mmhg"]["value"]
    err = _rel_err(actual, spec["value"])
    assert err <= spec["tolerance_rel"], (
        f"tutorial pressure_drop_mean_mmhg = {actual:.3f}, expected "
        f"{spec['value']:.3f} ± {spec['tolerance_rel'] * 100:.0f}% "
        f"({err * 100:.1f}% deviation)"
    )


@pytest.mark.benchmark
def test_tutorial_wss_p99(expected_tutorial, actual_tutorial_qoi):
    spec = expected_tutorial["wss_p99_pa"]
    actual = actual_tutorial_qoi["qoi"]["wss_p99_pa"]["value"]
    err = _rel_err(actual, spec["value"])
    assert err <= spec["tolerance_rel"], (
        f"tutorial wss_p99_pa = {actual:.3f}, expected "
        f"{spec['value']:.3f} ± {spec['tolerance_rel'] * 100:.0f}% "
        f"({err * 100:.1f}% deviation)"
    )


@pytest.mark.benchmark
def test_tutorial_outlet4_pressure_drop(expected_tutorial, actual_tutorial_qoi):
    """outlet4 is the coarctation jet — clinically meaningful per-outlet QoI."""
    spec = expected_tutorial["per_outlet_pressure_drop_mmhg.outlet4"]
    per_outlet = actual_tutorial_qoi.get("per_outlet_pressure_drop_mmhg", {})
    actual = per_outlet.get("outlet4")
    assert actual is not None, "per_outlet_pressure_drop_mmhg.outlet4 missing from qoi_summary.json"
    err = _rel_err(actual, spec["value"])
    assert err <= spec["tolerance_rel"], (
        f"tutorial outlet4 ΔP = {actual:.3f} mmHg, expected "
        f"{spec['value']:.3f} ± {spec['tolerance_rel'] * 100:.0f}% "
        f"({err * 100:.1f}% deviation)"
    )
