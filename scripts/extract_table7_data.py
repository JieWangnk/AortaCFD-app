#!/usr/bin/env python3
"""
Extract Table 7 data: Turbulence model comparison (Laminar vs RANS vs LES)
Computes peak velocity magnitude and pressure values at peak systole.
"""

import os
import sys
import re
import struct
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def parse_openfoam_binary_field(filepath):
    """Parse an OpenFOAM binary field file and return values as numpy array."""
    with open(filepath, 'rb') as f:
        content = f.read()

    # Decode header as text to get metadata
    # Find where binary data starts (after the count and opening paren)
    text_part = content[:2000].decode('utf-8', errors='ignore')

    # Check if binary format
    is_binary = 'format      binary' in text_part

    # Get field class (vector or scalar)
    is_vector = 'volVectorField' in text_part

    # Find the count - look for pattern like "349093\n("
    count_match = re.search(r'(\d+)\s*\(', text_part)
    if not count_match:
        raise ValueError(f"Could not find field count in: {filepath}")

    n_values = int(count_match.group(1))

    if is_binary:
        # Find the position of the count in bytes
        count_str = count_match.group(0)
        header_end = content.find(count_str.encode()) + len(count_str.encode())

        if is_vector:
            # Vector field: 3 doubles per value
            n_bytes = n_values * 3 * 8  # 8 bytes per double
            data = struct.unpack(f'{n_values * 3}d', content[header_end:header_end + n_bytes])
            return np.array(data).reshape(n_values, 3)
        else:
            # Scalar field
            n_bytes = n_values * 8
            data = struct.unpack(f'{n_values}d', content[header_end:header_end + n_bytes])
            return np.array(data)
    else:
        # ASCII format - use original parsing
        text_content = content.decode('utf-8')
        match = re.search(r'(\d+)\s*\(\s*(.*?)\s*\)', text_content, re.DOTALL)
        if not match:
            raise ValueError(f"Could not parse field file: {filepath}")

        data_block = match.group(2).strip()

        if is_vector:
            vectors = re.findall(r'\(([-\d.e+]+)\s+([-\d.e+]+)\s+([-\d.e+]+)\)', data_block)
            return np.array([[float(x), float(y), float(z)] for x, y, z in vectors])
        else:
            values = data_block.split()
            return np.array([float(v) for v in values])


def compute_velocity_magnitude(U):
    """Compute velocity magnitude from vector field."""
    return np.sqrt(U[:, 0]**2 + U[:, 1]**2 + U[:, 2]**2)


def extract_physics_model_data(case_dir, time_dir="0.2"):
    """Extract key metrics from a physics model simulation."""
    openfoam_dir = Path(case_dir) / "openfoam"
    time_path = openfoam_dir / time_dir

    if not time_path.exists():
        # Try without openfoam subdirectory
        time_path = Path(case_dir) / time_dir

    if not time_path.exists():
        raise FileNotFoundError(f"Time directory not found: {time_path}")

    # Parse U field
    U_file = time_path / "U"
    U = parse_openfoam_binary_field(U_file)
    U_mag = compute_velocity_magnitude(U)

    # Parse p field
    p_file = time_path / "p"
    p = parse_openfoam_binary_field(p_file)

    # Compute statistics
    results = {
        "peak_velocity": np.max(U_mag),
        "mean_velocity": np.mean(U_mag),
        "max_pressure": np.max(p),
        "min_pressure": np.min(p),
        "pressure_range": np.max(p) - np.min(p),
        "n_cells": len(U_mag),
    }

    return results


def main():
    base_dir = Path("/home/mchi4jw4/GitHub/AortaCFD-app/output/BPM120/physics_model")

    models = {
        "Laminar": base_dir / "laminar",
        "RANS k-ω SST": base_dir / "rans",
        "LES WALE": base_dir / "les",
    }

    # Peak systole is around t=0.1-0.2s for BPM120 (0.5s cycle)
    time_dir = "0.2"

    print("=" * 70)
    print("Table 7: Turbulence Model Comparison at Peak Systole (t=0.2s)")
    print("=" * 70)
    print()

    results = {}
    for model_name, case_dir in models.items():
        try:
            data = extract_physics_model_data(case_dir, time_dir)
            results[model_name] = data
            print(f"{model_name}:")
            print(f"  Cells: {data['n_cells']:,}")
            print(f"  Peak velocity: {data['peak_velocity']:.4f} m/s")
            print(f"  Mean velocity: {data['mean_velocity']:.4f} m/s")
            print(f"  Pressure range: {data['pressure_range']:.2f} Pa")
            print(f"  Max pressure: {data['max_pressure']:.2f} Pa")
            print(f"  Min pressure: {data['min_pressure']:.2f} Pa")
            print()
        except Exception as e:
            print(f"{model_name}: ERROR - {e}")
            print()

    # Compute relative differences using LES as reference
    if "LES WALE" in results:
        print("-" * 70)
        print("Relative Differences (LES WALE as reference)")
        print("-" * 70)
        les_data = results["LES WALE"]

        for model_name, data in results.items():
            if model_name == "LES WALE":
                continue

            vel_diff = (data["peak_velocity"] - les_data["peak_velocity"]) / les_data["peak_velocity"] * 100
            pres_diff = (data["pressure_range"] - les_data["pressure_range"]) / les_data["pressure_range"] * 100

            print(f"{model_name}:")
            print(f"  Peak velocity difference: {vel_diff:+.2f}%")
            print(f"  Pressure range difference: {pres_diff:+.2f}%")
            print()

    # Output in LaTeX table format
    print("=" * 70)
    print("LaTeX Table Format")
    print("=" * 70)
    print()
    print("Peak Velocity (m/s) & " + " & ".join([f"{results[m]['peak_velocity']:.3f}" for m in models.keys() if m in results]) + " \\\\")
    print("Pressure Range (Pa) & " + " & ".join([f"{results[m]['pressure_range']:.1f}" for m in models.keys() if m in results]) + " \\\\")


if __name__ == "__main__":
    main()
