import os
from typing import Any

class FvSolutionWriter:
    def __init__(self, DIRECTORY, SIMULATIONTYPE, SIMULATIONPERFORMANCE, OUTTER_CORR, OPENFOAM_VERSION):
        self.DIRECTORY = DIRECTORY
        self.SIMULATIONTYPE = SIMULATIONTYPE
        self.SIMULATIONPERFORMANCE = SIMULATIONPERFORMANCE
        self.OUTTER_CORR = OUTTER_CORR
        self.openfoam_version = OPENFOAM_VERSION  # Store the OpenFOAM version

    def write_fvSolution_file(self):
        filepath = os.path.join(self.DIRECTORY, "system", "fvSolution")

        with open(filepath, 'w') as f:
            if self.SIMULATIONTYPE == 'laminar':
                if self.SIMULATIONPERFORMANCE == "high":
                    f.write(self._get_laminar_high_fvSolution())
                elif self.SIMULATIONPERFORMANCE == "medium":
                    f.write(self._get_laminar_medium_fvSolution())
                elif self.SIMULATIONPERFORMANCE == "low":
                    f.write(self._get_laminar_low_fvSolution())
                else:
                    print("Invalid simulation performance.")
            elif self.SIMULATIONTYPE == 'LES':
                if self.SIMULATIONPERFORMANCE == "high":
                    f.write(self._get_LES_high_fvSolution())
                elif self.SIMULATIONPERFORMANCE == "medium":
                    f.write(self._get_LES_medium_fvSolution())
                elif self.SIMULATIONPERFORMANCE == "low":
                    f.write(self._get_LES_low_fvSolution())
                else:
                    print("Invalid simulation performance.")
            elif self.SIMULATIONTYPE == 'RAS':
                f.write(self._get_RAS_fvSolution())
            else:
                print("Invalid simulation type.")

    def _get_foam_file_header(self):
        """
        Generate the FoamFile header dynamically based on the OpenFOAM version.
        """
        return f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  {self.openfoam_version}                              |
|   \\\\  /    A nd           | Web:      www.OpenFOAM.org                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSolution;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
"""

    def _get_laminar_high_fvSolution(self):
        laminar_fvSolution = f"""{self._get_foam_file_header()}

solvers
{{
    p
    {{
        solver          GAMG;
        tolerance       1e-06;
        relTol          0.01;
        smoother        GaussSeidel;
        cacheAgglomeration true;
        nCellsInCoarsestLevel 10;
        agglomerator    faceAreaPair;
        mergeLevels     1;
    }}

    pFinal
    {{
        solver          GAMG;
        tolerance       1e-06;
        relTol          0;
        smoother        GaussSeidel;
        cacheAgglomeration true;
        nCellsInCoarsestLevel 10;
        agglomerator    faceAreaPair;
        mergeLevels     1;
    }}

    "(U|k|nuTilda)"
    {{
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-05;
        relTol          0.1;
    }}

    "(U|k|nuTilda)Final"
    {{
        $U;
        tolerance       1e-05;
        relTol          0;
    }}
}}

PIMPLE
{{
    momentumPredictor   no;
    nOuterCorrectors    {self.OUTTER_CORR};
    nCorrectors         2;
    nNonOrthogonalCorrectors 1;
    pRefCell        0;
    pRefValue       0;

    outerCorrectorResidualControl
    {{
        U
        {{
            tolerance 1e-5;
            relTol 0;
        }}
        p
        {{
            tolerance 1e-6;
            relTol 0;
        }}
    }}
}}

relaxationFactors
{{
    fields
    {{
        p       0.3;
        pFinal  1;
    }}

    equations
    {{
        "U.*"           0.5;
        "k.*"           1;
        "epsilon.*"     1;
    }}
}}

// ************************************************************************* //
"""
        return laminar_fvSolution

    # Similar methods for `_get_laminar_medium_fvSolution`, `_get_laminar_low_fvSolution`,
    # `_get_LES_high_fvSolution`, `_get_LES_medium_fvSolution`, `_get_LES_low_fvSolution`,
    # and `_get_RAS_fvSolution` can be implemented here, following the same pattern.
