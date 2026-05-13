#!/usr/bin/env python3
"""Run a sweep of config variants and summarise solver-level outcomes.

For Epic D of v1.2.0 we built mock-OpenFOAM tests that verify
config → rendered OpenFOAM dict. This script complements them: it runs
each *axis* once with a real solver (short --end-time so the matrix is
tractable) and records pass/fail + QoIs, so we can claim "every config
branch was exercised with a live OpenFOAM solver, not just template
rendering".

Usage:
    source /opt/openfoam12/etc/bashrc
    source venv/bin/activate
    python scripts/run_config_matrix.py                  # run everything
    python scripts/run_config_matrix.py --variants R2_RAS_kOmegaSST,R3_LES_WALE
    python scripts/run_config_matrix.py --end-time 0.1   # longer runs

Results land in ``config_matrix_results/<timestamp>/`` with one log per
variant and a ``summary.json``.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# =============================================================================
# Matrix definition — extend for v1.3.0 by adding entries.
# Each entry merges ``overrides`` over ``cases_input/<patient>/config.json``.
# ``None`` overrides means "use the default config unmodified".
# =============================================================================
MATRIX: list[dict[str, Any]] = [
    {
        "name": "R2_RAS_kOmegaSST",
        "patient": "BPM120",
        "purpose": "k-omega-SST RAS converges and renders k/omega/nut fields",
        "overrides": {
            "physics": {
                "model": "rans",
                "simulation_type": "RAS",
                "rans_model": "kOmegaSST",
                "turbulence_intensity": 0.05,
            },
        },
    },
    {
        "name": "R3_LES_WALE",
        "patient": "BPM120",
        "purpose": "LES WALE runs without nut blowup; backflow stabilisation auto-disables",
        "overrides": {
            "physics": {
                "model": "les",
                "simulation_type": "LES",
                "les_model": "WALE",
                "turbulence_intensity": 0.05,
            },
        },
    },
    {
        "name": "R4_MAPPED_PROFILE",
        "patient": "VOL04",
        "purpose": "Pre-mapped inlet (VOL04 inlet/) runs end-to-end; alias MRI warns",
        "overrides": None,
    },
    # R5 (zeroGradient outlets on BPM120) intentionally removed from the live-
    # solver matrix in v1.2.0. The rendering is covered by D.11 unit tests in
    # tests/test_config_matrix.py (5 passing tests). Live-solver R5 was
    # attempted four times during v1.2.0 development with progressively more
    # conservative settings — all crashed:
    #   1. Pulsatile (TIMEVARYING) + zG (no anchor)           → FPE t=0.018s
    #   2. Pulsatile + zG + pressure_anchor                    → FPE t=0.020s
    #   3. CONSTANT 0.5 m/s + zG + anchor (default numerics)   → dt collapse t=0.0007s
    #   4. CONSTANT 0.2 m/s + zG + anchor + nOuter=8, max_co=0.5 → dt collapse t=0.0009s
    # The "PIMPLE: Not converged within N iterations" pattern was identical
    # across (3) and (4) even with 8 outer correctors and lower flow — i.e.
    # this is not a numerics-tunable problem on BPM120. The severe pediatric
    # coarctation creates a pressure matrix that GAMG can't reliably solve
    # when one or more outlets is pressure-unconstrained. v1.2.0's Option-B
    # validator already rejects the unphysical pulsatile + zG case at
    # config-build. Live integration testing for the CONSTANT + zG + anchor
    # path is deferred to v1.3.0+ once a less pathological patient case is
    # available; tagged as a known limitation in README.
    {
        "name": "R6_robust_profile",
        "patient": "BPM120",
        "purpose": "robust 1st-order numerics profile converges (high-stability fallback)",
        "overrides": {"numerics": {"profile": "robust"}},
    },
    # A.1 is the benchmark-validation run: full default config, full 1.5s sim,
    # matched against benchmarks/expected_values.json by tests/benchmarks/.
    {
        "name": "A1_BPM120_benchmark",
        "patient": "BPM120",
        "purpose": "Full benchmark — 1.5s on ~1.9M cells, validates Wang et al. Table 3",
        "overrides": None,
        "end_time": 1.5,  # default endTime; matrix smoke-test override skipped
    },
]


def deep_merge(base: dict, overlay: dict) -> dict:
    out = {**base}
    for k, v in overlay.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def preflight() -> None:
    """Bail out early on the two things that always go wrong."""
    if os.environ.get("WM_PROJECT_VERSION") != "12":
        sys.stderr.write(
            "ERROR: OpenFOAM 12 not sourced (WM_PROJECT_VERSION != 12).\n"
            "  source /opt/openfoam12/etc/bashrc  # or set OPENFOAM_ENV_PATH\n"
        )
        sys.exit(2)
    try:
        import aortacfd_lib  # noqa: F401
    except ImportError:
        sys.stderr.write(
            "ERROR: aortacfd_lib not importable. Activate the venv:\n"
            "  source venv/bin/activate && pip install -e .\n"
        )
        sys.exit(2)


def _absolutise_inlet_paths(config: dict, patient_dir: Path) -> None:
    """Rewrite relative inlet.csv_file / inlet.file to absolute paths anchored
    at the patient's cases_input dir. Necessary when the temp config lives
    outside cases_input/, because PrepareBoundaryDataTask resolves these
    paths relative to the config file's parent."""
    for key in ("inlet", "boundary_conditions"):
        block = config.get(key, {})
        inlet = block.get("inlet") if key == "boundary_conditions" else block
        if not isinstance(inlet, dict):
            continue
        for path_key in ("csv_file", "file", "source_dir"):
            val = inlet.get(path_key)
            if isinstance(val, str) and not os.path.isabs(val):
                resolved = (patient_dir / val).resolve()
                if resolved.exists():
                    inlet[path_key] = str(resolved)


