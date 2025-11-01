"""Aggressive numeric profile - Minimal dissipation for wall-resolved LES.

⚠️  EXPERT USE ONLY ⚠️
=====================
This profile uses unbounded second-order schemes with minimal numerical
dissipation. It REQUIRES:
- Wall-resolved LES mesh (y+ < 1, cells_per_diameter ≥ 25)
- Excellent mesh quality (ortho > 80°, skewness < 1)
- Very small time steps (max Co ≤ 0.3)
- Experienced user who understands stability trade-offs

DO NOT USE for RANS or coarse LES - will diverge or produce oscillations.

INTENDED USE
============
- Wall-resolved Large Eddy Simulation (LES)
- Direct Numerical Simulation (DNS)
- High-fidelity turbulence research
- Cases where numerical diffusion must be absolutely minimized
- Comparison to experimental PIV/LDA data

CHARACTERISTICS
===============
Time Integration:    CrankNicolson 0.7 (more explicit character for accuracy)
Convection:          Gauss linear (pure central differencing - unbounded!)
Gradients:           Gauss linear (2nd order)
Laplacian:           Gauss linear corrected (2nd order, unbounded correction)
Solver:              PIMPLE with few correctors (rely on small time steps)
Relaxation:          Minimal (rely on small Δt and correctors)
Residual tolerance:  1e-5 (moderate - many small time steps compensate)
Max Courant:         0.3 (very small for stability with unbounded schemes)

TRADE-OFFS
==========
✅ Pros:
   - Absolutely minimal numerical diffusion
   - Preserves turbulent structures and vortices
   - Appropriate for wall-resolved LES
   - Suitable for turbulence research

⚠️  CRITICAL REQUIREMENTS:
   - Mesh: cells_per_diameter ≥ 25, y+ < 1
   - Quality: orthogonality > 80°, skewness < 1
   - Time step: Δt ~ 1e-5 to 1e-6 seconds
   - Budget: 10-50x more expensive than RANS

❌ Will Fail If:
   - Mesh quality is poor → DIVERGENCE
   - Time step too large (Co > 0.5) → OSCILLATIONS
   - Used with RANS → UNBOUNDED SOLUTION
   - Wall y+ > 1 → INCORRECT WALL MODELING

LITERATURE BASIS
================
Central Differencing for LES:
  Pope, S.B. (2000). Turbulent Flows. Cambridge University Press.
  "For LES, central differencing is preferred to minimize numerical
   dissipation, which would interfere with subgrid-scale modeling."

  Sagaut, P. (2006). Large Eddy Simulation for Incompressible Flows.
  Springer. Section 4.3.2: "Upwind-biased schemes should be avoided
   for LES as they introduce excessive numerical dissipation."

Unbounded vs Bounded Schemes:
  Wolf Dynamics (2015). CFD Tips & Tricks:
  "Linear schemes are second-order and unbounded but may be oscillatory.
   Use only with very fine meshes and small time steps."

  OpenFOAM User Guide, Section 4.4.2:
  "Central differencing (Gauss linear) has no numerical diffusion but
   can produce oscillations. Requires fine meshes and small Courant numbers."

Wall-Resolved LES Requirements:
  Choi, H., Moin, P. (2012). "Grid-point requirements for LES."
  Journal of Computational Physics, 231(2), 516-523.
  Recommends: Δx+ < 50-100, Δy+ < 1, Δz+ < 15-40 in wall units.

MESH REQUIREMENTS
=================
STRICT requirements - failure to meet these will cause divergence:

Resolution:
  cells_per_diameter: ≥ 25 (preferably 30-40)
  y+ at wall:         < 1 (wall-resolved, NOT wall-modeled)
  Boundary layers:    ≥ 8 layers, expansion ratio < 1.15

Quality:
  Orthogonality:  > 80° (STRICT - central differencing is sensitive)
  Max skewness:   < 1 (preferably < 0.5)
  Aspect ratio:   < 20 near walls, < 50 in bulk flow

Time stepping:
  max_co:         ≤ 0.3 (may need 0.1-0.2 for stability)
  Δt:             ~ 1e-5 to 1e-6 seconds (acoustic CFL)
  Total timesteps: 50,000-500,000 (LES needs long integration times)

Turbulence model:
  MUST use: WALE, dynamic Smagorinsky, or no SGS model (implicit LES)
  DO NOT use: RANS models (will diverge)

WHEN TO USE
===========
Use this profile ONLY when:
1. Running wall-resolved LES (y+ < 1 verified)
2. Mesh quality exceeds all requirements above
3. Computational budget allows 10-50x RANS cost
4. Turbulent structures/dynamics are research objective
5. You understand LES theory and numerical stability

DO NOT USE if:
- Running RANS (use publication profile instead)
- Mesh is coarse (y+ > 1, cells/D < 20)
- Need quick results (use standard profile)
- Unsure about LES requirements (get expert help first)

VALIDATION REQUIREMENTS
=======================
When using this profile:

1. Verify Wall Resolution:
   - Post-process y+ field: max(y+) < 1 everywhere
   - Check resolved turbulent structures near walls
   - Verify boundary layer velocity profile matches theory

2. Check Numerical Stability:
   - Monitor Courant number: max(Co) < 0.3 at all times
   - Residuals should decrease smoothly (no spikes)
   - No unbounded growth in any field

3. LES Quality Metrics:
   - Resolved turbulent kinetic energy > 80% of total
   - Two-point correlations to verify resolution
   - Energy spectra show -5/3 slope in inertial subrange

4. Temporal Averaging:
   - LES requires averaging over many flow-through times
   - Minimum: 10 cardiac cycles for hemodynamics
   - Preferably: 20+ cycles for converged statistics

5. Comparison to Data:
   - Experimental PIV/LDA if available
   - DNS for canonical flows
   - Published LES studies of similar geometry

COMPUTATIONAL COST
==================
Expect 10-50x RANS cost due to:
- Very fine mesh (cells_per_diameter ≥ 25, y+ < 1)
- Small time steps (Δt ~ 1e-5 s, max Co ~ 0.3)
- Long integration times (50,000+ time steps)
- Parallel scaling required (typically 64-256 cores)

Example: Aorta LES
- Mesh: 8-15 million cells
- Time step: 5e-6 seconds
- Cardiac cycles: 20 (70 seconds of flow)
- Timesteps: 14,000,000
- Wallclock: 2-4 weeks on 128 cores

Budget and plan accordingly.

TROUBLESHOOTING
===============
If solution diverges:
1. Check y+: post-process yPlus field, must be < 1
2. Reduce Co: try 0.2 or even 0.1
3. Increase correctors: try nOuterCorrectors = 3
4. Check mesh quality: re-run checkMesh, fix ALL warnings
5. Verify SGS model: must be LES model (WALE/Smagorinsky), not RANS

If results are oscillatory:
1. Time step too large: reduce Co to 0.1-0.2
2. Need more averaging: run 10+ more cardiac cycles
3. Check inlet BC: turbulent fluctuations may need damping

If no turbulence develops:
1. Inlet BC may be too smooth: add perturbations
2. Re too low: LES may not be appropriate (use laminar or RANS)
3. Mesh too coarse: increase resolution

EXAMPLE METHODS SECTION
========================
For inclusion in paper:

  "Wall-resolved large eddy simulation was performed using OpenFOAM vXX
   with the WALE subgrid-scale model. Pure central differencing (Gauss linear)
   was employed for all convective terms to minimize numerical dissipation.
   Time integration used the Crank-Nicolson scheme (α=0.7) with adaptive
   time-stepping maintaining max Courant number Co ≤ 0.3. The mesh contained
   [X] million cells with wall-normal resolution y+ < 1 throughout. Simulations
   were averaged over [N] cardiac cycles after initial transients decayed.
   LES quality was verified by checking resolved turbulent kinetic energy
   exceeded 80% of total, and energy spectra exhibited -5/3 inertial subrange
   scaling."
"""

