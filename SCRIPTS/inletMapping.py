import numpy as np
import re
import os
import glob
from scipy.special import jv
from userParameter_HL import *
from userParameter_LL import *

class InletMapping:
    def __init__(self, center, radius, inlet_data_file, inlet_name, scale=1e0, profile='parabolic', **kwargs):
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
        if (orientation == 'in' and v3[2] > 0) or (orientation == 'out' and v3[2] < 0):
            v3 = -v3
        return v3

    def read_csv_file(self, file_name):
        data = np.genfromtxt(file_name, delimiter=',', skip_header=0)
        time = data[:, 0]
        vel = data[:, 1]
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

    def get_velocity_components_plug(self, vel, face_normal_vectors):
        return vel * face_normal_vectors

    def write_openfoam_data_format(self, file_name, n_points, vel_x_array, vel_y_array, vel_z_array):
        with open(file_name, 'w') as file:
            file.write(f"{n_points}\n(\n")
            for vel_x, vel_y, vel_z in zip(vel_x_array, vel_y_array, vel_z_array):
                formatted_line = "({:.12f} {:.12f} {:.12f})\n".format(float(vel_x), float(vel_y), float(vel_z))
                file.write(formatted_line)
            file.write(")\n")

    @staticmethod
    def womersley_velocity_profile_half_sine(t, r, R, rho, nu, delta_P_max,Vmax, HR):
        """
        Calculate the Womersley velocity profile at a given time and radial position.
        """
        # Convert heart rate to angular frequency
        f = HR / 60.0
        omega = 2 * np.pi * f

        # Calculate Womersley number
        alpha = R * np.sqrt(omega / nu)
        if alpha > 0.1:
            # Compute complex parameters
            i = complex(0, 1)
            gamma = alpha * np.exp(-i * np.pi / 4)
            numerator = jv(0, gamma * (r / R))
            denominator = jv(0, gamma)
            # Compute delta_P using V_max
            delta_P = Vmax * omega * rho * np.abs(denominator / (denominator - 1))
            if np.abs(denominator) < 1e-10:
                raise ValueError("Denominator in Bessel function computation is too small.")
            U = (delta_P / (omega * rho)) * np.abs(1 - numerator / denominator)
        else:
            # Simplified parabolic profile
            U = delta_P_max / (4 * nu) * (1 - (r / R)**2)

        # Time-dependent term
        sin_omega_t = np.sin(omega * t)
        heaviside = np.heaviside(sin_omega_t, 0)
        time_factor = sin_omega_t * heaviside

        # Compute velocity
        u = time_factor * U
        return u, alpha

    def write_out(self, inlet_data_file, inlet_name,n_points, points, normal_vector, scale=1.0, profile='parabolic', **kwargs):
        if profile == 'womersley':
            directory = f"constant/boundaryData/{inlet_name}/BPM{HEART_RATE}"
        else:
            directory = f"constant/boundaryData/{inlet_name}/{inlet_data_file.split('.')[0]}"
        parent_dir = os.getcwd()
        directory = os.path.join(parent_dir, directory)
        os.makedirs(directory, exist_ok=True)

        for file in glob.glob(directory + '/*'):
            os.remove(file)
        
        if profile == 'parabolic':
            # Read the velocity data from the csv file in the INLET folder
            times, velocities = self.read_csv_file('constant/boundaryData/{}/{}'.format(self.inlet_name, self.inlet_data_file))
            if times.size > 0:
                for t in times:
                    vel_x_array, vel_y_array, vel_z_array = [], [], []
                    for point in points:
                        point = np.array(point, dtype=float) * scale
                        dist = self.get_distance_from_center(point)
                        if dist <= self.radius:
                            t_idx = np.where(times == t)[0]
                            if len(t_idx) > 0:
                                velocity_magnitude = velocities[t_idx[0]]
                                vel_x, vel_y, vel_z = self.get_velocity_components_parabolic(
                                    velocity_magnitude, normal_vector, dist)
                                vel_x_array.append(vel_x)
                                vel_y_array.append(vel_y)
                                vel_z_array.append(vel_z)
                        else:
                            # Point is outside the vessel radius; set velocity to zero
                            vel_x_array.append(0.0)
                            vel_y_array.append(0.0)
                            vel_z_array.append(0.0)
                    # Write the velocities for this time step
                    self.write_openfoam_data_format(
                        os.path.join(directory, 'U_'+f'{t:.6f}'),
                        n_points,
                        vel_x_array,
                        vel_y_array,
                        vel_z_array
                    )
        elif profile == 'womersley':
            # Womersley parameters
            R = self.radius
            rho = eval(RHO)
            nu = eval(NU)
            delta_P = eval(WOMERSLEY_PARAMETERS['SYSTOLIC_PRESSURE']) - eval(WOMERSLEY_PARAMETERS['DIASTOLIC_PRESSURE'])
            vmax = eval(WOMERSLEY_PARAMETERS['MAX_VELOCITY'])
            HR = eval(HEART_RATE)

            newTime = np.linspace(0, 60/HR, 100)
            velocity_magnitude_list = []

            for t in newTime:
                vel_x_array, vel_y_array, vel_z_array = [], [], []

                # Calculate the velocity profile at center of the vessel
                center_velocity, alpha = self.womersley_velocity_profile_half_sine(
                    t=t, r=0, R=R, rho=rho, nu=nu, delta_P_max=delta_P,Vmax=vmax, HR=HR)
                velocity_magnitude_list.append(center_velocity)

                for point in points:
                    point = np.array(point, dtype=float) * scale
                    dist = self.get_distance_from_center(point)
                    r = dist
                    if dist <= self.radius:
                        velocity_magnitude,alpha  = self.womersley_velocity_profile_half_sine(
                            t=t, r=r, R=R, rho=rho, nu=nu, delta_P_max=delta_P,Vmax=vmax, HR=HR)
                        vel_x, vel_y, vel_z = self.get_velocity_components(
                            velocity_magnitude, normal_vector)
                        vel_x_array.append(vel_x)
                        vel_y_array.append(vel_y)
                        vel_z_array.append(vel_z)
                    else:
                        velocity_magnitude = 0.0
                        # Point is outside the vessel radius; set velocity to zero
                        vel_x_array.append(0.0)
                        vel_y_array.append(0.0)
                        vel_z_array.append(0.0)
                    # return t and velocity magnitude as inlet velocity profile csv file
                    
                # Write the velocities for this time step
                self.write_openfoam_data_format(
                    os.path.join(directory, 'U_'+f'{t:.6f}'),
                    n_points,
                    vel_x_array,
                    vel_y_array,
                    vel_z_array
                )
                # Write the velocity profile to a csv file
                csv_file_path = os.path.join("constant/boundaryData/", inlet_name, f"BPM{HEART_RATE}.csv")
                with open(csv_file_path, 'w') as file:
                    for i in range(len(newTime)):
                        file.write(f"{newTime[i]},{velocity_magnitude_list[i]}\n")
                    print(f"Velocity profile saved to {csv_file_path}")
                print("Womersley velocity profile generated: alpha = ", alpha)
            else:
                raise ValueError("Invalid profile type. Choose 'parabolic', 'plug' or 'womersley'.")

        elif profile == 'plug':
            times, velocities = self.read_csv_file(
                'constant/boundaryData/{}/{}'.format(self.inlet_name, self.inlet_data_file))
            if times.size > 0:
                for t in times:
                    vel_x_array, vel_y_array, vel_z_array = [], [], []
                    for point in points:
                        point = np.array(point, dtype=float) * scale
                        dist = self.get_distance_from_center(point)
                        t_idx = np.where(times == t)[0]
                        if len(t_idx) > 0:
                            velocity_magnitude = velocities[t_idx[0]]
                            vel_x, vel_y, vel_z = self.get_velocity_components_plug(
                                velocity_magnitude, normal_vector)
                            vel_x_array.append(vel_x)
                            vel_y_array.append(vel_y)
                            vel_z_array.append(vel_z)

                    # Write the velocities for this time step
                    self.write_openfoam_data_format(
                        os.path.join(directory, 'U_' + f'{t:.6f}'),
                        n_points,
                        vel_x_array,
                        vel_y_array,
                        vel_z_array
                    )



    def run(self):
        n_points, points = self.read_points_file(
            'constant/boundaryData/{}/points'.format(self.inlet_name))
        indices = np.random.randint(0, len(points), size=3)

        p1, p2, p3 = points[indices[0]], points[indices[1]], points[indices[2]]
        normal_vector = self.get_face_normal_vectors(
            np.asarray(p1), np.asarray(p2), np.asarray(p3), 'out')
        self.write_out(self.inlet_data_file, self.inlet_name, n_points, points, normal_vector, profile=self.profile, scale=self.scale, **self.kwargs)

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
        kwargs['nu'] = 4e-6          # Blood kinematic viscosity (m^2/s)
        kwargs['delta_P'] = 1        # Pressure gradient amplitude
        kwargs['HR'] = 75            # Heart rate (beats per minute)
    inlet_mapping = InletMapping(center=center, radius=radius, inlet_data_file=inlet_data_file, inlet_name="inlet", profile=profile, scale=1, **kwargs)
    inlet_mapping.run()
    print("Inlet mapping completed.")
