{{ header }}

solvers
{
    p
    {
        {% set of_version = template_vars.openfoam_major_version if template_vars else openfoam_major_version %}
        {% if of_version >= 12 %}
        solver          GAMG;
        smoother        DICGaussSeidel;
        tolerance       1e-7;
        relTol          0.01;
        {% else %}
        solver          {{ fvSolution.solvers.p.solver }};
        {% if fvSolution.solvers.p.preconditioner %}preconditioner  {{ fvSolution.solvers.p.preconditioner }};{% endif %}
        {% if fvSolution.solvers.p.smoother %}smoother        {{ fvSolution.solvers.p.smoother }};{% endif %}
        tolerance       {{ fvSolution.solvers.p.tolerance }};
        relTol          {{ fvSolution.solvers.p.relTol }};
        {% endif %}
    }

    U
    {
        {% if of_version >= 12 %}
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-8;
        relTol          0.01;
        {% else %}
        solver          {{ fvSolution.solvers.U.solver }};
        {% if fvSolution.solvers.U.preconditioner %}preconditioner  {{ fvSolution.solvers.U.preconditioner }};{% endif %}
        {% if fvSolution.solvers.U.smoother %}smoother        {{ fvSolution.solvers.U.smoother }};{% endif %}
        tolerance       {{ fvSolution.solvers.U.tolerance }};
        relTol          {{ fvSolution.solvers.U.relTol }};
        {% endif %}
    }
    
    {# OpenFOAM 12+ incompressibleFluid solver requires pFinal and UFinal entries #}
    {% set of_version = template_vars.openfoam_major_version if template_vars else openfoam_major_version %}
    {% if of_version >= 12 or fvSolution.get('solvers_final') %}
    pFinal
    {
        $p;
        relTol          0;
    }

    UFinal
    {
        $U;
        relTol          0;
    }
    {% endif %}
}

{% set of_version = template_vars.openfoam_major_version if template_vars else openfoam_major_version %}
{% if of_version >= 12 %}
PIMPLE
{
    nOuterCorrectors     {{ fvSolution.PIMPLE.get('nOuterCorrectors', 50) }};
    nCorrectors          {{ fvSolution.PIMPLE.get('nCorrectors', 3) }};
    nNonOrthogonalCorrectors {{ fvSolution.PIMPLE.get('nNonOrthogonalCorrectors', 2) }};

    pRefCell             {{ fvSolution.PIMPLE.get('pRefCell', 0) }};
    pRefValue            {{ fvSolution.PIMPLE.get('pRefValue', 0) }};
    
    // Mass conservation control
    adjustPhi           yes;
    checkMeshCourantNo  off;

    // Convergence criteria for robust simulation
    residualControl
    {
        p               1e-4;
        U               1e-5;
    }
    
    // Inner corrector convergence criteria
    correctorResidualControl
    {
        p               1e-3;
        U               1e-4;
    }
}
{% else %}
PIMPLE
{
    nOuterCorrectors     {{ fvSolution.PIMPLE.nOuterCorrectors }};
    nCorrectors          {{ fvSolution.PIMPLE.nCorrectors }};
    nNonOrthogonalCorrectors {{ fvSolution.PIMPLE.nNonOrthogonalCorrectors }};

    pRefCell             {{ fvSolution.PIMPLE.get('pRefCell', 0) }};
    pRefValue            {{ fvSolution.PIMPLE.get('pRefValue', 0) }};

    {% if fvSolution.PIMPLE.get('residualControl') %}
    outerCorrectorResidualControl
    {
        p
        {
            tolerance   {{ fvSolution.PIMPLE.residualControl.p.tolerance }};
            relTol      {{ fvSolution.PIMPLE.residualControl.p.relTol | default(0) }};
        }
        U
        {
            tolerance   {{ fvSolution.PIMPLE.residualControl.U.tolerance }};
            relTol      {{ fvSolution.PIMPLE.residualControl.U.relTol | default(0) }};
        }
    }
    {% endif %}
}
{% endif %}

{% if fvSolution.get('relaxationFactors') %}
relaxationFactors
{
    fields
    {
        p               {{ fvSolution.relaxationFactors.fields.p }};
    }
    equations
    {
        U               {{ fvSolution.relaxationFactors.equations.U }};
    }
}
{% endif %}

// ************************************************************************* //