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

{# Use pre-computed values from template_context.py when available, fallback to inline check #}
{%- set _is_les = is_les if is_les is defined else (physics.simulation_type == "LES") -%}
{%- set _bound_nut = bound_nut if bound_nut is defined else _is_les -%}
{%- set _nut_min = nut_min if nut_min is defined else 1e-15 -%}
{% if _bound_nut %}
// STABILITY: Bound nut to prevent FPE in LES models (especially WALE)
// WALE model can produce extreme nut values causing pow3() to crash
// This sets a minimum bound to prevent division by zero / underflow

boundNut
{
    type            bound;
    field           nut;
    min             {{ _nut_min }};
}
{% endif %}

// ************************************************************************* //
