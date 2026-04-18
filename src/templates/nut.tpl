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
    class       volScalarField;
    object      nut;
}
// ************************************************************************* //

dimensions      [0 2 -1 0 0 0 0];

internalField   uniform 0;

boundaryField
{
    {% if world_patch_mode %}
    // World patch mode - all boundaries combined into single patch
    world
    {
        type            calculated;
        value           uniform 0;
    }
    {% else %}
    // The inlet turbulent viscosity boundary condition
    {{ inlet_patch }}
    {
        type            calculated;
        value           uniform 0;
    }

    // The outlets are created dynamically based on the JSON settings
    {% for outlet in outlet_patches %}
    {{ outlet }}
    {
        type            calculated;
        value           uniform 0;
    }
    {% endfor %}

    // The wall condition is standardized here
    {{ wall_patch }}
    {
        type            nutkWallFunction;
        value           uniform 0;
    }

    {% if has_world_patch %}
    world
    {
        type            calculated;
        value           uniform 0;
    }
    {% endif %}
    {% endif %}
}
// ************************************************************************* //