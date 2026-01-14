#!/usr/bin/env python3
"""
Generate GCI Profile Plots for Supplementary Material

Creates publication-quality velocity profile plots at multiple cross-sections
with discretization error bars computed using the Grid Convergence Index (GCI)
method following Celik et al. (2008).

Reference:
- Celik, I.B. et al. (2008). "Procedure for Estimation and Reporting of
  Uncertainty Due to Discretization in CFD Applications." ASME J. Fluids Eng.

Usage:
    python scripts/generate_gci_profile_figure.py
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.interpolate import interp1d

# Publication-quality matplotlib settings
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 8,
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.linewidth': 0.8,
    'lines.linewidth': 1.5,
    'lines.markersize': 4,
})


def compute_gci_pointwise(phi_coarse, phi_medium, phi_fine, r_21=1.33, r_32=1.35, Fs=1.25):
    """
    Compute point-wise GCI following Celik et al. (2008) procedure.

    Parameters:
    -----------
    phi_coarse, phi_medium, phi_fine : np.array
        QoI values at each point for coarse, medium, fine grids
    r_21, r_32 : float
        Refinement ratios (coarse/medium and medium/fine)
    Fs : float
        Safety factor (1.25 for 3+ grids)

    Returns:
    --------
    dict with:
        - phi_ext: Richardson extrapolated values
        - gci_fine: GCI uncertainty (as absolute value, same units as phi)
        - p: apparent order of accuracy at each point
        - convergence: 'monotonic' or 'oscillatory' at each point
    """
    n_points = len(phi_fine)
    phi_ext = np.zeros(n_points)
    gci_fine = np.zeros(n_points)
    p_values = np.zeros(n_points)
    convergence = []

    r = (r_21 + r_32) / 2  # Average refinement ratio

    for i in range(n_points):
        phi_1 = phi_coarse[i]  # Coarse
        phi_2 = phi_medium[i]  # Medium
        phi_3 = phi_fine[i]    # Fine

        eps_32 = phi_3 - phi_2
        eps_21 = phi_2 - phi_1

        # Check for zero differences
        if abs(eps_32) < 1e-15 or abs(eps_21) < 1e-15:
            phi_ext[i] = phi_3
            gci_fine[i] = 0
            p_values[i] = np.nan
            convergence.append('converged')
            continue

        # Check for oscillatory convergence
        if eps_32 * eps_21 <= 0:
            phi_ext[i] = phi_3
            # For oscillatory, use max difference as uncertainty estimate
            gci_fine[i] = max(abs(eps_32), abs(eps_21))
            p_values[i] = np.nan
            convergence.append('oscillatory')
            continue

        # Compute apparent order (Eq. 6 in Celik 2008)
        p = np.log(abs(eps_21 / eps_32)) / np.log(r)

        # Constrain to reasonable range
        if p < 0.5:
            p = 0.5
        elif p > 5.0:
            p = 5.0

        p_values[i] = p

        # Richardson extrapolation (Eq. 8)
        phi_ext[i] = phi_3 + eps_32 / (r**p - 1)

        # Relative error (Eq. 9)
        e_32 = abs(eps_32 / phi_3) if abs(phi_3) > 1e-15 else abs(eps_32)

        # GCI (Eq. 10) - return as absolute uncertainty
        gci_fine[i] = abs(Fs * e_32 / (r**p - 1) * phi_3)

        convergence.append('monotonic')

    return {
        'phi_ext': phi_ext,
        'gci_fine': gci_fine,
        'p': p_values,
        'convergence': convergence
    }


def interpolate_to_common_grid(arc_coarse, U_coarse, arc_medium, U_medium, arc_fine, U_fine):
    """
    Interpolate all profiles to a common grid (the fine mesh grid).
    """
    # Use fine mesh arc_length as reference
    arc_common = np.array(arc_fine)

    # Interpolate coarse and medium to fine grid
    interp_coarse = interp1d(arc_coarse, U_coarse, kind='linear',
                             bounds_error=False, fill_value='extrapolate')
    interp_medium = interp1d(arc_medium, U_medium, kind='linear',
                             bounds_error=False, fill_value='extrapolate')

    U_coarse_interp = interp_coarse(arc_common)
    U_medium_interp = interp_medium(arc_common)
    U_fine_interp = np.array(U_fine)

    return arc_common, U_coarse_interp, U_medium_interp, U_fine_interp


def create_gci_profile_figure(probe_data, output_dir):
    """
    Create a multi-panel figure showing velocity profiles with GCI error bars.

    Similar to Fig. 3 in Celik et al. (2008).
    """
    # Extract data for each mesh
    mesh_data = {d['mesh']: d['probes'] for d in probe_data}

    # Cross-sections to plot (from ParaView with documented coordinates)
    cross_sections = [
        ('ascending', 'Ascending Aorta'),
        ('arch', 'Aortic Arch'),
        ('descending', 'Descending Aorta'),
    ]

    # Create figure
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.5))

    # Colors
    colors = {
        'Coarse': '#1f77b4',
        'Medium': '#ff7f0e',
        'Fine': '#2ca02c',
        'Extrapolated': '#d62728',
    }

    # Markers
    markers = {
        'Coarse': 's',
        'Medium': '^',
        'Fine': 'o',
    }

    for ax_idx, (probe_name, title) in enumerate(cross_sections):
        ax = axes[ax_idx]

        # Check if probe exists in all meshes
        if not all(probe_name in mesh_data[m] for m in ['Coarse', 'Medium', 'Fine']):
            ax.text(0.5, 0.5, f'No data for\n{probe_name}',
                   ha='center', va='center', transform=ax.transAxes)
            ax.set_title(f'({chr(97+ax_idx)}) {title}')
            continue

        # Get data
        coarse = mesh_data['Coarse'][probe_name]
        medium = mesh_data['Medium'][probe_name]
        fine = mesh_data['Fine'][probe_name]

        # Interpolate to common grid
        arc, U_c, U_m, U_f = interpolate_to_common_grid(
            coarse['arc_length'], coarse['U_magnitude'],
            medium['arc_length'], medium['U_magnitude'],
            fine['arc_length'], fine['U_magnitude']
        )

        # Normalize arc_length to diameter (0 to 1)
        arc_norm = (arc - arc.min()) / (arc.max() - arc.min()) if arc.max() > arc.min() else arc

        # Compute point-wise GCI
        gci_result = compute_gci_pointwise(U_c, U_m, U_f)

        # Plot profiles (subsample for clarity)
        subsample = max(1, len(arc) // 20)
        idx = np.arange(0, len(arc), subsample)

        # Plot coarse mesh
        ax.plot(arc_norm[idx], U_c[idx], marker=markers['Coarse'],
               color=colors['Coarse'], linestyle='--', linewidth=1,
               markersize=5, label='Coarse (0.8M)', alpha=0.7)

        # Plot medium mesh
        ax.plot(arc_norm[idx], U_m[idx], marker=markers['Medium'],
               color=colors['Medium'], linestyle='-.', linewidth=1,
               markersize=5, label='Medium (1.9M)', alpha=0.7)

        # Plot fine mesh with GCI error bars
        ax.errorbar(arc_norm[idx], U_f[idx], yerr=gci_result['gci_fine'][idx],
                   marker=markers['Fine'], color=colors['Fine'], linestyle='-',
                   linewidth=1.5, markersize=6, capsize=3, capthick=1,
                   label='Fine (4.8M) ± GCI', zorder=10)

        # Plot Richardson extrapolated value
        ax.plot(arc_norm, gci_result['phi_ext'], color=colors['Extrapolated'],
               linestyle=':', linewidth=1.5, label='Richardson ext.', alpha=0.8)

        # Labels and formatting
        ax.set_xlabel('Normalized Position (r/D)')
        if ax_idx == 0:
            ax.set_ylabel('Velocity Magnitude (m/s)')
        ax.set_title(f'({chr(97+ax_idx)}) {title}')
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.set_xlim(-0.05, 1.05)

        # Legend only on first panel
        if ax_idx == 0:
            ax.legend(loc='upper right', framealpha=0.95)

        # Add GCI statistics as text
        mean_gci = np.nanmean(gci_result['gci_fine'] / np.maximum(U_f, 1e-6)) * 100
        n_oscillatory = sum(1 for c in gci_result['convergence'] if c == 'oscillatory')

        stats_text = f'Mean GCI: {mean_gci:.1f}%\nOsc. points: {n_oscillatory}/{len(arc)}'
        ax.text(0.97, 0.03, stats_text, transform=ax.transAxes,
               fontsize=7, ha='right', va='bottom',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.tight_layout()

    # Save
    fig.savefig(output_dir / 'gci_profile_uncertainty.png', dpi=300)
    fig.savefig(output_dir / 'gci_profile_uncertainty.pdf')
    print(f"Saved: {output_dir / 'gci_profile_uncertainty.png'}")

    plt.close()

    return fig


def create_detailed_gci_analysis_figure(probe_data, output_dir):
    """
    Create a detailed 2x2 figure showing:
    - Top row: Velocity profiles at two key locations
    - Bottom row: Local GCI (%) and apparent order p along the profile
    """
    mesh_data = {d['mesh']: d['probes'] for d in probe_data}

    fig = plt.figure(figsize=(11, 9))

    # Use ascending aorta cross-section (cleaner parabolic profile for GCI analysis)
    probe_name = 'ascending'

    # Verify this probe has valid data
    if mesh_data['Fine'][probe_name].get('U_mean', 0) < 1e-6:
        probe_name = 'arch'

    coarse = mesh_data['Coarse'][probe_name]
    medium = mesh_data['Medium'][probe_name]
    fine = mesh_data['Fine'][probe_name]

    # Interpolate
    arc, U_c, U_m, U_f = interpolate_to_common_grid(
        coarse['arc_length'], coarse['U_magnitude'],
        medium['arc_length'], medium['U_magnitude'],
        fine['arc_length'], fine['U_magnitude']
    )

    arc_norm = (arc - arc.min()) / (arc.max() - arc.min()) if arc.max() > arc.min() else arc

    # Compute GCI
    gci_result = compute_gci_pointwise(U_c, U_m, U_f)

    # Panel A: Velocity profiles
    ax1 = fig.add_subplot(2, 2, 1)
    subsample = max(1, len(arc) // 15)
    idx = np.arange(0, len(arc), subsample)

    ax1.plot(arc_norm[idx], U_c[idx], 's--', color='#1f77b4', markersize=6,
            linewidth=1, label='Coarse (0.8M cells)')
    ax1.plot(arc_norm[idx], U_m[idx], '^-.', color='#ff7f0e', markersize=6,
            linewidth=1, label='Medium (1.9M cells)')
    ax1.errorbar(arc_norm[idx], U_f[idx], yerr=gci_result['gci_fine'][idx],
                marker='o', color='#2ca02c', linestyle='-', markersize=7,
                capsize=4, capthick=1.5, linewidth=1.5,
                label='Fine (4.8M cells) ± GCI')
    ax1.plot(arc_norm, gci_result['phi_ext'], 'r:', linewidth=2,
            label='Richardson extrapolated', alpha=0.8)

    ax1.set_xlabel('Normalized radial position (r/R)')
    ax1.set_ylabel('Velocity magnitude (m/s)')
    ax1.set_title('(a) Velocity Profile Convergence')
    ax1.legend(loc='best', framealpha=0.95)
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(-0.05, 1.05)

    # Panel B: GCI distribution
    ax2 = fig.add_subplot(2, 2, 2)

    # GCI as percentage
    gci_pct = gci_result['gci_fine'] / np.maximum(np.abs(U_f), 1e-6) * 100
    gci_pct = np.clip(gci_pct, 0, 100)  # Clip extreme values

    ax2.fill_between(arc_norm, 0, gci_pct, alpha=0.3, color='#2ca02c')
    ax2.plot(arc_norm, gci_pct, '-', color='#2ca02c', linewidth=1.5)
    ax2.axhline(y=5, color='orange', linestyle='--', linewidth=1, label='5% threshold')
    ax2.axhline(y=1, color='green', linestyle='--', linewidth=1, label='1% threshold')

    ax2.set_xlabel('Normalized radial position (r/R)')
    ax2.set_ylabel('Local GCI (%)')
    ax2.set_title('(b) Discretization Uncertainty Distribution')
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(-0.05, 1.05)
    ax2.set_ylim(0, min(20, np.percentile(gci_pct, 95) * 1.5))

    # Panel C: Apparent order of accuracy
    ax3 = fig.add_subplot(2, 2, 3)

    # Color by convergence type
    p_plot = gci_result['p'].copy()
    p_plot[np.isnan(p_plot)] = 0  # For visualization

    colors_conv = ['#2ca02c' if c == 'monotonic' else '#d62728' if c == 'oscillatory' else '#7f7f7f'
                   for c in gci_result['convergence']]

    ax3.scatter(arc_norm, p_plot, c=colors_conv, s=20, alpha=0.7)
    ax3.axhline(y=2, color='blue', linestyle='--', linewidth=1, label='Expected p=2 (2nd order)')
    ax3.axhline(y=1, color='gray', linestyle=':', linewidth=1, label='p=1 (1st order)')

    ax3.set_xlabel('Normalized radial position (r/R)')
    ax3.set_ylabel('Apparent order p')
    ax3.set_title('(c) Observed Order of Accuracy')
    ax3.legend(loc='upper right')
    ax3.grid(True, alpha=0.3)
    ax3.set_xlim(-0.05, 1.05)
    ax3.set_ylim(0, 5)

    # Add legend for convergence type
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#2ca02c', label='Monotonic'),
        Patch(facecolor='#d62728', label='Oscillatory'),
        Patch(facecolor='#7f7f7f', label='Converged'),
    ]
    ax3.legend(handles=legend_elements, loc='lower right', title='Convergence')

    # Panel D: Summary statistics
    ax4 = fig.add_subplot(2, 2, 4)
    ax4.axis('off')

    # Compute summary statistics
    n_mono = sum(1 for c in gci_result['convergence'] if c == 'monotonic')
    n_osc = sum(1 for c in gci_result['convergence'] if c == 'oscillatory')
    n_conv = sum(1 for c in gci_result['convergence'] if c == 'converged')
    n_total = len(gci_result['convergence'])

    mean_gci = np.nanmean(gci_pct)
    max_gci = np.nanmax(gci_pct)
    p95_gci = np.nanpercentile(gci_pct, 95)

    valid_p = gci_result['p'][~np.isnan(gci_result['p'])]
    mean_p = np.mean(valid_p) if len(valid_p) > 0 else np.nan

    summary_text = f"""
