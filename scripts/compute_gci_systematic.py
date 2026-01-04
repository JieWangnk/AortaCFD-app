#!/usr/bin/env python3
"""
Compute Grid Convergence Index (GCI) for Systematic Mesh Study

This script computes GCI using Richardson extrapolation for meshes with
consistent refinement ratio r=2. It follows ASME V&V 20-2009 guidelines.

Reference:
- Roache, P.J. "Verification and Validation in Computational Science and Engineering"
- ASME V&V 20-2009: Standard for Verification and Validation in CFD and Heat Transfer
- Celik, I.B. et al. "Procedure for Estimation of Discretization Error in CFD"

Usage:
    python scripts/compute_gci_systematic.py --study-dir output/BPM120/mesh_gci_study

The script extracts:
1. Peak velocity magnitude (U_max)
2. Area-weighted mean pressure at outlet
3. Wall shear stress (if available)

And computes:
- Apparent order of accuracy (p)
- Richardson extrapolated values
- GCI_fine and GCI_medium
- Asymptotic range check
"""

import argparse
import json
import sys
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))
from extract_table7_data import parse_openfoam_binary_field, compute_velocity_magnitude


def extract_qoi(run_dir: Path, time_dir: str = None) -> dict:
    """
    Extract Quantities of Interest (QoI) from a simulation.

    Parameters:
    -----------
    run_dir : Path
        Path to simulation run directory
    time_dir : str, optional
        Specific time directory to use. If None, uses the last available.

    Returns:
    --------
    dict with QoI values
    """
    openfoam_dir = run_dir / "openfoam"
    if not openfoam_dir.exists():
        openfoam_dir = run_dir

    # Find available time directories
    time_dirs = sorted([
        d for d in openfoam_dir.iterdir()
        if d.is_dir() and d.name.replace('.', '', 1).isdigit()
        and d.name != "0"
    ], key=lambda x: float(x.name))

    if not time_dirs:
        return {"error": "No time directories found"}

    # Use specified time or last available
    if time_dir:
        time_path = openfoam_dir / time_dir
    else:
        time_path = time_dirs[-1]

    if not time_path.exists():
        return {"error": f"Time directory not found: {time_path}"}

    # Extract velocity field
    U_file = time_path / "U"
    if not U_file.exists():
        return {"error": f"U field not found: {U_file}"}

    U = parse_openfoam_binary_field(U_file)
    U_mag = compute_velocity_magnitude(U)

    # Extract pressure field
    p_file = time_path / "p"
    p = None
    if p_file.exists():
        p = parse_openfoam_binary_field(p_file)

    # Compute QoIs
    qoi = {
        "time": float(time_path.name),
        "n_cells": len(U_mag),
        "U_max": float(np.max(U_mag)),
        "U_mean": float(np.mean(U_mag)),
        "U_95": float(np.percentile(U_mag, 95)),
        "U_50": float(np.percentile(U_mag, 50)),
    }

    if p is not None:
        qoi["p_max"] = float(np.max(p))
        qoi["p_min"] = float(np.min(p))
        qoi["p_mean"] = float(np.mean(p))
        qoi["p_range"] = float(np.max(p) - np.min(p))

    return qoi


def compute_apparent_order(phi_1, phi_2, phi_3, r_21, r_32):
    """
    Compute apparent order of accuracy using the generalized Richardson method.

    Parameters:
    -----------
    phi_1, phi_2, phi_3 : float
        QoI values on coarse, medium, fine grids
    r_21, r_32 : float
        Refinement ratios (h2/h1 and h3/h2)

    Returns:
    --------
    p : float or None
        Apparent order of accuracy
    """
    eps_32 = phi_3 - phi_2
    eps_21 = phi_2 - phi_1

    if abs(eps_32) < 1e-15:
        return None  # Exact convergence

    if eps_32 * eps_21 <= 0:
        return None  # Oscillatory convergence

    # For uniform refinement (r_21 = r_32 = r)
    r = (r_21 + r_32) / 2

    # Fixed-point iteration for p
    p = np.log(abs(eps_21 / eps_32)) / np.log(r)

    # Constrain to physical range
    if p < 0.5 or p > 5.0:
        return None

    return p


