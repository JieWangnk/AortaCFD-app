"""Accurate numeric profile - Second-order with low numerical diffusion.

INTENDED USE
============
- Mesh independence / convergence studies (GCI analysis)
- Validation against experimental data
- Cases requiring lower diffusion than standard profile
- Good mesh quality (ortho > 65°, skewness < 3)

CHARACTERISTICS
===============
Time Integration:    backward (2nd order implicit)
Convection:          Gauss linearUpwind grad(U) (2nd order, low diffusion)
Gradients:           cellLimited Gauss linear 1.0 (standard limiting)
Laplacian:           Gauss linear corrected (full non-orthogonal correction)
Solver:              PIMPLE with convergence-based exit
Relaxation:          Moderate (p: 0.3, U: 0.7)
Residual tolerance:  1e-7 (tighter than standard)
Max Courant:         1.0 (adaptive time-stepping)

COMPARISON TO OTHER PROFILES
=============================

vs standard:
- Lower diffusion: linearUpwind vs limitedLinearV (TVD)
- Full correction: corrected vs limited corrected 0.5
- Tighter tolerances: 1e-7 vs 1e-6
- Requires better mesh quality

vs precise:
- More stable: backward vs CrankNicolson, linearUpwind vs LUST
- Less mesh-sensitive: works on ortho > 65° vs ortho > 70°
- Faster computation: ~1.5x vs 2-3x baseline

TRADE-OFFS
==========
Pros:
   - Second-order with lower diffusion than standard
   - More stable than precise profile
   - Good for mesh convergence studies
   - Works on typical good-quality meshes

Neutral:
   - Requires good mesh quality (ortho > 65°, skewness < 3)
   - ~1.5x runtime vs standard

Cons:
   - Not as low-diffusion as precise (for LES, use precise)
   - May show oscillations on poor meshes (use standard)

WHEN TO USE
===========
Use 'accurate' profile when:
1. Performing mesh independence studies (GCI analysis)
2. Validating against experimental data
3. Good mesh quality verified (ortho > 65°)
4. Need lower diffusion than standard but more stability than precise

Use 'standard' profile when:
1. Production runs with Windkessel outlets
2. Typical mesh quality
3. Stability is priority

Use 'precise' profile when:
1. LES simulations (LUST required)
2. Excellent mesh quality (ortho > 70°)
3. Minimal diffusion required

MESH REQUIREMENTS
=================
Recommended mesh quality:
- Orthogonality: > 65 degrees (> 70 preferred)
- Max skewness: < 3 (< 2 preferred)
- Aspect ratio: < 100 (< 50 in regions of interest)
- y+ (for RANS): 1-10 for wall-resolved, 30-300 for wall functions

LITERATURE BASIS
================
- OpenFOAM User Guide (section 4.4.2): "linearUpwind provides second-order
  accuracy with improved stability over pure central differencing."

- Jasak, H. (1996). Error Analysis and Estimation for FVM with Applications
  to Fluid Flows. PhD Thesis, Imperial College.

- Roache, P.J. (1998). Verification and Validation. AIAA Journal 36(5).
"""

from typing import Any, Dict

config: Dict[str, Any] = {
    # Time discretization
    "ddtSchemes": {
        "default": "backward",
        "_comment": "Second-order implicit - stable and accurate for transient flows"
    },

    # Gradient discretization
    "gradSchemes": {
        "default": "cellLimited Gauss linear 1",
        "grad(U)": "cellLimited Gauss linear 1",
        "grad(p)": "Gauss linear",
        "_comment": "Standard gradient limiting (1.0) - less restrictive than standard profile"
    },

    # Convection discretization
    "divSchemes": {
        "default": "none",
        "div(phi,U)": "Gauss linearUpwind grad(U)",
        "div(phi,k)": "Gauss linearUpwind grad(k)",
        "div(phi,omega)": "Gauss linearUpwind grad(omega)",
        "div(phi,epsilon)": "Gauss linearUpwind grad(epsilon)",
        "div((nuEff*dev2(T(grad(U)))))": "Gauss linear",
        "_comment": (
            "linearUpwind: 2nd order with gradient-based upwinding. "
            "Lower diffusion than limitedLinearV but unbounded. "
            "Requires good mesh quality for stability."
        )
    },

    # Laplacian discretization
    "laplacianSchemes": {
        "default": "Gauss linear corrected",
        "_comment": "Full non-orthogonal correction - requires good mesh orthogonality"
    },

    # Interpolation
    "interpolationSchemes": {
        "default": "linear",
        "_comment": "Second-order linear interpolation"
    },

    # Surface-normal gradients
    "snGradSchemes": {
        "default": "corrected",
        "_comment": "Full correction - requires good mesh orthogonality"
    },

    # Solver settings
    "solvers": {
        "PIMPLE": {
            "nOuterCorrectors": 50,
            "nCorrectors": 2,
            "nNonOrthogonalCorrectors": 1,
            "momentumPredictor": True,
            "_comment": (
                "HIGH nOuterCorrectors (50) with convergence-based early exit. "
                "Standard corrector counts for efficiency."
            ),
            "outerCorrectorResidualControl": {
                "p": {"tolerance": 1e-4, "relTol": 0},
                "U": {"tolerance": 1e-5, "relTol": 0},
                "(k|epsilon|omega)": {"tolerance": 1e-5, "relTol": 0},
                "_comment": "Standard tolerances for convergence-based early exit"
            }
        },
        "relaxationFactors": {
            "fields": {
                "p": 0.3,
                "pFinal": 1.0,
                "_comment": "Moderate pressure relaxation with full correction on final iteration"
            },
            "equations": {
                "U": 0.7,
                "UFinal": 1.0,
                "k": 0.7,
                "kFinal": 1.0,
                "omega": 0.7,
                "omegaFinal": 1.0,
                "epsilon": 0.7,
                "epsilonFinal": 1.0,
                "_comment": "Moderate relaxation with full correction on final PIMPLE iteration"
            }
        },
        "residualControl": {
            "p": 1e-7,
            "U": 1e-7,
            "k": 1e-7,
            "omega": 1e-7,
            "_comment": "Tighter tolerance than standard for convergence studies"
        }
    },

    # Time stepping
    "time_stepping": {
        "max_co": 1.0,
        "initial_delta_t": 1e-6,
        "max_delta_t": 1e-3,
        "adjustable_time_step": True,
        "_comment": "Standard time stepping with Co=1.0"
    },

    # Metadata
    "_profile_metadata": {
        "name": "accurate",
        "order_of_accuracy": 2,
        "stability": "good",
        "numerical_diffusion": "low (linearUpwind)",
        "intended_use": "convergence studies, validation, good meshes",
        "recommended_for": "mesh independence studies, validation cases",
        "expected_diffusion": "low (unbounded 2nd order)",
        "mesh_requirements": "orthogonality > 65 degrees, skewness < 3",
        "key_features": [
            "linearUpwind for low-diffusion convection",
            "Full corrected Laplacian/snGrad",
            "Tighter tolerances (1e-7)",
            "pFinal/UFinal = 1 for full correction"
        ],
        "literature": [
            "OpenFOAM User Guide v11, Section 4.4 (Numerical Schemes)",
            "Jasak, H. (1996). Error Analysis for FVM. PhD Thesis, Imperial College",
            "Roache, P.J. (1998). Verification and Validation. AIAA Journal 36(5)"
        ]
    }
}

__all__ = ["config"]
