"""Accurate numeric profile - High accuracy for all physics models (laminar, RANS, LES).

INTENDED USE
============
- Publication-quality simulations
- Validation and verification studies
- Mesh independence demonstrations
- Any case requiring high accuracy
- All physics models: laminar, RANS k-ω SST, LES

CHARACTERISTICS
===============
Time Integration:    CrankNicolson 0.9 (2nd order, implicit-explicit blend)
Convection:          Gauss LUST grad(U) (hybrid: 75% central + 25% upwind, low diffusion)
Gradients:           cellLimited Gauss linear 0.5 (tighter limiting than standard)
Laplacian:           Gauss linear limited corrected 0.33 (bounded non-orthogonal correction)
Solver:              PIMPLE with many correctors (3 outer, 3 inner)
Relaxation:          Light (U: 0.9, p: 0.5) - rely on correctors for stability
Residual tolerance:  1e-8 (very tight, publication quality)
Max Courant:         0.8 (smaller time steps for accuracy)

IMPROVEMENTS OVER STANDARD
===========================
1. **Time Integration**: CrankNicolson 0.9 (2nd order) vs backward (2nd order)
   - CN has better phase accuracy for wave propagation
   - CN 0.9 coefficient balances accuracy (implicit-explicit blend) with stability

2. **Convection**: LUST vs linearUpwind
   - LUST = 75% central + 25% upwind blend
   - Less numerical diffusion than pure linearUpwind
   - Still bounded for stability

3. **Tighter Tolerances**: 1e-8 vs 1e-6
   - Ensures converged solutions
   - Essential for mesh independence studies

4. **More Correctors**: 3/3 vs 2/2 (outer/inner)
   - Better pressure-velocity coupling
   - More accurate mass conservation

5. **Limited Laplacian**: Coefficient 0.33
   - Better handling of non-orthogonal meshes
   - Prevents overshoot on imperfect meshes

TRADE-OFFS
==========
✅ Pros:
   - Higher accuracy than standard (less numerical diffusion)
   - Suitable for ALL physics models (laminar, RANS, LES)
   - Publication-quality results
   - Demonstrates mesh convergence
   - Defensible numerical choices for papers

⚖️ Neutral:
   - Requires GOOD mesh quality (ortho > 70°, skewness < 2)
   - ~2-3x longer runtime than standard (tighter tolerances, more correctors)

❌ Cons:
   - More expensive than standard
   - May not converge on poor-quality meshes (use standard or improve mesh)
   - Not necessary for routine/screening simulations

WHEN TO USE
===========
Use 'accurate' profile when:
1. ✅ Publishing in journals or conferences
2. ✅ Validating against experimental data
3. ✅ Performing mesh independence studies
4. ✅ LES simulations (all LES should use accurate)
5. ✅ Final production runs for important cases

Use 'standard' profile when:
1. 🔄 Initial testing or geometry exploration
2. 🔄 Screening multiple cases quickly
3. 🔄 Mesh quality is marginal (60° < ortho < 70°)
4. 🔄 Computational budget is limited

Use 'conservative' profile when:
1. ⚠️ Debugging convergence issues
2. ⚠️ Very poor mesh quality
3. ⚠️ Initial geometry validation

MESH REQUIREMENTS
=================
Minimum requirements for 'accurate' profile:

Orthogonality:  > 70° (preferably > 75°)
Max skewness:   < 2 (preferably < 1.5)
Aspect ratio:   < 100 (< 50 in regions of interest)

For RANS:
- y+ = 1-10 (wall-resolved or enhanced wall treatment)
- OR y+ = 30-300 (wall functions with high-quality near-wall mesh)

For LES:
- y+ < 1 (MANDATORY wall-resolved)
- Smooth boundary layer mesh with expansion ratio < 1.3

Run checkMesh and resolve major warnings before using this profile.

LITERATURE BASIS
================
LUST Scheme (Linear Upwind Stabilised Transport):
  Friess, C., Manceau, R., Gatski, T.B. (2015).
  "Toward an equivalence criterion for hybrid RANS/LES methods."
  Computers & Fluids, 122, 233-246.

CrankNicolson Time Integration:
  Crank, J., Nicolson, P. (1947).
  "A practical method for numerical evaluation of PDEs."
  Mathematical Proceedings of the Cambridge Philosophical Society.

OpenFOAM User Guide (v11+):
  Section 4.4.1: "CrankNicolson coefficient 0.9 provides good balance"
  Section 4.4.2: "LUST combines accuracy of central with boundedness"

Verification & Validation:
  Roache, P.J. (1998). "Verification of Codes and Calculations."
  AIAA Journal, 36(5), 696-702. (Grid Convergence Index method)

VALIDATION CHECKLIST
====================
When using 'accurate' profile for publication:

1. ✅ Mesh Independence Study:
   - Run at 3 mesh levels (base, 1.5x refinement, 2x refinement)
   - Calculate Grid Convergence Index (GCI)
   - Verify monotonic convergence
   - Document observed order of accuracy (should be ~2)

2. ✅ Temporal Convergence:
   - Halve time-step (Co → Co/2)
   - Show < 1% change in key results
   - Verify second-order temporal accuracy

3. ✅ Residual Monitoring:
   - All residuals < 1e-8
   - Mass conservation error < 0.01%
   - Document residual histories

4. ✅ Scheme Documentation:
   - State: "LUST convection (bounded 2nd order)"
   - State: "CrankNicolson 0.9 time integration"
   - Cite relevant literature

5. ✅ Comparison (if available):
   - Experimental data
   - Analytical solutions
   - Higher-fidelity simulations (DNS/LES for RANS validation)

EXAMPLE METHODS SECTION FOR PAPER
==================================
"Simulations employed OpenFOAM v12 with second-order accurate
discretization schemes throughout. Time integration used the Crank-Nicolson
scheme (α=0.9), providing implicit stability with reduced numerical diffusion
compared to fully implicit methods. Convection terms employed the Linear
Upwind Stabilised Transport (LUST) scheme, which blends 75% central
differencing with 25% linearUpwind stabilization, maintaining second-order
accuracy while ensuring boundedness. Pressure-velocity coupling utilized the
PIMPLE algorithm with 3 outer correctors and 3 inner pressure correctors per
time step. All equation residuals were converged to 10⁻⁸. Mesh independence
was verified via Grid Convergence Index analysis on three successively refined
meshes (refinement ratio r=√2), yielding estimated discretization errors of
<2% for all reported quantities."

COMPUTATIONAL COST
==================
Expect ~2-3x longer runtime compared to 'standard' profile:
- Tighter tolerances: 1e-8 vs 1e-6 → +30-50% per iteration
- More correctors: 3/3 vs 2/2 → +50% per time step
- Smaller Co: 0.8 vs 1.0 → +25% more time steps

Budget accordingly. For a standard case taking 1 hour on 'standard',
expect 2-3 hours on 'accurate'.

This is WORTH IT for:
- Publications (necessary for credibility)
- Validation studies (essential for accuracy)
- Final production runs (justifies computational cost)

Not worth it for:
- Initial geometry testing (use standard)
- Multiple screening cases (use standard)
- Parametric studies (use standard, then verify with accurate)
"""

