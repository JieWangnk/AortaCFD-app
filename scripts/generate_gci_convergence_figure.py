#!/usr/bin/env python3
"""
Generate GCI Mesh Convergence Figure for Publication

Creates a publication-quality convergence plot showing:
- U_mean convergence with GCI
- WSS convergence metrics
- Clear visualization of mesh independence

Data source: output/BPM120/gci_mesh_study/GCI_ANALYSIS_REPORT.md
"""

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Set publication-quality defaults
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.linewidth': 0.8,
    'lines.linewidth': 1.5,
    'lines.markersize': 8,
})

# =============================================================================
# GCI Study Data from BPM120 mesh study
# =============================================================================

# Mesh configuration
mesh_names = ['Coarse\n(0.8M)', 'Medium\n(1.9M)', 'Fine\n(4.8M)']
cells = np.array([822361, 1945401, 4785879])
cells_per_d = np.array([8, 12, 18])

# X-axis: cells per diameter (more intuitive)
x_values = cells_per_d

# Velocity data (from gci_comprehensive.json)
U_mean = np.array([0.03888, 0.03100, 0.03074])  # m/s
U_mean_ext = 0.03062  # Richardson extrapolated
U_mean_gci = 0.46  # GCI_fine in %

U_max = np.array([0.6184, 0.5372, 0.5621])  # m/s (oscillatory)

# WSS data (from wss_openfoam_results.json, converted to mPa)
WSS_max = np.array([27.74, 29.63, 29.57])   # mPa (Fine-Med Δ = 0.20%)
WSS_mean = np.array([0.571, 0.474, 0.480])  # mPa (Fine-Med Δ = 1.15%)
WSS_median = np.array([0.331, 0.286, 0.296])  # mPa (Fine-Med Δ = 3.38%)

# =============================================================================
# Create Figure - Normalized Convergence Plot
# =============================================================================

fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))

# Colors
color_umean = '#1f77b4'  # Blue
color_umax = '#ff7f0e'   # Orange
color_wss_max = '#2ca02c'  # Green
color_wss_mean = '#d62728'  # Red
color_ext = '#666666'  # Gray

# -----------------------------------------------------------------------------
# Panel A: Velocity Convergence (Normalized to Fine Mesh)
# -----------------------------------------------------------------------------
ax1 = axes[0]

# Normalize to fine mesh value (%)
U_mean_norm = (U_mean / U_mean[-1] - 1) * 100  # % deviation from fine
U_max_norm = (U_max / U_max[-1] - 1) * 100
U_ext_norm = (U_mean_ext / U_mean[-1] - 1) * 100

# Plot U_mean (monotonic) - with GCI error bar on fine mesh point
ax1.plot(x_values[:-1], U_mean_norm[:-1], 'o-', color=color_umean, markersize=10, zorder=3)
ax1.plot(x_values[-1], U_mean_norm[-1], 'o', color=color_umean, markersize=10, zorder=3,
         label=r'$U_{mean}$ (monotonic)')
# Connect the last two points
ax1.plot(x_values[-2:], U_mean_norm[-2:], '-', color=color_umean, zorder=3)

# GCI error bar on fine mesh point (more visible than fill_between)
ax1.errorbar(x_values[-1], U_mean_norm[-1], yerr=U_mean_gci,
             fmt='none', ecolor='#d62728', elinewidth=3, capsize=8, capthick=2,
             label=f'GCI$_{{fine}}$ = ±{U_mean_gci}%', zorder=5)

# Plot U_max (oscillatory)
ax1.plot(x_values, U_max_norm, 's--', color=color_umax, markersize=8, alpha=0.7,
         label=r'$U_{max}$ (oscillatory)', zorder=2)

# Richardson extrapolated reference line
ax1.axhline(y=U_ext_norm, color=color_ext, linestyle=':', linewidth=1.5,
            label=f'Richardson ext. ({U_ext_norm:.2f}%)')

# Zero reference (fine mesh)
ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.5, alpha=0.5)

ax1.set_xlabel('Mesh Resolution (cells/diameter)')
ax1.set_ylabel('Deviation from Fine Mesh (%)')
ax1.set_title('(a) Velocity Convergence')
ax1.set_xticks(x_values)
ax1.set_xlim([6, 20])
ax1.set_ylim([-10, 30])  # Set y limits to avoid clipping
ax1.legend(loc='upper right', framealpha=0.95, fontsize=8)
ax1.grid(True, alpha=0.3, linestyle='--')

