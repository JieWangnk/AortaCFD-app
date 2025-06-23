{{ header }}

ddtSchemes
{
    {% if physics.simulation_performance == 'low' %}
    default         Euler;
    {% else %}
    default         backward;
    {% endif %}
}

gradSchemes
{
    {% if physics.simulation_type == 'LES' and physics.simulation_performance == 'high' %}
    default         cellMDLimited Gauss linear 0.5;
    {% elif physics.simulation_performance == 'high' %}
    default         cellLimited Gauss linear 1;
    grad(p)         cellLimited Gauss linear 0.5;
    {% else %}
    default         cellLimited Gauss linear 0.5;
    {% endif %}
}

divSchemes
{
    default         none;
    {% if physics.simulation_performance == 'low' %}
    div(phi,U)      Gauss upwind;
    {% elif physics.simulation_performance == 'high' and physics.simulation_type == 'laminar' %}
    div(phi,U)      Gauss linearUpwind default;
    {% else %}
    div(phi,U)      Gauss linear;
    {% endif %}
    div((nuEff*dev2(T(grad(U)))))  Gauss linear;
}

laplacianSchemes
{
    {% if physics.simulation_type == 'LES' %}
    default         Gauss linear corrected;
    {% else %}
    default         Gauss linear limited 0.5;
    {% endif %}
}

interpolationSchemes
{
    default         linear;
}

snGradSchemes
{
    default         corrected;
}

{% if physics.simulation_type == 'LES' %}
wallDist
{
    method meshWave;
}
{% endif %}

// ************************************************************************* //