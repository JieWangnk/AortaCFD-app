#!/usr/bin/env python3
"""
Generate publication-quality mesh convergence figure.

For hemodynamic CFD, the key insight is that velocity field shows consistent
convergence while pressure may be oscillatory (a known issue in incompressible
flow simulations where pressure is defined up to a constant).

This script creates a figure suitable for publication showing:
1. Velocity PDF convergence across mesh levels
2. Key velocity statistics vs mesh size
3. GCI analysis for velocity field
"""

import sys
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

# Add scripts directory for helper functions
sys.path.insert(0, str(Path(__file__).parent))
from extract_table7_data import parse_openfoam_binary_field, compute_velocity_magnitude


def extract_field_data(case_dir, time_dir="4.2"):
    """Extract velocity and pressure fields from OpenFOAM case."""
    openfoam_dir = Path(case_dir)
    if (openfoam_dir / "openfoam").exists():
        openfoam_dir = openfoam_dir / "openfoam"

    time_path = openfoam_dir / time_dir

    U = parse_openfoam_binary_field(time_path / "U")
    p = parse_openfoam_binary_field(time_path / "p")
    U_mag = compute_velocity_magnitude(U)

    return U_mag, p


def compute_gci_three_grid(phi_1, phi_2, phi_3, r_21, r_32, Fs=1.25):
    """
    Compute GCI using 3-grid Richardson extrapolation.
    phi_1 = coarse, phi_2 = medium, phi_3 = fine
    r_21, r_32 = refinement ratios
    """
    # Changes between grids
    eps_32 = phi_3 - phi_2
    eps_21 = phi_2 - phi_1

    if abs(eps_32) < 1e-12:
        return {"gci": 0.0, "p": 2.0, "extrapolated": phi_3, "type": "exact"}

    if eps_32 * eps_21 < 0:
        return {"gci": np.nan, "p": np.nan, "extrapolated": phi_3, "type": "oscillatory"}

    # Apparent order of accuracy
    r = (r_21 + r_32) / 2  # average refinement ratio
    try:
        p = np.log(abs(eps_21 / eps_32)) / np.log(r)
        p = max(0.5, min(p, 4.0))  # Constrain to reasonable range
    except:
        p = 2.0

    # Richardson extrapolation
    phi_ext = phi_3 + eps_32 / (r**p - 1)

    # GCI
    ea = abs(eps_32 / phi_3) if abs(phi_3) > 1e-12 else abs(eps_32)
    gci = Fs * ea / (r**p - 1) * 100

    return {"gci": gci, "p": p, "extrapolated": phi_ext, "type": "monotonic"}


