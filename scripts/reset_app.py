"""Reset the AortaCFD application to a fresh-clone-equivalent state.

Removes everything regenerable (output/, build artefacts, Python caches)
while preserving user data (cases_input/) and the installed environment
(venv/, unless --include-venv is passed).

Default behaviour is **dry-run** — prints what would be removed, with
sizes, and exits without touching disk. Pass ``--yes`` (or set the
``CONFIRM=yes`` env var when invoked via ``make clean-all``) to actually
delete.

Safety guards:
  - Paths are resolved relative to the repo root (the script's parent).
    Anything that resolves outside the repo aborts the run.
  - A hard-coded set of "always-protect" paths is checked before any
    delete. If a target accidentally overlaps one of them, the run
    aborts loudly.

Usage::

    python -m scripts.reset_app                    # dry-run, default
    python -m scripts.reset_app --yes              # actually delete
    python -m scripts.reset_app --yes --include-venv
    make clean-all                                 # same as dry-run
    make clean-all CONFIRM=yes                     # actually delete
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]

# Top-level directories and files that are *always* preserved.
# A target that would touch any of these aborts the run.
PROTECTED_TOPLEVEL = frozenset({
    "cases_input",      # user case directories
    "src",              # source code
    "scripts",          # CLI tools (this script lives here)
    "examples",         # config templates + case template
    "docs",             # documentation
    "tests",            # test suite
    ".git",
    ".github",
    ".zenodo.json",
    "CHANGELOG.md",
    "CITATION.cff",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "Makefile",
    "README.md",
    "pyproject.toml",
    "run_batch.py",
    "run_patient.py",
})

# Always-removed: regenerable artefacts. These are deleted whenever the
# user passes --yes. Each entry is either a top-level path (relative to
# repo root) or a glob pattern that we recurse for.
ALWAYS_REMOVE_TOPLEVEL = [
    "output",
    "build",
    "dist",
    "batch_submit.sh",
    ".pytest_cache",
    ".mypy_cache",
    ".coverage",
    "coverage.xml",
    "htmlcov",
]

# Glob patterns matched anywhere under the repo (recursively).
ALWAYS_REMOVE_GLOB = [
    "**/__pycache__",
    "**/*.pyc",
    "**/*.pyo",
    "**/*.egg-info",
]


# ─────────────────────────────────────────────────────────────────────────────
# Path discovery & safety
# ─────────────────────────────────────────────────────────────────────────────


def _is_inside_repo(p: Path) -> bool:
    try:
        p.resolve().relative_to(REPO_ROOT)
        return True
    except ValueError:
        return False


def _is_protected(p: Path) -> bool:
    """True if the path is (or is inside) one of the protected top-level entries.

    Used as a "this should never be deleted" guard.
    """
    try:
        rel = p.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return False
    if not rel.parts:
        return True  # the repo root itself
    return rel.parts[0] in PROTECTED_TOPLEVEL


def _path_size(p: Path) -> int:
    """Total size in bytes (recursive for directories, plain for files)."""
    if p.is_file() or p.is_symlink():
        try:
            return p.stat().st_size
        except OSError:
            return 0
    total = 0
    for f in p.rglob("*"):
        try:
            if f.is_file() and not f.is_symlink():
                total += f.stat().st_size
        except OSError:
            continue
    return total


def _humanise(n_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    n = float(n_bytes)
    for u in units:
        if n < 1024 or u == units[-1]:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


def _filter_redundant(paths: list[Path]) -> list[Path]:
    """Drop paths whose ancestor is already in the list.

    Without this, `**/*.pyc` and `**/__pycache__` double-count the same
    bytes (every .pyc inside a __pycache__ appears twice in the report).
    """
    path_set = {p.resolve() for p in paths}
    out: list[Path] = []
    for p in paths:
        pr = p.resolve()
        if any(ancestor in path_set for ancestor in pr.parents):
            continue
        out.append(p)
    return out


def discover_targets(include_venv: bool = False) -> list[Path]:
    """Return the list of paths that would be removed.

    Order: top-level explicit entries first, then recursive glob matches.
    Deduplicated (no path whose ancestor is also a target). Excludes
    paths that don't exist.
    """
    targets: list[Path] = []
    seen: set[Path] = set()

    explicit = list(ALWAYS_REMOVE_TOPLEVEL)
    if include_venv:
        explicit.append("venv")

    for name in explicit:
        p = (REPO_ROOT / name).resolve()
        if p.exists() and p not in seen:
            targets.append(p)
            seen.add(p)

    # Toplevels we never recurse into during glob matching. __pycache__
    # inside src/, tests/, scripts/ is fine to clean; inside venv/,
    # cases_input/, examples/, docs/, .git/ it is not.
    glob_skip_toplevels = {".git", "cases_input", "examples", "docs"}
    if not include_venv:
        glob_skip_toplevels.add("venv")

    for pattern in ALWAYS_REMOVE_GLOB:
        for p in REPO_ROOT.glob(pattern):
            try:
                rel = p.resolve().relative_to(REPO_ROOT)
            except ValueError:
                continue
            if rel.parts and rel.parts[0] in glob_skip_toplevels:
                continue
            if p not in seen and p.exists():
                targets.append(p)
                seen.add(p)

    return _filter_redundant(targets)


def assert_safe(targets: Iterable[Path]) -> None:
    """Abort if any target is outside the repo or accidentally hits a protected toplevel."""
    for p in targets:
        if not _is_inside_repo(p):
            raise SystemExit(f"REFUSING: target outside repo root: {p}")
        rel = p.resolve().relative_to(REPO_ROOT)
        # __pycache__ inside protected toplevels is OK; the protected
        # toplevel itself is not.
        if len(rel.parts) == 1 and rel.parts[0] in PROTECTED_TOPLEVEL:
            raise SystemExit(
                f"REFUSING: target matches protected toplevel: {rel}\n"
                f"This is a bug in reset_app.py — please report it."
            )


# ─────────────────────────────────────────────────────────────────────────────
# Action
# ─────────────────────────────────────────────────────────────────────────────


def _delete(p: Path) -> None:
    if p.is_dir() and not p.is_symlink():
        shutil.rmtree(p)
    else:
        p.unlink(missing_ok=True)


def _print_report(targets: list[Path], header: str) -> int:
    """Print a sized list, returns the total bytes freed."""
    if not targets:
        print(f"{header}: nothing to remove. Already clean.")
        return 0

    print(f"{header}:")
    total = 0
    for p in sorted(targets):
        try:
            rel = p.resolve().relative_to(REPO_ROOT)
        except ValueError:
            rel = p
        size = _path_size(p)
        total += size
        kind = "dir" if p.is_dir() else "file"
        print(f"  [{kind:4s}] {_humanise(size):>10s}   {rel}")
    print(f"  {'─' * 40}")
    print(f"  {'total':>15s} {_humanise(total):>10s}")
    return total


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="reset_app",
        description=(
            "Reset the AortaCFD application to a fresh-clone-equivalent state. "
            "Removes output/, build artefacts, and Python caches. "
            "Preserves cases_input/, venv/, and the repo source."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--yes", "-y", action="store_true",
                   help="Actually delete (default is dry-run).")
    p.add_argument("--include-venv", action="store_true",
                   help="Also delete venv/ (rare; for a true rebuild). "
                        "After this, run `make install` to recreate it.")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="More detail on each delete.")
    args = p.parse_args(argv)

    targets = discover_targets(include_venv=args.include_venv)
    assert_safe(targets)

    if not args.yes:
        total = _print_report(targets, header="Would remove (dry-run)")
        if targets:
            print()
            print("Re-run with --yes to actually delete.")
            print("Or via make:  make clean-all CONFIRM=yes")
        return 0

    total = _print_report(targets, header="Removing")
    print()
    for t in targets:
        try:
            if args.verbose:
                print(f"  rm {t}")
            _delete(t)
        except OSError as e:
            print(f"  ! could not remove {t}: {e}", file=sys.stderr)
    print(f"Done. Freed approximately {_humanise(total)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