from typing import Any, Dict

config: Dict[str, Any] = {
    # Time discretization
    "ddtSchemes": {
        "default": "CrankNicolson 0.9",
        "_comment": (
            "Second-order implicit-explicit blend (α=0.9). "
            "Better phase accuracy than backward scheme. "
            "90% implicit (stable), 10% explicit (accurate). "
            "Use 1.0 if stability issues arise."
        )
    },

    # Gradient discretization
    "gradSchemes": {
        "default": "cellLimited Gauss linear 0.5",
        "grad(U)": "cellLimited Gauss linear 0.5",
        "_comment": (
            "Tighter limiting (0.5) than standard (1.0). "
            "Reduces overshoots on complex geometries. "
            "Requires ortho > 70° for stability."
        )
    },

    # Convection discretization
    "divSchemes": {
        "default": "none",
        "div(phi,U)": "Gauss LUST grad(U)",
        "div(phi,k)": "Gauss limitedLinear 1",
        "div(phi,omega)": "Gauss limitedLinear 1",
        "div(phi,epsilon)": "Gauss limitedLinear 1",
        "div((nuEff*dev2(T(grad(U)))))": "Gauss linear",
        "div(B)": "Gauss linear",
        "_comment": (
            "LUST: Linear Upwind Stabilised Transport. "
            "Blends 75% Gauss linear (central) + 25% linearUpwind. "
            "Lower numerical diffusion than pure linearUpwind. "
            "Bounded stability suitable for all physics models. "
            "Turbulence: limitedLinear 1 (bounded, conservative for k/ω/ε). "
            "See: Friess et al. (2015), Computers & Fluids 122:233-246."
        )
    },

    # Laplacian discretization
    "laplacianSchemes": {
        "default": "Gauss linear limited corrected 0.33",
        "_comment": (
            "Second-order with limited non-orthogonal correction. "
            "Coefficient 0.33 limits correction for stability. "
            "Better than plain 'corrected' on imperfect meshes. "
            "Prevents overshoot on non-orthogonal cells."
        )
    },

    # Interpolation
    "interpolationSchemes": {
        "default": "linear",
        "_comment": "Second-order linear interpolation"
    },

    # Surface-normal gradients
    "snGradSchemes": {
        "default": "limited corrected 0.33",
        "_comment": "Limited correction matching Laplacian scheme"
    },

    # Solver settings
    "solvers": {
        "PIMPLE": {
            "nOuterCorrectors": 3,
            "nCorrectors": 3,
            "nNonOrthogonalCorrectors": 2,
            "_comment": (
                "3 outer correctors for tight pressure-velocity coupling. "
                "3 inner pressure correctors for accurate mass conservation. "
                "2 non-orthogonal correctors for complex geometries."
            )
        },
        "relaxationFactors": {
            "fields": {
                "p": 0.5,
                "_comment": "Light pressure relaxation (rely on correctors)"
            },
            "equations": {
                "U": 0.9,
                "k": 0.8,
                "omega": 0.8,
                "epsilon": 0.8,
                "_comment": "Light equation relaxation for faster convergence with many correctors"
            }
        },
        "residualControl": {
            "p": 1e-8,
            "U": 1e-8,
            "k": 1e-8,
            "omega": 1e-8,
            "_comment": "Very tight tolerances for publication quality"
        }
    },

    # Time stepping
    "time_stepping": {
        "max_co": 0.8,
        "max_delta_t": 0.0008,
        "adjustable_time_step": True,
        "_comment": (
            "Co=0.8 for accuracy with CrankNicolson. "
            "Smaller than standard (Co=1.0) for temporal accuracy. "
            "Larger than aggressive/LES-only profiles (Co=0.3-0.5). "
            "Suitable for laminar, RANS, and LES."
        )
    },

    # Metadata
    "_profile_metadata": {
        "name": "accurate",
        "order_of_accuracy": 2,
        "stability": "good (requires quality mesh)",
        "intended_use": "publications, validation, mesh independence, LES, final production runs",
        "recommended_for": "ALL physics models (laminar, RANS, LES) with good mesh quality",
        "not_recommended_for": "poor meshes, initial testing, screening simulations",
        "expected_diffusion": "low (less than standard, more than pure central)",
        "mesh_requirements": "orthogonality > 70°, skewness < 2, y+ < 1 for LES",
        "improvements_over_standard": [
            "CrankNicolson time integration (better phase accuracy)",
            "LUST convection (less diffusion than linearUpwind)",
            "Tighter tolerances (1e-8 vs 1e-6)",
            "More correctors (3/3 vs 2/2)",
            "Limited Laplacian (better non-orthogonal handling)"
        ],
        "literature": [
            "Friess et al. (2015). LUST scheme. Computers & Fluids 122:233-246",
            "Crank & Nicolson (1947). Practical method for PDEs. Math Proc Cambridge",
            "Roache, P.J. (1998). Grid Convergence Index. AIAA Journal 36(5):696-702",
            "OpenFOAM User Guide v11+, Sections 4.4-4.5 (Numerical Schemes)"
        ],
        "validation_checklist": [
            "Run checkMesh - resolve major warnings (ortho > 70°, skewness < 2)",
            "Mesh independence: 3 levels, calculate GCI, verify 2nd order convergence",
            "Temporal convergence: halve Δt, show < 1% change in key results",
            "Residuals < 1e-8 for all variables (p, U, k, ω)",
            "Mass conservation error < 0.01%",
            "Compare to experimental/analytical data if available",
            "Document: LUST convection, CrankNicolson 0.9, GCI analysis"
        ],
        "computational_cost_multiplier": "2-3x vs standard profile",
        "runtime_comparison": {
            "standard_1h": "accurate_2-3h",
            "standard_30min": "accurate_1-1.5h",
            "standard_4h": "accurate_8-12h"
        }
    }
}

__all__ = ["config"]
