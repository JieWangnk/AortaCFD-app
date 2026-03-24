#!/usr/bin/env python3
"""
3-timepoint validation: AortaCFD vs SimVascular at acceleration, peak systole, diastole.
Loads only 3 specific arrays from the 5.3GB SV VTU to avoid memory issues.
"""

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pyvista as pv
import vtk

RHO = 1060.0
CYCLE = 1.2
OUTPUT_DIR = "/home/mchi4jw4/GitHub/AortaCFD-app/output/0023_H_AO_MFS/run_A_laminar_robust/reports/validation"
AC_CASE = "/home/mchi4jw4/GitHub/AortaCFD-app/output/0023_H_AO_MFS/run_A_laminar_robust/openfoam"
SV_VTU = "/home/mchi4jw4/VMR/0023_H_AO_MFS_3D_RIGID_VTU/0023_H_AO_MFS_3D_RIGID.vtu"

# 3 comparison points
TIMEPOINTS = {
    'acceleration': {
        'sv_step': 42160, 'ac_time': 3.78, 'phase': '15%',
        'ac_vtk_id': '45104',
    },
    'peak_systole': {
        'sv_step': 42480, 'ac_time': 3.90, 'phase': '25%',
        'ac_vtk_id': '49434',
    },
    'mid_diastole': {
        'sv_step': 43760, 'ac_time': 4.38, 'phase': '65%',
        'ac_vtk_id': '53957',
    },
}

os.makedirs(OUTPUT_DIR, exist_ok=True)
plt.rcParams.update({'font.size': 11, 'axes.labelsize': 12, 'savefig.dpi': 300})


def load_sv_single_step(vtu_path, step_num):
    """Load only pressure and velocity for ONE step from the SV VTU using raw VTK reader."""
    print(f"  Loading SV step {step_num} from VTU...")

    reader = vtk.vtkXMLUnstructuredGridReader()
    reader.SetFileName(vtu_path)

    # Only read the specific arrays we need
    reader.GetPointDataArraySelection().DisableAllArrays()
    reader.GetPointDataArraySelection().EnableArray(f"pressure_{step_num}")
    reader.GetPointDataArraySelection().EnableArray(f"velocity_{step_num}")
    reader.Update()

    mesh = pv.wrap(reader.GetOutput())
    print(f"  SV: {mesh.n_points} points, arrays: {mesh.array_names}")

    result = {'n_points': mesh.n_points}

    p_name = f"pressure_{step_num}"
    v_name = f"velocity_{step_num}"

    if p_name in mesh.array_names and mesh.n_points > 0:
        p_cgs = mesh[p_name]  # dyne/cm2
        result['p_Pa'] = p_cgs * 0.1
        result['p_mmHg'] = result['p_Pa'] / 133.322
        print(f"  SV pressure: mean={np.mean(result['p_mmHg']):.1f} mmHg, "
              f"range=[{np.min(result['p_mmHg']):.1f}, {np.max(result['p_mmHg']):.1f}]")

    if v_name in mesh.array_names and mesh.n_points > 0:
        v_cgs = mesh[v_name]  # cm/s
        result['v_ms'] = v_cgs * 0.01
        result['v_mag'] = np.linalg.norm(result['v_ms'], axis=1)
        print(f"  SV velocity: max={np.max(result['v_mag']):.3f} m/s, "
              f"mean={np.mean(result['v_mag']):.3f} m/s")

    return result


def load_ac_wall(vtk_id):
    """Load AortaCFD wall patch with kinematic to dynamic conversion."""
    path = os.path.join(AC_CASE, "VTK", "wall_aorta", f"wall_aorta_{vtk_id}.vtk")
    mesh = pv.read(path)

    result = {'n_points': mesh.n_points}

    if 'wallShearStress' in mesh.array_names:
        wss = mesh['wallShearStress'] * RHO  # kinematic -> Pa
        result['wss_mag'] = np.linalg.norm(wss, axis=1)
        print(f"  AC WSS: mean={np.mean(result['wss_mag']):.2f}, "
              f"max={np.max(result['wss_mag']):.2f} Pa")

    if 'p' in mesh.array_names:
        result['p_Pa'] = mesh['p'] * RHO
        result['p_mmHg'] = result['p_Pa'] / 133.322
        print(f"  AC pressure: mean={np.mean(result['p_mmHg']):.1f} mmHg, "
              f"range=[{np.min(result['p_mmHg']):.1f}, {np.max(result['p_mmHg']):.1f}]")

    return result


