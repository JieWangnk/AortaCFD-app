/*--------------------------------*- C++ -*----------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  12
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvOptions;
}
// ************************************************************************* //

{% if physics.simulation_type == "LES" %}
// STABILITY: Bound nut to prevent FPE in LES models (especially WALE)
// WALE model can produce extreme nut values causing pow3() to crash
// This sets a minimum bound to prevent division by zero / underflow

boundNut
{
    type            bound;
    field           nut;
    min             1e-15;
}
{% endif %}

// ************************************************************************* //
