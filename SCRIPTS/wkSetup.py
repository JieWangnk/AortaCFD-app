import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from SCRIPTS.patchProcessing import PatchProcessing
from SCRIPTS.logger import Logger

class wk_Setup:
    """
    A class to compute and write 3-element Windkessel properties for outlets,
    replicating the approach from the MATLAB script.
    """

    def __init__(
        self,
        DIRECTORY,
        GEOMETRY_SCALE,
        STL_FILES,
        WK_SETTING,
        CARDIAC_CYCLE,
        INLET_DATA_FILE,
        DATA_TYPE,
        OPENFOAM_VERSION,
        log_file="wkSetup.log"
    ):
        self.DIRECTORY = DIRECTORY
        self.STL_FILES = STL_FILES
        self.GEOMETRY_SCALE = GEOMETRY_SCALE
        self.WK_SETTING = WK_SETTING
        self.CARDIAC_CYCLE = CARDIAC_CYCLE
        self.INLET_DATA_FILE = INLET_DATA_FILE
        self.DATA_TYPE = DATA_TYPE
        self.openfoam_version = OPENFOAM_VERSION  # Store the OpenFOAM version
        self.logger = Logger(log_file).get_logger()

    def write_WK_Setup(self, filename="windkesselProperties"):
        """
        Main method to compute and write Windkessel properties.
        """
        try:
            # ------------------------- 1) Patch Areas -------------------------
            
            area_inlet = PatchProcessing(os.path.join(self.DIRECTORY, "constant", "triSurface"), self.STL_FILES, "inlet").calculate_surface_area(scale_factor=self.GEOMETRY_SCALE)
            area_out1 = PatchProcessing(os.path.join(self.DIRECTORY, "constant", "triSurface"), self.STL_FILES, "outlet1").calculate_surface_area(scale_factor=self.GEOMETRY_SCALE)
            area_out2 = PatchProcessing(os.path.join(self.DIRECTORY, "constant", "triSurface"), self.STL_FILES, "outlet2").calculate_surface_area(scale_factor=self.GEOMETRY_SCALE)
            area_out3 = PatchProcessing(os.path.join(self.DIRECTORY, "constant", "triSurface"), self.STL_FILES, "outlet3").calculate_surface_area(scale_factor=self.GEOMETRY_SCALE)
            area_out4 = PatchProcessing(os.path.join(self.DIRECTORY, "constant", "triSurface"), self.STL_FILES, "outlet4").calculate_surface_area(scale_factor=self.GEOMETRY_SCALE)

            # -------------- 2) Read the inlet flow CSV & Check --------------
            inlet_csv_path = os.path.join(self.DIRECTORY, "constant", "boundaryData", "inlet", self.INLET_DATA_FILE)
            if not os.path.isfile(inlet_csv_path):
                self.logger.error(f"Could not find inlet data file: {inlet_csv_path}")
                raise FileNotFoundError(f"Could not find inlet data file: {inlet_csv_path}")


            with open(inlet_csv_path, 'r') as f:
                first_line = f.readline()
                if "time" in first_line.lower() or "flow" in first_line.lower() or "velocity" in first_line.lower():
                    Q_data = np.loadtxt(inlet_csv_path, delimiter=",", skiprows=1)
                else:
                    Q_data = np.loadtxt(inlet_csv_path, delimiter=",")

            if self.DATA_TYPE == "flowRate":
                times = Q_data[:, 0]
                flow_inlet = Q_data[:, 1]
            elif self.DATA_TYPE == "velocity":
                times = Q_data[:, 0]
                flow_inlet = Q_data[:, 1] * area_inlet
            else:
                self.logger.error(f"Unknown data type: {self.DATA_TYPE}. Use 'flowRate' or 'velocity'.")
                raise ValueError(f"Unknown data type: {self.DATA_TYPE}. Use 'flowRate' or 'velocity'.")

            # -------------- 3) Split Flow Among Outlets --------------
            
            percentage = self.WK_SETTING["percentage"]
            perc_branches = percentage / 100.0
            area_3branches = (area_out1 + area_out2 + area_out3)

            if area_3branches <= 0:
                self.logger.error("Sum of areas for outlet1/outlet2/outlet3 is zero or negative.")
                raise ValueError("Sum of areas for outlet1/outlet2/outlet3 is zero or negative.")

            ratio1 = area_out1 / area_3branches
            ratio2 = area_out2 / area_3branches
            ratio3 = area_out3 / area_3branches

            Q_out = np.zeros((len(flow_inlet), 4))
            Q_out[:, 0] = flow_inlet * ratio1 * perc_branches
            Q_out[:, 1] = flow_inlet * ratio2 * perc_branches
            Q_out[:, 2] = flow_inlet * ratio3 * perc_branches
            Q_out[:, 3] = flow_inlet * (1.0 - perc_branches)

            # -------------- 4) Compute Windkessel Parameters --------------
            
            SP = self.WK_SETTING["systolic_pressure"]
            DP = self.WK_SETTING["diastolic_pressure"]
            MAP = (SP + DP) / 2.0
            mP = MAP * 133.33

            a = 13.3
            b = 0.3
            tau = 1.92
            rho = 1060.0

            mean_flows = np.mean(Q_out, axis=0)
            areas = np.array([area_out1, area_out2, area_out3, area_out4])
            c_vals = a / (2.0 * np.sqrt((areas * 1e6) / np.pi))**b

            R_total = np.zeros(4)
            R1 = np.zeros(4)
            R2 = np.zeros(4)
            C_wk = np.zeros(4)

            for i in range(4):
                if mean_flows[i] <= 1e-15:
                    R_total[i] = 1e15
                else:
                    R_total[i] = mP / mean_flows[i]
                R1[i] = rho * c_vals[i] / areas[i]
                R2[i] = R_total[i] - R1[i]
                if R2[i] < 0:
                    R2[i] = 0.0
                C_wk[i] = tau / R_total[i]

            outlet_block_template = """{outlet_name}
{{
    C                   {C_val};
    R                   {R_val};
    Z                   {Z_val};
    outIndex            {index};     
    FDM_order           3;      
    Flowrate_threeStepBefore      0;    
    Flowrate_twoStepBefore        0;
    Flowrate_oneStepBefore        0;
    Pressure_twoStepBefore        0;
    Pressure_oneStepBefore        0;
    Pressure_start                0;
}}
"""

            outlet_names = ["outlet1", "outlet2", "outlet3", "outlet4"]
            outlet_block = ""
            for i, name in enumerate(outlet_names):
                c_str = f"{C_wk[i]:.4e}"
                r_str = f"{R2[i]:.4e}"
                z_str = f"{R1[i]:.4e}"
                outlet_block += outlet_block_template.format(
                    outlet_name=name,
                    C_val=c_str,
                    R_val=r_str,
                    Z_val=z_str,
                    index=i
                )

            # -------------- 5) Create the Output Dictionary Content --------------
            template = f"""/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  {self.openfoam_version}
     \\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     4.0;
    format      ascii;
    class       dictionary;
    location    "constant";
    object      windkesselProperties;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

{outlet_block}

// ************************************************************************* //
"""
            # -------------- Write to File(s) --------------
            out_dir = os.path.join(self.DIRECTORY, "constant")
            os.makedirs(out_dir, exist_ok=True)

            main_file_path = os.path.join(out_dir, filename)
            backup_file_path = os.path.join(out_dir, filename + "_backup")

            with open(main_file_path, 'w') as f_main:
                f_main.write(template)
            with open(backup_file_path, 'w') as f_bak:
                f_bak.write(template)

            # -------------- 6) Plot Flow for Debugging --------------
            plt.figure()
            plt.plot(times, flow_inlet, label='Q-inlet')
            plt.plot(times, Q_out[:, 0], label='Q-outlet1')
            plt.plot(times, Q_out[:, 1], label='Q-outlet2')
            plt.plot(times, Q_out[:, 2], label='Q-outlet3')
            plt.plot(times, Q_out[:, 3], label='Q-outlet4')
            plt.legend()
            plt.xlabel('Time (s)')
            plt.ylabel('Flow Rate (m^3/s)')
            plt.title('Flow Splitting for Windkessel')
            plot_name = f"{filename}_flowSplit.png"
            plt.savefig(os.path.join(out_dir, plot_name))
            plt.close()

        except Exception as e:
            self.logger.error(f"Error in write_WK_Setup: {e}")
            raise

