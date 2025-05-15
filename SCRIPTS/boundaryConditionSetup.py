import os 
import re
import sys
from config import CONFIG 
from SCRIPTS.patchProcessing import *

# create the intial condition for the case DIRECTORY/0
class BoundaryConditionSetup():
    def __init__(self, DIRECTORY, STL_FILES, BC_INLET, BC_OUTLET, INITIAL_CONDITION_U, INITIAL_CONDITION_p, INITIAL_CONDITION_K, INITIAL_CONDITION_OMEGA, SIMULATIONTYPE,openfoam_version):
        self.DIRECTORY = DIRECTORY
        self.STL_FILES = STL_FILES
        self.BC_INLET = BC_INLET
        self.BC_OUTLET = BC_OUTLET
        self.INITIAL_CONDITION_U = INITIAL_CONDITION_U
        self.INITIAL_CONDITION_p = INITIAL_CONDITION_p
        self.INITIAL_CONDITION_K = INITIAL_CONDITION_K
        self.INITIAL_CONDITION_OMEGA = INITIAL_CONDITION_OMEGA
        self.SIMULATIONTYPE = SIMULATIONTYPE
        self.openfoam_version = openfoam_version  # Store the OpenFOAM version
        
        # Create an instance of PatchProcessing
        inlet_radius_calculator = PatchProcessing(os.path.join(self.DIRECTORY, "constant", "triSurface"), self.STL_FILES,"inlet")
        
        # Get the inlet parameters from inletRadius module
        self.inlet_center, self.inlet_radius, self.inlet_normal = inlet_radius_calculator.calculate_inlet_center_radius()
        # Update the initial condition dictionary
        self.INITIAL_CONDITION_U["inlet_radius"] = self.inlet_radius
        self.INITIAL_CONDITION_U["inlet_center"] = self.inlet_center
        self.INITIAL_CONDITION_U["inlet_normal"] = self.inlet_normal

        # Find the main aorta STL file
        self.MAIN_AORTA_STL = os.path.basename([f for f in self.STL_FILES if "wall" in f][0])

        # Find the inlet STL file
        self.INLET_STL = os.path.basename([f for f in self.STL_FILES if "inlet" in f][0])

        # Find all the outlet STL files and append them to a list
        self.OUTLET_STL = sorted(
            [os.path.basename(f) for f in self.STL_FILES if "outlet" in f],
            key=lambda x: int(re.findall(r"\d+", x)[0])
        )

        if self.BC_INLET == "TIMEVARYING":
            self.INLET_TYPE_U = "timeVaryingMappedFixedValue"
        elif self.BC_INLET == "STEADYSTATE":
            self.INLET_TYPE_U = "timeVaryingMappedFixedValue"
        else:
            print("ERROR: inlet_type not found")
            sys.exit()
    
    def _get_foam_file_header(self, object_class, object_name):
        """
        Generate the FoamFile header dynamically based on the OpenFOAM version.
        """
        return f"""/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  {self.openfoam_version}
     \\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       {object_class};
    location    "0";
    object      {object_name};
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
"""

    def write_U_file(self):
        """
        Write the U file dynamically based on OpenFOAM version.
        """
        foam_file_header = self._get_foam_file_header("volVectorField", "U")
        if self.INLET_TYPE_U == "timeVaryingMappedFixedValue":
            inlet_block = """
        {inlet}
        {{
            type            timeVaryingMappedFixedValue;
            offset          (0 0 0);
            setAverage      off;
        }}
    """.format(inlet=self.INLET_STL.split(".")[0])
        else:
            print("ERROR: inlet_type not found")
            sys.exit()

        # ------------------------------------------------------------------------ #
        if self.BC_OUTLET == "ZERO_GRADIENT":
            outlet_block_template = """
        {outlet}
        {{
            type            zeroGradient;
        }}
    """
        elif self.BC_OUTLET == "3EWINDKESSEL":
            outlet_block_template = """
        {outlet}
        {{
            type            pressureInletOutletVelocity;
            phi             phi;
            value           uniform (0 0 0);
        }}
    """
        else:
            print("ERROR: outlet_type not found")
            sys.exit()

        outlet_block = ""
        for outlet in self.OUTLET_STL:
            outlet_name = outlet.split(".")[0]
            outlet_block += outlet_block_template.format(outlet=outlet_name)

        # -------------------------------------------------------------------------- #
        wall_aorta_block = """
        {wall}
        {{
            type            noSlip;
        }}
    """.format(wall=self.MAIN_AORTA_STL.split(".")[0])

        # Template for the U file
        template = f"""{foam_file_header}

    dimensions      [0 1 -1 0 0 0 0];

    internalField   uniform (0 0 0);

    boundaryField
    {{
        {inlet_block}
        {outlet_block}
        {wall_aorta_block}
    }}
    // ************************************************************************* //
    """

        # Write the U file
        with open(os.path.join(self.DIRECTORY, "0", "U"), "w") as f:
            f.write(template)
