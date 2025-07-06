/*--------------------------------*- C++ -*----------------------------------*\\
  ... (FoamFile Header) ...
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      surfaceFeaturesDict;
}

surfaces
(
    {# This loop dynamically adds all patch files #}
    {% for patch_name in patches %}
    "{{ patch_name }}.stl"
    {% endfor %}
);

includedAngle   {{ snappy_settings.resolveFeatureAngle }};

{% if config.mesh.SNAPPY_SETTINGS.get('span_refinement_enabled', False) %}
// Enable closeness calculation for span-based refinement
// Critical for aortic coarctation and narrow vessel regions
closeness
{
    pointCloseness          yes;
    internalCloseness       yes;
}
{% endif %}