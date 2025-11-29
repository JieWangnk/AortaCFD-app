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

    {% if bounding_box_refine_level and bounding_box_refine_level > 0 %}
    // Bounding box for two-stage refinement (coarse blockMesh + snappy refinement)
    geometryRefinementBox
    {
        type searchableBox;
        min ({{ '%.6g' % geometry_bbox.min[0] }} {{ '%.6g' % geometry_bbox.min[1] }} {{ '%.6g' % geometry_bbox.min[2] }});
        max ({{ '%.6g' % geometry_bbox.max[0] }} {{ '%.6g' % geometry_bbox.max[1] }} {{ '%.6g' % geometry_bbox.max[2] }});
    }
    {% endif %}
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
            {# Feature level should match max surface refinement to avoid over-refinement #}
            {% set surface_levels = config.mesh.SNAPPY_SETTINGS.get('surfaceRefinementLevels', [1, 1]) %}
            {% set auto_feature_level = surface_levels[1] if surface_levels|length > 1 else surface_levels[0] %}
            level {{ config.mesh.SNAPPY_SETTINGS.get('featureLevel', auto_feature_level) }};
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
    {% if bounding_box_refine_level and bounding_box_refine_level > 0 %}
        // Two-stage mesh refinement: bounding box refinement for fine meshes
        // This prevents blockMesh from becoming too large (> 5M cells)
        // Strategy: coarse blockMesh (2-4mm) + snappyHexMesh refinement inside geometry
        geometryRefinementBox
        {
            mode            inside;
            levels          (({{ bounding_box_refine_level }} {{ bounding_box_refine_level }}));
        }
    {% endif %}
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
    // Number of patch smoothing iterations before snapping
    nSmoothPatch        {{ config.mesh.SNAPPY_SETTINGS.get('nSmoothPatch', 3) }};

    // Snap tolerance as fraction of local cell size
    tolerance           {{ config.mesh.SNAPPY_SETTINGS.get('snapTolerance', 2.0) }};

    // Number of mesh displacement relaxation iterations
    // Note: Too high values can over-correct and degrade mesh quality
    nSolveIter          {{ config.mesh.SNAPPY_SETTINGS.get('nSolveIter', 30) }};

    // Maximum number of snapping relaxation iterations
    // Keep low (3-5) to avoid over-correction on curved surfaces
    nRelaxIter          {{ config.mesh.SNAPPY_SETTINGS.get('nRelaxIter', 5) }};

    // Number of feature edge snapping iterations
    // Keep moderate - too high causes mesh failures on curved geometry
    nFeatureSnapIter    {{ config.mesh.SNAPPY_SETTINGS.get('nFeatureSnapIter', 10) }};

    // Detect features by sampling the surface (not recommended for curved geometry)
    implicitFeatureSnap {{ config.mesh.SNAPPY_SETTINGS.get('implicitFeatureSnap', 'false') | string | lower }};

    // Use eMesh files for explicit feature capture (recommended)
    explicitFeatureSnap {{ config.mesh.SNAPPY_SETTINGS.get('explicitFeatureSnap', 'true') | string | lower }};

    // Detect features between multiple surfaces
    multiRegionFeatureSnap {{ config.mesh.SNAPPY_SETTINGS.get('multiRegionFeatureSnap', 'false') | string | lower }};
};

addLayersControls
{
    // ==========================================================================
    // Boundary Layer Settings for Transitional Flow
    // ==========================================================================
    // For transitional models (γ-Reθ SST, LES/DES): target y+ ≈ 1
    // Recommended: 7-10 prism layers with growth ratio 1.2
    // First layer thickness should achieve y+ < 2
    // ==========================================================================

    relativeSizes       {{ config.mesh.SNAPPY_SETTINGS.get('relativeSizes', 'true') | string | lower }};

    layers
    {
        "{{ wall_patch }}"
        {
            // Number of boundary layers
            // Recommended: 7-10 for transitional flow, 5 minimum for RANS
            nSurfaceLayers {{ config.mesh.SNAPPY_SETTINGS.get('addLayer', 7) }};
        }
    }

    // Layer expansion ratio (cell-to-cell growth)
    // Recommended: 1.2 for arterial flows (smooth transition)
    expansionRatio      {{ config.mesh.SNAPPY_SETTINGS.get('expansionRatio', 1.2) }};

    {% if config.mesh.SNAPPY_SETTINGS.get('firstLayerThickness') is not none %}
    // First layer thickness (relative to cell size if relativeSizes=true)
    // For y+ ≈ 1: typically 0.025mm for blood flow
    firstLayerThickness {{ config.mesh.SNAPPY_SETTINGS.get('firstLayerThickness') }};
    {% elif config.mesh.SNAPPY_SETTINGS.get('finalLayerThickness') is not none %}
    // Final (outer) layer thickness relative to cell size
    finalLayerThickness {{ config.mesh.SNAPPY_SETTINGS.get('finalLayerThickness') }};
    {% else %}
    finalLayerThickness 0.3;
    {% endif %}

    // Minimum total layer thickness (relative)
    // Prevents overly thin layers that cause high aspect ratio
    minThickness        {{ config.mesh.SNAPPY_SETTINGS.get('minThickness', 0.1) }};

    // Number of cells to grow layers from surface
    nGrow               {{ config.mesh.SNAPPY_SETTINGS.get('nGrow', 0) }};

    // Feature angle for layer termination [deg]
    // Higher values (100-130) allow layers around tighter curves
    featureAngle        {{ config.mesh.SNAPPY_SETTINGS.get('featureAngle', 130) }};

    // Angle for slip at feature edges
    slipFeatureAngle    {{ config.mesh.SNAPPY_SETTINGS.get('slipFeatureAngle', 30) }};

    // Layer addition relaxation iterations
    nRelaxIter          {{ config.mesh.SNAPPY_SETTINGS.get('addLayers_nRelaxIter', 5) }};

    // Smoothing iterations for layer normals
    nSmoothNormals      {{ config.mesh.SNAPPY_SETTINGS.get('nSmoothNormals', 3) }};

    // Smoothing iterations for surface normals
    nSmoothSurfaceNormals {{ config.mesh.SNAPPY_SETTINGS.get('nSmoothSurfaceNormals', 1) }};

    // Smoothing iterations for layer thickness
    nSmoothThickness    {{ config.mesh.SNAPPY_SETTINGS.get('nSmoothThickness', 10) }};

    // Maximum ratio of face thickness to point thickness
    maxFaceThicknessRatio {{ config.mesh.SNAPPY_SETTINGS.get('maxFaceThicknessRatio', 0.5) }};

    // Maximum ratio of layer thickness to medial distance
    // Lower values (0.3) for curved geometry to prevent self-intersection
    maxThicknessToMedialRatio {{ config.mesh.SNAPPY_SETTINGS.get('maxThicknessToMedialRatio', 0.3) }};

    // Minimum angle for medial axis point selection [deg]
    minMedianAxisAngle  {{ config.mesh.SNAPPY_SETTINGS.get('minMedianAxisAngle', 90) }};

    // Buffer cells for layer extrusion exclusion
    nBufferCellsNoExtrude {{ config.mesh.SNAPPY_SETTINGS.get('nBufferCellsNoExtrude', 0) }};

    // Maximum number of layer addition iterations
    nLayerIter          {{ config.mesh.SNAPPY_SETTINGS.get('nLayerIter', 50) }};
}

