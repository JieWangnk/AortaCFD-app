"""Spatial resolution fragment definitions (moved).

Original module path: config.profiles.resolution_fragments
"""

from __future__ import annotations

from typing import Any, Dict

FRAGMENT_META_KEY = "__profile_fragment__"

# --- Imported from previous resolution_fragments.py (verbatim) ---

RESOLUTION_COARSE: Dict[str, Any] = {
    "mesh": {
        "mesh_resolution": {
            "target_cell_size_mm": 1.8,
            "cells_per_diameter": {
                "inlet": 8,
                "branch": 6,
            },
            "refinement_targets_mm": {
                "background": 0.003,
                "surface": 0.002,
                "feature": 0.0015,
            },
        },
        "SNAPPY_SETTINGS": {
            "parallel": False,
            "nProcessors": 1,
            "maxLocalCells": 1_800_000,
            "maxGlobalCells": 2_000_000,
            "minRefinementCells": 0,
            "nCellsBetweenLevels": 1,
            "featureLevel": 0,
            "surfaceRefinementLevels": [1, 1],
            "resolveFeatureAngle": 60,
            "nSmoothPatch": 3,
            "tolerance": 1.0,
            "nSolveIter": 300,
            "nRelaxIter": 5,
            "nFeatureSnapIter": 10,
            "explicitFeatureSnap": True,
            "multiRegionFeatureSnap": True,
            "addLayer": 0,
            "useOpenFOAMDefaults": True,
            "relaxed": {
                "maxNonOrtho": 75,
            },
        },
        "refinement_levels": {
            "background": 0.003,
            "surface": 0.0015,
            "feature": 0.001,
        },
    },
    FRAGMENT_META_KEY: {
        "axis": "spatial_resolution",
        "level": "coarse",
        "targets": {
            "estimated_cells": 1_500_000,
            "cell_size_mm": 1.8,
            "min_patch_cells": {
                "inlet": 8,
                "branch": 6,
            },
            "delta_y_plus": 20,
        },
    },
}

RESOLUTION_MEDIUM: Dict[str, Any] = {
    "mesh": {
        "mesh_resolution": {
            "target_cell_size_mm": 1.0,
            "cells_per_diameter": {
                "inlet": 15,
                "branch": 12,
            },
            "refinement_targets_mm": {
                "background": 0.0015,
                "surface": 0.001,
                "feature": 0.0007,
            },
        },
        "SNAPPY_SETTINGS": {
            "parallel": False,
            "nProcessors": 1,
            "maxLocalCells": 3_800_000,
            "maxGlobalCells": 4_000_000,
            "minRefinementCells": 0,
            "nCellsBetweenLevels": 1,
            "featureLevel": 1,
            "surfaceRefinementLevels": [2, 2],
            "resolveFeatureAngle": 30,
            "nSmoothPatch": 4,
            "tolerance": 0.7,
            "nSolveIter": 600,
            "nRelaxIter": 8,
            "nFeatureSnapIter": 15,
            "explicitFeatureSnap": True,
            "multiRegionFeatureSnap": True,
            "addLayer": 1,
            "layer_settings": {
                "nSurfaceLayers": 2,
                "expansionRatio": 1.2,
                "finalLayerThickness": 0.5,
            },
            "useOpenFOAMDefaults": True,
            "relaxed": {
                "maxNonOrtho": 65,
            },
        },
        "refinement_levels": {
            "background": 0.0015,
            "surface": 0.001,
            "feature": 0.0007,
        },
    },
    FRAGMENT_META_KEY: {
        "axis": "spatial_resolution",
        "level": "medium",
        "targets": {
            "estimated_cells": 3_500_000,
            "cell_size_mm": 1.0,
            "min_patch_cells": {
                "inlet": 15,
                "branch": 12,
            },
            "delta_y_plus": 7,
        },
    },
}

RESOLUTION_FINE: Dict[str, Any] = {
    "mesh": {
        "mesh_resolution": {
            "target_cell_size_mm": 0.6,
            "cells_per_diameter": {
                "inlet": 22,
                "branch": 18,
            },
            "refinement_targets_mm": {
                "background": 0.001,
                "surface": 0.0007,
                "feature": 0.0005,
            },
        },
        "SNAPPY_SETTINGS": {
            "parallel": False,
            "nProcessors": 1,
            "maxLocalCells": 7_200_000,
            "maxGlobalCells": 7_500_000,
            "minRefinementCells": 0,
            "nCellsBetweenLevels": 2,
            "featureLevel": 2,
            "surfaceRefinementLevels": [2, 3],
            "resolveFeatureAngle": 30,
            "nSmoothPatch": 5,
            "tolerance": 0.5,
            "nSolveIter": 800,
            "nRelaxIter": 10,
            "nFeatureSnapIter": 20,
            "explicitFeatureSnap": True,
            "multiRegionFeatureSnap": True,
            "addLayer": 1,
            "layer_settings": {
                "nSurfaceLayers": 3,
                "expansionRatio": 1.1,
                "finalLayerThickness": 0.3,
            },
            "useOpenFOAMDefaults": True,
            "relaxed": {
                "maxNonOrtho": 55,
            },
        },
        "refinement_levels": {
            "background": 0.001,
            "surface": 0.0007,
            "feature": 0.0005,
        },
    },
    FRAGMENT_META_KEY: {
        "axis": "spatial_resolution",
        "level": "fine",
        "targets": {
            "estimated_cells": 7_000_000,
            "cell_size_mm": 0.6,
            "min_patch_cells": {
                "inlet": 22,
                "branch": 18,
            },
            "delta_y_plus": 2,
        },
    },
}

RESOLUTION_FRAGMENTS: Dict[str, Dict[str, Any]] = {
    "coarse": RESOLUTION_COARSE,
    "medium": RESOLUTION_MEDIUM,
    "fine": RESOLUTION_FINE,
}

__all__ = [
    "FRAGMENT_META_KEY",
    "RESOLUTION_FRAGMENTS",
]
