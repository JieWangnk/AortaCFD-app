"""Cohort QoI aggregator (Block D of the parametric-study workflow).

Walks ``output/<case>/<run>/.../qoi_summary.json`` files, joins each row
with ``cases_input/<case_id>/case.meta.json`` (if present) and the run's
``manifest.json`` (if present), and writes ``cohort_comparison.csv``.

The function ``aggregate_qoi(output_root, run_dirs=...)`` is the entry
point imported by ``run_batch.py``. CLI entry: ``python -m
scripts.compare_cohort output/``.

Tolerates missing or failed cases — emits a row with the status carried
from the manifest, NaN values for missing QoIs. Never crashes on partial
data.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)


def _flatten_qoi(payload: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for name, entry in (payload.get("qoi") or {}).items():
        if isinstance(entry, dict) and "value" in entry:
            flat[name] = entry["value"]
        else:
            flat[name] = entry
    for k, v in (payload.get("per_outlet_pressure_drop_mmhg") or {}).items():
        flat[f"dp_{k}_mmhg"] = v
    md = payload.get("_metadata") or {}
    for key in ("inlet_type", "is_pulsatile", "cardiac_cycle_s", "tawss_status"):
        if key in md:
            flat[key] = md[key]
    return flat


def _find_qoi_files(roots: Iterable[Path]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for r in roots:
        if not r.exists():
            logger.warning("aggregate_qoi: search root not found: %s", r)
            continue
        for q in r.rglob("qoi_summary.json"):
            if q in seen:
                continue
            seen.add(q)
            out.append(q)
    return sorted(out)


def _case_run_from_path(qoi_path: Path, output_root: Path) -> tuple[str, str]:
    try:
        rel = qoi_path.resolve().relative_to(output_root.resolve())
    except ValueError:
        return qoi_path.parent.name, ""
    parts = rel.parts
    case_id = parts[0] if parts else qoi_path.stem
    run_id = parts[1] if len(parts) >= 2 else ""
    return case_id, run_id


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as e:
        logger.warning("Could not parse %s: %s", path, e)
        return {}


def _load_run_manifest(qoi_path: Path) -> dict[str, Any]:
    parent: Path | None = qoi_path.parent
    for _ in range(4):
        if parent is None:
            break
        cand = parent / "manifest.json"
        if cand.exists():
            return _load_json(cand)
        parent = parent.parent if parent != parent.parent else None
    return {}


def aggregate_qoi(
    output_root: str | Path,
    run_dirs: Iterable[str | Path] | None = None,
    cases_input_root: str | Path | None = None,
    output_path: str | Path | None = None,
    write_parquet: bool = False,
) -> Path:
    """Aggregate per-case ``qoi_summary.json`` files into one CSV.

    Parameters
    ----------
    output_root
        Root of CFD output directories (typically ``output/``).
    run_dirs
        Optional list of case directories to aggregate (relative or
        absolute). If None, walks all of ``output_root``.
    cases_input_root
        Where to look for ``case.meta.json``. Default: sibling
        ``cases_input/`` of ``output_root``.
    output_path
        Where to write the CSV. Default: ``<output_root>/cohort_comparison.csv``.
    write_parquet
        Also write ``.parquet`` beside the CSV.

    Returns
    -------
    Path to the written CSV.
    """
    import pandas as pd

    output_root = Path(output_root)
    if cases_input_root is None:
        cases_input_root = output_root.parent / "cases_input"
    cases_input_root = Path(cases_input_root)
    if output_path is None:
        output_path = output_root / "cohort_comparison.csv"
    output_path = Path(output_path)

    if run_dirs is not None:
        roots = [Path(d) for d in run_dirs]
    else:
        roots = [output_root]
    qoi_files = _find_qoi_files(roots)

    rows: list[dict[str, Any]] = []
    for qoi_path in qoi_files:
        payload = _load_json(qoi_path)
        case_id, run_id = _case_run_from_path(qoi_path, output_root)
        row: dict[str, Any] = {"case_id": case_id, "run_id": run_id}

        row.update(_flatten_qoi(payload))

        manifest = _load_run_manifest(qoi_path)
        row["status"] = manifest.get("status", "ok" if payload else "missing")
        if manifest.get("wall_seconds") is not None:
            row["wall_seconds"] = manifest["wall_seconds"]
        if "git" in manifest:
            row["git_sha"] = manifest["git"].get("sha")

        meta = _load_json(cases_input_root / case_id / "case.meta.json")
        for k, v in (meta.get("params") or {}).items():
            row[f"param_{k}"] = v
        if meta.get("source"):
            row["geometry_source"] = meta["source"]
        if "sample_index" in meta:
            row["sample_index"] = meta["sample_index"]
        if "seed" in meta:
            row["sweep_seed"] = meta["seed"]

        row["qoi_path"] = str(qoi_path)
        rows.append(row)

    df = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if df.empty:
        logger.warning("No qoi_summary.json files found under %s", output_root)
        df.to_csv(output_path, index=False)
        return output_path

    id_cols = [
        c
        for c in (
            "case_id",
            "run_id",
            "status",
            "sample_index",
            "sweep_seed",
            "geometry_source",
            "inlet_type",
            "is_pulsatile",
            "cardiac_cycle_s",
            "tawss_status",
            "git_sha",
            "wall_seconds",
        )
        if c in df.columns
    ]
    param_cols = sorted(c for c in df.columns if c.startswith("param_"))
    other_cols = sorted(c for c in df.columns if c not in id_cols and c not in param_cols and c != "qoi_path")
    ordered = id_cols + param_cols + other_cols + ["qoi_path"]
    df = df[[c for c in ordered if c in df.columns]]

    df.to_csv(output_path, index=False)
    if write_parquet:
        try:
            df.to_parquet(output_path.with_suffix(".parquet"), index=False)
        except Exception as e:
            logger.warning("Skipping parquet write (%s); pip install pyarrow to enable", e)

    logger.info("Wrote cohort comparison (%d rows) to %s", len(df), output_path)
    return output_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="compare_cohort",
        description=(
            "Aggregate per-case QoI summaries into one tidy CSV. "
            "Walks output/<case>/<run>/.../qoi_summary.json and joins with "
            "cases_input/<case>/case.meta.json plus run manifests."
        ),
    )
    p.add_argument(
        "output_root",
        type=Path,
        help="Root directory containing per-case output folders (typically output/).",
    )
    p.add_argument(
        "--cases",
        nargs="+",
        help="Specific case dirs to aggregate (relative to output_root). Default: all.",
    )
    p.add_argument(
        "--cases-input",
        type=Path,
        default=None,
        help="Where to look for case.meta.json (default: <output_root sibling>/cases_input).",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Where to write the CSV (default: <output_root>/cohort_comparison.csv).",
    )
    p.add_argument("--parquet", action="store_true", help="Also write .parquet beside the CSV.")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    run_dirs = [args.output_root / c for c in args.cases] if args.cases else None

    out = aggregate_qoi(
        output_root=args.output_root,
        run_dirs=run_dirs,
        cases_input_root=args.cases_input,
        output_path=args.output,
        write_parquet=args.parquet,
    )
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
