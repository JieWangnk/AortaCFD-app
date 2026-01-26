# src/inlet/mapping.py
"""
Inlet velocity mapping and boundary data writer.

Maps velocity profiles to mesh face centers and writes
OpenFOAM boundaryData format files.

Usage:
    from src.inlet.mapping import process_inlet, InletMapper

    # Simple interface
    cardiac_cycle = process_inlet(config, case_dir)

    # Advanced interface
    mapper = InletMapper(config, case_dir)
    mapper.read_mesh_points()
    mapper.calculate_velocities(flow_data)
    mapper.write_boundary_data()
"""

import os
import numpy as np
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from ..config.accessor import Config, wrap_config
from .profiles import create_profile, VelocityProfile
from .csv_reader import read_flow_csv, FlowData, flow_to_velocity

logger = logging.getLogger(__name__)


class InletMapper:
    """
    Maps velocity profiles to mesh points and writes boundary data.

    This class handles:
    1. Reading mesh face center points
    2. Determining inlet geometry (center, radius, normal)
    3. Applying velocity profiles at each timestep
    4. Writing OpenFOAM boundaryData format
    """

    def __init__(
        self,
        config: Union[Dict[str, Any], Config],
        case_dir: str,
    ):
        """
        Initialize inlet mapper.

        Args:
            config: Configuration dict or Config accessor
            case_dir: Path to OpenFOAM case directory
        """
        self.cfg = wrap_config(config)
        self.case_dir = case_dir

        # Inlet info
        self.inlet_name = self.cfg.inlet_patch_name
        self.inlet_center: Optional[np.ndarray] = None
        self.inlet_radius: Optional[float] = None
        self.inlet_normal: Optional[np.ndarray] = None
        self.inlet_area: Optional[float] = None

        # Mesh points
        self.points: Optional[np.ndarray] = None
        self.n_points: int = 0

        # Calculated velocities
        self.velocities: Dict[float, np.ndarray] = {}

    def read_mesh_points(self, points_file: Optional[str] = None) -> np.ndarray:
        """
        Read mesh face center points from file.

        Args:
            points_file: Path to points file (default: boundaryData/{inlet}/points)

        Returns:
            Array of points (N, 3)
        """
        if points_file is None:
            points_file = os.path.join(
                self.case_dir, "constant", "boundaryData",
                self.inlet_name, "points"
            )

        if not os.path.exists(points_file):
            raise FileNotFoundError(f"Points file not found: {points_file}")

        logger.info(f"Reading mesh points from {points_file}")

        points = _parse_points_file(points_file)
        self.points = points
        self.n_points = len(points)

        logger.info(f"Read {self.n_points} face center points")

        return points

    def calculate_inlet_geometry(
        self,
        stl_dir: Optional[str] = None,
    ) -> Tuple[np.ndarray, float, np.ndarray]:
        """
        Calculate inlet center, radius, and normal from STL or points.

        Args:
            stl_dir: Directory containing inlet STL file

        Returns:
            Tuple of (center, radius, normal)
        """
        if self.points is None:
            raise ValueError("Must read mesh points first")

        # Calculate from points
        self.inlet_center = np.mean(self.points, axis=0)

        # Radius: max distance from center
        distances = np.linalg.norm(self.points - self.inlet_center, axis=1)
        self.inlet_radius = np.max(distances)

        # Normal: fit plane to points
        self.inlet_normal = _fit_plane_normal(self.points)

        # Ensure normal points inward (positive velocity direction)
        # Convention: normal should point INTO the domain
        # This may need adjustment based on mesh orientation

        # Calculate area
        self.inlet_area = np.pi * self.inlet_radius ** 2

        logger.info(
            f"Inlet geometry: center={self.inlet_center}, "
            f"radius={self.inlet_radius:.6f}m, area={self.inlet_area:.6e}m²"
        )

        return self.inlet_center, self.inlet_radius, self.inlet_normal

    def calculate_velocities(
        self,
        flow_data: FlowData,
        profile_type: str = 'plug',
        timesteps: Optional[np.ndarray] = None,
    ) -> Dict[float, np.ndarray]:
        """
        Calculate velocities at all points for all timesteps.

        Args:
            flow_data: Flow waveform data
            profile_type: Velocity profile type
            timesteps: Specific timesteps to calculate (default: from flow_data)

        Returns:
            Dictionary mapping time -> velocity array
        """
        if self.points is None:
            raise ValueError("Must read mesh points first")
        if self.inlet_center is None:
            self.calculate_inlet_geometry()

        # Create velocity profile
        profile = create_profile(
            profile_type,
            self.inlet_center,
            self.inlet_radius,
            self.inlet_normal,
            nu=self.cfg.nu,
            cardiac_cycle=flow_data.cardiac_cycle,
        )

        # Determine timesteps
        if timesteps is None:
            timesteps = flow_data.times

        logger.info(
            f"Calculating velocities for {len(timesteps)} timesteps "
            f"with '{profile_type}' profile"
        )

        self.velocities = {}

        for t in timesteps:
            # Get flow rate at this time
            flow_rate = np.interp(t, flow_data.times, flow_data.values)

            # Convert to mean velocity
            mean_velocity = flow_to_velocity(flow_rate, self.inlet_area)

            # Calculate velocity at each point
            velocities = profile.calculate_batch(self.points, mean_velocity)
            self.velocities[t] = velocities

        return self.velocities

    def write_boundary_data(
        self,
        output_dir: Optional[str] = None,
    ) -> List[str]:
        """
        Write velocity data in OpenFOAM boundaryData format.

        Args:
            output_dir: Output directory (default: boundaryData/{inlet})

        Returns:
            List of written file paths
        """
        if not self.velocities:
            raise ValueError("Must calculate velocities first")

        if output_dir is None:
            output_dir = os.path.join(
                self.case_dir, "constant", "boundaryData", self.inlet_name
            )

        os.makedirs(output_dir, exist_ok=True)
        written_files = []

        logger.info(f"Writing boundary data to {output_dir}")

        for time, velocities in self.velocities.items():
            time_dir = os.path.join(output_dir, f"{time}")
            os.makedirs(time_dir, exist_ok=True)

            u_file = os.path.join(time_dir, "U")
            _write_velocity_file(u_file, velocities)
            written_files.append(u_file)

        logger.info(f"Wrote {len(written_files)} velocity files")

        return written_files


