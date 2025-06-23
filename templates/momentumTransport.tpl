{{ header }}

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