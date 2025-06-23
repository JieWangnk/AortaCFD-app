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