#------------------------------------------------------------------------------------------------------------------

    def write_p_file(self):
        """
        Write the p file dynamically based on OpenFOAM version.
        """
        # Boundary condition for inlet
        inlet_block = """
    {inlet}
    {{
        type            zeroGradient;
    }}
    """.format(inlet=self.INLET_STL.split(".")[0])  # Extract only the file name without path

        # Boundary condition for outlets
        outlet_block_template = """
    {outlet_name}
    {{
        type            zeroGradient;
    }}
    """
        outlet_block_template_v2 = """
    {outlet_name}
    {{
        type            fixedValue;
        value           uniform 0; 
    }}
    """

        outlet_block = ""
        for outlet in self.OUTLET_STL:
            outlet_name = outlet.split(".")[0]  # Extract only the file name without path
            if outlet == self.OUTLET_STL[-1]:  # Special handling for the last outlet
                outlet_block += outlet_block_template_v2.format(outlet_name=outlet_name)
            else:
                outlet_block += outlet_block_template.format(outlet_name=outlet_name)

        # Boundary condition for wall
        wall_block = """
    {wall}
    {{
        type            zeroGradient;
    }}
    """.format(wall=self.MAIN_AORTA_STL.split(".")[0])  # Extract only the file name without path

        foam_file_header = self._get_foam_file_header("volScalarField", "p")
        template = f"""{foam_file_header}

dimensions      [0 2 -2 0 0 0 0];

internalField   uniform 0;

boundaryField
{{
    {inlet_block}
    {outlet_block}
    {wall_block}
}}
// ************************************************************************* """
        
        # Write to file
        with open(os.path.join(self.DIRECTORY, "0", "p"), "w") as f:
            f.write(template)

#------------------------------------------------------------------------------------------------------------------

    def write_nut_file(self):
        """
        Write the nut file dynamically based on OpenFOAM version.
        """
                   
        # Boundary condition for inlet
        inlet_block_nut = """
        {inlet}
        {{
            type            zeroGradient;
        }}""".format(inlet=self.INLET_STL.split(".")[0])

        outlet_block_nut_template = """
        {outlet_name}
        {{
            type            zeroGradient;
        }}"""
        
        outlet_block_nut = ""
        # sort self.OUTLET_STL
        for outlet in range(0, len(self.OUTLET_STL)):
            outletName = self.OUTLET_STL[outlet].split(".")[0]
            outlet_block_nut += outlet_block_nut_template.format(outlet_name=outletName)

        # Boundary condition for wall
        
        if self.SIMULATIONTYPE == "RAS":
            # Boundary condition for wall
            wall_block_nut = """
        {wall}
        {{
            type            nutkWallFunction;
            value           uniform 0;
        }}""".format(wall=self.MAIN_AORTA_STL.split(".")[0]) 
                        
          
        else:
            # Boundary condition for wall
            wall_block_nut = """    
        {wall}
        {{
            type            zeroGradient;
        }}""".format(wall=self.MAIN_AORTA_STL.split(".")[0])
 
        foam_file_header = self._get_foam_file_header("volScalarField", "nut")
        template = f"""{foam_file_header}
dimensions      [0 2 -1 0 0 0 0];

internalField   uniform 0;

boundaryField
{{
    {inlet_block_nut}
    {outlet_block_nut}
    {wall_block_nut}
}}
// ************************************************************************* 
"""
        # Write to file
        with open(os.path.join(self.DIRECTORY, "0", "nut"), "w") as f:
            f.write(template)

