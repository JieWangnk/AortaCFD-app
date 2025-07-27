/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  {{ config.openfoam_version }}
     \\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      snappyHexMeshDict;
}
// ************************************************************************* //

castellatedMesh {{ config.mesh.SNAPPY_SETTINGS.get('castellatedMesh', 'true') | string | lower }};
snap            {{ config.mesh.SNAPPY_SETTINGS.get('snap', 'true') | string | lower }};
addLayers       {{ config.mesh.SNAPPY_SETTINGS.get('addLayers', 'true') | string | lower }};

geometry
{
    {% for patch_name in patches %}
    "{{ patch_name }}.stl"
    {
        type triSurfaceMesh;
        file "{{ patch_name }}.stl";
        name {{ patch_name }};
    }
    {% endfor %}
};

castellatedMeshControls
{
    maxLocalCells       {{ config.mesh.SNAPPY_SETTINGS.get('maxLocalCells', 10000000) }};
    maxGlobalCells      {{ config.mesh.SNAPPY_SETTINGS.get('maxGlobalCells', 20000000) }};
    minRefinementCells  {{ config.mesh.SNAPPY_SETTINGS.get('minRefinementCells', 10) }};
    maxLoadUnbalance    {{ config.mesh.SNAPPY_SETTINGS.get('maxLoadUnbalance', 0.10) }};
    nCellsBetweenLevels {{ config.mesh.SNAPPY_SETTINGS.get('nCellsBetweenLevels', 3) }};

    features
    (
        {% for patch_name in patches %}
        {
            file "{{ patch_name }}.eMesh";
            level {{ config.mesh.SNAPPY_SETTINGS.get('featureLevel', 2) }};
        }
        {% endfor %}
    );

    refinementSurfaces
    {
        {% for patch_name in patches %}
        {{ patch_name }}
        {
            level ({{ config.mesh.SNAPPY_SETTINGS.get('surfaceRefinementLevels', [1, 2])[0] }} {{ config.mesh.SNAPPY_SETTINGS.get('surfaceRefinementLevels', [1, 2])[1] }});
        }
        {% endfor %}
    }
    
    refinementRegions
    {
    {% if config.mesh.SNAPPY_SETTINGS.get('span_refinement_enabled', False) %}
        // Span-based refinement for aortic coarctation and narrow regions
        // Guarantees minimum cells across vessel diameter
        {{ wall_patch }}
        {
            mode            insideSpan;
            level           ({{ config.mesh.SNAPPY_SETTINGS.get('span_refinement_distance', 1000) }} {{ config.mesh.SNAPPY_SETTINGS.get('span_refinement_level', 2) }});
            cellsAcrossSpan {{ config.mesh.SNAPPY_SETTINGS.get('cells_across_span', 20) }};
        }
    {% endif %}
    }

    locationInMesh ({{ '%.6g' % internal_point[0] }} {{ '%.6g' % internal_point[1] }} {{ '%.6g' % internal_point[2] }});
    allowFreeStandingZoneFaces true;
    resolveFeatureAngle {{ config.mesh.SNAPPY_SETTINGS.get('resolveFeatureAngle', 30) }};
};

snapControls
{
    nSmoothPatch        {{ config.mesh.SNAPPY_SETTINGS.get('nSmoothPatch', 3) }};
    tolerance           {{ config.mesh.SNAPPY_SETTINGS.get('snapTolerance', 2.0) }};
    nSolveIter          {{ config.mesh.SNAPPY_SETTINGS.get('nSolveIter', 30) }};
    nRelaxIter          {{ config.mesh.SNAPPY_SETTINGS.get('nRelaxIter', 5) }};
    nFeatureSnapIter    {{ config.mesh.SNAPPY_SETTINGS.get('nFeatureSnapIter', 10) }};
    implicitFeatureSnap {{ config.mesh.SNAPPY_SETTINGS.get('implicitFeatureSnap', 'false') | string | lower }};
    explicitFeatureSnap {{ config.mesh.SNAPPY_SETTINGS.get('explicitFeatureSnap', 'true') | string | lower }};
    multiRegionFeatureSnap {{ config.mesh.SNAPPY_SETTINGS.get('multiRegionFeatureSnap', 'false') | string | lower }};
};