def load_ac_volume(vtk_id):
    """Load AortaCFD volume mesh."""
    path = os.path.join(AC_CASE, "VTK", f"openfoam_{vtk_id}.vtk")
    if not os.path.exists(path):
        return None
    mesh = pv.read(path)
    result = {'n_points': mesh.n_points}
    if 'U' in mesh.array_names:
        result['v_mag'] = np.linalg.norm(mesh['U'], axis=1)
        print(f"  AC velocity: max={np.max(result['v_mag']):.3f} m/s, "
              f"mean={np.mean(result['v_mag']):.3f} m/s")
    if 'p' in mesh.array_names:
        result['p_Pa'] = mesh['p'] * RHO
        result['p_mmHg'] = result['p_Pa'] / 133.322
    return result


def make_comparison_figure(ac_data, sv_data, timepoints):
    """Create the main 3-timepoint comparison figure."""

    fig, axes = plt.subplots(3, 3, figsize=(15, 12))

    for row, (name, tp) in enumerate(timepoints.items()):
        ac = ac_data[name]
        sv = sv_data[name]

        # Col 1: Pressure histogram comparison
        ax = axes[row, 0]
        if 'p_mmHg' in sv and 'p_mmHg' in ac:
            ax.hist(sv['p_mmHg'], bins=80, alpha=0.5, color='red', density=True,
                    label=f"SV (mean={np.mean(sv['p_mmHg']):.1f})")
            ax.hist(ac['p_mmHg'], bins=80, alpha=0.5, color='blue', density=True,
                    label=f"AC (mean={np.mean(ac['p_mmHg']):.1f})")
            ax.set_xlabel('Pressure (mmHg)')
            ax.set_ylabel('Density')
            ax.legend(fontsize=8)
        ax.set_title(f"{name.replace('_', ' ').title()} ({tp['phase']})")

        # Col 2: Velocity histogram comparison
        ax = axes[row, 1]
        if 'v_mag' in sv and 'v_mag' in ac:
            v_max = max(np.percentile(sv['v_mag'], 99), np.percentile(ac['v_mag'], 99))
            ax.hist(sv['v_mag'], bins=80, alpha=0.5, color='red', density=True,
                    range=(0, v_max * 1.1),
                    label=f"SV (max={np.max(sv['v_mag']):.2f})")
            ax.hist(ac['v_mag'], bins=80, alpha=0.5, color='blue', density=True,
                    range=(0, v_max * 1.1),
                    label=f"AC (max={np.max(ac['v_mag']):.2f})")
            ax.set_xlabel('|U| (m/s)')
            ax.set_ylabel('Density')
            ax.legend(fontsize=8)
        ax.set_title(f"Velocity - {tp['phase']}")

        # Col 3: WSS histogram (AortaCFD only - SV doesn't store WSS directly)
        ax = axes[row, 2]
        if 'wss_mag' in ac:
            wss = ac['wss_mag']
            ax.hist(wss, bins=80, alpha=0.7, color='steelblue', density=True,
                    range=(0, np.percentile(wss, 99) * 1.3))
            ax.axvline(np.mean(wss), color='navy', ls='--',
                      label=f"Mean: {np.mean(wss):.2f} Pa")
            ax.axvline(np.percentile(wss, 95), color='red', ls=':',
                      label=f"P95: {np.percentile(wss, 95):.2f} Pa")
            ax.set_xlabel('WSS (Pa)')
            ax.set_ylabel('Density')
            ax.legend(fontsize=8)
        ax.set_title(f"AortaCFD WSS - {tp['phase']}")

    plt.suptitle('AortaCFD vs SimVascular - 0023_H_AO_MFS\n'
                 '(Red=SimVascular, Blue=AortaCFD)', fontsize=14, y=1.02)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'fig5_3timepoint_comparison.png')
    plt.savefig(path, bbox_inches='tight')
    plt.close()
    print(f"\n  Saved: {path}")


