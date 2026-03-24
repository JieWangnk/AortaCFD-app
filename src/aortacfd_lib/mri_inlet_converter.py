"""Convert 4D MRI inlet velocity data to OpenFOAM boundaryData format.

Supports two input formats:

1. CSV files (primary — what MRI processing tools export):
       points.csv   — N rows × 3 cols (x, y, z coordinates)
       Ux.csv       — N rows × T cols (x-velocity at each timestep)
       Uy.csv       — N rows × T cols (y-velocity at each timestep)
       Uz.csv       — N rows × T cols (z-velocity at each timestep)

2. Sequential OpenFOAM files (legacy — post-processed data):
       points       — OpenFOAM vectorField
       U1, U2, ...  — OpenFOAM vectorAverageField

Output (OpenFOAM boundaryData format used by timeVaryingMappedFixedValue):
    inlet/
        points          — OpenFOAM vectorField (face center coordinates)
        0.000000/U      — bare format (n_points + velocity vectors)
        0.001000/U
        ...

Usage:
    # From CSV files (primary workflow)
    python mri_inlet_converter.py csv \\
        --points points.csv --ux Ux.csv --uy Uy.csv --uz Uz.csv \\
        --output inlet/ --dt 0.001 --points-scale 0.001

    # From sequential OpenFOAM files (legacy)
    python mri_inlet_converter.py openfoam \\
        --source InletData_OF4_BL_95/ --output inlet/ --dt 0.001
"""

import os
import re
import shutil
import logging

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def _write_points_file(filepath: str, points: np.ndarray) -> None:
    """Write points in bare OpenFOAM boundaryData format (no FoamFile header)."""
    n = len(points)
    lines = [str(n), '(']
    lines.extend(f'({p[0]:.6g} {p[1]:.6g} {p[2]:.6g})' for p in points)
    lines.append(')')
    with open(filepath, 'w') as f:
        f.write('\n'.join(lines) + '\n')


def _write_velocity_file(filepath: str, velocities: np.ndarray) -> None:
    """Write velocity vectors in bare OpenFOAM boundaryData format."""
    n = len(velocities)
    lines = [str(n), '(']
    lines.extend(f'({v[0]:.6g} {v[1]:.6g} {v[2]:.6g})' for v in velocities)
    lines.append(')')
    with open(filepath, 'w') as f:
        f.write('\n'.join(lines) + '\n')


# ---------------------------------------------------------------------------
# CSV input (primary)
# ---------------------------------------------------------------------------