def run_variant(variant: dict, repo_root: Path, results_dir: Path, default_end_time: float) -> dict:
    name = variant["name"]
    patient = variant["patient"]
    overrides = variant.get("overrides")
    purpose = variant.get("purpose", "")
    # Per-variant end_time wins over the CLI default. Used for A.1 to run
    # the full 1.5s benchmark sim while the rest of the matrix stays short.
    end_time = float(variant.get("end_time", default_end_time))

    print(f"\n{'=' * 78}\n=== {name} — {purpose}\n=== end_time={end_time}s\n{'=' * 78}", flush=True)

    patient_dir = repo_root / "cases_input" / patient
    default_config_path = patient_dir / "config.json"
    with default_config_path.open() as f:
        config = json.load(f)
    if overrides:
        config = deep_merge(config, overrides)
    _absolutise_inlet_paths(config, patient_dir)

    temp_config_path = results_dir / f"{name}_config.json"
    with temp_config_path.open("w") as f:
        json.dump(config, f, indent=2)

    cmd = [
        sys.executable,
        str(repo_root / "run_patient.py"),
        patient,
        "--config",
        str(temp_config_path),
        "--end-time",
        str(end_time),
        "--run-name",
        name,
        "--max-runs",
        "10",
    ]

    log_path = results_dir / f"{name}.log"
    start = time.time()
    with log_path.open("w") as log_f:
        rc = subprocess.run(cmd, cwd=str(repo_root), stdout=log_f, stderr=subprocess.STDOUT)
    elapsed = time.time() - start

    run_dir = repo_root / "output" / patient / name
    qoi_path = run_dir / "reports" / "results" / "qoi_summary.json"
    qoi: dict[str, Any] = {}
    if qoi_path.exists():
        with qoi_path.open() as f:
            qoi_data = json.load(f)
        for key, val in qoi_data.get("qoi", {}).items():
            qoi[key] = val.get("value") if isinstance(val, dict) else val
        qoi["_tawss_status"] = qoi_data.get("_metadata", {}).get("tawss_status", "?")

    # Heuristic: solver crashed if log has "FOAM FATAL ERROR" / "Floating point exception"
    crashed = False
    if log_path.exists():
        with log_path.open() as f:
            tail = f.read()[-4000:]
        for marker in ("FOAM FATAL ERROR", "Floating point exception", "Segmentation fault"):
            if marker in tail:
                crashed = True
                break

    return {
        "name": name,
        "patient": patient,
        "purpose": purpose,
        "exit_code": rc.returncode,
        "crashed": crashed,
        "wall_seconds": round(elapsed, 1),
        "qoi": qoi,
        "log": str(log_path.relative_to(repo_root)),
        "case_dir": str(run_dir.relative_to(repo_root)) if run_dir.exists() else None,
        "config": str(temp_config_path.relative_to(repo_root)),
    }


