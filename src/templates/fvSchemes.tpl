/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  {{ template_vars.openfoam_version if template_vars else openfoam_version }}
     \\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSchemes;
}
// ************************************************************************* //

ddtSchemes
{
    {% set of_version = template_vars.openfoam_major_version if template_vars else openfoam_major_version %}
    {% if physics.get('steady_state', false) %}
    default         steadyState;
    {% elif physics.simulation_performance == 'low' %}
    default         Euler;
    {% else %}
    default         backward;
    {% endif %}
}

gradSchemes
{
    {% set of_version = template_vars.openfoam_major_version if template_vars else openfoam_major_version %}
    {% if of_version >= 12 %}
    // Robust gradient schemes for OpenFOAM 12
    default         cellLimited Gauss linear 0.5;
    grad(p)         cellLimited Gauss linear 0.33;
    grad(U)         cellLimited Gauss linear 0.5;
    {% else %}
    {% if physics.simulation_type == 'LES' and physics.simulation_performance == 'high' %}
    default         cellMDLimited Gauss linear 0.5;
    {% elif physics.simulation_performance == 'high' %}
    default         cellLimited Gauss linear 1;
    grad(p)         cellLimited Gauss linear 0.5;
    {% else %}
    default         cellLimited Gauss linear 0.5;
    {% endif %}
    {% endif %}
}

divSchemes
{
    default         none;
    {% set of_version = template_vars.openfoam_major_version if template_vars else openfoam_major_version %}
    {% if physics.simulation_performance == 'low' %}
    div(phi,U)      Gauss upwind;
    {% elif physics.simulation_performance == 'high' and physics.simulation_type == 'laminar' %}
        {% if of_version >= 12 %}
    div(phi,U)      bounded Gauss linearUpwindV grad(U);
        {% else %}
    div(phi,U)      Gauss linearUpwind default;
        {% endif %}
    {% else %}
        {% if of_version >= 12 %}
    div(phi,U)      bounded Gauss upwind;
        {% else %}
    div(phi,U)      Gauss linear;
        {% endif %}
    {% endif %}
    {% if of_version >= 12 %}
    div((nuEff*dev2(T(grad(U)))))  Gauss linear;
    {% else %}
    div((nuEff*dev2(T(grad(U)))))  Gauss linear;
    {% endif %}
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