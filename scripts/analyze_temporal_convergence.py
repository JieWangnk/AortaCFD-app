#!/usr/bin/env python3
"""
Analyze temporal convergence study comparing Co=0.5, Co=1.0, and Co=2.0 cases.

Extracts WSS statistics from VTK files to assess temporal discretization sensitivity.
"""

import numpy as np
import os
import glob
import re


def read_vtk_wss(filename):
    """Read wallShearStress from VTK file."""
    with open(filename, 'r') as f:
        content = f.read()

    # Find wallShearStress field
    wss_match = re.search(r'wallShearStress\s+3\s+(\d+)\s+float\s*\n([\s\S]*?)(?=\n[A-Za-z]|\Z)', content)
    if not wss_match:
        return None

    n_faces = int(wss_match.group(1))
    wss_text = wss_match.group(2)

    wss_values = []
    for line in wss_text.strip().split('\n'):
        vals = line.split()
        wss_values.extend([float(v) for v in vals])
        if len(wss_values) >= n_faces * 3:
            break

    wss = np.array(wss_values[:n_faces * 3]).reshape(-1, 3)
    return wss


def get_timestep_from_filename(filename):
    """Extract timestep number from VTK filename."""
    match = re.search(r'wall_aorta_(\d+)\.vtk', os.path.basename(filename))
    if match:
        return int(match.group(1))
    return 0


def analyze_wss_case(case_dir, case_name):
    """Analyze WSS for a single case."""
    vtk_dir = os.path.join(case_dir, 'openfoam', 'VTK', 'wall_aorta')
    if not os.path.exists(vtk_dir):
        print(f"  No VTK wall_aorta directory in {case_dir}")
        return None

    vtk_files = sorted(glob.glob(os.path.join(vtk_dir, 'wall_aorta_*.vtk')),
                       key=get_timestep_from_filename)

    if not vtk_files:
        print(f"  No VTK files found")
        return None

    print(f"\n{case_name}: Found {len(vtk_files)} time steps")

    # Collect WSS magnitude over time
    all_wss_mag = []

    for vtk_file in vtk_files:
        wss = read_vtk_wss(vtk_file)
        if wss is not None:
            wss_mag = np.linalg.norm(wss, axis=1)
            all_wss_mag.append(wss_mag)

    if not all_wss_mag:
        print(f"  No valid WSS data found")
        return None

    all_wss_mag = np.array(all_wss_mag)  # shape: (n_times, n_faces)
    n_times = all_wss_mag.shape[0]
    n_faces = all_wss_mag.shape[1]

    print(f"  Time steps analyzed: {n_times}")
    print(f"  Wall faces: {n_faces}")

    # Time-averaged WSS (TAWSS)
    tawss = np.mean(all_wss_mag, axis=0)

    # Temporal variation
    wss_std = np.std(all_wss_mag, axis=0)

    # Peak WSS at each face
    peak_wss = np.max(all_wss_mag, axis=0)

    # Instantaneous spatial statistics at each time
    spatial_mean_over_time = np.mean(all_wss_mag, axis=1)
    spatial_max_over_time = np.max(all_wss_mag, axis=1)

    # Statistics
    # OpenFOAM wallShearStress is in kinematic form (m²/s²)
    # Convert to dynamic WSS (Pa) by multiplying by density
    rho = 1060  # kg/m³ (blood density)

    results = {
        'case': case_name,
        'n_times': n_times,
        'n_faces': n_faces,
        'TAWSS_mean': np.mean(tawss) * rho,  # Convert to Pa
        'TAWSS_max': np.max(tawss) * rho,
        'TAWSS_std': np.std(tawss) * rho,
        'peak_WSS': np.max(peak_wss) * rho,
        'WSS_temporal_std': np.mean(wss_std) * rho,
        'spatial_mean_mean': np.mean(spatial_mean_over_time) * rho,
        'spatial_mean_std': np.std(spatial_mean_over_time) * rho,
    }

    print(f"  TAWSS (spatial mean): {results['TAWSS_mean']:.2f} Pa")
    print(f"  TAWSS (spatial max):  {results['TAWSS_max']:.2f} Pa")
    print(f"  Peak WSS (max ever):  {results['peak_WSS']:.2f} Pa")
    print(f"  Temporal std (mean):  {results['WSS_temporal_std']:.2f} Pa")

    return results, tawss


