import os
from typing import Any

class FvSolutionWriter():
    def __init__(self, DIRECTORY, SIMULATIONTYPE,SIMULATIONPERFORMACE, OUTTER_CORR):
        self.DIRECTORY = DIRECTORY
        self.SIMULATIONTYPE = SIMULATIONTYPE
        self.SIMULATIONPERFORMACE = SIMULATIONPERFORMACE
        self.OUTTER_CORR = OUTTER_CORR

    def write_fvSolution_file(self):
        filepath = os.path.join(self.DIRECTORY,"system","fvSolution")

        with open(filepath, 'w') as f:
            if self.SIMULATIONTYPE == 'laminar':
                if self.SIMULATIONPERFORMACE == "high":
                    f.write(self._get_laminar_high_fvSolution())
                elif self.SIMULATIONPERFORMACE == "medium":
                    f.write(self._get_laminar_medium_fvSolution())
                elif self.SIMULATIONPERFORMACE == "low":
                    f.write(self._get_laminar_low_fvSolution())
                else:
                    print("Invalid simulation performance.")
            if self.SIMULATIONTYPE == 'LES':
                if self.SIMULATIONPERFORMACE == "high":
                    f.write(self._get_LES_high_fvSolution())
                elif self.SIMULATIONPERFORMACE == "medium":
                    f.write(self._get_LES_medium_fvSolution())
                elif self.SIMULATIONPERFORMACE == "low":
                    f.write(self._get_LES_low_fvSolution())
                else:
                    print("Invalid simulation performance.")

    def _get_laminar_high_fvSolution(self):
        laminar_fvSolution = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  3.0.1                                 |
|   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
|    \\/     M anipulation  |                                                 |
\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSolution;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

solvers
{
    Phi
    {
        solver          GAMG;
        smoother        DIC;
        tolerance       1e-06;
        relTol          0.01;
    }

    p
    {
        solver          GAMG;
        tolerance       1e-06;
        relTol          0.01;
        smoother        GaussSeidel;
        cacheAgglomeration true;
        nCellsInCoarsestLevel 10;
        agglomerator    faceAreaPair;
        mergeLevels     1;
    }

    pFinal
    {
        solver          GAMG;
        tolerance       1e-06;
        relTol          0;
        smoother        GaussSeidel;
        cacheAgglomeration true;
        nCellsInCoarsestLevel 10;
        agglomerator    faceAreaPair;
        mergeLevels     1;
    }

    "(U|k|nuTilda)"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-05;
        relTol          0.1;
    }

    "(U|k|nuTilda)Final"
    {
        $U;
        tolerance       1e-05;
        relTol          0;
    }

   "(C_tPA|C_PLG|C_PLS|flowRate)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    }

    "(n_tPA|n_PLG|n_PLS)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    }

    "(n_tot|L_PLS)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    }

}

PIMPLE
{
    momentumPredictor   no;
    nOuterCorrectors    10;
    nCorrectors         2;
    nNonOrthogonalCorrectors 1;
    pRefCell        0;
    pRefValue       0;

    outerCorrectorResidualControl
    {
        U
        {
                tolerance 1e-5;
                relTol 0;
        }
        p
        {
                tolerance 1e-6;
                relTol 0;
        }

    }
}

potentialFlow
{
    nNonOrthogonalCorrectors 10;
}

relaxationFactors
{
    fields
    {
        p       0.3;
        pFinal  1;
    }


    equations
    {
        "U.*"           0.5;
        "C_*"                   0.7;
        "n_*"                   0.7;
        L_PLS                   0.7;
        "k.*"           1;
        "epsilon.*"     1;
    }
}

