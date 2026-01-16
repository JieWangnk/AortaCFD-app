/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  12
     \\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    location    "system";
    object      controlDict;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

application     foamRun;

solver          incompressibleFluid;

startFrom       {{ controlDict.get('startFrom', 'startTime') }};

startTime       {{ controlDict.get('startTime', 0) }};

stopAt          {{ controlDict.get('stopAt', 'endTime') }};

endTime         {{ controlDict.endTime }};

deltaT          {{ controlDict.deltaT }};

writeControl    {{ controlDict.get('writeControl', 'adjustableRunTime') }};

writeInterval   {{ controlDict.get('writeInterval', 0.01) }};

purgeWrite      {{ controlDict.get('purgeWrite', 0) }};

writeFormat     {{ controlDict.get('writeFormat', 'binary') }};

writePrecision  {{ controlDict.get('writePrecision', 6) }};

writeCompression {{ controlDict.get('writeCompression', 'off') }};

timeFormat      {{ controlDict.get('timeFormat', 'general') }};

timePrecision   {{ controlDict.get('timePrecision', 6) }};

runTimeModifiable {{ controlDict.get('runTimeModifiable', 'true') }};

adjustTimeStep  {{ controlDict.get('adjustTimeStep', 'yes') }};

maxCo           {{ controlDict.get('maxCo', 1.2) }};

maxDeltaT       {{ controlDict.get('maxDeltaT', 1e-3) }};
{# Use pre-computed values from template_context.py when available, fallback to inline computation for backward compatibility #}
{%- set _outlet_type = config.get('outlets', {}).get('type', '') or config.get('boundary_conditions', {}).get('outlets', {}).get('type', '') -%}
{%- set _needs_wk = needs_windkessel_lib if needs_windkessel_lib is defined else (config.get('windkessel_enabled', False) or _outlet_type in ['2EWINDKESSEL', '3EWINDKESSEL']) -%}
{%- if _needs_wk %}

libs
(
    "libmodularWKPressure.so"
);
{%- endif %}
{%- set hemodynamics = config.get('hemodynamics', {}) -%}
{%- set inlet_settings = config.get('inlet', {}) or config.get('boundary_conditions', {}).get('inlet', {}) -%}
{%- set _inlet_type = inlet_type if inlet_type is defined else inlet_settings.get('type', 'CONSTANT').upper() -%}
{%- set _is_pulsatile = is_pulsatile if is_pulsatile is defined else (_inlet_type in ['TIMEVARYING', 'WOMERSLEY']) -%}
{%- set cardiac_cycle_val = cardiac_cycle if cardiac_cycle is defined and cardiac_cycle else config.get('cardiac_cycle', 0.8) -%}
{%- set runtime_funcs = hemodynamics.get('runtime_functions', {}) -%}
{%- set enable_wss = runtime_funcs.get('wallShearStress', true) -%}
{%- set enable_fieldavg = runtime_funcs.get('fieldAverage', 'auto') -%}
{%- set enable_pressure = runtime_funcs.get('pressureMonitoring', true) -%}
{%- if enable_fieldavg == 'auto' -%}
    {%- set enable_fieldavg = _is_pulsatile -%}
{%- endif -%}
{%- set tawss_settings = hemodynamics.get('tawss_settings', {}) -%}
{%- set skip_cycles = tawss_settings.get('skip_cycles', 2) -%}
{%- set time_start = skip_cycles * cardiac_cycle_val -%}
{%- set periodic_restart = tawss_settings.get('periodicRestart', true) -%}
{%- set geom = config.get('geometry', {}) -%}
{%- set inlet_patch = geom.get('inlet_keywords_ordered', 'inlet') -%}
{%- set outlet_patches = geom.get('outlet_keywords_ordered', ['outlet']) -%}
{%- set wall_patch = geom.get('wall_keywords_ordered', 'wall') -%}
{%- if outlet_patches is string -%}{%- set outlet_patches = [outlet_patches] -%}{%- endif -%}
{%- set hemodynamics_enabled = enable_wss or enable_fieldavg or enable_pressure -%}
{%- set user_functions = config.get('simulation_control', {}).get('controlDict', {}).get('functions', []) %}
{%- if hemodynamics_enabled or user_functions %}

functions
{
{%- for func in user_functions %}
    #includeFunc {{ func }}
{%- endfor %}
{%- if enable_wss %}
    wallShearStress
    {
        type            wallShearStress;
        libs            ("libfieldFunctionObjects.so");
        writeControl    writeTime;
        patches         ({{ wall_patch }});
        log             true;
    }
{%- endif %}
{%- if enable_fieldavg and _is_pulsatile %}

    fieldAverageWSS
    {
        type            fieldAverage;
        libs            ("libfieldFunctionObjects.so");
        writeControl    writeTime;
        timeStart       {{ time_start }};
        periodicRestart {{ 'true' if periodic_restart else 'false' }};
        restartPeriod   {{ cardiac_cycle_val }};
        restartOnRestart false;

        fields
        (
            wallShearStress
            {
                mean        on;
                prime2Mean  off;
                base        time;
            }
        );
    }
{%- endif %}
{%- if enable_pressure %}

    {{ inlet_patch }}Pressure
    {
        type            surfaceFieldValue;
        libs            ("libfieldFunctionObjects.so");
        writeControl    timeStep;
        writeInterval   10;
        writeFields     false;
        regionType      patch;
        name            {{ inlet_patch }};
        operation       areaAverage;
        fields          (p);
        log             false;
    }
{%- for outlet in outlet_patches %}

    {{ outlet }}Pressure
    {
        type            surfaceFieldValue;
        libs            ("libfieldFunctionObjects.so");
        writeControl    timeStep;
        writeInterval   10;
        writeFields     false;
        regionType      patch;
        name            {{ outlet }};
        operation       areaAverage;
        fields          (p);
        log             false;
    }
{%- endfor %}
{%- endif %}
}
{%- endif %}

// ************************************************************************* //
