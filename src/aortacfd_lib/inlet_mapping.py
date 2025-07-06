import os
import re
import glob
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
        self.log = Logger("inletMapping.log").get_logger()

        # Get all necessary settings from the config dictionary
        self.inlet_settings = self.config['inlet']
        self.geom_settings = self.config['geometry']
        self.phys_settings = self.config['physics']
        self.inlet_name = self.geom_settings['inlet_keywords_ordered']
        self.inlet_data_file = self.inlet_settings['csv_file']
        self.data_type = self.inlet_settings['data_type'].lower().strip()
        self.profile = self.inlet_settings['profile'].lower().strip()
        self.nu = self.phys_settings.get('nu')

        self.center = None
        self.radius = None
        self.cardiac_cycle = None
        
        self.log.info("InletMapping initialized successfully.")

    def run(self):
        """
        Main orchestration method for this class.
        """
        self.log.info("Calculating inlet patch geometry...")
        tri_surface_dir = os.path.join(self.case_directory, "constant", "triSurface")
        stl_files = [f for f in os.listdir(tri_surface_dir) if f.endswith('.stl')]
        
        inlet_patch_processor = PatchProcessing(tri_surface_dir, self.inlet_name)
        scale_factor = self.geom_settings.get('scale_factor', 1e-3)
        self.center, self.radius, inlet_normal = inlet_patch_processor.calculate_inlet_center_radius(scale_factor=scale_factor)
        self.log.info(f"Inlet center: {self.center}, Radius: {self.radius}")

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
            with open(file_name, 'r') as f:
                first_line = f.readline()
                has_header = any(c.isalpha() for c in first_line)
            skiprows = 1 if has_header else 0
            data = np.genfromtxt(file_name, delimiter=',', skip_header=skiprows)
            if data.ndim < 2 or data.shape[1] < 2:
                raise ValueError(f"CSV file {file_name} must have at least 2 columns.")
        except Exception as e:
            raise RuntimeError(f"Error reading CSV file {file_name}: {e}")

        times = data[:, 0]
        yval = data[:, 1]
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

    def _get_velocity_components(self, speed_scalar, normal_vec):
        return speed_scalar * normal_vec

    def compute_cross_sectional_area(self):
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

    def womersley_profile(self, r, t, omega, alpha):
        R = self.radius
        z = 1j**1.5 * alpha * r / R
        z0 = 1j**1.5 * alpha
        bessel_ratio = jv(0, z) / jv(0, z0)
        v_r_t = (1 - bessel_ratio) * np.exp(1j * omega * t)
        return np.real(v_r_t)

    def _generate_time_data(self, parent_directory, time_array, csv_values, points, normal_vec):
        if self.profile == 'womersley':
            if not self.nu or self.nu <= 0:
                raise ValueError("Womersley profile requires a positive kinematic viscosity (nu) in config.")
            omega = 2 * np.pi / self.cardiac_cycle
            alpha = self.radius * np.sqrt(omega / self.nu)

        for i in range(len(time_array)):
            t = time_array[i]
            y_val = csv_values[i]
            speed = self.parabolic_centerline_speed(y_val) if self.profile != 'plug' else self.plug_profile_speed(y_val)

            velocities = []
            for pt in points:
                dist = self._get_distance_from_center(pt)
                if dist <= self.radius:
                    if self.profile == 'plug':
                        local_speed = speed
                    elif self.profile == 'parabolic':
                        shape_fac = self.parabolic_factor(dist)
                        local_speed = speed * shape_fac
                    elif self.profile == 'womersley':
                        local_speed = self.womersley_profile(dist, t, omega, alpha)
                    velocities.append(self._get_velocity_components(local_speed, normal_vec))
                else:
                    velocities.append((0.0, 0.0, 0.0))

            time_dir_path = os.path.join(parent_directory, f"{t:.6f}")
            os.makedirs(time_dir_path, exist_ok=True)
            out_file_path = os.path.join(time_dir_path, "U")
            self._write_openfoam_data_format(out_file_path, len(points), velocities)

    def _write_openfoam_data_format(self, file_name, n_points, velocities):
        with open(file_name, 'w') as file:
            file.write(f"{n_points}\n(\n")
            for v in velocities:
                file.write(f"({v[0]:.6e} {v[1]:.6e} {v[2]:.6e})\n")
            file.write(")\n")