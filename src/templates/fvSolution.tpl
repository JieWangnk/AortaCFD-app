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
    {% set pref = fvSolution.get('PIMPLE', {}).get('pRefPoint', None) %}
    {% if pref %}
    pRefPoint       ({{ pref[0] }} {{ pref[1] }} {{ pref[2] }});
    {% else %}
    // Note: pRefPoint should be calculated from mesh bounding box
    // If simulation diverges, ensure this point is inside the domain
    pRefCell        0;  // Use cell 0 as reference (safer default)
    {% endif %}
    pRefValue       0;

    // Corrector convergence criteria for inner PIMPLE loop
    {% set corr_res_ctrl = fvSolution.get('PIMPLE', {}).get('correctorResidualControl', {}) %}
    {% if corr_res_ctrl %}
    correctorResidualControl
    {
        {% for field_name, field_value in corr_res_ctrl.items() %}
        {% if not field_name.startswith('_') %}
        {% if '(' in field_name or '|' in field_name %}"{{ field_name }}"{% else %}{{ field_name }}{% endif %}
        {
            {% if field_value is mapping %}
            tolerance       {{ field_value.get('tolerance', '1e-4') }};
            relTol          {{ field_value.get('relTol', 0) }};
            {% else %}
            tolerance       {{ field_value }};
            relTol          0;
            {% endif %}
        }
        {% endif %}
        {% endfor %}
    }
    {% else %}
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
    {% endif %}

    {% set outer_res_ctrl = fvSolution.get('PIMPLE', {}).get('outerCorrectorResidualControl', {}) %}
    {% if outer_res_ctrl %}
    outerCorrectorResidualControl
    {
        {% for field_name, field_value in outer_res_ctrl.items() %}
        {% if not field_name.startswith('_') %}
        {% if '(' in field_name or '|' in field_name %}"{{ field_name }}"{% else %}{{ field_name }}{% endif %}
        {
            {% if field_value is mapping %}
            tolerance       {{ field_value.get('tolerance', '1e-5') }};
            relTol          {{ field_value.get('relTol', 0) }};
            {% else %}
            tolerance       {{ field_value }};
            relTol          0;
            {% endif %}
        }
        {% endif %}
        {% endfor %}
    }
    {% else %}
    outerCorrectorResidualControl
    {
        p
        {
            tolerance       1e-4;
            relTol          0;
        }
        U
        {
            tolerance       1e-5;
            relTol          0;
        }
        "(k|epsilon|omega)"
        {
            tolerance       1e-5;
            relTol          0;
        }
    }
    {% endif %}
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