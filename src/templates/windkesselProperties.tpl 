/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  {{ template_vars.openfoam_version if template_vars else openfoam_version }}
     \\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     4.0;
    format      ascii;
    class       dictionary;
    location    "constant";
    object      windkesselProperties;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

{# This template is for OpenFOAM 8 Windkessel model only #}
{# For OpenFOAM 12, Windkessel parameters are defined directly in boundary conditions #}
{% set of_version = template_vars.openfoam_major_version if template_vars else openfoam_major_version %}
{% if of_version < 12 %}
{# OpenFOAM 8 Windkessel format - requires windkesselProperties file #}
{% for outlet in outlets %}
{{ outlet.name }}
{
    C                   {{ outlet.C }};
    R                   {{ outlet.R }};
    Z                   {{ outlet.Z }};
    outIndex            {{ outlet.index }};     
    FDM_order           3;      
    Flowrate_threeStepBefore      0;    
    Flowrate_twoStepBefore        0;
    Flowrate_oneStepBefore        0;
    Pressure_twoStepBefore        0;
    Pressure_oneStepBefore        0;
    Pressure_start                0;
}
{% endfor %}
{% else %}
{# OpenFOAM 12 - Windkessel parameters are defined in boundary conditions #}
{# This file is not needed for OpenFOAM 12 modularWKPressure #}
// Note: For OpenFOAM 12, Windkessel parameters are defined
// directly in the boundary condition files (0/p, 0/U)
// This file is maintained for compatibility but not used.
{% endif %}

// ************************************************************************* //