from typing import Any, Dict

config: Dict[str, Any] = {
    # Time discretization
    "ddtSchemes": {
        "default": "CrankNicolson 0.7",
        "_comment": (
            "Second-order with 70% implicit, 30% explicit. "
            "More explicit than publication profile for LES accuracy. "
            "REQUIRES small time steps (max Co ≤ 0.3). "
            "Increase to 0.9 if stability issues arise."
        )
    },

    # Gradient discretization
    "gradSchemes": {
        "default": "Gauss linear",
        "grad(U)": "Gauss linear",
        "_comment": "Second-order central differencing - no dissipation"
    },

    # Convection discretization
    "divSchemes": {
        "default": "none",
        "div(phi,U)": "Gauss linear",
        "div(phi,k)": "Gauss linear",
        "div((nuEff*dev2(T(grad(U)))))": "Gauss linear",
        "div(B)": "Gauss linear",
        "div(phi,B)": "Gauss linear",
        "_comment": (
            "⚠️  UNBOUNDED CENTRAL DIFFERENCING ⚠️  "
            "Gauss linear = pure central, 2nd order, NO numerical diffusion. "
            "WILL OSCILLATE or DIVERGE if: "
            "  - Mesh quality poor (ortho < 80°, skew > 1) "
            "  - Time step too large (Co > 0.3) "
            "  - Used with RANS (not LES) "
            "See Pope (2000), Sagaut (2006) for LES numerics theory."
        )
    },

    # Laplacian discretization
    "laplacianSchemes": {
        "default": "Gauss linear corrected",
        "_comment": (
            "Second-order, unbounded non-orthogonal correction. "
            "Requires excellent mesh quality (ortho > 80°)."
        )
    },

    # Interpolation
    "interpolationSchemes": {
        "default": "linear",
        "_comment": "Second-order linear interpolation"
    },

    # Surface-normal gradients
    "snGradSchemes": {
        "default": "corrected",
        "_comment": "Unbounded correction - requires high-quality mesh"
    },

    # Solver settings
    "solvers": {
        "PIMPLE": {
            "nOuterCorrectors": 1,
            "nCorrectors": 2,
            "nNonOrthogonalCorrectors": 0,
            "_comment": (
                "Few correctors - rely on small time steps instead. "
                "Increase nOuterCorrectors to 2-3 if stability issues."
            )
        },
        "relaxationFactors": {
            "fields": {
                "p": 1.0,
                "_comment": "No relaxation - rely on small Δt and correctors"
            },
            "equations": {
                "U": 1.0,
                "_comment": "No relaxation for LES - time-accurate solution required"
            }
        },
        "residualControl": {
            "p": 1e-5,
            "U": 1e-5,
            "_comment": (
                "Moderate tolerance - many small time steps compensate. "
                "LES focuses on resolved turbulence, not tight convergence."
            )
        }
    },

    # Time stepping
    "time_stepping": {
        "max_co": 0.3,
        "max_delta_t": 5e-5,
        "adjustable_time_step": True,
        "_comment": (
            "CRITICAL: max_co ≤ 0.3 for stability with central differencing. "
            "May need Co = 0.1-0.2 for very challenging cases. "
            "Typical Δt ~ 1e-5 to 1e-6 seconds for hemodynamics LES."
        )
    },

    # Metadata
    "_profile_metadata": {
        "name": "aggressive",
        "order_of_accuracy": 2,
        "stability": "UNSTABLE without strict requirements",
        "expert_only": True,
        "intended_use": "wall-resolved LES, DNS, minimal-dissipation research",
        "not_recommended_for": "RANS, coarse LES, production runs, beginners",
        "expected_diffusion": "none (all physical, no numerical)",
        "mesh_requirements": (
            "cells_per_diameter ≥ 25, y+ < 1, "
            "orthogonality > 80°, skewness < 1, "
            "aspect ratio < 20 near walls"
        ),
        "literature": [
            "Pope, S.B. (2000). Turbulent Flows. Cambridge University Press",
            "Sagaut, P. (2006). Large Eddy Simulation. Springer, Section 4.3",
            "Choi & Moin (2012). Grid requirements for LES. J. Comp. Phys. 231(2)",
            "OpenFOAM User Guide v11, Section 4.4 (Central Differencing)",
            "Wolf Dynamics (2015). CFD Tips: Unbounded vs Bounded Schemes"
        ],
        "validation_checklist": [
            "Verify y+ < 1 everywhere (post-process yPlus field)",
            "Monitor Courant number: max(Co) < 0.3 at all times",
            "Check LES quality: resolved TKE > 80% of total",
            "Verify energy spectra: -5/3 slope in inertial range",
            "Average over ≥ 10 cardiac cycles (or flow-through times)",
            "Compare to experimental data (PIV/LDA) if available",
            "Document computational cost and scaling"
        ],
        "computational_cost_multiplier": "10-50x vs RANS",
        "typical_mesh_size": "8-15 million cells for aorta",
        "typical_timesteps": "50,000-500,000 (depends on physics timescale)",
        "typical_wallclock": "1-4 weeks on 64-256 cores",
        "example_methods_section": (
            "Wall-resolved LES with WALE SGS model. "
            "Pure central differencing (Gauss linear) for minimal dissipation. "
            "Crank-Nicolson time integration (α=0.7), max Co=0.3. "
            "Mesh: [X]M cells, y+<1. Averaged over [N] cycles. "
            "LES quality: resolved TKE>80%, E(k)~k^(-5/3) verified."
        ),
        "warnings": [
            "⚠️  WILL DIVERGE on poor-quality meshes",
            "⚠️  WILL OSCILLATE if time step too large (Co > 0.5)",
            "⚠️  DO NOT USE with RANS turbulence models",
            "⚠️  REQUIRES y+ < 1 (wall-resolved, not wall-modeled)",
            "⚠️  10-50x more expensive than RANS",
            "⚠️  Consult LES expert if unsure"
        ]
    }
}

__all__ = ["config"]
