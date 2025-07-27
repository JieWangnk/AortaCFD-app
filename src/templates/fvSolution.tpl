/*--------------------------------*- C++ -*----------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  12
     \\/     M anipulation  |
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
    p
    {
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       1e-06;
        relTol          0.05;
    }

    pFinal
    {
        $p;
        relTol          0;
    }

    "(U|k|epsilon|omega)"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-05;
        relTol          0.1;
    }

    "(U|k|epsilon|omega)Final"
    {
        $U;
        relTol          0;
    }
}

SIMPLE
{
    nNonOrthogonalCorrectors {{ fvSolution.get('SIMPLE', {}).get('nNonOrthogonalCorrectors', 0) }};

    residualControl
    {
        p               {{ fvSolution.get('SIMPLE', {}).get('residualControl', {}).get('p', '1e-2') }};
        U               {{ fvSolution.get('SIMPLE', {}).get('residualControl', {}).get('U', '1e-3') }};
        "(k|epsilon|omega)"   {{ fvSolution.get('SIMPLE', {}).get('residualControl', {}).get('k', '1e-3') }};
    }
}

PIMPLE
{
    nOuterCorrectors {{ fvSolution.get('PIMPLE', {}).get('nOuterCorrectors', 1) }};
    nCorrectors     {{ fvSolution.get('PIMPLE', {}).get('nCorrectors', 2) }};
    nNonOrthogonalCorrectors {{ fvSolution.get('PIMPLE', {}).get('nNonOrthogonalCorrectors', 0) }};
    pRefPoint       (-0.013 -0.034 0.001);
    pRefValue       0;

    // Corrector convergence criteria for inner PIMPLE loop
    correctorResidualControl
    {
        p
        {
            tolerance       1e-3;
            relTol          0;
        }
        U
        {
            tolerance       1e-4;
            relTol          0;
        }
    }

    outerCorrectorResidualControl
    {
        p
        {
            tolerance       {{ fvSolution.get('PIMPLE', {}).get('outerCorrectorResidualControl', {}).get('p', '1e-4') }};
            relTol          0;
        }
        U
        {
            tolerance       {{ fvSolution.get('PIMPLE', {}).get('outerCorrectorResidualControl', {}).get('U', '1e-5') }};
            relTol          0;
        }
        "(k|epsilon|omega)"
        {
            tolerance       {{ fvSolution.get('PIMPLE', {}).get('outerCorrectorResidualControl', {}).get('k', '1e-5') }};
            relTol          0;
        }
    }
}

relaxationFactors
{
    fields
    {
        p               {{ fvSolution.get('relaxationFactors', {}).get('fields', {}).get('p', '0.3') }};
    }

    equations
    {
        U               {{ fvSolution.get('relaxationFactors', {}).get('equations', {}).get('U', '0.7') }};
        "(k|epsilon|omega).*"   {{ fvSolution.get('relaxationFactors', {}).get('equations', {}).get('k', '0.7') }};
    }
}

cache
{
    grad(U);
}

// ************************************************************************* //