GCI Profile Analysis Summary
{'='*40}

Convergence Behavior:
  • Monotonic points:    {n_mono:3d} / {n_total} ({100*n_mono/n_total:.1f}%)
  • Oscillatory points:  {n_osc:3d} / {n_total} ({100*n_osc/n_total:.1f}%)
  • Converged points:    {n_conv:3d} / {n_total} ({100*n_conv/n_total:.1f}%)

GCI Statistics:
  • Mean GCI:           {mean_gci:6.2f}%
  • Max GCI:            {max_gci:6.2f}%
  • 95th percentile:    {p95_gci:6.2f}%

Order of Accuracy:
  • Mean observed p:    {mean_p:6.2f}
  • Expected (2nd order): 2.00

{'='*40}
Method: Celik et al. (2008) GCI procedure
Safety factor Fs = 1.25 (three mesh levels)
"""

    ax4.text(0.05, 0.95, summary_text, transform=ax4.transAxes,
            fontsize=9, fontfamily='monospace',
            verticalalignment='top', horizontalalignment='left',
            bbox=dict(boxstyle='round', facecolor='#f0f0f0', alpha=0.8))

    ax4.set_title('(d) Summary Statistics')

    plt.tight_layout()

    # Save
    fig.savefig(output_dir / 'gci_profile_detailed.png', dpi=300)
    fig.savefig(output_dir / 'gci_profile_detailed.pdf')
    print(f"Saved: {output_dir / 'gci_profile_detailed.png'}")

    plt.close()

    return fig


def main():
    # Load profile data (from sample_gci_profiles.py with documented coordinates)
    profile_file = Path(__file__).parent.parent / 'output' / 'BPM120' / 'gci_mesh_study' / 'gci_profile_samples.json'

    if not profile_file.exists():
        print(f"ERROR: Profile samples not found: {profile_file}")
        print("Run: python scripts/sample_gci_profiles.py")
        return 1

    with open(profile_file) as f:
        raw_data = json.load(f)

    # Convert to expected format for existing functions
    probe_data = []
    for mesh_entry in raw_data:
        probes = {}
        for line_id, line_data in mesh_entry['profiles'].items():
            probes[line_id] = {
                'n_points': len(line_data['arc_length']),
                'arc_length': line_data['arc_length'],
                'U_magnitude': line_data['U_magnitude'],
                'U_mean': np.mean(line_data['U_magnitude']),
                'name': line_data['name'],
            }
        probe_data.append({
            'mesh': mesh_entry['mesh'],
            'probes': probes,
        })

    print("="*70)
    print("GCI Profile Figure Generator")
    print("Following Celik et al. (2008) procedure")
    print("="*70)
    print()

    # Output directory
    output_dir = profile_file.parent

    # Create profile figure (supplementary)
    print("Creating velocity profile figure with GCI error bars...")
    create_gci_profile_figure(probe_data, output_dir)

    # Create detailed analysis figure
    print("\nCreating detailed GCI analysis figure...")
    create_detailed_gci_analysis_figure(probe_data, output_dir)

    # Also save to paper figures directory
    paper_fig_dir = Path.home() / 'GitHub' / 'AortaCFDappPaper' / 'figures'
    if paper_fig_dir.exists():
        import shutil
        shutil.copy(output_dir / 'gci_profile_uncertainty.png', paper_fig_dir)
        shutil.copy(output_dir / 'gci_profile_uncertainty.pdf', paper_fig_dir)
        shutil.copy(output_dir / 'gci_profile_detailed.png', paper_fig_dir)
        shutil.copy(output_dir / 'gci_profile_detailed.pdf', paper_fig_dir)
        print(f"\nAlso copied to {paper_fig_dir}")

    # Print LaTeX code
    print("\n" + "="*70)
    print("LaTeX Figure Code for Supplementary Material:")
    print("="*70)
    print(r"""
