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
    {% if template_vars and template_vars.openfoam_major_version >= 11 %}
    location    "constant";
    object      momentumTransport;
    {% else %}
    location    "constant";
    object      momentumTransport;
    {% endif %}
}
// ************************************************************************* //

{# This template uses conditions to generate the correct block #}
{% if physics.simulation_type == "laminar" %}
simulationType  laminar;
{% elif physics.simulation_type == "RAS" %}
simulationType  RAS;

RAS
{
    model           kOmegaSST;
    turbulence      on;
    printCoeffs     on;
}
{% elif physics.simulation_type == "LES" %}
simulationType LES;

LES
{
    model           WALE;
    turbulence      on;
    printCoeffs     on;
    delta           cubeRootVol;
    cubeRootVolCoeffs
    {
        deltaCoeff      1;
    }
    smoothCoeffs
    {
        delta           cubeRootVol;
        maxDeltaRatio   1.1;
    }
}
{% endif %}

// ************************************************************************* //