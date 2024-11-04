import numpy as np
import re
import os
import glob
from scipy.special import jv
from userParameter_HL import *
from userParameter_LL import *

class InletMapping:
    def __init__(self, center, radius, inlet_data_file, inlet_name, scale=1e0,profile='parabolic', **kwargs):
        self.center = np.array(center)
        self.radius = radius
        self.inlet_data_file = inlet_data_file
        self.inlet_name = inlet_name
        self.scale = scale
        self.profile = profile
        self.kwargs = kwargs

    def get_face_normal_vectors(self, p1, p2, p3, orientation='in'):
        v1 = p2 - p1
        v2 = p3 - p1
        v3 = np.cross(v1, v2)
        v3 = v3 / np.linalg.norm(v3)
        if orientation == 'in' and v3[2] > 0 or orientation == 'out' and v3[2] < 0:
            v3 = -v3
        return v3

    def read_csv_file(self, file_name):
        data = np.genfromtxt(file_name, delimiter=',', skip_header=0)
        time = data[:, 0]
        vel = np.transpose(data[:, 1])
        return time, vel

    def get_velocity_components(self, vel, face_normal_vectors):
        vel_x = vel * face_normal_vectors[0]
        vel_y = vel * face_normal_vectors[1]
        vel_z = vel * face_normal_vectors[2]
        return vel_x, vel_y, vel_z

    def read_points_file(self, file_name):
        with open(file_name, 'r') as file:
            lines = [line.rstrip() for line in file if line.strip()]
            n_points = int(lines[0])
            points = []
            for i in range(n_points):
                line_s = re.sub('[()]', '', lines[i + 1])
                point = [float(p) for p in line_s.split()]
                if point:
                    points.append(point)
        return n_points, points

    def get_distance_from_center(self, point):
        return np.linalg.norm(self.center - point)

    def get_velocity_components_parabolic(self, vel, face_normal_vectors, dist):
        factor = (1 - (dist / self.radius)**2)
        return vel * face_normal_vectors * factor

    def write_openfoam_data_format_parabolic(self, file_name, n_points, vel_x_array, vel_y_array, vel_z_array):
        with open(file_name, 'w') as file:
            file.write(f"{n_points}\n(\n")
            for vel_x, vel_y, vel_z in zip(vel_x_array, vel_y_array, vel_z_array):
                formatted_line = "({:.12f} {:.12f} {:.12f})\n".format(float(vel_x), float(vel_y), float(vel_z))
                file.write(formatted_line)
            file.write(")\n")

    def womersley_velocity_profile(self, r, t, R, rho, nu, delta_P, HR):
        omega = 2 * np.pi * int(HR) / 60  # Convert HR to angular frequency
        alpha = R * np.sqrt(omega / float(nu))
        i = complex(0, 1)
        gamma = i ** 1.5 * alpha
        exponent = i * omega * t

        # Compute Bessel function terms using jv
        numerator = jv(0, gamma * (r / R))
        denominator = jv(0, gamma)

        # Compute complex velocity
        u_complex = (int(delta_P) / (i * omega * int(rho))) * (1 - numerator / denominator) * np.exp(exponent)

        # Return the real part
        return np.real(u_complex)



    def write_out(self, inlet_data_file, inlet_name, time, vel, n_points, points, normal_vector, scale= 1e0, profile='parabolic', **kwargs):
        directory = f"constant/boundaryData/{inlet_name}/{inlet_data_file.split('.')[0]}"
        parent_dir = os.getcwd()
        directory = os.path.join(parent_dir, directory)
        os.makedirs(directory, exist_ok=True)

        for files in glob.glob(directory + '/*'):
            os.remove(files)
        
        if time.size > 0:  # Check if time is not empty
            for t in time:
                # print("Processing time:", t)  # Print current time being processed
                vel_x_array, vel_y_array, vel_z_array = [], [], []
                for point in points:
                    point = np.array(point, dtype=float) * scale
                    dist = self.get_distance_from_center(point)
                    if dist <= self.radius:
                        if profile == 'parabolic':
                            t_idx = np.where(time == t)[0]
                            if len(t_idx) > 0:  # Check if index exists
                                velocity_magnitude = vel[t_idx[0]]  # Access velocity magnitude
                                # print("Velocity magnitude at time", t, ":", velocity_magnitude)
                                # print("Normal vector:", normal_vector)
                                # print("Distance from center:", dist)
                                vel_x, vel_y, vel_z = self.get_velocity_components_parabolic(
                                    velocity_magnitude, normal_vector, dist)
                        elif profile == 'womersley':
                            # Womersley parameters
                            R = self.radius
                            rho = RHO #kwargs.get('rho', 1060)  # Blood density in kg/m^3
                            nu = NU  #kwargs.get('mu', 0.004)   # Blood dynamic viscosity in Pa·s
                            delta_P = WOMERSLEY_PARAMETERS["DELTA_P"]  # Pressure gradient amplitude
                            HR = WOMERSLEY_PARAMETERS["HEART_RATE"]      # Heart rate in beats per minute

                            # Calculate radial position normalized to inlet radius
                            r = dist
                            velocity_magnitude = self.womersley_velocity_profile(r, t, R, rho, nu, delta_P, HR)
                            vel_x, vel_y, vel_z = self.get_velocity_components(
                                velocity_magnitude, normal_vector)
                        else:
                            raise ValueError("Invalid profile type. Choose 'parabolic' or 'womersley'.")
                        vel_x_array.append(vel_x)
                        vel_y_array.append(vel_y)
                        vel_z_array.append(vel_z)
                    else:
                        vel_x_array.append(0)
                        vel_y_array.append(0)
                        vel_z_array.append(0)
                self.write_openfoam_data_format_parabolic(
                    os.path.join(directory, f'U_{t:.6f}'), str(n_points), vel_x_array, vel_y_array, vel_z_array)

    def run(self):
        # Read the velocity data from the csv file in the INLET folder
        times, velocities = self.read_csv_file(
            'constant/boundaryData/{}/{}'.format(self.inlet_name, self.inlet_data_file))
        n_points, points = self.read_points_file(
            'constant/boundaryData/{}/points'.format(self.inlet_name))
        indices = np.random.randint(0, len(points), size=3)

        p1, p2, p3 = points[indices[0]], points[indices[1]], points[indices[2]]
        normal_vector = self.get_face_normal_vectors(
            np.asarray(p1), np.asarray(p2), np.asarray(p3), 'out')
        self.write_out(self.inlet_data_file, self.inlet_name,
                       times, velocities, n_points, points, normal_vector, profile=self.profile,scale=self.scale, **self.kwargs)

if __name__ == "__main__":
    import sys
    inlet_data_file = sys.argv[1]
    profile = sys.argv[2]  # 'parabolic' or 'womersley'
    # Additional parameters can be passed via kwargs
    center = [-0.02256496, -0.0363579, -0.014821885]
    radius = 0.014
    
    # Example of passing additional parameters for Womersley profile
    kwargs = {}
    if profile == 'womersley':
        kwargs['rho'] = 1060         # Blood density (kg/m^3) 
        kwargs['mu'] = 0.004         # Blood dynamic viscosity (Pa·s)
        kwargs['delta_P'] = 1        # Pressure gradient amplitude
        kwargs['HR'] = 75            # Heart rate (beats per minute)
        kwargs['scale'] = 1e0        # Scaling factor if needed
    else:
        kwargs['scale'] = 1e0        # Scaling factor if needed
    inlet_mapping = InletMapping(center=center,radius= radius,inlet_data_file=inlet_data_file, inlet_name="inlet", profile=profile,scale=1)
    inlet_mapping.run()
    print("Inlet mapping completed.")
