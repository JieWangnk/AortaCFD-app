"""Standard numeric profile - Second-order bounded schemes, production quality.

INTENDED USE
============
- Production simulations with good-quality meshes
- Clinical studies requiring accurate flow predictions
- Most laminar and RANS cases
- Default choice for validated geometries

CHARACTERISTICS
===============
Time Integration:    backward (2nd order implicit)
Convection:          Gauss linearUpwind (2nd order, bounded via upwind gradient)
Gradients:           Gauss linear (2nd order)
Laplacian:           Gauss linear corrected (2nd order)
Solver:              PIMPLE with moderate correctors
Relaxation:          Moderate (U: 0.7, p: 0.3)
Residual tolerance:  1e-6 (standard for clinical applications)
Max Courant:         1.0 (adaptive time-stepping)

TRADE-OFFS
==========
✅ Pros:
   - Second-order accurate in space and time
   - Bounded schemes prevent oscillations
   - Good balance of accuracy and stability
   - Mesh convergence achievable with refinement

⚖️ Neutral:
   - Requires reasonable mesh quality (ortho > 60°, skewness < 3)
   - May need slight relaxation on challenging cases

❌ Cons (minor):
   - Not as stable as first-order on very poor meshes
   - Slight numerical diffusion from limiters (less than upwind)

LITERATURE BASIS
================
OpenFOAM User Guide (section 4.4.2):
  "limitedLinear and linearUpwind provide good compromise between
   accuracy and boundedness for convection-dominated flows."

Jasak, H. (1996). Error Analysis and Estimation for FVM with Applications
to Fluid Flows. PhD Thesis, Imperial College:
  "Second-order schemes are essential for accurate flow prediction.
   Upwind-biased schemes (linearUpwind, LUST) provide boundedness."

CFD Best Practices (NASA, AIAA):
  "Always aim for second-order accurate solutions. First-order methods
   should only be used temporarily for convergence acceleration."

MESH REQUIREMENTS
=================
Recommended mesh quality:
- Orthogonality: > 60° (> 70° preferred)
- Max skewness: < 3 (< 2 preferred)
- Aspect ratio: < 100 (< 50 in regions of interest)
- y+ (for RANS): 1-10 for wall functions, < 1 for wall-resolved

Run checkMesh before using this profile. If warnings appear,
consider conservative profile or mesh improvement.

WHEN TO USE
===========
Use this profile when:
1. Mesh quality is reasonable (checkMesh passes)
2. Production runs for clinical decision-making
3. Baseline accuracy is sufficient (not publication/validation)
4. Computational budget is moderate

This is the RECOMMENDED DEFAULT for most users.

VALIDATION REQUIREMENTS
=======================
For publication or validation studies:
- Perform mesh independence study (1.5x refinement shows < 5% change)
- Verify second-order convergence rate (log-log plot)
- Compare to experimental/analytical data if available
- Document residual histories and mass conservation

Consider 'publication' profile if:
- Tighter tolerances needed (residuals < 1e-8)
- Reviewing mesh independence reveals sensitivity
- Comparisons to reference data show systematic bias
"""

from typing import Any, Dict

config: Dict[str, Any] = {
    # Time discretization
    "ddtSchemes": {
        "default": "backward",
        "_comment": "Second-order implicit - good accuracy and stability for transient flows"
    },

    # Gradient discretization
    "gradSchemes": {
        "default": "cellLimited Gauss linear 1.0",
        "grad(U)": "cellLimited Gauss linear 1.0",
        "_comment": "Bounded gradient limiter=1.0 - stable on skewed cells (skewness < 4), prevents overshoots"
    },

    # Convection discretization
    "divSchemes": {
        "default": "none",
        "div(phi,U)": "Gauss linearUpwind grad(U)",
        "div(phi,k)": "Gauss limitedLinear 1",
        "div(phi,omega)": "Gauss limitedLinear 1",
        "div(phi,epsilon)": "Gauss limitedLinear 1",
        "div((nuEff*dev2(T(grad(U)))))": "Gauss linear",
        "_comment": (
            "linearUpwind: 2nd order, upwind-biased (bounded). "
            "limitedLinear: 2nd order, TVD limited (bounded). "
            "Coefficient '1' = full limiting for robustness."
        )
    },

    # Laplacian discretization
    "laplacianSchemes": {
        "default": "Gauss linear corrected",
        "_comment": "Second-order with explicit non-orthogonal correction"
    },

    # Interpolation
    "interpolationSchemes": {
        "default": "linear",
        "_comment": "Second-order linear interpolation"
    },

    # Surface-normal gradients
    "snGradSchemes": {
        "default": "corrected",
        "_comment": "Corrected snGrad for non-orthogonal meshes"
    },

    # Solver settings
    "solvers": {
        "PIMPLE": {
            "nOuterCorrectors": 2,
            "nCorrectors": 2,
            "nNonOrthogonalCorrectors": 1,
            "_comment": "Moderate correctors - balance between accuracy and cost"
        },
        "relaxationFactors": {
            "fields": {
                "p": 0.3,
                "_comment": "Moderate pressure relaxation"
            },
            "equations": {
                "U": 0.7,
                "k": 0.7,
                "omega": 0.7,
                "epsilon": 0.7,
                "_comment": "Moderate equation relaxation - standard practice"
            }
        },
        "residualControl": {
            "p": 1e-6,
            "U": 1e-6,
            "k": 1e-6,
            "omega": 1e-6,
            "_comment": "Standard tolerance for clinical/engineering applications"
        }
    },

    # Time stepping
    "time_stepping": {
        "max_co": 1.0,
        "max_delta_t": 0.001,
        "adjustable_time_step": True,
        "_comment": "Co=1 is standard for backward scheme. Adjustable time-stepping for efficiency."
    },

    # Metadata
    "_profile_metadata": {
        "name": "standard",
        "order_of_accuracy": 2,
        "stability": "good",
        "intended_use": "production runs, clinical studies, default choice",
        "recommended_for": "laminar and RANS with reasonable mesh quality",
        "expected_diffusion": "low",
        "mesh_requirements": "orthogonality > 60°, skewness < 3",
        "literature": [
            "OpenFOAM User Guide v11, Section 4.4 (Numerical Schemes)",
            "Jasak, H. (1996). Error Analysis for FVM. PhD Thesis, Imperial College",
            "Roache, P.J. (1998). Verification and Validation in CFD. AIAA Journal 36(5)"
        ],
        "validation_checklist": [
            "Run checkMesh and resolve warnings",
            "Monitor residuals < 1e-6",
            "Check mass conservation < 0.1%",
            "Perform mesh independence study at 1.5x refinement"
        ]
    }
}

__all__ = ["config"]
