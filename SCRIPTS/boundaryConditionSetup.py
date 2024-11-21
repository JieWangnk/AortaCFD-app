import os 
import sys
from userParameter_HL import *
from SCRIPTS.patchProcessing import *
from SCRIPTS.meshSetup import GeometryAnalyzer



# create the intial condition for the case DIRECTORY/0
class BoundaryConditionSetup():
    def __init__(self, DIRECTORY, STL_FILES, BC_INLET, BC_OUTLET , INITIAL_CONDITION_U, INITIAL_CONDITION_p, INITIAL_CONDITION_K, INITIAL_CONDITION_OMEGA, SIMULATIONTYPE):
        self.DIRECTORY = DIRECTORY
        self.STL_FILES = STL_FILES
        self.BC_INLET = BC_INLET
        self.BC_OUTLET = BC_OUTLET
        self.INITIAL_CONDITION_U = INITIAL_CONDITION_U
        self.INITIAL_CONDITION_p = INITIAL_CONDITION_p
        self.INITIAL_CONDITION_K = INITIAL_CONDITION_K
        self.INITIAL_CONDITION_OMEGA = INITIAL_CONDITION_OMEGA
        self.SIMULATIONTYPE = SIMULATIONTYPE
        print(os.path.join(os.getcwd(),self.DIRECTORY))
        # Create an instance of PatchProcessing
        inlet_radius_calculator = PatchProcessing(self.DIRECTORY, self.STL_FILES,"inlet")
        
        # Get the inlet parameters from inletRadius module
        self.inlet_center, self.inlet_radius, self.inlet_normal = inlet_radius_calculator.calculate_inlet_center_radius()
        # Update the initial condition dictionary
        self.INITIAL_CONDITION_U["inlet_radius"] = self.inlet_radius
        self.INITIAL_CONDITION_U["inlet_center"] = self.inlet_center
        self.INITIAL_CONDITION_U["inlet_normal"] = self.inlet_normal

        # find the main aorta stl file and rest are inlet and outlet patch
        self.MAIN_AORTA_STL = [f for f in self.STL_FILES if "wall" in f][0]
        # find the inlet stl file 
        self.INLET_STL = [f for f in self.STL_FILES if "inlet" in f][0]
        # find all the outlet stl file append in list
        self.OUTLET_STL = []
        for f in self.STL_FILES:
            if "outlet" in f:
                self.OUTLET_STL.append(f)

        if self.BC_INLET == "FIXED_PARABOLIC_VELCOITY":
            self.INLET_TYPE_U = "staticParabolicInletVelocity"
        elif self.BC_INLET == "TIMEVARYING_PARABOLIC_VELOCITY": 
            self.INLET_TYPE_U = "timeVaringParabolicInletVelocity"
        elif self.BC_INLET == "WAVEFORM":
            self.INLET_TYPE_U = "timeVaryingMappedFixedValue"
        elif self.BC_INLET == "TIME_VARYING_MAPPED_FIXED_VALUE":
            self.INLET_TYPE_U = "timeVaryingMappedFixedValue"
        else:
            print("ERROR: inlet_type not found")
            sys.exit()

    def write_U_file(self):
        # write U file based on initial condition 
        template = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v1906                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       volVectorField;
    location    "0";
    object      U;  
}}

dimensions      [0 1 -1 0 0 0 0];

internalField   uniform (0 0 0);

