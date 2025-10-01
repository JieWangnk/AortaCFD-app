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
    class       volVectorField;
    object      U;
}
// ************************************************************************* //

dimensions      [0 1 -1 0 0 0 0];

internalField   uniform (0 0 0);

boundaryField
{
    {% if world_patch_mode %}
    // World patch mode - all boundaries combined into single patch
    world
    {
        type            fixedValue;
        value           uniform (0 0 0);
    }
    {% else %}
    // The inlet velocity boundary condition
    {{ inlet_patch }}
    {
        {% if inlet_settings.type == "TIMEVARYING" or (inlet_settings.data_type == "velocity" and inlet_settings.profile == "womersley") %}
        type            timeVaryingMappedFixedValue;
        offset          (0 0 0);
        setAverage      false;
        {% else %}
        type            fixedValue;
        value           uniform (0 0 0);
        {% endif %}
    }

    // The outlets are created dynamically based on the JSON settings
    {% for outlet in outlet_patches %}
    {{ outlet }}
    {
        {% if outlet_settings.type == "3EWINDKESSEL" %}
        {% set wk_settings = outlet_settings.get('windkessel_settings', {}) %}
        {% set outlet_velocity = wk_settings.get('velocity_bc', {}).get(outlet, {}) %}
        {% set beta_value = outlet_velocity.get('beta', wk_settings.get('beta', 1.0)) %}
        {% set enable_stab = outlet_velocity.get('enable_stabilization', wk_settings.get('enable_stabilization', True)) %}
        type            stabilizedWindkesselVelocity;
        beta            {{ beta_value }};
        enableStabilization {{ 'true' if enable_stab else 'false' }};
        value           uniform (0 0 0);
        {% else %}
        type            zeroGradient;
        {% endif %}
    }
    {% endfor %}

    // The wall condition is standardized here
    {{ wall_patch }}
    {
        type            fixedValue;
        value           uniform (0 0 0);
    }
    {% endif %}
}
// ************************************************************************* //