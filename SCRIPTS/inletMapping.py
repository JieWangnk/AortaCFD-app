import os
import re
import glob
import numpy as np
from scipy.special import jv
import logging

logging.basicConfig(level=logging.INFO)


class InletMapping:
    """
    A class that reads time-vs-(flowRate or velocity) data from CSV, computes or applies
    velocity profiles (plug, parabolic, or Womersley), and writes out OpenFOAM
    time-varying boundary condition files.

    CSV Format (2 columns, no headers):
        - time, flowOrVel
        Example:
            0.00, 1.2e-5
            0.01, 1.3e-5
            ...
    """

    def __init__(
        self,
        center,
        radius,
        inlet_data_file,
        inlet_name,
        data_type='flowRate',  # 'flowRate' or 'velocity'
        profile='parabolic',   # 'plug', 'parabolic', or 'womersley'
        scale=1.0,
        **kwargs
    ):
        """
        Args:
            center (array-like): The (x, y, z) center of the inlet face.
            radius (float): The inlet radius.
            inlet_data_file (str): CSV containing time and either flowRate or velocity.
            inlet_name (str): Name of the inlet patch (for file structure).
            data_type (str): 'flowRate' (CSV column = flow rate in m^3/s) or 'velocity' (CSV column = speed in m/s).
            profile (str): 'plug', 'parabolic', or 'womersley'.
            scale (float): Additional scaling factor for coordinates, default=1.0.
            **kwargs: Additional parameters (e.g., orientation='out', rho=..., nu=..., etc.).
        """
        self.center = np.array(center, dtype=float)
        self.radius = float(radius)
        self.inlet_data_file = inlet_data_file
        self.inlet_name = inlet_name
        self.data_type = data_type.lower().strip()    # 'flowRate' or 'velocity'
        self.profile = profile.lower().strip()        # 'plug', 'parabolic', 'womersley'
        self.scale = scale
        self.kwargs = kwargs

        # Potentially read optional parameters from kwargs, if used for Womersley or advanced BC
        self.rho = kwargs.get("rho", 1060)  # default blood density
        self.nu = kwargs.get("nu", 3.3e-6)  # default blood kinematic viscosity
        self.delta_p = kwargs.get("delta_p", 1.0)  # default pressure gradient amplitude if needed

        VALID_PROFILES = ['plug', 'parabolic', 'womersley']
        VALID_DATA_TYPES = ['flowrate', 'velocity']

        if self.profile not in VALID_PROFILES:
            raise ValueError(f"Invalid profile: {self.profile}. Must be one of {VALID_PROFILES}.")
        if self.data_type not in VALID_DATA_TYPES:
            raise ValueError(f"Invalid data_type: {self.data_type}. Must be one of {VALID_DATA_TYPES}.")

    def compute_cross_sectional_area(self):
        return np.pi * (self.radius * self.scale)**2

    def read_csv_file(self, file_name):
        try:
            data = np.genfromtxt(file_name, delimiter=',', skip_header=1)
            if data.ndim < 2 or data.shape[1] < 2:
                raise ValueError(f"CSV file {file_name} must have at least 2 columns.")
        except Exception as e:
            logging.error(f"Error reading CSV file {file_name}: {e}")
            raise
        return data[:, 0], data[:, 1], data[-1, 0] - data[0, 0]

    def read_points_file(self, file_name):
        """
        Reads an OpenFOAM points file:
            N
            (
              (x0 y0 z0)
              ...
            )
        """
        with open(file_name, 'r') as file:
            lines = [line.strip() for line in file if line.strip()]
            n_points = int(lines[0])
            points = []
            for i in range(n_points):
                line_s = re.sub('[()]', '', lines[i + 1])
                xyz = [float(p) for p in line_s.split()]
                points.append(xyz)
        return n_points, np.array(points, dtype=float)

    def get_face_normal_vectors(self, p1, p2, p3, orientation):
        """
        Computes the normal vector for three points on the plane, flipping
        direction if orientation='in' or 'out' doesn't match the z-component.
        """
        v1 = p2 - p1
        v2 = p3 - p1
        v3 = np.cross(v1, v2)
        v3 /= np.linalg.norm(v3)

        # Flip if needed
        if (orientation == 'in' and v3[2] > 0) or (orientation == 'out' and v3[2] < 0):
            v3 = -v3
        return v3

    def get_distance_from_center(self, point):
        """
        Returns the Euclidean distance from the inlet center to 'point'.
        """
        return np.linalg.norm(point - self.center)

    def get_velocity_components(self, speed_scalar, normal_vec):
        """
        Projects a scalar speed onto the inlet's normal direction.
        """
        vx = speed_scalar * normal_vec[0]
        vy = speed_scalar * normal_vec[1]
        vz = speed_scalar * normal_vec[2]
        return vx, vy, vz

    # ------------------------ BASIC PROFILE HELPERS -------------------------
    def plug_profile_speed(self, data_val):
        """
        If CSV data is flow (m^3/s), compute the uniform (plug) velocity = flow / area.
        If CSV data is already velocity (m/s), just return it as is.
        """
        if self.data_type == 'flowrate':
            return data_val / self.compute_cross_sectional_area()
        elif self.data_type == 'velocity':
            # The CSV data is already velocity
            return data_val
        else:
            raise ValueError("data_type must be 'flowRate' or 'velocity'.")

    def parabolic_centerline_speed(self, data_val):
        """
        For a laminar parabolic flow, the centerline velocity = 2 * average velocity.
        - If the CSV data is flow, average velocity = flow / area => centerline = 2 * avg_vel.
        - If the CSV data is velocity, we assume it is the average velocity => centerline = 2 * velocity_in_csv.
          (If it's truly the centerline velocity in the CSV, remove the factor of 2.)
        """
        if self.data_type == 'flowrate':
            cross_area = np.pi * (self.radius * self.scale)**2
            avg_vel = data_val / cross_area
            return 2.0 * avg_vel  # centerline velocity
        elif self.data_type == 'velocity':
            return 2.0 * data_val  # centerline velocity
        else:
            raise ValueError("data_type must be 'flowRate' or 'velocity'.")

    def parabolic_factor(self, dist):
        """
        Returns the radial shape factor for parabolic flow: 1 - (r/R)^2.
        Clamped to 0 for r>R.
        """
        # Ensure we compare dist to the scaled radius
        scaled_radius = self.radius * self.scale
        rel = dist / scaled_radius
        return max(0.0, 1.0 - rel**2)

    def womersley_profile(self, r, t, omega, alpha):
        """
        Compute the Womersley velocity profile at a given radius `r` and time `t`.
        Args:
            r (float): Radial distance from the center (0 <= r <= R).
            t (float): Time (s).
            omega (float): Angular frequency of the pulsatile flow (rad/s).
            alpha (float): Womersley number.
        Returns:
            float: Velocity at radius `r` and time `t`.
        """
        # Compute the complex Womersley profile
        R = self.radius * self.scale  # Scaled radius
        z = 1j**1.5 * alpha * r / R  # Argument for Bessel functions
        z0 = 1j**1.5 * alpha  # Argument for centerline velocity

        # Bessel function ratio
        bessel_ratio = jv(0, z) / jv(0, z0)

        # Oscillatory velocity profile
        v_r_t = (1 - bessel_ratio) * np.exp(1j * omega * t)

        # Return the real part (physical velocity)
        return np.real(v_r_t)

    def generate_time_data(self, directory, time_array, points, normal_vec):
        """
        The main routine for generating velocity files (U_<time>),
        depending on 'plug', 'parabolic', or 'womersley' profile.
        """
        # Compute Womersley parameters if the profile is 'womersley'
        if self.profile == 'womersley':
            cardiac_cycle = self.cardiac_cycle  # Period of the cardiac cycle (s)
            omega = 2 * np.pi / cardiac_cycle  # Angular frequency (rad/s)
            alpha = self.radius * np.sqrt(omega / self.nu)  # Womersley number
            logging.info(f"Womersley number (alpha): {alpha:.4f}")

        for i in range(len(time_array)):
            t = time_array[i]
            y_val = self.csv_vals[i]  # CSV's second column is either flowRate(t) or velocity(t)

            # ---------- Determine a "base speed" -----------
            if self.profile == 'plug':
                speed = self.plug_profile_speed(y_val)

            elif self.profile == 'parabolic':
                speed = self.parabolic_centerline_speed(y_val)

            elif self.profile == 'womersley':
                # Use the Womersley profile to compute the centerline velocity
                speed = self.parabolic_centerline_speed(y_val)  # Approximate centerline velocity

            else:
                raise ValueError("profile must be 'plug', 'parabolic', or 'womersley'.")

            # ---------- Distribute velocity to each point -----------
            vel_x_array, vel_y_array, vel_z_array = [], [], []
            scaled_radius = self.radius * self.scale

            for pt in points:
                pt_scaled = pt * self.scale
                dist = self.get_distance_from_center(pt_scaled)

                if dist <= scaled_radius:
                    if self.profile == 'plug':
                        vx, vy, vz = self.get_velocity_components(speed, normal_vec)
                    elif self.profile == 'parabolic':
                        shape_fac = self.parabolic_factor(dist)
                        local_speed = speed * shape_fac
                        vx, vy, vz = self.get_velocity_components(local_speed, normal_vec)
                    elif self.profile == 'womersley':
                        # Compute the Womersley velocity at this radius and time
                        local_speed = self.womersley_profile(dist, t, omega, alpha)
                        vx, vy, vz = self.get_velocity_components(local_speed, normal_vec)
                else:
                    vx, vy, vz = 0.0, 0.0, 0.0

                vel_x_array.append(vx)
                vel_y_array.append(vy)
                vel_z_array.append(vz)

            out_file = os.path.join(directory, f"U_{t:.6f}")
            self.write_openfoam_data_format(
                out_file, len(points), vel_x_array, vel_y_array, vel_z_array
            )

    def write_openfoam_data_format(self, file_name, n_points, vel_x_array, vel_y_array, vel_z_array):
        """
        Writes velocity vectors into OpenFOAM time-varying format:
            N
            (
              (vx vy vz)
              ...
            )
        """
        with open(file_name, 'w') as file:
            file.write(f"{n_points}\n(\n")
            for vx, vy, vz in zip(vel_x_array, vel_y_array, vel_z_array):
                file.write(f"({vx:.6e} {vy:.6e} {vz:.6e})\n")
            file.write(")\n")

    def run(self):
        """
        Orchestrates:
          1. Read points file.
          2. Compute normal vector of inlet patch.
          3. Read CSV data (flow or velocity).
          4. For each time step, compute velocity distribution and write files.
        """
        # 1) Read the points
        points_file = f"constant/boundaryData/{self.inlet_name}/points"
        if not os.path.isfile(points_file):
            raise FileNotFoundError(f"Points file not found: {points_file}")
        n_points, points = self.read_points_file(points_file)

        if n_points < 3:
            raise ValueError(f"Not enough points in {points_file} to define a plane normal.")

        # 2) Compute normal vector
        orientation = self.kwargs.get("orientation")
        print(f"Orientation: {orientation}")
        idx_rand = np.random.choice(n_points, 3, replace=False)
        p1, p2, p3 = points[idx_rand[0]], points[idx_rand[1]], points[idx_rand[2]]
        normal_vec = self.get_face_normal_vectors(p1, p2, p3, orientation)

        # 3) Read the CSV
        csv_path = os.path.join("constant", "boundaryData", self.inlet_name, self.inlet_data_file)
        if not os.path.isfile(csv_path):
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        times, yval, cycle = self.read_csv_file(csv_path)

        self.times = times
        self.csv_vals = yval
        self.cardiac_cycle = cycle

        logging.info(f"Read {len(times)} time steps from {times[0]} to {times[-1]} (s)")
        logging.info(f"Data type = {self.data_type}")

        # 4) Create a subfolder to hold time-varying velocity files
        parent_dir = os.path.join(
            os.getcwd(),
            "constant",
            "boundaryData",
            self.inlet_name,
            os.path.splitext(self.inlet_data_file)[0]
        )
        os.makedirs(parent_dir, exist_ok=True)

        # Clean old files:
        for oldf in glob.glob(os.path.join(parent_dir, "U_*")):
            os.remove(oldf)

        # 5) Generate the velocity distribution
        self.generate_time_data(parent_dir, times, points, normal_vec)

        print(f"\nInletMapping complete for profile={self.profile}, data_type={self.data_type}")
        print(f" - CSV file: {csv_path}")
        print(f" - Time steps: {len(times)} from {times[0]} to {times[-1]} s")
        print(f" - Computed cycle length: {cycle:.4f} s")
        print(f" - Output: ./{os.path.relpath(parent_dir)}")


# ----------------------- Example Usage ---------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 4:
        print("Usage: python inletMapping.py <inlet_data_file> <data_type> <profile>")
        print("  data_type: 'flowRate' or 'velocity'")
        print("  profile:   'plug', 'parabolic', or 'womersley'")
        sys.exit(1)

    inlet_data_file = sys.argv[1]   # e.g. "myInlet.csv"
    data_type       = sys.argv[2]   # "flowRate" or "velocity"
    profile         = sys.argv[3]   # "plug", "parabolic", "womersley"

    # Example geometry
    center = [0.0, 0.0, 0.0]
    radius = 0.01

    # Instantiate
    inlet_mapping = InletMapping(
        center=center,
        radius=radius,
        inlet_data_file=inlet_data_file,
        inlet_name="inlet",
        data_type=data_type,
        profile=profile,
        scale=1.0,
        orientation="in"
    )
    # Run
    inlet_mapping.run()
