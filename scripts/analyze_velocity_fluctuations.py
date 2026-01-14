#!/usr/bin/env python3
"""
Analyze velocity fluctuations from physics_model cases to compare
laminar, LES, and RANS turbulence modeling approaches.

Extracts:
- Mean velocity magnitude
- RMS velocity fluctuations
- Turbulence intensity (I = u_rms / U_mean)
"""

import numpy as np
import os
import glob
import re


def read_vtk_velocity(filename):
    """Read velocity field from OpenFOAM VTK file (ASCII format)."""
    with open(filename, 'r') as f:
        content = f.read()

    # Find CELL_DATA section
    cell_match = re.search(r'CELL_DATA\s+(\d+)', content)
    if not cell_match:
        return None, 0
    n_cells = int(cell_match.group(1))

    # Find U field: "U 3 N float" format
    u_match = re.search(r'U\s+3\s+(\d+)\s+float\s*\n([\s\S]*?)(?=\n[A-Za-z]|\nPOINT_DATA|\Z)', content)
    if not u_match:
        return None, n_cells

    # Parse velocity values
    vel_text = u_match.group(2)
    vel_values = []
    for line in vel_text.strip().split('\n'):
        vals = line.split()
        vel_values.extend([float(v) for v in vals])
        if len(vel_values) >= n_cells * 3:
            break

    velocity = np.array(vel_values[:n_cells * 3]).reshape(-1, 3)
    return velocity, n_cells


def get_time_from_filename(filename):
    """Extract time step number from VTK filename."""
    match = re.search(r'openfoam_(\d+)\.vtk', os.path.basename(filename))
    if match:
        return int(match.group(1))
    return 0


def analyze_case(case_dir, model_name):
    """Analyze velocity fluctuations for a single case."""
    vtk_dir = os.path.join(case_dir, 'openfoam', 'VTK')
    vtk_files = sorted(glob.glob(os.path.join(vtk_dir, 'openfoam_*.vtk')),
                       key=get_time_from_filename)

    if not vtk_files:
        print(f"  No VTK files found in {vtk_dir}")
        return None

    print(f"\n{model_name}: Found {len(vtk_files)} time steps")

    # Read first file to get mesh info
    vel0, n_cells = read_vtk_velocity(vtk_files[0])
    if vel0 is None:
        print(f"  Could not read velocity from first file")
        return None
    print(f"  Mesh: {n_cells} cells")

    # Collect velocity magnitude at all cells over time
    all_vel_mag = []
    for i, vtk_file in enumerate(vtk_files):
        velocity, _ = read_vtk_velocity(vtk_file)
        if velocity is not None:
            vel_mag = np.linalg.norm(velocity, axis=1)
            all_vel_mag.append(vel_mag)
            if (i + 1) % 5 == 0:
                print(f"    Processed {i+1}/{len(vtk_files)} files...")

    all_vel_mag = np.array(all_vel_mag)  # shape: (n_times, n_cells)
    n_times = all_vel_mag.shape[0]
    print(f"  Time steps loaded: {n_times}")

    # Time-averaged velocity magnitude at each cell
    mean_vel = np.mean(all_vel_mag, axis=0)  # shape: (n_cells,)

    # Velocity fluctuations
    vel_fluct = all_vel_mag - mean_vel  # shape: (n_times, n_cells)

    # RMS fluctuation at each cell
    rms_fluct = np.sqrt(np.mean(vel_fluct**2, axis=0))  # shape: (n_cells,)

    # Filter for cells with meaningful flow (>5% of max velocity)
    threshold = 0.05 * np.max(mean_vel)
    flow_mask = mean_vel > threshold
    n_flow_cells = np.sum(flow_mask)
    print(f"  Cells with significant flow: {n_flow_cells} ({100*n_flow_cells/n_cells:.1f}%)")

    # Turbulence intensity at each cell
    turb_intensity = np.zeros_like(mean_vel)
    turb_intensity[flow_mask] = rms_fluct[flow_mask] / mean_vel[flow_mask]

    # Statistics
    results = {
        'model': model_name,
        'n_cells': n_cells,
        'n_times': n_times,
        'U_mean': np.mean(mean_vel[flow_mask]),
        'U_max': np.max(mean_vel),
        'U_rms': np.mean(rms_fluct[flow_mask]),
        'I_mean': np.mean(turb_intensity[flow_mask]),
        'I_median': np.median(turb_intensity[flow_mask]),
        'I_p95': np.percentile(turb_intensity[flow_mask], 95),
    }

    print(f"  Mean velocity (in flow region): {results['U_mean']:.3f} m/s")
    print(f"  Max velocity:  {results['U_max']:.3f} m/s")
    print(f"  Mean RMS fluctuation: {results['U_rms']:.4f} m/s")
    print(f"  Mean turbulence intensity I: {results['I_mean']:.4f}")
    print(f"  Median turbulence intensity I: {results['I_median']:.4f}")
    print(f"  95th percentile I: {results['I_p95']:.4f}")

    return results


def main():
    base_dir = '/home/mchi4jw4/GitHub/AortaCFD-app/output/BPM120/physics_model'

    models = ['laminar', 'les', 'rans']
    results = []

    for model in models:
        case_dir = os.path.join(base_dir, model)
        if os.path.exists(case_dir):
            result = analyze_case(case_dir, model.upper())
            if result:
                results.append(result)

    # Summary table
    print("\n" + "="*80)
    print("SUMMARY: Velocity Fluctuation Analysis")
    print("="*80)
    print(f"{'Model':<10} {'U_mean':<10} {'U_max':<10} {'U_rms':<12} {'I_mean':<10} {'I_median':<10} {'I_p95':<10}")
    print("-"*80)
    for r in results:
        print(f"{r['model']:<10} {r['U_mean']:<10.3f} {r['U_max']:<10.3f} "
              f"{r['U_rms']:<12.5f} {r['I_mean']:<10.4f} {r['I_median']:<10.4f} {r['I_p95']:<10.4f}")
    print("="*80)

    print("\nNote: Turbulence intensity I = u'_rms / U_mean")
    print("Higher I in laminar case indicates numerical fluctuations (under-resolved DNS)")
    print("I_mean = spatial mean of local turbulence intensity over flow region")


if __name__ == '__main__':
    main()
