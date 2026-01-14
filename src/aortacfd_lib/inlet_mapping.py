import os
import re
import shutil
import numpy as np
from scipy.special import jv

from .utils.logger import Logger
from .utils.patch_processing import PatchProcessing

class InletMapping:
    """
    Reads time-series data from a CSV, applies a velocity profile, and writes
    the time-varying boundary condition files into the correct directory structure.
    """
    def __init__(self, config: dict, case_directory: str):
        self.config = config
        self.case_directory = case_directory
        self.log = Logger("inlet_mapping").get_logger()

        # Get all necessary settings from the config dictionary
        # Support both config structures: boundary_conditions.inlet or inlet
        self.inlet_settings = self.config.get('boundary_conditions', {}).get('inlet') or self.config.get('inlet', {})
        self.geom_settings = self.config['geometry']
        self.phys_settings = self.config['physics']
        self.inlet_name = self.geom_settings['inlet_keywords_ordered']
        self.inlet_data_file = self.inlet_settings['csv_file']
        self.data_type = self.inlet_settings['data_type'].lower().strip()
        self.profile = self.inlet_settings['profile'].lower().strip()
        self.orientation = self.inlet_settings.get('orientation', 'auto').lower().strip()
        self.nu = self.phys_settings.get('nu')

        self.center = None
        self.radius = None
        self.area = None  # Actual STL surface area
        self.cardiac_cycle = None
        self.auto_flip_normal = False  # For automatic orientation detection

        self.log.info("InletMapping initialized successfully.")

    def run(self):
        """
        Main orchestration method for this class.
        """
        self.log.info("Calculating inlet patch geometry...")
        tri_surface_dir = os.path.join(self.case_directory, "constant", "triSurface")
        stl_files = [f for f in os.listdir(tri_surface_dir) if f.endswith('.stl')]

        # STL files in constant/triSurface/ are PRE-SCALED to meters during case setup
        # No scale_factor needed - values returned directly in SI units (meters)
        inlet_patch_processor = PatchProcessing(tri_surface_dir, self.inlet_name)
        self.center, self.radius, inlet_normal = inlet_patch_processor.calculate_inlet_center_radius()
        self.area = inlet_patch_processor.calculate_surface_area()
        self.log.info(f"Inlet center: {self.center}, Radius: {self.radius:.6f} m, Area: {self.area:.6e} m²")
        
        # Automatic orientation detection
        if self.orientation == 'auto':
            self.auto_flip_normal = self._determine_inward_direction(inlet_normal, self.case_directory)
        else:
            self.log.info(f"Using manual orientation setting: {self.orientation}")

        points_file = os.path.join(self.case_directory, "constant", "boundaryData", self.inlet_name, "points")
        if not os.path.isfile(points_file):
            raise FileNotFoundError(f"Points file not found: {points_file}")
        n_points, points = self._read_points_file(points_file)

        csv_path = os.path.join(self.case_directory, "constant", "boundaryData", self.inlet_name, self.inlet_data_file)
        if not os.path.isfile(csv_path):
            raise FileNotFoundError(f"Inlet data CSV not found: {csv_path}")
        times, yval, self.cardiac_cycle = self._read_csv_file(csv_path)

        parent_dir = os.path.join(self.case_directory, "constant", "boundaryData", self.inlet_name)
        self.log.debug(f"Cleaning old time directories and symlinks in {parent_dir}")
        for item in os.listdir(parent_dir):
            item_path = os.path.join(parent_dir, item)
            if item.replace('.', '', 1).isdigit():
                if os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)

        self.log.info("Generating time-varying velocity data directories...")
        self._generate_time_data(parent_dir, times, yval, points, inlet_normal)
        self.log.info(f"Generated velocity data directories in {parent_dir}")

    # --- MISSING HELPER METHODS NOW INCLUDED ---

    def _determine_cardiac_period(self, times):
        if len(times) < 2:
            raise ValueError("Insufficient time data to determine cardiac cycle period.")
        total_duration = times[-1] - times[0]
        if total_duration <= 0:
            raise ValueError("Invalid time range in the CSV file.")
        self.log.info(f"Determined cardiac cycle period: {total_duration:.6f} seconds.")
        return total_duration

    def _read_csv_file(self, file_name):
        try:
            # Count comment/empty lines and detect header
            # skip_header in genfromtxt skips from beginning BEFORE comment processing
            comment_lines = 0
            header_line = 0

            with open(file_name, 'r') as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped or stripped.startswith('#'):
                        comment_lines += 1
                    else:
                        # First non-comment line - check if it's a header
                        if any(c.isalpha() for c in stripped):
                            header_line = 1
                        break

            # Total lines to skip = comment lines + header (if present)
            skiprows = comment_lines + header_line

            data = np.genfromtxt(file_name, delimiter=',', skip_header=skiprows)
            if data.ndim < 2 or data.shape[1] < 2:
                raise ValueError(f"CSV file {file_name} must have at least 2 columns.")
        except Exception as e:
            raise RuntimeError(f"Error reading CSV file {file_name}: {e}")

        times = data[:, 0]
        yval = data[:, 1]

        # Auto-detect flowrate units and convert to m³/s if needed
        # Clinical data is typically in L/min (values > 1.0)
        # CFD data is typically in m³/s (values << 1.0, order of 1e-4 to 1e-5)
        if self.data_type == 'flowrate':
            max_abs_value = np.max(np.abs(yval))
            if max_abs_value > 1.0:
                # Likely L/min - convert to m³/s
                yval = yval * 1e-3 / 60.0  # L/min -> m³/s
                self.log.info(f"Flowrate CSV auto-detected as L/min (max={max_abs_value:.2f})")
                self.log.info(f"  Converted to m³/s: max={np.max(np.abs(yval)):.6e} m³/s")
            else:
                self.log.info(f"Flowrate CSV appears to be in m³/s (max={max_abs_value:.6e})")

        cardiac_cycle = self._determine_cardiac_period(times)
        return times, yval, cardiac_cycle

    def _read_points_file(self, file_name):
        with open(file_name, 'r') as file:
            lines = [line.strip() for line in file if line.strip()]
            n_points = int(lines[0])
            points = []
            start_index = 2 if lines[1] == '(' else 1
            for i in range(n_points):
                line_s = re.sub('[()]', '', lines[i + start_index])
                xyz = [float(p) for p in line_s.split()]
                points.append(xyz)
        return n_points, np.array(points, dtype=float)

    def _get_distance_from_center(self, point):
        return np.linalg.norm(point - self.center)

    def _determine_inward_direction(self, inlet_normal, case_directory):
        """
        Automatically determine if the normal should be flipped to point into the domain.
        Uses geometric analysis with outlet centroids to determine flow direction.
        """
        try:
            # Get outlet centroids to determine domain interior direction
            tri_surface_dir = os.path.join(case_directory, "constant", "triSurface")
            stl_files = [f for f in os.listdir(tri_surface_dir) if f.endswith('.stl')]
            outlet_files = [f for f in stl_files if "outlet" in f.lower()]
            
            if not outlet_files:
                self.log.warning("No outlet files found for automatic orientation. Using normal as-is.")
                return False
            
            # Calculate average outlet centroid position
            # STL files are pre-scaled to meters, no scale_factor needed
            outlet_centroids = []

            for outlet_file in outlet_files:
                outlet_name = outlet_file.replace('.stl', '')
                try:
                    outlet_processor = PatchProcessing(tri_surface_dir, outlet_name)
                    outlet_center, _, _ = outlet_processor.calculate_inlet_center_radius()
                    outlet_centroids.append(outlet_center)
                except Exception as e:
                    self.log.warning(f"Could not process outlet {outlet_name}: {e}")
                    continue
            
            if not outlet_centroids:
                self.log.warning("No valid outlet centroids found. Using normal as-is.")
                return False
            
            # Calculate average outlet position
            avg_outlet_pos = np.mean(outlet_centroids, axis=0)
            
            # Vector from inlet center to average outlet center (expected flow direction)
            inlet_to_outlets = avg_outlet_pos - self.center
            inlet_to_outlets_normalized = inlet_to_outlets / np.linalg.norm(inlet_to_outlets)
            
            # Check if inlet normal aligns with expected flow direction
            dot_product = np.dot(inlet_normal, inlet_to_outlets_normalized)
            
            self.log.info(f"Inlet center: {self.center}")
            self.log.info(f"Average outlet center: {avg_outlet_pos}")
            self.log.info(f"Flow direction vector: {inlet_to_outlets_normalized}")
            self.log.info(f"Inlet normal: {inlet_normal}")
            self.log.info(f"Dot product (alignment): {dot_product:.4f}")
            
            # If dot product is negative, normal points opposite to flow direction
            should_flip = dot_product < 0
            
            if should_flip:
                self.log.info("Auto-detected: Normal points outward from domain, flipping for inward flow")
            else:
                self.log.info("Auto-detected: Normal points inward to domain, keeping as-is")
                
            return should_flip
            
        except Exception as e:
            self.log.error(f"Error in automatic orientation detection: {e}")
            self.log.warning("Falling back to manual orientation setting")
            return False

    def _get_velocity_components(self, speed_scalar, normal_vec):
        # Apply orientation: 'out' means positive normal direction, 'in' means negative, 'auto' means automatic detection
        if self.orientation == 'auto':
            direction_multiplier = -1.0 if self.auto_flip_normal else 1.0
        else:
            direction_multiplier = -1.0 if self.orientation == 'in' else 1.0
        return speed_scalar * direction_multiplier * normal_vec

    def compute_cross_sectional_area(self):
        """
        Returns the actual STL surface area instead of circular approximation.
        Falls back to π*r² if STL area not yet calculated.
        """
        if self.area is not None:
            return self.area
        # Fallback to circular approximation if area not yet computed
        return np.pi * self.radius**2

    def plug_profile_speed(self, data_val):
        if self.data_type == 'flowrate':
            return data_val / self.compute_cross_sectional_area()
        return data_val

    def parabolic_centerline_speed(self, data_val):
        if self.data_type == 'flowrate':
            avg_vel = data_val / self.compute_cross_sectional_area()
            return 2.0 * avg_vel
        return 2.0 * data_val

    def parabolic_factor(self, dist):
        rel = dist / self.radius
        return max(0.0, 1.0 - rel**2)

    def womersley_shape_factor(self, r, t, omega, alpha):
        """
        Compute the Womersley velocity profile shape factor (normalized).

        This returns a dimensionless shape factor that describes the radial
        velocity distribution. The actual velocity is obtained by scaling
        this by the target flow rate.

        Args:
            r: Radial distance from center (m)
            t: Time (s)
            omega: Angular frequency (rad/s)
            alpha: Womersley number (dimensionless)

        Returns:
            float: Shape factor (dimensionless, typically 0-1 range)
        """
        R = self.radius
        z = 1j**1.5 * alpha * r / R
        z0 = 1j**1.5 * alpha
        bessel_ratio = jv(0, z) / jv(0, z0)
        v_r_t = (1 - bessel_ratio) * np.exp(1j * omega * t)
        return np.real(v_r_t)

    # =========================================================================
    # DOPPLER + WOMERSLEY FFT RECONSTRUCTION
    # =========================================================================
    # Uses Doppler waveform as radius-averaged signal and reconstructs the
    # unsteady inlet profile using analytical Womersley solution with Fourier
    # decomposition. This captures entrance effects, temporal development,
    # and the oscillatory nature of aortic flow.
    # =========================================================================

    def _estimate_required_harmonics(self, values: np.ndarray,
                                       energy_threshold: float = 0.99) -> int:
        """
        Auto-detect required number of Womersley harmonics based on spectral energy.

        Uses FFT to determine how many harmonics are needed to capture a given
        fraction of the signal's energy (variance).

        Args:
            values: Flow/velocity waveform values
            energy_threshold: Fraction of total energy to capture (default: 99%)

        Returns:
            int: Recommended number of harmonics (minimum 4, maximum N/2)

        Status: UNDER DEVELOPMENT - Feature may change
        """
        N = len(values)
        max_harmonics = min(N // 2 - 1, 50)  # Cap at 50 or Nyquist

        # Compute FFT
        fft_result = np.fft.fft(values)

        # Power spectrum (energy per harmonic)
        power = np.abs(fft_result[:N//2])**2

        # Total energy (excluding DC)
        total_energy = np.sum(power[1:])

        if total_energy < 1e-15:
            return 8  # Default for constant signal

        # Cumulative energy
        cumulative_energy = np.cumsum(power[1:])
        normalized_energy = cumulative_energy / total_energy

        # Find number of harmonics for threshold
        n_required = np.searchsorted(normalized_energy, energy_threshold) + 1

        # Bounds: minimum 4, maximum from signal length
        n_required = max(4, min(n_required, max_harmonics))

        self.log.info(f"Auto-detected Womersley harmonics: {n_required} "
                      f"(captures {energy_threshold*100:.0f}% of signal energy)")

        return n_required

    def _compute_fourier_coefficients(self, times, values, n_harmonics=8):
        """
        Compute Fourier coefficients from Doppler/flow waveform using FFT.

        The waveform is decomposed as:
            V(t) = V₀ + Σₙ Re[Vₙ * e^(inωt)]

        Args:
            times: Time array (s)
            values: Velocity or flow rate values
            n_harmonics: Number of harmonics to use (default: 8, or 'auto')

        Returns:
            tuple: (V0, Vn_complex, omega_fundamental)
                - V0: Mean (DC) component
                - Vn_complex: Complex Fourier coefficients for harmonics 1..n
                - omega_fundamental: Fundamental angular frequency (rad/s)
        """
        N = len(values)
        T = times[-1] - times[0]  # Cardiac cycle period
        omega_fundamental = 2 * np.pi / T

        # Compute FFT
        fft_result = np.fft.fft(values)

        # DC component (mean)
        V0 = np.real(fft_result[0]) / N

        # Complex coefficients for harmonics 1 to n_harmonics
        # FFT gives coefficients scaled by N, and we need factor of 2 for one-sided spectrum
        Vn_complex = 2 * fft_result[1:n_harmonics + 1] / N

        self.log.info(f"Fourier decomposition: {n_harmonics} harmonics, T={T:.4f}s, ω₀={omega_fundamental:.4f} rad/s")
        self.log.debug(f"  V₀ (mean) = {V0:.6e}")
        for n, Vn in enumerate(Vn_complex, 1):
            self.log.debug(f"  V_{n} = {np.abs(Vn):.6e} ∠ {np.angle(Vn)*180/np.pi:.1f}°")

        return V0, Vn_complex, omega_fundamental

    def _womersley_profile_harmonic(self, r, n, omega_fundamental, Vn_complex, t):
        """
        Compute velocity contribution from a single Womersley harmonic.

        For harmonic n, the radial velocity profile is:
            uₙ(r,t) = Re[ Vₙ · Φₙ(r) · e^(inωt) ]

        where:
            Φₙ(r) = (1 - J₀(αₙ·i^(3/2)·r/R)) / (1 - J₀(αₙ·i^(3/2)))
            αₙ = R·√(n·ω/ν)

        Args:
            r: Radial distance from center (m)
            n: Harmonic number (1, 2, 3, ...)
            omega_fundamental: Fundamental angular frequency (rad/s)
            Vn_complex: Complex Fourier coefficient for this harmonic
            t: Time (s)

        Returns:
            float: Velocity contribution from this harmonic (m/s)
        """
        R = self.radius
        omega_n = n * omega_fundamental

        # Womersley number for this harmonic
        alpha_n = R * np.sqrt(omega_n / self.nu)

        # Womersley shape function Φₙ(r)
        z = 1j**1.5 * alpha_n * r / R
        z0 = 1j**1.5 * alpha_n

        # Handle the Bessel function ratio
        J0_z = jv(0, z)
        J0_z0 = jv(0, z0)

        if np.abs(J0_z0) < 1e-15:
            # Avoid division by zero for very high alpha
            Phi_n = 0.0
        else:
            Phi_n = (1 - J0_z / J0_z0)

        # Complete harmonic contribution: Vₙ · Φₙ(r) · e^(inωt)
        u_n = Vn_complex * Phi_n * np.exp(1j * omega_n * t)

        return np.real(u_n)

    def _womersley_fft_velocity(self, r, t, V0, Vn_complex, omega_fundamental):
        """
        Compute complete Womersley velocity profile from Fourier decomposition.

        Total velocity:
            u(r,t) = u₀(r) + Σₙ uₙ(r,t)

        where u₀(r) = 2·V₀·(1 - r²/R²) is the steady Poiseuille component
        for the mean flow.

        Args:
            r: Radial distance from center (m)
            t: Time (s)
            V0: Mean (DC) velocity component
            Vn_complex: Complex Fourier coefficients for harmonics
            omega_fundamental: Fundamental angular frequency (rad/s)

        Returns:
            float: Total velocity at position r and time t (m/s)
        """
        R = self.radius

        # Steady (Poiseuille) component for mean flow
        # For mean velocity V0, the parabolic profile has centerline = 2*V0
        r_ratio = r / R
        if r_ratio > 1.0:
            return 0.0

        u_steady = 2.0 * V0 * (1 - r_ratio**2)

        # Sum oscillatory components from each harmonic
        u_oscillatory = 0.0
        for n, Vn in enumerate(Vn_complex, 1):
            u_oscillatory += self._womersley_profile_harmonic(r, n, omega_fundamental, Vn, t)

        return u_steady + u_oscillatory

    def _compute_womersley_fft_shape_factors(self, points, t, V0, Vn_complex, omega_fundamental):
        """
        Compute velocity values at all points using Womersley FFT reconstruction.

        Unlike the simple Womersley which uses a single frequency, this method
        uses the full Fourier decomposition of the Doppler waveform.

        Args:
            points: Array of face center coordinates
            t: Current time (s)
            V0: Mean (DC) velocity component
            Vn_complex: Complex Fourier coefficients
            omega_fundamental: Fundamental angular frequency (rad/s)

        Returns:
            numpy.ndarray: Velocity values at each point (m/s)
        """
        velocities = np.zeros(len(points))

        for idx, pt in enumerate(points):
            dist = self._get_distance_from_center(pt)

            if dist <= self.radius:
                velocities[idx] = self._womersley_fft_velocity(
                    dist, t, V0, Vn_complex, omega_fundamental
                )
            else:
                velocities[idx] = 0.0

        return velocities

    def _compute_womersley_fft_scale_factor(self, points, t, V0, Vn_complex, omega_fundamental, target_Q):
        """
        Compute scale factor to ensure flow rate conservation for Womersley FFT.

        The Womersley FFT reconstruction inherently conserves flow rate if the
        Doppler signal represents the true cross-sectional average. However,
        we apply a correction factor to account for:
        - Discrete sampling of face centers
        - Non-uniform face areas
        - Truncation of Fourier series

        Args:
            points: Array of face center coordinates
            t: Current time (s)
            V0, Vn_complex, omega_fundamental: Fourier parameters
            target_Q: Target flow rate from CSV (m³/s)

        Returns:
            float: Scale factor to apply to velocities
        """
        # Compute raw velocities
        raw_velocities = self._compute_womersley_fft_shape_factors(
            points, t, V0, Vn_complex, omega_fundamental
        )

        # Estimate integrated flow rate
        active_mask = np.abs(raw_velocities) > 1e-15
        n_active = np.sum(active_mask)

        if n_active == 0:
            return 0.0

        A_face = self.area / n_active
        Q_raw = np.sum(raw_velocities[active_mask]) * A_face

        if np.abs(Q_raw) < 1e-15:
            return 0.0

        # Scale factor
        scale_factor = target_Q / Q_raw

        return scale_factor

    # =========================================================================
    # WALL-DISTANCE BASED PROFILE FOR IRREGULAR INLETS
    # =========================================================================
    # For non-circular inlet geometries (e.g., irregular aortic roots), this
    # method computes velocity based on distance to the nearest boundary.
    # Inspired by OpenFOAM's powerLawVelocity boundary condition.
    # Reference: OpenFOAM Issue #2322 - powerLawVelocity based on wall distance
    # =========================================================================

    def _compute_wall_distances(self, points, inlet_boundary_points=None):
        """
        Compute perpendicular distance from each face center to nearest inlet boundary.

        For irregular cross-sections, this provides a generalized "radial" distance
        that can be used to construct Poiseuille-like velocity profiles.

        Args:
            points: Array of face center coordinates (N x 3)
            inlet_boundary_points: Optional array of boundary points. If None,
                                   uses STL vertices from inlet patch.

        Returns:
            numpy.ndarray: Distance to nearest boundary for each point (m)
        """
        if inlet_boundary_points is None:
            # Load boundary points from inlet STL
            inlet_boundary_points = self._get_inlet_boundary_points()

        # Use KDTree for fast nearest-neighbor lookup: O(N log M) instead of O(N*M)
        try:
            from scipy.spatial import cKDTree

            # Project to 2D (inlet plane) for distance calculation
            points_2d = points[:, :2] if points.shape[1] >= 2 else points
            boundary_2d = inlet_boundary_points[:, :2] if inlet_boundary_points.shape[1] >= 2 else inlet_boundary_points

            tree = cKDTree(boundary_2d)
            distances, _ = tree.query(points_2d, k=1)

        except ImportError:
            # Fallback to vectorized numpy
            self.log.warning("scipy not available, using vectorized fallback (slower)")
            distances = np.zeros(len(points))
            for idx, pt in enumerate(points):
                pt_2d = pt[:2] if len(pt) >= 2 else pt
                boundary_2d = inlet_boundary_points[:, :2] if inlet_boundary_points.shape[1] >= 2 else inlet_boundary_points
                distances[idx] = np.min(np.linalg.norm(boundary_2d - pt_2d, axis=1))

        return distances

    def _get_inlet_boundary_points(self):
        """
        Extract boundary vertices from inlet STL file.

        Returns:
            numpy.ndarray: Array of boundary point coordinates
        """
        try:
            tri_surface_dir = os.path.join(self.case_directory, "constant", "triSurface")
            inlet_stl_path = os.path.join(tri_surface_dir, f"{self.inlet_name}.stl")

            # Use trimesh to load STL and extract boundary edges
            import trimesh
            mesh = trimesh.load(inlet_stl_path)

            # Get unique vertices on the boundary (edges that appear only once)
            edges = mesh.edges_unique
            edge_counts = np.bincount(mesh.edges.flatten(), minlength=len(mesh.vertices))

            # Boundary vertices are those with lower connectivity
            # For a flat surface patch, boundary vertices are on the outer edge
            boundary_mask = edge_counts < 6  # Heuristic: boundary vertices have fewer connections
            boundary_vertices = mesh.vertices[boundary_mask]

            if len(boundary_vertices) < 3:
                # Fallback: use all vertices on the convex hull projection
                from scipy.spatial import ConvexHull
                vertices_2d = mesh.vertices[:, :2]
                hull = ConvexHull(vertices_2d)
                boundary_vertices = mesh.vertices[hull.vertices]

            self.log.debug(f"Extracted {len(boundary_vertices)} boundary points from inlet STL")
            return boundary_vertices

        except Exception as e:
            self.log.warning(f"Could not extract boundary from STL: {e}")
            self.log.warning("Falling back to circular approximation")
            # Fallback: generate circular boundary points
            n_boundary = 36
            theta = np.linspace(0, 2*np.pi, n_boundary, endpoint=False)
            boundary_points = np.zeros((n_boundary, 3))
            boundary_points[:, 0] = self.center[0] + self.radius * np.cos(theta)
            boundary_points[:, 1] = self.center[1] + self.radius * np.sin(theta)
            boundary_points[:, 2] = self.center[2]
            return boundary_points

    def _compute_wall_distance_shape_factors(self, points, profile_exponent=2.0):
        """
        Compute velocity shape factors based on wall distance.

        Uses a generalized parabolic profile:
            u(d) = u_max * (1 - (1 - d/d_max)^n)

        where:
            d = distance from point to nearest wall
            d_max = maximum distance (characteristic length)
            n = profile exponent (2 for parabolic, higher for flatter profiles)

        For n=2, this approximates the Poiseuille profile for any cross-section.

        Args:
            points: Array of face center coordinates
            profile_exponent: Exponent n in the profile formula (default: 2.0)

        Returns:
            numpy.ndarray: Shape factors for each point (dimensionless, 0-1)
        """
        # Compute wall distances
        wall_distances = self._compute_wall_distances(points)

        # Maximum distance (characteristic length scale)
        d_max = np.max(wall_distances)

        if d_max < 1e-15:
            self.log.warning("Maximum wall distance is zero. Returning uniform profile.")
            return np.ones(len(points))

        # Normalized distance (0 at wall, 1 at center/max distance point)
        d_normalized = wall_distances / d_max

        # Shape factor: parabolic-like profile
        # u/u_max = 1 - (1 - d/d_max)^n
        # At wall (d=0): u = 0
        # At center (d=d_max): u = u_max
        shape_factors = 1.0 - (1.0 - d_normalized) ** profile_exponent

        # Ensure no negative values
        shape_factors = np.maximum(shape_factors, 0.0)

        self.log.debug(f"Wall-distance profile: d_max={d_max:.6f}m, exponent={profile_exponent}")
        self.log.debug(f"  Shape factor range: [{np.min(shape_factors):.4f}, {np.max(shape_factors):.4f}]")

        return shape_factors

    def _compute_elliptical_poiseuille_factors(self, points, semi_axis_a=None, semi_axis_b=None):
        """
        Compute velocity shape factors for elliptical Poiseuille flow.

        For an elliptical cross-section with semi-axes a and b, the exact
        velocity profile is:
            u(x,y) = u_max * (1 - y²/b² - x²/a²)

        where the coordinate system is centered at the ellipse center with
        x along the major axis.

        Args:
            points: Array of face center coordinates
            semi_axis_a: Semi-major axis (m). If None, estimated from geometry.
            semi_axis_b: Semi-minor axis (m). If None, estimated from geometry.

        Returns:
            numpy.ndarray: Shape factors for each point (dimensionless, 0-1)
        """
        # Estimate semi-axes if not provided
        if semi_axis_a is None or semi_axis_b is None:
            semi_axis_a, semi_axis_b = self._estimate_ellipse_axes(points)

        self.log.info(f"Elliptical Poiseuille: a={semi_axis_a*1000:.2f}mm, b={semi_axis_b*1000:.2f}mm")
        self.log.info(f"  Aspect ratio: {semi_axis_a/semi_axis_b:.3f}")

        shape_factors = np.zeros(len(points))

        for idx, pt in enumerate(points):
            # Transform to ellipse-centered coordinates
            x = pt[0] - self.center[0]
            y = pt[1] - self.center[1]

            # Elliptical profile: 1 - (x/a)² - (y/b)²
            ellipse_term = (x / semi_axis_a) ** 2 + (y / semi_axis_b) ** 2

            if ellipse_term <= 1.0:
                shape_factors[idx] = 1.0 - ellipse_term
            else:
                # Outside ellipse
                shape_factors[idx] = 0.0

        return shape_factors

    def _estimate_ellipse_axes(self, points):
        """
        Estimate ellipse semi-axes from point distribution using PCA.

        Args:
            points: Array of face center coordinates

        Returns:
            tuple: (semi_axis_a, semi_axis_b) in meters
        """
        # Center the points
        centered = points[:, :2] - self.center[:2]

        # Use PCA to find principal axes
        cov_matrix = np.cov(centered.T)
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)

        # Sort by eigenvalue (largest first)
        sort_idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[sort_idx]

        # Semi-axes are proportional to sqrt of eigenvalues
        # Scale factor based on actual extent of points
        scale = 2.0  # Empirical factor for inlet patches
        semi_axis_a = scale * np.sqrt(eigenvalues[0])
        semi_axis_b = scale * np.sqrt(eigenvalues[1])

        # Ensure a >= b
        if semi_axis_b > semi_axis_a:
            semi_axis_a, semi_axis_b = semi_axis_b, semi_axis_a

        return semi_axis_a, semi_axis_b

    def _compute_shape_factors(self, points, t, omega=None, alpha=None,
                                V0=None, Vn_complex=None, omega_fundamental=None,
                                profile_exponent=None):
        """
        Compute normalized shape factors for all points based on profile type.

        Returns shape factors that integrate to a known value, allowing
        proper scaling to match target flow rate.

        Supported profiles:
            - plug / plug_flow: Uniform velocity (shape = 1.0)
            - parabolic: Circular Poiseuille (1 - r²/R²)
            - womersley: Single-frequency pulsatile (Bessel functions)
            - womersley_fft: Multi-harmonic Doppler reconstruction
            - wall_distance: Distance-to-wall based (for irregular inlets)
            - elliptical: Elliptical Poiseuille (1 - x²/a² - y²/b²)

        Args:
            points: Array of face center coordinates
            t: Current time (for Womersley)
            omega: Angular frequency (for simple Womersley)
            alpha: Womersley number (for simple Womersley)
            V0: Mean velocity (for womersley_fft)
            Vn_complex: Fourier coefficients (for womersley_fft)
            omega_fundamental: Fundamental frequency (for womersley_fft)
            profile_exponent: Exponent for wall_distance profile (default: 2.0)

        Returns:
            numpy.ndarray: Shape factors for each point (dimensionless)
        """
        # For womersley_fft, use the dedicated method
        if self.profile == 'womersley_fft':
            return self._compute_womersley_fft_shape_factors(
                points, t, V0, Vn_complex, omega_fundamental
            )

        # For wall_distance profile, use distance-based calculation
        if self.profile == 'wall_distance':
            exponent = profile_exponent if profile_exponent is not None else 2.0
            return self._compute_wall_distance_shape_factors(points, exponent)

        # For elliptical profile, use elliptical Poiseuille
        if self.profile == 'elliptical':
            return self._compute_elliptical_poiseuille_factors(points)

        # Standard radial-distance based profiles
        shape_factors = np.zeros(len(points))

        for idx, pt in enumerate(points):
            dist = self._get_distance_from_center(pt)

            if dist <= self.radius:
                if self.profile in ['plug', 'plug_flow']:
                    # Plug flow: uniform shape factor
                    shape_factors[idx] = 1.0

                elif self.profile == 'parabolic':
                    # Parabolic: 1 - (r/R)^2
                    shape_factors[idx] = self.parabolic_factor(dist)

                elif self.profile == 'womersley':
                    # Womersley: time-dependent shape from Bessel functions
                    shape_factors[idx] = self.womersley_shape_factor(dist, t, omega, alpha)

                else:
                    # Default to plug flow
                    shape_factors[idx] = 1.0
            else:
                # Outside the inlet radius
                shape_factors[idx] = 0.0

        return shape_factors

    def _scale_to_target_flowrate(self, shape_factors, target_flowrate, n_points):
        """
        Scale shape factors to produce velocities that integrate to target flow rate.

        For standard profiles (parabolic, plug), uses ANALYTICAL integration to avoid
        mesh distribution artifacts. For non-standard profiles, uses mesh-based summation.

        Analytical integrals for circular inlet (radius R, area A = πR²):
        - Parabolic: Q = U_max * A/2  =>  U_max = 2*Q/A = 2*U_avg
        - Plug:      Q = U_max * A    =>  U_max = Q/A = U_avg

        Args:
            shape_factors: Normalized shape factors for each point
            target_flowrate: Target volumetric flow rate (m³/s)
            n_points: Total number of points

        Returns:
            numpy.ndarray: Scaled velocities (m/s)
        """
        # Count active points (inside inlet radius)
        active_mask = shape_factors > 0
        n_active = np.sum(active_mask)

        if n_active == 0:
            self.log.warning("No active points inside inlet radius!")
            return np.zeros(len(shape_factors))

        # Use analytical scaling for standard profiles to avoid mesh distribution artifacts
        # Mesh face centers are often NOT uniformly distributed by area, which causes
        # incorrect velocity scaling when using discrete summation.
        if self.profile == 'parabolic':
            # Parabolic (Poiseuille): u(r) = U_max * (1 - r²/R²)
            # Analytical integral: Q = U_max * πR² / 2 = U_max * A / 2
            # => U_max = 2 * Q / A = 2 * U_avg
            U_max = 2.0 * abs(target_flowrate) / self.area
            velocities = shape_factors * U_max
            return velocities

        elif self.profile in ['plug', 'plug_flow']:
            # Plug flow: u = U_max (uniform)
            # Analytical integral: Q = U_max * A
            # => U_max = Q / A = U_avg
            U_max = abs(target_flowrate) / self.area
            velocities = shape_factors * U_max
            return velocities

        else:
            # For non-standard profiles (womersley, wall_distance, elliptical, etc.),
            # use mesh-based integration as these don't have simple analytical forms
            # Estimate face area per point (uniform distribution assumption)
            A_face = self.area / n_active

            # Compute integrated flow with unit velocity scaling
            # Q_unit = Σ(shape_i * A_face) for active points
            Q_unit = np.sum(shape_factors[active_mask]) * A_face

            if abs(Q_unit) < 1e-15:
                # Avoid division by zero for zero flow
                return np.zeros(len(shape_factors))

            # Scale factor to achieve target flow rate
            scale_factor = abs(target_flowrate) / Q_unit

            # Apply scaling
            velocities = shape_factors * scale_factor

            return velocities

    def _generate_time_data(self, parent_directory, time_array, csv_values, points, normal_vec):
        """
        Generate time-varying velocity data with proper flow rate conservation.

        This method ensures that the integrated flow rate across the inlet
        matches the target flow rate from the CSV file at each timestep.

        Supported profile types:
        - plug, plug_flow: Uniform velocity
        - parabolic: Circular Poiseuille (1 - r²/R²)
        - womersley: Single-frequency pulsatile
        - womersley_fft: Multi-harmonic Doppler reconstruction
        - wall_distance: Distance-to-wall based (irregular inlets)
        - elliptical: Elliptical Poiseuille (1 - x²/a² - y²/b²)

        Algorithm:
        1. Compute normalized shape factors based on profile type
        2. Scale velocities to match target flow rate
        3. Apply flow direction (orientation)
        4. Write OpenFOAM-compatible velocity files
        """
        # Precompute parameters based on profile type
        omega = None
        alpha = None
        V0 = None
        Vn_complex = None
        omega_fundamental = None
        n_harmonics_setting = self.inlet_settings.get('n_harmonics', 8)
        profile_exponent = self.inlet_settings.get('exponent', 2.0)

        if self.profile == 'womersley':
            # Simple single-frequency Womersley
            if not self.nu or self.nu <= 0:
                raise ValueError("Womersley profile requires a positive kinematic viscosity (nu) in config.")
            omega = 2 * np.pi / self.cardiac_cycle
            alpha = self.radius * np.sqrt(omega / self.nu)
            self.log.info(f"Womersley parameters: omega={omega:.4f} rad/s, alpha={alpha:.4f}")

        elif self.profile == 'womersley_fft':
            # Multi-harmonic Womersley with Fourier decomposition
            if not self.nu or self.nu <= 0:
                raise ValueError("Womersley FFT profile requires a positive kinematic viscosity (nu) in config.")

            # Convert flow rate to velocity for FFT if needed
            if self.data_type == 'flowrate':
                velocity_values = csv_values / self.area
            else:
                velocity_values = csv_values

            # Determine number of harmonics (auto-detect or user-specified)
            if n_harmonics_setting == 'auto' or n_harmonics_setting == -1:
                # Auto-detect based on spectral energy content
                # Status: UNDER DEVELOPMENT
                energy_threshold = self.inlet_settings.get('energy_threshold', 0.99)
                n_harmonics = self._estimate_required_harmonics(velocity_values, energy_threshold)
            else:
                n_harmonics = int(n_harmonics_setting)

            # Compute Fourier coefficients from the waveform
            V0, Vn_complex, omega_fundamental = self._compute_fourier_coefficients(
                time_array, velocity_values, n_harmonics
            )

            # Log Womersley numbers for each harmonic
            self.log.info(f"Womersley FFT profile with {n_harmonics} harmonics:")
            for n in range(1, min(4, n_harmonics + 1)):  # Log first 3 harmonics
                alpha_n = self.radius * np.sqrt(n * omega_fundamental / self.nu)
                self.log.info(f"  Harmonic {n}: α={alpha_n:.2f}")

        elif self.profile == 'wall_distance':
            self.log.info(f"Wall-distance profile with exponent={profile_exponent}")
            self.log.info("  Suitable for irregular (non-circular) inlet geometries")

        elif self.profile == 'elliptical':
            self.log.info("Elliptical Poiseuille profile")
            self.log.info("  Semi-axes will be estimated from inlet geometry")

        n_points = len(points)

        # Track flow rate statistics for verification
        max_error_percent = 0.0
        total_timesteps = len(time_array)

        self.log.info(f"Generating {total_timesteps} timesteps with flow rate conservation...")
        self.log.info(f"Profile: {self.profile}, Data type: {self.data_type}")

        for i in range(total_timesteps):
            t = time_array[i]
            csv_value = csv_values[i]

            # Determine target flow rate in m³/s
            # Note: csv_values are already converted to m³/s in _read_csv_file()
            if self.data_type == 'flowrate':
                # CSV flow rate already converted to m³/s during file read
                target_Q = csv_value
            else:
                # CSV contains velocity - convert to flow rate
                # Q = V_avg * A
                target_Q = csv_value * self.area

            # Step 1: Compute shape factors for this timestep
            if self.profile == 'womersley_fft':
                # For womersley_fft, shape factors are actual velocities
                shape_factors = self._compute_shape_factors(
                    points, t, omega, alpha,
                    V0=V0, Vn_complex=Vn_complex, omega_fundamental=omega_fundamental
                )
                # Apply flow conservation scaling
                scale_factor = self._compute_womersley_fft_scale_factor(
                    points, t, V0, Vn_complex, omega_fundamental, target_Q
                )
                velocity_magnitudes = shape_factors * scale_factor
            else:
                # For all other profiles (plug, parabolic, womersley, wall_distance, elliptical)
                shape_factors = self._compute_shape_factors(
                    points, t, omega, alpha,
                    profile_exponent=profile_exponent
                )
                # Step 2: Scale to target flow rate
                velocity_magnitudes = self._scale_to_target_flowrate(shape_factors, target_Q, n_points)

            # Step 3: Apply direction and create velocity vectors
            velocities = []
            for mag in velocity_magnitudes:
                vel_vector = self._get_velocity_components(mag, normal_vec)
                velocities.append(vel_vector)

            # Step 4: Verify flow rate (for logging)
            if abs(target_Q) > 1e-15:
                computed_Q = self._verify_flowrate(velocity_magnitudes, n_points)
                if abs(target_Q) > 1e-15:
                    error_percent = abs(computed_Q - target_Q) / abs(target_Q) * 100
                    max_error_percent = max(max_error_percent, error_percent)

            # Step 5: Write to file
            time_dir_path = os.path.join(parent_directory, f"{t:.6f}")
            os.makedirs(time_dir_path, exist_ok=True)
            out_file_path = os.path.join(time_dir_path, "U")
            self._write_openfoam_data_format(out_file_path, n_points, velocities)

        # Log summary
        self.log.info(f"Flow rate conservation complete. Max error: {max_error_percent:.4f}%")
        if max_error_percent > 1.0:
            self.log.warning(f"Flow rate error exceeds 1%. Consider checking mesh face distribution.")

    def _verify_flowrate(self, velocity_magnitudes, n_points):
        """
        Verify the integrated flow rate from velocity magnitudes.

        Args:
            velocity_magnitudes: Array of velocity magnitudes (m/s)
            n_points: Total number of points

        Returns:
            float: Computed flow rate (m³/s)
        """
        active_mask = velocity_magnitudes > 0
        n_active = np.sum(active_mask)

        if n_active == 0:
            return 0.0

        A_face = self.area / n_active
        Q_computed = np.sum(velocity_magnitudes[active_mask]) * A_face

        return Q_computed

    def _write_openfoam_data_format(self, file_name, n_points, velocities):
        with open(file_name, 'w') as file:
            file.write(f"{n_points}\n(\n")
            for v in velocities:
                file.write(f"({v[0]:.6e} {v[1]:.6e} {v[2]:.6e})\n")
            file.write(")\n")