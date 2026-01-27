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
        {% if inlet_settings.type in ["TIMEVARYING", "WOMERSLEY", "MRI"] %}
        type            timeVaryingMappedFixedValue;
        offset          (0 0 0);
        setAverage      false;
        {% elif inlet_settings.type == "CONSTANT" or inlet_settings.type == "PARABOLIC" %}
        {% set inlet_profile = inlet_settings.get('profile', 'plug').lower() %}
        {% if inlet_profile in ['wall_distance', 'elliptical'] %}
        // CONSTANT inlet with non-uniform {{ inlet_profile }} profile
        // Uses boundaryData from distance-wall profile generator
        type            timeVaryingMappedFixedValue;
        offset          (0 0 0);
        setAverage      false;
        {% else %}
        // CONSTANT inlet with uniform {{ inlet_profile }} profile
        type            fixedValue;
        value           uniform {{ inlet_velocity_vector }};
        {% endif %}
        {% else %}
        type            fixedValue;
        value           uniform (0 0 0);
        {% endif %}
    }

    // The outlets are created dynamically based on the JSON settings
    {% set outlet_type = outlet_settings.get('type', '3EWINDKESSEL') %}
    {% set wk_settings = outlet_settings.get('windkessel_settings', {}) %}
    {% set enable_stabilization = wk_settings.get('enable_stabilization', false) %}
    {% set stabilization_type = wk_settings.get('stabilization_type', 'simple') %}
    {% set beta = wk_settings.get('beta', 0.5) %}
    {% set damping_factor = wk_settings.get('damping_factor', 1.0) %}
    {% if not outlet_patches %}
    // WARNING: No outlet patches defined! Simulation will likely fail.
    // Check that outlet_patches is set in the template context.
    {% endif %}
    {% for outlet in outlet_patches|default([]) %}
    {{ outlet }}
    {
        {% if outlet_type == "3EWINDKESSEL" and enable_stabilization %}
        // Stabilized Windkessel velocity BC - modularWKPressure library
        // Backflow stabilization methods (damping formula: V_out = (1 - damping) * V_backflow):
        //   simple:    damping = beta           (DEFAULT, most robust, ignores dampingFactor)
        //   fluxBased: damping = beta × dampingFactor  (FVM-consistent, uses phi field)
        //   traction:  damping = beta × dampingFactor  (physics-based, Moghadam 2011)
        // Robustness: simple > fluxBased ≈ traction (for same effective damping)
        type            stabilizedWindkesselVelocity;
        enableStabilization true;
        stabilizationType {{ stabilization_type }};
        beta            {{ beta }};
        dampingFactor   {{ damping_factor }};
        value           uniform (0 0 0);

        {% elif outlet_type in ["2EWINDKESSEL", "3EWINDKESSEL"] %}
        // Windkessel outlet: Use pressureInletOutletVelocity for proper p-U coupling
        // - Ensures velocity is consistent with pressure-driven Windkessel BC
        // - Better stability than inletOutlet for pressure BCs
        // For enhanced backflow stabilization, set enable_stabilization: true in config
        type            pressureInletOutletVelocity;
        phi             phi;
        value           uniform (0 0 0);

        {% elif outlet_type == "fixedPressure" %}
        // Fixed pressure: use pressureInletOutletVelocity for better coupling
        type            pressureInletOutletVelocity;
        phi             phi;
        value           uniform (0 0 0);

        {% elif outlet_type == "resistance" %}
        // Resistance: velocity determined by flow rate
        type            pressureInletOutletVelocity;
        phi             phi;
        value           uniform (0 0 0);

        {% else %}
        // Default: pressureInletOutletVelocity for pressure-driven outlets
        type            pressureInletOutletVelocity;
        phi             phi;
        value           uniform (0 0 0);
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