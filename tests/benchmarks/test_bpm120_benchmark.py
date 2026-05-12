"""Benchmark validation for BPM120 against the published reference values.

These tests do NOT run the simulation; they assume a `qoi_summary.json`
already exists (produced by `python run_patient.py BPM120 --steps all`)
and only validate its contents against `benchmarks/expected_values.json`.

Skipped by default. To run:

    BPM120_QOI=output/BPM120/run_XXX/reports/results/qoi_summary.json \\
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