#------------------------------------------------------------------------------------------------------------------
            
    def write_k_file(self):
        if 'kInlet' not in self.INITIAL_CONDITION_K or 'intensityInlet' not in self.INITIAL_CONDITION_K:
            print("ERROR: Required keys 'kInlet' and 'intensityInlet' not found in INITIAL_CONDITION_K dictionary.")
            return

        # Boundary condition for inlet
        inlet_blockk = """    {inlet}
{{
    type            turbulentIntensityKineticEnergyInlet;
    intensity       $intensityInlet;
    value           uniform $kInlet;
}}
""".format(inlet=self.INLET_STL.split(".")[0])

        outlet_block_template = """    {outlet_name}
{{
    type            inletOutlet;
    inletValue      uniform $kInlet;
    value           uniform $kInlet;
}}
"""
        outlet_blockks = ""
        # sort self.OUTLET_STL
        for outlet in range(0, len(self.OUTLET_STL)):
            outletName = self.OUTLET_STL[outlet].split(".")[0]
            outlet_blockks += outlet_block_template.format(outlet_name=outletName)

        # Boundary condition for wall
        wall_blockk = """    {wall}
{{
    type            kqRWallFunction;
    value           uniform $kInlet;
}}
""".format(wall=self.MAIN_AORTA_STL.split(".")[0])
        
        foam_file_header = self._get_foam_file_header("volScalarField", "k")
        # Template for k file
        template = """{header}

kInlet          {kInlet};

intensityInlet  {intensityInlet};

dimensions      [0 2 -2 0 0 0 0];

internalField   uniform $kInlet;

boundaryField
{{
    {inlet_blockk}
    {outlet_blockk}
    {wall_blockk}
}}

// ************************************************************************* """.format(header=foam_file_header, kInlet=self.INITIAL_CONDITION_K['kInlet'], intensityInlet=self.INITIAL_CONDITION_K['intensityInlet'], inlet_blockk=inlet_blockk, outlet_blockk=outlet_blockks, wall_blockk=wall_blockk)
        # Write to file
        with open(os.path.join(self.DIRECTORY, "0", "k"), "w") as f:
            f.write(template)

#------------------------------------------------------------------------------------------------------------------
            
    def write_omega_file(self):
        # Boundary condition for inlet
        inlet_blocko = """    {inlet}
{{
        type            fixedValue;
        value           uniform $omegaInlet;
}}
""".format(inlet=self.INLET_STL.split(".")[0])

        outlet_block_template = """    {outlet_name}
{{
        type            inletOutlet;
        inletValue      uniform $omegaInlet;
        value           uniform $omegaInlet;
}}
"""
        outlet_blockos = ""
        # sort self.OUTLET_STL
        for outlet in range(0, len(self.OUTLET_STL)):
            outletName = self.OUTLET_STL[outlet].split(".")[0]
            outlet_blockos += outlet_block_template.format(outlet_name=outletName)

        # Boundary condition for wall
        wall_blocko = """    {wall}
{{
        type            omegaWallFunction;
        value           uniform $omegaInlet;
}}
""".format(wall=self.MAIN_AORTA_STL.split(".")[0])
        
        foam_file_header = self._get_foam_file_header("volScalarField", "omega")
        # Template for omega file
        template = """{header}

omegaInlet      {omegaInlet};

dimensions      [0 0 -1 0 0 0 0];

internalField   uniform $omegaInlet;

boundaryField
{{
    {inlet_blocko}
    {outlet_blocko}
    {wall_blocko}
}}

// ************************************************************************* """.format(header=foam_file_header ,omegaInlet=self.INITIAL_CONDITION_OMEGA['omegaInlet'], inlet_blocko=inlet_blocko, outlet_blocko=outlet_blockos, wall_blocko=wall_blocko)
	
        # Write to file
        with open(os.path.join(self.DIRECTORY, "0", "omega"), "w") as f:
            f.write(template)
            
#------------------------------------------------------------------------------------------------------------------
    
    def write_sampleDict_file(self):

        # FoamFile header
        foam_file_header = self._get_foam_file_header("dictionary", "sampleDict")
        # Template for sampleDict file
        template = """{header}

interpolationScheme cellPoint;
setFormat       raw;
surfaceFormat   foam;

type            surfaces;

fields          ();
surfaces
(
        triSurfaceSampling    {{
        type        triSurfaceMesh;  
        surface     {inlet}; 
        source      cells;  
        interpolate true;
    }}
);

// ************************************************************************* //
"""
        # write sampleDict file
        with open(os.path.join(self.DIRECTORY, "system", "sampleDict"), "w") as f:
            f.write(template.format(header = foam_file_header,inlet=self.INLET_STL))
