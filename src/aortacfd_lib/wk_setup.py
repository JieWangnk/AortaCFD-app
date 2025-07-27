import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader

from .utils.patch_processing import PatchProcessing
from .utils.logger import Logger

class WkSetup:
    """
    Computes and writes 3-element Windkessel properties for all outlets
    dynamically based on the provided configuration.
    """

    def __init__(self, config: dict, stl_files: list, case_directory: str, cardiac_cycle: float):
        """The constructor is simplified to take the config and key context items."""
        self.config = config
        self.stl_files = stl_files
        self.case_dir = case_directory
        self.cardiac_cycle = cardiac_cycle
        self.log = Logger("wk_setup").get_logger()
        
        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_path))

        self.geom_settings = self.config['geometry']
        self.inlet_settings = self.config['inlet']
        self.outlet_settings = self.config['outlets']
        self.wk_model_settings = self.outlet_settings['windkessel_settings']

    def execute(self, filename="windkesselProperties"):
        """Main method to compute and write Windkessel properties."""
        self.log.info("Calculating Windkessel properties for all outlets...")
        
        tri_surface_dir = os.path.join(self.case_dir, "constant", "triSurface")
        scale_factor = self.geom_settings.get('scale_factor', 1e-3)
        
        inlet_patch_name = self.geom_settings['inlet_keywords_ordered']
        area_inlet = PatchProcessing(tri_surface_dir, inlet_patch_name).calculate_surface_area(scale_factor=scale_factor)

        outlet_patches = self.geom_settings['outlet_keywords_ordered']
        outlet_areas = {name: PatchProcessing(tri_surface_dir, name).calculate_surface_area(scale_factor=scale_factor) for name in outlet_patches}

        inlet_csv_path = os.path.join("data", "CAD", self.geom_settings['case_name'], self.inlet_settings['csv_file'])
        times, flow_inlet = self._read_inlet_flow(inlet_csv_path, self.inlet_settings['data_type'], area_inlet)

        flow_split_ratios = self.wk_model_settings['flow_split']
        num_outlets = len(outlet_patches)
        Q_out = np.zeros((len(flow_inlet), num_outlets))
        
        for i, name in enumerate(outlet_patches):
            if name not in flow_split_ratios:
                raise ValueError(f"Flow split for outlet '{name}' not defined in boundary_conditions.json")
            Q_out[:, i] = flow_inlet * flow_split_ratios[name]

        SP = self.wk_model_settings["systolic_pressure"]
        DP = self.wk_model_settings["diastolic_pressure"]
        rho = self.config['physics']['rho']
        mP = ((SP + DP) / 2.0) * 133.33

        a = 13.3; b = 0.3; tau = 1.92
        
        mean_flows = np.mean(Q_out, axis=0)
        areas_np = np.array([outlet_areas[name] for name in outlet_patches])
        
        R_total = np.divide(mP, mean_flows, out=np.full_like(mean_flows, 1e15), where=mean_flows>1e-15)
        c_vals = a / (2.0 * np.sqrt((areas_np * 1e6) / np.pi))**b
        R1 = rho * c_vals / areas_np
        R2 = R_total - R1
        R2[R2 < 0] = 0.0
        C_wk = tau / R_total

        template = self.jinja_env.get_template('windkesselProperties.tpl')
        
        outlets_context = []
        for i, name in enumerate(outlet_patches):
            outlets_context.append({
                "name": name,
                "C": f"{C_wk[i]:.4e}",
                "R": f"{R2[i]:.4e}",
                "Z": f"{R1[i]:.4e}",
                "index": i
            })
        
        context = {
            "version": self.config['openfoam_version'],
            "outlets": outlets_context
        }

        output_path = os.path.join(self.case_dir, "constant", filename)
        with open(output_path, 'w') as f:
            f.write(template.render(context))
        self.log.info(f"Wrote Windkessel properties to {output_path}")

        self._generate_debug_plot(times, flow_inlet, Q_out, outlet_patches, output_path)

    # --- FILLED IN HELPER FUNCTION ---
    def _read_inlet_flow(self, file_path, data_type, inlet_area):
        """Reads the inlet flow CSV and converts to flow rate if necessary."""
        if not os.path.isfile(file_path):
            self.log.error(f"Could not find inlet data file: {file_path}")
            raise FileNotFoundError(f"Could not find inlet data file: {file_path}")

        with open(file_path, 'r') as f:
            first_line = f.readline()
            if "time" in first_line.lower() or "flow" in first_line.lower() or "velocity" in first_line.lower():
                Q_data = np.loadtxt(file_path, delimiter=",", skiprows=1)
            else:
                Q_data = np.loadtxt(file_path, delimiter=",")

        if data_type == "flowRate":
            times = Q_data[:, 0]
            flow_inlet = Q_data[:, 1]
        elif data_type == "velocity":
            times = Q_data[:, 0]
            flow_inlet = Q_data[:, 1] * inlet_area
        else:
            self.log.error(f"Unknown data type: {data_type}. Use 'flowRate' or 'velocity'.")
            raise ValueError(f"Unknown data type: {data_type}. Use 'flowRate' or 'velocity'.")
        
        return times, flow_inlet

    # --- FILLED IN HELPER FUNCTION ---
    def _generate_debug_plot(self, times, q_inlet, q_out_matrix, outlet_names, output_path):
        """Creates a plot showing how the inlet flow was split among the outlets."""
        plt.figure(figsize=(10, 6))
        plt.plot(times, q_inlet, label='Q-inlet', linewidth=2)
        for i, name in enumerate(outlet_names):
            plt.plot(times, q_out_matrix[:, i], label=f'Q-{name}')
        plt.legend()
        plt.xlabel('Time (s)')
        plt.ylabel('Flow Rate (m^3/s)')
        plt.title('Flow Splitting for Windkessel Outlets')
        plt.grid(True)
        plot_name = os.path.basename(output_path) + "_flowSplit.png"
        plt.savefig(os.path.join(os.path.dirname(output_path), plot_name))
        plt.close()
        self.log.info(f"Generated debug plot: {plot_name}")