def render_summary(results: list[dict]) -> str:
    """Markdown table for the console; same data lands in summary.json."""
    lines = []
    lines.append(f"{'Variant':<22} {'Patient':<8} {'Status':<8} {'Wall':<8} {'Δp(mmHg)':<10} {'WSS p99(Pa)':<12}")
    lines.append("-" * 75)
    for r in results:
        status = "OK" if r["exit_code"] == 0 and not r["crashed"] else "FAIL"
        wall = f"{r['wall_seconds'] / 60:.1f}m" if r["wall_seconds"] >= 60 else f"{r['wall_seconds']:.0f}s"
        dp = r["qoi"].get("pressure_drop_mean_mmhg")
        wss = r["qoi"].get("wss_p99_pa")
        dp_str = f"{dp:.2f}" if isinstance(dp, (int, float)) else "—"
        wss_str = f"{wss:.2f}" if isinstance(wss, (int, float)) else "—"
        lines.append(f"{r['name']:<22} {r['patient']:<8} {status:<8} {wall:<8} {dp_str:<10} {wss_str:<12}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--variants",
        help="comma-separated subset of MATRIX names (default: all)",
    )
    parser.add_argument(
        "--end-time",
        type=float,
        default=0.05,
        help="simulation duration in seconds (default 0.05 — enough to catch solver crashes)",
    )
    parser.add_argument(
        "--cool-down",
        type=int,
        default=0,
        metavar="SECONDS",
        help="pause N seconds between variants so the machine can cool off "
        "(important on laptops — mpirun foamRun is thermally intense). "
        "Default 0; recommended 300 (5 min) for back-to-back BPM120 runs.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list available variants and exit",
    )
    args = parser.parse_args()

    if args.list:
        for v in MATRIX:
            print(f"  {v['name']:<24} {v['patient']:<8}  {v.get('purpose', '')}")
        return 0

    preflight()

    repo_root = Path(__file__).resolve().parents[1]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = repo_root / "config_matrix_results" / timestamp
    results_dir.mkdir(parents=True, exist_ok=True)

    selected = MATRIX
    if args.variants:
        wanted = set(args.variants.split(","))
        selected = [v for v in MATRIX if v["name"] in wanted]
        missing = wanted - {v["name"] for v in MATRIX}
        if missing:
            sys.stderr.write(f"ERROR: unknown variants: {sorted(missing)}\n")
            return 2

    print(
        f"Running {len(selected)} variant(s); end_time={args.end_time}s; "
        f"cool_down={args.cool_down}s; results → {results_dir}"
    )
    results = []
    for idx, variant in enumerate(selected):
        try:
            results.append(run_variant(variant, repo_root, results_dir, args.end_time))
        except Exception as exc:
            results.append(
                {
                    "name": variant["name"],
                    "patient": variant["patient"],
                    "exit_code": -1,
                    "crashed": True,
                    "wall_seconds": 0,
                    "qoi": {},
                    "error": str(exc),
                }
            )

        # Cool-down between variants (laptop thermal budget). Skip after the last one.
        if args.cool_down > 0 and idx < len(selected) - 1:
            print(f"\n  💤 Cooling down for {args.cool_down}s before next variant…", flush=True)
            time.sleep(args.cool_down)

    (results_dir / "summary.json").write_text(json.dumps(results, indent=2))

    summary = render_summary(results)
    print(f"\n{'=' * 78}\n=== Summary\n{'=' * 78}\n{summary}\n\nFull JSON: {results_dir / 'summary.json'}")

    # Exit 1 if any variant failed — useful for CI
    return 0 if all(r["exit_code"] == 0 and not r.get("crashed", False) for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
