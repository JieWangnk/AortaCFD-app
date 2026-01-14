#!/usr/bin/env python3
"""
Analyze WSS profile sensitivity for AortaCFD paper.
Reads binary wallShearStress fields and compares standard vs accurate profiles.
"""

import struct
import re
import numpy as np
from pathlib import Path

# Physical constants
RHO = 1060.0  # kg/m³ blood density
MU = 0.0035   # Pa.s dynamic viscosity

def read_binary_wss_field(filepath):
    """
    Read binary wallShearStress field from OpenFOAM.
    Returns WSS magnitude for wall_aorta patch.
    """
    with open(filepath, 'rb') as f:
        content = f.read()

    # Decode header to find wall_aorta patch info
    header = content[:2000].decode('latin-1', errors='replace')

    # Find wall_aorta section
    match = re.search(r'wall_aorta\s*\{[^}]*value\s+nonuniform\s+List<vector>\s*\n\s*(\d+)', header)
    if not match:
        print(f"Could not find wall_aorta patch in {filepath}")
        return None

    n_faces = int(match.group(1))
    print(f"  Found {n_faces} wall faces")

    # Find the start of binary data after the count
    # Look for the '(' character after the count
    header_end = content.find(b'wall_aorta')
    search_start = header_end + 100  # Skip past the header text

    # Find pattern: number followed by newline and '('
    pattern = str(n_faces).encode() + b'\n('
    data_start = content.find(pattern, search_start)
    if data_start == -1:
        print(f"Could not find binary data start")
        return None

    # Binary data starts after the '('
    binary_start = data_start + len(pattern)

    # Each vector is 3 doubles (24 bytes)
    vector_size = 24
    binary_data = content[binary_start:binary_start + n_faces * vector_size]

    # Unpack as little-endian doubles
    wss_vectors = []
    for i in range(n_faces):
        offset = i * vector_size
        x, y, z = struct.unpack('<3d', binary_data[offset:offset + vector_size])
        wss_vectors.append([x, y, z])

    wss_vectors = np.array(wss_vectors)

    # Compute magnitude (WSS is in kinematic units m²/s² = ν * du/dn)
    # Convert to Pa: τ = ρ * ν * du/dn = μ * du/dn
    # But OpenFOAM wallShearStress is already τ/ρ, so multiply by ρ
    wss_magnitude = np.linalg.norm(wss_vectors, axis=1) * RHO

    return wss_magnitude


def main():
    base_dir = Path("/home/mchi4jw4/GitHub/AortaCFD-app/output/BPM120/profile_sensitivity")

    profiles = {
        "robust": base_dir / "profile_robust" / "1.5" / "wallShearStress",
        "standard": base_dir / "profile_standard" / "1.5" / "wallShearStress",
        "accurate": base_dir / "profile_accurate" / "1.5" / "wallShearStress",
    }

    results = {}

    print("=" * 70)
    print("WSS PROFILE SENSITIVITY ANALYSIS")
    print("=" * 70)

    for name, path in profiles.items():
        print(f"\n--- {name.upper()} ---")

        if not path.exists():
            print(f"  File not found: {path}")
            continue

        wss = read_binary_wss_field(path)
        if wss is None:
            continue

        results[name] = {
            "wss": wss,
            "max": float(np.max(wss)),
            "mean": float(np.mean(wss)),
            "min": float(np.min(wss)),
            "std": float(np.std(wss)),
            "p95": float(np.percentile(wss, 95)),
        }

        print(f"  WSS max:  {results[name]['max']:.4f} Pa")
        print(f"  WSS mean: {results[name]['mean']:.4f} Pa")
        print(f"  WSS min:  {results[name]['min']:.4f} Pa")
        print(f"  WSS 95th: {results[name]['p95']:.4f} Pa")
        print(f"  WSS std:  {results[name]['std']:.4f} Pa")

    # Comparison - use standard as reference
    if "standard" in results:
        print("\n" + "=" * 70)
        print("COMPARISON (vs standard)")
        print("=" * 70)

        std = results["standard"]

        for name in ["robust", "accurate"]:
            if name not in results:
                continue
            other = results[name]

            print(f"\n--- {name.upper()} vs STANDARD ---")
            print(f"WSS max difference:  {other['max'] - std['max']:.4f} Pa ({(other['max']-std['max'])/std['max']*100:.2f}%)")
            print(f"WSS mean difference: {other['mean'] - std['mean']:.4f} Pa ({(other['mean']-std['mean'])/std['mean']*100:.2f}%)")
            print(f"WSS 95th difference: {other['p95'] - std['p95']:.4f} Pa ({(other['p95']-std['p95'])/std['p95']*100:.2f}%)")

            # Point-wise comparison
            wss_diff = results[name]["wss"] - results["standard"]["wss"]
            print(f"\nPoint-wise difference statistics:")
            print(f"  Mean absolute diff: {np.mean(np.abs(wss_diff)):.4f} Pa")
            print(f"  Max absolute diff:  {np.max(np.abs(wss_diff)):.4f} Pa")
            print(f"  RMS difference:     {np.sqrt(np.mean(wss_diff**2)):.4f} Pa")

            # Relative difference
            rel_diff = wss_diff / (results["standard"]["wss"] + 1e-10) * 100
            print(f"\nRelative difference:")
            print(f"  Mean: {np.mean(np.abs(rel_diff)):.2f}%")
            print(f"  Max:  {np.max(np.abs(rel_diff)):.2f}%")

        # Summary table
        print("\n" + "=" * 70)
        print("SUMMARY TABLE")
        print("=" * 70)
        print(f"\n{'Profile':<12} {'Mean WSS (Pa)':<15} {'Peak WSS (Pa)':<15} {'95th WSS (Pa)':<15}")
        print("-" * 60)
        for name in ["robust", "standard", "accurate"]:
            if name in results:
                r = results[name]
                print(f"{name:<12} {r['mean']:.4f}         {r['max']:.4f}         {r['p95']:.4f}")


if __name__ == "__main__":
    main()
