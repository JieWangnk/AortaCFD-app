"""Tests for scripts/reset_app.py.

We can't run reset_app against the real repo (it would actually delete
things), so we monkey-patch ``REPO_ROOT`` to a tmp_path fixture and
build a fake repo tree inside it. The protected-paths logic and the
discover_targets logic are then exercised against that fake tree.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT_REAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT_REAL))

import scripts.reset_app as reset_app  # noqa: E402


@pytest.fixture
def fake_repo(tmp_path: Path, monkeypatch):
    """Build a fake AortaCFD-app repo tree under tmp_path."""
    # Protected toplevels (must survive)
    for name in ("cases_input", "src", "scripts", "examples", "docs", "tests", ".git"):
        (tmp_path / name).mkdir()
    for name in ("README.md", "Makefile", "pyproject.toml", "CHANGELOG.md",
                 "run_patient.py", "run_batch.py"):
        (tmp_path / name).write_text("# placeholder\n")

    # User data inside protected dirs (must survive)
    (tmp_path / "cases_input" / "BPM120").mkdir()
    (tmp_path / "cases_input" / "BPM120" / "config.json").write_text("{}")
    (tmp_path / "cases_input" / "BPM120" / "inlet.stl").write_text("solid\n")

    # Regenerable artefacts (must be removed)
    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "BPM120").mkdir()
    (tmp_path / "output" / "BPM120" / "run_20260101_120000").mkdir()
    (tmp_path / "output" / "BPM120" / "run_20260101_120000" / "log.solver").write_text("solver log content")

    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "lib").mkdir()
    (tmp_path / "build" / "lib" / "x.py").write_text("# build artefact")

    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "aortacfd-1.4.1.tar.gz").write_text("fake tarball")

    (tmp_path / "batch_submit.sh").write_text("#!/bin/bash\n#SBATCH ...\n")

    (tmp_path / ".pytest_cache").mkdir()
    (tmp_path / ".pytest_cache" / "CACHEDIR.TAG").write_text("Signature")
    (tmp_path / ".mypy_cache").mkdir()
    (tmp_path / ".coverage").write_text("data")

    # __pycache__ inside protected dirs (should still be removed — the
    # pycache content is regenerable even though src/ itself is protected)
    (tmp_path / "src" / "__pycache__").mkdir()
    (tmp_path / "src" / "__pycache__" / "module.cpython-312.pyc").write_text("bytecode")
    (tmp_path / "tests" / "__pycache__").mkdir()
    (tmp_path / "tests" / "__pycache__" / "test_x.cpython-312.pyc").write_text("bytecode")

    # *.egg-info (regenerable)
    (tmp_path / "aortacfd.egg-info").mkdir()
    (tmp_path / "aortacfd.egg-info" / "PKG-INFO").write_text("Metadata")

    # venv (must survive unless --include-venv)
    (tmp_path / "venv").mkdir()
    (tmp_path / "venv" / "bin").mkdir()
    (tmp_path / "venv" / "bin" / "python").write_text("#!/bin/bash\n")

    # Patch REPO_ROOT in the module
    monkeypatch.setattr(reset_app, "REPO_ROOT", tmp_path)
    return tmp_path


# ─── discover_targets ───────────────────────────────────────────────────────


def test_discovers_top_level_artefacts(fake_repo: Path) -> None:
    targets = reset_app.discover_targets()
    names = {p.name for p in targets}
    assert "output" in names
    assert "build" in names
    assert "dist" in names
    assert "batch_submit.sh" in names
    assert ".pytest_cache" in names
    assert ".mypy_cache" in names


def test_discovers_pycache_inside_protected_dirs(fake_repo: Path) -> None:
    targets = reset_app.discover_targets()
    # Both src/__pycache__ and tests/__pycache__ should be discovered
    pycaches = [p for p in targets if p.name == "__pycache__"]
    assert len(pycaches) >= 2


def test_does_not_discover_protected_dirs(fake_repo: Path) -> None:
    targets = reset_app.discover_targets()
    rels = {p.resolve().relative_to(fake_repo) for p in targets}
    for protected in ("cases_input", "src", "scripts", "examples", "docs", "tests"):
        assert Path(protected) not in rels, f"{protected} must not be a removal target"


def test_does_not_discover_protected_files(fake_repo: Path) -> None:
    targets = reset_app.discover_targets()
    rels = {p.resolve().relative_to(fake_repo) for p in targets}
    for f in ("README.md", "Makefile", "pyproject.toml", "CHANGELOG.md",
              "run_patient.py", "run_batch.py"):
        assert Path(f) not in rels


def test_venv_excluded_by_default(fake_repo: Path) -> None:
    targets = reset_app.discover_targets()
    names = {p.name for p in targets}
    assert "venv" not in names


def test_venv_included_with_flag(fake_repo: Path) -> None:
    targets = reset_app.discover_targets(include_venv=True)
    names = {p.name for p in targets}
    assert "venv" in names


def test_pycache_inside_venv_not_listed_by_default(fake_repo: Path) -> None:
    """A typical venv install has hundreds of __pycache__ dirs inside it.
    Default behaviour preserves the venv → must not touch its caches either."""
    (fake_repo / "venv" / "lib" / "python3.12" / "site-packages" / "pkg" / "__pycache__").mkdir(parents=True)
    (fake_repo / "venv" / "lib" / "python3.12" / "site-packages" / "pkg" / "__pycache__" / "x.pyc").write_text("bc")
    targets = reset_app.discover_targets(include_venv=False)
    for p in targets:
        rel = p.resolve().relative_to(fake_repo)
        assert rel.parts[0] != "venv", f"venv path {rel} should not be a target without --include-venv"


def test_pycache_inside_cases_input_never_touched(fake_repo: Path) -> None:
    """User data is sacred — even regenerable __pycache__ inside cases_input/
    is left alone to avoid surprising users."""
    (fake_repo / "cases_input" / "BPM120" / "__pycache__").mkdir()
    (fake_repo / "cases_input" / "BPM120" / "__pycache__" / "x.pyc").write_text("bc")
    targets = reset_app.discover_targets(include_venv=False)
    for p in targets:
        rel = p.resolve().relative_to(fake_repo)
        assert rel.parts[0] != "cases_input", f"cases_input path {rel} must never be a target"


def test_egg_info_discovered(fake_repo: Path) -> None:
    targets = reset_app.discover_targets()
    egg_infos = [p for p in targets if p.name.endswith(".egg-info")]
    assert len(egg_infos) >= 1


def test_no_redundant_targets(fake_repo: Path) -> None:
    """A .pyc file inside __pycache__ should appear once at most.

    If both the dir and the file are listed, the report double-counts
    bytes and is confusing.
    """
    targets = reset_app.discover_targets()
    target_set = {p.resolve() for p in targets}
    for p in targets:
        pr = p.resolve()
        ancestors = list(pr.parents)
        assert not any(a in target_set for a in ancestors), \
            f"{pr} has ancestor in target set: {[a for a in ancestors if a in target_set]}"


# ─── assert_safe ────────────────────────────────────────────────────────────


def test_assert_safe_rejects_outside_repo(fake_repo: Path, tmp_path: Path) -> None:
    outside = tmp_path.parent / "elsewhere"
    outside.mkdir(exist_ok=True)
    with pytest.raises(SystemExit, match="outside repo root"):
        reset_app.assert_safe([outside])


def test_assert_safe_rejects_protected_toplevel(fake_repo: Path) -> None:
    with pytest.raises(SystemExit, match="protected toplevel"):
        reset_app.assert_safe([fake_repo / "cases_input"])


def test_assert_safe_allows_normal_targets(fake_repo: Path) -> None:
    reset_app.assert_safe([fake_repo / "output", fake_repo / ".pytest_cache"])


# ─── main() — dry-run vs --yes ──────────────────────────────────────────────


def test_dry_run_does_not_delete(fake_repo: Path, capsys) -> None:
    assert (fake_repo / "output").exists()
    assert (fake_repo / "build").exists()
    rc = reset_app.main([])
    assert rc == 0
    assert (fake_repo / "output").exists(), "dry-run should preserve output/"
    assert (fake_repo / "build").exists(), "dry-run should preserve build/"
    captured = capsys.readouterr()
    assert "Would remove" in captured.out
    assert "Re-run with --yes" in captured.out


def test_yes_actually_deletes(fake_repo: Path) -> None:
    assert (fake_repo / "output").exists()
    assert (fake_repo / "build").exists()
    assert (fake_repo / "src" / "__pycache__").exists()
    rc = reset_app.main(["--yes"])
    assert rc == 0
    assert not (fake_repo / "output").exists()
    assert not (fake_repo / "build").exists()
    assert not (fake_repo / "src" / "__pycache__").exists()


def test_yes_preserves_user_data(fake_repo: Path) -> None:
    rc = reset_app.main(["--yes"])
    assert rc == 0
    assert (fake_repo / "cases_input" / "BPM120" / "config.json").exists()
    assert (fake_repo / "cases_input" / "BPM120" / "inlet.stl").exists()
    assert (fake_repo / "README.md").exists()
    assert (fake_repo / "venv" / "bin" / "python").exists()
    assert (fake_repo / "src").exists()


def test_yes_with_include_venv_deletes_venv(fake_repo: Path) -> None:
    assert (fake_repo / "venv").exists()
    rc = reset_app.main(["--yes", "--include-venv"])
    assert rc == 0
    assert not (fake_repo / "venv").exists()
    # Still preserves user data
    assert (fake_repo / "cases_input" / "BPM120").exists()


def test_idempotent_on_already_clean(fake_repo: Path, capsys) -> None:
    reset_app.main(["--yes"])
    rc = reset_app.main([])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Already clean" in captured.out