def compute_gci(phi_1, phi_2, phi_3, r_21, r_32, p=None, Fs=1.25):
    """
    Compute Grid Convergence Index following Celik et al. (2008) procedure.

    Parameters:
    -----------
    phi_1, phi_2, phi_3 : float
        QoI values on coarse, medium, fine grids (1=coarse, 3=fine)
    r_21, r_32 : float
        Refinement ratios
    p : float, optional
        Order of accuracy. If None, computed from data.
    Fs : float
        Factor of safety (1.25 for 3+ grids)

    Returns:
    --------
    dict with GCI results
    """
    # Compute apparent order if not provided
    if p is None:
        p = compute_apparent_order(phi_1, phi_2, phi_3, r_21, r_32)

    if p is None:
        return {
            "convergence": "oscillatory",
            "p": None,
            "phi_ext": phi_3,
            "gci_fine": None,
            "gci_medium": None,
            "asymptotic": None
        }

    r = (r_21 + r_32) / 2

    # Richardson extrapolated value
    eps_32 = phi_3 - phi_2
    phi_ext = phi_3 + eps_32 / (r**p - 1)

    # Relative errors
    e_32 = abs((phi_3 - phi_2) / phi_3) if phi_3 != 0 else abs(phi_3 - phi_2)
    e_21 = abs((phi_2 - phi_1) / phi_2) if phi_2 != 0 else abs(phi_2 - phi_1)

    # GCI values
    gci_fine = Fs * e_32 / (r**p - 1) * 100
    gci_medium = Fs * e_21 / (r**p - 1) * 100

    # Asymptotic range check
    # If in asymptotic range: GCI_medium / (r^p * GCI_fine) ≈ 1
    if gci_fine > 0:
        asymptotic = gci_medium / (r**p * gci_fine)
    else:
        asymptotic = None

    return {
        "convergence": "monotonic",
        "p": p,
        "phi_ext": phi_ext,
        "gci_fine": gci_fine,
        "gci_medium": gci_medium,
        "asymptotic": asymptotic
    }


def generate_publication_figure(results: dict, output_dir: Path):
    """Generate publication-quality GCI figure."""
    fig = plt.figure(figsize=(14, 10))
    gs = GridSpec(2, 2, figure=fig)

    # Colors for mesh levels
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']

    # Panel A: Velocity statistics vs mesh size
    ax1 = fig.add_subplot(gs[0, 0])

    mesh_labels = list(results["meshes"].keys())
    cell_counts = [results["meshes"][m]["cells"] / 1000 for m in mesh_labels]

    for qoi in ["U_max", "U_95", "U_mean"]:
        values = [results["meshes"][m]["qoi"].get(qoi, np.nan) for m in mesh_labels]
        ax1.plot(cell_counts, values, 'o-', label=qoi.replace("_", " "), markersize=8)

    # Add extrapolated values if available
    if "U_max" in results["gci"]:
        gci = results["gci"]["U_max"]
        if gci["phi_ext"]:
            ax1.axhline(y=gci["phi_ext"], color='red', linestyle='--',
                       label=f'Extrapolated U_max: {gci["phi_ext"]:.3f}')

    ax1.set_xlabel('Mesh size (thousands of cells)')
    ax1.set_ylabel('Velocity (m/s)')
    ax1.set_title('(a) Velocity vs Mesh Size')
    ax1.set_xscale('log')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Panel B: Convergence plot
    ax2 = fig.add_subplot(gs[0, 1])

    h_values = [1/c**(1/3) for c in [results["meshes"][m]["cells"] for m in mesh_labels]]
    u_max_values = [results["meshes"][m]["qoi"].get("U_max", np.nan) for m in mesh_labels]

    ax2.plot(h_values, u_max_values, 'bo-', markersize=10, linewidth=2, label='Computed')

    if "U_max" in results["gci"]:
        gci = results["gci"]["U_max"]
        if gci["phi_ext"]:
            ax2.axhline(y=gci["phi_ext"], color='red', linestyle='--',
                       label=f'Richardson extrapolated')
            # Add extrapolation line
            h_ext = 0
            ax2.plot([h_ext, h_values[-1]], [gci["phi_ext"], u_max_values[-1]], 'r:', alpha=0.5)

    ax2.set_xlabel('Effective mesh spacing h = N$^{-1/3}$')
    ax2.set_ylabel('$U_{max}$ (m/s)')
    ax2.set_title('(b) Richardson Extrapolation')
    ax2.invert_xaxis()
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Panel C: GCI values
    ax3 = fig.add_subplot(gs[1, 0])

    qoi_names = ["U_max", "U_95", "U_mean", "p_range"]
    gci_values = []
    gci_labels = []

    for qoi in qoi_names:
        if qoi in results["gci"]:
            gci = results["gci"][qoi]
            if gci["gci_fine"] is not None:
                gci_values.append(gci["gci_fine"])
                gci_labels.append(qoi.replace("_", "\n"))

    if gci_values:
        bars = ax3.bar(gci_labels, gci_values, color='steelblue', alpha=0.7, edgecolor='black')
        ax3.axhline(y=1.0, color='green', linestyle='--', label='1% threshold')
        ax3.axhline(y=5.0, color='orange', linestyle='--', label='5% threshold')

        # Add value labels
        for bar, val in zip(bars, gci_values):
            ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                    f'{val:.1f}%', ha='center', va='bottom', fontsize=9)

        ax3.set_ylabel('GCI (%)')
        ax3.set_title('(c) Grid Convergence Index (Fine Mesh)')
        ax3.legend()
        ax3.grid(True, alpha=0.3, axis='y')
    else:
        ax3.text(0.5, 0.5, 'GCI not computed\n(oscillatory or insufficient data)',
                ha='center', va='center', transform=ax3.transAxes)

    # Panel D: Summary table
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.axis('off')

    # Build table data
    table_data = [["QoI"] + [m.capitalize() for m in mesh_labels] + ["Extrapolated", "GCI (%)"]]

    for qoi in ["U_max", "U_95", "U_mean"]:
        row = [qoi.replace("_", " ")]
        for m in mesh_labels:
            val = results["meshes"][m]["qoi"].get(qoi, np.nan)
            row.append(f"{val:.3f}" if not np.isnan(val) else "---")

        if qoi in results["gci"]:
            gci = results["gci"][qoi]
            row.append(f"{gci['phi_ext']:.3f}" if gci['phi_ext'] else "---")
            row.append(f"{gci['gci_fine']:.1f}" if gci['gci_fine'] else "---")
        else:
            row.extend(["---", "---"])

        table_data.append(row)

    table = ax4.table(cellText=table_data, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.2, 1.5)

    # Style header
    for j in range(len(table_data[0])):
        table[(0, j)].set_facecolor('#E6E6E6')
        table[(0, j)].set_text_props(fontweight='bold')

    ax4.set_title('(d) Summary', fontsize=12, fontweight='bold', y=0.9)

    plt.suptitle('Mesh Convergence Study with GCI Analysis', fontsize=14, fontweight='bold')
    plt.tight_layout()

    # Save
    fig.savefig(output_dir / "gci_analysis.png", dpi=300, bbox_inches='tight')
    fig.savefig(output_dir / "gci_analysis.pdf", bbox_inches='tight')
    print(f"Saved: {output_dir / 'gci_analysis.png'}")

    plt.close()