boundaryField
{{
    {inlet_block}
    {outlet_block}
    {wall_aorta_block}
}}
// ************************************************************************* """
            
        if self.INLET_TYPE_U == "staticParabolicInletVelocity":
            inlet_block = """
            {inlet}
        {{  
            type            codedFixedValue;
            value           uniform (0 0 0); // Initial value (will be overwritten by the code)

            code
            #{{
                const vectorField& points = this->db().time().lookupObject<volVectorField>("U").mesh().C().boundaryField()[patch().index()];
                vectorField::subField values = this->patchInternalField();

                const scalar maxVelocity = {inlet_max_velocity};
                const scalar R = {inlet_radius}; // Radius of the pipe

                // User-defined direction vector
                vector direction = vector{inlet_normal}; // Replace with the direction you want

                forAll(values, i)
                {{
                    const vector& pt = points[i];
                    scalar r = sqrt(pt.y()*pt.y() + pt.z()*pt.z());
                    scalar u = maxVelocity*(1 - (r / R)*(r / R));
                    values[i] = direction * u;
                }}

                operator==(values);
            #}};
        }}"""
            
        elif self.INLET_TYPE_U == "timeVaringParabolicInletVelocity":
            inlet_block = """
            {inlet}
        {{
            type            codedFixedValue;
            value           uniform (0 0 0); // Initial value (will be overwritten by the code)

            code
            #{{
                const vectorField& points = this->db().time().lookupObject<volVectorField>("U").mesh().C().boundaryField()[patch().index()];
                vectorField::subField values = this->patchInternalField();

                scalar maxVelocity = {inlet_max_velocity};
                scalar R = {self.inlet_radius}; // Radius of the pipe

                // Heart rate in BPM
                scalar heartRate = {heart_rate}; // for example, 75 beats per minute
                scalar frequencyInHz = heartRate / 60.0;

                // Time varying aspect (positive part of a sine wave)
                scalar omega = 2 * M_PI * frequencyInHz;
                scalar time = this->db().time().value();
                scalar sineValue = std::sin(omega * time);
                scalar amplitude = std::max(0.0, sineValue);

                // User-defined direction vector
                vector direction = vector{self.inlet_normal}; // Replace with the direction you want

                forAll(values, i)
                {{
                const vector& pt = points[i];
                scalar r = sqrt(pt.y()*pt.y() + pt.z()*pt.z());
                scalar u = amplitude * maxVelocity * (1 - (r / R)*(r / R));
                values[i] = direction * u;
                }}

                operator==(values);
            #}};  
        }}"""
            
        elif self.INLET_TYPE_U == "timeVaryingMappedFixedValue":
            inlet_block = """
            inlet
        {{
            type            timeVaryingMappedFixedValue;
            offset          (0 0 0);
            setAverage       off;
        }}"""
        
            
        else:
            print("ERROR: inlet_type not found")
            sys.exit()

        inlet_block = inlet_block.format(inlet=self.INLET_STL.split(".")[0], **self.INITIAL_CONDITION_U)
        
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
            # remove .stl 
            outlet_name = outlet.split(".")[0]
            # append the outlet_block
            outlet_block += outlet_block_template.format(outlet=outlet_name)

        # -------------------------------------------------------------------------- # 
        wall_aorta_block = """
            {wall}
        {{
            type            noSlip;
        }}"""

        wall_aorta_block = wall_aorta_block.format(wall=self.MAIN_AORTA_STL.split(".")[0])
        # write U file
        with open(os.path.join(self.DIRECTORY, "0", "U"), "w") as f:
            f.write(template.format(inlet_block=inlet_block, outlet_block=outlet_block, wall_aorta_block=wall_aorta_block))
#------------------------------------------------------------------------------------------------------------------

    def write_p_file(self):
        # Template for p file
        template = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v1906                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       volScalarField;
    location    "0";
    object      p;  
}}

dimensions      [0 2 -2 0 0 0 0];

internalField   uniform 0;