def convert_csv_to_timedirs(
    points_csv: str,
    ux_csv: str,
    uy_csv: str,
    uz_csv: str,
    output_dir: str,
    dt: float = 0.001,
    points_scale: float = 1.0,
) -> dict:
    """Convert CSV-based MRI inlet data to OpenFOAM boundaryData format.

    This is the primary conversion path. Users export CSV files from their
    MRI processing tool (GTFlow, Segment, CVI42, custom MATLAB, etc.).

    Args:
        points_csv: Path to points CSV (N rows × 3 cols: x, y, z).
        ux_csv: Path to Ux CSV (N rows × T cols).
        uy_csv: Path to Uy CSV (N rows × T cols).
        uz_csv: Path to Uz CSV (N rows × T cols).
        output_dir: Output directory for time-directory structure.
        dt: Time step between columns in seconds.
        points_scale: Scale factor for point coordinates (e.g., 0.001 for mm→m).

    Returns:
        dict with conversion summary.
    """
    logger.info("Loading CSV files...")
    points = np.loadtxt(points_csv, delimiter=',')
    ux = np.loadtxt(ux_csv, delimiter=',')
    uy = np.loadtxt(uy_csv, delimiter=',')
    uz = np.loadtxt(uz_csv, delimiter=',')

    n_points = points.shape[0]
    n_timesteps = ux.shape[1]

    # Validate shapes
    if points.shape != (n_points, 3):
        raise ValueError(f"points CSV must be N×3, got {points.shape}")
    if ux.shape != (n_points, n_timesteps):
        raise ValueError(f"Ux shape {ux.shape} doesn't match points ({n_points}) or timesteps")
    if uy.shape != (n_points, n_timesteps):
        raise ValueError(f"Uy shape {uy.shape} doesn't match Ux shape {ux.shape}")
    if uz.shape != (n_points, n_timesteps):
        raise ValueError(f"Uz shape {uz.shape} doesn't match Ux shape {ux.shape}")

    cardiac_cycle = (n_timesteps - 1) * dt
    logger.info(f"Inlet: {n_points} points, {n_timesteps} timesteps, cardiac cycle = {cardiac_cycle}s")

    # Scale points to meters
    if points_scale != 1.0:
        points = points * points_scale
        logger.info(f"Scaled points by {points_scale} (now in meters)")

    # Velocity statistics
    speed = np.sqrt(ux**2 + uy**2 + uz**2)
    logger.info(f"Velocity range: {speed.min():.4f} - {speed.max():.4f} m/s")
    logger.info(f"Mean velocity:  {speed.mean():.4f} m/s")

    # Create output
    os.makedirs(output_dir, exist_ok=True)

    # Write points file
    _write_points_file(os.path.join(output_dir, 'points'), points)
    logger.info("Wrote points file")

    # Write velocity files for each timestep
    for t_idx in range(n_timesteps):
        time_val = t_idx * dt
        time_str = f"{time_val:.6f}"
        time_dir = os.path.join(output_dir, time_str)
        os.makedirs(time_dir, exist_ok=True)

        velocities = np.column_stack([ux[:, t_idx], uy[:, t_idx], uz[:, t_idx]])
        _write_velocity_file(os.path.join(time_dir, 'U'), velocities)

    logger.info(f"Wrote {n_timesteps} time directories to {output_dir}")

    return {
        'n_timesteps': n_timesteps,
        'cardiac_cycle': cardiac_cycle,
        'n_points': n_points,
        'dt': dt,
        'points_scale': points_scale,
        'output_dir': output_dir,
    }


# ---------------------------------------------------------------------------
# Sequential OpenFOAM input (legacy)
# ---------------------------------------------------------------------------

def _parse_openfoam_velocity_file(filepath: str) -> str:
    """Parse vectorAverageField file, strip header, return bare content."""
    with open(filepath, 'r') as f:
        lines = f.readlines()

    # Find the point count line: first line that is just a number
    for i, line in enumerate(lines):
        if line.strip().isdigit():
            return ''.join(lines[i:])

    raise ValueError(f"Could not find point count in {filepath}")


