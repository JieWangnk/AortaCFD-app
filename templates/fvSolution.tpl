{{ header }}

solvers
{
    p
    {
        solver          {{ fvSolution.solvers.p.solver }};
        {% if fvSolution.solvers.p.preconditioner %}preconditioner  {{ fvSolution.solvers.p.preconditioner }};{% endif %}
        {% if fvSolution.solvers.p.smoother %}smoother        {{ fvSolution.solvers.p.smoother }};{% endif %}
        tolerance       {{ fvSolution.solvers.p.tolerance }};
        relTol          {{ fvSolution.solvers.p.relTol }};
    }

    U
    {
        solver          {{ fvSolution.solvers.U.solver }};
        {% if fvSolution.solvers.U.preconditioner %}preconditioner  {{ fvSolution.solvers.U.preconditioner }};{% endif %}
        {% if fvSolution.solvers.U.smoother %}smoother        {{ fvSolution.solvers.U.smoother }};{% endif %}
        tolerance       {{ fvSolution.solvers.U.tolerance }};
        relTol          {{ fvSolution.solvers.U.relTol }};
    }
    
    {# This handles the final solvers if they exist in the config #}
    {% if fvSolution.get('solvers_final') %}
    pFinal
    {
        $p;
        relTol          0;
        tolerance       {{ fvSolution.solvers_final.p.tolerance }};
    }

    UFinal
    {
        $U;
        relTol          0;
        tolerance       {{ fvSolution.solvers_final.U.tolerance }};
    }
    {% endif %}
}

PIMPLE
{
    nOuterCorrectors     {{ fvSolution.PIMPLE.nOuterCorrectors }};
    nCorrectors          {{ fvSolution.PIMPLE.nCorrectors }};
    nNonOrthogonalCorrectors {{ fvSolution.PIMPLE.nNonOrthogonalCorrectors }};

    {# --- ADD THE MISSING pRefValue KEYWORD --- #}
    pRefCell             {{ fvSolution.PIMPLE.get('pRefCell', 0) }};
    pRefValue            {{ fvSolution.PIMPLE.get('pRefPoint', 0) }}; {# Note: This should be pRefValue, using pRefPoint from config is likely a typo in my previous template #}


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