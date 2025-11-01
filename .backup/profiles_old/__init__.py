"""Numeric profiles for OpenFOAM discretization schemes and solver settings.

OVERVIEW
========
Numeric profiles define discretization schemes, solver algorithms, and
convergence criteria INDEPENDENTLY from physics models and mesh resolution.

Each profile explicitly specifies:
- Time discretization (ddtSchemes)
- Convection schemes (divSchemes)
- Gradient, Laplacian, interpolation schemes
- PIMPLE/SIMPLE solver settings
- Under-relaxation factors
- Residual tolerances
- Time-stepping strategy

AVAILABLE PROFILES
==================

conservative
------------
First-order schemes, maximum stability.
USE FOR: Difficult cases, poor mesh quality, debugging
SCHEMES: Euler time, upwind convection
TRADE-OFF: Stable but diffusive (NOT publication quality)
COST: Low (heavy relaxation slows iterations, but cheap per iteration)

standard (RECOMMENDED DEFAULT)
-------------------------------
Second-order bounded schemes, production quality.
USE FOR: Most simulations, clinical studies
SCHEMES: backward time, linearUpwind/limitedLinear convection
TRADE-OFF: Good accuracy and stability balance
COST: Moderate (standard for most users)

publication
-----------
High-accuracy schemes, tight tolerances, journal quality.
USE FOR: Papers, validation studies, mesh independence
SCHEMES: CrankNicolson time, LUST convection, tight residuals (1e-8)
TRADE-OFF: Minimal diffusion, requires excellent mesh
COST: High (3-5x vs standard due to tight tolerances, many correctors)

aggressive (EXPERT ONLY)
------------------------
Unbounded central differencing, minimal dissipation.
USE FOR: Wall-resolved LES, DNS, turbulence research
SCHEMES: CrankNicolson 0.7, pure central (Gauss linear)
TRADE-OFF: No numerical diffusion, but UNSTABLE without strict requirements
COST: Very high (10-50x vs RANS, needs y+<1 mesh and Co<0.3)

PROFILE SELECTION GUIDE
=======================

┌─────────────────────────────────────────────────────────────────────┐
│ START: What is your objective?                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
   Quick test?         Production run?       Publication?
   New geometry?       Clinical study?       Validation?
        │                     │                     │
        ▼                     ▼                     ▼
  conservative            standard            publication
        │                     │                     │
        │                     │                     │
  Mesh quality OK?      Mesh quality OK?      Mesh excellent?
  No → Fix mesh         Yes → DONE            (ortho>70°, skew<2)
  Yes → Try standard                          Yes → DONE
                                              No → Fix mesh first

                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
              LES research?        RANS/Laminar?
              DNS?                      │
                    │                    │
              y+ < 1 mesh?              └→ Use publication
              ortho > 80°?
              Budget for
              10-50x cost?
                    │
                    ▼
              Yes → aggressive
              No → Use publication
                   or improve mesh

MESH QUALITY REQUIREMENTS
==========================

Profile        Orthogonality  Skewness  Aspect Ratio  y+ (RANS/LES)
-----------    -------------  --------  ------------  -------------
conservative   > 50°          < 4       < 200         Any
standard       > 60°          < 3       < 100         1-10 (RANS)
publication    > 70°          < 2       < 50          1-10 or <1
aggressive     > 80°          < 1       < 20          Must be <1

Run checkMesh before selecting profile!

LITERATURE GUIDANCE
===================

On first vs. second-order:
  "First order methods are bounded and stable but diffusive. Second order
   methods are accurate, but they might become oscillatory. At the end of
   the day, we always want a second order accurate solution."
   — Wolf Dynamics CFD Tips & Tricks

On numerical diffusion:
  "First-order schemes such as upwind are more stable but introduce numerical
   diffusion, smearing sharp gradients."
   — OpenFOAM User Guide v11, Section 4.4.2

On LES numerics:
  "For LES, central differencing is preferred to minimize numerical dissipation,
   which would interfere with subgrid-scale modeling."
   — Pope, S.B. (2000). Turbulent Flows. Cambridge University Press

On verification:
  "Always aim for second-order accurate solutions. Perform grid convergence
   studies using Richardson extrapolation or Grid Convergence Index."
   — Roache, P.J. (1998). Verification and Validation. AIAA Journal 36(5)

USAGE IN CONFIG
===============

Minimal (use profile defaults):
```json
{
  "numerics": {
    "profile": "standard"
  }
}
```

With high-level overrides (most users):
```json
{
  "numerics": {
    "profile": "standard",
    "max_co": 0.8,
    "correctors": {
      "nOuterCorrectors": 3
    }
  }
}
```

With expert patches (advanced):
```json
{
  "numerics": {
    "profile": "publication",
    "max_co": 0.5,
    "patches": {
      "divSchemes.div(phi,U)": "Gauss limitedLinearV 1.0",
      "solvers.PIMPLE.nNonOrthogonalCorrectors": 3
    }
  }
}
```

COMMON ISSUES
=============

Q: Solution diverges immediately
A: Mesh quality issue. Run checkMesh, fix warnings. Try conservative profile.

Q: Residuals oscillate around 1e-4
A: Increase correctors (nOuterCorrectors = 3-5) or reduce relaxation.

Q: Results are mesh-dependent
A: Using first-order schemes (conservative)? Switch to standard or publication.
   Perform mesh independence study at 1.5x refinement.

Q: LES shows no turbulence
A: Check: (1) Inlet BC has fluctuations, (2) Re is high enough,
   (3) Mesh resolves turbulence (cells_per_diameter ≥ 25)

Q: Need faster convergence
A: Check maxCo is appropriate (1.0 for standard, 0.5 for publication).
   Don't increase relaxation - makes steady-state convergence slower.

REFERENCES
==========

1. OpenFOAM User Guide v11
   https://doc.cfd.direct/openfoam/user-guide-v11/

2. Jasak, H. (1996). Error Analysis and Estimation for FVM
   PhD Thesis, Imperial College London

3. Roache, P.J. (1998). Verification of Codes and Calculations
   AIAA Journal, 36(5), 696-702

4. Pope, S.B. (2000). Turbulent Flows
   Cambridge University Press

5. Sagaut, P. (2006). Large Eddy Simulation for Incompressible Flows
   Springer, 3rd Edition

6. Ferziger, J.H., Peric, M. (2002). Computational Methods for Fluid Dynamics
   Springer, 3rd Edition

7. Wolf Dynamics (2015). CFD Tips and Tricks
   http://www.wolfdynamics.com/

8. Friess, C., Manceau, R., Gatski, T.B. (2015).
   Toward an equivalence criterion for hybrid RANS/LES methods
   Computers & Fluids, 122, 233-246 (LUST scheme)
"""