// ************************************************************************* //
"""
        return laminar_fvSolution
    
    def _get_laminar_medium_fvSolution(self):
        laminar_fvSolution = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  3.0.1                                 |
|   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
|    \\/     M anipulation  |                                                 |
\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSolution;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

solvers
{
    Phi
    {
        solver          GAMG;
        smoother        DIC;
        tolerance       1e-06;
        relTol          0.01;
    }

    p
    {
        solver          GAMG;
        tolerance       1e-06;
        relTol          0.01;
        smoother        GaussSeidel;
        cacheAgglomeration true;
        nCellsInCoarsestLevel 10;
        agglomerator    faceAreaPair;
        mergeLevels     1;
    }

    pFinal
    {
        solver          GAMG;
        tolerance       1e-06;
        relTol          0;
        smoother        GaussSeidel;
        cacheAgglomeration true;
        nCellsInCoarsestLevel 10;
        agglomerator    faceAreaPair;
        mergeLevels     1;
    }

    "(U|k|nuTilda)"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-05;
        relTol          0.1;
    }

    "(U|k|nuTilda)Final"
    {
        $U;
        tolerance       1e-05;
        relTol          0;
    }

   "(C_tPA|C_PLG|C_PLS|flowRate)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    }

    "(n_tPA|n_PLG|n_PLS)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    }

    "(n_tot|L_PLS)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    }

}

PIMPLE
{
    momentumPredictor   no;
    nOuterCorrectors    10;
    nCorrectors         2;
    nNonOrthogonalCorrectors 1;
    pRefCell        0;
    pRefValue       0;

    outerCorrectorResidualControl
    {
        U
        {
                tolerance 1e-5;
                relTol 0;
        }
        p
        {
                tolerance 1e-6;
                relTol 0;
        }

    }
}

potentialFlow
{
    nNonOrthogonalCorrectors 10;
}

relaxationFactors
{
    fields
    {
        p       0.5;
        pFinal  1;
    }


    equations
    {
        "U.*"           0.7;
        "C_*"                   0.7;
        "n_*"                   0.7;
        L_PLS                   0.7;
        "k.*"           1;
        "epsilon.*"     1;
    }
}

// ************************************************************************* //
"""
        return laminar_fvSolution

    def _get_laminar_low_fvSolution(self):
        laminar_fvSolution = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  3.0.1                                 |
|   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
|    \\/     M anipulation  |                                                 |
\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSolution;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

solvers
{
    Phi
    {
        solver          GAMG;
        smoother        DIC;
        tolerance       1e-06;
        relTol          0.01;
    }

    p
    {
        solver          GAMG;
        tolerance       1e-06;
        relTol          0.01;
        smoother        GaussSeidel;
        cacheAgglomeration true;
        nCellsInCoarsestLevel 10;
        agglomerator    faceAreaPair;
        mergeLevels     1;
    }

    pFinal
    {
        solver          GAMG;
        tolerance       1e-06;
        relTol          0;
        smoother        GaussSeidel;
        cacheAgglomeration true;
        nCellsInCoarsestLevel 10;
        agglomerator    faceAreaPair;
        mergeLevels     1;
    }

    "(U|k|nuTilda)"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-05;
        relTol          0.1;
    }

    "(U|k|nuTilda)Final"
    {
        $U;
        tolerance       1e-05;
        relTol          0;
    }

   "(C_tPA|C_PLG|C_PLS|flowRate)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    }

    "(n_tPA|n_PLG|n_PLS)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    }

    "(n_tot|L_PLS)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    }

}

PIMPLE
{
    momentumPredictor   no;
    nOuterCorrectors    10;
    nCorrectors         2;
    nNonOrthogonalCorrectors 1;
    pRefCell        0;
    pRefValue       0;

    outerCorrectorResidualControl
    {
        U
        {
                tolerance 1e-5;
                relTol 0;
        }
        p
        {
                tolerance 1e-6;
                relTol 0;
        }

    }
}

potentialFlow
{
    nNonOrthogonalCorrectors 10;
}

relaxationFactors
{
    fields
    {
        p       0.7;
        pFinal  1;
    }


    equations
    {
        "U.*"           0.7;
        "C_*"                   0.7;
        "n_*"                   0.7;
        L_PLS                   0.7;
        "k.*"           1;
        "epsilon.*"     1;
    }
}