\begin{figure}[htbp]
  \centering
  \includegraphics[width=\textwidth]{figures/gci_profile_uncertainty.pdf}
  \caption{Velocity profiles at three cross-sectional locations showing
    mesh convergence with discretization uncertainty. Error bars on the
    fine mesh solution represent the Grid Convergence Index (GCI) computed
    following Celik et al.~\cite{celik2008}. Dashed line shows Richardson
    extrapolated values. (a) Ascending aorta near inlet; (b) Aortic arch;
    (c) Descending aorta.}
  \label{fig:gci_profiles}
\end{figure}

\begin{figure}[htbp]
  \centering
  \includegraphics[width=\textwidth]{figures/gci_profile_detailed.pdf}
  \caption{Detailed GCI analysis for the center cross-section. (a) Velocity
    profiles from three mesh levels with Richardson extrapolation and GCI
    error bars on fine mesh. (b) Local discretization uncertainty (GCI\%)
    distribution along the profile. (c) Observed order of accuracy $p$ at
    each point, colored by convergence behavior. (d) Summary statistics
    showing predominantly monotonic convergence with mean GCI well below
    the 5\% threshold.}
  \label{fig:gci_detailed}
\end{figure}
""")

    print("="*70)
    print("Done!")

    return 0


if __name__ == "__main__":
    exit(main())
