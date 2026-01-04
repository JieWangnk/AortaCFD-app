#!/usr/bin/env python3
"""Extract simulation results for paper tables.

This script extracts hemodynamic quantities from OpenFOAM simulation outputs
for the AortaCFD paper verification and validation section.

Tables to populate:
- Table 4: Mesh convergence (GCI analysis)
- Table 5: Temporal convergence
- Table 6: Numerical scheme comparison
- Table 7: Turbulence model comparison
"""

import os
import re
import sys
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


def parse_openfoam_field(field_path: Path) -> Optional[np.ndarray]:
    """Parse an OpenFOAM field file and return values as numpy array.

    Args:
        field_path: Path to the OpenFOAM field file (U, p, etc.)

    Returns:
        numpy array of field values, or None if parsing fails
    """
    if not field_path.exists():
        return None

    with open(field_path, 'r') as f:
        content = f.read()

    # Find the internalField section
    # Format: internalField nonuniform List<vector|scalar>
    pattern = r'internalField\s+nonuniform\s+List<(\w+)>\s*\n(\d+)\s*\n\(([\s\S]*?)\);'
    match = re.search(pattern, content)

    if not match:
        # Try uniform field
        pattern_uniform = r'internalField\s+uniform\s+\(([\d\.\-e\+\s]+)\)'
        match_uniform = re.search(pattern_uniform, content)
        if match_uniform:
            return np.array([float(x) for x in match_uniform.group(1).split()])
        return None

    field_type = match.group(1)
    n_values = int(match.group(2))
    data_str = match.group(3)

    if field_type == 'vector':
        # Parse vectors like (0.1 0.2 0.3)
        vectors = re.findall(r'\(([\d\.\-e\+]+)\s+([\d\.\-e\+]+)\s+([\d\.\-e\+]+)\)', data_str)
        return np.array([[float(x), float(y), float(z)] for x, y, z in vectors])
    else:
        # Parse scalars
        values = re.findall(r'([\d\.\-e\+]+)', data_str)
        return np.array([float(v) for v in values])


def extract_peak_velocity(openfoam_dir: Path, time: str = "0.2") -> Optional[float]:
    """Extract peak velocity magnitude from U field at given time.

    Args:
        openfoam_dir: Path to openfoam directory containing time folders
        time: Time directory to read (e.g., "0.2" for peak systole)

    Returns:
        Peak velocity magnitude in m/s, or None if not found
    """
    u_path = openfoam_dir / time / "U"
    U = parse_openfoam_field(u_path)

    if U is None:
        print(f"  Warning: Could not parse U field at {u_path}")
        return None

    # Calculate velocity magnitude
    U_mag = np.sqrt(np.sum(U**2, axis=1))
    return float(np.max(U_mag))


def extract_pressure_stats(openfoam_dir: Path, time: str = "0.2") -> Optional[Dict]:
    """Extract pressure statistics from p field.

    Args:
        openfoam_dir: Path to openfoam directory
        time: Time directory to read

    Returns:
        Dict with min, max, mean pressure in Pa
    """
    p_path = openfoam_dir / time / "p"
    p = parse_openfoam_field(p_path)

    if p is None:
        print(f"  Warning: Could not parse p field at {p_path}")
        return None

    # Note: OpenFOAM stores kinematic pressure (p/rho)
    # For blood, rho = 1060 kg/m^3
    rho = 1060.0
    p_pascals = p * rho

    return {
        'min': float(np.min(p_pascals)),
        'max': float(np.max(p_pascals)),
        'mean': float(np.mean(p_pascals)),
        'range': float(np.max(p_pascals) - np.min(p_pascals))
    }


def parse_checkmesh_log(log_path: Path) -> Optional[Dict]:
    """Parse checkMesh log for mesh statistics.

    Args:
        log_path: Path to log.checkMesh file

    Returns:
        Dict with cells, points, faces, and quality metrics
    """
    if not log_path.exists():
        return None

    with open(log_path, 'r') as f:
        content = f.read()

    stats = {}

    # Cell count
    match = re.search(r'cells:\s*(\d+)', content)
    if match:
        stats['cells'] = int(match.group(1))

    # Point count
    match = re.search(r'points:\s*(\d+)', content)
    if match:
        stats['points'] = int(match.group(1))

    # Non-orthogonality
    match = re.search(r'Mesh non-orthogonality Max:\s*([\d\.]+)\s*average:\s*([\d\.]+)', content)
    if match:
        stats['non_ortho_max'] = float(match.group(1))
        stats['non_ortho_avg'] = float(match.group(2))

    # Skewness
    match = re.search(r'Max skewness\s*=\s*([\d\.]+)', content)
    if match:
        stats['skewness_max'] = float(match.group(1))

    # Aspect ratio
    match = re.search(r'Max aspect ratio\s*=\s*([\d\.]+)', content)
    if match:
        stats['aspect_ratio_max'] = float(match.group(1))

    return stats


def extract_solver_runtime(log_path: Path) -> Optional[float]:
    """Extract total solver runtime from log.solver or log.foamRun.

    Args:
        log_path: Path to solver log file

    Returns:
        Runtime in seconds, or None if not found
    """
    if not log_path.exists():
        return None

    with open(log_path, 'r') as f:
        content = f.read()

    # Look for ExecutionTime
    matches = re.findall(r'ExecutionTime\s*=\s*([\d\.]+)\s*s', content)
    if matches:
        return float(matches[-1])  # Return last (final) execution time

    return None


