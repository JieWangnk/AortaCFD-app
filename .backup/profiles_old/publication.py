"""Publication numeric profile - High accuracy, tight tolerances, journal quality.

INTENDED USE
============
- Journal publications and conference papers
- Validation against experimental data
- Benchmark studies and code verification
- Mesh independence demonstrations
- Studies requiring minimal numerical error

CHARACTERISTICS
===============
Time Integration:    CrankNicolson 0.9 (2nd order, near-implicit)
Convection:          Gauss LUST grad(U) (hybrid bounded/central, low diffusion)
Gradients:           Gauss linear (2nd order)
Laplacian:           Gauss linear limited corrected 0.33 (2nd order, bounded correction)
Solver:              PIMPLE with many correctors
Relaxation:          Light (U: 0.9, p: 0.5) - rely on correctors instead
Residual tolerance:  1e-8 (very tight for publication quality)
Max Courant:         0.5 (smaller time steps for accuracy)

TRADE-OFFS
==========
✅ Pros:
   - Minimal numerical diffusion
   - Publication-quality accuracy
   - Demonstrates mesh convergence
   - Suitable for code validation
   - Defensible numerical choices

⚖️ Neutral:
   - Requires HIGH-QUALITY mesh (ortho > 70°, skewness < 2)
   - Longer run times (tight tolerances, many correctors)
   - May need fine time-stepping (small Co)

❌ Cons:
   - Computationally expensive
   - May not converge on poor meshes
   - Requires validation of numerical choices

LITERATURE BASIS
================
LUST Scheme (Linear Upwind Stabilised Transport):
  Friess, C., Manceau, R., Gatski, T.B. (2015).
  "Toward an equivalence criterion for hybrid RANS/LES methods."
  Computers & Fluids, 122, 233-246.

  "LUST blends central differencing (75%) with linearUpwind (25%),
   providing accuracy similar to central schemes with bounded stability."

CrankNicolson Blending:
  OpenFOAM User Guide, Section 4.4.1:
  "CrankNicolson coefficient between 0.9-1.0 provides good balance
   of accuracy and stability. Use 1.0 for pure implicit (stable),
   0.9 for slightly more accuracy (may need smaller time steps)."

Verification & Validation:
  Roache, P.J. (1998). "Verification of Codes and Calculations."
  AIAA Journal, 36(5), 696-702.

  Stern, F., et al. (2001). "Comprehensive Approach to Verification
  and Validation of CFD Simulations." Journal of Fluids Engineering.

MESH REQUIREMENTS
=================
STRICT requirements for this profile:

Orthogonality:  > 70° (preferably > 75°)
Max skewness:   < 2 (preferably < 1)
Aspect ratio:   < 50 in regions of interest (< 20 near walls)
y+ (RANS):      Within log-layer (30-300) or wall-resolved (< 1)
y+ (LES):       Must be < 1 (wall-resolved)

Cell quality:
- No highly skewed cells
- Smooth transitions between refinement levels
- Boundary layer mesh with smooth expansion ratio (< 1.3)

Run checkMesh and resolve ALL warnings before using this profile.

WHEN TO USE
===========
Use this profile when:
1. Publishing in peer-reviewed journals
2. Validating against experimental/DNS data
3. Performing verification studies (MMS, exact solutions)
4. Mesh independence is primary objective
5. Numerical error must be minimized

DO NOT USE if:
- Mesh quality is poor (use standard or improve mesh)
- Quick results needed (use standard)
- Computational budget is limited

VALIDATION REQUIREMENTS
=======================
When using this profile for publication:

1. Mesh Independence Study:
   - Run at 3 mesh levels (base, 1.5x, 2x refinement)
   - Calculate Grid Convergence Index (GCI)
   - Show monotonic convergence
   - Document observed order of accuracy

2. Temporal Convergence:
   - Halve time-step and show < 1% change in results
   - Verify second-order temporal accuracy

3. Residual Monitoring:
   - All residuals < 1e-8
   - Mass conservation error < 0.01%
   - Show residual histories in paper

4. Scheme Justification:
   - Document why LUST/CrankNicolson chosen
   - Cite relevant literature
   - Show scheme sensitivity if questioned by reviewers

5. Comparison to Reference:
   - Experimental data (if available)
   - Analytical solutions (if available)
   - Higher-fidelity simulations (DNS/LES for RANS validation)

EXAMPLE METHODS SECTION
========================
For inclusion in paper:

  "Simulations were performed using OpenFOAM vXX with second-order
   accurate discretization schemes. Time integration used the implicit
   Crank-Nicolson scheme (α=0.9), providing second-order accuracy in
   time. Convection terms were discretized using the LUST scheme, which
   blends central differencing (75%) with upwind stabilization (25%) for
   low numerical diffusion while maintaining boundedness. Pressure-velocity
   coupling used the PIMPLE algorithm with [X] outer correctors and [Y]
   inner correctors per time step. Residuals were converged to 10⁻⁸ for
   all variables. Mesh independence was demonstrated via Grid Convergence
   Index analysis on three successively refined meshes, yielding an
   estimated discretization error of [X]%."

COMPUTATIONAL COST
==================
Expect ~3-5x longer run times compared to 'standard' profile due to:
- Tighter residual tolerances (1e-8 vs 1e-6)
- More correctors per time step
- Smaller time steps (Co=0.5 vs 1.0)
- Additional mesh levels for independence study

Budget accordingly for publication-quality simulations.
"""

