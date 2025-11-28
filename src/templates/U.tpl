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
        {% if inlet_settings.type == "TIMEVARYING" or inlet_settings.type == "WOMERSLEY" %}
        type            timeVaryingMappedFixedValue;
        offset          (0 0 0);
        setAverage      false;
        {% elif inlet_settings.type == "CONSTANT" or inlet_settings.type == "PARABOLIC" %}
        type            fixedValue;
        value           uniform {{ inlet_velocity_vector }};
        {% else %}
        type            fixedValue;
        value           uniform (0 0 0);
        {% endif %}
    }

    // The outlets are created dynamically based on the JSON settings
    {% set outlet_type = outlet_settings.get('type', '3EWINDKESSEL') %}
    {% for outlet in outlet_patches %}
    {{ outlet }}
    {
        {% if outlet_type == "3EWINDKESSEL" %}
        {% set wk_settings = outlet_settings.get('windkessel_settings', {}) %}
        {% set stab_type = wk_settings.get('stabilization_type', 'fluxBased') %}
        {% set enable_stab = wk_settings.get('enable_stabilization', true) %}
        {% if enable_stab %}
        // Stabilized Windkessel velocity BC (prevents backflow divergence)
        // Stabilization types: simple, fluxBased (recommended), traction
        type                stabilizedWindkesselVelocity;
        stabilizationType   {{ stab_type }};
        beta                {{ wk_settings.get('beta', 0.9) }};
        dampingFactor       {{ wk_settings.get('damping_factor', 1.0) }};
        {% if stab_type == 'traction' %}
        rho                 {{ outlet_settings.get('rho', 1060) }};
        {% endif %}
        enableStabilization true;
        value               uniform (0 0 0);
        {% else %}
        // No stabilization - use standard pressure-velocity coupling
        type                pressureInletOutletVelocity;
        value               uniform (0 0 0);
        {% endif %}

        {% elif outlet_type == "fixedPressure" %}
        // Fixed pressure: velocity adjusts naturally
        type            pressureInletOutletVelocity;
        value           uniform (0 0 0);

        {% elif outlet_type == "resistance" %}
        // Resistance: velocity determined by flow rate
        type            zeroGradient;

        {% else %}
        // Default: zero gradient velocity
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