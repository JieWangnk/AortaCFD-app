"""
Per-run provenance record (RO-Crate).

Every case setup writes ``reports/ro-crate-metadata.json``: a small JSON-LD
document in RO-Crate 1.1 form, following the Workflow Run RO-Crate
"Process Run Crate" profile. It records what produced the run:

- AortaCFD version, git commit, branch and whether the checkout was dirty
- OpenFOAM version (from the sourced environment) and the Python version
- every input file (config JSON, STL patches, inlet CSV) with a sha256
- the resolved (merged) configuration file

The record is plain JSON. Nothing else in the pipeline depends on it, so a
failure here must never stop a run; callers wrap ``write_run_record`` in a
try/except and log a warning.

References:
    RO-Crate 1.1: https://w3id.org/ro/crate/1.1
    Workflow Run RO-Crate, Process Run Crate profile: https://w3id.org/ro/wfrun/process/0.5
    Leo S. et al. Recording provenance of workflow runs with RO-Crate. PLoS ONE 2024.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess  # nosec B404 - git is invoked with a fixed argument list, no shell
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

RO_CRATE_CONTEXT = "https://w3id.org/ro/crate/1.1/context"
PROCESS_RUN_PROFILE = "https://w3id.org/ro/wfrun/process/0.5"
WFRUN_TERMS = "https://w3id.org/ro/terms/workflow-run#"
RECORD_FILENAME = "ro-crate-metadata.json"


def _package_version() -> str:
    try:
        from aortacfd_lib import __version__

        return str(__version__)
    except Exception:  # noqa: BLE001
        return "unknown"


def default_repo_root() -> Path:
    """Repository root when running from a git checkout (src/aortacfd_lib/run_record.py -> root)."""
    return Path(__file__).resolve().parents[2]


def git_state(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Return ``{"commit", "branch", "dirty"}`` for a git checkout, or ``{}`` outside one.

    ``dirty`` is True when ``git status --porcelain`` lists any tracked change
    or untracked file. Each call is bounded by a short timeout so a hung git
    (network filesystem, lock) cannot stall the pipeline.
    """
    root = Path(repo_root) if repo_root else default_repo_root()
    if not (root / ".git").exists():
        return {}

    def _git(*args: str) -> Optional[str]:
        try:
            out = subprocess.run(  # nosec B603 B607 - fixed argv, no shell
                ["git", *args], cwd=root, capture_output=True, text=True, timeout=3, check=False
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return out.stdout.strip() if out.returncode == 0 else None

    commit = _git("rev-parse", "HEAD")
    if not commit:
        return {}
    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or ""
    status = _git("status", "--porcelain", "--untracked-files=normal")
    return {"commit": commit, "branch": branch, "dirty": bool(status)}


def openfoam_version() -> Optional[str]:
    """OpenFOAM version from the sourced environment (``WM_PROJECT_VERSION``), else from ``WM_PROJECT_DIR``."""
    version = os.environ.get("WM_PROJECT_VERSION")
    if version:
        return version
    project_dir = os.environ.get("WM_PROJECT_DIR", "")
    tail = Path(project_dir).name if project_dir else ""
    return tail.replace("OpenFOAM-", "") or None


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _file_entity(path: Path, root: Path) -> Dict[str, Any]:
    try:
        rel = str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        rel = str(path.resolve())
    return {
        "@id": rel,
        "@type": "File",
        "name": path.name,
        "contentSize": path.stat().st_size,
        "sha256": sha256_of(path),
    }


def build_run_record(
    case_name: str,
    input_files: Iterable[Path],
    output_files: Iterable[Path],
    output_dir: Path,
    repo_root: Optional[Path] = None,
    now: Optional[datetime] = None,
    extra_software: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Assemble the RO-Crate graph for one case setup.

    Args:
        case_name: patient / case identifier (used as the dataset name)
        input_files: files the setup read (config, STL patches, inlet CSV)
        output_files: files the setup wrote that should be listed (merged config)
        output_dir: run output directory; file ids are made relative to it where possible
        repo_root: git checkout root (defaults to this package's checkout)
        now: timestamp override (tests); default UTC now
        extra_software: further SoftwareApplication entities (for example a compiled BC library)
    """
    stamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    output_dir = Path(output_dir)
    git = git_state(repo_root)

    aortacfd: Dict[str, Any] = {
        "@id": "#aortacfd",
        "@type": "SoftwareApplication",
        "name": "AortaCFD",
        "version": _package_version(),
        "codeRepository": "https://github.com/JieWangnk/AortaCFD-app",
    }
    if git:
        aortacfd["gitCommit"] = git["commit"]
        aortacfd["gitBranch"] = git["branch"]
        aortacfd["gitDirty"] = git["dirty"]

    software: List[Dict[str, Any]] = [
        aortacfd,
        {
            "@id": "#openfoam",
            "@type": "SoftwareApplication",
            "name": "OpenFOAM",
            "version": openfoam_version() or "unknown",
        },
        {
            "@id": "#python",
            "@type": "SoftwareApplication",
            "name": "Python",
            "version": platform.python_version(),
            "executable": sys.executable,
        },
    ]
    software.extend(extra_software or [])

    inputs = [_file_entity(Path(p), output_dir) for p in input_files if Path(p).is_file()]
    outputs = [_file_entity(Path(p), output_dir) for p in output_files if Path(p).is_file()]

    run_action = {
        "@id": "#run",
        "@type": "CreateAction",
        "name": f"AortaCFD case setup: {case_name}",
        "startTime": stamp,
        "instrument": {"@id": "#aortacfd"},
        "object": [{"@id": e["@id"]} for e in inputs],
        "result": [{"@id": e["@id"]} for e in outputs],
        "environment": [{"@id": "#openfoam"}, {"@id": "#python"}],
    }

    root_dataset = {
        "@id": "./",
        "@type": "Dataset",
        "name": f"AortaCFD run: {case_name}",
        "datePublished": stamp,
        "conformsTo": {"@id": PROCESS_RUN_PROFILE},
        "hasPart": [{"@id": e["@id"]} for e in inputs + outputs],
        "mentions": [{"@id": "#run"}],
    }

    descriptor = {
        "@id": RECORD_FILENAME,
        "@type": "CreativeWork",
        "conformsTo": [{"@id": "https://w3id.org/ro/crate/1.1"}, {"@id": PROCESS_RUN_PROFILE}],
        "about": {"@id": "./"},
    }

    return {
        "@context": [
            RO_CRATE_CONTEXT,
            {
                "sha256": WFRUN_TERMS + "sha256",
                "gitCommit": WFRUN_TERMS + "gitCommit",
                "gitBranch": WFRUN_TERMS + "gitBranch",
                "gitDirty": WFRUN_TERMS + "gitDirty",
                "executable": WFRUN_TERMS + "executable",
            },
        ],
        "@graph": [descriptor, root_dataset, run_action, *software, *inputs, *outputs],
    }


def write_run_record(output_dir: Path, record: Dict[str, Any]) -> Path:
    """Write the record to ``<output_dir>/reports/ro-crate-metadata.json`` and return its path."""
    reports = Path(output_dir) / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    path = reports / RECORD_FILENAME
    with open(path, "w") as f:
        json.dump(record, f, indent=2)
    return path


def collect_case_inputs(config: Dict[str, Any]) -> List[Path]:
    """Input files for a case: the config JSON plus every regular file in the patient input folder."""
    files: List[Path] = []
    seen = set()

    def _add(p: Path) -> None:
        key = p.resolve()
        if key not in seen:
            seen.add(key)
            files.append(p)

    cfg_path = config.get("_config_file_path")
    if cfg_path and Path(cfg_path).is_file():
        _add(Path(cfg_path))
    patient_dir = config.get("patient_case_directory") or ""
    if patient_dir and Path(patient_dir).is_dir():
        for p in sorted(Path(patient_dir).iterdir()):
            if p.is_file() and p.suffix.lower() in {".stl", ".csv", ".json", ".txt", ".obj", ".vtp", ".npz"}:
                _add(p)
    return files
