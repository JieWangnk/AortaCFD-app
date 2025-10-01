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
    object      fvSchemes;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

ddtSchemes
{
    {% if physics.get('steady_state', false) %}
    default         steadyState;
    {% elif schemes and schemes.ddtSchemes %}
    {%- for key, value in schemes.ddtSchemes.items() %}
    {{ key }}       {{ value }};
    {%- endfor %}
    {% elif physics.simulation_performance == 'low' %}
    default         Euler;
    {% else %}
    default         backward;
    {% endif %}
}

gradSchemes
{
    {% if schemes and schemes.gradSchemes %}
    {%- for key, value in schemes.gradSchemes.items() %}
    {{ key }}       {{ value }};
    {%- endfor %}
    {% else %}
    // Robust gradient schemes for OpenFOAM 12
    default         cellLimited Gauss linear 0.5;
    grad(p)         cellLimited Gauss linear 0.33;
    grad(U)         cellLimited Gauss linear 0.5;
    {% endif %}
}

divSchemes
{
    {% if schemes and schemes.divSchemes %}
    {%- for key, value in schemes.divSchemes.items() %}
    {{ key }}       {{ value }};
    {%- endfor %}
    {% else %}
    default         none;
    {% if physics.simulation_performance == 'low' %}
    div(phi,U)      Gauss upwind;
    {% elif physics.simulation_performance == 'high' and physics.simulation_type == 'laminar' %}
    div(phi,U)      bounded Gauss linearUpwindV grad(U);
    {% else %}
    div(phi,U)      bounded Gauss limitedLinearV 1;
    {% endif %}
    div(phi,k)      bounded Gauss limitedLinear 1;
    div(phi,epsilon) bounded Gauss limitedLinear 1;
    div(phi,omega)  bounded Gauss limitedLinear 1;
    div((nuEff*dev2(T(grad(U)))))  Gauss linear;
    {% endif %}
}

laplacianSchemes
{
    {% if schemes and schemes.laplacianSchemes %}
    {%- for key, value in schemes.laplacianSchemes.items() %}
    {{ key }}       {{ value }};
    {%- endfor %}
    {% elif physics.simulation_type == 'LES' %}
    default         Gauss linear corrected;
    {% else %}
    default         Gauss linear corrected;
    {% endif %}
}

interpolationSchemes
{
    {% if schemes and schemes.interpolationSchemes %}
    {%- for key, value in schemes.interpolationSchemes.items() %}
    {{ key }}       {{ value }};
    {%- endfor %}
    {% else %}
    default         linear;
    {% endif %}
}

snGradSchemes
{
    {% if schemes and schemes.snGradSchemes %}
    {%- for key, value in schemes.snGradSchemes.items() %}
    {{ key }}       {{ value }};
    {%- endfor %}
    {% else %}
    default         corrected;
    {% endif %}
}

{% if physics.simulation_type in ['LES', 'RAS', 'RANS'] %}
wallDist
{
    method meshWave;
}
{% endif %}

// ************************************************************************* //