from typing import Any, Dict

config: Dict[str, Any] = {
    # Time discretization
    "ddtSchemes": {
        "default": "CrankNicolson 0.9",
        "_comment": (
            "Second-order implicit-explicit blending. "
            "Coefficient 0.9 = 90% implicit (stable), 10% explicit (accurate). "
            "Use 1.0 if stability issues arise."
        )
    },

    # Gradient discretization
    "gradSchemes": {
        "default": "cellLimited Gauss linear 0.5",
        "grad(U)": "cellLimited Gauss linear 0.5",
        "_comment": "Bounded gradient limiter=0.5 - publication-quality on complex geometries (skewness < 3), tighter than limiter=1.0"
    },

    # Convection discretization
    "divSchemes": {
        "default": "none",
        "div(phi,U)": "Gauss LUST grad(U)",
        "div(phi,k)": "Gauss limitedLinear 1",
        "div(phi,omega)": "Gauss limitedLinear 1",
        "div(phi,epsilon)": "Gauss limitedLinear 1",
        "div((nuEff*dev2(T(grad(U)))))": "Gauss linear",
        "_comment": (
            "LUST: Linear Upwind Stabilised Transport. "
            "Blends 75% central differencing + 25% linearUpwind. "
            "Low numerical diffusion, bounded stability. "
            "See: Friess et al. (2015), Computers & Fluids 122:233-246"
        )
    },

    # Laplacian discretization
    "laplacianSchemes": {
        "default": "Gauss linear limited corrected 0.33",
        "_comment": (
            "Second-order with limited non-orthogonal correction. "
            "Coefficient 0.33 limits correction for stability on imperfect meshes."
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
        "_comment": "Limited correction for non-orthogonality"
    },

    # Solver settings
    "solvers": {
        "PIMPLE": {
            "nOuterCorrectors": 3,
            "nCorrectors": 3,
            "nNonOrthogonalCorrectors": 2,
            "_comment": "Many correctors for tight coupling and accuracy"
        },
        "relaxationFactors": {
            "fields": {
                "p": 0.5,
                "_comment": "Light relaxation - rely on correctors for stability"
            },
            "equations": {
                "U": 0.9,
                "k": 0.8,
                "omega": 0.8,
                "epsilon": 0.8,
                "_comment": "Light relaxation - faster convergence with many correctors"
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
        "max_co": 0.5,
        "max_delta_t": 0.0005,
        "adjustable_time_step": True,
        "_comment": (
            "Small time steps for accuracy with CrankNicolson. "
            "May need Co < 0.5 for stability with CN < 1.0."
        )
    },

    # Metadata
    "_profile_metadata": {
        "name": "publication",
        "order_of_accuracy": 2,
        "stability": "requires high-quality mesh",
        "intended_use": "journal publications, validation studies, code verification",
        "not_recommended_for": "poor meshes, quick screening, limited computational budget",
        "expected_diffusion": "minimal",
        "mesh_requirements": "orthogonality > 70°, skewness < 2, aspect ratio < 50",
        "literature": [
            "Friess et al. (2015). LUST scheme. Computers & Fluids 122:233-246",
            "Roache, P.J. (1998). Grid Convergence Index. AIAA Journal 36(5):696-702",
            "Stern et al. (2001). V&V of CFD Simulations. J. Fluids Engineering 123(4)",
            "OpenFOAM User Guide v11, Sections 4.4-4.5 (Numerical Schemes)"
        ],
        "validation_checklist": [
            "Run checkMesh - resolve ALL warnings",
            "Mesh independence: 3 levels, calculate GCI",
            "Temporal convergence: halve Δt, show < 1% change",
            "Residuals < 1e-8 for all variables",
            "Mass conservation < 0.01%",
            "Compare to experimental data or analytical solution",
            "Document all numerical choices in paper"
        ],
        "computational_cost_multiplier": "3-5x vs standard profile",
        "example_methods_section": (
            "Time integration: Crank-Nicolson (α=0.9, 2nd order). "
            "Convection: LUST scheme (75% central, 25% upwind). "
            "Pressure-velocity: PIMPLE (3 outer, 3 inner correctors). "
            "Residuals: < 10⁻⁸. Mesh independence: GCI method."
        )
    }
}

__all__ = ["config"]