def process_inlet(
    config: Union[Dict[str, Any], Config],
    case_dir: str,
    csv_path: Optional[str] = None,
) -> float:
    """
    Process inlet boundary condition (high-level interface).

    This function:
    1. Reads the flow CSV file
    2. Reads mesh points
    3. Calculates inlet geometry
    4. Calculates velocities for each timestep
    5. Writes boundaryData files

    Args:
        config: Configuration dict or Config accessor
        case_dir: Path to OpenFOAM case directory
        csv_path: Path to CSV file (default: from config)

    Returns:
        Cardiac cycle duration (s)
    """
    cfg = wrap_config(config)

    # Get inlet settings
    inlet_config = cfg.inlet
    inlet_type = cfg.inlet_type

    if inlet_type == 'CONSTANT':
        logger.info("CONSTANT inlet type - no CSV processing needed")
        return 1.0  # Default cardiac cycle for steady

    # Find CSV file
    if csv_path is None:
        csv_file = inlet_config.get('csv_file', 'flow.csv')
        csv_path = _find_csv_file(csv_file, case_dir, cfg)

    # Read flow data
    data_type = inlet_config.get('data_type', 'flow_rate')
    flow_data = read_flow_csv(csv_path, data_type=data_type)

    # Create mapper
    mapper = InletMapper(cfg, case_dir)

    # Read mesh points
    mapper.read_mesh_points()

    # Calculate inlet geometry
    mapper.calculate_inlet_geometry()

    # Get profile type
    profile_type = inlet_config.get('profile', 'plug')

    # Calculate velocities
    mapper.calculate_velocities(flow_data, profile_type)

    # Write boundary data
    mapper.write_boundary_data()

    return flow_data.cardiac_cycle


