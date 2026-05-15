"""Tests for scripts/compare_cohort.py — the missing aggregator.

Builds a fake output tree with three cases (two good, one failed), runs
``aggregate_qoi``, and asserts the CSV row count, the join with
``case.meta.json``, and the failure-case fallback behaviour.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.compare_cohort import aggregate_qoi


def _write_qoi(path: Path, pressure_drop: float, wss_p99: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_metadata": {
            "inlet_type": "TIMEVARYING",
            "is_pulsatile": True,
            "cardiac_cycle_s": 0.8,
            "tawss_status": "OK",
        },
        "qoi": {
            "pressure_drop_mean_mmhg": {"value": pressure_drop, "unit": "mmHg"},
            "wss_p99_pa": {"value": wss_p99, "unit": "Pa"},
        },
        "per_outlet_pressure_drop_mmhg": {"outlet1": pressure_drop * 0.5},
    }
    path.write_text(json.dumps(payload))


def _write_case_meta(path: Path, params: dict, sample_index: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "case_id": path.parent.name,
        "source": "synthetic",
        "sample_index": sample_index,
        "seed": 42,
        "params": params,
    }
    path.write_text(json.dumps(payload))


def _write_manifest(path: Path, status: str, wall_seconds: float = 60.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "wall_seconds": wall_seconds,
        "git": {"sha": "deadbeef", "dirty": False, "branch": "main"},
    }
    path.write_text(json.dumps(payload))


@pytest.fixture
def cohort_tree(tmp_path: Path) -> tuple[Path, Path]:
    output_root = tmp_path / "output"
    cases_input = tmp_path / "cases_input"

    # case_001 — success
    _write_qoi(output_root / "case_001" / "run_001" / "results" / "qoi_summary.json", 12.3, 81.0)
    _write_manifest(output_root / "case_001" / "run_001" / "manifest.json", status="ok", wall_seconds=120.0)
    _write_case_meta(cases_input / "case_001" / "case.meta.json", {"d_ascending": 28.0, "area_reduction": 0.5}, 1)

    # case_002 — success with different params
    _write_qoi(output_root / "case_002" / "run_001" / "results" / "qoi_summary.json", 19.5, 116.0)
    _write_manifest(output_root / "case_002" / "run_001" / "manifest.json", status="ok", wall_seconds=145.0)
    _write_case_meta(cases_input / "case_002" / "case.meta.json", {"d_ascending": 32.0, "area_reduction": 0.7}, 2)

    # case_003 — fails (manifest but no qoi_summary)
    _write_manifest(output_root / "case_003" / "run_001" / "manifest.json", status="diverged", wall_seconds=12.0)
    _write_case_meta(cases_input / "case_003" / "case.meta.json", {"d_ascending": 36.0, "area_reduction": 0.9}, 3)

    return output_root, cases_input


def test_aggregates_two_good_cases(cohort_tree: tuple[Path, Path]) -> None:
    output_root, cases_input = cohort_tree
    csv = aggregate_qoi(output_root=output_root, cases_input_root=cases_input)
    df = pd.read_csv(csv)

    # case_003 has no qoi_summary so it's not in the cohort by default
    assert sorted(df["case_id"].tolist()) == ["case_001", "case_002"]
    assert set(df.columns) >= {
        "case_id",
        "status",
        "pressure_drop_mean_mmhg",
        "wss_p99_pa",
        "param_d_ascending",
        "param_area_reduction",
        "sample_index",
        "geometry_source",
    }


def test_joins_meta_params(cohort_tree: tuple[Path, Path]) -> None:
    output_root, cases_input = cohort_tree
    csv = aggregate_qoi(output_root=output_root, cases_input_root=cases_input)
    df = pd.read_csv(csv).set_index("case_id")
    assert df.loc["case_001", "param_d_ascending"] == 28.0
    assert df.loc["case_002", "param_area_reduction"] == 0.7
    assert df.loc["case_001", "sample_index"] == 1
    assert df.loc["case_001", "geometry_source"] == "synthetic"


def test_status_from_manifest(cohort_tree: tuple[Path, Path]) -> None:
    output_root, cases_input = cohort_tree
    csv = aggregate_qoi(output_root=output_root, cases_input_root=cases_input)
    df = pd.read_csv(csv).set_index("case_id")
    assert df.loc["case_001", "status"] == "ok"
    assert df.loc["case_001", "wall_seconds"] == 120.0
    assert df.loc["case_001", "git_sha"] == "deadbeef"


def test_empty_output_root_writes_empty_csv(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    output_root.mkdir()
    csv = aggregate_qoi(output_root=output_root)
    assert csv.exists()
    assert csv.read_text().strip() == ""


def test_writes_to_default_path(cohort_tree: tuple[Path, Path]) -> None:
    output_root, cases_input = cohort_tree
    csv = aggregate_qoi(output_root=output_root, cases_input_root=cases_input)
    assert csv == output_root / "cohort_comparison.csv"


def test_run_dirs_subset(cohort_tree: tuple[Path, Path]) -> None:
    output_root, cases_input = cohort_tree
    csv = aggregate_qoi(
        output_root=output_root,
        run_dirs=[output_root / "case_001"],
        cases_input_root=cases_input,
    )
    df = pd.read_csv(csv)
    assert df["case_id"].tolist() == ["case_001"]


def test_run_batch_import_works() -> None:
    """The exact import that run_batch.py uses must resolve."""
    from scripts.compare_cohort import aggregate_qoi  # noqa: F401