def main():
    base_dir = '/home/mchi4jw4/GitHub/AortaCFD-app/output/BPM120'

    cases = [
        ('temporal/co05', 'Co=0.5'),
        ('temporal/co1', 'Co=1.0'),
        ('temporal/co2', 'Co=2.0'),
    ]

    results = []
    tawss_fields = {}

    for case_dir_name, case_label in cases:
        case_dir = os.path.join(base_dir, case_dir_name)
        if os.path.exists(case_dir):
            result = analyze_wss_case(case_dir, case_label)
            if result:
                results.append(result[0])
                tawss_fields[case_label] = result[1]

    if not results:
        print("\nNo results to compare")
        return

    # Summary table
    print("\n" + "="*90)
    print("TEMPORAL CONVERGENCE STUDY: WSS Statistics (Courant Number Sensitivity)")
    print("="*90)
    print(f"{'Case':<12} {'TAWSS_mean':<14} {'TAWSS_max':<14} {'Peak_WSS':<14} {'Temporal_std':<14}")
    print(f"{'':12} {'(Pa)':<14} {'(Pa)':<14} {'(Pa)':<14} {'(Pa)':<14}")
    print("-"*90)
    for r in results:
        print(f"{r['case']:<12} {r['TAWSS_mean']:<14.2f} {r['TAWSS_max']:<14.2f} "
              f"{r['peak_WSS']:<14.2f} {r['WSS_temporal_std']:<14.2f}")
    print("="*90)

    # Calculate differences relative to finest resolution (Co=0.5)
    if len(results) >= 2:
        ref = results[0]  # Co=0.5 as reference
        print("\nRelative difference vs Co=0.5 (finest temporal resolution):")
        print("-"*70)
        for r in results[1:]:
            diff_mean = 100 * (r['TAWSS_mean'] - ref['TAWSS_mean']) / ref['TAWSS_mean']
            diff_max = 100 * (r['TAWSS_max'] - ref['TAWSS_max']) / ref['TAWSS_max']
            diff_peak = 100 * (r['peak_WSS'] - ref['peak_WSS']) / ref['peak_WSS']
            print(f"{r['case']}: TAWSS_mean {diff_mean:+.2f}%, TAWSS_max {diff_max:+.2f}%, Peak {diff_peak:+.2f}%")

    # Point-by-point comparison (L2 norm of TAWSS difference)
    rho = 1060  # kg/m³
    if len(tawss_fields) >= 2 and 'Co=0.5' in tawss_fields:
        ref_tawss = tawss_fields['Co=0.5']
        print("\nPoint-wise TAWSS comparison (L2 error vs Co=0.5):")
        print("-"*70)
        for label, tawss in tawss_fields.items():
            if label != 'Co=0.5':
                l2_error = np.sqrt(np.mean((tawss - ref_tawss)**2)) * rho
                l2_rel = 100 * l2_error / (np.mean(ref_tawss) * rho)
                print(f"{label}: L2 error = {l2_error:.3f} Pa ({l2_rel:.2f}% of mean TAWSS)")

    print("\n" + "="*90)
    print("CONCLUSION:")
    if len(results) >= 3:
        # Check if results converged
        diff_co1 = abs(results[1]['TAWSS_mean'] - results[0]['TAWSS_mean']) / results[0]['TAWSS_mean'] * 100
        diff_co2 = abs(results[2]['TAWSS_mean'] - results[0]['TAWSS_mean']) / results[0]['TAWSS_mean'] * 100
        print(f"Co=1.0 differs from Co=0.5 by {diff_co1:.2f}% in mean TAWSS")
        print(f"Co=2.0 differs from Co=0.5 by {diff_co2:.2f}% in mean TAWSS")
        if diff_co1 < 5 and diff_co2 < 5:
            print("All Courant numbers show good agreement (<5% difference)")
            print("Recommendation: Co=1.0 provides good balance of accuracy and efficiency")
        elif diff_co1 < 5:
            print("Co=1.0 shows good agreement with Co=0.5")
            print("Co=2.0 shows larger deviation - use with caution")
    print("="*90)


if __name__ == '__main__':
    main()
