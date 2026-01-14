#!/usr/bin/env python3
"""
Sample velocity profiles along defined lines for GCI analysis.

Uses coordinates from ParaView PlotOverLine to sample velocity at
consistent locations across all mesh levels.

Cross-sections defined by user in ParaView:
1. Ascending Aorta
2. Aortic Arch
3. Descending Aorta
"""

import numpy as np
import json
import struct
import re
from pathlib import Path
from scipy.interpolate import NearestNDInterpolator, LinearNDInterpolator


# Sampling line definitions (from ParaView)
SAMPLING_LINES = {
    'ascending': {
        'name': 'Ascending Aorta',
        'point1': np.array([-0.0243909, -0.0244289, 0.0042441]),
        'point2': np.array([-0.0173972, -0.0135506, 0.00156382]),
    },
    'arch': {
        'name': 'Aortic Arch',
        'point1': np.array([-0.00791061, -0.007685, 0.0157702]),
        'point2': np.array([-0.00871511, -0.0102629, 0.008778]),
    },
    'descending': {
        'name': 'Descending Aorta',
        'point1': np.array([-0.00205959, 0.00128985, -0.0188373]),
        'point2': np.array([0.00597293, 0.00835758, -0.0182025]),
    },
}


def parse_openfoam_points(points_file):
    """Parse OpenFOAM binary points file."""
    with open(points_file, 'rb') as f:
        content = f.read()

    # Get header info
    text_part = content[:2000].decode('utf-8', errors='ignore')

    # Find point count
    count_match = re.search(r'(\d+)\s*\(', text_part)
    if not count_match:
        raise ValueError("Could not find point count")

    n_points = int(count_match.group(1))

    # Find binary data start
    count_str = count_match.group(0)
    header_end = content.find(count_str.encode()) + len(count_str.encode())

    # Read binary data (3 doubles per point)
    n_bytes = n_points * 3 * 8
    data = struct.unpack(f'{n_points * 3}d', content[header_end:header_end + n_bytes])

    return np.array(data).reshape(n_points, 3)


def parse_openfoam_field(field_file):
    """Parse OpenFOAM binary field file (scalar or vector)."""
    with open(field_file, 'rb') as f:
        content = f.read()

    text_part = content[:2000].decode('utf-8', errors='ignore')
    is_vector = 'volVectorField' in text_part

    count_match = re.search(r'(\d+)\s*\(', text_part)
    if not count_match:
        raise ValueError("Could not find field count")

    n_values = int(count_match.group(1))
    count_str = count_match.group(0)
    header_end = content.find(count_str.encode()) + len(count_str.encode())

    if is_vector:
        n_bytes = n_values * 3 * 8
        data = struct.unpack(f'{n_values * 3}d', content[header_end:header_end + n_bytes])
        return np.array(data).reshape(n_values, 3)
    else:
        n_bytes = n_values * 8
        data = struct.unpack(f'{n_values}d', content[header_end:header_end + n_bytes])
        return np.array(data)


def compute_cell_centers(case_dir):
    """Compute cell centers from mesh data."""
    poly_mesh = case_dir / 'constant' / 'polyMesh'

    # For simplicity, use the existing cell centers if available
    # Otherwise we'd need to compute from faces/points which is complex

    # Try to find writeCellCentres output
    for time_dir in sorted(case_dir.iterdir()):
        if time_dir.is_dir() and time_dir.name.replace('.', '', 1).isdigit():
            cc_file = time_dir / 'C'
            if cc_file.exists():
                return parse_openfoam_field(cc_file)

    # If no cell centers, we need to compute them
    # This is a simplified approach - use mesh points and average
    print("  Warning: No cell centers found, using approximation")
    return None


def sample_along_line(cell_centers, field_values, point1, point2, n_samples=51):
    """
    Sample field values along a line from point1 to point2.

    Uses nearest neighbor interpolation for robustness.
    """
    # Generate sample points along line
    t = np.linspace(0, 1, n_samples)
    sample_points = point1 + np.outer(t, (point2 - point1))

    # Create interpolator
    # Use nearest neighbor for robustness (works even if points are outside convex hull)
    interpolator = NearestNDInterpolator(cell_centers, field_values)

    # Sample
    sampled_values = interpolator(sample_points)

    # Compute arc length
    arc_length = t * np.linalg.norm(point2 - point1)

    return arc_length, sampled_values, sample_points