from .conservative import config as conservative_config
from .standard import config as standard_config
from .publication import config as publication_config
from .aggressive import config as aggressive_config

# NEW: Import renamed profiles
from .robust import config as robust_config
from .accurate import config as accurate_config
from .precise import config as precise_config

# Profile registry - NEW names (recommended)
NUMERICS_PROFILES = {
    # NEW NAMES (based on numerical properties)
    "robust": robust_config,        # 1st order bounded - max stability
    "accurate": accurate_config,    # 2nd order bounded - RECOMMENDED
    "precise": precise_config,      # 2nd order unbounded - high accuracy

    # OLD NAMES (deprecated, for backward compatibility)
    "conservative": conservative_config,  # DEPRECATED: use 'robust'
    "standard": standard_config,          # DEPRECATED: use 'accurate'
    "publication": publication_config,    # DEPRECATED: use 'precise'
    "aggressive": aggressive_config,      # DEPRECATED: use 'precise'
}

# Backward compatibility aliases
PROFILE_ALIASES = {
    "conservative": "robust",
    "standard": "accurate",
    "publication": "precise",
    "aggressive": "precise"
}

# Profile metadata for quick reference
PROFILE_METADATA = {
    name: profile["_profile_metadata"]
    for name, profile in NUMERICS_PROFILES.items()
}


def get_profile(name: str):
    """
    Get numeric profile configuration by name.

    Args:
        name: Profile name (robust, accurate, precise)
              OLD names (conservative, standard, publication) still work but deprecated

    Returns:
        Profile configuration dictionary

    Raises:
        ValueError: If profile name is unknown
    """
    import logging
    logger = logging.getLogger(__name__)

    # Check if using deprecated name
    if name in PROFILE_ALIASES:
        new_name = PROFILE_ALIASES[name]
        logger.warning(
            f"⚠️  Numerics profile '{name}' is DEPRECATED.\n"
            f"   Please use '{new_name}' instead.\n"
            f"   Mapping: conservative→robust, standard→accurate, publication→precise\n"
            f"   Old names will be removed in a future version."
        )

    if name not in NUMERICS_PROFILES:
        available = ", ".join([k for k in NUMERICS_PROFILES.keys() if k in ['robust', 'accurate', 'precise']])
        raise ValueError(
            f"Unknown numeric profile '{name}'. "
            f"Available profiles: {available}"
        )
    return NUMERICS_PROFILES[name]


def list_profiles():
    """
    List available numeric profiles with brief descriptions.

    Returns:
        Dictionary mapping profile names to metadata
    """
    return {
        name: {
            "order": meta["order_of_accuracy"],
            "stability": meta["stability"],
            "use": meta["intended_use"],
        }
        for name, meta in PROFILE_METADATA.items()
    }


def recommend_profile(mesh_quality: dict, objective: str = "production") -> str:
    """
    Recommend numeric profile based on mesh quality and objective.

    Args:
        mesh_quality: Dict with keys 'orthogonality', 'skewness'
        objective: One of 'debug', 'production', 'publication', 'les'

    Returns:
        Recommended profile name

    Example:
        >>> recommend_profile({'orthogonality': 65, 'skewness': 2.5}, 'production')
        'standard'
        >>> recommend_profile({'orthogonality': 55, 'skewness': 4}, 'production')
        'conservative'
    """
    ortho = mesh_quality.get("orthogonality", 0)
    skew = mesh_quality.get("skewness", 10)

    if objective == "debug":
        return "conservative"

    elif objective == "les":
        if ortho > 80 and skew < 1:
            return "aggressive"
        else:
            return "publication"  # Need better mesh for aggressive

    elif objective == "publication":
        if ortho > 70 and skew < 2:
            return "publication"
        else:
            return "standard"  # Mesh not good enough for publication profile

    else:  # production
        if ortho < 60 or skew > 3:
            return "conservative"
        else:
            return "standard"


__all__ = [
    "NUMERICS_PROFILES",
    "PROFILE_METADATA",
    "get_profile",
    "list_profiles",
    "recommend_profile",
    "conservative_config",
    "standard_config",
    "publication_config",
    "aggressive_config",
]
