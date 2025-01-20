import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from SCRIPTS.patchProcessing import PatchProcessing

class wk_Setup:
    """
    A class to compute and write 3-element Windkessel properties for outlets,
    replicating the approach from the MATLAB script. The first three outlets
    share 'percentage' of the total flow (split by area ratios), while the
    fourth outlet gets the remaining flow.

    Attributes:
        DIRECTORY (str): Path to the OpenFOAM case directory.
        STL_FILES (list): List of STL filenames in the geometry.
        GEOMETRY_SCALE (float): Scaling factor (e.g., 1e-3 if geometry is in mm).
        WK_SETTING (dict): Dictionary with Windkessel settings like
            "percentage", "systolic_pressure", "diastolic_pressure".
        CARDIAC_CYCLE (float): Duration of one cardiac cycle in seconds.
        INLET_DATA_FILE (str): CSV file (time, flow) for the inlet.
    """

    def __init__(
        self,
        DIRECTORY,
        GEOMETRY_SCALE,
        STL_FILES,
        WK_SETTING,
        CARDIAC_CYCLE,
        INLET_DATA_FILE,
        DATA_TYPE
    ):
        self.DIRECTORY = DIRECTORY
        self.STL_FILES = STL_FILES
        self.GEOMETRY_SCALE = GEOMETRY_SCALE
        self.WK_SETTING = WK_SETTING
        self.CARDIAC_CYCLE = CARDIAC_CYCLE
        self.INLET_DATA_FILE = INLET_DATA_FILE
        self.DATA_TYPE = DATA_TYPE

    def write_WK_Setup(self, filename="windkesselProperties"):
        """
        Main method to:
          1) Compute patch areas for 'outlet1'..'outlet4'
          2) Read the inlet flow CSV
          3) Split flow among outlets
          4) Compute Windkessel parameters R1, R2, C
          5) Write the final dictionary to `constant/windkesselProperties`
             and `constant/windkesselProperties_backup`
        """
        # ------------------------- 1) Patch Areas -------------------------
        # In your MATLAB code, you used RCCA, LCCA, LSCA, and DAO.
        # Here we map them as: outlet1 -> RCCA, outlet2 -> LCCA,
        #                       outlet3 -> LSCA, outlet4 -> DAO (descending aorta).
        # If your geometry differs, rename accordingly.
        area_inlet = PatchProcessing(self.DIRECTORY, self.STL_FILES, "inlet").calculate_surface_area(scale_factor=self.GEOMETRY_SCALE)
        area_out1 = PatchProcessing(self.DIRECTORY, self.STL_FILES, "outlet1").calculate_surface_area(scale_factor=self.GEOMETRY_SCALE)
        area_out2 = PatchProcessing(self.DIRECTORY, self.STL_FILES, "outlet2").calculate_surface_area(scale_factor=self.GEOMETRY_SCALE)
        area_out3 = PatchProcessing(self.DIRECTORY, self.STL_FILES, "outlet3").calculate_surface_area(scale_factor=self.GEOMETRY_SCALE)
        area_out4 = PatchProcessing(self.DIRECTORY, self.STL_FILES, "outlet4").calculate_surface_area(scale_factor=self.GEOMETRY_SCALE)

        # -------------- 2) Read the inlet flow CSV & Check --------------
        inlet_csv_path = os.path.join("constant", "boundaryData", "inlet", self.INLET_DATA_FILE)
        if not os.path.isfile(inlet_csv_path):
            raise FileNotFoundError(f"Could not find inlet data file: {inlet_csv_path}")

        # We expect the CSV to have columns: time, flowRate or velocity
        # check if the file has headers row 
        with open(inlet_csv_path, 'r') as f:
            first_line = f.readline()
            # if the first line contains headers "string" then skip the first line
            if "time" in first_line.lower() or "flow" in first_line.lower() or "velocity" in first_line.lower():
                Q_data = np.loadtxt(inlet_csv_path, delimiter=",", skiprows=1)
            else:
                Q_data = np.loadtxt(inlet_csv_path, delimiter=",")
        
        # if the data type is flowRate
        if self.DATA_TYPE == "flowRate":
            times = Q_data[:, 0]
            flow_inlet = Q_data[:, 1]  # m^3/s ?
        # if the data type is velocity
        elif self.DATA_TYPE == "velocity":
            times = Q_data[:, 0]
            # Assuming the inlet area is 1 m^2
            flow_inlet = Q_data[:, 1] * area_inlet  # m^3/s
        else:
            raise ValueError(f"Unknown data type: {self.DATA_TYPE}. Use 'flowRate' or 'velocity'.")
        
        # -------------- 3) Split Flow Among Outlets --------------
        # 'percentage' fraction is distributed among the first 3 outlets by their area ratio
        # The last outlet gets the remainder (1 - percentage).
        # Example: if percentage=70 => 70% goes to 3 branches, 30% goes to outlet4
        percentage = self.WK_SETTING["percentage"]  # e.g. 70
        perc_branches = percentage / 100.0
        # sum of first 3 outlets
        area_3branches = (area_out1 + area_out2 + area_out3)

        # If your geometry doesn't have these 3 outlets, area_3branches might be zero
        if area_3branches <= 0:
            raise ValueError("Sum of areas for outlet1/outlet2/outlet3 is zero or negative.")

        # Each branch ratio
        ratio1 = area_out1 / area_3branches
        ratio2 = area_out2 / area_3branches
        ratio3 = area_out3 / area_3branches

        # Q[ :, 0..3 ] = flows for outlets 1..4
        Q_out = np.zeros((len(flow_inlet), 4))
        Q_out[:, 0] = flow_inlet * ratio1 * perc_branches
        Q_out[:, 1] = flow_inlet * ratio2 * perc_branches
        Q_out[:, 2] = flow_inlet * ratio3 * perc_branches
        Q_out[:, 3] = flow_inlet * (1.0 - perc_branches)

        # -------------- 4) Compute Windkessel Parameters --------------
        # The approach in your MATLAB code:
        #   1) c = a / [2 sqrt(A * 1e6 / pi)]^b
        #   2) Rtotal = meanPressure / meanFlow
        #   3) R1 = rho * c / A
        #   4) R2 = Rtotal - R1
        #   5) C = tau / Rtotal
        #   MAP = (SP + DP)/2  => convert to [Pa] by x 133.33
        # Hard-coded constants
        SP = self.WK_SETTING["systolic_pressure"]   # e.g. 120 [mmHg]
        DP = self.WK_SETTING["diastolic_pressure"]  # e.g. 80  [mmHg]
        MAP = (SP + DP) / 2.0  # [mmHg]
        mP = MAP * 133.33      # [Pa], 1 mmHg = 133.33 Pa

        a = 13.3
        b = 0.3
        tau = 1.92
        rho = 1060.0  # blood density [kg/m^3]

        # Mean flows for each outlet
        mean_flows = np.mean(Q_out, axis=0)  # array of 4 elements
        # Convert area from m^2 to the same units used in your formula:
        #   c = a / (2 sqrt(A*1e6/pi))^b
        # If your area is already in [m^2], multiply by 1e6 to get [mm^2], etc.
        # "A" in your MATLAB code was in [m^2] or [mm^2]? We replicate the same approach:
        # If in MATLAB you had: c = a/(2*sqrt(Arcca*10^6/pi))^b
        # that implies A was in [m^2], but you multiplied by 1e6 => [mm^2]
        # We'll do the same:
        areas = np.array([area_out1, area_out2, area_out3, area_out4])
        c_vals = a / (2.0 * np.sqrt((areas * 1e6) / np.pi))**b  # array of 4

        R_total = np.zeros(4)
        R1 = np.zeros(4)
        R2 = np.zeros(4)
        C_wk = np.zeros(4)

        # Avoid divide-by-zero if any mean_flows are 0
        for i in range(4):
            if mean_flows[i] <= 1e-15:
                # If flow is essentially zero, R_total = large, but let's handle gracefully
                R_total[i] = 1e15
            else:
                R_total[i] = mP / mean_flows[i]
            R1[i] = rho * c_vals[i] / areas[i]
            R2[i] = R_total[i] - R1[i]
            if R2[i] < 0:
                # If the user inputs produce negative R2, it implies c or flow is inconsistent
                R2[i] = 0.0  # or raise a warning
            C_wk[i] = tau / R_total[i]

        # -------------- 5) Create the Output Dictionary Content --------------
        template = """/*--------------------------------*- C++ -*----------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  10
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/
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

        # We'll label the outlets consistent with your usage
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

        # Final text for windkesselProperties
        final_content = template.format(outlet_block=outlet_block)

        # -------------- Write to File(s) --------------
        out_dir = os.path.join("constant")
        os.makedirs(out_dir, exist_ok=True)

        main_file_path = os.path.join(out_dir, filename)
        backup_file_path = os.path.join(out_dir, filename + "_backup")

        with open(main_file_path, 'w') as f_main:
            f_main.write(final_content)
        with open(backup_file_path, 'w') as f_bak:
            f_bak.write(final_content)

        # -------------- 6) Plot Flow for Debugging --------------
        plt.figure()
        plt.plot(times, flow_inlet, label='Q-inlet')
        plt.plot(times, Q_out[:,0], label='Q-outlet1')
        plt.plot(times, Q_out[:,1], label='Q-outlet2')
        plt.plot(times, Q_out[:,2], label='Q-outlet3')
        plt.plot(times, Q_out[:,3], label='Q-outlet4')
        plt.legend()
        plt.xlabel('Time (s)')
        plt.ylabel('Flow Rate (m^3/s)')
        plt.title('Flow Splitting for Windkessel')
        plot_name = f"{filename}_flowSplit.png"
        plt.savefig(os.path.join("constant", plot_name))
        plt.close()

        print(f"Windkessel properties have been written to:\n  {main_file_path}\n  {backup_file_path}")
        print(f"Flow-split plot saved as: constant/{plot_name}")