def sample_case(case_dir, time_dir='1.5'):
    """Sample velocity profiles from a single case."""
    case_path = Path(case_dir)
    openfoam_dir = case_path / 'openfoam' if (case_path / 'openfoam').exists() else case_path

    # Find time directory
    time_path = openfoam_dir / time_dir
    if not time_path.exists():
        # Find last time directory
        time_dirs = sorted([
            d for d in openfoam_dir.iterdir()
            if d.is_dir() and d.name.replace('.', '', 1).isdigit() and d.name != '0'
        ], key=lambda x: float(x.name))
        if time_dirs:
            time_path = time_dirs[-1]
        else:
            raise FileNotFoundError(f"No time directories found in {openfoam_dir}")

    print(f"  Using time directory: {time_path.name}")

    # Load velocity field
    U_file = time_path / 'U'
    if not U_file.exists():
        raise FileNotFoundError(f"U field not found: {U_file}")

    U = parse_openfoam_field(U_file)
    U_mag = np.linalg.norm(U, axis=1)

    # Get cell centers (OpenFOAM 12 writes separate Ccx, Ccy, Ccz files)
    Ccx_file = time_path / 'Ccx'
    Ccy_file = time_path / 'Ccy'
    Ccz_file = time_path / 'Ccz'

    if Ccx_file.exists() and Ccy_file.exists() and Ccz_file.exists():
        Ccx = parse_openfoam_field(Ccx_file)
        Ccy = parse_openfoam_field(Ccy_file)
        Ccz = parse_openfoam_field(Ccz_file)
        cell_centers = np.column_stack([Ccx, Ccy, Ccz])
    elif (time_path / 'C').exists():
        cell_centers = parse_openfoam_field(time_path / 'C')
    else:
        raise FileNotFoundError(
            f"Cell centers not found. Run: "
            f"postProcess -case {openfoam_dir} -func writeCellCentres -time {time_path.name}"
        )

    print(f"  Loaded {len(U_mag)} cells")

    # Sample each line
    results = {}
    for line_id, line_def in SAMPLING_LINES.items():
        arc, U_sampled, points = sample_along_line(
            cell_centers, U_mag,
            line_def['point1'], line_def['point2'],
            n_samples=51
        )

        results[line_id] = {
            'name': line_def['name'],
            'arc_length': arc.tolist(),
            'U_magnitude': U_sampled.tolist(),
            'points': points.tolist(),
            'point1': line_def['point1'].tolist(),
            'point2': line_def['point2'].tolist(),
        }

        print(f"    {line_def['name']}: U_mean={np.mean(U_sampled):.4f} m/s, "
              f"U_max={np.max(U_sampled):.4f} m/s")

    return results


def main():
    base_dir = Path('/home/mchi4jw4/GitHub/AortaCFD-app/output/BPM120/gci_mesh_study')

    meshes = [
        ('mesh1_coarse', 'Coarse'),
        ('mesh2_medium', 'Medium'),
        ('mesh3_fine', 'Fine'),
    ]

    print("="*70)
    print("GCI Profile Sampling")
    print("="*70)
    print(f"\nSampling lines:")
    for line_id, line_def in SAMPLING_LINES.items():
        length = np.linalg.norm(line_def['point2'] - line_def['point1']) * 1000
        print(f"  {line_def['name']}: {length:.1f} mm")
    print()

    all_results = []

    for mesh_dir, mesh_name in meshes:
        case_dir = base_dir / mesh_dir
        if not case_dir.exists():
            print(f"WARNING: {case_dir} not found, skipping")
            continue

        print(f"\n{mesh_name} mesh ({mesh_dir}):")

        try:
            results = sample_case(case_dir)
            all_results.append({
                'mesh': mesh_name,
                'case_path': str(case_dir),
                'profiles': results,
            })
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

    # Save results
    output_file = base_dir / 'gci_profile_samples.json'
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved results to: {output_file}")

    # Print summary
    if len(all_results) >= 3:
        print("\n" + "="*70)
        print("Summary: Velocity at line centers")
        print("="*70)
        for line_id in SAMPLING_LINES.keys():
            print(f"\n{SAMPLING_LINES[line_id]['name']}:")
            for result in all_results:
                mid_idx = len(result['profiles'][line_id]['U_magnitude']) // 2
                U_center = result['profiles'][line_id]['U_magnitude'][mid_idx]
                U_mean = np.mean(result['profiles'][line_id]['U_magnitude'])
                print(f"  {result['mesh']:8s}: U_center={U_center:.4f}, U_mean={U_mean:.4f} m/s")


if __name__ == '__main__':
    main()
