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
    {% set outlet_type = outlet_settings.get('type', '3EWINDKESSEL') %}
    {% for outlet in outlet_patches %}
    {{ outlet }}
    {
        {% if outlet_type == "3EWINDKESSEL" %}
            {# ========== Option 1: Windkessel (Physiological) ========== #}
            {% if of_version >= 12 %}
        // OpenFOAM 12+ modularWKPressure boundary condition
        // 3-Element Windkessel model (R-C-Z) with implicit coupling
        {% set wk_settings = outlet_settings.get('windkessel_settings', {}) %}
        {% set outlet_params = wk_settings.get('outlet_parameters', {}).get(outlet, {}) %}
        {% set outlet_pressure = outlet_initial_pressures.get(outlet, initial_pressure)|default(0) %}
        {% set fluid_rho = outlet_settings.get('rho', 1060) %}
        {% set coupling = wk_settings.get('coupling_mode', 'implicit') %}
        type            modularWKPressure;
        phi             phi;
        U               U;
        couplingMode    {{ coupling }};
        order           {{ wk_settings.get('order', 3) }};
        // Windkessel parameters (dynamic units: Pa·s/m³, m³/Pa)
        R               {{ outlet_params.get('R', wk_settings.get('R', 1e9)) }};
        C               {{ outlet_params.get('C', wk_settings.get('C', 1e-9)) }};
        Z               {{ outlet_params.get('Z', wk_settings.get('Z', 1e8)) }};
        // Fluid density for kinematic conversion
        rho             {{ fluid_rho }};
        // Initial/reference pressure [Pa] (dynamic)
        p0              {{ outlet_pressure }};
        // State variables (initialized to reference)
        p_1             {{ outlet_pressure }};
        q_1             0;
        q_2             0;
        q_3             0;
        // Initial value (kinematic pressure m²/s²)
        value           uniform {{ (outlet_pressure / fluid_rho)|round(6) }};
            {% else %}
        // OpenFOAM 8 WKBC boundary condition
        type            WKBC;
        index           {{ loop.index0 }};
        value           uniform 0;
            {% endif %}

        {% elif outlet_type == "fixedPressure" %}
            {# ========== Option 2: Fixed Pressure (Simple) ========== #}
        // Fixed pressure outlet - all outlets at same pressure
        {% set pressure_pa = (outlet_settings.get('pressure_mmHg', 80) * 133.322)|int %}
        type            fixedValue;
        value           uniform {{ pressure_pa }};  // {{ outlet_settings.get('pressure_mmHg', 80) }} mmHg

        {% elif outlet_type == "resistance" %}
            {# ========== Option 3: Resistance (Advanced) ========== #}
            {% set outlet_resistances = outlet_settings.get('outlet_resistances', {}) %}
            {% if outlet in outlet_resistances %}
        // Individual resistance for this outlet
        {% set R_value = outlet_resistances[outlet] %}
        type            flowRateOutletVelocity;  // Resistance-based
        flowRate        {{ R_value }};
        value           uniform 0;
            {% else %}
        // No resistance specified - fallback to zeroGradient
        type            zeroGradient;
            {% endif %}

        {% else %}
            {# ========== Fallback: zeroGradient (Debug only) ========== #}
            {% if loop.last %}
        // Last outlet (abdominal) gets fixed pressure for mass conservation
        type            fixedValue;
        value           uniform 0;
            {% else %}
        type            zeroGradient;
            {% endif %}
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