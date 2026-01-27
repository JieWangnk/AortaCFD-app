{# ==========================================================================
   Jinja2 Macros for AortaCFD OpenFOAM Templates

   Usage in templates:
   {% import 'macros.tpl' as macros %}
   {{ macros.world_patch_bc('zeroGradient') }}
   {{ macros.outlet_loop_start() }}
   ========================================================================== #}

{# --------------------------------------------------------------------------
   World Patch Boundary Condition
   Used when mesh has only a single 'world' patch (blockMesh without snappy)

   Args:
       bc_type: The boundary condition type (e.g., 'zeroGradient', 'fixedValue')
       value: Optional value for fixedValue types
   -------------------------------------------------------------------------- #}
{% macro world_patch_bc(bc_type='zeroGradient', value=None) %}
    // World patch mode - all boundaries combined into single patch
    world
    {
        type            {{ bc_type }};
        {% if value is not none %}
        value           {{ value }};
        {% endif %}
    }
{% endmacro %}

{# --------------------------------------------------------------------------
   Validate Outlet Patches
   Adds a warning comment if outlet_patches is not defined
   -------------------------------------------------------------------------- #}
{% macro validate_outlet_patches(outlet_patches) %}
{% if not outlet_patches %}
    // WARNING: No outlet patches defined! Simulation will likely fail.
    // Check that outlet_patches is set in the template context.
{% endif %}
{% endmacro %}

{# --------------------------------------------------------------------------
   Outlet Patch Header
   Generates the opening for an outlet patch boundary condition

   Args:
       outlet_name: Name of the outlet patch
   -------------------------------------------------------------------------- #}
{% macro outlet_patch_start(outlet_name) %}
    {{ outlet_name }}
    {
{% endmacro %}

{# --------------------------------------------------------------------------
   Outlet Patch Footer
   Closes an outlet patch boundary condition
   -------------------------------------------------------------------------- #}
{% macro outlet_patch_end() %}
    }
{% endmacro %}

{# --------------------------------------------------------------------------
   Simple Outlet BC
   For non-Windkessel outlets (zeroGradient, fixedValue, etc.)

   Args:
       bc_type: The boundary condition type
       value: Optional value (for fixedValue types)
   -------------------------------------------------------------------------- #}
{% macro simple_outlet_bc(bc_type='zeroGradient', value=None) %}
        type            {{ bc_type }};
        {% if value is not none %}
        value           {{ value }};
        {% endif %}
{% endmacro %}

{# --------------------------------------------------------------------------
   Pressure Inlet Outlet Velocity BC
   Standard outlet velocity BC for pressure-driven outlets
   -------------------------------------------------------------------------- #}
{% macro pressure_inlet_outlet_velocity() %}
        type            pressureInletOutletVelocity;
        phi             phi;
        value           uniform (0 0 0);
{% endmacro %}

{# --------------------------------------------------------------------------
   Wall BC for Velocity (No-slip)
   -------------------------------------------------------------------------- #}
{% macro wall_velocity_noslip() %}
        type            fixedValue;
        value           uniform (0 0 0);
{% endmacro %}

{# --------------------------------------------------------------------------
   Wall BC for Pressure
   -------------------------------------------------------------------------- #}
{% macro wall_pressure() %}
        type            zeroGradient;
{% endmacro %}

{# --------------------------------------------------------------------------
   Wall BC for Turbulence k
   -------------------------------------------------------------------------- #}
{% macro wall_k() %}
        type            kqRWallFunction;
        value           uniform 0;
{% endmacro %}

{# --------------------------------------------------------------------------
   Wall BC for Turbulence omega
   -------------------------------------------------------------------------- #}
{% macro wall_omega(omega_wall=1e6) %}
        type            omegaWallFunction;
        value           uniform {{ omega_wall }};
{% endmacro %}

{# --------------------------------------------------------------------------
   Wall BC for Turbulence nut
   -------------------------------------------------------------------------- #}
{% macro wall_nut() %}
        type            nutkWallFunction;
        value           uniform 0;
{% endmacro %}