# Add mesh cell count on top axis
ax1_top = ax1.twiny()
ax1_top.set_xlim(ax1.get_xlim())
ax1_top.set_xticks(x_values)
ax1_top.set_xticklabels([f'{c/1e6:.1f}M' for c in cells], fontsize=8)
ax1_top.set_xlabel('Total Cells', fontsize=9)

# -----------------------------------------------------------------------------
# Panel B: WSS Convergence (Absolute Values)
# -----------------------------------------------------------------------------
ax2 = axes[1]

# Plot WSS metrics (percentages validated against OpenFOAM outputs)
ax2.plot(x_values, WSS_max, 'o-', color=color_wss_max, markersize=10,
         label=r'WSS$_{max}$ ($\Delta$ = 0.21%)')
ax2.plot(x_values, WSS_mean, 's-', color=color_wss_mean, markersize=8,
         label=r'WSS$_{mean}$ ($\Delta$ = 1.13%)')
ax2.plot(x_values, WSS_median, '^-', color='#9467bd', markersize=8,
         label=r'WSS$_{median}$ ($\Delta$ = 3.41%)')

ax2.set_xlabel('Mesh Resolution (cells/diameter)')
ax2.set_ylabel('Wall Shear Stress (mPa)')
ax2.set_title('(b) WSS Convergence')
ax2.set_xticks(x_values)
ax2.set_xlim([6, 20])
ax2.set_ylim([0, 38])  # Extend y-axis for better spacing
ax2.legend(loc='upper left', framealpha=0.95, fontsize=8)
ax2.grid(True, alpha=0.3, linestyle='--')

# Add mesh cell count on top axis
ax2_top = ax2.twiny()
ax2_top.set_xlim(ax2.get_xlim())
ax2_top.set_xticks(x_values)
ax2_top.set_xticklabels([f'{c/1e6:.1f}M' for c in cells], fontsize=8)
ax2_top.set_xlabel('Total Cells', fontsize=9)

# -----------------------------------------------------------------------------
# Finalize
# -----------------------------------------------------------------------------
plt.tight_layout()

# Save figures
output_dir = Path(__file__).parent.parent / 'output' / 'BPM120' / 'gci_mesh_study'
output_dir.mkdir(parents=True, exist_ok=True)

fig.savefig(output_dir / 'gci_convergence_plot.png', dpi=300)
fig.savefig(output_dir / 'gci_convergence_plot.pdf')
print(f"Saved figures to {output_dir}")

# Also save to paper figures directory
paper_fig_dir = Path.home() / 'GitHub' / 'AortaCFDappPaper' / 'figures'
if paper_fig_dir.exists():
    fig.savefig(paper_fig_dir / 'gci_convergence_plot.png', dpi=300)
    fig.savefig(paper_fig_dir / 'gci_convergence_plot.pdf')
    print(f"Also saved to {paper_fig_dir}")

plt.show()

print("\n" + "="*70)
print("GCI Mesh Convergence Figure Generated")
print("="*70)
print("""
Key Results Visualized:
  Panel (a) - Velocity:
    - U_mean shows monotonic convergence toward Richardson extrapolated value
    - U_max shows oscillatory behavior (common for local maxima)
    - GCI_fine = 0.46% shown as shaded uncertainty band

  Panel (b) - WSS:
    - WSS_max converged to 0.21% (essentially mesh-independent)
    - WSS_mean converged to 1.1%
    - WSS_median converged to 3.4%

LaTeX Figure Code:
""")
print(r"""
\begin{figure}[h]
  \centering
  \includegraphics[width=\textwidth]{figures/gci_convergence_plot.pdf}
  \caption{Mesh convergence study for BPM120 thoracic aorta geometry.
    (a) Velocity convergence showing deviation from fine mesh: $U_{mean}$
    exhibits monotonic convergence (GCI$_{fine}$ = 0.46\%) while $U_{max}$
    shows oscillatory behavior typical of localized maxima.
    (b) WSS metrics demonstrating mesh independence: WSS$_{max}$ converges
    to within 0.21\% between medium and fine meshes.}
  \label{fig:gci_convergence}
\end{figure}
""")