// ************************************************************************* //
"""
        return laminar_fvSolution
    
    def _get_LES_high_fvSolution(self):
        LES_fvSolution = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  3.0.1                                 |
|   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
|    \\/     M anipulation  |                                                 |
\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSolution;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

solvers
{
    p
    {
        solver          GAMG;
        tolerance       1e-06;
        relTol          0.01;
        smoother        GaussSeidel;
        cacheAgglomeration true;
        nCellsInCoarsestLevel 10;
        agglomerator    faceAreaPair;
        mergeLevels     1;
    }

    pFinal
    {
        solver          GAMG;
        tolerance       1e-06;
        relTol          0;
        smoother        GaussSeidel;
        cacheAgglomeration true;
        nCellsInCoarsestLevel 10;
        agglomerator    faceAreaPair;
        mergeLevels     1;
    }

    "(U|k|epsilon)"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-05;
        relTol          0.1;
    }

    "(U|k|epsilon)Final"
    {
        $U;
        relTol          0;
    }

   "(C_tPA|C_PLG|C_PLS|flowRate)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    };

    "(n_tPA|n_PLG|n_PLS)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    };

    "(n_tot|L_PLS)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    };
}


PIMPLE
{
    nOuterCorrectors 100;
    nCorrectors     2;
    nNonOrthogonalCorrectors 0;
    pRefCell        0;
    pRefValue       0;

    outerCorrectorResidualControl
    {
        U
        {
                tolerance 1e-5;
                relTol 0;
        }
        p
        {
                tolerance 1e-6;
                relTol 0;
        }
   }

}

potentialFlow
{
    nNonOrthogonalCorrectors 10;
}

relaxationFactors
{
    fields
    {
        p       0.4;
        pFinal  1;
    }


    equations
    {
        "U.*"           0.5;
        "C_*"                   0.7;
        "n_*"                   0.7;
        L_PLS                   0.7;
        "k.*"           1;
        "epsilon.*"     1;
    }
}

// ************************************************************************* //
"""
        return LES_fvSolution

    def _get_LES_medium_fvSolution(self):
        laminar_fvSolution = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  3.0.1                                 |
|   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
|    \\/     M anipulation  |                                                 |
\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSolution;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

solvers
{
    Phi
    {
        solver          GAMG;
        smoother        DIC;
        tolerance       1e-06;
        relTol          0.01;
    }

    p
    {
        solver          GAMG;
        tolerance       1e-06;
        relTol          0.01;
        smoother        GaussSeidel;
        cacheAgglomeration true;
        nCellsInCoarsestLevel 10;
        agglomerator    faceAreaPair;
        mergeLevels     1;
    }

    pFinal
    {
        solver          GAMG;
        tolerance       1e-06;
        relTol          0;
        smoother        GaussSeidel;
        cacheAgglomeration true;
        nCellsInCoarsestLevel 10;
        agglomerator    faceAreaPair;
        mergeLevels     1;
    }

    "(U|k|nuTilda)"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-05;
        relTol          0.1;
    }

    "(U|k|nuTilda)Final"
    {
        $U;
        tolerance       1e-05;
        relTol          0;
    }

   "(C_tPA|C_PLG|C_PLS|flowRate)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    }

    "(n_tPA|n_PLG|n_PLS)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    }

    "(n_tot|L_PLS)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    }

}

PIMPLE
{
    momentumPredictor   no;
    nOuterCorrectors    10;
    nCorrectors         2;
    nNonOrthogonalCorrectors 1;
    pRefCell        0;
    pRefValue       0;

    outerCorrectorResidualControl
    {
        U
        {
                tolerance 1e-5;
                relTol 0;
        }
        p
        {
                tolerance 1e-6;
                relTol 0;
        }

    }
}

potentialFlow
{
    nNonOrthogonalCorrectors 10;
}

relaxationFactors
{
    fields
    {
        p       0.4;
        pFinal  1;
    }


    equations
    {
        "U.*"           0.5;
        "C_*"                   0.7;
        "n_*"                   0.7;
        L_PLS                   0.7;
        "k.*"           1;
        "epsilon.*"     1;
    }
}