def gci_calculation(phi_coarse: float, phi_medium: float, phi_fine: float,
                    r: float = 2.0, p: float = 2.0, Fs: float = 1.25) -> Dict:
    """Calculate Grid Convergence Index (GCI) using Richardson extrapolation.

    Args:
        phi_coarse: Quantity on coarse mesh
        phi_medium: Quantity on medium mesh
        phi_fine: Quantity on fine mesh
        r: Refinement ratio (default 2.0)
        p: Order of accuracy (default 2.0 for second-order schemes)
        Fs: Safety factor (default 1.25 for 3-mesh studies)

    Returns:
        Dict with GCI values, extrapolated value, observed order
    """
    # Calculate observed order of convergence
    eps32 = phi_medium - phi_coarse
    eps21 = phi_fine - phi_medium

    if abs(eps21) < 1e-15 or abs(eps32) < 1e-15:
        return {'error': 'Converged or non-monotonic'}

    # Observed order of accuracy
    p_obs = abs(np.log(abs(eps32 / eps21)) / np.log(r))

    # Richardson extrapolated value
    phi_ext = phi_fine + (phi_fine - phi_medium) / (r**p_obs - 1)

    # GCI (fine mesh)
    e_fine = abs((phi_fine - phi_medium) / phi_fine)
    gci_fine = Fs * e_fine / (r**p_obs - 1)

    # GCI (medium mesh)
    e_medium = abs((phi_medium - phi_coarse) / phi_medium)
    gci_medium = Fs * e_medium / (r**p_obs - 1)

    return {
        'phi_ext': phi_ext,
        'p_observed': p_obs,
        'gci_fine': gci_fine * 100,  # As percentage
        'gci_medium': gci_medium * 100,
        'asymptotic_ratio': gci_medium / (r**p_obs * gci_fine) if gci_fine > 0 else float('nan')
    }


def extract_physics_model_results(base_dir: Path, time: str = "0.2") -> Dict:
    """Extract results from laminar/rans/les simulations for Table 7.

    Args:
        base_dir: Path to output/BPM120/physics_model/
        time: Time to extract (peak systole)

    Returns:
        Dict with results for each physics model
    """
    results = {}

    for model in ['laminar', 'rans', 'les']:
        model_dir = base_dir / model / 'openfoam'
        print(f"\nProcessing {model}...")

        if not model_dir.exists():
            print(f"  Directory not found: {model_dir}")
            continue

        model_results = {}

        # Peak velocity
        v_max = extract_peak_velocity(model_dir, time)
        if v_max:
            model_results['v_max'] = v_max
            print(f"  Peak velocity: {v_max:.3f} m/s")

        # Pressure stats
        p_stats = extract_pressure_stats(model_dir, time)
        if p_stats:
            model_results['delta_p'] = p_stats['range']
            print(f"  Pressure range: {p_stats['range']:.1f} Pa")

        # Runtime
        log_solver = model_dir / 'logs' / 'log.solver'
        log_foamrun = model_dir / 'logs' / 'log.foamRun'
        runtime = extract_solver_runtime(log_solver) or extract_solver_runtime(log_foamrun)
        if runtime:
            model_results['runtime_sec'] = runtime
            model_results['runtime_min'] = runtime / 60
            print(f"  Runtime: {runtime/60:.1f} min")

        # Mesh stats
        checkmesh_log = model_dir / 'logs' / 'log.checkMesh'
        mesh_stats = parse_checkmesh_log(checkmesh_log)
        if mesh_stats:
            model_results['cells'] = mesh_stats.get('cells')
            print(f"  Cells: {mesh_stats.get('cells')}")

        results[model] = model_results

    return results


def main():
    """Main function to extract all paper results."""
    print("=" * 60)
    print("AortaCFD Paper Results Extraction")
    print("=" * 60)

    base_output = Path('/home/mchi4jw4/GitHub/AortaCFD-app/output')

    # Table 7: Physics model comparison
    print("\n" + "=" * 60)
    print("TABLE 7: Turbulence Model Comparison")
    print("=" * 60)

    physics_dir = base_output / 'BPM120' / 'physics_model'
    physics_results = extract_physics_model_results(physics_dir, time="0.2")

    print("\n--- Results Summary ---")
    print(f"{'Model':<10} {'v_max (m/s)':<12} {'ΔP (Pa)':<10} {'Runtime (min)':<15}")
    print("-" * 50)
    for model, data in physics_results.items():
        v = data.get('v_max', 'N/A')
        dp = data.get('delta_p', 'N/A')
        rt = data.get('runtime_min', 'N/A')
        v_str = f"{v:.3f}" if isinstance(v, float) else v
        dp_str = f"{dp:.1f}" if isinstance(dp, float) else dp
        rt_str = f"{rt:.1f}" if isinstance(rt, float) else rt
        print(f"{model:<10} {v_str:<12} {dp_str:<10} {rt_str:<15}")

    # Table 4: Mesh convergence
    print("\n" + "=" * 60)
    print("TABLE 4: Mesh Convergence Study")
    print("=" * 60)

    mesh_dir = base_output / 'BPM120' / 'config_mesh'
    mesh_levels = ['138k', '664k', '3m']

    print("\nMesh statistics:")
    for level in mesh_levels:
        checkmesh = mesh_dir / level / 'openfoam' / 'logs' / 'log.checkMesh'
        stats = parse_checkmesh_log(checkmesh)
        if stats:
            print(f"  {level}: {stats.get('cells', 'N/A')} cells, "
                  f"non-ortho max={stats.get('non_ortho_max', 'N/A')}, "
                  f"skewness={stats.get('skewness_max', 'N/A')}")

    print("\n" + "=" * 60)
    print("Extraction complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