def write_comparison_table(ac_data, sv_data, ac_wall, timepoints):
    """Write quantitative comparison table."""
    path = os.path.join(OUTPUT_DIR, 'comparison_table.txt')

    with open(path, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("QUANTITATIVE COMPARISON: AortaCFD vs SimVascular\n")
        f.write("Case: 0023_H_AO_MFS (Marfan syndrome aorta)\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"{'Phase':<20} {'Metric':<25} {'AortaCFD':<15} {'SimVascular':<15} {'Diff %':<10}\n")
        f.write("-" * 80 + "\n")

        for name, tp in timepoints.items():
            ac = ac_data[name]
            sv = sv_data[name]
            acw = ac_wall[name]

            label = f"{name.replace('_', ' ')} ({tp['phase']})"

            # Pressure
            if 'p_mmHg' in ac and 'p_mmHg' in sv:
                ac_p = np.mean(ac['p_mmHg'])
                sv_p = np.mean(sv['p_mmHg'])
                diff = (ac_p - sv_p) / sv_p * 100 if sv_p != 0 else 0
                f.write(f"{label:<20} {'Mean P (mmHg)':<25} {ac_p:<15.1f} {sv_p:<15.1f} {diff:<+10.1f}\n")

                ac_dp = np.max(ac['p_mmHg']) - np.min(ac['p_mmHg'])
                sv_dp = np.max(sv['p_mmHg']) - np.min(sv['p_mmHg'])
                diff_dp = (ac_dp - sv_dp) / sv_dp * 100 if sv_dp != 0 else 0
                f.write(f"{'':<20} {'P drop (mmHg)':<25} {ac_dp:<15.1f} {sv_dp:<15.1f} {diff_dp:<+10.1f}\n")

            # Velocity - use P99 not max (max has single-cell spikes in both solvers)
            if 'v_mag' in ac and 'v_mag' in sv:
                ac_v99 = np.percentile(ac['v_mag'], 99)
                sv_v99 = np.percentile(sv['v_mag'], 99)
                diff99 = (ac_v99 - sv_v99) / sv_v99 * 100 if sv_v99 != 0 else 0
                f.write(f"{'':<20} {'P99 |U| (m/s)':<25} {ac_v99:<15.3f} {sv_v99:<15.3f} {diff99:<+10.1f}\n")
                ac_vmean = np.mean(ac['v_mag'])
                sv_vmean = np.mean(sv['v_mag'])
                diff_m = (ac_vmean - sv_vmean) / sv_vmean * 100 if sv_vmean != 0 else 0
                f.write(f"{'':<20} {'Mean |U| (m/s)':<25} {ac_vmean:<15.3f} {sv_vmean:<15.3f} {diff_m:<+10.1f}\n")

            # WSS (AortaCFD only)
            if 'wss_mag' in acw:
                wss = acw['wss_mag']
                f.write(f"{'':<20} {'Mean WSS (Pa)':<25} {np.mean(wss):<15.2f} {'N/A':<15} {'':<10}\n")
                f.write(f"{'':<20} {'P95 WSS (Pa)':<25} {np.percentile(wss,95):<15.2f} {'N/A':<15} {'':<10}\n")

            f.write("\n")

    print(f"  Saved: {path}")


def main():
    print("=" * 70)
    print("3-Timepoint Comparison: AortaCFD vs SimVascular")
    print("0023_H_AO_MFS - Acceleration / Peak Systole / Diastole")
    print("=" * 70)

    # Load SimVascular data (3 steps only)
    print("\n[1] Loading SimVascular data (3 steps only)...")
    sv_data = {}
    for name, tp in TIMEPOINTS.items():
        print(f"\n  --- {name} (SV step {tp['sv_step']}) ---")
        sv_data[name] = load_sv_single_step(SV_VTU, tp['sv_step'])

    # Load AortaCFD data
    print("\n[2] Loading AortaCFD data...")
    ac_data = {}
    ac_wall = {}
    for name, tp in TIMEPOINTS.items():
        print(f"\n  --- {name} (AC t={tp['ac_time']}s) ---")
        ac_wall[name] = load_ac_wall(tp['ac_vtk_id'])
        ac_data[name] = load_ac_volume(tp['ac_vtk_id'])
        if ac_data[name] is None:
            ac_data[name] = ac_wall[name]  # fallback to wall data

    # Generate comparison figure
    print("\n[3] Generating comparison figure...")
    make_comparison_figure(ac_data, sv_data, TIMEPOINTS)

    # Write quantitative table
    print("\n[4] Writing comparison table...")
    write_comparison_table(ac_data, sv_data, ac_wall, TIMEPOINTS)

    print("\n" + "=" * 70)
    print(f"Outputs: {OUTPUT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()
