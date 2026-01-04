#!/usr/bin/env python3
"""
Extract Table 4 data: Mesh Convergence Study with GCI Calculation
Uses Richardson extrapolation to compute Grid Convergence Index.
"""

import sys
import numpy as np
from pathlib import Path

# Add scripts to path for extract_table7_data module
sys.path.insert(0, str(Path(__file__).parent))
from extract_table7_data import extract_physics_model_data


def compute_gci(phi_coarse, phi_medium, phi_fine, r_coarse_medium, r_medium_fine, p=2.0, Fs=1.25):
    """
    Compute Grid Convergence Index (GCI) using Richardson extrapolation.

    Parameters:
    -----------
    phi_coarse, phi_medium, phi_fine : float
        Values of the quantity of interest on coarse, medium, and fine meshes
    r_coarse_medium : float
        Refinement ratio between coarse and medium meshes (h_coarse/h_medium)
    r_medium_fine : float
        Refinement ratio between medium and fine meshes (h_medium/h_fine)
    p : float
        Order of convergence (default 2.0 for second-order methods)
    Fs : float
        Factor of safety (1.25 for 3+ grids)

    Returns:
    --------
    dict with GCI values and extrapolated value
    """
    # Use average refinement ratio
    r = (r_coarse_medium + r_medium_fine) / 2

    # Compute apparent order of convergence
    epsilon_32 = phi_medium - phi_coarse  # coarse to medium
    epsilon_21 = phi_fine - phi_medium    # medium to fine

    if epsilon_21 == 0 or epsilon_32 == 0:
        # Monotonic convergence not achieved
        return {
            "gci_fine": float('nan'),
            "gci_medium": float('nan'),
            "extrapolated": phi_fine,
            "convergence": "oscillatory",
            "p_apparent": float('nan')
        }

    # Check for monotonic convergence
    if epsilon_32 * epsilon_21 < 0:
        return {
            "gci_fine": float('nan'),
            "gci_medium": float('nan'),
            "extrapolated": phi_fine,
            "convergence": "oscillatory",
            "p_apparent": float('nan')
        }

    # Apparent order of convergence
    try:
        p_apparent = np.log(abs(epsilon_32 / epsilon_21)) / np.log(r)
    except:
        p_apparent = p

    # Limit p to reasonable range
    p_apparent = max(0.5, min(p_apparent, 4.0))

    # Richardson extrapolated value
    phi_extrapolated = phi_fine + (phi_fine - phi_medium) / (r**p_apparent - 1)

    # GCI for fine mesh
    e_a = abs((phi_fine - phi_medium) / phi_fine) if phi_fine != 0 else 0
    gci_fine = Fs * e_a / (r**p_apparent - 1) * 100  # as percentage

    # GCI for medium mesh
    e_a_medium = abs((phi_medium - phi_coarse) / phi_medium) if phi_medium != 0 else 0
    gci_medium = Fs * e_a_medium / (r**p_apparent - 1) * 100

    return {
        "gci_fine": gci_fine,
        "gci_medium": gci_medium,
        "extrapolated": phi_extrapolated,
        "convergence": "monotonic",
        "p_apparent": p_apparent
    }


