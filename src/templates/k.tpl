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
    object      k;
}
// ************************************************************************* //

dimensions      [0 2 -2 0 0 0 0];

internalField   uniform {{ k_initial }};

boundaryField
{
    {% if world_patch_mode %}
    // World patch mode - all boundaries combined into single patch
    world
    {
        type            fixedValue;
        value           uniform {{ k_initial }};
    }
    {% else %}
    // The inlet turbulent kinetic energy boundary condition
    {{ inlet_patch }}
    {
        type            turbulentIntensityKineticEnergyInlet;
        intensity       {{ turbulence_intensity }};
        value           uniform {{ k_initial }};
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
        type            kqRWallFunction;
        value           uniform {{ k_initial }};
    }
    {% endif %}
}
// ************************************************************************* //