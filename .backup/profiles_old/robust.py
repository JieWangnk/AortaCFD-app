"""Conservative numeric profile - Maximum stability, first-order accuracy.

INTENDED USE
============
- Initial runs of new geometries
- Difficult cases with poor mesh quality (high skewness, non-orthogonality)
- Debugging divergence issues
- Coarse meshes where second-order schemes oscillate

CHARACTERISTICS
===============
Time Integration:    Euler (1st order implicit)
Convection:          Gauss upwind (1st order, bounded, highly stable)
Gradients:           Gauss linear (2nd order - gradients less sensitive)
Laplacian:           Gauss linear corrected (2nd order)
Solver:              PIMPLE with many correctors
Relaxation:          Heavy (U: 0.5, p: 0.2)
Residual tolerance:  1e-5 (tight for stability)
Max Courant:         0.5 (small time steps)

TRADE-OFFS
==========
✅ Pros:
   - Maximum stability (bounded, monotone schemes)
   - Converges on poor-quality meshes
   - Robust to difficult boundary conditions

❌ Cons:
   - Numerical diffusion from first-order schemes
   - Less accurate than second-order methods
   - Results are mesh-dependent (not second-order accurate)
   - Slower convergence due to heavy relaxation

LITERATURE BASIS
================
OpenFOAM User Guide (section 4.4.2):
  "First-order schemes such as upwind are more stable but introduce
   numerical diffusion, smearing sharp gradients."

Wolf Dynamics CFD Tips:
  "First order methods are bounded and stable but diffusive."

WHEN TO USE
===========
Use this profile when:
1. Standard profile diverges or oscillates
2. Initial testing of new geometry
3. Mesh quality warnings present (checkMesh shows high skewness)
4. Need guaranteed convergence for rough estimates

DO NOT USE for final results - numerical diffusion will affect accuracy.

VALIDATION REQUIREMENTS
=======================
If using this profile for published results:
- Document that first-order schemes were necessary for convergence
- Perform mesh refinement study to show results converge
- Explain physical justification (if any)
- Consider improving mesh quality instead of using first-order schemes

See: Roache, P.J. (1998). Verification of Codes and Calculations.
     AIAA Journal, 36(5), 696-702. (Grid Convergence Index method)
"""

from typing import Any, Dict

config: Dict[str, Any] = {
    # Time discretization
    "ddtSchemes": {
        "default": "Euler",
        "_comment": "First-order implicit - maximum stability, but introduces temporal diffusion"
    },

    # Gradient discretization
    "gradSchemes": {
        "default": "cellLimited Gauss linear 1.0",
        "grad(U)": "cellLimited Gauss linear 1.0",
        "_comment": "Bounded gradient with limiter=1.0 - stable on highly skewed cells, prevents overshoots"
    },

    # Convection discretization
    "divSchemes": {
        "default": "none",
        "div(phi,U)": "Gauss upwind",
        "div(phi,k)": "Gauss upwind",
        "div(phi,omega)": "Gauss upwind",
        "div(phi,epsilon)": "Gauss upwind",
        "div((nuEff*dev2(T(grad(U)))))": "Gauss linear",
        "_comment": "First-order upwind - bounded and stable but diffusive. Use only for stability."
    },

    # Laplacian discretization
    "laplacianSchemes": {
        "default": "Gauss linear corrected",
        "_comment": "Second-order with non-orthogonal correction"
    },

    # Interpolation
    "interpolationSchemes": {
        "default": "linear",
        "_comment": "Second-order linear interpolation"
    },

    # Surface-normal gradients
    "snGradSchemes": {
        "default": "corrected",
        "_comment": "Corrected for non-orthogonal meshes"
    },

    # Solver settings
    "solvers": {
        "PIMPLE": {
            "nOuterCorrectors": 3,
            "nCorrectors": 3,
            "nNonOrthogonalCorrectors": 2,
            "_comment": "Many correctors for stability on poor meshes"
        },
        "relaxationFactors": {
            "fields": {
                "p": 0.2,
                "_comment": "Heavy pressure relaxation for stability"
            },
            "equations": {
                "U": 0.5,
                "k": 0.5,
                "omega": 0.5,
                "epsilon": 0.5,
                "_comment": "Heavy equation relaxation - slower but more stable"
            }
        },
        "residualControl": {
            "p": 1e-5,
            "U": 1e-5,
            "k": 1e-5,
            "omega": 1e-5,
            "_comment": "Tight tolerances compensate for first-order accuracy loss"
        }
    },

    # Time stepping
    "time_stepping": {
        "max_co": 0.5,
        "max_delta_t": 0.001,
        "adjustable_time_step": True,
        "_comment": "Small time steps for stability with Euler scheme"
    },

    # Metadata
    "_profile_metadata": {
        "name": "conservative",
        "order_of_accuracy": 1,
        "stability": "maximum",
        "intended_use": "debugging, poor meshes, initial testing",
        "not_recommended_for": "final results, publication, validation studies",
        "expected_diffusion": "high",
        "literature": [
            "OpenFOAM User Guide v11, Section 4.4 (Numerical Schemes)",
            "Ferziger & Peric (2002), Computational Methods for Fluid Dynamics, Ch. 5"
        ]
    }
}

__all__ = ["config"]
