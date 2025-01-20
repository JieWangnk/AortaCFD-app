import os 

class SimulationSetup:
    def __init__(self,DIRECTORY ,SIMULATION_CONTROL):
        self.DIRECTORY = DIRECTORY
        self.SIMULATION_CONTROL = SIMULATION_CONTROL

    def write_controlDict(self, filename="controlDict"):
        template = '''/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  5                                     |
|   \\\\  /    A nd           | Web:      www.OpenFOAM.org                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      controlDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

application     solverFoam;

startFrom       {startFrom};

startTime       {startTime};

stopAt          {stopAt};

endTime         {endTime};

deltaT          {deltaT};

writeControl    {writeControl};

writeInterval   {writeInterval};

purgeWrite      0;

writeFormat     binary;

writePrecision  6;

writeCompression off;

timeFormat      general;

timePrecision   6;

runTimeModifiable {runTimeModifiable};

adjustTimeStep  true;

maxCo   1;

functions
{{
    {function_block}
}}

// ************************************************************************* //
'''
        function_block = ""
        # Create the function block
        for f in self.SIMULATION_CONTROL["controlDict"]["functionList"]:
            template_v2 = """
            #includeFunc    {function}"""
            function_block += template_v2.format(function=f)

        # Use the template to fill in the variables and write to the file
        with open(os.path.join(self.DIRECTORY,"system","controlDict"), 'w') as f:
            f.write(template.format(function_block=function_block,**self.SIMULATION_CONTROL["controlDict"]))
        print("controlDict file has been written")
        
