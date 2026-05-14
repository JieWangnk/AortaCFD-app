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

{# IMPORTANT: OpenFOAM incompressible solvers use KINEMATIC pressure (m²/s²) #}
{# initial_pressure is passed in Pa (dynamic), so we divide by rho to get kinematic #}
{% set rho = outlet_settings.get('rho', 1060) if outlet_settings else 1060 %}
{% set kinematic_pressure = (initial_pressure|default(0)) / rho %}
internalField   uniform {{ kinematic_pressure|round(6) }};

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

    // The outlets are created dynamically based on the JSON settings.
    // Per-outlet dispatch: each outlet looks up its effective type in
    // _outlet_type_map (built by BoundaryConditionSetup._build_outlet_type_map
    // from outlets.type defaults + outlets.per_outlet overrides + legacy
    // outlets.pressure_anchor). v1.4.0 — see CHANGELOG theme B.
    {% set of_version = template_vars.openfoam_major_version if template_vars else openfoam_major_version %}
    {% set default_outlet_type = outlet_settings.get('type', '3EWINDKESSEL') %}
    {% set outlet_type_map = outlet_settings.get('_outlet_type_map', {}) %}
    {% if not outlet_patches %}
    // WARNING: No outlet patches defined! Simulation will likely fail.
    // Check that outlet_patches is set in the template context.
    {% endif %}
    {% for outlet in outlet_patches|default([]) %}
    {{ outlet }}
    {
        {% set _entry = outlet_type_map.get(outlet, {'type': default_outlet_type}) %}
        {% set outlet_type = _entry.get('type', default_outlet_type) %}
        {% if outlet_type == "fixedValue" %}
        // Per-outlet fixed pressure ({{ _entry.get('pressure_mmHg', 80) }} mmHg{% if _entry.get('_from') %}; from {{ _entry.get('_from') }}{% endif %})
        type            fixedValue;
        value           uniform {{ _entry.get('p_kinematic', 0)|round(6) }};

        {% elif outlet_type == "3EWINDKESSEL" or outlet_type == "2EWINDKESSEL" %}
            {# ========== Option 1: Windkessel (Physiological) ========== #}
            {# 3-Element: R-C-Z model for pulsatile flow #}
            {# 2-Element: R-C model (Z=0) for steady/CONSTANT flow #}
            {% if of_version >= 12 %}
        // OpenFOAM 12+ modularWKPressure boundary condition
        // Windkessel model - 3-Element (R-C-Z) or 2-Element (R-C, Z=0) - ALL KINEMATIC UNITS
        // Prefer per-outlet windkessel_settings; fall back to the global block
        {% set wk_settings = _entry.get('windkessel_settings', outlet_settings.get('windkessel_settings', {})) %}
        {% set outlet_params = wk_settings.get('outlet_parameters', {}).get(outlet, {}) %}
        {% set outlet_pressure_pa = outlet_initial_pressures.get(outlet, initial_pressure)|default(0) %}
        {% set fluid_rho = outlet_settings.get('rho', 1060) %}
        {% set coupling = wk_settings.get('coupling_mode', 'implicit') %}
        {# Get dynamic (SI) parameters and convert to kinematic #}
        {% set R_dyn = outlet_params.get('R', wk_settings.get('R', 1e9)) %}
        {% set C_dyn = outlet_params.get('C', wk_settings.get('C', 1e-9)) %}
        {% set Z_dyn = outlet_params.get('Z', wk_settings.get('Z', 1e8)) %}
        {# Convert to kinematic: R_kin = R_dyn/rho, C_kin = C_dyn*rho, p_kin = p/rho #}
        {% set R_kin = R_dyn / fluid_rho %}
        {% set C_kin = C_dyn * fluid_rho %}
        {% set Z_kin = Z_dyn / fluid_rho %}
        {% set p_kin = outlet_pressure_pa / fluid_rho %}
        {# Initialize q_1 to expected steady-state flow to prevent startup divergence #}
        {% set q_init = outlet_params.get('q_init', 0) %}
        type            modularWKPressure;
        phi             phi;
        U               U;
        couplingMode    {{ coupling }};
        order           {{ wk_settings.get('order', 3) }};
        // Windkessel parameters (KINEMATIC units)
        // Conversion: R_kin = R_dyn/rho [s/m], C_kin = C_dyn*rho [m], p_kin = p/rho [m²/s²]
        R               {{ R_kin }};    // s/m (= {{ R_dyn }} Pa·s/m³ / {{ fluid_rho }})
        C               {{ C_kin }};    // m (= {{ C_dyn }} m³/Pa × {{ fluid_rho }})
        Z               {{ Z_kin }};    // s/m (= {{ Z_dyn }} Pa·s/m³ / {{ fluid_rho }})
        // Fluid density (reference only - not used in calculations)
        rho             {{ fluid_rho }};
        // Initial/reference pressure [m²/s²] (kinematic)
        p0              {{ p_kin|round(6) }};
        // State variables - initialized to steady-state values for smooth startup
        // q_init is set to expected mean flow (from Murray's law) to prevent
        // startup divergence caused by sudden flow imposition on zero-history WK state
        p_1             {{ p_kin|round(6) }};
        q_1             {{ q_init }};
        q_2             {{ q_init }};
        q_3             {{ q_init }};
        // Initial field value [m²/s²] (kinematic)
        value           uniform {{ p_kin|round(6) }};
            {% else %}
        // OpenFOAM 8 WKBC boundary condition
        type            WKBC;
        index           {{ loop.index0 }};
        value           uniform 0;
            {% endif %}

        {% elif outlet_type == "fixedPressure" %}
            {# ========== Option 2: Fixed Pressure (Simple) ========== #}
        // Fixed pressure outlet (kinematic pressure m²/s² = dynamic Pa / rho).
        // Prefer per-outlet pressure_mmHg from the type map; fall back to the global setting.
        {% set _p_mmhg = _entry.get('pressure_mmHg', outlet_settings.get('pressure_mmHg', 80)) %}
        {% set _p_kin = _entry.get('p_kinematic', _p_mmhg * 133.322 / 1060) %}
        type            fixedValue;
        value           uniform {{ _p_kin|round(6) }};  // {{ _p_mmhg }} mmHg

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
            {# ========== Fallback: zeroGradient outlets ========== #}
            {# With outlets.pressure_anchor set, the anchored outlet is handled #}
            {# in the early branch above; the rest fall through to zeroGradient. #}
            {# Without an anchor, the validator in builder.py blocks pulsatile-  #}
            {# inlet configs and steady inlets find their own pressure equilibrium.#}
        type            zeroGradient;
        {% endif %}
    }
    {% endfor %}

    // The wall condition is standardized here
    {{ wall_patch }}
    {
        type            zeroGradient;
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