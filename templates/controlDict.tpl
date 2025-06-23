/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  {{ version }}
     \\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      controlDict;
}
// ************************************************************************* //

application     {{ controlDict.get('application', 'pimpleFoam') }};

startFrom       {{ controlDict.get('startFrom', 'startTime') }};
startTime       {{ controlDict.get('startTime', 0) }};

stopAt          {{ controlDict.get('stopAt', 'endTime') }};
endTime         {{ controlDict.endTime }};

deltaT          {{ controlDict.deltaT }};

writeControl    {{ controlDict.get('writeControl', 'timeStep') }};
writeInterval   {{ controlDict.writeInterval }};

purgeWrite      {{ controlDict.get('purgeWrite', 0) }};
writeFormat     {{ controlDict.get('writeFormat', 'binary') }};
writePrecision  {{ controlDict.get('writePrecision', 6) }};
writeCompression {{ controlDict.get('writeCompression', 'off') }};
timeFormat      {{ controlDict.get('timeFormat', 'general') }};
timePrecision   {{ controlDict.get('timePrecision', 6) }};

runTimeModifiable {{ controlDict.get('runTimeModifiable', 'true') }};
allowSystemOperations {{controlDict.get('allowSystemOperations', 'true') }};
adjustTimeStep {{controlDict.get('adjustTimeStep', 'true') }};
maxCo {{controlDict.get('maxCo', 1) }};

functions
{
    // This corrected version uses #includeFunc without quotes.
    {% for func in config.simulation_control.controlDict.get('functions', []) %}
    #includeFunc {{ func }}
    {% endfor %}
}

// ************************************************************************* //