def write_boundary_data(
    output_dir: str,
    times: np.ndarray,
    velocities: Dict[float, np.ndarray],
) -> List[str]:
    """
    Write velocity boundary data to files.

    Args:
        output_dir: Output directory
        times: Array of timesteps
        velocities: Dictionary mapping time -> velocity array (N, 3)

    Returns:
        List of written file paths
    """
    os.makedirs(output_dir, exist_ok=True)
    written_files = []

    for t in times:
        if t not in velocities:
            continue

        time_dir = os.path.join(output_dir, f"{t}")
        os.makedirs(time_dir, exist_ok=True)

        u_file = os.path.join(time_dir, "U")
        _write_velocity_file(u_file, velocities[t])
        written_files.append(u_file)

    return written_files


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _parse_points_file(points_file: str) -> np.ndarray:
    """
    Parse OpenFOAM points file format.

    Format:
    N
    (
    (x1 y1 z1)
    (x2 y2 z2)
    ...
    )

    Args:
        points_file: Path to points file

    Returns:
        Array of points (N, 3)
    """
    with open(points_file, 'r') as f:
        content = f.read()

    points = []

    # Find all (x y z) tuples
    import re
    pattern = r'\(\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s*\)'
    matches = re.findall(pattern, content)

    for match in matches:
        x, y, z = float(match[0]), float(match[1]), float(match[2])
        points.append([x, y, z])

    return np.array(points)


def _fit_plane_normal(points: np.ndarray) -> np.ndarray:
    """
    Fit a plane to points and return normal vector.

    Uses SVD to find the best-fit plane.

    Args:
        points: Array of points (N, 3)

    Returns:
        Unit normal vector (3,)
    """
    # Center the points
    centroid = np.mean(points, axis=0)
    centered = points - centroid

    # SVD
    _, _, vh = np.linalg.svd(centered)

    # Normal is the last row of vh (smallest singular value)
    normal = vh[-1]

    # Normalize
    return normal / np.linalg.norm(normal)


def _write_velocity_file(filepath: str, velocities: np.ndarray) -> None:
    """
    Write velocity data in OpenFOAM format.

    Args:
        filepath: Output file path
        velocities: Velocity array (N, 3)
    """
    n_points = len(velocities)

    with open(filepath, 'w') as f:
        # Header
        f.write("// Velocity field for inlet boundary\n")
        f.write(f"{n_points}\n")
        f.write("(\n")

        # Write velocities
        for v in velocities:
            f.write(f"({v[0]:.10e} {v[1]:.10e} {v[2]:.10e})\n")

        f.write(")\n")


def _find_csv_file(
    csv_filename: str,
    case_dir: str,
    cfg: Config,
) -> str:
    """
    Find the CSV file in various locations.

    Search order:
    1. boundaryData/{inlet}/
    2. Case directory
    3. cases_input/{case_name}/

    Args:
        csv_filename: CSV filename
        case_dir: Case directory path
        cfg: Config accessor

    Returns:
        Path to CSV file

    Raises:
        FileNotFoundError: If CSV not found
    """
    inlet_name = cfg.inlet_patch_name
    case_name = cfg.case_name

    # Search locations
    search_paths = [
        os.path.join(case_dir, "constant", "boundaryData", inlet_name, csv_filename),
        os.path.join(case_dir, csv_filename),
        os.path.join("cases_input", case_name, csv_filename),
    ]

    for path in search_paths:
        if os.path.exists(path):
            logger.debug(f"Found CSV at: {path}")
            return path

    raise FileNotFoundError(
        f"CSV file '{csv_filename}' not found in: {search_paths}"
    )
