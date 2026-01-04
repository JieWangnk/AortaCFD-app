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

            # Surface refinement
            "surfaceRefinementLevels": [1, 2],  # [min, max] - conservative for cardiovascular

            # Feature edge detection (for surfaceFeatures command)
            # Features = edges where face angle < includedAngle
            # 150° = detect edges with angle > 30° (conservative for smooth vessel walls)
            "includedAngle": 150,

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

            # Surface smoothing
            "nSmoothPatch": 3,              # OpenFOAM default: 3 (pre-snap surface smoothing)
            "nSmoothInternal": 3,           # Internal smoothing to reduce non-orthogonality

            # Snap attraction
            "snapTolerance": 1.0,           # Proven: 1.0 works better than 2.0 for cardiovascular

            # Mesh displacement iterations
            "nSolveIter": 10,               # Proven: 10 sufficient for cardiovascular (not 30)

            # Relaxation iterations
            "nRelaxIter": 5,                # OpenFOAM default: 5 (adaptation attempts)

            # Feature edge snapping
            "nFeatureSnapIter": 5,          # Proven: 5 sufficient for cardiovascular (not 10)

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

            # Layer count and growth
            "addLayer": 7,                  # nSurfaceLayers: 7-10 for y+ ≈ 1 in cardiovascular
            "expansionRatio": 1.15,         # OpenFOAM typical: 1.1, slightly higher for gradual growth
            "finalLayerThickness": 0.3,     # Last layer as fraction of cell size (0.3-0.5)
            "minThickness": 0.1,            # Minimum before termination (OpenFOAM default: 0.1)

            # Feature angle controls (critical for curved surfaces)
            "featureAngle": 170,            # Proven: 170 for good layer coverage at bifurcations
            "slipFeatureAngle": 30,         # Permit sliding on patches without layers
            "layerTerminationAngle": -180,  # -180 = attempt extrusion everywhere

            # Growth controls
            "nGrow": 0,                     # Delay extrusion near features (0 = immediate)
            "nBufferCellsNoExtrude": 0,     # Gradual layer termination regions
            "addLayers_nRelaxIter": 5,      # Layer addition relaxation iterations

            # Smoothing iterations (DOE study findings)
            "nSmoothNormals": 3,            # Interior mesh movement direction smoothing
            "nSmoothSurfaceNormals": 20,    # DOE: insensitive (10-50 all work)
            "nSmoothThickness": 10,         # DOE: +0.367 effect - LOWER is better!
            "nSmoothDisplacement": 10,      # Post-medial axis smoothing

            # Thickness ratio controls (DOE findings)
            "maxFaceThicknessRatio": 0.5,   # DOE: +0.286 effect - LOWER is better!
            "maxThicknessToMedialRatio": 0.3,  # OpenFOAM typical: 0.3 (protect narrow cavities)
            "minMedianAxisAngle": 90,       # OpenFOAM typical: 90°

            # Iteration limits
            "nLayerIter": 50,               # OpenFOAM default: 50 (max layer addition iterations)
            "nRelaxedIter": 20,             # Iterations before switching to relaxed quality

            # ==========================================================================
            # MESH QUALITY CONTROLS
            # Ref: guide-meshing-snappyhexmesh-meshquality.html
            # ==========================================================================

            # Non-orthogonality (angle between cell center vector and face normal)
            # < 65°: no correctors needed
            # 65-75°: 1 corrector
            # > 85°: likely divergence
            "maxNonOrtho": 65,              # OpenFOAM default: 65°

            # Skewness (critical for numerical accuracy)
            # Note: OpenFOAM default of 4 is too strict for cardiovascular geometries
            # Coarctations, bifurcations, and high-curvature regions often produce
            # isolated cells with skewness 4-8. Values up to 8 are acceptable for
            # pimpleFoam/foamRun with proper under-relaxation.
            "maxBoundarySkewness": 20,      # OpenFOAM default: 20
            "maxInternalSkewness": 8,       # OpenFOAM default: 4, relaxed for cardiovascular

            # Cell shape quality
            "maxConcave": 80,               # OpenFOAM default: 80°
            "minVol": 1e-13,                # OpenFOAM default: 1e-13 m³
            "minTetQuality": 1e-15,         # OpenFOAM default: 1e-15
            "minArea": -1,                  # -1 = disabled (OpenFOAM default)
            "minTwist": 0.02,               # OpenFOAM default: 0.02
            "minDeterminant": 0.001,        # OpenFOAM default: 0.001
            "minFaceWeight": 0.05,          # OpenFOAM default: 0.05
            "minVolRatio": 0.01,            # OpenFOAM default: 0.01
            "minTriangleTwist": -1,         # -1 = disabled

            # Smoothing and error reduction
            "nSmoothScale": 4,              # OpenFOAM default: 4
            "errorReduction": 0.75,         # OpenFOAM default: 0.75

            # Relaxed quality controls (used during layer addition after nRelaxedIter)
            # More permissive to allow layers to be added, final mesh checked against base
            "relaxed_maxNonOrtho": 75,
            "relaxed_maxBoundarySkewness": 25,
            "relaxed_maxInternalSkewness": 10   # Relaxed for layer addition phase
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