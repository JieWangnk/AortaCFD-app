# config/base.py
"""
OpenFOAM 12 specific configuration.
All version compatibility removed for simplicity.
"""

config = {
    # OpenFOAM 12 configuration
    "openfoam": {
        "version": "12",
        "major_version": 12,
        "env_path": "/opt/openfoam12/etc/bashrc",
        "foundation": True,
        "solver_names": {
            "incompressible": "foamRun",
            "windkessel": "foamRun"
        },
        "windkessel": {
            "repository": "https://github.com/JieWangnk/OpenFOAM-WK",
            "boundary_condition": "modularWKPressure",
            "solver_name": "foamRun",
            "solver_module": "incompressibleFluid",
            "supported": True,
            "compilation_required": True
        }
    },
    
    # Numerical schemes optimized for OpenFOAM 12
    "numerical": {
        "default_solver": "GAMG",
        "pressure_solver": "GAMG",
        "velocity_solver": "smoothSolver",
        "time_scheme": "backward",
        "divergence_scheme": "bounded Gauss limitedLinearV 1",
        "gradient_scheme": "cellLimited Gauss linear 0.5",
        "laplacian_scheme": "Gauss linear corrected"
    },
    
    # Physics defaults
    "physics": {
        "default_turbulence": "laminar",
        "default_viscosity": 0.004,  # Pa·s (blood)
        "default_density": 1060,     # kg/m³ (blood)
        "default_temperature": 310,  # K (body temperature)
        "default_prandtl": 0.7
    },
    
    # Mesh defaults - OpenFOAM defaults optimized for high-curvature cardiovascular geometries
    # Based on: OpenFOAM documentation (openfoam.com/documentation/guides/latest)
    # Optimized for: coarctations, stenoses, aneurysms, bifurcations, high curvature vessels
    # Updated: 2025-12-17 - Aligned with OpenFOAM defaults + cardiovascular best practices
    "mesh": {
        # Mesh goal preset: maps clinical intent to meshing parameters
        # pressure_fast | routine_hemodynamics | wall_sensitive
        # Set to None/omit to use explicit settings instead
        # "goal": "routine_hemodynamics",

        "SNAPPY_SETTINGS": {
            # ==========================================================================
            # CASTELLATED MESH CONTROLS
            # Ref: guide-meshing-snappyhexmesh-castellation.html
            # ==========================================================================

            # Cell count limits
            "maxLocalCells": 10000000,      # Per-processor hint, triggers balancing when exceeded
            "maxGlobalCells": 20000000,     # Overall limit before removing unwanted regions
            "minRefinementCells": 10,       # Halts refinement when cells below this count
            "maxLoadUnbalance": 0.10,       # Relative cell difference tolerance between processors

            # Refinement transition
            "nCellsBetweenLevels": 3,       # OpenFOAM recommended: 3 (balances transitions)

            # Mesh strategy: 'adaptive_span' uses span-based refinement with coarse
            # blockMesh; 'legacy_surface' uses cpd-driven blockMesh + fixed surface levels
            "mesh_strategy": "adaptive_span",   # 'adaptive_span' | 'legacy_surface'
            "default_cells_across_span": 12,    # fallback target when adaptive_span + no explicit resolution

            # Surface refinement
            "surfaceRefinementLevels": [1, 2],  # [min, max] - conservative for cardiovascular

            # Feature edge detection (for surfaceFeatures command)
            # Features = edges where face angle < includedAngle
            # Higher value = more edges detected (captures gentle curves at patch junctions)
            # 170° = detect edges with angle > 10° (good for inlet-wall transitions)
            "includedAngle": 170,

            # Feature resolution in snappyHexMesh
            # Threshold angle between surface normals triggering higher refinement
            "resolveFeatureAngle": 30,      # Typical for cardiovascular (captures branches)

            # Main controls
            "castellatedMesh": True,
            "snap": True,
            "addLayers": True,

            # ==========================================================================
            # SNAP CONTROLS
            # Ref: guide-meshing-snappyhexmesh-snapping.html
            # ==========================================================================

            # Surface smoothing - increased for better quality and to prevent negative volume cells
            "nSmoothPatch": 5,              # Increased from 3 for better surface quality
            "nSmoothInternal": 5,           # Internal smoothing to reduce non-orthogonality

            # Snap attraction
            "snapTolerance": 2.0,           # Increased for better snapping on complex geometry

            # Mesh displacement iterations - increased to prevent negative volume cells
            "nSolveIter": 100,              # Increased from 10 for complex cardiovascular geometry

            # Relaxation iterations - increased for better quality
            "nRelaxIter": 10,               # Increased from 5 for better adaptation

            # Feature edge snapping - increased for complex geometry
            "nFeatureSnapIter": 10,         # Increased from 5 for better feature edge snapping

            # Feature snap modes
            "implicitFeatureSnap": False,   # Not recommended for complex geometry
            "explicitFeatureSnap": True,    # Use pre-extracted .eMesh files (recommended)
            "multiRegionFeatureSnap": False,

            # ==========================================================================
            # ADD LAYERS CONTROLS
            # Ref: guide-meshing-snappyhexmesh-layers.html
            # Critical for WSS accuracy in cardiovascular CFD
            # ==========================================================================

            # Layer sizing mode
            "relativeSizes": True,          # true = relative to cell size (recommended)

            # Layer count and growth - more conservative for quality
            "addLayer": 10,                 # nSurfaceLayers: 10 for y+ ≈ 1 in cardiovascular
            "expansionRatio": 1.1,          # Conservative growth ratio for better quality
            "finalLayerThickness": 0.4,     # Last layer as fraction of cell size
            "minThickness": 0.15,           # Minimum before termination

            # Feature angle controls (critical for curved surfaces)
            "featureAngle": 150,            # Conservative for better layer quality
            "slipFeatureAngle": 30,         # Permit sliding on patches without layers
            "layerTerminationAngle": -180,  # -180 = attempt extrusion everywhere

            # Growth controls
            "nGrow": 0,                     # Delay extrusion near features (0 = immediate)
            "nBufferCellsNoExtrude": 0,     # Gradual layer termination regions
            "addLayers_nRelaxIter": 10,     # Layer addition relaxation iterations - increased

            # Smoothing iterations - increased for better quality
            "nSmoothNormals": 5,            # Interior mesh movement direction smoothing
            "nSmoothSurfaceNormals": 30,    # Increased for curved cardiovascular surfaces
            "nSmoothThickness": 15,         # Increased for better layer quality
            "nSmoothDisplacement": 15,      # Post-medial axis smoothing - increased

            # Thickness ratio controls - tightened for quality
            "maxFaceThicknessRatio": 0.4,   # Tighter for better quality
            "maxThicknessToMedialRatio": 0.25,  # Tighter to prevent self-intersection
            "minMedianAxisAngle": 90,       # OpenFOAM typical: 90°

            # Iteration limits - increased for better quality
            "nLayerIter": 100,              # Increased from 50 for complex geometry
            "nRelaxedIter": 50,             # Increased for more iterations before relaxing

            # ==========================================================================
            # MESH QUALITY CONTROLS
            # Ref: guide-meshing-snappyhexmesh-meshquality.html
            # Tightened to prevent negative volume cells in complex cardiovascular geometry
            # ==========================================================================

            # Non-orthogonality (angle between cell center vector and face normal)
            # < 65°: no correctors needed
            # 65-75°: 1 corrector
            # > 85°: likely divergence
            "maxNonOrtho": 60,              # Tightened from 65° for better quality

            # Skewness (critical for numerical accuracy and LES)
            # Tightened for LES and to prevent negative volume cells
            "maxBoundarySkewness": 4,       # Tightened from 20 for WSS accuracy
            "maxInternalSkewness": 4,       # Tightened from 8 for LES compatibility

            # Cell shape quality - tightened to prevent negative volume cells
            "maxConcave": 80,               # OpenFOAM default: 80°
            "minVol": 1e-18,                # Tightened from 1e-13 to prevent negative volume
            "minTetQuality": 1e-30,         # Tighter tet quality
            "minArea": 1e-20,               # Positive minimum area (was -1 disabled)
            "minTwist": 0.01,               # Tightened from 0.02 for better quality
            "minDeterminant": 0.01,         # Tightened from 0.001 for cell quality
            "minFaceWeight": 0.02,          # Tightened from 0.05 for better face weighting
            "minVolRatio": 0.01,            # OpenFOAM default: 0.01
            "minTriangleTwist": -1,         # -1 = disabled

            # Smoothing and error reduction - increased iterations
            "nSmoothScale": 6,              # Increased from 4 for more smoothing
            "errorReduction": 0.75,         # OpenFOAM default: 0.75

            # Relaxed quality controls (used during layer addition after nRelaxedIter)
            # Still tighter than before to prevent quality issues
            "relaxed_maxNonOrtho": 70,
            "relaxed_maxBoundarySkewness": 10,
            "relaxed_maxInternalSkewness": 6,
            "relaxed_minDeterminant": 0.001,
            "relaxed_minVol": 1e-20
        }
    },
    
    # Simulation control
    "simulation": {
        "default_end_time": 5.0,     # cardiac cycles
        "default_time_step": 0.001,  # seconds
        "default_write_interval": 0.1,
        "default_max_co": 1.0,
        "default_max_delta_t": 0.01
    },
    
    # Paths
    "paths": {
        "templates": "src/templates",
        "windkessel_lib": "windkessel_of12",
        "logs": "logs",
        "results": "results"
    }
}