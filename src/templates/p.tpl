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
    object      p;
}
// ************************************************************************* //

dimensions      [0 2 -2 0 0 0 0];

internalField   uniform {{ initial_pressure|default(0) }};

boundaryField
{
    {% if world_patch_mode %}
    // World patch mode - all boundaries combined into single patch
    world
    {
        type            zeroGradient;
    }
    {% else %}
    // The inlet pressure is standardized here
    {{ inlet_patch }}
    {
        type            zeroGradient;
    }

    // The outlets are created dynamically based on the JSON settings
    {% set of_version = template_vars.openfoam_major_version if template_vars else openfoam_major_version %}
    {% for outlet in outlet_patches %}
    {{ outlet }}
    {
        {% if outlet_settings.type == "3EWINDKESSEL" %}
            {% if of_version >= 12 %}
        // OpenFOAM 12 modularWKPressure boundary condition
        {% set wk_settings = outlet_settings.get('windkessel_settings', {}) %}
        {% set outlet_params = wk_settings.get('outlet_parameters', {}).get(outlet, {}) %}
        {% set outlet_pressure = outlet_initial_pressures.get(outlet, initial_pressure)|default(0) %}
        type            modularWKPressure;
        phi             phi;
        order           {{ outlet_settings.get('order', 3) }};  // Higher order for stability with large R values
        R               {{ outlet_params.get('R', outlet_settings.get('R', 1000)) }};
        C               {{ outlet_params.get('C', outlet_settings.get('C', 1e-6)) }};
        Z               {{ outlet_params.get('Z', outlet_settings.get('Z', 100)) }};

        // Initial historical values for resistance-weighted initialization
        p0              {{ outlet_pressure }};      // Outlet-specific initial pressure [Pa]
        p_1             {{ outlet_pressure }};      // Pressure at t=-dt [Pa]
        q_1             0;      // Flow at t=-dt [m3/s]
        q_2             0;      // Flow at t=-2*dt [m3/s]
        q_3             0;      // Flow at t=-3*dt [m3/s]

        value           uniform {{ outlet_pressure }};
            {% else %}
        // OpenFOAM 8 WKBC boundary condition
        type            WKBC;
        index           {{ loop.index0 }};
        value           uniform 0;
            {% endif %}
        {% elif loop.first %}
        // First outlet gets fixed pressure for mass conservation
        type            fixedValue;
        value           uniform 0;
        {% else %}
        type            zeroGradient;
        {% endif %}
    }
    {% endfor %}

    // The wall condition is standardized here
    {{ wall_patch }}
    {
        type            zeroGradient;
    }
    {% endif %}
}
// ************************************************************************* //