meshQualityControls
{
    // ==========================================================================
    // Mesh Quality Criteria for Curved Geometry / Transitional Flow Simulations
    // ==========================================================================
    // These thresholds are optimized for aortic/arterial CFD simulations
    // where mesh quality directly impacts simulation stability and accuracy.
    //
    // Non-orthogonality correction guidelines:
    //   < 65°: no correctors needed
    //   65-75°: 1 non-orthogonal corrector
    //   75-82°: 2 non-orthogonal correctors
    //   > 82°: consider improving mesh
    //
    // For transitional flow (γ-Reθ SST, LES/DES): y+ ≈ 1 required
    // ==========================================================================

    // Maximum non-orthogonality angle [deg]
    // Recommended: 65 for robust simulation, <50 for high accuracy
    // >85 will likely cause divergence
    maxNonOrtho         {{ config.mesh.SNAPPY_SETTINGS.get('maxNonOrtho', 65) }};

    // Maximum skewness at boundary faces
    // Critical for wall shear stress accuracy in arterial flows
    maxBoundarySkewness {{ config.mesh.SNAPPY_SETTINGS.get('maxBoundarySkewness', 20) }};

    // Maximum skewness for internal faces
    // Recommended: <2 for curved geometry, <0.85 for high accuracy
    // >4 causes significant numerical diffusion
    maxInternalSkewness {{ config.mesh.SNAPPY_SETTINGS.get('maxInternalSkewness', 2) }};

    // Maximum concavity angle [deg]
    maxConcave          {{ config.mesh.SNAPPY_SETTINGS.get('maxConcave', 80) }};

    // Minimum cell volume [m³] - prevents collapsed cells
    minVol              {{ config.mesh.SNAPPY_SETTINGS.get('minVol', 1e-13) }};

    // Minimum tet quality for tet decomposition
    minTetQuality       {{ config.mesh.SNAPPY_SETTINGS.get('minTetQuality', 1e-15) }};

    // Minimum face area [m²] - set to -1 to disable
    minArea             {{ config.mesh.SNAPPY_SETTINGS.get('minArea', -1) }};

    // Minimum face twist - important for polyhedral cells
    // Higher values (0.02) ensure better gradient interpolation
    minTwist            {{ config.mesh.SNAPPY_SETTINGS.get('minTwist', 0.02) }};

    // Minimum cell determinant (0-1)
    // Measures cell deformation; >0.001 required, >0.01 for accuracy
    minDeterminant      {{ config.mesh.SNAPPY_SETTINGS.get('minDeterminant', 0.001) }};

    // Minimum face interpolation weight (0-0.5)
    // >0.05 ensures accurate gradient interpolation at faces
    minFaceWeight       {{ config.mesh.SNAPPY_SETTINGS.get('minFaceWeight', 0.05) }};

    // Minimum volume ratio between adjacent cells
    // >0.01 ensures smooth cell size transitions
    minVolRatio         {{ config.mesh.SNAPPY_SETTINGS.get('minVolRatio', 0.01) }};

    // Minimum triangle twist - set to -1 to disable
    minTriangleTwist    {{ config.mesh.SNAPPY_SETTINGS.get('minTriangleTwist', -1) }};

    // Relaxation for snap phase
    nSmoothScale        {{ config.mesh.SNAPPY_SETTINGS.get('nSmoothScale', 4) }};
    errorReduction      {{ config.mesh.SNAPPY_SETTINGS.get('errorReduction', 0.75) }};

    // Relaxed constraints for layer addition phase
    // Allows slightly worse quality during layer insertion to improve coverage
    relaxed
    {
        maxNonOrtho         {{ config.mesh.SNAPPY_SETTINGS.get('relaxed_maxNonOrtho', 75) }};
        maxBoundarySkewness {{ config.mesh.SNAPPY_SETTINGS.get('relaxed_maxBoundarySkewness', 25) }};
        maxInternalSkewness {{ config.mesh.SNAPPY_SETTINGS.get('relaxed_maxInternalSkewness', 4) }};
    }
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