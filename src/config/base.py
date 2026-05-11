# config/base.py
"""
OpenFOAM 12 specific configuration.
All version compatibility removed for simplicity.
"""

import os

config = {
    # OpenFOAM 12 configuration
    "openfoam": {
        "version": "12",
        "major_version": 12,
        # HPC override: $OPENFOAM_BASHRC or $foamDotFile (CSF3 OF module).
        "env_path": os.environ.get(
            "OPENFOAM_BASHRC",
            os.environ.get("foamDotFile", "/opt/openfoam12/etc/bashrc"),
        ),
        "foundation": True,
        "solver_names": {"incompressible": "foamRun", "windkessel": "foamRun"},
        "windkessel": {
            "repository": "https://github.com/JieWangnk/OpenFOAM-WK",
            "boundary_condition": "modularWKPressure",
            "solver_name": "foamRun",
            "solver_module": "incompressibleFluid",
            "supported": True,
            "compilation_required": True,
        },
    },
    # Numerical schemes optimized for OpenFOAM 12
    "numerical": {
        "default_solver": "GAMG",
        "pressure_solver": "GAMG",
        "velocity_solver": "smoothSolver",
        "time_scheme": "backward",
        "divergence_scheme": "bounded Gauss limitedLinearV 1",
        "gradient_scheme": "cellLimited Gauss linear 0.5",
        "laplacian_scheme": "Gauss linear corrected",
    },
    # Physics defaults
    "physics": {
        "default_turbulence": "laminar",
        "default_viscosity": 0.004,  # Pa·s (blood)
        "default_density": 1060,  # kg/m³ (blood)
        "default_temperature": 310,  # K (body temperature)
        "default_prandtl": 0.7,
    },
    # ==========================================================================
    # MESH DEFAULTS
    # Evidence: 114-case HPC study on BPM120/PAT002/VOL04 (April 2026)
    # Ref: doc.cfd.direct/openfoam/user-guide-v13/snappyhexmesh
    # ==========================================================================
    "mesh": {
        "SNAPPY_SETTINGS": {
            # --- Strategy ---
            "mesh_strategy": "adaptive_span",  # adaptive_span | legacy_surface
            "default_cells_across_span": 12,  # fallback when no explicit resolution
            # --- Castellated mesh controls ---
            "maxLocalCells": 10000000,
            "maxGlobalCells": 20000000,
            "minRefinementCells": 10,
            "maxLoadUnbalance": 0.10,
            "nCellsBetweenLevels": 3,
            # --- Surface refinement ---
            # [2,2] when layers enabled (evidence: [0,1] gives 0% layer coverage)
            # [0,1] when layers off (sufficient for geometry capture)
            "surfaceRefinementLevels": [2, 2],
            # --- Feature detection ---
            "includedAngle": 170,  # edge detection threshold
            "resolveFeatureAngle": 30,  # sharp feature refinement
            # --- Main controls ---
            "castellatedMesh": True,
            "snap": True,
            "addLayers": True,
            # --- Snap controls ---
            "nSmoothPatch": 5,
            "nSmoothInternal": 5,
            "snapTolerance": 2.0,
            "nSolveIter": 100,
            "nRelaxIter": 10,
            "nFeatureSnapIter": 10,
            "implicitFeatureSnap": False,
            "explicitFeatureSnap": True,
            "multiRegionFeatureSnap": False,
            # --- Layer controls ---
            # Evidence: 2 layers gives best coverage/quality tradeoff
            #   PAT002: 99.7% coverage with 2 layers (checkMesh OK)
            #   VOL04:  28.8% coverage with 2 layers (checkMesh OK)
            #   3 layers: 47% / 23% — lower coverage, higher ortho
            #   1 layer:  99.9% / 45.7% — higher coverage but ortho marginal
            "relativeSizes": True,
            "addLayer": 5,  # nSurfaceLayers
            "expansionRatio": 1.2,
            "finalLayerThickness": 0.3,
            "minThickness": 0.01,
            "featureAngle": 190,  # >180 forces layers at sharp junctions
            "slipFeatureAngle": 30,
            "layerTerminationAngle": -180,
            # --- Layer quality (optimised for vascular coverage) ---
            # Strategy C: featureAngle 190 + unlocked ratios + moderate smoothing
            # Evidence: 48.6% coverage on BPM120 coarctation with 5 layers at
            # finalLayerThickness=0.5 (vs 8% with OF defaults). See
            # cases_input/BPM120/layer_test/ for reproducer configs.
            "nGrow": 0,  # don't delay near features (each face independent)
            "nBufferCellsNoExtrude": 0,
            "addLayers_nRelaxIter": 5,
            "nSmoothNormals": 5,  # moderate internal smoothing
            "nSmoothSurfaceNormals": 10,  # 10 = sweet spot (1 too rough, 50 washes out)
            "nSmoothThickness": 0,  # disabled — lets each face adapt thickness
            "nSmoothDisplacement": 5,
            "maxFaceThicknessRatio": 1.0,  # unlocked (0.5 rejects half the faces)
            "maxThicknessToMedialRatio": 1.0,  # unlocked (0.3 stops layers in narrow regions)
            "minMedianAxisAngle": 30,  # allows layers in tighter angles (was 90)
            "nLayerIter": 50,
            "nRelaxedIter": 0,  # relaxed from start
            # --- Mesh quality controls (strict base) ---
            "maxNonOrtho": 65,
            "maxBoundarySkewness": 20,
            "maxInternalSkewness": 4,
            "maxConcave": 80,
            "minVol": 1e-18,
            "minTetQuality": 1e-30,
            "minArea": 1e-20,
            "minTwist": 0.01,
            "minDeterminant": 0.01,
            "minFaceWeight": 0.02,
            "minVolRatio": 0.01,
            "minTriangleTwist": -1,
            "nSmoothScale": 6,
            "errorReduction": 0.75,
            # --- Relaxed quality (used from nRelaxedIter=0, layer insertion only) ---
            # Evidence: moderate relaxation (70/100/8) same as strict
            # Stronger relaxation needed for any coverage improvement
            "relaxed_maxNonOrtho": 75,
            "relaxed_maxBoundarySkewness": 200,
            "relaxed_maxInternalSkewness": 12,
            "relaxed_minDeterminant": 0.001,
            "relaxed_minVol": 1e-20,
        }
    },
    # Simulation control
    "simulation": {
        "default_end_time": 5.0,  # cardiac cycles
        "default_time_step": 0.001,  # seconds
        "default_write_interval": 0.1,
        "default_max_co": 1.0,
        "default_max_delta_t": 0.01,
    },
    # Paths
    "paths": {"templates": "src/templates", "windkessel_lib": "windkessel_of12", "logs": "logs", "results": "results"},
}
