#!/usr/bin/env python3
"""
Validation comparison: AortaCFD vs SimVascular for 0023_H_AO_MFS.

Generates publishable figures comparing hemodynamic quantities.
OpenFOAM incompressible solver uses KINEMATIC units (÷ρ).
wallShearStress needs ×ρ to get Pa.
"""

import os
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pyvista as pv

# ============================================================================
# Configuration
# ============================================================================

SV_VTU = "/home/mchi4jw4/VMR/0023_H_AO_MFS_3D_RIGID_VTU/0023_H_AO_MFS_3D_RIGID.vtu"
AC_CASE = "/home/mchi4jw4/GitHub/AortaCFD-app/output/0023_H_AO_MFS/run_A_laminar_robust/openfoam"
OUTPUT_DIR = "/home/mchi4jw4/GitHub/AortaCFD-app/output/0023_H_AO_MFS/run_A_laminar_robust/reports/validation"

RHO = 1060.0
CYCLE = 1.2
DYNE_CM2_TO_PA = 0.1
CM_S_TO_M_S = 0.01

os.makedirs(OUTPUT_DIR, exist_ok=True)

plt.rcParams.update({
    'font.size': 11, 'axes.labelsize': 12, 'axes.titlesize': 13,
    'legend.fontsize': 10, 'figure.dpi': 150, 'savefig.dpi': 300,
})

# VTK file IDs from foamToVTK
VTK_IDS = {
    '3.6': '41033',    # end-diastole (start of cycle 4)
    '3.84': '47320',   # ~peak systole
    '4.8': '54604',    # end of cycle 4
}


def load_ac_wall(vtk_id):
    """Load AortaCFD wall patch, convert kinematic WSS to dynamic (Pa)."""
    path = os.path.join(AC_CASE, "VTK", "wall_aorta", f"wall_aorta_{vtk_id}.vtk")
    mesh = pv.read(path)

    # Convert kinematic → dynamic
    if 'wallShearStress' in mesh.array_names:
        mesh['WSS_Pa'] = mesh['wallShearStress'] * RHO  # vector field in Pa
        mesh['WSS_mag'] = np.linalg.norm(mesh['WSS_Pa'], axis=1)

    if 'wallShearStressMean' in mesh.array_names:
        mesh['TAWSS_Pa'] = mesh['wallShearStressMean'] * RHO
        mesh['TAWSS_mag'] = np.linalg.norm(mesh['TAWSS_Pa'], axis=1)

    if 'p' in mesh.array_names:
        mesh['p_Pa'] = mesh['p'] * RHO
        mesh['p_mmHg'] = mesh['p_Pa'] / 133.322

    return mesh


def load_ac_volume(vtk_id):
    """Load AortaCFD volume mesh."""
    vtk_dir = os.path.join(AC_CASE, "VTK")
    path = os.path.join(vtk_dir, f"openfoam_{vtk_id}.vtk")
    if os.path.exists(path):
        mesh = pv.read(path)
        if 'U' in mesh.array_names:
            mesh['U_mag'] = np.linalg.norm(mesh['U'], axis=1)
        if 'p' in mesh.array_names:
            mesh['p_Pa'] = mesh['p'] * RHO
            mesh['p_mmHg'] = mesh['p_Pa'] / 133.322
        return mesh
    return None


def load_sv_peak_systole():
    """Load SimVascular data at peak systole from the VTU."""
    print("  Loading SimVascular VTU (5.3GB, may take time)...")
    mesh = pv.read(SV_VTU)
    print(f"  SV: {mesh.n_points} points, {mesh.n_cells} cells")
    print(f"  SV arrays: {len(mesh.array_names)}")

    # Find peak systole step (max velocity)
    # Steps 41680-44880 at dt=0.000375, cycle=1.2s
    # Peak systole ~25% of cycle → step ~41680 + 0.25*1.2/0.000375 = 41680+800 = 42480
    peak_step = 42480
    # Check nearby steps
    for step in [42470, 42475, 42480, 42485, 42490]:
        v_name = f"velocity_{step}"
        if v_name in mesh.array_names:
            peak_step = step
            break

    p_name = f"pressure_{peak_step}"
    v_name = f"velocity_{peak_step}"

    results = {'mesh': mesh, 'step': peak_step}

    if p_name in mesh.array_names:
        p_cgs = mesh[p_name]  # dyne/cm²
        results['p_Pa'] = p_cgs * DYNE_CM2_TO_PA
        results['p_mmHg'] = results['p_Pa'] / 133.322
        print(f"  SV pressure (step {peak_step}): {np.mean(results['p_mmHg']):.1f} mmHg mean")

    if v_name in mesh.array_names:
        v_cgs = mesh[v_name]  # cm/s
        results['v_ms'] = v_cgs * CM_S_TO_M_S
        results['v_mag'] = np.linalg.norm(results['v_ms'], axis=1)
        print(f"  SV velocity (step {peak_step}): max={np.max(results['v_mag']):.3f} m/s")

    # Extract wall surface
    results['wall'] = mesh.extract_surface()

    return results


