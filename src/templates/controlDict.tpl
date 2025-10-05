/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  12
     \\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    location    "system";
    object      controlDict;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

application     foamRun;

solver          incompressibleFluid;

startFrom       {{ controlDict.get('startFrom', 'startTime') }};

startTime       {{ controlDict.get('startTime', 0) }};

stopAt          {{ controlDict.get('stopAt', 'endTime') }};

endTime         {{ controlDict.endTime }};

deltaT          {{ controlDict.deltaT }};

writeControl    {{ controlDict.get('writeControl', 'adjustableRunTime') }};

writeInterval   {{ controlDict.get('writeInterval', 0.01) }};

purgeWrite      {{ controlDict.get('purgeWrite', 0) }};

writeFormat     {{ controlDict.get('writeFormat', 'binary') }};

writePrecision  {{ controlDict.get('writePrecision', 6) }};

writeCompression {{ controlDict.get('writeCompression', 'off') }};

timeFormat      {{ controlDict.get('timeFormat', 'general') }};

timePrecision   {{ controlDict.get('timePrecision', 6) }};

runTimeModifiable {{ controlDict.get('runTimeModifiable', 'true') }};

// Adaptive time stepping for numerical robustness and efficiency
adjustTimeStep  {{ controlDict.get('adjustTimeStep', 'yes') }};

maxCo           {{ controlDict.get('maxCo', 1.2) }};

maxAlphaCo      {{ controlDict.get('maxAlphaCo', 1.2) }};

maxDeltaT       {{ controlDict.get('maxDeltaT', 1e-3) }};

minDeltaT       {{ controlDict.get('minDeltaT', 1e-8) }};

{% if config.get('windkessel_enabled', False) or config.get('outlets', {}).get('type') == '3EWINDKESSEL' or config.get('boundary_conditions', {}).get('outlets', {}).get('type') == '3EWINDKESSEL' %}

libs
(
    "libmodularWKPressure.so"
);
{% endif %}

{% if config.simulation_control.controlDict.get('functions', []) %}
functions
{
    {% for func in config.simulation_control.controlDict.get('functions', []) %}
    #includeFunc {{ func }}
    {% endfor %}
}
{% endif %}

// ************************************************************************* //