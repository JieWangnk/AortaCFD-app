/*--------------------------------*- C++ -*----------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  {{ config.template_vars.openfoam_version }}
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    object      surfaceFeaturesDict;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

surfaces ({% for patch_name in patches %}"{{ patch_name }}.stl"{% if not loop.last %} {% endif %}{% endfor %});

// Identify a feature when angle between faces < includedAngle
// Higher value = more edges detected (captures gentle curves at patch junctions)
// 170° = detect edges with deviation > 10° from flat (good for inlet-wall transitions)
includedAngle   {{ config.mesh.SNAPPY_SETTINGS.get('includedAngle', 170) }};

{% if config.mesh.SNAPPY_SETTINGS.get('span_refinement_enabled', False) %}
// ==========================================================================
// SPAN-BASED REFINEMENT: Closeness data for insideSpan mode
// ==========================================================================
// Generates closeness field for wall surface to enable cellsAcrossSpan
// refinement in snappyHexMesh. This guarantees minimum cells across the
// vessel diameter at every cross-section.
//
// Use case: Aortic coarctation, variable diameter vessels, small branches
// ==========================================================================
closeness
{
    // Only wall surface needs closeness (defines internal span)
    surface     "{{ wall_patch }}.stl";

    // Generate internal point closeness field for span calculation
    pointCloseness  yes;
}
{% endif %}