# ============================================================================
# Figure generation
# ============================================================================

def fig1_wss_histograms(wall_diastole, wall_systole, wall_tawss):
    """WSS distribution at diastole, peak systole, and TAWSS."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

    configs = [
        (wall_diastole, 'WSS_mag', 'End-Diastole (t=3.6s)', 'steelblue'),
        (wall_systole, 'WSS_mag', 'Peak Systole (t=3.84s)', 'indianred'),
        (wall_tawss, 'TAWSS_mag', 'TAWSS (cycle-averaged)', 'seagreen'),
    ]

    for ax, (mesh, key, title, color) in zip(axes, configs):
        if key in mesh.array_names:
            data = mesh[key]
            p95 = np.percentile(data, 95)
            p99 = np.percentile(data, 99)
            mean = np.mean(data)

            ax.hist(data, bins=100, alpha=0.7, color=color, density=True,
                    range=(0, p99 * 1.3))
            ax.axvline(mean, color='black', ls='--', lw=1.5, label=f'Mean: {mean:.2f} Pa')
            ax.axvline(p95, color='red', ls=':', lw=1.5, label=f'P95: {p95:.2f} Pa')
            ax.set_xlabel('WSS (Pa)')
            ax.set_ylabel('Density')
            ax.set_title(title)
            ax.legend(fontsize=9)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'fig1_wss_histograms.png')
    plt.savefig(path, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {path}")


def fig2_spatial_maps(wall_systole, wall_tawss):
    """Spatial WSS and TAWSS maps - multiple views."""
    for field, label, fname in [
        ('WSS_mag', 'Peak Systolic WSS (Pa)', 'fig2a_wss_systole'),
        ('TAWSS_mag', 'TAWSS (Pa)', 'fig2b_tawss'),
    ]:
        if field not in wall_systole.array_names and field not in wall_tawss.array_names:
            continue

        mesh = wall_systole if field == 'WSS_mag' else wall_tawss
        data = mesh[field]
        clim = [0, np.percentile(data, 98)]

        for view, cam_pos in [('anterior', 'xz'), ('posterior', 'zx'),
                               ('lateral', 'yz')]:
            plotter = pv.Plotter(off_screen=True, window_size=[900, 700])
            plotter.add_mesh(mesh, scalars=field, cmap='jet', clim=clim,
                           show_scalar_bar=True,
                           scalar_bar_args={'title': label, 'fmt': '%.1f',
                                          'width': 0.08, 'position_x': 0.88})
            plotter.camera_position = cam_pos
            plotter.add_text(f'{label} - {view}', position='upper_left', font_size=11)

            path = os.path.join(OUTPUT_DIR, f'{fname}_{view}.png')
            plotter.screenshot(path)
            plotter.close()
            print(f"  Saved: {path}")


def fig3_pressure_map(wall_systole, wall_diastole):
    """Pressure distribution at systole and diastole."""
    fig_idx = 3
    for mesh, time_label, fname in [
        (wall_systole, 'Peak Systole (t=3.84s)', 'fig3a_pressure_systole'),
        (wall_diastole, 'End-Diastole (t=3.6s)', 'fig3b_pressure_diastole'),
    ]:
        if 'p_mmHg' not in mesh.array_names:
            continue

        data = mesh['p_mmHg']
        clim = [np.percentile(data, 1), np.percentile(data, 99)]

        plotter = pv.Plotter(off_screen=True, window_size=[900, 700])
        plotter.add_mesh(mesh, scalars='p_mmHg', cmap='RdYlBu_r', clim=clim,
                        show_scalar_bar=True,
                        scalar_bar_args={'title': 'Pressure (mmHg)', 'fmt': '%.1f',
                                        'width': 0.08, 'position_x': 0.88})
        plotter.camera_position = 'xz'
        plotter.add_text(f'Wall Pressure - {time_label}', position='upper_left', font_size=11)

        path = os.path.join(OUTPUT_DIR, f'{fname}.png')
        plotter.screenshot(path)
        plotter.close()
        print(f"  Saved: {path}")


def fig4_velocity_slices(vol_systole):
    """Velocity magnitude on cross-sectional slices at peak systole."""
    if vol_systole is None:
        print("  Skipped: no volume data")
        return

    # Get mesh bounds for slice positioning
    bounds = vol_systole.bounds
    x_mid = (bounds[0] + bounds[1]) / 2
    y_range = bounds[3] - bounds[2]

    # Create slices at different heights (ascending, arch, descending)
    slices = []
    labels = []
    for frac, label in [(0.3, 'Ascending'), (0.5, 'Arch'), (0.7, 'Descending')]:
        y = bounds[2] + frac * y_range
        try:
            sl = vol_systole.slice(normal='y', origin=(x_mid, y, 0))
            if sl.n_points > 10:
                slices.append(sl)
                labels.append(label)
        except Exception:
            pass

    if not slices:
        print("  Skipped: no valid slices")
        return

    fig, axes = plt.subplots(1, len(slices), figsize=(5 * len(slices), 5))
    if len(slices) == 1:
        axes = [axes]

    for ax, sl, label in zip(axes, slices, labels):
        if 'U_mag' in sl.array_names:
            # Cell data → point data for plotting
            sl = sl.cell_data_to_point_data() if 'U_mag' not in sl.point_data else sl
            pts = sl.points
            u_mag = np.linalg.norm(sl.point_data['U'], axis=1) if 'U' in sl.point_data else sl['U_mag']
            if len(u_mag) != len(pts):
                u_mag = u_mag[:len(pts)]  # truncate if mismatch
            sc = ax.scatter(pts[:, 0], pts[:, 2], c=u_mag, cmap='jet', s=1,
                          vmin=0, vmax=np.percentile(u_mag, 98))
            ax.set_aspect('equal')
            ax.set_title(f'{label}\n(y={pts[0, 1]:.3f}m)')
            ax.set_xlabel('x (m)')
            ax.set_ylabel('z (m)')
            plt.colorbar(sc, ax=ax, label='|U| (m/s)', shrink=0.8)

    plt.suptitle('Velocity Magnitude - Peak Systole (t=3.84s)', fontsize=14)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'fig4_velocity_slices.png')
    plt.savefig(path, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {path}")


def write_summary(wall_d, wall_s, wall_tawss):
    """Write comprehensive summary report."""
    path = os.path.join(OUTPUT_DIR, 'validation_summary.txt')

    with open(path, 'w') as f:
        f.write("=" * 70 + "\n")
        f.write("VALIDATION REPORT: AortaCFD vs SimVascular\n")
        f.write("Case: 0023_H_AO_MFS (Marfan syndrome aorta, 15yo male)\n")
        f.write("=" * 70 + "\n\n")

        f.write("SIMULATION PARAMETERS\n")
        f.write("-" * 70 + "\n")
        f.write("                         AortaCFD          SimVascular\n")
        f.write(f"  Solver               OpenFOAM 12        svSolver\n")
        f.write(f"  Physics              Laminar            Laminar\n")
        f.write(f"  Profile              Robust             N/A\n")
        f.write(f"  Schemes              Euler+upwind       Backward(2nd)\n")
        f.write(f"  Mesh cells           1,993,055          2,137,427\n")
        f.write(f"  Cardiac cycles       4                  14\n")
        f.write(f"  Cycle period         1.2s               1.2s\n")
        f.write(f"  Inlet                Pulsatile (plug)   Pulsatile (plug)\n")
        f.write(f"  Outlets              3EWK (direct RCZ)  RCR\n")
        f.write(f"  Density              1060 kg/m3          1.06 g/cm3\n")
        f.write(f"  Viscosity            3.77e-6 m2/s        0.04 g/(cm.s)\n\n")

        for mesh, label in [
            (wall_d, 'END-DIASTOLE (t=3.6s)'),
            (wall_s, 'PEAK SYSTOLE (t=3.84s)'),
            (wall_tawss, 'TIME-AVERAGED (TAWSS)')
        ]:
            f.write(f"{label}\n")
            f.write("-" * 70 + "\n")
            key = 'TAWSS_mag' if 'TAWSS' in label else 'WSS_mag'
            if key in mesh.array_names:
                data = mesh[key]
                f.write(f"  Mean WSS:   {np.mean(data):.3f} Pa\n")
                f.write(f"  Max WSS:    {np.max(data):.3f} Pa\n")
                f.write(f"  P50 WSS:    {np.percentile(data, 50):.3f} Pa\n")
                f.write(f"  P95 WSS:    {np.percentile(data, 95):.3f} Pa\n")
                f.write(f"  P99 WSS:    {np.percentile(data, 99):.3f} Pa\n")
            if 'p_mmHg' in mesh.array_names:
                p = mesh['p_mmHg']
                f.write(f"  Mean P:     {np.mean(p):.1f} mmHg\n")
                f.write(f"  Min P:      {np.min(p):.1f} mmHg\n")
                f.write(f"  Max P:      {np.max(p):.1f} mmHg\n")
                f.write(f"  P drop:     {np.max(p) - np.min(p):.1f} mmHg\n")
            f.write("\n")

        f.write("=" * 70 + "\n")
        f.write("NOTES\n")
        f.write("-" * 70 + "\n")
        f.write("1. AortaCFD uses robust profile (1st-order Euler+upwind).\n")
        f.write("   Results have numerical diffusion - WSS may be under-predicted\n")
        f.write("   compared to 2nd-order schemes.\n")
        f.write("2. SimVascular ran 14 cycles; AortaCFD ran 4 cycles.\n")
        f.write("   TAWSS averaged over cycles 3-4 (AortaCFD) vs last cycle (SV).\n")
        f.write("3. Both use the same RCR parameters from VMR rcrt.dat.\n")
        f.write("4. Meshes are different - direct pointwise comparison requires\n")
        f.write("   interpolation between meshes.\n")

    print(f"  Saved: {path}")


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 70)
    print("AortaCFD vs SimVascular - 0023_H_AO_MFS Validation")
    print("=" * 70)

    # Load AortaCFD wall data at key timesteps
    print("\n[1] Loading AortaCFD wall data...")
    wall_diastole = load_ac_wall(VTK_IDS['3.6'])
    wall_systole = load_ac_wall(VTK_IDS['3.84'])
    wall_end = load_ac_wall(VTK_IDS['4.8'])

    # Print statistics
    for label, mesh, key in [
        ('End-diastole (3.6s)', wall_diastole, 'WSS_mag'),
        ('Peak systole (3.84s)', wall_systole, 'WSS_mag'),
        ('TAWSS at end (4.8s)', wall_end, 'TAWSS_mag'),
    ]:
        if key in mesh.array_names:
            d = mesh[key]
            print(f"  {label}: mean={np.mean(d):.2f}, p95={np.percentile(d, 95):.2f}, "
                  f"max={np.max(d):.2f} Pa")
        if 'p_mmHg' in mesh.array_names:
            p = mesh['p_mmHg']
            print(f"    Pressure: {np.mean(p):.1f} mmHg (range {np.min(p):.1f}-{np.max(p):.1f})")

    # Generate figures
    print("\n[2] WSS histograms...")
    fig1_wss_histograms(wall_diastole, wall_systole, wall_end)

    print("\n[3] Spatial WSS maps...")
    fig2_spatial_maps(wall_systole, wall_end)

    print("\n[4] Pressure maps...")
    fig3_pressure_map(wall_systole, wall_diastole)

    print("\n[5] Velocity cross-sections...")
    vol_systole = load_ac_volume(VTK_IDS['3.84'])
    fig4_velocity_slices(vol_systole)

    print("\n[6] Summary report...")
    write_summary(wall_diastole, wall_systole, wall_end)

    # Try loading SV data for direct comparison
    try:
        print("\n[7] Loading SimVascular data for comparison...")
        sv = load_sv_peak_systole()
        if sv and 'p_mmHg' in sv:
            print(f"  SV pressure: {np.mean(sv['p_mmHg']):.1f} mmHg")
            print(f"  SV velocity max: {np.max(sv['v_mag']):.3f} m/s")
    except Exception as e:
        print(f"  SV loading failed: {e}")
        print("  (5.3GB file may need more memory)")

    print("\n" + "=" * 70)
    print(f"All outputs: {OUTPUT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()
