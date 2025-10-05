"""Solver recipe fragment definitions (moved).

Original module path: config.profiles.solver_recipe_fragments
"""

from __future__ import annotations

from typing import Any, Dict

FRAGMENT_META_KEY = "__profile_fragment__"

# --- Imported from previous solver_recipe_fragments.py (verbatim) ---

SOLVER_RECIPE_ROBUST: Dict[str, Any] = {
    "schemes": {
        "ddtSchemes": {"default": "Euler"},
        "gradSchemes": {"default": "cellLimited Gauss linear 1", "grad(U)": "cellLimited Gauss linear 1"},
        "divSchemes": {
            "default": "none",
            "div(phi,U)": "Gauss upwind",
            "div(phi,k)": "Gauss upwind",
            "div(phi,omega)": "Gauss upwind",
            "div((nuEff*dev2(T(grad(U)))))": "Gauss linear",
        },
        "laplacianSchemes": {"default": "Gauss linear limited 0.5"},
        "interpolationSchemes": {"default": "linear"},
        "snGradSchemes": {"default": "limited 0.5"},
    },
    "fvSolution": {
        "SIMPLE": {"nNonOrthogonalCorrectors": 2},
        "solvers": {
            "p": {
                "solver": "GAMG",
                "tolerance": 1e-6,
                "relTol": 1e-2,
                "smoother": "GaussSeidel",
                "nPreSweeps": 0,
                "nPostSweeps": 2,
                "nFinestSweeps": 2,
                "cacheAgglomeration": "true",
                "nCellsInCoarsestLevel": 50,
                "agglomerator": "faceAreaPair",
                "mergeLevels": 1,
            },
            "U": {"solver": "smoothSolver", "smoother": "symGaussSeidel", "tolerance": 1e-5, "relTol": 1e-1},
        },
        "relaxationFactors": {"fields": {"p": 0.3}, "equations": {"U": 0.7, "k": 0.7, "omega": 0.7}},
    },
    "time_stepping": {"maxCo": 0.5},
    FRAGMENT_META_KEY: {
        "axis": "solver_recipe",
        "level": "robust",
        "targets": {
            "loop": "SIMPLE",
            "max_co": 0.5,
            "notes": "First-order Euler + upwind, strong URF for difficult start-ups.",
        },
    },
}

SOLVER_RECIPE_BALANCED: Dict[str, Any] = {
    "schemes": {
        "ddtSchemes": {"default": "CrankNicolson 0.9"},
        "gradSchemes": {"default": "cellLimited Gauss linear 0.5", "grad(U)": "cellLimited Gauss linear 1"},
        "divSchemes": {
            "default": "none",
            "div(phi,U)": "Gauss linearUpwindV grad(U)",
            "div(phi,k)": "Gauss linearUpwind default",
            "div(phi,omega)": "Gauss linearUpwind default",
            "div((nuEff*dev2(T(grad(U)))))": "Gauss linear",
        },
        "laplacianSchemes": {"default": "Gauss linear limited 1"},
        "interpolationSchemes": {"default": "linear"},
        "snGradSchemes": {"default": "limited 1"},
    },
    "fvSolution": {
        "PIMPLE": {
            "momentumPredictor": "yes",
            "nOuterCorrectors": 1,
            "nCorrectors": 2,
            "nNonOrthogonalCorrectors": 1,
        },
        "solvers": {
            "p": {
                "solver": "GAMG",
                "tolerance": 1e-7,
                "relTol": 5e-3,
                "smoother": "GaussSeidel",
                "nPreSweeps": 0,
                "nPostSweeps": 2,
                "nFinestSweeps": 2,
                "cacheAgglomeration": "true",
                "nCellsInCoarsestLevel": 20,
                "agglomerator": "faceAreaPair",
                "mergeLevels": 1,
            },
            "U": {"solver": "smoothSolver", "smoother": "symGaussSeidel", "tolerance": 1e-7, "relTol": 5e-2},
        },
        "relaxationFactors": {"fields": {"p": 0.3}, "equations": {"U": 0.7, "k": 0.7, "omega": 0.7}},
    },
    "time_stepping": {"maxCo": 1.0},
    FRAGMENT_META_KEY: {
        "axis": "solver_recipe",
        "level": "balanced",
        "targets": {
            "loop": "PISO/PIMPLE (nOuter=1)",
            "max_co": 1.0,
            "notes": "Second-order bounded schemes with momentum predictor enabled.",
        },
    },
}

SOLVER_RECIPE_AGGRESSIVE: Dict[str, Any] = {
    "schemes": {
        "ddtSchemes": {"default": "CrankNicolson 0.7"},
        "gradSchemes": {"default": "cellLimited Gauss linear 1"},
        "divSchemes": {
            "default": "none",
            "div(phi,U)": "Gauss linear",
            "div(phi,k)": "Gauss limitedLinear 1",
            "div(phi,omega)": "Gauss limitedLinear 1",
            "div((nuEff*dev2(T(grad(U)))))": "Gauss linear",
        },
        "laplacianSchemes": {"default": "Gauss linear limited 1"},
        "interpolationSchemes": {"default": "linear"},
        "snGradSchemes": {"default": "limited 1"},
    },
    "fvSolution": {
        "PIMPLE": {
            "momentumPredictor": "yes",
            "nOuterCorrectors": 2,
            "nCorrectors": 3,
            "nNonOrthogonalCorrectors": 2,
        },
        "solvers": {
            "p": {
                "solver": "GAMG",
                "tolerance": 1e-8,
                "relTol": 1e-3,
                "smoother": "GaussSeidel",
                "nPreSweeps": 0,
                "nPostSweeps": 2,
                "nFinestSweeps": 2,
                "cacheAgglomeration": "true",
                "nCellsInCoarsestLevel": 10,
                "agglomerator": "faceAreaPair",
                "mergeLevels": 1,
            },
            "U": {"solver": "smoothSolver", "smoother": "symGaussSeidel", "tolerance": 1e-8, "relTol": 1e-2},
        },
        "relaxationFactors": {
            "fields": {"p.*": 0.7},
            "equations": {"p.*": 0.7, "U.*": 0.7, "k.*": 0.7, "omega.*": 0.7},
        },
    },
    "time_stepping": {"maxCo": 1.5},
    FRAGMENT_META_KEY: {
        "axis": "solver_recipe",
        "level": "aggressive",
        "targets": {
            "loop": "PIMPLE (outer=2)",
            "max_co": 1.5,
            "notes": "High-order schemes with additional outer loops for large CFL runs.",
        },
    },
}

SOLVER_RECIPE_FRAGMENTS: Dict[str, Dict[str, Any]] = {
    "robust": SOLVER_RECIPE_ROBUST,
    "balanced": SOLVER_RECIPE_BALANCED,
    "aggressive": SOLVER_RECIPE_AGGRESSIVE,
}

__all__ = [
    "FRAGMENT_META_KEY",
    "SOLVER_RECIPE_FRAGMENTS",
]