// ************************************************************************* //
"""
        return laminar_fvSolution

    def _get_LES_low_fvSolution(self):
        laminar_fvSolution = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  3.0.1                                 |
|   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
|    \\/     M anipulation  |                                                 |
\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSolution;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

solvers
{
    Phi
    {
        solver          GAMG;
        smoother        DIC;
        tolerance       1e-06;
        relTol          0.01;
    }

    p
    {
        solver          GAMG;
        tolerance       1e-06;
        relTol          0.01;
        smoother        GaussSeidel;
        cacheAgglomeration true;
        nCellsInCoarsestLevel 10;
        agglomerator    faceAreaPair;
        mergeLevels     1;
    }

    pFinal
    {
        solver          GAMG;
        tolerance       1e-06;
        relTol          0;
        smoother        GaussSeidel;
        cacheAgglomeration true;
        nCellsInCoarsestLevel 10;
        agglomerator    faceAreaPair;
        mergeLevels     1;
    }

    "(U|k|nuTilda)"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-05;
        relTol          0.1;
    }

    "(U|k|nuTilda)Final"
    {
        $U;
        tolerance       1e-05;
        relTol          0;
    }

   "(C_tPA|C_PLG|C_PLS|flowRate)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    }

    "(n_tPA|n_PLG|n_PLS)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    }

    "(n_tot|L_PLS)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    }

}

PIMPLE
{
    momentumPredictor   no;
    nOuterCorrectors    10;
    nCorrectors         2;
    nNonOrthogonalCorrectors 1;
    pRefCell        0;
    pRefValue       0;

    outerCorrectorResidualControl
    {
        U
        {
                tolerance 1e-5;
                relTol 0;
        }
        p
        {
                tolerance 1e-6;
                relTol 0;
        }

    }
}

potentialFlow
{
    nNonOrthogonalCorrectors 10;
}

relaxationFactors
{
    fields
    {
        p       0.4;
        pFinal  1;
    }


    equations
    {
        "U.*"           0.5;
        "C_*"                   0.7;
        "n_*"                   0.7;
        L_PLS                   0.7;
        "k.*"           1;
        "epsilon.*"     1;
    }
}

// ************************************************************************* //
"""
        return laminar_fvSolution

    def _get_RAS_fvSolution(self):
        RAS_fvSolution = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  3.0.1                                 |
|   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
|    \\/     M anipulation  |                                                 |
\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSolution;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

solvers
{
    p
    {
        solver          GAMG;
        tolerance       1e-06;
        relTol          0.01;
        smoother        GaussSeidel;
        cacheAgglomeration true;
        nCellsInCoarsestLevel 10;
        agglomerator    faceAreaPair;
        mergeLevels     1;
    }

    pFinal
    {
        solver          GAMG;
        tolerance       1e-06;
        relTol          0;
        smoother        GaussSeidel;
        cacheAgglomeration true;
        nCellsInCoarsestLevel 10;
        agglomerator    faceAreaPair;
        mergeLevels     1;
    }
    
    "(U|k|omega|epsilon)"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-05;
        relTol          0.1;
    }

    "(U|k|omega|epsilon)Final"
    {
        $U;
        relTol          0;
    }

   "(C_tPA|C_PLG|C_PLS|flowRate)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    };

    "(n_tPA|n_PLG|n_PLS)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    };

    "(n_tot|L_PLS)"
    {
       solver            PBiCG;
        preconditioner   DILU;
        tolerance        1e-6;
        relTol           0;
    };
}


PIMPLE
{
    nOuterCorrectors 2;
    nCorrectors     10;
    nNonOrthogonalCorrectors 0;
    pRefCell        0;
    pRefValue       0;

    outerCorrectorResidualControl
    {
        U
        {
                tolerance 1e-5;
                relTol 0;
        }
        p
        {
                tolerance 1e-6;
                relTol 0;
        }
   }

}

potentialFlow
{
    nNonOrthogonalCorrectors 10;
}

relaxationFactors
{
    fields
    {
        p       0.4;
        pFinal  1;
    }


    equations
    {
        "U.*"           0.5;
        "C_*"                   0.7;
        "n_*"                   0.7;
        L_PLS                   0.7;
        "k.*"           1;
        "epsilon.*"     1;
        "omega.*"     1;
    }
}



// ************************************************************************* //
"""
        return RAS_fvSolution
