import os
from SCRIPTS.logger import Logger

class PhysicalPropertiesWriter:
    def __init__(self, DIRECTORY, NU, RHO, SIMULATIONTYPE, OPENFOAM_VERSION, log_file="physicalPropertiesSetup.log"):
        self.DIRECTORY = DIRECTORY
        self.NU = NU
        self.RHO = RHO
        self.SIMULATIONTYPE = SIMULATIONTYPE
        self.openfoam_version = OPENFOAM_VERSION  # Store the OpenFOAM version
        self.logger = Logger(log_file).get_logger()

    def _get_foam_file_header(self, object_name):
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
    class       dictionary;
    location    "constant";
    object      {object_name};
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
"""

    def write_transportProperties_file(self):
        """
        Write the transportProperties file dynamically based on OpenFOAM version.
        """
        foam_file_header = self._get_foam_file_header("transportProperties")
        content = f"""{foam_file_header}

transportModel  Newtonian;

nu              [0 2 -1 0 0 0 0] {self.NU};

rho             [1 -3 0 0 0 0 0] {self.RHO};

// ************************************************************************* //
"""
        filepath = os.path.join(self.DIRECTORY, "constant", "transportProperties")
        try:
            with open(filepath, "w") as f:
                f.write(content)
        except Exception as e:
            self.logger.error(f"Failed to write transportProperties file: {e}")
            raise

    def write_momentumProperties_file(self):
        """
        Write the momentumProperties file dynamically based on OpenFOAM version and simulation type.
        """
        if self.SIMULATIONTYPE == "RAS":
            SIMULATION_BLOCK = """simulationType  RAS;

RAS
{
    model           kOmegaSST;

    turbulence      on;

    printCoeffs     on;
}
"""
        elif self.SIMULATIONTYPE == "laminar":
            SIMULATION_BLOCK = """simulationType  laminar;"""
        elif self.SIMULATIONTYPE == "LES":
            SIMULATION_BLOCK = """simulationType LES;

LES
{
    model           WALE;

    turbulence      on;

    printCoeffs     on;

    delta           cubeRootVol;

    cubeRootVolCoeffs
    {
        deltaCoeff      1;
    }

    smoothCoeffs
    {
        delta           cubeRootVol;
        cubeRootVolCoeffs
        {
            deltaCoeff      1;
        }

        maxDeltaRatio   1.1;
    }
}
"""
        else:
            self.logger.error("Invalid simulation type.")
            raise ValueError("Invalid simulation type.")

        foam_file_header = self._get_foam_file_header("momentumTransport")
        content = f"""{foam_file_header}

{SIMULATION_BLOCK}

// ************************************************************************* //
"""
        filepath = os.path.join(self.DIRECTORY, "constant", "momentumTransport")
        try:
            with open(filepath, "w") as f:
                f.write(content)
        except Exception as e:
            self.logger.error(f"Failed to write momentumProperties file: {e}")
            raise