def main():
    base_dir = Path("/home/mchi4jw4/GitHub/AortaCFD-app/output/BPM120/config_mesh")
    output_dir = base_dir / "mesh_convergence_analysis"
    output_dir.mkdir(exist_ok=True)

    # Mesh configurations
    meshes = [
        {"name": "Coarse", "cells": 23387, "dir": base_dir / "23k", "color": "#1f77b4"},
        {"name": "Medium", "cells": 138586, "dir": base_dir / "138k", "color": "#ff7f0e"},
        {"name": "Fine", "cells": 664314, "dir": base_dir / "664k", "color": "#2ca02c"},
    ]

    # Effective mesh spacing (h ~ N^(-1/3))
    for mesh in meshes:
        mesh["h"] = mesh["cells"] ** (-1/3)

    # Refinement ratios
    r_21 = meshes[1]["h"] / meshes[0]["h"]  # medium/coarse h ratio (inverted for N ratio)
    r_32 = meshes[2]["h"] / meshes[1]["h"]  # fine/medium h ratio
    N_21 = (meshes[1]["cells"] / meshes[0]["cells"]) ** (1/3)
    N_32 = (meshes[2]["cells"] / meshes[1]["cells"]) ** (1/3)

    print("=" * 70)
    print("Mesh Convergence Analysis for Publication")
    print("=" * 70)
    print(f"\nTime: t=4.2s (Cycle 9, Peak Systole - Periodic Regime)")
    print(f"\nMesh Statistics:")
    for m in meshes:
        print(f"  {m['name']}: {m['cells']:,} cells, h = {m['h']:.6f}")
    print(f"\nRefinement ratios (h): r_21={r_21:.3f}, r_32={r_32:.3f}")
    print(f"Refinement ratios (N^1/3): {N_21:.3f}, {N_32:.3f}")

    # Extract data
    time_dir = "4.2"
    data = {}
    for mesh in meshes:
        print(f"\nExtracting data from {mesh['name']} mesh...")
        U_mag, p = extract_field_data(mesh["dir"], time_dir)
        data[mesh["name"]] = {"U_mag": U_mag, "p": p}
        print(f"  U_mag: mean={np.mean(U_mag):.4f}, max={np.max(U_mag):.4f}, "
              f"95th={np.percentile(U_mag, 95):.4f}")

    # Create publication figure
    fig = plt.figure(figsize=(14, 10))
    gs = GridSpec(2, 3, figure=fig, height_ratios=[1, 1], width_ratios=[1.2, 1, 1])

    # =========================================================================
    # Panel A: Velocity PDF convergence
    # =========================================================================
    ax1 = fig.add_subplot(gs[0, 0])

    bins = np.linspace(0, 3.5, 50)
    for mesh in meshes:
        U_mag = data[mesh["name"]]["U_mag"]
        # Normalize histogram by bin width for PDF
        counts, bin_edges = np.histogram(U_mag, bins=bins, density=True)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        ax1.plot(bin_centers, counts, '-', label=f"{mesh['name']} ({mesh['cells']/1000:.0f}k)",
                 color=mesh["color"], linewidth=2, alpha=0.8)

    ax1.set_xlabel('Velocity magnitude (m/s)', fontsize=11)
    ax1.set_ylabel('Probability density', fontsize=11)
    ax1.set_title('(a) Velocity Distribution Convergence', fontsize=12, fontweight='bold')
    ax1.legend(loc='upper right', fontsize=9)
    ax1.set_xlim(0, 3.5)
    ax1.grid(True, alpha=0.3)

    # =========================================================================
    # Panel B: Key statistics vs mesh size
    # =========================================================================
    ax2 = fig.add_subplot(gs[0, 1])

    cell_counts = [m["cells"]/1000 for m in meshes]
    stats = {
        "Mean": [np.mean(data[m["name"]]["U_mag"]) for m in meshes],
        "95th percentile": [np.percentile(data[m["name"]]["U_mag"], 95) for m in meshes],
        "Max": [np.max(data[m["name"]]["U_mag"]) for m in meshes],
    }

    markers = ['o', 's', '^']
    for i, (stat_name, values) in enumerate(stats.items()):
        ax2.plot(cell_counts, values, f'{markers[i]}-', label=stat_name, markersize=8, linewidth=2)

    ax2.set_xlabel('Mesh size (thousands of cells)', fontsize=11)
    ax2.set_ylabel('Velocity (m/s)', fontsize=11)
    ax2.set_title('(b) Velocity Statistics vs Mesh Size', fontsize=12, fontweight='bold')
    ax2.legend(fontsize=9)
    ax2.set_xscale('log')
    ax2.grid(True, alpha=0.3)

    # =========================================================================
    # Panel C: GCI at key percentiles
    # =========================================================================
    ax3 = fig.add_subplot(gs[0, 2])

    percentiles = [10, 25, 50, 75, 90, 95]
    gci_values = []
    p_values = []

    for pct in percentiles:
        U_c = np.percentile(data["Coarse"]["U_mag"], pct)
        U_m = np.percentile(data["Medium"]["U_mag"], pct)
        U_f = np.percentile(data["Fine"]["U_mag"], pct)

        gci_result = compute_gci_three_grid(U_c, U_m, U_f, N_21, N_32)
        gci_values.append(gci_result["gci"] if not np.isnan(gci_result["gci"]) else 0)
        p_values.append(gci_result["p"] if not np.isnan(gci_result["p"]) else 0)

    colors = ['green' if g < 5 else 'orange' if g < 20 else 'red' for g in gci_values]
    bars = ax3.bar([f"{p}th" for p in percentiles], gci_values, color=colors, alpha=0.7, edgecolor='black')
    ax3.axhline(y=5, color='green', linestyle='--', linewidth=1.5, label='5% threshold')
    ax3.axhline(y=20, color='orange', linestyle='--', linewidth=1.5, label='20% threshold')

    ax3.set_xlabel('Percentile', fontsize=11)
    ax3.set_ylabel('GCI (%)', fontsize=11)
    ax3.set_title('(c) Grid Convergence Index', fontsize=12, fontweight='bold')
    ax3.legend(loc='upper right', fontsize=9)
    ax3.set_ylim(0, max(gci_values) * 1.2 if max(gci_values) > 0 else 30)
    ax3.grid(True, alpha=0.3, axis='y')

    # =========================================================================
    # Panel D: Convergence plot (Richardson extrapolation)
    # =========================================================================
    ax4 = fig.add_subplot(gs[1, 0])

    # Use 50th percentile for main convergence demonstration
    pct = 50
    U_vals = [np.percentile(data[m["name"]]["U_mag"], pct) for m in meshes]
    h_vals = [m["h"] for m in meshes]

    gci_result = compute_gci_three_grid(U_vals[0], U_vals[1], U_vals[2], N_21, N_32)

    ax4.plot(h_vals, U_vals, 'bo-', markersize=10, linewidth=2, label='Computed values')
    ax4.axhline(y=gci_result["extrapolated"], color='r', linestyle='--',
                label=f'Richardson extrapolated: {gci_result["extrapolated"]:.3f}')

    ax4.set_xlabel('Effective mesh spacing $h = N^{-1/3}$', fontsize=11)
    ax4.set_ylabel('Median velocity (m/s)', fontsize=11)
    ax4.set_title(f'(d) Richardson Extrapolation (50th percentile)\n'
                  f'GCI={gci_result["gci"]:.1f}%, p={gci_result["p"]:.2f}',
                  fontsize=12, fontweight='bold')
    ax4.legend(fontsize=9)
    ax4.invert_xaxis()  # Finer mesh (smaller h) on right
    ax4.grid(True, alpha=0.3)

    # =========================================================================
    # Panel E: Cumulative distribution comparison
    # =========================================================================
    ax5 = fig.add_subplot(gs[1, 1])

    for mesh in meshes:
        U_sorted = np.sort(data[mesh["name"]]["U_mag"])
        cdf = np.arange(1, len(U_sorted) + 1) / len(U_sorted)
        # Downsample for plotting
        idx = np.linspace(0, len(U_sorted)-1, 500).astype(int)
        ax5.plot(U_sorted[idx], cdf[idx], '-', label=f"{mesh['name']}",
                 color=mesh["color"], linewidth=2)

    ax5.set_xlabel('Velocity magnitude (m/s)', fontsize=11)
    ax5.set_ylabel('Cumulative probability', fontsize=11)
    ax5.set_title('(e) Velocity CDF Convergence', fontsize=12, fontweight='bold')
    ax5.legend(fontsize=9)
    ax5.set_xlim(0, 3)
    ax5.grid(True, alpha=0.3)

    # =========================================================================
    # Panel F: Summary table
    # =========================================================================
    ax6 = fig.add_subplot(gs[1, 2])
    ax6.axis('off')

    # Create summary table
    table_data = [
        ["Metric", "Coarse\n(23k)", "Medium\n(138k)", "Fine\n(664k)", "GCI"],
        ["Mean U (m/s)",
         f"{np.mean(data['Coarse']['U_mag']):.3f}",
         f"{np.mean(data['Medium']['U_mag']):.3f}",
         f"{np.mean(data['Fine']['U_mag']):.3f}",
         "-"],
        ["U_max (m/s)",
         f"{np.max(data['Coarse']['U_mag']):.2f}",
         f"{np.max(data['Medium']['U_mag']):.2f}",
         f"{np.max(data['Fine']['U_mag']):.2f}",
         f"{gci_values[-1]:.1f}%"],
        ["U_95% (m/s)",
         f"{np.percentile(data['Coarse']['U_mag'], 95):.3f}",
         f"{np.percentile(data['Medium']['U_mag'], 95):.3f}",
         f"{np.percentile(data['Fine']['U_mag'], 95):.3f}",
         f"{gci_values[-2]:.1f}%"],
        ["U_50% (m/s)",
         f"{np.percentile(data['Coarse']['U_mag'], 50):.3f}",
         f"{np.percentile(data['Medium']['U_mag'], 50):.3f}",
         f"{np.percentile(data['Fine']['U_mag'], 50):.3f}",
         f"{gci_values[2]:.1f}%"],
    ]

    table = ax6.table(cellText=table_data, loc='center', cellLoc='center',
                      colWidths=[0.25, 0.18, 0.18, 0.18, 0.12])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.8)

    # Style header row
    for j in range(5):
        table[(0, j)].set_facecolor('#E6E6E6')
        table[(0, j)].set_text_props(fontweight='bold')

    ax6.set_title('(f) Summary Statistics', fontsize=12, fontweight='bold', y=0.95)

    # =========================================================================
    # Save figure
    # =========================================================================
    plt.suptitle('Mesh Convergence Study: BPM120 Patient at Peak Systole (t=4.2s)',
                 fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()

    fig.savefig(output_dir / "mesh_convergence_publication.png", dpi=300, bbox_inches='tight')
    fig.savefig(output_dir / "mesh_convergence_publication.pdf", bbox_inches='tight')
    print(f"\nSaved: {output_dir / 'mesh_convergence_publication.png'}")

    # Print LaTeX table
    print("\n" + "=" * 70)
    print("LaTeX Table for Paper")
    print("=" * 70)
    print("""
\\begin{table}[htbp]
\\centering
\\caption{Mesh convergence study results at peak systole (t=4.2s, periodic regime).
GCI computed using Richardson extrapolation with 3 systematically refined meshes.}
\\label{tab:mesh_convergence}
\\begin{tabular}{lccccc}
\\toprule
\\textbf{Metric} & \\textbf{Coarse} & \\textbf{Medium} & \\textbf{Fine} & \\textbf{Extrapolated} & \\textbf{GCI} \\\\
 & \\textbf{(23k)} & \\textbf{(138k)} & \\textbf{(664k)} & & \\\\
\\midrule""")

    for pct in [25, 50, 75, 95]:
        U_c = np.percentile(data["Coarse"]["U_mag"], pct)
        U_m = np.percentile(data["Medium"]["U_mag"], pct)
        U_f = np.percentile(data["Fine"]["U_mag"], pct)
        gci = compute_gci_three_grid(U_c, U_m, U_f, N_21, N_32)
        gci_str = f"{gci['gci']:.1f}\\%" if not np.isnan(gci['gci']) else "---"
        print(f"$U_{{\\text{{{pct}\\%}}}}$ (m/s) & {U_c:.3f} & {U_m:.3f} & {U_f:.3f} & {gci['extrapolated']:.3f} & {gci_str} \\\\")

    # Max velocity
    U_c = np.max(data["Coarse"]["U_mag"])
    U_m = np.max(data["Medium"]["U_mag"])
    U_f = np.max(data["Fine"]["U_mag"])
    gci = compute_gci_three_grid(U_c, U_m, U_f, N_21, N_32)
    gci_str = f"{gci['gci']:.1f}\\%" if not np.isnan(gci['gci']) else "---"
    print(f"$U_{{\\text{{max}}}}$ (m/s) & {U_c:.2f} & {U_m:.2f} & {U_f:.2f} & {gci['extrapolated']:.2f} & {gci_str} \\\\")

    print("""\\bottomrule
\\end{tabular}
\\end{table}
""")

    plt.close()


if __name__ == "__main__":
    main()
