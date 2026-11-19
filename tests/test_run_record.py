"""Tests for the per-run RO-Crate provenance record."""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from aortacfd_lib import run_record as rr


@pytest.fixture
def fake_repo(tmp_path):
    """A tiny git repository with one commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    (repo / "a.txt").write_text("a")
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True, env={**env, "PATH": "/usr/bin:/bin"})
    return repo


def test_sha256_matches_hashlib(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"hello world")
    import hashlib

    assert rr.sha256_of(f) == hashlib.sha256(b"hello world").hexdigest()


def test_git_state_clean_then_dirty(fake_repo):
    state = rr.git_state(fake_repo)
    assert len(state["commit"]) == 40
    assert state["branch"] == "main"
    assert state["dirty"] is False
    (fake_repo / "b.txt").write_text("b")  # untracked file counts as dirty
    assert rr.git_state(fake_repo)["dirty"] is True


def test_git_state_outside_repo(tmp_path):
    assert rr.git_state(tmp_path) == {}


def test_openfoam_version_from_env(monkeypatch):
    monkeypatch.setenv("WM_PROJECT_VERSION", "12")
    assert rr.openfoam_version() == "12"
    monkeypatch.delenv("WM_PROJECT_VERSION")
    monkeypatch.setenv("WM_PROJECT_DIR", "/opt/openfoam12")
    assert rr.openfoam_version() == "openfoam12"
    monkeypatch.delenv("WM_PROJECT_DIR")
    assert rr.openfoam_version() is None


def test_build_and_write_record(tmp_path, fake_repo):
    out = tmp_path / "run"
    out.mkdir()
    cfg = tmp_path / "config.json"
    cfg.write_text("{}")
    stl = tmp_path / "inlet.stl"
    stl.write_bytes(b"solid x\nendsolid x\n")
    merged = out / "reports" / "merged_config.json"
    merged.parent.mkdir()
    merged.write_text("{}")

    when = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
    rec = rr.build_run_record(
        "CASE1", [cfg, stl, tmp_path / "missing.csv"], [merged], out, repo_root=fake_repo, now=when
    )
    path = rr.write_run_record(out, rec)

    assert path == out / "reports" / rr.RECORD_FILENAME
    data = json.loads(path.read_text())
    graph = {e["@id"]: e for e in data["@graph"]}
    assert graph["./"]["@type"] == "Dataset"
    assert graph["#run"]["startTime"] == "2026-11-19T12:00:00+00:00"
    assert graph["#aortacfd"]["gitCommit"] == rr.git_state(fake_repo)["commit"]
    assert graph["#aortacfd"]["gitDirty"] is False
    # inputs: missing file is skipped, present ones carry a sha256 and size
    in_ids = [o["@id"] for o in graph["#run"]["object"]]
    assert len(in_ids) == 2
    assert all("sha256" in graph[i] and graph[i]["contentSize"] > 0 for i in in_ids)
    # the merged config is listed as a result, relative to the run directory
    assert graph["#run"]["result"] == [{"@id": "reports/merged_config.json"}]
    assert "sha256" in data["@context"][1]


def test_collect_case_inputs(tmp_path):
    pdir = tmp_path / "PAT"
    pdir.mkdir()
    for n in ["inlet.stl", "wall.stl", "flow.csv", "notes.md", "big.vtk"]:
        (pdir / n).write_text("x")
    cfg = pdir / "config.json"
    cfg.write_text("{}")
    # config path absolute, patient dir relative to the cwd: both spellings of config.json must collapse to one
    rel = Path(os.path.relpath(pdir))
    files = rr.collect_case_inputs({"_config_file_path": str(cfg.resolve()), "patient_case_directory": str(rel)})
    names = [f.name for f in files]
    assert names[0] == "config.json"
    assert "inlet.stl" in names and "flow.csv" in names
    assert "notes.md" not in names and "big.vtk" not in names
    assert names.count("config.json") == 1
