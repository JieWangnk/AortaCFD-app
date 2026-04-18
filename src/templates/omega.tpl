/*--------------------------------*- C++ -*----------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  {{ template_vars.openfoam_version if template_vars else openfoam_version }}
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       volScalarField;
    object      omega;
}
// ************************************************************************* //

dimensions      [0 0 -1 0 0 0 0];

internalField   uniform {{ omega_initial }};

boundaryField
{
    {% if world_patch_mode %}
    // World patch mode - all boundaries combined into single patch
    world
    {
        type            fixedValue;
        value           uniform {{ omega_initial }};
    }
    {% else %}
    // The inlet specific dissipation rate boundary condition
    {{ inlet_patch }}
    {
        type            turbulentMixingLengthFrequencyInlet;
        mixingLength    {{ mixing_length }};
        value           uniform {{ omega_initial }};
    }

    // The outlets are created dynamically based on the JSON settings
    {% for outlet in outlet_patches %}
    {{ outlet }}
    {
        type            zeroGradient;
    }
    {% endfor %}

    // The wall condition is standardized here
    {{ wall_patch }}
    {
        type            omegaWallFunction;
        value           uniform {{ omega_initial }};
    }

    {% if has_world_patch %}
    world
    {
        type            zeroGradient;
    }
    {% endif %}
    {% endif %}
}
// ************************************************************************* //