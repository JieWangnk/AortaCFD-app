import os
from SCRIPTS.logger import Logger

class SimulationSetup:
    def __init__(self, DIRECTORY, SIMULATION_CONTROL, OPENFOAM_VERSION, log_file="simulationSetup.log"):
        self.DIRECTORY = DIRECTORY
        self.SIMULATION_CONTROL = SIMULATION_CONTROL
        self.openfoam_version = OPENFOAM_VERSION  # Store the OpenFOAM version
        self.logger = Logger(log_file).get_logger()

    def write_controlDict(self, filename="controlDict", cardiac_period=None, number_of_cycles=None):
        """
        Writes the controlDict file for the simulation.
        Dynamically sets endTime if cardiac_period and number_of_cycles are provided.
        """
        template = '''/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  {openfoam_version}                              |
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

maxCo           1;

functions
{{
    {function_block}
}}

// ************************************************************************* //
'''
        # Debugging: Log cardiac_period and number_of_cycles
        self.logger.info(f"Received cardiac_period: {cardiac_period}, number_of_cycles: {number_of_cycles}")
       
        # Dynamically calculate endTime
        if self.SIMULATION_CONTROL["controlDict"]["endTime"] is None:
            if number_of_cycles is not None and cardiac_period is not None:
                self.SIMULATION_CONTROL["controlDict"]["endTime"] = cardiac_period * number_of_cycles
            else:
                self.SIMULATION_CONTROL["controlDict"]["endTime"] = 1

        # Ensure the system folder exists
        system_folder = os.path.join(self.DIRECTORY, "system")
        os.makedirs(system_folder, exist_ok=True)

        # Remove the existing controlDict file if it exists
        filepath = os.path.join(system_folder, filename)
        if os.path.exists(filepath):
            self.logger.info(f"Removing existing {filename} file.")
            os.remove(filepath)

        # Create the function block
        function_block = ""
        for f in self.SIMULATION_CONTROL["controlDict"]["functionList"]:
            template_v2 = """
            #includeFunc    {function}"""
            function_block += template_v2.format(function=f)

        # Write the controlDict file
        try:
            self.logger.info(f"Writing controlDict to: {filepath}")
            with open(filepath, 'w') as f:
                f.write(template.format(
                    openfoam_version=self.openfoam_version,
                    function_block=function_block,
                    **self.SIMULATION_CONTROL["controlDict"]
                ))
            self.logger.info(f"Successfully wrote {filename} to {filepath}.")
        except Exception as e:
            self.logger.error(f"Failed to write {filename} file: {e}")
            raise