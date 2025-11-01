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
        // Stabilized Windkessel velocity BC (prevents backflow divergence)
        type                stabilizedWindkesselVelocity;
        beta                {{ outlet_settings.get('windkessel_settings', {}).get('beta', 1.0) }};
        enableStabilization {{ 'true' if outlet_settings.get('windkessel_settings', {}).get('enable_stabilization', True) else 'false' }};

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