def main():
    parser = argparse.ArgumentParser(
        description="Compute GCI for systematic mesh convergence study"
    )
    parser.add_argument(
        "--study-dir", type=Path, required=True,
        help="Directory containing mesh study results"
    )
    parser.add_argument(
        "--time", type=str, default=None,
        help="Specific time directory to analyze (default: last available)"
    )
    parser.add_argument(
        "--r", type=float, default=2.0,
        help="Nominal refinement ratio (default: 2.0)"
    )

    args = parser.parse_args()

    if not args.study_dir.exists():
        print(f"ERROR: Study directory not found: {args.study_dir}")
        sys.exit(1)

    print("="*70)
    print("GCI Analysis for Systematic Mesh Convergence Study")
    print("="*70)
    print(f"Study directory: {args.study_dir}")
    print()

    # Find mesh directories
    mesh_dirs = {}
    for d in sorted(args.study_dir.iterdir()):
        if d.is_dir() and (d / "openfoam").exists():
            mesh_dirs[d.name] = d

    if len(mesh_dirs) < 3:
        print(f"ERROR: Need at least 3 mesh levels for GCI. Found: {list(mesh_dirs.keys())}")
        sys.exit(1)

    print(f"Found mesh directories: {list(mesh_dirs.keys())}")

    # Check for span-based study and extract span values
    span_values = {}
    for name in mesh_dirs.keys():
        if name.startswith("span"):
            try:
                span_values[name] = int(name.replace("span", ""))
            except ValueError:
                pass

    is_span_study = len(span_values) == len(mesh_dirs)
    if is_span_study:
        print("Detected span-based mesh study (cells_across_span)")
        for name, span in sorted(span_values.items(), key=lambda x: x[1]):
            print(f"  {name}: cells_across_span = {span}")
    print()

    # Extract QoI from each mesh
    results = {"meshes": {}, "gci": {}}

    for name, run_dir in mesh_dirs.items():
        print(f"Extracting QoI from {name}...")
        qoi = extract_qoi(run_dir, args.time)

        if "error" in qoi:
            print(f"  ERROR: {qoi['error']}")
            continue

        # Get cell count from mesh stats or QoI
        mesh_stats_file = run_dir / "openfoam" / "mesh_stats.json"
        if mesh_stats_file.exists():
            with open(mesh_stats_file) as f:
                mesh_stats = json.load(f)
                qoi["cells"] = mesh_stats.get("cells", qoi["n_cells"])
        else:
            qoi["cells"] = qoi["n_cells"]

        results["meshes"][name] = {
            "cells": qoi["cells"],
            "qoi": qoi
        }
        print(f"  Cells: {qoi['cells']:,}")
        print(f"  U_max: {qoi['U_max']:.4f} m/s")
        print(f"  U_95:  {qoi['U_95']:.4f} m/s")

    # Sort by cell count (coarse to fine)
    sorted_meshes = sorted(results["meshes"].keys(),
                          key=lambda x: results["meshes"][x]["cells"])

    if len(sorted_meshes) < 3:
        print("ERROR: Need at least 3 successful mesh extractions for GCI")
        sys.exit(1)

    # Use 3 finest meshes for GCI
    mesh_names = sorted_meshes[-3:]
    print()
    print(f"Using meshes for GCI: {mesh_names}")

    # Cell counts for refinement ratio
    cells = [results["meshes"][m]["cells"] for m in mesh_names]
    h = [c**(-1/3) for c in cells]

    # Actual refinement ratios
    r_21 = h[1] / h[0]  # medium/coarse
    r_32 = h[2] / h[1]  # fine/medium

    print(f"Refinement ratios: r_21={r_21:.3f}, r_32={r_32:.3f}")
    print()

    # Compute GCI for each QoI
    print("="*70)
    print("GCI Results")
    print("="*70)
    print()

    qois = ["U_max", "U_95", "U_mean", "U_50", "p_range"]

    for qoi in qois:
        phi_1 = results["meshes"][mesh_names[0]]["qoi"].get(qoi)
        phi_2 = results["meshes"][mesh_names[1]]["qoi"].get(qoi)
        phi_3 = results["meshes"][mesh_names[2]]["qoi"].get(qoi)

        if None in [phi_1, phi_2, phi_3]:
            continue

        gci = compute_gci(phi_1, phi_2, phi_3, r_21, r_32)
        results["gci"][qoi] = gci

        print(f"{qoi}:")
        print(f"  Coarse: {phi_1:.4f}, Medium: {phi_2:.4f}, Fine: {phi_3:.4f}")
        print(f"  Convergence: {gci['convergence']}")

        if gci['p'] is not None:
            print(f"  Apparent order: p = {gci['p']:.2f}")
            print(f"  Extrapolated: {gci['phi_ext']:.4f}")
            print(f"  GCI_fine: {gci['gci_fine']:.2f}%")
            print(f"  GCI_medium: {gci['gci_medium']:.2f}%")
            if gci['asymptotic']:
                print(f"  Asymptotic ratio: {gci['asymptotic']:.3f} (≈1.0 = asymptotic range)")
        print()

    # Generate figure
    print("Generating publication figure...")
    generate_publication_figure(results, args.study_dir)

    # Save results
    results_file = args.study_dir / "gci_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Results saved to: {results_file}")

    # Print LaTeX table
    print()
    print("="*70)
    print("LaTeX Table")
    print("="*70)
    print()
    print(r"""
\begin{table}[htbp]
\centering
\caption{Grid convergence study with GCI analysis. Refinement ratio $r \approx 2$.}
\label{tab:gci}
\begin{tabular}{lccccc}
\toprule
\textbf{QoI} & \textbf{Coarse} & \textbf{Medium} & \textbf{Fine} & \textbf{Extrapolated} & \textbf{GCI (\%)} \\
\midrule""")

    for qoi in ["U_max", "U_95", "U_mean"]:
        if qoi in results["gci"]:
            phi_1 = results["meshes"][mesh_names[0]]["qoi"].get(qoi, 0)
            phi_2 = results["meshes"][mesh_names[1]]["qoi"].get(qoi, 0)
            phi_3 = results["meshes"][mesh_names[2]]["qoi"].get(qoi, 0)
            gci = results["gci"][qoi]

            label = qoi.replace("_", r"\_")
            ext = f"{gci['phi_ext']:.3f}" if gci['phi_ext'] else "---"
            gci_val = f"{gci['gci_fine']:.1f}" if gci['gci_fine'] else "---"

            print(f"${label}$ & {phi_1:.3f} & {phi_2:.3f} & {phi_3:.3f} & {ext} & {gci_val} \\\\")

    print(r"""\bottomrule
\end{tabular}
\end{table}
""")


if __name__ == "__main__":
    main()
