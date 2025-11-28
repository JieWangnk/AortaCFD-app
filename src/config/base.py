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
    
    # Mesh defaults - Robust settings optimized for cardiovascular geometries
    # Philosophy: QUALITY OVER DETAIL - prioritize mesh robustness for complex aortic geometries
    # These defaults handle: coarctations, stenoses, aneurysms, bifurcations, high curvature
    # Updated: 2025-10-28 - Conservative defaults to avoid skewness and boundary layer collapse
    "mesh": {
        "SNAPPY_SETTINGS": {
            # ========== SURFACE REFINEMENT (CONSERVATIVE) ==========
            # Conservative: [1,2] provides smooth transitions without excessive skewness
            # Only use [2,3] for simple geometries or after verifying [1,2] works
            "surfaceRefinementLevels": [1, 2],

            # ========== FEATURE RESOLUTION (CONSERVATIVE) ==========
            # resolveFeatureAngle: 60° is ROBUST for aortas (30° was too aggressive)
            # Higher angle = fewer features captured = smoother mesh
            # 60° is the sweet spot for cardiovascular geometries
            "resolveFeatureAngle": 60,

            # Feature level: AUTO-CALCULATED in template to match max(surfaceRefinementLevels)
            # This prevents over-refinement at edges

            # ========== QUALITY CONTROLS ==========
            "maxNonOrtho": 65,
            "maxBoundarySkewness": 20,
            "maxInternalSkewness": 4,
            "maxConcave": 80,
            "minVol": 1e-18,
            "minTetQuality": 1e-20,
            "minArea": -1,
            "minTwist": 0.01,
            "minDeterminant": 0.001,
            "minFaceWeight": 0.02,
            "minVolRatio": 0.01,
            "minTriangleTwist": -1,

            # ========== TRANSITION SMOOTHNESS ==========
            "nCellsBetweenLevels": 2,       # Smoother transitions (was 3)

            # ========== SNAPPING & QUALITY ITERATIONS ==========
            "snapTolerance": 2.0,
            "nSmoothPatch": 5,
            "nSmoothScale": 4,
            "nSolveIter": 250,
            "nRelaxIter": 10,
            "nFeatureSnapIter": 15,
            "nSmoothInternal": 3,
            "nSmoothDisplacement": 90,
            "errorReduction": 0.75,

            # ========== RELAXED QUALITY CONTROLS ==========
            "relaxed_maxNonOrtho": 75,  # More gradual transition between refinement levels

            # ========== CELL COUNTS AND LIMITS ==========
            "maxLocalCells": 10000000,
            "maxGlobalCells": 20000000,
            "minRefinementCells": 10,

            # ========== CASTELLATED MESH CONTROLS ==========
            "castellatedMesh": True,
            "snap": True,
            "addLayers": True,

            # ========== BOUNDARY LAYER SETTINGS (TRADITIONAL OPENFOAM STYLE) ==========
            # Uses relativeSizes=true with finalLayerThickness as fraction of local cell size
            # This is the standard OpenFOAM approach - simple and predictable
            # Y+ based sizing is OPTIONAL (only if mesh.boundary_layers.target_yplus is set)
            "addLayer": 5,                  # nSurfaceLayers: typical for cardiovascular
            "expansionRatio": 1.2,          # Growth ratio between layers (1.15-1.25 typical)
            "finalLayerThickness": 0.3,     # Outermost layer as fraction of cell size
            "minThickness": 0.1,            # Minimum layer thickness (allows graceful collapse)
            "relativeSizes": True,          # Use relative sizing (fraction of cell size)

            # ========== LAYER ADDITION CONTROLS (MAXIMUM CONSERVATISM) ==========
            # CRITICAL: nSmoothSurfaceNormals is THE KEY to layer success
            # Philosophy: Let layers fail gracefully rather than create bad cells
            # FINAL PUSH: Skip even more features, maximum smoothing
            "nGrow": 0,
            "featureAngle": 160,            # ⭐⭐⭐ Was 150° → 160° (FINAL: skip MOST features)
            "slipFeatureAngle": 30,         # Allow layer slip at boundaries
            "nSmoothSurfaceNormals": 15,    # ⭐⭐⭐ Was 10 → 15 (FINAL: maximum smoothing)
            "nSmoothThickness": 10,         # Smooth thickness field
            "maxFaceThicknessRatio": 0.25,  # ⭐⭐⭐ Was 0.3 → 0.25 (FINAL: thinnest safe ratio)
            "maxThicknessToMedialRatio": 0.3,
            "minMedianAxisAngle": 90,
            "nBufferCellsNoExtrude": 0,
            "nLayerIter": 30,               # ⭐ Was 50 → 30 (less aggressive pushing)
            "nRelaxedIter": 30,             # ⭐⭐⭐ Was 20 → 30 (FINAL: maximum relaxation)
            "nSmoothNormals": 3             # ⭐ Additional normal smoothing
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