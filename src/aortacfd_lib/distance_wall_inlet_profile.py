"""
Distance-to-Wall Inlet Profile Generator
=========================================

When 4D-MRI data is unavailable and the aortic root is highly irregular (e.g., due to
valve leaflets), standard parabolic or elliptical Poiseuille profiles are inappropriate.
This module implements a distance-to-wall-based synthetic profile that:
- Enforces no-slip condition at walls
- Preserves the measured flow rate Q(t)
- Works with any irregular inlet shape

Procedure (following OpenFOAM convention)
-----------------------------------------
1. Compute distance field d(x_i) from each inlet face centre to nearest wall edge
2. Determine d_max (maximum distance across the patch)
3. Define shape function f(d) satisfying f(0)=0 and f(d_max)=1
4. Scale to match measured flow rate: U_0(t) = Q(t) / sum(f(d_i) * dA_i)
5. Assign velocity: u(x_i, t) = U_0(t) * f(d(x_i)) * n_inlet

Shape Function Options
----------------------
- Power law:     f(d) = (d/d_max)^n   [n=1: linear, n=2: quadratic, n=1/7: turbulent]
- Poiseuille:    f(d) = 1 - (1 - d/d_max)^2   [equivalent to parabolic]
- Hybrid jet:    Flat core + near-wall decay
- Blunted:       Flat core + parabolic near-wall

Output Format
-------------
Creates boundaryData/<inlet>/<time>/U files for use with timeVaryingMappedFixedValue BC.

Author: Jie Wang
Date: November 2025
"""

import os
import shutil
import numpy as np
from typing import Tuple, List, Optional
from enum import Enum

try:
    from scipy.spatial import cKDTree

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from .utils.logger import Logger
from .utils.patch_processing import PatchProcessing


class ShapeFunction(Enum):
    """Available shape function types."""

    POWER_LAW = "power_law"  # f(d) = (d/d_max)^n
    POISEUILLE = "poiseuille"  # f(d) = 1 - (1 - d/d_max)^2
    HYBRID_JET = "hybrid_jet"  # Flat core + wall decay
    BLUNTED_PARABOLIC = "blunted"  # Flat core + parabolic wall