addLayersControls
{
    relativeSizes       {{ config.mesh.SNAPPY_SETTINGS.get('relativeSizes', 'true') | string | lower }};
    layers
    {
        "{{ wall_patch }}"
        {
            nSurfaceLayers {{ config.mesh.SNAPPY_SETTINGS.get('addLayer', 5) }};
        }
    }
    expansionRatio      {{ config.mesh.SNAPPY_SETTINGS.get('expansionRatio', 1.2) }};
    finalLayerThickness {{ config.mesh.SNAPPY_SETTINGS.get('finalLayerThickness', 0.3) }};
    minThickness        {{ config.mesh.SNAPPY_SETTINGS.get('minThickness', 0.1) }};
    nGrow               {{ config.mesh.SNAPPY_SETTINGS.get('nGrow', 0) }};
    featureAngle        {{ config.mesh.SNAPPY_SETTINGS.get('featureAngle', 60) }};
    slipFeatureAngle    {{ config.mesh.SNAPPY_SETTINGS.get('slipFeatureAngle', 30) }};
    nRelaxIter          {{ config.mesh.SNAPPY_SETTINGS.get('addLayers_nRelaxIter', 5) }};
    nSmoothNormals      {{ config.mesh.SNAPPY_SETTINGS.get('nSmoothNormals', 1) }};
    nSmoothSurfaceNormals {{ config.mesh.SNAPPY_SETTINGS.get('nSmoothSurfaceNormals', 1) }};
    nSmoothThickness    {{ config.mesh.SNAPPY_SETTINGS.get('nSmoothThickness', 10) }};
    maxFaceThicknessRatio {{ config.mesh.SNAPPY_SETTINGS.get('maxFaceThicknessRatio', 0.5) }};
    maxThicknessToMedialRatio {{ config.mesh.SNAPPY_SETTINGS.get('maxThicknessToMedialRatio', 0.3) }};
    minMedianAxisAngle  {{ config.mesh.SNAPPY_SETTINGS.get('minMedianAxisAngle', 90) }};
    nBufferCellsNoExtrude {{ config.mesh.SNAPPY_SETTINGS.get('nBufferCellsNoExtrude', 0) }};
    nLayerIter          {{ config.mesh.SNAPPY_SETTINGS.get('nLayerIter', 50) }};
}

meshQualityControls
{
    maxNonOrtho         {{ config.mesh.SNAPPY_SETTINGS.get('maxNonOrtho', 65) }};
    maxBoundarySkewness {{ config.mesh.SNAPPY_SETTINGS.get('maxBoundarySkewness', 20) }};
    maxInternalSkewness {{ config.mesh.SNAPPY_SETTINGS.get('maxInternalSkewness', 4) }};
    maxConcave          {{ config.mesh.SNAPPY_SETTINGS.get('maxConcave', 80) }};
    minVol              {{ config.mesh.SNAPPY_SETTINGS.get('minVol', 1e-13) }};
    minTetQuality       {{ config.mesh.SNAPPY_SETTINGS.get('minTetQuality', 1e-30) }};
    minArea             {{ config.mesh.SNAPPY_SETTINGS.get('minArea', -1) }};
    minTwist            {{ config.mesh.SNAPPY_SETTINGS.get('minTwist', 0.02) }};
    minTriangleTwist    {{ config.mesh.SNAPPY_SETTINGS.get('minTriangleTwist', 0.02) }};
    minDeterminant      {{ config.mesh.SNAPPY_SETTINGS.get('minDeterminant', 0.001) }};
    minFaceWeight       {{ config.mesh.SNAPPY_SETTINGS.get('minFaceWeight', 0.05) }};
    minVolRatio         {{ config.mesh.SNAPPY_SETTINGS.get('minVolRatio', 0.01) }};
    maxAspectRatio      {{ config.mesh.SNAPPY_SETTINGS.get('maxAspectRatio', 10) }};
    nSmoothScale        {{ config.mesh.SNAPPY_SETTINGS.get('nSmoothScale', 4) }};
    errorReduction      {{ config.mesh.SNAPPY_SETTINGS.get('errorReduction', 0.75) }};
};

debug 0;

writeFlags
(
    scalarLevels
    layerSets
    layerFields
);

mergeTolerance {{ config.mesh.SNAPPY_SETTINGS.get('mergeTolerance', 1e-6) }};

// ************************************************************************* //