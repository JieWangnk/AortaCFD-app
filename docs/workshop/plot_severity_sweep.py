"""Workshop finale plot — QoIs vs coarctation severity.

Reads output/cohort_comparison.csv (Block D output) and produces a 2x2
panel of the four most-cited QoIs against the severity parameter from
the synthetic sweep. Used at the end of the workshop demo recording.

Usage:
    python docs/workshop/plot_severity_sweep.py
    python docs/workshop/plot_severity_sweep.py --csv output/cohort_comparison.csv
    python docs/workshop/plot_severity_sweep.py --output severity_sweep.png

Falls back gracefully if some QoI columns are missing (e.g. TAWSS=0
because the run was too short to compute a meaningful cycle average).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


QOIS = [
    ("pressure_drop_mean_mmhg", "Pressure drop (mmHg)", "Across the coarctation"),
    ("wss_p99_pa", "99th-percentile WSS (Pa)", "Peak systolic, instantaneous"),
    ("tawss_p99_pa", "99th-percentile TAWSS (Pa)", "Time-averaged over the cycle"),
    ("osi_mean_masked", "Mean OSI (TAWSS > 0.5 Pa)", "Oscillatory shear, masked"),
]

SEVERITY_COL = "param_coarctation_area_reduction"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", type=Path, default=Path("output/cohort_comparison.csv"))
    p.add_argument("--output", "-o", type=Path, default=Path("output/severity_sweep.png"))
    p.add_argument("--show", action="store_true", help="Open an interactive window in addition to saving")
    args = p.parse_args(argv)

    if not args.csv.exists():
        print(f"Cohort CSV not found: {args.csv}", file=sys.stderr)
        print("Run the demo first:  bash docs/workshop/demo.sh", file=sys.stderr)
        return 1

    df = pd.read_csv(args.csv)
    # Restrict to successful cases that have a severity parameter
    df = df[df.get("status").fillna("ok").eq("ok")]
    if SEVERITY_COL not in df.columns:
        print(f"Column {SEVERITY_COL!r} not in CSV. Available param columns:", file=sys.stderr)
        for c in df.columns:
            if c.startswith("param_"):
                print(f"  {c}", file=sys.stderr)
        return 1
    df = df.dropna(subset=[SEVERITY_COL]).sort_values(SEVERITY_COL)
    if df.empty:
        print("No cases with a severity parameter in the CSV.", file=sys.stderr)
        return 1

    print(f"Plotting {len(df)} cases from {args.csv}")

    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    axes = axes.flatten()

    severity_pct = df[SEVERITY_COL] * 100  # display as 0-90 % rather than 0.0-0.9
    for ax, (col, ylabel, subtitle) in zip(axes, QOIS):
        if col not in df.columns or df[col].isna().all() or (df[col] == 0).all():
            ax.text(0.5, 0.5, f"{col}\nnot computed\n(--quick run, too short)",
                    ha="center", va="center", transform=ax.transAxes, color="gray")
            ax.set_title(ylabel + "  (skipped)")
            ax.set_xticks([])
            ax.set_yticks([])
            continue
        y = df[col]
        ax.plot(severity_pct, y, "o-", color="C0", markersize=8, linewidth=2)
        ax.set_xlabel("Coarctation area reduction (%)")
        ax.set_ylabel(ylabel)
        ax.set_title(f"{ylabel}\n{subtitle}", fontsize=10)
        ax.grid(True, alpha=0.3)
        # Annotate each point with the case id
        for x_pt, y_pt, cid in zip(severity_pct, y, df["case_id"]):
            ax.annotate(cid, (x_pt, y_pt), xytext=(4, 4), textcoords="offset points", fontsize=7, color="gray")

    fig.suptitle("Synthetic coarctation severity sweep — workshop demo",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=150)
    print(f"Saved: {args.output}")

    if args.show:
        plt.show()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
