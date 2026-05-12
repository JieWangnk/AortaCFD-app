"""Environment diagnostics for AortaCFD — invoked via `--doctor`.

Checks the user's environment for the common things that go wrong on a fresh
install (Python version, declared deps importable, OpenFOAM sourced, sample
geometry parseable, output disk has headroom). Exits 0 if all hard checks
pass; 1 if anything failed.
"""

from __future__ import annotations

import importlib
import os
import shutil
import sys
from pathlib import Path
from typing import List, Tuple


def _color(s: str, c: str) -> str:
    """ANSI-colour `s` if stdout is a TTY, else return plain text."""
    if not sys.stdout.isatty():
        return s
    codes = {"green": "32", "yellow": "33", "red": "31", "dim": "2", "bold": "1"}
    return f"\033[{codes[c]}m{s}\033[0m"


def _ok(msg: str) -> None:
    print(f"  {_color('✓', 'green')} {msg}")


def _warn(msg: str) -> None:
    print(f"  {_color('!', 'yellow')} {msg}")


def _fail(msg: str) -> None:
    print(f"  {_color('✗', 'red')} {msg}")


def _check_python() -> bool:
    v = sys.version_info
    if v >= (3, 10):
        _ok(f"Python {v.major}.{v.minor}.{v.micro} (>= 3.10 required)")
        return True
    _fail(f"Python {v.major}.{v.minor}.{v.micro} is too old; need >= 3.10")
    return False


def _check_runtime_deps() -> bool:
    """Try to import every package declared in pyproject [project.dependencies]."""
    # Pinned list, kept in sync with pyproject.toml. Names are import names,
    # which differ from distribution names in two cases (numpy-stl -> stl,
    # scikit-learn -> sklearn, pyyaml -> yaml).
    deps: List[Tuple[str, str]] = [
        ("numpy", "numpy"),
        ("scipy", "scipy"),
        ("pandas", "pandas"),
        ("matplotlib", "matplotlib"),
        ("jinja2", "jinja2"),
        ("stl", "numpy-stl"),
        ("sklearn", "scikit-learn"),
        ("vtk", "vtk"),
        ("yaml", "pyyaml"),
        ("pydantic", "pydantic"),
        ("psutil", "psutil"),
    ]
    all_ok = True
    for import_name, dist_name in deps:
        try:
            importlib.import_module(import_name)
            _ok(f"{dist_name} importable")
        except ImportError as e:
            _fail(f"{dist_name} not importable: {e}")
            all_ok = False
    return all_ok


def _check_openfoam() -> bool:
    """OpenFOAM 12 must be sourced for mesh/solver/reconstruct steps. Warning only."""
    wm_project = os.environ.get("WM_PROJECT_VERSION")
    if wm_project == "12":
        _ok(f"OpenFOAM 12 sourced (WM_PROJECT_VERSION={wm_project})")
        return True

    blockmesh = shutil.which("blockMesh")
    if blockmesh:
        _warn(
            f"OpenFOAM not sourced but blockMesh is on PATH at {blockmesh}. "
            "Source /opt/openfoam12/etc/bashrc before running mesh/solver/reconstruct."
        )
    else:
        _warn(
            "OpenFOAM 12 not detected. The case and postprocess steps work without it, "
            "but mesh/solver/reconstruct will fail. See README install section."
        )
    return True  # soft, doesn't affect exit


def _check_sample_stls(repo_root: Path) -> bool:
    """Each case under cases_input/ must have a parseable inlet.stl and at least one outletN.stl."""
    cases_dir = repo_root / "cases_input"
    if not cases_dir.is_dir():
        _warn(f"cases_input/ not found at {cases_dir} — skipping STL check")
        return True

    try:
        from stl import mesh as stl_mesh  # type: ignore
    except ImportError:
        _fail("numpy-stl not importable — cannot validate sample geometry")
        return False

    seen_any = False
    all_ok = True
    for case in sorted(cases_dir.iterdir()):
        if not case.is_dir():
            continue
        if case.name.startswith(".") or case.name == "PAT003":  # PAT003 is gitignored
            continue
        stls = sorted(case.glob("*.stl"))
        if not stls:
            continue
        seen_any = True
        for s in stls:
            try:
                m = stl_mesh.Mesh.from_file(str(s))
                n_tri = len(m.vectors)
                if n_tri < 10:
                    _warn(f"{s.relative_to(repo_root)}: only {n_tri} triangles — likely degenerate")
                else:
                    _ok(f"{s.relative_to(repo_root)}: {n_tri:,} triangles")
            except Exception as e:
                _fail(f"{s.relative_to(repo_root)}: cannot parse — {e}")
                all_ok = False
    if not seen_any:
        _warn("No STL files found in any cases_input/*/ subdirectory")
    return all_ok


def _check_disk(repo_root: Path) -> bool:
    """Soft: warn if <5 GB free on the partition where output/ lives. Each run is ~150MB."""
    output = repo_root / "output"
    target = output if output.exists() else repo_root
    try:
        usage = shutil.disk_usage(str(target))
        free_gb = usage.free / 1e9
        if free_gb >= 5:
            _ok(f"{free_gb:.1f} GB free on {target.resolve().anchor or target.resolve()}")
        else:
            _warn(
                f"only {free_gb:.1f} GB free on {target.resolve()} — each AortaCFD run is "
                "~150 MB, consider --max-runs N or freeing space."
            )
        return True
    except OSError as e:
        _warn(f"could not stat free space on {target}: {e}")
        return True


def _check_optional_tools() -> bool:
    """Soft: check for tools the postprocess/paraview steps want."""
    for tool, hint in (
        ("paraview", "for --steps paraview only"),
        ("foamPostProcess", "ships with OpenFOAM 12"),
    ):
        path = shutil.which(tool)
        if path:
            _ok(f"{tool} -> {path}")
        else:
            _warn(f"{tool} not on PATH ({hint})")
    return True


def _section(title: str) -> None:
    print(f"\n{_color(title, 'bold')}")


def run_doctor() -> int:
    """Run all checks and return an exit code (0 = green, 1 = red)."""
    repo_root = Path(__file__).resolve().parents[2]
    print(_color("AortaCFD doctor", "bold"))
    print(_color(f"  repo: {repo_root}", "dim"))

    _section("Python")
    py_ok = _check_python()

    _section("Runtime dependencies")
    deps_ok = _check_runtime_deps()

    _section("OpenFOAM 12")
    _check_openfoam()  # soft

    _section("Sample geometry (cases_input/*/*.stl)")
    stl_ok = _check_sample_stls(repo_root)

    _section("Disk space")
    _check_disk(repo_root)  # soft

    _section("Optional tools")
    _check_optional_tools()  # soft

    print()
    if py_ok and deps_ok and stl_ok:
        print(_color("All hard checks passed.", "green"))
        return 0
    print(_color("One or more hard checks failed — see above.", "red"))
    return 1
