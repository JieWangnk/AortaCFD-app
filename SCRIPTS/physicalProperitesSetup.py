import os

class PhysicalPropertiesWriter:
    def __init__(self,DIRECTORY ,NU, RHO,SIMULATIONTYPE):
        self.DIRECTORY = DIRECTORY
        self.NU = NU
        self.RHO = RHO
        self.SIMULATIONTYPE = SIMULATIONTYPE
            

    def write_transportProperties_file(self):
        content = """/*--------------------------------*- C++ -*----------------------------------*\\
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
    location    "constant";
    object      transportProperties;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

transportModel  Newtonian;

nu              [0 2 -1 0 0 0 0] {nu_val};

rho             [1 -3 0 0 0 0 0] {rho_val};

// ************************************************************************* //""".format(nu_val=self.NU, rho_val=self.RHO)
        
        with open(os.path.join(self.DIRECTORY,"constant","transportProperties"), "w") as f:
            f.write(content)
        print("transportProperties file has been written.")

    def write_momentumProperties_file(self):
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
            SIMULATION_BLOCK= """simulationType  laminar;"""
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

    PrandtlCoeffs
    {
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

        Cdelta          0.158;
    }

    vanDriestCoeffs
    {
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

        Aplus           26;
        Cdelta          0.158;
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
            print("Invalid simulation type.")
            return
        content = """/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  8
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "constant";
    object      momentumTransport;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

{CODE_BLOCK}


// ************************************************************************* //""".format(CODE_BLOCK = SIMULATION_BLOCK)
        
        with open(os.path.join(self.DIRECTORY,"constant","momentumTransport"), "w") as f:
            f.write(content)
        print("momentumProperties file has been written.")