class DistanceWallInletProfile:
    """
    Generate inlet velocity profiles based on distance-to-wall field.

    This class computes velocity profiles for irregular inlet geometries where
    standard circular/elliptical assumptions don't apply. The profile is derived
    from the distance of each face centre to the nearest wall edge, ensuring
    zero velocity at walls and correct total flow rate.

    Parameters
    ----------
    config : dict
        Configuration with inlet, geometry, and physics settings.
    case_directory : str
        Path to OpenFOAM case directory.

    Example
    -------
    >>> config = {
    ...     'inlet': {
    ...         'csv_file': 'flow.csv',
    ...         'data_type': 'flowrate',
    ...         'profile': 'distance_wall',
    ...         'exponent': 2.0  # Quadratic profile
    ...     },
    ...     'geometry': {'inlet_keywords_ordered': 'inlet'}
    ... }
    >>> generator = DistanceWallInletProfile(config, '/path/to/case')
    >>> generator.run()

    NOTE: STL files in constant/triSurface/ are PRE-SCALED to meters during case setup.
    No scale_factor needed - all geometry values are in SI units (meters).
    """

    def __init__(self, config: dict, case_directory: str):
        self.config = config
        self.case_directory = case_directory
        self.log = Logger("distance_wall_inlet").get_logger()

        # Extract settings
        # Support both config structures: boundary_conditions.inlet or inlet
        self.inlet_settings = config.get("boundary_conditions", {}).get("inlet") or config.get("inlet", {})
        self.geom_settings = config.get("geometry", {})
        self.phys_settings = config.get("physics", {})

        # Inlet identification
        self.inlet_name = self.geom_settings.get("inlet_keywords_ordered", "inlet")
        self.inlet_data_file = self.inlet_settings.get("csv_file", "flow.csv")
        self.data_type = self.inlet_settings.get("data_type", "flowrate").lower().strip()

        # Shape function settings
        # Default to power_law so that 'exponent' parameter is actually used
        shape_str = self.inlet_settings.get("shape_function", "power_law").lower()
        self.shape_function = self._parse_shape_function(shape_str)
        self.exponent = float(self.inlet_settings.get("exponent", 2.0))
        self.core_fraction = float(self.inlet_settings.get("core_fraction", 0.3))

        # Orientation
        self.orientation = self.inlet_settings.get("orientation", "auto").lower().strip()

        # Geometry data (computed during run)
        self.inlet_normal = None
        self.center = None
        self.d_max = None
        self.area = None
        self.face_areas = None
        self.cardiac_cycle = None

        self.log.info("DistanceWallInletProfile initialized")
        self.log.info(f"  Shape function: {self.shape_function.value}, exponent: {self.exponent}")

    def _parse_shape_function(self, shape_str: str) -> ShapeFunction:
        """Parse shape function string to enum."""
        mapping = {
            "power_law": ShapeFunction.POWER_LAW,
            "power": ShapeFunction.POWER_LAW,
            "linear": ShapeFunction.POWER_LAW,
            "poiseuille": ShapeFunction.POISEUILLE,
            "parabolic": ShapeFunction.POISEUILLE,
            "hybrid": ShapeFunction.HYBRID_JET,
            "hybrid_jet": ShapeFunction.HYBRID_JET,
            "blunted": ShapeFunction.BLUNTED_PARABOLIC,
            "blunted_parabolic": ShapeFunction.BLUNTED_PARABOLIC,
        }
        return mapping.get(shape_str, ShapeFunction.POISEUILLE)

    def run(self) -> None:
        """
        Main execution method for TIME-VARYING inlet.

        Steps:
        1. Load inlet geometry and compute basic properties
        2. Calculate distance-to-wall for each face centre
        3. Read time-series flow data from CSV
        4. For each timestep, compute velocity field and write to boundaryData
        """
        self.log.info("=" * 60)
        self.log.info("Distance-to-Wall Inlet Profile Generation")
        self.log.info("=" * 60)

        # Step 1: Load inlet geometry
        self._load_inlet_geometry()

        # Step 2: Read mesh points from boundaryData
        points_file = os.path.join(self.case_directory, "constant", "boundaryData", self.inlet_name, "points")
        if not os.path.isfile(points_file):
            raise FileNotFoundError(f"Points file not found: {points_file}")

        n_points, points = self._read_points_file(points_file)
        self.log.info(f"Read {n_points} face centres from boundaryData")

        # Step 3: Calculate distance-to-wall for each point
        distances = self._calculate_wall_distances(points)
        self.d_max = np.max(distances)
        self.log.info(f"Distance range: [0, {self.d_max:.6f}] m")

        # Estimate face areas (assume uniform if not available)
        self.face_areas = np.full(n_points, self.area / n_points)

        # Step 4: Read CSV flow data
        csv_path = os.path.join(self.case_directory, "constant", "boundaryData", self.inlet_name, self.inlet_data_file)
        if not os.path.isfile(csv_path):
            raise FileNotFoundError(f"Inlet CSV not found: {csv_path}")

        times, values, self.cardiac_cycle = self._read_csv_file(csv_path)
        self.log.info(f"Read {len(times)} timesteps, cardiac cycle: {self.cardiac_cycle:.4f}s")

        # Step 5: Clean old time directories
        parent_dir = os.path.join(self.case_directory, "constant", "boundaryData", self.inlet_name)
        self._clean_time_directories(parent_dir)

        # Step 6: Generate velocity for each timestep
        self.log.info("Generating velocity profiles...")
        self._generate_time_data(parent_dir, times, values, n_points, distances)

        self.log.info("=" * 60)
        self.log.info("Distance-to-Wall Profile Generation Complete")
        self.log.info("=" * 60)

    def run_constant(self, flow_rate_m3s: float) -> None:
        """
        Generate wall-distance profile for CONSTANT inlet (single timestep at t=0).

        This method creates boundaryData for use with timeVaryingMappedFixedValue BC,
        but with a single constant timestep. This allows CONSTANT inlets to use
        non-uniform profiles like wall_distance.

        Parameters
        ----------
        flow_rate_m3s : float
            Constant flow rate in m³/s. If negative, flow direction will be
            determined automatically based on outlet positions.

        Steps:
        1. Load inlet geometry
        2. Calculate distance-to-wall for each face centre
        3. Compute shape factors and scale to target flow rate
        4. Write single timestep (t=0) to boundaryData
        """
        self.log.info("=" * 60)
        self.log.info("Distance-to-Wall Profile (CONSTANT inlet)")
        self.log.info("=" * 60)

        # Step 1: Load inlet geometry
        self._load_inlet_geometry()

        # Step 2: Read mesh points from boundaryData
        points_file = os.path.join(self.case_directory, "constant", "boundaryData", self.inlet_name, "points")
        if not os.path.isfile(points_file):
            raise FileNotFoundError(f"Points file not found: {points_file}")

        n_points, points = self._read_points_file(points_file)
        self.log.info(f"Read {n_points} face centres from boundaryData")

        # Step 3: Calculate distance-to-wall for each point
        distances = self._calculate_wall_distances(points)
        self.d_max = np.max(distances)
        self.log.info(f"Distance range: [0, {self.d_max:.6f}] m")

        # Estimate face areas (assume uniform if not available)
        self.face_areas = np.full(n_points, self.area / n_points)

        # Step 4: Clean old time directories
        parent_dir = os.path.join(self.case_directory, "constant", "boundaryData", self.inlet_name)
        self._clean_time_directories(parent_dir)

        # Step 5: Generate single timestep at t=0
        self.log.info("Generating constant wall-distance profile...")
        self.log.info(f"  Target flow rate: {flow_rate_m3s:.6e} m³/s ({abs(flow_rate_m3s)*60*1000:.2f} L/min)")

        # Generate velocity data for t=0
        self._generate_constant_data(parent_dir, flow_rate_m3s, n_points, distances)

        self.log.info("=" * 60)
        self.log.info("Constant Wall-Distance Profile Generation Complete")
        self.log.info("=" * 60)

    def _generate_constant_data(
        self, parent_dir: str, flow_rate_m3s: float, n_points: int, distances: np.ndarray
    ) -> None:
        """Generate velocity data for constant inlet (single timestep at t=0)."""
        # Determine normal direction
        normal = self.inlet_normal.copy()
        if self.orientation == "in" or (self.orientation == "auto" and self._should_flip_normal()):
            normal = -normal
            self.log.info("Using inward-pointing normal")

        # Pre-compute shape factors (vectorized)
        shape_factors = self._compute_shape_factors_vectorized(distances)

        # Pre-compute the integrated shape*area
        integrated_shape_area = np.sum(shape_factors * self.face_areas)
        if integrated_shape_area <= 0:
            self.log.warning("Integrated shape*area is zero, using uniform profile")
            integrated_shape_area = self.area
            shape_factors = np.ones(n_points)

        # Calculate U_0 to match target flow rate
        U_0 = abs(flow_rate_m3s) / integrated_shape_area

        # Calculate velocities: U_0 * shape_factors * normal
        velocity_directions = np.outer(shape_factors, normal)
        velocities = U_0 * velocity_directions

        # Statistics
        avg_vel = U_0 * np.mean(shape_factors)
        max_vel = U_0 * np.max(shape_factors)
        self.log.info(f"  U_avg: {avg_vel:.4f} m/s, U_max: {max_vel:.4f} m/s")

        # Write to t=0 directory
        time_dir = os.path.join(parent_dir, "0.000000")
        os.makedirs(time_dir, exist_ok=True)
        self._write_velocity_file_fast(os.path.join(time_dir, "U"), velocities)
        self.log.info(f"  Wrote velocity data to {time_dir}/U")

    def _load_inlet_geometry(self) -> None:
        """Load inlet STL and calculate geometry properties.

        NOTE: STL files are PRE-SCALED to meters during case setup.
        No scale_factor needed - values returned directly in SI units.
        """
        tri_surface_dir = os.path.join(self.case_directory, "constant", "triSurface")

        patch_proc = PatchProcessing(tri_surface_dir, self.inlet_name)
        self.center, _, self.inlet_normal = patch_proc.calculate_inlet_center_radius()
        self.area = patch_proc.calculate_surface_area()

        self.log.info(f"Inlet centre: {self.center}")
        self.log.info(f"Inlet area: {self.area:.6e} m²")
        self.log.info(f"Inlet normal: {self.inlet_normal}")

    def _calculate_wall_distances(self, points: np.ndarray) -> np.ndarray:
        """
        Calculate distance from each face centre to nearest wall edge.

        This uses the inlet patch boundary (extracted from STL) as the "wall".
        Each face centre's distance to this boundary defines its d value.

        Parameters
        ----------
        points : np.ndarray
            Face centre coordinates (N, 3).

        Returns
        -------
        np.ndarray
            Distance to wall for each point (N,).
        """
        n_points = len(points)

        # Try to get boundary points from STL
        wall_points = self._extract_inlet_boundary()

        if wall_points is not None and len(wall_points) > 0:
            self.log.info(f"Using {len(wall_points)} boundary points for distance calculation")

            # Use KDTree for fast nearest-neighbor lookup: O(N log M) instead of O(N*M)
            if HAS_SCIPY:
                tree = cKDTree(wall_points)
                distances, _ = tree.query(points, k=1)
                self.log.debug(f"KDTree distance calculation completed for {n_points} points")
            else:
                # Fallback to vectorized numpy (still faster than pure loop)
                self.log.warning("scipy not available, using vectorized fallback (slower)")
                distances = np.array([np.min(np.linalg.norm(wall_points - pt, axis=1)) for pt in points])
        else:
            # Fallback: radial distance from centre
            self.log.info("Using radial distance approximation")
            distances_from_center = np.linalg.norm(points - self.center, axis=1)
            max_radius = np.max(distances_from_center)
            distances = max_radius - distances_from_center
            distances = np.maximum(distances, 0)

        return distances

    def _extract_inlet_boundary(self) -> Optional[np.ndarray]:
        """Extract boundary edge points from inlet STL.

        NOTE: STL files are PRE-SCALED to meters during case setup.
        No additional scaling needed.

        Returns vertices that lie on the boundary (open edges) of the mesh.
        Boundary edges are edges that belong to only one triangle face.
        """
        try:
            import trimesh
            from collections import Counter

            inlet_stl = os.path.join(self.case_directory, "constant", "triSurface", f"{self.inlet_name}.stl")
            if not os.path.isfile(inlet_stl):
                return None

            # STL is already in meters, no scaling needed
            mesh = trimesh.load(inlet_stl)

            # Find boundary edges (edges that appear only once = open boundary)
            # Each face contributes 3 edges
            edges = []
            for face in mesh.faces:
                edges.append(tuple(sorted([face[0], face[1]])))
                edges.append(tuple(sorted([face[1], face[2]])))
                edges.append(tuple(sorted([face[2], face[0]])))

            edge_counts = Counter(edges)
            boundary_edges = [e for e, count in edge_counts.items() if count == 1]

            if boundary_edges:
                # Get unique boundary vertex indices
                boundary_vertex_indices = set()
                for e in boundary_edges:
                    boundary_vertex_indices.add(e[0])
                    boundary_vertex_indices.add(e[1])

                boundary_vertices = mesh.vertices[list(boundary_vertex_indices)]
                self.log.debug(
                    f"Found {len(boundary_vertices)} boundary vertices from {len(boundary_edges)} boundary edges"
                )
                return boundary_vertices
            else:
                # Fallback: use peripheral vertices (mesh may be closed/watertight)
                self.log.warning("No boundary edges found, using peripheral vertex fallback")
                vertices = mesh.vertices
                distances_from_center = np.linalg.norm(vertices - self.center, axis=1)
                max_dist = np.max(distances_from_center)
                threshold = 0.85 * max_dist
                return vertices[distances_from_center > threshold]

        except ImportError:
            self.log.warning("trimesh not available, using radial approximation")
            return None
        except Exception as e:
            self.log.warning(f"Could not extract boundary: {e}")
            return None

    def _compute_shape_factor(self, d: float) -> float:
        """
        Compute shape factor f(d) for given distance.

        Shape function satisfies f(0) = 0 (at wall) and f(d_max) = 1 (at centre).

        Parameters
        ----------
        d : float
            Distance from point to wall.

        Returns
        -------
        float
            Shape factor in [0, 1].
        """
        if self.d_max <= 0:
            return 1.0

        d_norm = min(d / self.d_max, 1.0)

        if self.shape_function == ShapeFunction.POWER_LAW:
            # f(d) = (d/d_max)^n
            return d_norm**self.exponent

        elif self.shape_function == ShapeFunction.POISEUILLE:
            # f(d) = 1 - (1 - d/d_max)^2 = 1 - r_norm^2
            r_norm = 1.0 - d_norm
            return max(0, 1.0 - r_norm**2)

        elif self.shape_function == ShapeFunction.HYBRID_JET:
            # Flat core (f=1) for d > core_fraction * d_max
            # Power decay near wall
            core_dist = self.core_fraction * self.d_max
            if d >= core_dist:
                return 1.0
            else:
                return (d / core_dist) ** self.exponent

        elif self.shape_function == ShapeFunction.BLUNTED_PARABOLIC:
            # Flat core + parabolic near wall
            core_dist = self.core_fraction * self.d_max
            if d >= core_dist:
                return 1.0
            else:
                local_r = 1.0 - (d / core_dist)
                return max(0, 1.0 - local_r**2)

        else:
            # Default Poiseuille
            r_norm = 1.0 - d_norm
            return max(0, 1.0 - r_norm**2)

    def _calculate_scaling_factor(self, distances: np.ndarray, target_flow_rate: float) -> float:
        """
        Calculate U_0 to match target flow rate.

        Q(t) = sum_i f(d_i) * U_0(t) * dA_i
        => U_0(t) = Q(t) / sum_i (f(d_i) * dA_i)

        Parameters
        ----------
        distances : np.ndarray
            Distance to wall for each face.
        target_flow_rate : float
            Target volumetric flow rate (m³/s).

        Returns
        -------
        float
            Scaling velocity U_0.
        """
        shape_factors = np.array([self._compute_shape_factor(d) for d in distances])
        integrated = np.sum(shape_factors * self.face_areas)

        if integrated <= 0:
            self.log.warning("Integrated shape*area is zero, using average velocity")
            return abs(target_flow_rate) / self.area

        return abs(target_flow_rate) / integrated

    def _generate_time_data(
        self, parent_dir: str, times: np.ndarray, values: np.ndarray, n_points: int, distances: np.ndarray
    ) -> None:
        """Generate velocity data for each timestep (optimized vectorized version)."""
        # Determine normal direction
        normal = self.inlet_normal.copy()
        if self.orientation == "in" or (self.orientation == "auto" and self._should_flip_normal()):
            normal = -normal
            self.log.info("Using inward-pointing normal")

        # Pre-compute shape factors (vectorized)
        shape_factors = self._compute_shape_factors_vectorized(distances)

        # Pre-compute the integrated shape*area (constant for all timesteps)
        integrated_shape_area = np.sum(shape_factors * self.face_areas)
        if integrated_shape_area <= 0:
            self.log.warning("Integrated shape*area is zero, using uniform profile")
            integrated_shape_area = self.area
            shape_factors = np.ones(n_points)

        # Convert all flow rates at once (vectorized)
        if self.data_type == "velocity":
            flow_rates = values * self.area
        else:
            # Check if values are in L/min (magnitude > 1) or m³/s
            if np.max(np.abs(values)) > 1.0:
                flow_rates = values * 1e-3 / 60.0  # L/min -> m³/s
            else:
                flow_rates = values  # Already m³/s

        # Calculate all U_0 values at once
        U_0_all = np.abs(flow_rates) / integrated_shape_area

        # Pre-compute the velocity direction vectors (shape_factor * normal for each point)
        # This is (n_points, 3) array
        velocity_directions = np.outer(shape_factors, normal)

        self.log.info(f"Writing {len(times)} timesteps...")

        # Generate all timesteps
        for i, t in enumerate(times):
            U_0 = U_0_all[i]

            # Vectorized velocity calculation: velocities = U_0 * shape_factors[:, None] * normal
            velocities = U_0 * velocity_directions

            # Write to file
            time_dir = os.path.join(parent_dir, f"{t:.6f}")
            os.makedirs(time_dir, exist_ok=True)
            self._write_velocity_file_fast(os.path.join(time_dir, "U"), velocities)

            # Progress update every 10%
            if i % max(1, len(times) // 10) == 0:
                avg_vel = U_0 * np.mean(shape_factors)
                self.log.info(f"  t={t:.4f}s: Q={flow_rates[i]:.4e} m³/s, U_avg={avg_vel:.4f} m/s")

    def _compute_shape_factors_vectorized(self, distances: np.ndarray) -> np.ndarray:
        """Vectorized computation of shape factors for all points."""
        if self.d_max <= 0:
            return np.ones(len(distances))

        d_norm = np.minimum(distances / self.d_max, 1.0)

        if self.shape_function == ShapeFunction.POWER_LAW:
            return d_norm**self.exponent

        elif self.shape_function == ShapeFunction.POISEUILLE:
            r_norm = 1.0 - d_norm
            return np.maximum(0, 1.0 - r_norm**2)

        elif self.shape_function == ShapeFunction.HYBRID_JET:
            core_dist = self.core_fraction * self.d_max
            result = np.ones(len(distances))
            near_wall = distances < core_dist
            result[near_wall] = (distances[near_wall] / core_dist) ** self.exponent
            return result

        elif self.shape_function == ShapeFunction.BLUNTED_PARABOLIC:
            core_dist = self.core_fraction * self.d_max
            result = np.ones(len(distances))
            near_wall = distances < core_dist
            local_r = 1.0 - (distances[near_wall] / core_dist)
            result[near_wall] = np.maximum(0, 1.0 - local_r**2)
            return result

        else:
            # Default Poiseuille
            r_norm = 1.0 - d_norm
            return np.maximum(0, 1.0 - r_norm**2)

    def _write_velocity_file_fast(self, file_path: str, velocities: np.ndarray) -> None:
        """Fast write velocity in OpenFOAM boundaryData format using numpy."""
        n = len(velocities)
        # Build the entire content as a single string for faster I/O
        lines = [f"{n}", "("]
        lines.extend(f"({v[0]:.6e} {v[1]:.6e} {v[2]:.6e})" for v in velocities)
        lines.append(")")
        with open(file_path, "w") as f:
            f.write("\n".join(lines) + "\n")

    def _should_flip_normal(self) -> bool:
        """Determine if normal needs flipping using inlet–wall edge-ring method.

        Falls back to the outlet-direction heuristic when STL surfaces are
        missing (partial pipelines / tests).

        NOTE: STL files are PRE-SCALED to meters, no scale_factor needed.
        """
        tri_surface_dir = os.path.join(self.case_directory, "constant", "triSurface")
        inlet_name = self.config.get("geometry", {}).get("inlet_keywords_ordered", "inlet")
        wall_name = self.config.get("geometry", {}).get("wall_keywords_ordered", "wall")

        try:
            from .utils.patch_processing import compute_inward_normal

            inward = compute_inward_normal(tri_surface_dir, inlet_name, wall_name)
            return np.dot(self.inlet_normal, inward) < 0
        except FileNotFoundError:
            return self._should_flip_normal_via_outlets(tri_surface_dir)
        except Exception:
            return False

    def _should_flip_normal_via_outlets(self, tri_surface_dir: str) -> bool:
        """Legacy flip detection: compare inlet normal to outlet bearing."""
        try:
            if not os.path.isdir(tri_surface_dir):
                return False
            stl_files = [f for f in os.listdir(tri_surface_dir) if f.endswith(".stl")]
            outlet_files = [f for f in stl_files if "outlet" in f.lower()]
            if not outlet_files:
                return False

            outlet_centers = []
            for outlet_file in outlet_files:
                outlet_name = outlet_file.replace(".stl", "")
                try:
                    proc = PatchProcessing(tri_surface_dir, outlet_name)
                    center, _, _ = proc.calculate_inlet_center_radius()
                    outlet_centers.append(center)
                except Exception:
                    continue
            if not outlet_centers:
                return False

            avg_outlet = np.mean(outlet_centers, axis=0)
            flow_dir = avg_outlet - self.center
            n = np.linalg.norm(flow_dir)
            if n == 0:
                return False
            flow_dir = flow_dir / n
            return np.dot(self.inlet_normal, flow_dir) < 0
        except Exception:
            return False

    def _read_csv_file(self, file_path: str) -> Tuple[np.ndarray, np.ndarray, float]:
        """Read time-series data from CSV."""
        # Count comment/empty lines and detect header
        # skip_header in genfromtxt skips from beginning BEFORE comment processing
        comment_lines = 0
        header_line = 0

        with open(file_path, "r") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    comment_lines += 1
                else:
                    # First non-comment line - check if it's a header
                    if any(c.isalpha() for c in stripped):
                        header_line = 1
                    break

        # Total lines to skip = comment lines + header (if present)
        skiprows = comment_lines + header_line

        data = np.genfromtxt(file_path, delimiter=",", skip_header=skiprows)

        if data.ndim < 2 or data.shape[1] < 2:
            raise ValueError("CSV must have at least 2 columns (time, value)")

        times = data[:, 0]
        values = data[:, 1]
        cardiac_cycle = times[-1] - times[0]

        return times, values, cardiac_cycle

    def _read_points_file(self, file_path: str) -> Tuple[int, np.ndarray]:
        """Read OpenFOAM points file."""
        import re

        with open(file_path, "r") as f:
            lines = [line.strip() for line in f if line.strip()]

        n_points = int(lines[0])
        points = []
        start_idx = 2 if lines[1] == "(" else 1

        for i in range(n_points):
            line = re.sub(r"[()]", "", lines[i + start_idx])
            xyz = [float(p) for p in line.split()]
            points.append(xyz)

        return n_points, np.array(points, dtype=float)

    def _clean_time_directories(self, parent_dir: str) -> None:
        """Remove old time directories."""
        for item in os.listdir(parent_dir):
            item_path = os.path.join(parent_dir, item)
            if item.replace(".", "", 1).replace("-", "", 1).isdigit():
                if os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)

    def _write_velocity_file(self, file_path: str, velocities: List[np.ndarray]) -> None:
        """Write velocity in OpenFOAM boundaryData format."""
        with open(file_path, "w") as f:
            f.write(f"{len(velocities)}\n(\n")
            for v in velocities:
                f.write(f"({v[0]:.6e} {v[1]:.6e} {v[2]:.6e})\n")
            f.write(")\n")


def create_distance_wall_profile(config: dict, case_directory: str) -> DistanceWallInletProfile:
    """Factory function to create profile generator."""
    return DistanceWallInletProfile(config, case_directory)
