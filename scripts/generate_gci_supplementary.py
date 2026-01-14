#!/usr/bin/env python3
"""
Generate Comprehensive GCI Supplementary Figure

Creates a publication-quality figure comparing:
- Local velocity profile GCI at three cross-sections
- Scalar QoI GCI for comparison
- Interpretation of why scalar QoIs are preferred

Following Celik et al. (2008) procedure.
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.interpolate import interp1d

# Publication-quality settings
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 9,
    'axes.labelsize': 10,
    'axes.titlesize': 11,
    'xtick.labelsize': 8,
    'ytick.labelsize': 8,
    'legend.fontsize': 7,
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
})


def compute_gci_pointwise(phi_coarse, phi_medium, phi_fine, r=1.34, Fs=1.25):
    """Compute point-wise GCI following Celik et al. (2008)."""
    n_points = len(phi_fine)
    gci_fine = np.zeros(n_points)
    p_values = np.zeros(n_points)
    convergence = []

    for i in range(n_points):
        phi_1, phi_2, phi_3 = phi_coarse[i], phi_medium[i], phi_fine[i]
        eps_32 = phi_3 - phi_2
        eps_21 = phi_2 - phi_1

        if abs(eps_32) < 1e-15 or abs(eps_21) < 1e-15:
            gci_fine[i] = 0
            p_values[i] = np.nan
            convergence.append('converged')
            continue

        if eps_32 * eps_21 <= 0:
            gci_fine[i] = max(abs(eps_32), abs(eps_21))
            p_values[i] = np.nan
            convergence.append('oscillatory')
            continue

        p = np.log(abs(eps_21 / eps_32)) / np.log(r)
        p = np.clip(p, 0.5, 5.0)
        p_values[i] = p

        e_32 = abs(eps_32 / phi_3) if abs(phi_3) > 1e-15 else abs(eps_32)
        gci_fine[i] = abs(Fs * e_32 / (r**p - 1) * phi_3)
        convergence.append('monotonic')

    return gci_fine, p_values, convergence


def interpolate_profiles(coarse, medium, fine):
    """Interpolate all profiles to common grid."""
    arc = np.array(fine['arc_length'])

    interp_c = interp1d(coarse['arc_length'], coarse['U_magnitude'],
                        kind='linear', bounds_error=False, fill_value='extrapolate')
    interp_m = interp1d(medium['arc_length'], medium['U_magnitude'],
                        kind='linear', bounds_error=False, fill_value='extrapolate')

    return arc, interp_c(arc), interp_m(arc), np.array(fine['U_magnitude'])


def create_comprehensive_supplementary(profile_data, output_dir):
    """Create GCI supplementary figure - simple style like Celik et al. (2008) Fig. 3."""

    mesh_data = {d['mesh']: d['probes'] for d in profile_data}

    # Cross-sections with documented coordinates
    cross_sections = [
        ('ascending', 'Ascending Aorta'),
        ('arch', 'Aortic Arch'),
        ('descending', 'Descending Aorta'),
    ]

    # Simple figure: just 1 row of 3 panels (like Celik Fig. 3)
    fig, axes = plt.subplots(1, 3, figsize=(11, 4))

    # Simple loop - just velocity profiles with GCI error bars
    all_stats = []

    for col, (line_id, title) in enumerate(cross_sections):
        ax = axes[col]

        coarse = mesh_data['Coarse'][line_id]
        medium = mesh_data['Medium'][line_id]
        fine = mesh_data['Fine'][line_id]

        arc, U_c, U_m, U_f = interpolate_profiles(coarse, medium, fine)
        arc_norm = (arc - arc.min()) / (arc.max() - arc.min())

        gci, p_vals, conv = compute_gci_pointwise(U_c, U_m, U_f)

        # Collect stats for printing
        gci_pct = np.clip(gci / np.maximum(np.abs(U_f), 1e-6) * 100, 0, 200)
        all_stats.append({
            'name': title,
            'mean_gci': np.nanmean(gci_pct),
        })

        # Plot: Coarse, Medium, and Fine with GCI error bars
        ax.plot(arc_norm, U_c, 's-', color='#1f77b4', markersize=4, linewidth=1,
                label='Coarse (0.8M)', alpha=0.7)
        ax.plot(arc_norm, U_m, '^-', color='#ff7f0e', markersize=4, linewidth=1,
                label='Medium (1.9M)', alpha=0.7)
        ax.errorbar(arc_norm, U_f, yerr=gci, fmt='o-', color='#2ca02c', markersize=5,
                    linewidth=1.2, capsize=2, capthick=1, label='Fine (4.8M) ± GCI')

        ax.set_xlabel('Normalized Position (r/R)')
        if col == 0:
            ax.set_ylabel('Velocity Magnitude (m/s)')
        ax.set_title(f'({chr(97+col)}) {title}', fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.set_xlim(-0.02, 1.02)

        if col == 2:  # Legend on last panel
            ax.legend(loc='upper right', fontsize=8)

    plt.tight_layout()

    # Save
    fig.savefig(output_dir / 'gci_supplementary_profiles.png', dpi=300)
    fig.savefig(output_dir / 'gci_supplementary_profiles.pdf')
    print(f"Saved: {output_dir / 'gci_supplementary_profiles.png'}")

    plt.close()

    # Print LaTeX
    print("\n" + "="*70)
    print("LaTeX for Supplementary Material:")
    print("="*70)
    print(r"""
\begin{figure}[htbp]
  \centering
  \includegraphics[width=\textwidth]{figures/gci_supplementary_profiles.pdf}
  \caption{Velocity profiles at three cross-sections with Grid Convergence Index
    (GCI) uncertainty bands following Celik et al.~\cite{celik2008}. Error bars
    on the fine mesh (4.8M cells) represent local discretization uncertainty.
    The large local GCI values (typically 20--100\%) contrast with scalar QoI GCI
    ($<$1.5\%), demonstrating why integral quantities provide more robust
    convergence estimates for complex 3D geometries.}
  \label{fig:gci_supplementary}
\end{figure}
""")

    return all_stats


def main():
    profile_file = Path(__file__).parent.parent / 'output' / 'BPM120' / 'gci_mesh_study' / 'gci_profile_samples.json'

    if not profile_file.exists():
        print(f"ERROR: {profile_file} not found")
        print("Run: python scripts/sample_gci_profiles.py")
        return 1

    with open(profile_file) as f:
        raw_data = json.load(f)

    # Convert format
    profile_data = []
    for entry in raw_data:
        probes = {}
        for line_id, line_data in entry['profiles'].items():
            probes[line_id] = {
                'arc_length': line_data['arc_length'],
                'U_magnitude': line_data['U_magnitude'],
            }
        profile_data.append({'mesh': entry['mesh'], 'probes': probes})

    print("="*70)
    print("Generating Comprehensive GCI Supplementary Figure")
    print("="*70)

    output_dir = profile_file.parent
    stats = create_comprehensive_supplementary(profile_data, output_dir)

    # Also copy to paper figures
    paper_dir = Path.home() / 'GitHub' / 'AortaCFDappPaper' / 'figures'
    if paper_dir.exists():
        import shutil
        shutil.copy(output_dir / 'gci_supplementary_profiles.png', paper_dir)
        shutil.copy(output_dir / 'gci_supplementary_profiles.pdf', paper_dir)
        print(f"Copied to {paper_dir}")

    print("\nDone!")
    return 0


if __name__ == '__main__':
    exit(main())
