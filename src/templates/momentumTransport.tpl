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
    model           {{ physics.rans_model | default('kOmegaSST') }};
    turbulence      on;
    printCoeffs     on;
}
{% elif physics.simulation_type == "LES" %}
simulationType LES;

LES
{
{% if physics.les_model | default('WALE') == 'Smagorinsky' %}
    // Smagorinsky: Algebraic model, robust with Windkessel BCs
    // (WALE can cause FPE in pow3() during backflow)
    LESModel        Smagorinsky;

    turbulence      on;
    printCoeffs     on;

    SmagorinskyCoeffs
    {
        Cs              {{ physics.les_settings.Cs | default(0.1) }};
        Ck              {{ physics.les_settings.Ck | default(0.094) }};
    }

    delta           {{ physics.les_settings.delta | default('cubeRootVol') }};

    cubeRootVolCoeffs
    {
        deltaCoeff      1;
    }
{% else %}
    // WALE: Wall-Adapting Local Eddy-viscosity model
    // Note: May cause FPE with Windkessel BCs - use Smagorinsky if unstable
    model           {{ physics.les_model | default('WALE') }};
    turbulence      on;
    printCoeffs     on;
    delta           {{ physics.les_settings.delta | default('cubeRootVol') if physics.les_settings else 'cubeRootVol' }};
    cubeRootVolCoeffs
    {
        deltaCoeff      1;
    }
    smoothCoeffs
    {
        delta           cubeRootVol;
        maxDeltaRatio   1.1;
    }
{% endif %}
}
{% endif %}

// ************************************************************************* //