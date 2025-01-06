import os 
import sys
import numpy as np
import matplotlib.pyplot as plt 
from SCRIPTS.patchProcessing import *
from userParameter_HL import *
from userParameter_LL import *

class wk_Setup:
    def __init__(self,DIRECTORY, STL_FILES, WK_SETTING):
        self.DIRECTORY = DIRECTORY
        self.STL_FILES = STL_FILES
        self.WK_SETTING = WK_SETTING

    def write_WK_Setup(self, filename="windkesselProperties"):
        template = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  4.0                                   |
|   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
|    \\/     M anipulation  |                                                 |
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

#------------------------------------------------------------------
        # calcuate the patch area 
        inlet = PatchProcessing(self.DIRECTORY, self.STL_FILES, "inlet").calculate_surface_area()
        outlet1 = PatchProcessing(self.DIRECTORY, self.STL_FILES, "outlet1").calculate_surface_area()
        outlet2 = PatchProcessing(self.DIRECTORY, self.STL_FILES, "outlet2").calculate_surface_area()
        outlet3 = PatchProcessing(self.DIRECTORY, self.STL_FILES, "outlet3").calculate_surface_area()
        outlet4 = PatchProcessing(self.DIRECTORY, self.STL_FILES, "outlet4").calculate_surface_area()
        # covert the area to gemetery scale
        inlet = inlet * eval(GEOMETRY_SCALE) * eval(GEOMETRY_SCALE)
        outlet1 = outlet1 * eval(GEOMETRY_SCALE) * eval(GEOMETRY_SCALE)
        outlet2 = outlet2 * eval(GEOMETRY_SCALE) * eval(GEOMETRY_SCALE)
        outlet3 = outlet3 * eval(GEOMETRY_SCALE) * eval(GEOMETRY_SCALE)
        outlet4 = outlet4 * eval(GEOMETRY_SCALE) * eval(GEOMETRY_SCALE)
        print(outlet1,outlet2,outlet3,outlet4)
        # Accessing the WK_SETTING dictionary values
        percentage = eval(self.WK_SETTING["percentage"])
        SP = eval(SYSTOLIC_PRESSURE)
        DP = eval(DIASTOLIC_PRESSURE)
        HR = [int(hr) for hr in str(HEART_RATE).split()]
        
        perc_branches = percentage / 100 
        PD = SP - DP   # Calculate PD 41
        for i in HR:
            filename = f'./constant/boundaryData/inlet/BPM{i}.csv'
            U = np.loadtxt(filename, delimiter=',')  # Load as array, inlet velocity profile
            #Calculate the flow rate at the inlet
            Q_orig = np.zeros((len(U), 2))
            Q_orig[:, 0] = U[:, 0]
            Q_orig[:, 1] = U[:, 1] * inlet
            Q_in = Q_orig[:, :]
            fileout_OF = f'{SP}bp{DP}WK_Coef_SP{percentage}_HR{i}'
            # check if file exists and if so, delete it
    
            if os.path.exists(fileout_OF):
                os.remove(fileout_OF)    

            # CALCULATE WK COEFFICIENTS
            A = np.array([outlet1, outlet2, outlet3, outlet4])
            A_branches = np.sum(A[:3])

            flowSplit_branches = A[:3] / A_branches
            Q = np.zeros((len(Q_in), 4))
            for j in range(3):
                Q[:, j] = Q_in[:, 1] * flowSplit_branches[j] * perc_branches
            Q[:, 3] = Q_in[:, 1] * (1 - perc_branches)

            plt.plot(Q_in[:, 1])
            for j in range(4):
               plt.plot(Q[:, j])
            plt.legend(['Q-inlet', 'Q-rcca', 'Q-lcca', 'Q-lsca', 'Q-DAo'])
            # save the plot in constant/
            plt.savefig(f'./constant/{fileout_OF}.png')    
            plt.close()        
            # Constants
            branch_names = ["outlet1", "outlet2", "outlet3", "outlet4"]
            a = 13.3
        b = 0.3
        tau = 1.92
        BloodDens = 1060
        MAP = (SP + DP) / 2
        mP = MAP * 133.33

        mean_Q = np.mean(Q, axis=0)
        c = a / (2 * np.sqrt(A * 10**6 / np.pi))**b
        R_total = mP / mean_Q
        R_1 = BloodDens * c / A
        R_2 = R_total - R_1
        C = tau / R_total
#------------------------------------------------------------------
        # Create the function block
        # self.OUTLET_STL = []
        # for f in self.STL_FILES:
        #     if "outlet" in f:
        #         self.OUTLET_STL.append(f)      

        outlet_block_template = """
{outlet_name}
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

        outlet_block = ""
        # sort self.OUTLET_STL
        for outlet in range(len(branch_names)):
            outletName = branch_names[outlet]
            index = outlet
            outlet_block += outlet_block_template.format(
        outlet_name=outletName,
        index=index,
        C_val="{:.4e}".format(C[outlet]),
        R_val="{:.4e}".format(R_2[outlet]),
        Z_val="{:.4e}".format(R_1[outlet])
        )
        # Use the template to fill in the variables and write to the file with tow copy
        with open(os.path.join("constant", "windkesselProperties"), 'w') as f:
            f.write(template.format(outlet_block=outlet_block))
        # write the second copy as backup
        with open(os.path.join("constant", "windkesselProperties_backup"), 'w') as f:
            f.write(template.format(outlet_block=outlet_block))
        print("windkesselProperties file has been written")