def convert_sequential_to_timedirs(
    source_dir: str,
    output_dir: str,
    dt: float = 0.001,
    file_prefix: str = 'U',
) -> dict:
    """Convert sequential OpenFOAM U files to time-directory format.

    For legacy data already in OpenFOAM vectorAverageField format (U1, U2, ...).

    Args:
        source_dir: Directory containing points + U1, U2, ... UN files.
        output_dir: Output directory for time-directory structure.
        dt: Time step between consecutive files (seconds).
        file_prefix: Prefix of velocity files (default 'U').

    Returns:
        dict with conversion summary.
    """
    if not os.path.isdir(source_dir):
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    # Discover U<n> files
    pattern = re.compile(rf'^{re.escape(file_prefix)}(\d+)$')
    u_files = {}
    for name in os.listdir(source_dir):
        match = pattern.match(name)
        if match:
            u_files[int(match.group(1))] = name

    if not u_files:
        raise ValueError(f"No {file_prefix}<n> files found in {source_dir}")

    indices = sorted(u_files.keys())
    n_timesteps = len(indices)
    cardiac_cycle = (indices[-1] - 1) * dt
    logger.info(f"Found {n_timesteps} velocity files ({file_prefix}{indices[0]}-{file_prefix}{indices[-1]})")
    logger.info(f"Time step: {dt}s, cardiac cycle: {cardiac_cycle}s")

    os.makedirs(output_dir, exist_ok=True)

    # Copy points file, stripping any FoamFile header to bare format
    points_src = os.path.join(source_dir, 'points')
    if os.path.exists(points_src):
        bare_content = _parse_openfoam_velocity_file(points_src)
        with open(os.path.join(output_dir, 'points'), 'w') as f:
            f.write(bare_content)
        logger.info("Copied points file (stripped header to bare format)")
    else:
        logger.warning("No points file found in source directory")

    # Convert each U file
    n_points = None
    for idx in indices:
        time_val = (idx - 1) * dt
        time_str = f"{time_val:.6f}"
        time_dir = os.path.join(output_dir, time_str)
        os.makedirs(time_dir, exist_ok=True)

        src_file = os.path.join(source_dir, u_files[idx])
        bare_content = _parse_openfoam_velocity_file(src_file)

        if n_points is None:
            n_points = int(bare_content.split('\n', 1)[0].strip())
            logger.info(f"Inlet has {n_points} points")

        with open(os.path.join(time_dir, 'U'), 'w') as f:
            f.write(bare_content)

    logger.info(f"Converted {n_timesteps} files to {output_dir}")

    return {
        'n_timesteps': n_timesteps,
        'cardiac_cycle': cardiac_cycle,
        'n_points': n_points,
        'dt': dt,
        'output_dir': output_dir,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import argparse

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    parser = argparse.ArgumentParser(
        description='Convert 4D MRI inlet velocity data to OpenFOAM boundaryData format'
    )
    subparsers = parser.add_subparsers(dest='mode', required=True)

    # CSV mode
    csv_parser = subparsers.add_parser('csv', help='Convert from CSV files (primary workflow)')
    csv_parser.add_argument('--points', required=True, help='Points CSV (N×3: x, y, z)')
    csv_parser.add_argument('--ux', required=True, help='Ux velocity CSV (N×T)')
    csv_parser.add_argument('--uy', required=True, help='Uy velocity CSV (N×T)')
    csv_parser.add_argument('--uz', required=True, help='Uz velocity CSV (N×T)')
    csv_parser.add_argument('--output', required=True, help='Output directory')
    csv_parser.add_argument('--dt', type=float, default=0.001,
                            help='Time step between columns in seconds (default: 0.001)')
    csv_parser.add_argument('--points-scale', type=float, default=1.0,
                            help='Scale factor for point coordinates, e.g. 0.001 for mm→m (default: 1.0)')

    # OpenFOAM sequential mode
    of_parser = subparsers.add_parser('openfoam', help='Convert from sequential OpenFOAM files (legacy)')
    of_parser.add_argument('--source', required=True, help='Directory with points + U1, U2, ... files')
    of_parser.add_argument('--output', required=True, help='Output directory')
    of_parser.add_argument('--dt', type=float, default=0.001,
                            help='Time step between files in seconds (default: 0.001)')
    of_parser.add_argument('--prefix', default='U',
                            help='Velocity file prefix (default: U)')

    args = parser.parse_args()

    if args.mode == 'csv':
        result = convert_csv_to_timedirs(
            points_csv=args.points,
            ux_csv=args.ux,
            uy_csv=args.uy,
            uz_csv=args.uz,
            output_dir=args.output,
            dt=args.dt,
            points_scale=args.points_scale,
        )
    elif args.mode == 'openfoam':
        result = convert_sequential_to_timedirs(
            source_dir=args.source,
            output_dir=args.output,
            dt=args.dt,
            file_prefix=args.prefix,
        )

    print(f"\nConversion complete:")
    print(f"  Timesteps:     {result['n_timesteps']}")
    print(f"  Points:        {result['n_points']}")
    print(f"  Cardiac cycle: {result['cardiac_cycle']}s")
    if 'points_scale' in result:
        print(f"  Points scale:  {result['points_scale']}")
    print(f"  Output:        {result['output_dir']}")
