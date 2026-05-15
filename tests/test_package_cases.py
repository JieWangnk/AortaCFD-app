"""Tests for scripts/package_cases.py — Block B (case packager).

Fakes a "generated cases" directory tree with a couple of case folders
(each containing inlet.stl, wall_aorta.stl, outlet1..3.stl, and a
geometry.meta.json) plus a small template config. Asserts that the
packager produces a config.json + case.meta.json in each case dir, that
outlet_keywords_ordered is derived from the actual STL files present,
and that the optional inflow CSV gets copied.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.package_cases import package_directory


TEMPLATE = {
    "case_info": {"patient_id": "SWEEP_CASE"},
    "physics": {"model": "laminar", "transport_properties": {"rho": 1060, "nu": 3.7736e-6}},
    "numerics": {"profile": "standard"},
    "mesh": {"cells_per_diameter": 15},
    "geometry": {
        "inlet_keywords_ordered": "inlet",
        "outlet_keywords_ordered": ["outlet1"],
        "wall_keywords_ordered": "wall_aorta",
        "scale_factor": 0.001,
    },
    "boundary_conditions": {
        "inlet": {"type": "TIMEVARYING", "csv_file": "placeholder.csv", "data_type": "flowrate"},
        "outlets": {"type": "3EWINDKESSEL"},
        "walls": {"type": "no_slip"},
    },
}


@pytest.fixture
def generated_dir(tmp_path: Path) -> Path:
    """Build a fake generator output directory with two case folders."""
    src = tmp_path / "generated"
    src.mkdir()

    # case_001 — 3 outlets, includes geometry.meta.json
    c1 = src / "case_001"
    c1.mkdir()
    for f in ("inlet.stl", "outlet1.stl", "outlet2.stl", "outlet3.stl", "wall_aorta.stl"):
        (c1 / f).write_text("solid test\nendsolid test\n")
    (c1 / "geometry.meta.json").write_text(json.dumps({
        "schema_version": "1.0",
        "case_id": "case_001",
        "generator": "blender_aorta_like_generator",
        "mode": "sample",
        "sampler": "sobol",
        "sample_index": 1,
        "seed": 42,
        "params": {"d_ascending": 28.0, "area_reduction": 0.5},
    }))

    # case_002 — 4 outlets, also has geometry.meta.json
    c2 = src / "case_002"
    c2.mkdir()
    for f in ("inlet.stl", "outlet1.stl", "outlet2.stl", "outlet3.stl", "outlet4.stl", "wall_aorta.stl"):
        (c2 / f).write_text("solid test\nendsolid test\n")
    (c2 / "geometry.meta.json").write_text(json.dumps({
        "schema_version": "1.0",
        "case_id": "case_002",
        "generator": "blender_aorta_like_generator",
        "mode": "sample",
        "sampler": "sobol",
        "sample_index": 2,
        "seed": 42,
        "params": {"d_ascending": 32.0, "area_reduction": 0.7},
    }))

    # A junk directory with no STL — must be skipped, not crashed on
    (src / "not_a_case").mkdir()
    (src / "not_a_case" / "readme.txt").write_text("ignore me")

    return src


@pytest.fixture
def template_path(tmp_path: Path) -> Path:
    p = tmp_path / "template.json"
    p.write_text(json.dumps(TEMPLATE))
    return p


def test_packages_in_place(generated_dir: Path, template_path: Path) -> None:
    packaged = package_directory(src=generated_dir, config_template=template_path)
    assert len(packaged) == 2
    assert all(p.parent == generated_dir for p in packaged)
    for p in packaged:
        assert (p / "config.json").exists()
        assert (p / "case.meta.json").exists()


def test_outlet_keywords_match_present_stls(generated_dir: Path, template_path: Path) -> None:
    packaged = package_directory(src=generated_dir, config_template=template_path)
    for p in packaged:
        config = json.loads((p / "config.json").read_text())
        if p.name == "case_001":
            assert config["geometry"]["outlet_keywords_ordered"] == ["outlet1", "outlet2", "outlet3"]
        elif p.name == "case_002":
            assert config["geometry"]["outlet_keywords_ordered"] == ["outlet1", "outlet2", "outlet3", "outlet4"]


def test_case_meta_lifts_geometry_meta(generated_dir: Path, template_path: Path) -> None:
    packaged = package_directory(src=generated_dir, config_template=template_path)
    case_001 = next(p for p in packaged if p.name == "case_001")
    meta = json.loads((case_001 / "case.meta.json").read_text())
    assert meta["source"] == "synthetic"
    assert meta["sample_index"] == 1
    assert meta["params"]["d_ascending"] == 28.0


def test_inflow_csv_is_copied_and_referenced(generated_dir: Path, template_path: Path, tmp_path: Path) -> None:
    csv = tmp_path / "inflow.csv"
    csv.write_text("time,Q\n0.0,0.0\n0.4,1e-4\n0.8,0.0\n")
    packaged = package_directory(src=generated_dir, config_template=template_path, inflow_csv=csv)
    for p in packaged:
        assert (p / "inflow.csv").exists()
        config = json.loads((p / "config.json").read_text())
        assert config["boundary_conditions"]["inlet"]["csv_file"] == "inflow.csv"


def test_output_dir_creates_separate_copy(generated_dir: Path, template_path: Path, tmp_path: Path) -> None:
    out = tmp_path / "cases_input" / "sobol_demo"
    packaged = package_directory(src=generated_dir, config_template=template_path, output_dir=out)
    for p in packaged:
        assert p.parent == out
        assert (p / "inlet.stl").exists()
        assert (p / "wall_aorta.stl").exists()
        assert (p / "config.json").exists()
    # Original generated dir untouched (no config.json added in-place)
    assert not (generated_dir / "case_001" / "config.json").exists()


def test_skips_dirs_without_stls(generated_dir: Path, template_path: Path) -> None:
    packaged = package_directory(src=generated_dir, config_template=template_path)
    names = [p.name for p in packaged]
    assert "not_a_case" not in names


def test_does_not_mutate_caller_template(generated_dir: Path, template_path: Path) -> None:
    """Packaging case_002 should not change the outlet list for case_001."""
    before = json.loads(template_path.read_text())
    package_directory(src=generated_dir, config_template=template_path)
    after = json.loads(template_path.read_text())
    assert before == after, "Template file on disk was modified"
