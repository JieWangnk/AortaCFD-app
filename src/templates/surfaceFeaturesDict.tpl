/*--------------------------------*- C++ -*----------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  {{ config.template_vars.openfoam_version }}
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    object      surfaceFeaturesDict;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

surfaces ({% for patch_name in patches %}"{{ patch_name }}.stl"{% if not loop.last %} {% endif %}{% endfor %});

// Identify a feature when angle between faces < includedAngle
// 150° = detect edges with angle > 30° (180 - 150 = 30°)
// Lower value = more edges detected (aggressive), Higher value = fewer edges (conservative)
includedAngle   {{ config.mesh.SNAPPY_SETTINGS.get('includedAngle', 150) }};