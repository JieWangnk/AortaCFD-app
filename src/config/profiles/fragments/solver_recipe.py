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
            "div(phi,U)": "Gauss linearUpwindV grad(U)",  # Bounded 2nd-order for better accuracy than pure upwind
            "div(phi,k)": "Gauss upwind",
            "div(phi,omega)": "Gauss upwind",
            "div(phi,epsilon)": "Gauss upwind",
            "div((nuEff*dev2(T(grad(U)))))": "Gauss linear",
        },
        "laplacianSchemes": {"default": "Gauss linear limited 0.5"},
        "interpolationSchemes": {"default": "linear"},
        "snGradSchemes": {"default": "limited 0.5"},
    },
    "fvSolution": {
        "SIMPLE": {"nNonOrthogonalCorrectors": 2},
        "PIMPLE": {
            "momentumPredictor": "yes",
            "nOuterCorrectors": 3,
            "nCorrectors": 3,
            "nNonOrthogonalCorrectors": 2,
            "pRefCell": 0,
            "pRefValue": 0,
        },
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
            "k": {"solver": "smoothSolver", "smoother": "symGaussSeidel", "tolerance": 1e-5, "relTol": 1e-1},
            "omega": {"solver": "smoothSolver", "smoother": "symGaussSeidel", "tolerance": 1e-5, "relTol": 1e-1},
            "epsilon": {"solver": "smoothSolver", "smoother": "symGaussSeidel", "tolerance": 1e-5, "relTol": 1e-1},
        },
        "relaxationFactors": {
            "fields": {"p": 0.2},
            "equations": {"U": 0.5, "k": 0.5, "omega": 0.5, "epsilon": 0.5}
        },
    },
    "time_stepping": {"maxCo": 0.5},
    FRAGMENT_META_KEY: {
        "axis": "solver_recipe",
        "level": "robust",
        "targets": {
            "loop": "PIMPLE (outer=3, correctors=3)",
            "max_co": 0.5,
            "notes": "Strong under-relaxation and multiple correctors for RANS stability with complex BCs (Windkessel, etc).",
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
            "div(phi,epsilon)": "Gauss linearUpwind default",
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
            "k": {"solver": "smoothSolver", "smoother": "symGaussSeidel", "tolerance": 1e-7, "relTol": 5e-2},
            "omega": {"solver": "smoothSolver", "smoother": "symGaussSeidel", "tolerance": 1e-7, "relTol": 5e-2},
            "epsilon": {"solver": "smoothSolver", "smoother": "symGaussSeidel", "tolerance": 1e-7, "relTol": 5e-2},
        },
        "relaxationFactors": {"fields": {"p": 0.3}, "equations": {"U": 0.6, "k": 0.6, "omega": 0.6, "epsilon": 0.6}},
    },
    "time_stepping": {"maxCo": 0.8},
    FRAGMENT_META_KEY: {
        "axis": "solver_recipe",
        "level": "balanced",
        "targets": {
            "loop": "PIMPLE (outer=2, correctors=3)",
            "max_co": 0.8,
            "notes": "Accuracy-focused: 2nd-order time/space discretization with 2 outer correctors for good pressure-velocity coupling.",
        },
    },
}

SOLVER_RECIPE_AGGRESSIVE: Dict[str, Any] = {
    "schemes": {
        "ddtSchemes": {"default": "CrankNicolson 0.7"},
        "gradSchemes": {"default": "Gauss linear", "grad(U)": "Gauss linear"},
        "divSchemes": {
            "default": "none",
            "div(phi,U)": "Gauss linear",
            "div(phi,k)": "Gauss limitedLinear 1",
            "div(phi,omega)": "Gauss limitedLinear 1",
            "div(phi,epsilon)": "Gauss limitedLinear 1",
            "div((nuEff*dev2(T(grad(U)))))": "Gauss linear",
        },
        "laplacianSchemes": {"default": "Gauss linear corrected"},
        "interpolationSchemes": {"default": "linear"},
        "snGradSchemes": {"default": "corrected"},
    },
    "fvSolution": {
        "PIMPLE": {
            "momentumPredictor": "yes",
            "nOuterCorrectors": 3,
            "nCorrectors": 4,
            "nNonOrthogonalCorrectors": 3,
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
            "k": {"solver": "smoothSolver", "smoother": "symGaussSeidel", "tolerance": 1e-8, "relTol": 1e-2},
            "omega": {"solver": "smoothSolver", "smoother": "symGaussSeidel", "tolerance": 1e-8, "relTol": 1e-2},
            "epsilon": {"solver": "smoothSolver", "smoother": "symGaussSeidel", "tolerance": 1e-8, "relTol": 1e-2},
        },
        "relaxationFactors": {
            "fields": {"p": 0.4},
            "equations": {"U": 0.7, "k": 0.7, "omega": 0.7, "epsilon": 0.7},
        },
    },
    "time_stepping": {"maxCo": 1.0},
    FRAGMENT_META_KEY: {
        "axis": "solver_recipe",
        "level": "aggressive",
        "targets": {
            "loop": "PIMPLE (outer=3, correctors=4)",
            "max_co": 1.0,
            "notes": "Maximum accuracy: Pure 2nd-order central schemes, tight tolerances, 3 outer correctors for publication-quality results.",
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