def main():
    base_dir = Path("/home/mchi4jw4/GitHub/AortaCFD-app/output/BPM120/config_mesh")

    # Define mesh levels - using directory names
    meshes = {
        "23k": {"cells": 23387, "dir": base_dir / "23k"},
        "138k": {"cells": 138586, "dir": base_dir / "138k"},
        "664k": {"cells": 664314, "dir": base_dir / "664k"},
    }

    # Compute effective mesh size (h) based on cell count
    # h ~ N^(-1/3) for 3D
    for name, mesh in meshes.items():
        mesh["h"] = mesh["cells"] ** (-1/3)

    # Peak systole time
    time_dir = "0.2"

    print("=" * 70)
    print("Table 4: Mesh Convergence Study (t=0.2s, Peak Systole)")
    print("=" * 70)
    print()

    # Extract data for each mesh
    results = {}
    for name, mesh in meshes.items():
        try:
            data = extract_physics_model_data(mesh["dir"], time_dir)
            results[name] = {
                "cells": mesh["cells"],
                "h": mesh["h"],
                "peak_velocity": data["peak_velocity"],
                "mean_velocity": data["mean_velocity"],
                "pressure_range": data["pressure_range"],
            }
            print(f"{name} ({mesh['cells']:,} cells):")
            print(f"  Peak velocity: {data['peak_velocity']:.4f} m/s")
            print(f"  Mean velocity: {data['mean_velocity']:.4f} m/s")
            print(f"  Pressure range: {data['pressure_range']:.2f} Pa")
            print()
        except Exception as e:
            print(f"{name}: ERROR - {e}")
            print()

    # Compute refinement ratios
    if len(results) >= 3:
        mesh_names = list(results.keys())
        coarse = results[mesh_names[0]]
        medium = results[mesh_names[1]]
        fine = results[mesh_names[2]]

        r_cm = coarse["h"] / medium["h"]  # coarse to medium
        r_mf = medium["h"] / fine["h"]    # medium to fine

        print("-" * 70)
        print("Refinement Ratios:")
        print(f"  Coarse→Medium: r = {r_cm:.3f}")
        print(f"  Medium→Fine:   r = {r_mf:.3f}")
        print()

        # GCI for peak velocity
        print("-" * 70)
        print("GCI Analysis - Peak Velocity")
        print("-" * 70)
        gci_vel = compute_gci(
            coarse["peak_velocity"],
            medium["peak_velocity"],
            fine["peak_velocity"],
            r_cm, r_mf
        )
        print(f"  Convergence: {gci_vel['convergence']}")
        print(f"  Apparent order: {gci_vel['p_apparent']:.2f}")
        print(f"  Extrapolated value: {gci_vel['extrapolated']:.4f} m/s")
        print(f"  GCI_fine: {gci_vel['gci_fine']:.2f}%")
        print(f"  GCI_medium: {gci_vel['gci_medium']:.2f}%")
        print()

        # GCI for pressure range
        print("-" * 70)
        print("GCI Analysis - Pressure Range")
        print("-" * 70)
        gci_pres = compute_gci(
            coarse["pressure_range"],
            medium["pressure_range"],
            fine["pressure_range"],
            r_cm, r_mf
        )
        print(f"  Convergence: {gci_pres['convergence']}")
        print(f"  Apparent order: {gci_pres['p_apparent']:.2f}")
        print(f"  Extrapolated value: {gci_pres['extrapolated']:.2f} Pa")
        print(f"  GCI_fine: {gci_pres['gci_fine']:.2f}%")
        print(f"  GCI_medium: {gci_pres['gci_medium']:.2f}%")
        print()

        # Output in LaTeX format
        print("=" * 70)
        print("LaTeX Table Format")
        print("=" * 70)
        print()
        print("% Table 4: Mesh Convergence")
        print("\\begin{tabular}{lccc}")
        print("\\toprule")
        print("\\textbf{Parameter} & \\textbf{Coarse} & \\textbf{Medium} & \\textbf{Fine} \\\\")
        print("\\midrule")
        print(f"Cells & {coarse['cells']:,} & {medium['cells']:,} & {fine['cells']:,} \\\\")
        print(f"Peak velocity (m/s) & {coarse['peak_velocity']:.3f} & {medium['peak_velocity']:.3f} & {fine['peak_velocity']:.3f} \\\\")
        print(f"Pressure range (Pa) & {coarse['pressure_range']:.1f} & {medium['pressure_range']:.1f} & {fine['pressure_range']:.1f} \\\\")
        print("\\midrule")
        print(f"GCI velocity (\\%) & -- & {gci_vel['gci_medium']:.1f} & {gci_vel['gci_fine']:.1f} \\\\")
        print(f"GCI pressure (\\%) & -- & {gci_pres['gci_medium']:.1f} & {gci_pres['gci_fine']:.1f} \\\\")
        print("\\bottomrule")
        print("\\end{tabular}")


if __name__ == "__main__":
    main()