boundaryField
{{
    {inlet_block}
    {outlet_block}
    {wall_block}
}}
// ************************************************************************* """
        if self.BC_OUTLET == "3EWINDKESSEL":
            # Boundary condition for inlet
            inlet_block = """
            {inlet}
            {{
                type            zeroGradient;
            }}
            """.format(inlet=self.INLET_STL.split(".")[0])

            outlet_block_template = """
            {outlet_name}
            {{
                type            {outlet_type};
                index           {index};
                value           uniform 0;
            }}
            """
            
            outlet_blocks = ""
            # sort self.OUTLET_STL
            for outlet in range(0,len(self.OUTLET_STL)):
                outletName = self.OUTLET_STL[outlet].split(".")[0]
                outlet_type = "WKBC"
                index = outlet
                outlet_blocks += outlet_block_template.format(outlet_name=outletName, outlet_type=outlet_type, index=index)

        elif self.BC_OUTLET == "ZERO_GRADIENT":
            # Boundary condition for inlet
            inlet_block = """
            {inlet}
            {{
                type            zeroGradient;
            }}
            """.format(inlet=self.INLET_STL.split(".")[0])

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

            outlet_blocks = ""
            for outlet in self.OUTLET_STL:
                outletName = outlet.split(".")[0]
                if outlet is self.OUTLET_STL[-1]:
                    outlet_blocks += outlet_block_template_v2.format(outlet_name=outletName)
                else:
                    outlet_blocks += outlet_block_template.format(outlet_name=outletName)

        else:
            print("ERROR: outlet_type not found")
            sys.exit()        

        # Boundary condition for wall
        wall_block = """
            {wall}
            {{
                type            zeroGradient;
            }}
        """.format(wall=self.MAIN_AORTA_STL.split(".")[0])
        

        # Combine all blocks into the final template
        p_file_content = template.format(
            inlet_block=inlet_block,
            outlet_block = outlet_blocks,
            wall_block=wall_block
        )

        # Write to file
        with open(os.path.join(self.DIRECTORY, "0", "p"), "w") as f:
            f.write(p_file_content)
#------------------------------------------------------------------------------------------------------------------

    def write_nut_file(self):
        # Template for nut file
        template = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v1906                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       volScalarField;
    location    "0";
    object      nut;  
}}

dimensions      [0 2 -1 0 0 0 0];

internalField   uniform 0;

boundaryField
{{
    {inlet_block_nut}
    {outlet_block_nut}
    {wall_block_nut}
}}
// ************************************************************************* """
            
            
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
        
        outlet_blocks_nut = ""
        # sort self.OUTLET_STL
        for outlet in range(0, len(self.OUTLET_STL)):
            outletName = self.OUTLET_STL[outlet].split(".")[0]
            outlet_blocks_nut += outlet_block_nut_template.format(outlet_name=outletName)

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
 
        # Combine all blocks into the final template
        nut_file_content = template.format(
            inlet_block_nut = inlet_block_nut,
            outlet_block_nut = outlet_blocks_nut,
            wall_block_nut = wall_block_nut
        )
        # Write to file
        with open(os.path.join(self.DIRECTORY, "0", "nut"), "w") as f:
            f.write(nut_file_content)

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
        
        # Template for k file
        template = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v1906                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\*---------------------------------------------------------------------------*/

FoamFile
{{
    version     2.0;
    format      ascii;
    class       volScalarField;
    location    "0";
    object      k;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

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

// ************************************************************************* """.format(kInlet=self.INITIAL_CONDITION_K['kInlet'], intensityInlet=self.INITIAL_CONDITION_K['intensityInlet'], inlet_blockk=inlet_blockk, outlet_blockk=outlet_blockks, wall_blockk=wall_blockk)
	
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
        
        # Template for omega file
        template = """/*--------------------------------*- C++ -*----------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  11
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/
FoamFile
{{
    format      ascii;
    class       volScalarField;
    object      omega;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

omegaInlet      {omegaInlet};

dimensions      [0 0 -1 0 0 0 0];

internalField   uniform $omegaInlet;

boundaryField
{{
    {inlet_blocko}
    {outlet_blocko}
    {wall_blocko}
}}

// ************************************************************************* """.format(omegaInlet=self.INITIAL_CONDITION_OMEGA['omegaInlet'], inlet_blocko=inlet_blocko, outlet_blocko=outlet_blockos, wall_blocko=wall_blocko)
	
        # Write to file
        with open(os.path.join(self.DIRECTORY, "0", "omega"), "w") as f:
            f.write(template)
            
#------------------------------------------------------------------------------------------------------------------

    
    def write_sampleDict_file(self):
        # Template for sampleDict file
        template = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v1906                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      sampleDict;
}}

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
            f.write(template.format(inlet=self.INLET_STL))    
